from django.db import models

class Wallet(models.Model):
    current_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    def __str__(self):
        return f"Current Wallet Balance: {self.current_balance}"

class WalletEntry(models.Model):
    TRANSACTION_TYPE_CHOICES = [
        ('sale', 'Sale'),
        ('return', 'Return'),
        ('salary', 'Employee Salary'),
        ('expense', 'Other Expense'),
        ('deposit', 'Deposit'), # For initial funding or manual additions
        ('advance_salary', 'Advance Salary'),
        ('other', 'Other Transaction'),
    ]
    
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPE_CHOICES, default='sale')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField(blank=True, null=True)
    transaction_date = models.DateField(auto_now_add=True)
    balance_after_transaction = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)

    def __str__(self):
        return f"{self.transaction_type.capitalize()} - {self.amount} on {self.transaction_date}"

    class Meta:
        ordering = ['-transaction_date']
