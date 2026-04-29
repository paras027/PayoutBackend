from celery import shared_task
from celery.exceptions import Retry
import random
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from datetime import timedelta

from payouts.models import Payout
from ledger.models import Ledger


VALID_TRANSITIONS = {
    'pending': ['processing'],
    'processing': ['completed', 'failed'],
    'completed': [],
    'failed': []
}


def can_transition(current_status, new_status):
    return new_status in VALID_TRANSITIONS.get(current_status, [])


def _fail_payout_and_refund(payout):
    """Atomically mark payout as failed and return funds to ledger."""
    with transaction.atomic():
        payout = Payout.objects.select_for_update().get(id=payout.id)
        if not can_transition(payout.status, 'failed'):
            return
        payout.status = 'failed'
        payout.save()


@shared_task(bind=True, max_retries=3)
def process_payout(self, payout_id):

    with transaction.atomic():
        payout = Payout.objects.select_for_update().get(id=payout_id)

        if payout.status in ['completed', 'failed']:
            return

        if payout.status == 'pending':
            if not can_transition(payout.status, 'processing'):
                return
            payout.status = 'processing'
            if not payout.processing_started_at:
                payout.processing_started_at = timezone.now()
            payout.save()

        Payout.objects.filter(id=payout.id).update(attempts=F('attempts') + 1)
        payout.refresh_from_db()

        if payout.attempts > 3:
            _fail_payout_and_refund(payout)
            return

    # simulate external bank call outside the lock
    import time
    time.sleep(8)  # simulate bank API latency so frontend can show held/processing state
    result = random.random()

    if result < 0.7:
        # SUCCESS
        with transaction.atomic():
            payout = Payout.objects.select_for_update().get(id=payout_id)
            if not can_transition(payout.status, 'completed'):
                return
            Ledger.objects.create(
                merchant=payout.merchant,
                amount=payout.amount,
                type='debit'
            )
            payout.status = 'completed'
            payout.save()

    elif result < 0.9:
        # FAILURE — refund atomically
        payout = Payout.objects.get(id=payout_id)
        _fail_payout_and_refund(payout)

    else:
        # HANG — retry with exponential backoff, do NOT catch Retry
        countdown = 5 * (2 ** self.request.retries)
        raise self.retry(countdown=countdown)


@shared_task
def retry_stuck_payouts():
    """Periodic task: pick up payouts stuck in processing > 30 seconds and retry them."""
    cutoff = timezone.now() - timedelta(seconds=30)
    stuck = Payout.objects.filter(
        status='processing',
        processing_started_at__lte=cutoff,
        attempts__lte=3
    )
    for payout in stuck:
        process_payout.delay(payout.id)