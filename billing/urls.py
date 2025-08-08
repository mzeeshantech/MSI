from django.urls import path
from . import views

urlpatterns = [
    path('', views.billing_home, name='billing_home'),
    path('bills/', views.bill_list, name='bill_list'),
    path('bills/<int:bill_id>/', views.bill_detail, name='bill_detail'),
    path('get_skus_by_category/<int:category_id>/', views.get_skus_by_category, name='get_skus_by_category'),
    path('generate_bill/', views.generate_bill, name='generate_bill'),
]
