from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('items/', views.stock_items, name='stock_items'),
    path('categories/', views.inventory_categories, name='inventory_categories'),
    path('item_detail/<int:item_id>/', views.item_detail, name='item_detail'),
    path('delete_item/<int:item_id>/', views.delete_item, name='delete_item'),
    path('export_items/', views.export_items, name='export_items'),
    path('delete_category/<int:category_id>/', views.delete_category, name='delete_category'),
    path('restore_item/', views.restore_item, name='restore_item'),
    path('item_history/<int:item_id>/', views.item_history, name='item_history'),
    path('stock/export_history/<int:item_id>/', views.export_history, name='export_history'),
]
