from django.db import models

class InventoryCategory(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class Supplier(models.Model):
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)

    def __str__(self):
        return self.name


class InventoryItem(models.Model):
    UNIT_OF_MEASURE_CHOICES = [
        ('KG', 'Kilogram'),
        ('PIECE', 'Piece'),
    ]

    category = models.ForeignKey(InventoryCategory, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    sku = models.CharField(max_length=100, unique=True)
    total_stock_quantity = models.IntegerField(default=0)
    unit_of_measure = models.CharField(
        max_length=50,
        choices=UNIT_OF_MEASURE_CHOICES,
        default='KG'
    )
    is_sold_in_kgs = models.BooleanField(default=False)
    sale_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def __str__(self):
        return f"{self.name} ({self.sku})"


class InventoryHistory(models.Model):
    item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE, related_name='history')
    quantity = models.IntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)  # purchase price
    retail_price_per_unit = models.DecimalField(max_digits=10, decimal_places=2)
    expiry_date = models.DateField(null=True, blank=True)
    supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"History for {self.item.name} - {self.quantity} on {self.timestamp.strftime('%Y-%m-%d')}"
