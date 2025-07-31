from django.db import models

class WalletEntry(models.Model):
    PLATFORM_CHOICES = [
        ('daraz', 'Daraz'),
        ('bykea', 'Bykea'),
    ]
    platform = models.CharField(max_length=10, choices=PLATFORM_CHOICES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    transaction_date = models.DateField()

    def __str__(self):
        return f"{self.platform.capitalize()} - {self.amount}"
