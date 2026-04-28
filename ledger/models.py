from django.db import models
from merchants.models import Merchant

# Create your models here.
class Ledger(models.Model):
    Transaction_Type = [('credit', 'Credit'), ('debit', 'Debit')]

    merchant = models.ForeignKey(Merchant, on_delete=models.CASCADE)
    amount = models.BigIntegerField(default=0)
    type = models.CharField(max_length=10, choices=Transaction_Type)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.merchant} - {self.type} - {self.amount}'

