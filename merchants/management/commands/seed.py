from django.core.management.base import BaseCommand
from merchants.models import Merchant
from ledger.models import Ledger


SEED_DATA = [
    {
        "name": "Acme Agency",
        "credits": [500000, 300000, 200000],  # 10000 INR total in paise
    },
    {
        "name": "Freelancer Hub",
        "credits": [750000, 250000],  # 10000 INR total
    },
    {
        "name": "Digital Studio",
        "credits": [1000000, 500000, 500000],  # 20000 INR total
    },
]


class Command(BaseCommand):
    help = "Seed database with merchants and credit history"

    def handle(self, *args, **kwargs):
        for data in SEED_DATA:
            merchant, created = Merchant.objects.get_or_create(name=data["name"])
            if created:
                for amount in data["credits"]:
                    Ledger.objects.create(merchant=merchant, amount=amount, type='credit')
                self.stdout.write(self.style.SUCCESS(
                    f"Created {merchant.name} with {sum(data['credits'])} paise credit"
                ))
            else:
                self.stdout.write(f"Skipped {merchant.name} — already exists")
