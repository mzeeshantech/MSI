from django.urls import path
from . import views

urlpatterns = [
    path('', views.billing_home, name='billing_home'),
    path('bills/', views.bill_list, name='bill_list'),
    path('bills/<int:bill_id>/', views.bill_detail, name='bill_detail'),
    path('get_skus_by_category/<int:category_id>/', views.get_skus_by_category, name='get_skus_by_category'),
    path('generate_bill/', views.generate_bill, name='generate_bill'),
    path('delete_bill/<int:bill_id>/', views.delete_bill, name='delete_bill'),
    path('get_bill_details/<int:bill_id>/', views.get_bill_details, name='get_bill_details'),
    path('update_bill/<int:bill_id>/', views.update_bill, name='update_bill'),
    path('mark_bill_closed/<int:bill_id>/', views.mark_bill_closed, name='mark_bill_closed'),
    path('export_bills_excel/', views.export_bills_excel, name='export_bills_excel'),
    path('bulk_delete_bills/', views.bulk_delete_bills, name='bulk_delete_bills'),
    path('generate_bill_pdf/<int:bill_id>/', views.generate_bill_pdf, name='generate_bill_pdf'),
]
