from django.db import models
from merchants.models import Merchant
# Create your models here.
class Payout(models.Model):

    choose_status = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed')
    ]

    merchant = models.ForeignKey(Merchant, on_delete=models.CASCADE)
    amount = models.BigIntegerField(default=0)

    bank_account_id = models.CharField(max_length=255, null=True, blank=True)

    status = models.CharField(max_length=20, choices=choose_status, default='pending')

    attempts = models.IntegerField(default=0)
    processing_started_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.merchant} - {self.amount}'


class IdempotantKey(models.Model):
    merchant = models.ForeignKey(Merchant, on_delete=models.CASCADE)
    response_data = models.JSONField()
    key = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('merchant', 'key')

    def __str__(self):
        return self.key
