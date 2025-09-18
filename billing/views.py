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
from .models import Bill, BillItem, Customer, Return
from datetime import datetime
from django.db.models import Case, When, Value, IntegerField
from wallet.models import WalletEntry, Wallet

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
        if bill.rent_payer == "both" or bill.rent_payer == "company":
            bill.rent_amount = bill.rent_amount - bill.rent_company_amount
            bill.total_amount = bill.total_amount - bill.rent_company_amount
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


def update_wallet_balance(amount, is_deduction=True):
    wallet = Wallet.objects.get_or_create(pk=1)[0]
    amount_decimal = Decimal(str(amount)) # Convert float to Decimal
    if is_deduction:
        wallet.current_balance -= amount_decimal
    else:
        wallet.current_balance += amount_decimal
    wallet.save()
    return wallet.current_balance

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

            with transaction.atomic():                
                # Deduct stock if not already deducted (i.e., if status was 'open' or 'advance')
                if bill.status not in ['paid_later', 'shipped_pending']:
                    for bill_item in bill.items.all():
                        inventory_item = bill_item.item
                        if inventory_item.total_stock_quantity < bill_item.quantity:
                            transaction.set_rollback(True)
                            return JsonResponse({'success': False, 'message': f'Not enough stock for {inventory_item.name} to close the bill. Available: {inventory_item.total_stock_quantity}'}, status=400)
                        inventory_item.total_stock_quantity -= bill_item.quantity
                        inventory_item.save()
                
                # Calculate additional payment received
                previous_total_paid = bill.amount_paid + bill.online_amount_paid
                current_total_paid = cash_received + online_received
                # additional_payment = current_total_paid - previous_total_paid
                additional_payment = current_total_paid

                bill.amount_paid = bill.amount_paid + cash_received
                bill.online_amount_paid = bill.online_amount_paid + online_received
                bill.payment_method = payment_method
                bill.rent_amount = rent_amount
                bill.rent_payer = rent_payer
                bill.rent_customer_amount = rent_customer_amount
                bill.rent_company_amount = rent_company_amount
                bill.closed_at = datetime.now()
                bill.status = 'closed'
                bill.remaining_charges = Decimal(0) # Set remaining charges to 0
                bill.save()

                # Add additional payment to wallet
                if additional_payment > 0:
                    new_balance = update_wallet_balance(additional_payment, False)
                    WalletEntry.objects.create(
                        transaction_type="sale",
                        amount=additional_payment,
                        description=f"Remaining payment for Bill {bill.bill_number} (Closed)",
                        balance_after_transaction=new_balance,
                        payment_mode=payment_method,
                        cash_received=cash_received,
                        online_received=online_received
                    )
                
            return JsonResponse({'success': True, 'message': 'Bill marked as closed successfully!'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)
            return JsonResponse({'error': 'Invalid request method'}, status=400)

@csrf_exempt
def mark_bill_shipped_pending(request, bill_id):
    if request.method == 'POST':
        try:
            bill = get_object_or_404(Bill, id=bill_id)
            if bill.status == 'shipped_pending':
                return JsonResponse({'success': False, 'message': 'Bill is already marked as Shipped/Charges Pending.'}, status=400)
            
            if bill.status == 'closed':
                return JsonResponse({'success': False, 'message': 'Cannot mark a closed bill as Shipped/Charges Pending.'}, status=400)

            data = json.loads(request.body)
            cash_received = Decimal(data.get('cash_received', 0))
            online_received = Decimal(data.get('online_received', 0))
            payment_method = data.get('payment_method', 'cash')
            rent_amount = Decimal(data.get('rent_amount', 0))
            rent_payer = data.get('rent_payer', 'customer')
            rent_customer_amount = Decimal(data.get('rent_customer_amount', 0))
            rent_company_amount = Decimal(data.get('rent_company_amount', 0))

            with transaction.atomic():
                # Deduct stock if not already deducted (i.e., if status was 'open' or 'advance')
                if bill.status not in ['paid_later', 'shipped_pending']:
                    for bill_item in bill.items.all():
                        inventory_item = bill_item.item
                        if inventory_item.total_stock_quantity < bill_item.quantity:
                            transaction.set_rollback(True)
                            return JsonResponse({'success': False, 'message': f'Not enough stock for {inventory_item.name}. Available: {inventory_item.total_stock_quantity}'}, status=400)
                        inventory_item.total_stock_quantity -= bill_item.quantity
                        inventory_item.save()
                
                # Calculate additional payment received
                previous_total_paid = bill.amount_paid + bill.online_amount_paid
                current_total_paid = cash_received + online_received
                # additional_payment = current_total_paid - previous_total_paid
                additional_payment = current_total_paid

                bill.amount_paid = cash_received
                bill.online_amount_paid = online_received
                bill.payment_method = payment_method
                bill.rent_amount = rent_amount
                bill.rent_payer = rent_payer
                bill.rent_customer_amount = rent_customer_amount
                bill.rent_company_amount = rent_company_amount
                bill.status = 'shipped_pending'
                bill.remaining_charges = bill.total_amount - (bill.amount_paid + bill.online_amount_paid)
                bill.save()

                # Add additional payment to wallet
                if additional_payment > 0:
                    new_balance = update_wallet_balance(additional_payment, False)
                    WalletEntry.objects.create(
                        transaction_type="sale",
                        amount=additional_payment,
                        description=f"Payment for Bill {bill.bill_number} (Shipped/Charges Pending)",
                        balance_after_transaction=new_balance,
                        payment_mode=payment_method,
                        cash_received=cash_received,
                        online_received=online_received
                    )
            
            return JsonResponse({'success': True, 'message': 'Bill marked as Shipped/Charges Pending successfully!'})
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
    bills_list = Bill.objects.filter(status__in=['open', 'closed', 'shipped_pending']).annotate(
        status_order=Case(
            When(status='open', then=Value(0)),
            When(status='shipped_pending', then=Value(1)),
            When(status='closed', then=Value(2)),
            output_field=IntegerField(),
        )
    ).order_by('status_order', '-id')

    search_term = request.GET.get('search_term')
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')

    if search_term:
        bills_list = bills_list.filter(
            Q(customer__name__icontains=search_term) |
            Q(bill_number__icontains=search_term)
        )

    if start_date_str:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        bills_list = bills_list.filter(created_at__date__gte=start_date)

    if end_date_str:
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        bills_list = bills_list.filter(created_at__date__lte=end_date)

    paginator = Paginator(bills_list, 10)
    page = request.GET.get('page')

    try:
        bills = paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        bills = paginator.page(1)
    except EmptyPage:
        # If page is out of range (e.g. 9999), deliver last page of results.
        bills = paginator.page(paginator.num_pages)
    

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
                'online_amount_paid': float(bill.online_amount_paid),
                'rent_amount': float(bill.rent_amount),
                'status': bill.status,
                'get_status_display': bill.get_status_display(),
                'bill_remaining_amount': float(bill.bill_remaining_amount) # Use the property
            })
        
        pagination_html = render(request, 'stock/pagination.html', {'page_obj': bills, 'request': request}).content.decode('utf-8')
        
        return JsonResponse({
            'bills': bills_data,
            'pagination_html': pagination_html
        })
    else:
        for bill in bills:
            # The property is already available on the model instance, no need to re-calculate
            pass 

    context = {
        'selected_page': 'billing',
        'bills': bills,
        'categories' : InventoryCategory.objects.all(),
        'page_obj': bills, # Pass page_obj to the context for initial load
    }

    return render(request, 'billing/home.html', context)

@csrf_exempt
def get_bill_items(request, bill_id):
    if request.method == 'GET':
        print(f"Received request for bill_id: {bill_id}")
        try:
            bill = get_object_or_404(Bill, id=bill_id)
            bill_items_data = []
            for item in bill.items.all():
                bill_items_data.append({
                    'id': item.id,
                    'name': item.item.name,
                    'quantity': float(item.quantity),
                    'unit_of_measure': item.item.unit_of_measure,
                })
            print(f"Returning {len(bill_items_data)} items for bill_id {bill_id}")
            return JsonResponse({'success': True, 'items': bill_items_data})
        except Bill.DoesNotExist:
            print(f"Bill with id {bill_id} not found.")
            return JsonResponse({'success': False, 'message': 'Bill not found.'}, status=404)
        except Exception as e:
            import traceback
            print(f"Error in get_bill_items for bill_id {bill_id}: {e}")
            print(traceback.format_exc())
            return JsonResponse({'success': False, 'message': str(e)}, status=500)
    return JsonResponse({'error': 'Invalid request method'}, status=400)

@csrf_exempt
def get_bill_details_by_number(request, bill_number):
    if request.method == 'GET':
        try:
            bill = get_object_or_404(Bill, bill_number=bill_number)
            bill_items_data = []
            for item in bill.items.all():
                bill_items_data.append({
                    'bill_item_id': item.id, # Add bill_item_id for return functionality
                    'item_id': item.item.id,
                    'sku': item.item.sku,
                    'name': item.item.name,
                    'category_name': item.item.category.name,
                    'category_id': item.item.category.id,
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
                'bill_number': bill.bill_number,
                'customer': customer_data,
                'rent_amount': float(bill.rent_amount),
                'rent_payer': bill.rent_payer,
                'rent_customer_amount': float(bill.rent_customer_amount),
                'rent_company_amount': float(bill.rent_company_amount),
                'payment_method': bill.payment_method,
                'amount_paid': float(bill.amount_paid),
                'online_amount_paid': float(bill.online_amount_paid),
                'status': bill.status,
                'items': bill_items_data,
            }
            return JsonResponse({'success': True, 'bill': bill_data})
        except Bill.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Bill not found.'}, status=404)
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)
    return JsonResponse({'error': 'Invalid request method'}, status=400)

@csrf_exempt
def return_item_view(request):
    import traceback
    if request.method == 'POST':
        try:
            data = json.loads(request.body) 
            bill_item_id = data.get('bill_item_id')
            quantity_returned = Decimal(str(data.get('quantity_returned')))
            reason = data.get('reason')

            with transaction.atomic():
                bill_item = get_object_or_404(BillItem, id=bill_item_id)
                bill = bill_item.bill

                if quantity_returned <= 0 or quantity_returned > bill_item.quantity:
                    print('first if')
                    return JsonResponse({'success': False, 'message': 'Invalid quantity for return.'}, status=400)

                # Calculate the amount to be removed from the wallet
                item_price_after_discount = bill_item.price_per_unit
                if bill_item.discount_type == 'percentage':
                    item_price_after_discount -= (bill_item.price_per_unit * (bill_item.discount_amount / 100))
                elif bill_item.discount_type == 'fixed':
                    item_price_after_discount -= bill_item.discount_amount
                
                amount_to_return = quantity_returned * item_price_after_discount

                # Create a new Return record
                Return.objects.create(
                    bill_item=bill_item,
                    quantity_returned=quantity_returned,
                    amount_returned=amount_to_return, # Save the calculated amount
                    reason=reason
                )

                # Update stock quantity
                inventory_item = bill_item.item
                inventory_item.total_stock_quantity += quantity_returned
                inventory_item.save()

                # Optionally, update the BillItem's quantity if partial return
                bill_item.quantity -= quantity_returned
                bill_item.save() # This line was missing in the previous change.

                # Calculate the amount to be removed from the wallet
                item_price_after_discount = bill_item.price_per_unit
                if bill_item.discount_type == 'percentage':
                    item_price_after_discount -= (bill_item.price_per_unit * (bill_item.discount_amount / 100))
                elif bill_item.discount_type == 'fixed':
                    item_price_after_discount -= bill_item.discount_amount
                
                amount_to_remove = quantity_returned * item_price_after_discount

                new_balance = update_wallet_balance(amount_to_remove, True)
                WalletEntry.objects.create(
                    transaction_type="return",
                    amount=amount_to_remove,
                    description=f"Return for Bill {bill.bill_number} - Item: {inventory_item.name}",
                    balance_after_transaction=new_balance
                )

            return JsonResponse({'success': True, 'message': 'Item returned successfully!'})
        except json.JSONDecodeError:
            print('first error')
            print(traceback.format_exc())
            return JsonResponse({'success': False, 'message': 'Invalid JSON data.'}, status=400)
        except Exception as e:
            print('second error')
            print(traceback.format_exc())
            return JsonResponse({'success': False, 'message': str(e)}, status=500)
    
    returns_list = Return.objects.all().order_by('-created_at')

    search_term = request.GET.get('search_term')
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')

    if search_term:
        returns_list = returns_list.filter(
            Q(bill_item__bill__customer__name__icontains=search_term) |
            Q(bill_item__bill__bill_number__icontains=search_term) |
            Q(bill_item__item__name__icontains=search_term)
        )

    if start_date_str:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        returns_list = returns_list.filter(created_at__date__gte=start_date)

    if end_date_str:
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        returns_list = returns_list.filter(created_at__date__lte=end_date)

    paginator = Paginator(returns_list, 10)
    page = request.GET.get('page')

    try:
        returns = paginator.page(page)
    except PageNotAnInteger:
        returns = paginator.page(1)
    except EmptyPage:
        returns = paginator.page(paginator.num_pages)

    returns_data = []
    for ret in returns:
        returns_data.append({
            'id': ret.id,
            'bill_number': ret.bill_item.bill.bill_number,
            'customer_name': ret.bill_item.bill.customer.name,
            'item_name': ret.bill_item.item.name,
            'quantity_returned': float(ret.quantity_returned),
            'amount_returned': float(ret.amount_returned), # Include amount_returned
            'reason': ret.reason,
            'return_date': ret.created_at.isoformat(),
        })

    context = {
        'selected_page': 'return_item',
        'bills_json': json.dumps(list(Bill.objects.filter(status='closed').order_by('-created_at').values('id', 'bill_number'))),
        'returns': returns_data,
        'page_obj': returns,
    }

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        pagination_html = render(request, 'stock/pagination.html', {'page_obj': returns, 'request': request}).content.decode('utf-8')
        return JsonResponse({
            'returns': returns_data,
            'pagination_html': pagination_html
        })

    return render(request, 'billing/return_item.html', context)

@csrf_exempt
def bulk_delete_returns(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            return_ids = data.get('return_ids', [])

            if not return_ids:
                return JsonResponse({'success': False, 'error': 'No return IDs provided.'}, status=400)

            with transaction.atomic():
                deleted_count = 0
                for return_id in return_ids:
                    try:
                        return_obj = Return.objects.get(id=return_id)
                        # Restore stock for the returned item
                        inventory_item = return_obj.bill_item.item
                        inventory_item.total_stock_quantity -= return_obj.quantity_returned
                        inventory_item.save()
                        return_obj.delete()
                        deleted_count += 1
                    except Return.DoesNotExist:
                        pass
                return JsonResponse({'success': True, 'message': f'{deleted_count} return(s) deleted successfully!'})
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Invalid JSON data.'}, status=400)
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
    return JsonResponse({'error': 'Invalid request method'}, status=400)

@csrf_exempt
def return_detail_api(request, return_id):
    if request.method == 'GET':
        try:
            return_obj = get_object_or_404(Return, id=return_id)
            return JsonResponse({
                'success': True,
                'return_item': {
                    'id': return_obj.id,
                    'bill_id': return_obj.bill_item.bill.id,
                    'bill_item_id': return_obj.bill_item.id,
                    'bill_number': return_obj.bill_item.bill.bill_number,
                    'item_name': return_obj.bill_item.item.name,
                    'quantity_returned': float(return_obj.quantity_returned),
                    'amount_returned': float(return_obj.amount_returned), # Include amount_returned
                    'reason': return_obj.reason,
                    'return_date': return_obj.created_at.isoformat(),
                }
            })
        except Return.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Return not found.'}, status=404)
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)
    elif request.method == 'PUT':
        try:
            return_obj = get_object_or_404(Return, id=return_id)
            data = json.loads(request.body)
            
            new_bill_item_id = data.get('bill_item_id')
            new_quantity_returned = Decimal(str(data.get('quantity_returned')))
            new_reason = data.get('reason')

            if not new_bill_item_id or new_quantity_returned <= 0 or not new_reason:
                return JsonResponse({'success': False, 'message': 'All fields are required and quantity must be positive.'}, status=400)

            with transaction.atomic():
                old_bill_item = return_obj.bill_item
                old_quantity_returned = return_obj.quantity_returned
                old_inventory_item = old_bill_item.item

                old_inventory_item.total_stock_quantity -= old_quantity_returned
                old_inventory_item.save()

                new_bill_item = get_object_or_404(BillItem, id=new_bill_item_id)
                new_inventory_item = new_bill_item.item

                if new_quantity_returned > new_bill_item.quantity:
                    transaction.set_rollback(True)
                    return JsonResponse({'success': False, 'message': f'Quantity returned ({new_quantity_returned}) cannot exceed original billed quantity ({new_bill_item.quantity}) for selected item.'}, status=400)


                new_inventory_item.total_stock_quantity += new_quantity_returned
                new_inventory_item.save()

                return_obj.bill_item = new_bill_item
                return_obj.quantity_returned = new_quantity_returned
                return_obj.reason = new_reason
                return_obj.save()

            return JsonResponse({'success': True, 'message': 'Return updated successfully!'})
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'message': 'Invalid JSON data.'}, status=400)
        except BillItem.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Selected Bill Item not found.'}, status=404)
        except Exception as e:
            import traceback
            print(traceback.format_exc())
            return JsonResponse({'success': False, 'message': str(e)}, status=500)
    elif request.method == 'DELETE':
        try:
            return_obj = get_object_or_404(Return, id=return_id)
            with transaction.atomic():
                # Restore stock for the returned item
                inventory_item = return_obj.bill_item.item
                inventory_item.total_stock_quantity -= return_obj.quantity_returned
                inventory_item.save()
                return_obj.delete()
            return JsonResponse({'success': True, 'message': 'Return deleted successfully!'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)
    return JsonResponse({'error': 'Invalid request method'}, status=400)

def paid_later(request):
    bills_list = Bill.objects.filter(status='paid_later').order_by('-created_at')

    search_term = request.GET.get('search_term')
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')

    if search_term:
        bills_list = bills_list.filter(
            Q(customer__name__icontains=search_term) |
            Q(bill_number__icontains=search_term)
        )

    if start_date_str:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        bills_list = bills_list.filter(created_at__date__gte=start_date)

    if end_date_str:
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        # Add one day to the end_date to include the entire end day
        bills_list = bills_list.filter(created_at__date__lte=end_date)

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
                    amount_paid=cash_received,
                    online_amount_paid=online_received,
                    rent_amount=rent_amount,
                    rent_payer=rent_payer,
                    rent_customer_amount=rent_customer_amount,
                    rent_company_amount=rent_company_amount,
                    payment_method=payment_method,
                    status='advance' if is_booking else status,
                    remaining_charges=final_total - total_amount_paid # Set remaining charges
                )
                bill.bill_number = f"BILL-{bill.id:06d}"
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
                    
                    # Deduct stock and add to wallet based on bill status at creation
                    if not is_booking and status != 'paid_later': # For 'open' bills
                        inventory_item.total_stock_quantity -= quantity
                        inventory_item.save()
                    elif status == 'paid_later': # For 'paid_later' bills, deduct stock immediately
                        inventory_item.total_stock_quantity -= quantity
                        inventory_item.save()

                # Add initial payment to wallet if not an advance booking or paid later
                if not is_booking and status != 'open' and status != 'paid_later' and total_amount_paid > 0:
                    new_balance = update_wallet_balance(total_amount_paid, False)
                    WalletEntry.objects.create(
                        transaction_type="sale",
                        amount=total_amount_paid,
                        description=f"Initial payment for Bill {bill.bill_number}",
                        balance_after_transaction=new_balance,
                        payment_mode=payment_method,
                        cash_received=cash_received,
                        online_received=online_received
                    )

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
                'remaining_charges': float(bill.remaining_charges), # Include remaining_charges
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

                # Determine total amount paid based on payment method
                total_amount_paid = Decimal(0)
                if payment_method == 'cash':
                    total_amount_paid = cash_received
                elif payment_method == 'online':
                    total_amount_paid = online_received
                elif payment_method == 'both':
                    total_amount_paid = cash_received + online_received

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
                bill.remaining_charges = final_total - total_amount_paid # Update remaining charges
                bill.save()

                for item_data in bill_items_data:
                    item_id = item_data['itemId']
                    quantity = Decimal(str(item_data['quantity']))
                    retail_price = Decimal(str(item_data['retailPrice']))
                    item_discount_type = item_data.get('itemDiscountType', 'none')
                    item_discount_amount = Decimal(str(item_data.get('itemDiscountAmount', 0)))

                    inventory_item = get_object_or_404(InventoryItem, id=item_id)
                    
                    # Check stock before creating new BillItem and deducting
                    # Deduct stock if the bill's current status is 'paid_later' or 'shipped_pending'
                    if bill.status in ['paid_later', 'shipped_pending']:
                        if inventory_item.total_stock_quantity < quantity:
                            transaction.set_rollback(True)
                            return JsonResponse({'success': False, 'message': f'Not enough stock for {inventory_item.name}. Available: {inventory_item.total_stock_quantity}'}, status=400)
                        inventory_item.total_stock_quantity -= quantity
                        inventory_item.save()

                    BillItem.objects.create(
                        bill=bill,
                        item=inventory_item,
                        quantity=quantity,
                        price_per_unit=retail_price,
                        discount_type=item_discount_type,
                        discount_amount=item_discount_amount
                    )
                    
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
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')

    if search_term:
        bills_list = bills_list.filter(
            Q(customer__name__icontains=search_term) |
            Q(bill_number__icontains=search_term)
        )

    if start_date_str:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        bills_list = bills_list.filter(created_at__date__gte=start_date)

    if end_date_str:
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        # Add one day to the end_date to include the entire end day
        bills_list = bills_list.filter(created_at__date__lte=end_date)

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
