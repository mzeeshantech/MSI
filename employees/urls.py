from django.urls import path
from . import views

urlpatterns = [
    path('', views.employees_home, name='employees_home'),
    path('add/', views.add_employee, name='add_employee'),
    path('edit/<int:employee_id>/', views.edit_employee, name='edit_employee'),
    path('delete/<int:employee_id>/', views.delete_employee, name='delete_employee'),
    path('advances/', views.employee_advances, name='employee_advances'),
    path('advances/grant/', views.grant_advance_salary, name='grant_advance_salary'),
    path('advance/<int:advance_id>/', views.advance_detail, name='advance_detail'),
]
