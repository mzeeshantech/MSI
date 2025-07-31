from django.urls import path
from . import views

urlpatterns = [
    path('', views.expenses_home, name='expenses_home'),
    path('list/', views.expense_list, name='expense_list'),
]
