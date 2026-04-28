import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from rest_framework.test import APIClient

from merchants.models import Merchant
from ledger.models import Ledger
from payouts.models import Payout, IdempotantKey


def make_merchant(name="Test Merchant", credit_paise=10000):
    merchant = Merchant.objects.create(name=name)
    Ledger.objects.create(merchant=merchant, amount=credit_paise, type='credit')
    return merchant


class IdempotencyTest(TestCase):
    """Same Idempotency-Key twice must return identical response and create only one payout."""

    def setUp(self):
        self.client = APIClient()
        self.merchant = make_merchant(credit_paise=10000)
        self.key = str(uuid.uuid4())

    def post_payout(self):
        return self.client.post(
            '/api/v1/payouts/',
            data={'merchant_id': self.merchant.id, 'amount': 5000, 'bank_account_id': 'HDFC001'},
            format='json',
            headers={'Idempotency-Key': self.key}
        )

    def test_same_key_returns_same_response(self):
        r1 = self.post_payout()
        r2 = self.post_payout()

        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r1.data, r2.data)

    def test_only_one_payout_created(self):
        self.post_payout()
        self.post_payout()
        self.assertEqual(Payout.objects.filter(merchant=self.merchant).count(), 1)

    def test_different_keys_create_separate_payouts(self):
        self.post_payout()

        self.key = str(uuid.uuid4())
        r2 = self.post_payout()

        self.assertEqual(r2.status_code, 200)
        self.assertEqual(Payout.objects.filter(merchant=self.merchant).count(), 2)


class ConcurrencyTest(TransactionTestCase):
    """Two simultaneous 6000 paise requests against 10000 paise balance — exactly one must succeed."""

    def setUp(self):
        self.client = APIClient()
        self.merchant = make_merchant(credit_paise=10000)

    def post_payout(self, amount=6000):
        key = str(uuid.uuid4())
        return self.client.post(
            '/api/v1/payouts/',
            data={'merchant_id': self.merchant.id, 'amount': amount, 'bank_account_id': 'HDFC001'},
            format='json',
            headers={'Idempotency-Key': key}
        )

    def _post_and_close(self, amount=6000):
        result = self.post_payout(amount)
        from django.db import connections
        for conn in connections.all():
            conn.close()
        return result

    def test_only_one_of_two_concurrent_requests_succeeds(self):
        results = []

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(self._post_and_close) for _ in range(2)]
            for f in as_completed(futures):
                results.append(f.result())

        statuses = [r.status_code for r in results]
        self.assertIn(200, statuses)
        self.assertIn(400, statuses)

        # Only one payout should exist
        self.assertEqual(Payout.objects.filter(merchant=self.merchant).count(), 1)

    def test_balance_never_goes_negative(self):
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(self._post_and_close) for _ in range(2)]
            for f in as_completed(futures):
                f.result()

        from django.db.models import Sum, Case, When, F
        balance = Ledger.objects.filter(merchant=self.merchant).aggregate(
            total=Sum(
                Case(
                    When(type='credit', then=F('amount')),
                    When(type='debit', then=-F('amount')),
                )
            )
        )['total'] or 0

        self.assertGreaterEqual(balance, 0)
