from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q, Count, Avg, Sum, F
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.template.loader import render_to_string
from django.utils import timezone
from datetime import datetime
import openpyxl
from decimal import Decimal

from .models import InventoryItem, InventoryCategory, Supplier, InventoryHistory
from billing.models import Bill, BillItem

def dashboard(request):
    # Date range filtering for sales data and closed bills
    today = timezone.localdate()
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')

    if start_date_str:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
    else:
        start_date = today

    if end_date_str:
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    else:
        end_date = today

    # Date range filtering for sales data and closed bills
    today = timezone.localdate()
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')
    category_id = request.GET.get('category_id')
    item_name_search = request.GET.get('item_name')

    if start_date_str:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
    else:
        start_date = today

    if end_date_str:
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    else:
        end_date = today

    # Filter BillItems based on date range, category, and item name
    bill_items_query = BillItem.objects.filter(
        bill__status='closed',
        bill__closed_at__date__range=(start_date, end_date)
    ).select_related('item', 'bill__customer')

    if category_id:
        bill_items_query = bill_items_query.filter(item__category_id=category_id)

    if item_name_search:
        bill_items_query = bill_items_query.filter(
            Q(item__name__icontains=item_name_search) |
            Q(item__sku__icontains=item_name_search)
        )

    # Aggregate sales data for the selected filters
    sales_summary_for_range = {}
    for bill_item in bill_items_query:
        sku = bill_item.item.sku
        name = bill_item.item.name
        uom = bill_item.item.get_unit_of_measure_display()
        line_total = bill_item.get_line_total()

        if sku not in sales_summary_for_range:
            sales_summary_for_range[sku] = {
                'sku': sku,
                'name': name,
                'unit_of_measure': uom,
                'total_quantity_sold': Decimal(0),
                'total_revenue': Decimal(0)
            }
        sales_summary_for_range[sku]['total_quantity_sold'] += bill_item.quantity
        sales_summary_for_range[sku]['total_revenue'] += line_total

    sales_summary_list = list(sales_summary_for_range.values())

    # Fetch unique closed bills from the filtered bill_items_query
    closed_bills_ids = bill_items_query.values_list('bill_id', flat=True).distinct()
    closed_bills = Bill.objects.filter(id__in=closed_bills_ids).select_related('customer').order_by('-closed_at')

    # Pagination for closed bills
    bills_paginator = Paginator(closed_bills, 5)
    bills_page_number = request.GET.get('bills_page', 1)
    try:
        bills_page = bills_paginator.page(bills_page_number)
    except PageNotAnInteger:
        bills_page = bills_paginator.page(1)
    except EmptyPage:
        bills_page = bills_paginator.page(bills_paginator.num_pages)

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        # Prepare data for AJAX response
        sales_summary_data = sales_summary_list
        closed_bills_data = [{
            'id': bill.id,
            'bill_number': bill.bill_number,
            'customer_name': bill.customer.name if bill.customer else 'N/A',
            'total_amount': str(bill.total_amount),
            'amount_paid': str(bill.amount_paid),
            'online_amount_paid': str(bill.online_amount_paid),
            'closed_at': bill.closed_at.isoformat() if bill.closed_at else None,
        } for bill in bills_page]
        
        pagination_html = render_to_string('stock/pagination.html', {'page_obj': bills_page})
        
        return JsonResponse({
            'sales_summary_for_range': sales_summary_data,
            'closed_bills': {
                'data': closed_bills_data,
                'pagination_html': pagination_html
            }
        })

    context = {
        'categories': InventoryCategory.objects.all(),
        'suppliers': Supplier.objects.all(),
        'unit_of_measure_choices': InventoryItem.UNIT_OF_MEASURE_CHOICES,
        'selected_page': 'dashboard',
        'sales_summary_for_range': sales_summary_list, # Initial load
        'closed_bills': bills_page, # Initial load
        'start_date': start_date.strftime('%Y-%m-%d'),
        'end_date': end_date.strftime('%Y-%m-%d'),
        'selected_category_id': category_id, # Pass selected category to template
        'search_item_name': item_name_search, # Pass search term to template
    }
    return render(request, 'stock/dashboard.html', context)

def stock_items(request):
    if request.method == 'POST':
        item_id = request.POST.get('item_id')
        category_id = request.POST.get('category')

        category = get_object_or_404(InventoryCategory, pk=category_id) if category_id else None

        item_data = {
            'name': request.POST.get('name'),
            'sku': request.POST.get('sku'),
            'category': category,
            'unit_of_measure': request.POST.get('unit_of_measure'),
            'is_sold_in_kgs': 'is_sold_in_kgs' in request.POST,
            'sale_price': request.POST.get('sale_price'), # Add sale_price
        }

        if item_id:
            item = get_object_or_404(InventoryItem, pk=item_id)
            # Only update sale_price. last_system_sale_price should only be updated by system actions (e.g., restore or initial creation).
            InventoryItem.objects.filter(pk=item_id).update(**item_data)
        else:
            # For new items, set last_system_sale_price to the initial sale_price
            item_data['last_system_sale_price'] = item_data['sale_price']
            InventoryItem.objects.create(**item_data)
        
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'message': 'Item saved successfully.'})
        return redirect('stock_items')

    # GET request handling
    items_list = InventoryItem.objects.select_related('category').order_by('-id')
    
    category_id = request.GET.get('category_id')
    if category_id:
        items_list = items_list.filter(category_id=category_id)

    search_term = request.GET.get('item_name')
    if search_term:
        items_list = items_list.filter(Q(name__icontains=search_term) | Q(sku__icontains=search_term))

    paginator = Paginator(items_list, 10)
    page_number = request.GET.get('page', 1)

    try:
        items_page = paginator.page(page_number)
    except PageNotAnInteger:
        items_page = paginator.page(1)
    except EmptyPage:
        items_page = paginator.page(paginator.num_pages)

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        items_data = [{
            'id': item.id, 'sku': item.sku, 'name': item.name,
            'category_name': item.category.name, 
            'total_stock_quantity': item.total_stock_quantity,
            'unit_of_measure': item.get_unit_of_measure_display(),
            'sale_price': str(item.sale_price),
        } for item in items_page]
        
        pagination_html = render_to_string('stock/pagination.html', {'page_obj': items_page}) # Pass page_obj
        return JsonResponse({'items': items_data, 'pagination_html': pagination_html})

    context = {
        'items': items_page,
        'categories': InventoryCategory.objects.all(),
        'suppliers': Supplier.objects.all(),
        'unit_of_measure_choices': InventoryItem.UNIT_OF_MEASURE_CHOICES,
        'page_obj': items_page, # Pass the Page object directly
        'selected_page': 'stock_items'
    }
    return render(request, 'stock/items.html', context)


def item_detail(request, item_id):
    item = get_object_or_404(InventoryItem, pk=item_id)
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        data = {
            'id': item.id, 'name': item.name, 'sku': item.sku,
            'category_id': item.category_id,
            'category_name': item.category.name,
            'total_stock_quantity': item.total_stock_quantity,
            'unit_of_measure': item.unit_of_measure,
            'is_sold_in_kgs': item.is_sold_in_kgs,
            'sale_price': str(item.sale_price),
            'last_system_sale_price': str(item.last_system_sale_price), # Include last_system_sale_price
        }
        return JsonResponse(data)
    return redirect('stock_items')

def restore_item(request):
    if request.method == 'POST' and request.headers.get('x-requested-with') == 'XMLHttpRequest':
        item_id = request.POST.get('item_id')
        quantity = Decimal(request.POST.get('quantity'))
        unit_price = request.POST.get('unit_price')
        retail_price_per_unit = request.POST.get('retail_price_per_unit')
        supplier_id = request.POST.get('supplier')
        expiry_date = request.POST.get('expiry_date') or None

        item = get_object_or_404(InventoryItem, pk=item_id)
        supplier = get_object_or_404(Supplier, pk=supplier_id) if supplier_id else None

        # Update total stock quantity
        item.total_stock_quantity += quantity
        item.save()

        # Create history entry
        InventoryHistory.objects.create(
            item=item,
            quantity=quantity,
            unit_price=unit_price,
            retail_price_per_unit=retail_price_per_unit,
            supplier=supplier,
            expiry_date=expiry_date
        )

        # Set sale_price to the retail_price_per_unit provided in the restore form
        item.sale_price = retail_price_per_unit
        item.last_system_sale_price = retail_price_per_unit # Also update last_system_sale_price on restore
        item.save()

        return JsonResponse({'success': True, 'message': 'Item restored successfully.'})
    return JsonResponse({'success': False, 'error': 'Invalid request'}, status=400)

def item_history(request, item_id):
    item = get_object_or_404(InventoryItem, pk=item_id)
    history_list = item.history.select_related('supplier').order_by('-timestamp')

    paginator = Paginator(history_list, 5)  # Paginate by 5 items per page
    page_number = request.GET.get('page', 1)
    try:
        history_page = paginator.page(page_number)
    except PageNotAnInteger:
        history_page = paginator.page(1)
    except EmptyPage:
        history_page = paginator.page(paginator.num_pages)

    history_data = [{
        'quantity': entry.quantity,
        'unit_price': str(entry.unit_price),
        'retail_price_per_unit': str(entry.retail_price_per_unit),
        'supplier_name': entry.supplier.name if entry.supplier else None,
        'expiry_date': entry.expiry_date.strftime('%Y-%m-%d') if entry.expiry_date else None,
        'timestamp': entry.timestamp.isoformat(),
    } for entry in history_page]

    pagination_html = render_to_string('stock/pagination.html', {'page_obj': history_page})

    return JsonResponse({
        'item_name': item.name,
        'history': history_data,
        'pagination_html': pagination_html
    })


def delete_item(request, item_id):
    if request.method == 'POST' and request.headers.get('x-requested-with') == 'XMLHttpRequest':
        item = get_object_or_404(InventoryItem, pk=item_id)
        item.delete()
        return JsonResponse({'success': True})
    return JsonResponse({'success': False, 'error': 'Invalid request'}, status=400)


def export_items(request):
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename=inventory_items.xlsx'
    
    workbook = openpyxl.Workbook()
    worksheet = workbook.active
    worksheet.title = 'Inventory Items'
    
    columns = ['SKU', 'Name', 'Category', 'Total Stock Quantity', 'Unit of Measure', 'Sale Price']
    worksheet.append(columns)
    
    items = InventoryItem.objects.select_related('category').all()
    for item in items:
        worksheet.append([
            item.sku, item.name, item.category.name, item.total_stock_quantity, item.get_unit_of_measure_display(),
            item.sale_price,
        ])
        
    workbook.save(response)
    return response

def export_history(request, item_id):
    item = get_object_or_404(InventoryItem, pk=item_id)
    history_list = item.history.select_related('supplier').order_by('-timestamp')

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename=item_{item_id}_history.xlsx'
    
    workbook = openpyxl.Workbook()
    worksheet = workbook.active
    worksheet.title = f'History for {item.name}'
    
    columns = ['Date', 'Quantity', 'Purchase Price', 'Retail Price', 'Supplier', 'Expiry Date']
    worksheet.append(columns)
    
    for entry in history_list:
        worksheet.append([
            entry.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            entry.quantity,
            entry.unit_price,
            entry.retail_price_per_unit,
            entry.supplier.name if entry.supplier else 'N/A',
            entry.expiry_date.strftime('%Y-%m-%d') if entry.expiry_date else 'N/A'
        ])
        
    workbook.save(response)
    return response

def inventory_categories(request):
    if request.method == 'POST':
        category_id = request.POST.get('category_id')
        name = request.POST.get('name')
        if category_id:
            category = get_object_or_404(InventoryCategory, pk=category_id)
            category.name = name
            category.save()
        else:
            InventoryCategory.objects.create(name=name)
        return redirect('inventory_categories')

    categories = InventoryCategory.objects.annotate(item_count=Count('inventoryitem')).order_by('name')
    return render(request, 'stock/categories.html', {'categories': categories, 'selected_page': 'inventory_categories'})


def delete_category(request, category_id):
    if request.method == 'POST' and request.headers.get('x-requested-with') == 'XMLHttpRequest':
        category = get_object_or_404(InventoryCategory, pk=category_id)
        category.delete()
        return JsonResponse({'success': True})
    return JsonResponse({'success': False, 'error': 'Invalid request'}, status=400)
