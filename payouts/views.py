from rest_framework.views import APIView
from rest_framework.response import Response
from django.db import transaction
from django.db.models import Sum, Case, When, F
from django.utils import timezone
from datetime import timedelta

from merchants.models import Merchant
from ledger.models import Ledger
from payouts.models import Payout, IdempotantKey
from payouts.tasks import process_payout
from payouts.serializers import PayoutSerializer


class PayoutView(APIView):

    def get(self, request):
        merchant_id = request.query_params.get('merchant')
        qs = Payout.objects.all().order_by('-created_at')
        if merchant_id:
            qs = qs.filter(merchant_id=merchant_id)
        return Response(PayoutSerializer(qs, many=True).data)

    def post(self, request):

        # Get data from request
        merchant_id = request.data.get('merchant_id')
        amount = request.data.get('amount')
        key = request.headers.get('Idempotency-Key')

        if not merchant_id or not amount or not key:
            return Response({"error": "merchant_id, amount, Idempotency-Key required"}, status=400)

        amount = int(amount)

        try:
            merchant = Merchant.objects.get(id=merchant_id)
        except Merchant.DoesNotExist:
            return Response({"error": "Invalid merchant"}, status=404)

        #Idempotency expiry check (24 hours)
        expiry_time = timezone.now() - timedelta(hours=24)

        existing_key = IdempotantKey.objects.filter(
            merchant=merchant,
            key=key,
            created_at__gte=expiry_time
        ).first()

        if existing_key:
            return Response(existing_key.response_data, status=200)

        #  Main transaction block
        with transaction.atomic():

            # Lock merchant row (concurrency)
            merchant = Merchant.objects.select_for_update().get(id=merchant.id)

            # Calculate balance
            balance = Ledger.objects.filter(merchant=merchant).aggregate(
                total_balance=Sum(
                    Case(
                        When(type='credit', then=F('amount')),
                        When(type='debit', then=-F('amount')),
                    )
                )
            )['total_balance'] or 0

            # Calculate held amount
            held = Payout.objects.filter(
                merchant=merchant,
                status__in=['pending', 'processing']
            ).aggregate(total=Sum('amount'))['total'] or 0

            available_balance = balance - held

            #Correct balance check
            if available_balance < amount:
                return Response({"error": "Insufficient balance"}, status=400)

            bank_account_id = request.data.get('bank_account_id', '')

            #Create payout
            payout = Payout.objects.create(
                merchant=merchant,
                amount=amount,
                status='pending',
                bank_account_id=bank_account_id
            )

            response_data = {
                "payout_id": payout.id,
                "amount": amount,
                "balance": balance
            }

            # Save idempotency key
            IdempotantKey.objects.create(
                merchant=merchant,
                key=key,
                response_data=response_data
            )

            # IMPORTANT → send task AFTER commit
            def send_task():
                process_payout.delay(payout.id)

            transaction.on_commit(send_task)

        return Response(response_data, status=200)