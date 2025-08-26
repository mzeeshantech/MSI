from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from django.db.models import Q
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.http import HttpResponse
import json
from decimal import Decimal
import openpyxl
from openpyxl.styles import Font, Border, Side, Alignment
from weasyprint import HTML
from django.template.loader import render_to_string

from stock.models import InventoryItem, InventoryCategory
from .models import Bill, BillItem, Customer

@csrf_exempt
def bulk_delete_bills(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            bill_ids = data.get('bill_ids', [])

            if not bill_ids:
                return JsonResponse({'success': False, 'error': 'No bill IDs provided.'}, status=400)

            with transaction.atomic():
                deleted_count = 0
                for bill_id in bill_ids:
                    try:
                        bill = Bill.objects.get(id=bill_id)
                        # Restore stock for each item in the bill
                        for bill_item in bill.items.all():
                            inventory_item = bill_item.item
                            inventory_item.total_stock_quantity += bill_item.quantity
                            inventory_item.save()
                        bill.delete()
                        deleted_count += 1
                    except Bill.DoesNotExist:
                        # Optionally log or handle bills that don't exist
                        pass
                return JsonResponse({'success': True, 'message': f'{deleted_count} bill(s) deleted successfully!'})
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Invalid JSON data.'}, status=400)
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
    return JsonResponse({'error': 'Invalid request method'}, status=400)

def generate_bill_pdf(request, bill_id):
    bill = get_object_or_404(Bill, id=bill_id)
    
    context = {
        'bill': bill,
        'bill_items': bill.items.all(),
    }
    
    pdf_type = request.GET.get('type', 'default')
    if pdf_type == 'customer':
        template_name = 'billing/customer_bill_detail.html'
        filename = f'customer_bill_{bill.bill_number}.pdf'
    else:
        template_name = 'billing/bill_detail.html'
        filename = f'bill_{bill.bill_number}.pdf'

    html_string = render_to_string(template_name, context)
    
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{filename}"'
    
    pdf_file = HTML(string=html_string, base_url=request.build_absolute_uri('/')).write_pdf()
    response.write(pdf_file)
    
    return response

@csrf_exempt
def mark_bill_closed(request, bill_id):
    if request.method == 'POST':
        try:
            bill = get_object_or_404(Bill, id=bill_id)
            if bill.status == 'closed':
                return JsonResponse({'success': False, 'message': 'Bill is already closed.'}, status=400)
            
            data = json.loads(request.body)
            cash_received = Decimal(data.get('cash_received', 0))
            online_received = Decimal(data.get('online_received', 0))
            payment_method = data.get('payment_method', 'cash')
            rent_amount = Decimal(data.get('rent_amount', 0))
            rent_payer = data.get('rent_payer', 'customer')
            rent_customer_amount = Decimal(data.get('rent_customer_amount', 0))
            rent_company_amount = Decimal(data.get('rent_company_amount', 0))

            # Deduct stock for each item in the bill
            if bill.status != 'paid_later':
                for bill_item in bill.items.all():
                    inventory_item = bill_item.item
                    if inventory_item.total_stock_quantity < bill_item.quantity:
                        return JsonResponse({'success': False, 'message': f'Not enough stock for {inventory_item.name} to close the bill. Available: {inventory_item.total_stock_quantity}'}, status=400)
                    inventory_item.total_stock_quantity -= bill_item.quantity
                    inventory_item.save()
            
            bill.amount_paid = cash_received
            bill.online_amount_paid = online_received
            bill.payment_method = payment_method
            bill.rent_amount = rent_amount
            bill.rent_payer = rent_payer
            bill.rent_customer_amount = rent_customer_amount
            bill.rent_company_amount = rent_company_amount
            bill.status = 'closed'
            bill.save()
            return JsonResponse({'success': True, 'message': 'Bill marked as closed successfully!'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)
    return JsonResponse({'error': 'Invalid request method'}, status=400)

def export_bills_excel(request):
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="bills.xlsx"'

    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Bills"

    # Define headers
    headers = [
        "Bill No.", "Customer Name", "Date", "Grand Total", "Rent Amount",
        "Cash Received", "Online Received", "Payment Method", "Rent Payer",
        "Customer Rent Amount", "Company Rent Amount", "Bill Status"
    ]
    sheet.append(headers)

    # Apply bold style to headers
    header_font = Font(bold=True)
    for col_num, header_text in enumerate(headers, 1):
        cell = sheet.cell(row=1, column=col_num)
        cell.font = header_font
        cell.alignment = Alignment(horizontal='center', vertical='center')
        
    # Get all bills
    bills = Bill.objects.all().order_by('-created_at')

    # Populate data
    for bill in bills:
        row_data = [
            bill.bill_number,
            bill.customer.name,
            bill.created_at.strftime("%d %b, %Y"),
            float(bill.total_amount),
            float(bill.rent_amount),
            float(bill.amount_paid),
            float(bill.online_amount_paid),
            bill.get_payment_method_display(),
            bill.get_rent_payer_display(),
            float(bill.rent_customer_amount),
            float(bill.rent_company_amount),
            bill.get_status_display(),
        ]
        sheet.append(row_data)

    # Adjust column widths
    for col in sheet.columns:
        max_length = 0
        column = col[0].column_letter # Get the column name
        for cell in col:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass
        adjusted_width = (max_length + 2)
        sheet.column_dimensions[column].width = adjusted_width

    workbook.save(response)
    return response

def billing_home(request):
    bills_list = Bill.objects.all().filter(status__in=['open', 'closed']).order_by('-created_at')

    search_term = request.GET.get('search_term')

    if search_term:
        bills_list = bills_list.filter(
            Q(customer__name__icontains=search_term) |
            Q(bill_number__icontains=search_term)
        )

    paginator = Paginator(bills_list, 10) # Show 10 bills per page
    page = request.GET.get('page')

    try:
        bills = paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        bills = paginator.page(1)
    except EmptyPage:
        # If page is out of range (e.g. 9999), deliver last page of results.
        bills = paginator.page(paginator.num_pages)
    
    context = {
        'selected_page': 'billing',
        'bills': bills,
        'categories' : InventoryCategory.objects.all(),
        'page_obj': bills, # Pass page_obj to the context for initial load
    }

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        # If it's an AJAX request, return JSON response for table and pagination
        bills_data = []
        for bill in bills:
            bills_data.append({
                'id': bill.id,
                'bill_number': bill.bill_number,
                'customer__name': bill.customer.name,
                'created_at': bill.created_at.isoformat(),
                'total_amount': float(bill.total_amount),
                'amount_paid': float(bill.amount_paid),
                'rent_amount': float(bill.rent_amount),
                'status': bill.status,
                'get_status_display': bill.get_status_display(),
            })
        
        pagination_html = render(request, 'stock/pagination.html', {'page_obj': bills, 'request': request}).content.decode('utf-8')
        
        return JsonResponse({
            'bills': bills_data,
            'pagination_html': pagination_html
        })

    return render(request, 'billing/home.html', context)

def paid_later(request):
    bills_list = Bill.objects.filter(status='paid_later').order_by('-created_at')

    search_term = request.GET.get('search_term')

    if search_term:
        bills_list = bills_list.filter(
            Q(customer__name__icontains=search_term) |
            Q(bill_number__icontains=search_term)
        )

    paginator = Paginator(bills_list, 10)
    page = request.GET.get('page')

    try:
        bills = paginator.page(page)
    except PageNotAnInteger:
        bills = paginator.page(1)
    except EmptyPage:
        bills = paginator.page(paginator.num_pages)
    
    context = {
        'selected_page': 'paid_later',
        'bills': bills,
        'categories' : InventoryCategory.objects.all(),
        'page_obj': bills, # Pass page_obj to the context for initial load
    }

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        # If it's an AJAX request, return JSON response for table and pagination
        bills_data = []
        for bill in bills:
            bills_data.append({
                'id': bill.id,
                'bill_number': bill.bill_number,
                'customer__name': bill.customer.name,
                'created_at': bill.created_at.isoformat(),
                'total_amount': float(bill.total_amount),
                'amount_paid': float(bill.amount_paid),
                'rent_amount': float(bill.rent_amount),
                'status': bill.status,
                'get_status_display': bill.get_status_display(),
            })
        
        pagination_html = render(request, 'stock/pagination.html', {'page_obj': bills, 'request': request}).content.decode('utf-8')
        
        return JsonResponse({
            'bills': bills_data,
            'pagination_html': pagination_html
        })

    return render(request, 'billing/paid_later.html', context)

def bill_list(request):
    # This view might become redundant if billing_home handles all listing.
    # For now, keeping it as is, but it might be removed later.
    bills = Bill.objects.all()
    
    context = {
        'selected_page': 'billing',
        'bills' : bills
    }
    return render(request, 'billing/bills.html', context)

def bill_detail(request, bill_id):
    bill = get_object_or_404(Bill, id=bill_id)
    context = {
        'selected_page': 'billing',
        'bill' : bill
    }
    return render(request, 'billing/bill_detail.html', context)

@csrf_exempt
def get_skus_by_category(request, category_id):
    if request.method == 'GET':
        skus = InventoryItem.objects.filter(category_id=category_id).values('id', 'sku', 'name', 'sale_price', 'unit_of_measure', 'total_stock_quantity')
        return JsonResponse({'skus': list(skus)})
    return JsonResponse({'error': 'Invalid request method'}, status=400)

@csrf_exempt
def generate_bill(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            customer_name = data.get('customer_name')
            customer_cnic = data.get('customer_cnic')
            customer_phone = data.get('customer_phone')
            customer_address = data.get('customer_address')
            bill_items_data = data.get('bill_items', []) # bill_items is already a list, no need for json.loads again
            
            rent_amount = Decimal(data.get('rent_amount', 0))
            rent_payer = data.get('rent_payer', 'customer')
            rent_customer_amount = Decimal(data.get('rent_customer_amount', 0))
            rent_company_amount = Decimal(data.get('rent_company_amount', 0))
            payment_method = data.get('payment_method', 'cash')
            cash_received = Decimal(data.get('cash_received', 0))
            online_received = Decimal(data.get('online_received', 0))
            is_booking = data.get('is_booking', False)
            status = data.get('status', 'open')

            if not customer_name:
                return JsonResponse({'success': False, 'message': 'Customer name is required.'}, status=400)
            
            if not bill_items_data:
                return JsonResponse({'success': False, 'message': 'No items added to the bill.'}, status=400)

            with transaction.atomic():
                # Get or create customer
                customer, created = Customer.objects.get_or_create(
                    name=customer_name,
                    defaults={
                        'cnic': customer_cnic,
                        'phone': customer_phone,
                        'address': customer_address
                    }
                )
                if not created:
                    # Update customer details if customer already exists
                    customer.cnic = customer_cnic
                    customer.phone = customer_phone
                    customer.address = customer_address
                    customer.save()

                calculated_total_amount = Decimal(0)
                for item_data in bill_items_data:
                    retail_price = Decimal(str(item_data['retailPrice']))
                    quantity = Decimal(str(item_data['quantity']))
                    item_discount_type = item_data.get('itemDiscountType', 'none')
                    item_discount_amount = Decimal(str(item_data.get('itemDiscountAmount', 0)))

                    item_price_after_discount = retail_price
                    if item_discount_type == 'percentage':
                        item_price_after_discount -= (retail_price * (item_discount_amount / 100))
                    elif item_discount_type == 'fixed':
                        item_price_after_discount -= item_discount_amount
                    
                    calculated_total_amount += (quantity * item_price_after_discount)

                final_total = calculated_total_amount

                # Add rent based on payer
                if rent_payer == 'customer' or rent_payer == 'shared':
                    final_total += rent_amount
                elif rent_payer == 'both':
                    final_total += rent_customer_amount + rent_company_amount

                # Determine total amount paid based on payment method
                total_amount_paid = Decimal(0)
                if payment_method == 'cash':
                    total_amount_paid = cash_received
                elif payment_method == 'online':
                    total_amount_paid = online_received
                elif payment_method == 'both':
                    total_amount_paid = cash_received + online_received

                bill = Bill.objects.create(
                    customer=customer,
                    total_amount=final_total,
                    amount_paid=cash_received, # This is specifically cash received
                    online_amount_paid=online_received, # New field for online received
                    rent_amount=rent_amount,
                    rent_payer=rent_payer,
                    rent_customer_amount=rent_customer_amount, # New field
                    rent_company_amount=rent_company_amount, # New field
                    payment_method=payment_method,
                    status='advance' if is_booking else status
                )
                bill.bill_number = f"BILL-{bill.id:06d}" # Generate bill number based on ID
                bill.save()

                for item_data in bill_items_data:
                    item_id = item_data['itemId']
                    quantity = Decimal(str(item_data['quantity']))
                    retail_price = Decimal(str(item_data['retailPrice']))
                    item_discount_type = item_data.get('itemDiscountType', 'none')
                    item_discount_amount = Decimal(str(item_data.get('itemDiscountAmount', 0)))

                    inventory_item = get_object_or_404(InventoryItem, id=item_id)
                    
                    if inventory_item.total_stock_quantity < quantity:
                        transaction.set_rollback(True)
                        return JsonResponse({'success': False, 'message': f'Not enough stock for {inventory_item.name}. Available: {inventory_item.total_stock_quantity}'}, status=400)

                    BillItem.objects.create(
                        bill=bill,
                        item=inventory_item,
                        quantity=quantity,
                        price_per_unit=retail_price,
                        discount_type=item_discount_type,
                        discount_amount=item_discount_amount
                    )
                    if status == 'paid_later':
                        inventory_item.total_stock_quantity -= quantity
                        inventory_item.save()

            return JsonResponse({'success': True, 'message': 'Bill generated successfully!'})
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'message': 'Invalid JSON data.'}, status=400)
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)
    return JsonResponse({'error': 'Invalid request method'}, status=400)

@csrf_exempt
def get_bill_details(request, bill_id):
    if request.method == 'GET':
        try:
            bill = get_object_or_404(Bill, id=bill_id)
            bill_items_data = []
            for item in bill.items.all():
                bill_items_data.append({
                    'item_id': item.item.id,
                    'sku': item.item.sku,
                    'name': item.item.name,
                    'category_name': item.item.category.name,
                    'quantity': float(item.quantity),
                    'retail_price': float(item.price_per_unit),
                    'discount_type': item.discount_type,
                    'discount_amount': float(item.discount_amount),
                    'unit_of_measure': item.item.unit_of_measure,
                })

            customer_data = {
                'name': bill.customer.name,
                'cnic': bill.customer.cnic,
                'phone': bill.customer.phone,
                'address': bill.customer.address,
            }

            bill_data = {
                'id': bill.id,
                'customer': customer_data,
                'rent_amount': float(bill.rent_amount),
                'rent_payer': bill.rent_payer,
                'rent_customer_amount': float(bill.rent_customer_amount),
                'rent_company_amount': float(bill.rent_company_amount),
                'payment_method': bill.payment_method,
                'amount_paid': float(bill.amount_paid),
                'online_amount_paid': float(bill.online_amount_paid),
                'status': bill.status, # Include status
                'items': bill_items_data,
            }
            return JsonResponse({'success': True, 'bill': bill_data})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)
    return JsonResponse({'error': 'Invalid request method'}, status=400)

@csrf_exempt
def update_bill(request, bill_id):
    if request.method == 'PUT':
        try:
            data = json.loads(request.body)
            
            customer_name = data.get('customer_name')
            customer_cnic = data.get('customer_cnic')
            customer_phone = data.get('customer_phone')
            customer_address = data.get('customer_address')
            bill_items_data = data.get('bill_items', [])
            
            rent_amount = Decimal(data.get('rent_amount', 0))
            rent_payer = data.get('rent_payer', 'customer')
            rent_customer_amount = Decimal(data.get('rent_customer_amount', 0))
            rent_company_amount = Decimal(data.get('rent_company_amount', 0))
            payment_method = data.get('payment_method', 'cash')
            cash_received = Decimal(data.get('cash_received', 0))
            online_received = Decimal(data.get('online_received', 0))

            if not customer_name:
                return JsonResponse({'success': False, 'message': 'Customer name is required.'}, status=400)
            
            if not bill_items_data:
                return JsonResponse({'success': False, 'message': 'No items added to the bill.'}, status=400)

            with transaction.atomic():
                bill = get_object_or_404(Bill, id=bill_id)

                # Restore old stock quantities before updating
                for old_bill_item in bill.items.all():
                    inventory_item = old_bill_item.item
                    inventory_item.total_stock_quantity += old_bill_item.quantity
                    inventory_item.save()
                
                # Clear existing bill items
                bill.items.all().delete();

                # Update customer
                customer, created = Customer.objects.get_or_create(
                    name=customer_name,
                    defaults={
                        'cnic': customer_cnic,
                        'phone': customer_phone,
                        'address': customer_address
                    }
                )
                if not created:
                    customer.cnic = customer_cnic
                    customer.phone = customer_phone
                    customer.address = customer_address
                    customer.save()

                calculated_total_amount = Decimal(0)
                for item_data in bill_items_data:
                    retail_price = Decimal(str(item_data['retailPrice']))
                    quantity = Decimal(str(item_data['quantity']))
                    item_discount_type = item_data.get('itemDiscountType', 'none')
                    item_discount_amount = Decimal(str(item_data.get('itemDiscountAmount', 0)))

                    item_price_after_discount = retail_price
                    if item_discount_type == 'percentage':
                        item_price_after_discount -= (retail_price * (item_discount_amount / 100))
                    elif item_discount_type == 'fixed':
                        item_price_after_discount -= item_discount_amount
                    
                    calculated_total_amount += (quantity * item_price_after_discount)

                final_total = calculated_total_amount

                # Add rent based on payer
                if rent_payer == 'customer' or rent_payer == 'shared':
                    final_total += rent_amount
                elif rent_payer == 'both':
                    final_total += rent_customer_amount + rent_company_amount

                # Update bill details
                bill.customer = customer
                bill.total_amount = final_total
                bill.amount_paid = cash_received
                bill.online_amount_paid = online_received
                bill.rent_amount = rent_amount
                bill.rent_payer = rent_payer
                bill.rent_customer_amount = rent_customer_amount
                bill.rent_company_amount = rent_company_amount
                bill.payment_method = payment_method
                bill.save()

                for item_data in bill_items_data:
                    item_id = item_data['itemId']
                    quantity = Decimal(str(item_data['quantity']))
                    retail_price = Decimal(str(item_data['retailPrice']))
                    item_discount_type = item_data.get('itemDiscountType', 'none')
                    item_discount_amount = Decimal(str(item_data.get('itemDiscountAmount', 0)))

                    inventory_item = get_object_or_404(InventoryItem, id=item_id)
                    
                    # Check stock before creating new BillItem and deducting
                    if bill.status == 'paid_later': # Deduct stock for paid_later and advance bills immediately
                        if inventory_item.total_stock_quantity < quantity:
                            transaction.set_rollback(True)
                            return JsonResponse({'success': False, 'message': f'Not enough stock for {inventory_item.name}. Available: {inventory_item.total_stock_quantity}'}, status=400)

                    BillItem.objects.create(
                        bill=bill,
                        item=inventory_item,
                        quantity=quantity,
                        price_per_unit=retail_price,
                        discount_type=item_discount_type,
                        discount_amount=item_discount_amount
                    )
                    
                    # Deduct stock for new items if the bill is 'paid_later' or 'advance'
                    if bill.status == 'paid_later':
                        inventory_item.total_stock_quantity -= quantity
                        inventory_item.save()

            return JsonResponse({'success': True, 'message': 'Bill updated successfully!'})
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'message': 'Invalid JSON data.'}, status=400)
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)
    return JsonResponse({'error': 'Invalid request method'}, status=400)

@csrf_exempt
def delete_bill(request, bill_id):
    if request.method == 'POST':
        try:
            bill = get_object_or_404(Bill, id=bill_id)
            with transaction.atomic():
                # Restore stock for each item in the bill
                for bill_item in bill.items.all():
                    inventory_item = bill_item.item
                    inventory_item.total_stock_quantity += bill_item.quantity
                    inventory_item.save()
                bill.delete()
            return JsonResponse({'success': True, 'message': 'Bill deleted successfully!'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)
    return JsonResponse({'error': 'Invalid request method'}, status=400)

def advance_booking_view(request):
    bills_list = Bill.objects.filter(status='advance').order_by('-created_at')

    search_term = request.GET.get('search_term')

    if search_term:
        bills_list = bills_list.filter(
            Q(customer__name__icontains=search_term) |
            Q(bill_number__icontains=search_term)
        )

    paginator = Paginator(bills_list, 10)
    page = request.GET.get('page')

    try:
        bills = paginator.page(page)
    except PageNotAnInteger:
        bills = paginator.page(1)
    except EmptyPage:
        bills = paginator.page(paginator.num_pages)
    
    context = {
        'selected_page': 'advance_booking',
        'bills': bills,
        'categories' : InventoryCategory.objects.all(),
        'page_obj': bills,
    }

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        # If it's an AJAX request, return JSON response for table and pagination
        bills_data = []
        for bill in bills:
            bills_data.append({
                'id': bill.id,
                'bill_number': bill.bill_number,
                'customer__name': bill.customer.name,
                'created_at': bill.created_at.isoformat(),
                'total_amount': float(bill.total_amount),
                'amount_paid': float(bill.amount_paid),
                'rent_amount': float(bill.rent_amount),
                'status': bill.status,
                'get_status_display': bill.get_status_display(),
            })
        
        pagination_html = render(request, 'stock/pagination.html', {'page_obj': bills, 'request': request}).content.decode('utf-8')
        
        return JsonResponse({
            'bills': bills_data,
            'pagination_html': pagination_html
        })

    return render(request, 'billing/home.html', context)
