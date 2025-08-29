from django.db import models
from stock.models import InventoryItem
from decimal import Decimal

class Customer(models.Model):
    name = models.CharField(max_length=100)
    cnic = models.CharField(max_length=15, blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    address = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name


class Bill(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True)
    bill_number = models.CharField(max_length=50, unique=True, blank=True, null=True) # New field
    created_at = models.DateTimeField(auto_now_add=True)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    BILL_STATUS_CHOICES = [
        ('open', 'Open'),
        ('closed', 'Closed'),
        ('advance', 'Advance'),
        ('paid_later', 'Paid Later'),
    ]
    RENT_PAYER_CHOICES = [
        ('customer', 'Customer'),
        ('company', 'Company'),
        ('shared', 'Shared'),
        ('both', 'Both'),
    ]
    PAYMENT_METHOD_CHOICES = [
        ('cash', 'Cash'),
        ('online', 'Online'),
        ('both', 'Both'),
    ]

    rent_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    rent_payer = models.CharField(max_length=10, choices=RENT_PAYER_CHOICES, default='customer')
    rent_customer_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    rent_company_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    payment_method = models.CharField(max_length=10, choices=PAYMENT_METHOD_CHOICES, default='cash')
    online_amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=10, choices=BILL_STATUS_CHOICES, default='open')

    def __str__(self):
        return self.bill_number if self.bill_number else f"Bill #{self.id}"

    def get_items_total(self):
        total = Decimal(0)
        for item in self.items.all():
            total += item.get_line_total()
        return total

    def get_change_due(self):
        total_paid = self.amount_paid + self.online_amount_paid
        return total_paid - self.total_amount


class BillItem(models.Model):
    bill = models.ForeignKey(Bill, on_delete=models.CASCADE, related_name='items')
    item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    price_per_unit = models.DecimalField(max_digits=10, decimal_places=2)
    
    DISCOUNT_TYPE_CHOICES = [
        ('none', 'No Discount'),
        ('fixed', 'Fixed Amount'),
        ('percentage', 'Percentage (%)'),
    ]
    discount_type = models.CharField(max_length=10, choices=DISCOUNT_TYPE_CHOICES, default='none')
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def get_line_total(self):
        price_after_discount = self.price_per_unit
        if self.discount_type == 'percentage':
            price_after_discount -= (self.price_per_unit * (self.discount_amount / 100))
        elif self.discount_type == 'fixed':
            price_after_discount -= self.discount_amount
        return self.quantity * price_after_discount

    def __str__(self):
        return f"{self.item.name} x {self.quantity}"


class Return(models.Model):
    bill_item = models.ForeignKey(BillItem, on_delete=models.CASCADE)
    quantity_returned = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    reason = models.CharField(max_length=255, default='not used')

    def __str__(self):
        return f"Return: Bill {self.bill_item.bill.bill_number} - {self.bill_item.item.name} x {self.quantity_returned}"
