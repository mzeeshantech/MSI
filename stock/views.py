from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q, Count, Avg
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.template.loader import render_to_string
import openpyxl

from .models import InventoryItem, InventoryCategory, Supplier, InventoryHistory

def dashboard(request):
    # GET request handling
    items_list = InventoryItem.objects.select_related('category').order_by('name')
    
    category_id = request.GET.get('category_id')
    if category_id:
        items_list = items_list.filter(category_id=category_id)

    search_term = request.GET.get('item_name')
    if search_term:
        items_list = items_list.filter(Q(name__icontains=search_term) | Q(sku__icontains=search_term))

    paginator = Paginator(items_list, 10)
    page_number = request.GET.get('page')
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
        
        pagination_html = render_to_string('stock/pagination.html', {'current_page': items_page, 'total_pages': items_page.paginator.num_pages})
        return JsonResponse({'items': items_data, 'pagination_html': pagination_html})

    context = {
        'items': items_page,
        'categories': InventoryCategory.objects.all(),
        'suppliers': Supplier.objects.all(),
        'unit_of_measure_choices': InventoryItem.UNIT_OF_MEASURE_CHOICES,
        'current_page': items_page.number,
        'total_pages': items_page.paginator.num_pages,
        'selected_page': 'dashboard'
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
        }

        if item_id:
            InventoryItem.objects.filter(pk=item_id).update(**item_data)
        else:
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
    page_number = request.GET.get('page')
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
        
        pagination_html = render_to_string('stock/pagination.html', {'current_page': items_page, 'total_pages': items_page.paginator.num_pages})
        return JsonResponse({'items': items_data, 'pagination_html': pagination_html})

    context = {
        'items': items_page,
        'categories': InventoryCategory.objects.all(),
        'suppliers': Supplier.objects.all(),
        'unit_of_measure_choices': InventoryItem.UNIT_OF_MEASURE_CHOICES,
        'current_page': items_page.number,
        'total_pages': items_page.paginator.num_pages,
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
        }
        return JsonResponse(data)
    return redirect('stock_items')

def restore_item(request):
    if request.method == 'POST' and request.headers.get('x-requested-with') == 'XMLHttpRequest':
        item_id = request.POST.get('item_id')
        quantity = int(request.POST.get('quantity'))
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

        # Calculate average retail price and update sale_price
        average_retail_price = item.history.aggregate(Avg('retail_price_per_unit'))['retail_price_per_unit__avg']
        if average_retail_price is not None:
            item.sale_price = average_retail_price
            item.save()

        return JsonResponse({'success': True, 'message': 'Item restored successfully.'})
    return JsonResponse({'success': False, 'error': 'Invalid request'}, status=400)

def item_history(request, item_id):
    item = get_object_or_404(InventoryItem, pk=item_id)
    history_list = item.history.select_related('supplier').order_by('-timestamp')

    history_data = [{
        'quantity': entry.quantity,
        'unit_price': str(entry.unit_price),
        'retail_price_per_unit': str(entry.retail_price_per_unit),
        'supplier_name': entry.supplier.name if entry.supplier else None,
        'expiry_date': entry.expiry_date.strftime('%Y-%m-%d') if entry.expiry_date else None,
        'timestamp': entry.timestamp.isoformat(),
    } for entry in history_list]

    return JsonResponse({'item_name': item.name, 'history': history_data})


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
