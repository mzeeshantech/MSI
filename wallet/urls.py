from django.urls import path
from . import views

urlpatterns = [
    path('', views.wallet_home, name='wallet_home'),
    path('wallet_entry_detail/<int:pk>/', views.wallet_entry_detail, name='wallet_entry_detail'),
    path('delete_wallet_entry/<int:pk>/', views.delete_wallet_entry, name='delete_wallet_entry'),
]
