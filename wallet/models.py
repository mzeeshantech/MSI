from django.db import models
from billing.models import Bill

class Wallet(models.Model):
    current_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    def __str__(self):
        return f"Current Wallet Balance: {self.current_balance}"

class DailyWalletSummary(models.Model):
    date = models.DateField(unique=True)
    start_balance = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    start_time = models.DateTimeField(null=True, blank=True)
    end_balance = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    def __str__(self):
        return f"Daily Summary for {self.date}: Start {self.start_balance}, End {self.end_balance}"

    class Meta:
        ordering = ['-date']

class WalletEntry(models.Model):
    TRANSACTION_TYPE_CHOICES = [
        ('sale', 'Sale'),
        ('return', 'Return'),
        ('salary', 'Employee Salary'),
        ('expense', 'Other Expense'),
        ('deposit', 'Deposit'), # For initial funding or manual additions
        ('advance_salary', 'Advance Salary'),
        ('rent', 'MSI Rent'),
        ('other', 'Other Transaction'),
    ]

    PAYMENT_MODE_CHOICES = [
        ('cash', 'Cash'),
        ('online', 'Online'),
        ('both', 'Both'),
    ]
    
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPE_CHOICES, default='sale')
    payment_mode = models.CharField(max_length=10, choices=PAYMENT_MODE_CHOICES, default='cash')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    cash_received = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, default=0.00)
    online_received = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, default=0.00)
    description = models.TextField(blank=True, null=True)
    transaction_date = models.DateField(auto_now_add=True)
    balance_after_transaction = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    bill = models.ForeignKey(Bill, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"{self.transaction_type} - {self.amount} ({self.payment_mode})"

    class Meta:
        ordering = ['-transaction_date']
