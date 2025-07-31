from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('stock.urls')),
    path('billing/', include('billing.urls')),
    path('expenses/', include('expenses.urls')),
    path('employees/', include('employees.urls')),
    path('reports/', include('reports.urls')),
    path('wallet/', include('wallet.urls')),
]
