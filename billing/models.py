from django.db import models
from stock.models import InventoryItem

class Customer(models.Model):
    name = models.CharField(max_length=100)
    cnic = models.CharField(max_length=15, blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    address = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name


class Bill(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    RENT_PAYER_CHOICES = [
        ('customer', 'Customer'),
        ('company', 'Company'),
        ('shared', 'Shared'),
    ]
    PAYMENT_METHOD_CHOICES = [
        ('cash', 'Cash'),
        ('online', 'Online'),
    ]

    rent_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    rent_payer = models.CharField(max_length=10, choices=RENT_PAYER_CHOICES, default='customer')
    payment_method = models.CharField(max_length=10, choices=PAYMENT_METHOD_CHOICES, default='cash')

    def __str__(self):
        return f"Bill #{self.id}"


class BillItem(models.Model):
    bill = models.ForeignKey(Bill, on_delete=models.CASCADE, related_name='items')
    item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE)
    quantity = models.IntegerField()
    price_per_unit = models.DecimalField(max_digits=10, decimal_places=2)
    
    DISCOUNT_TYPE_CHOICES = [
        ('none', 'No Discount'),
        ('fixed', 'Fixed Amount'),
        ('percentage', 'Percentage (%)'),
    ]
    discount_type = models.CharField(max_length=10, choices=DISCOUNT_TYPE_CHOICES, default='none')
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def __str__(self):
        return f"{self.item.name} x {self.quantity}"


class Return(models.Model):
    bill_item = models.ForeignKey(BillItem, on_delete=models.CASCADE)
    quantity_returned = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Return: {self.bill_item.item.name} - {self.quantity_returned}"
