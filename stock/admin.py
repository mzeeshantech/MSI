from django.contrib import admin
from .models import InventoryCategory, Supplier, InventoryItem

# Register your models here.
admin.site.register(InventoryCategory)
admin.site.register(Supplier)
admin.site.register(InventoryItem)
