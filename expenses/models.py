from django.db import models
from django.db import models
import datetime

class Expense(models.Model):
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    receipt = models.FileField(upload_to='receipts/', null=True, blank=True)
    created_at = models.DateTimeField(default=datetime.date.today)
    approved_by = models.CharField(max_length=255, default='Admin')

    def __str__(self):
        return f"{self.description} - {self.amount}"
