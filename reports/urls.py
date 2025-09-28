from django.urls import path
from . import views

urlpatterns = [
    path('', views.reports_home, name='reports_home'),
    path('download_report/', views.download_report, name='download_report'),
    path('get_categories/', views.get_categories, name='get_categories'),
    path('rent_report_pdf/', views.rent_report_pdf, name='rent_report_pdf'),
]
