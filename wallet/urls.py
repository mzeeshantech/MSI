from django.urls import path
from . import views

urlpatterns = [
    path('', views.wallet_home, name='wallet_home'),
    path('entries/', views.wallet_entries, name='wallet_entries'),
]
