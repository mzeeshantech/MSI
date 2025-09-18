from django.db import models
from stock.models import InventoryCategory, InventoryItem

class DailySaleSummary(models.Model):
    date = models.DateField(unique=True)
    category = models.ForeignKey(InventoryCategory, on_delete=models.CASCADE)
    sku = models.ForeignKey(InventoryItem, on_delete=models.CASCADE)
    total_sale_quantity = models.DecimalField(max_digits=10, decimal_places=2)
    average_rate = models.DecimalField(max_digits=10, decimal_places=2)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        unique_together = ('date', 'sku')
        verbose_name_plural = "Daily Sale Summaries"

    def __str__(self):
        return f"Daily Sale Summary for {self.date} - {self.sku.name}"
