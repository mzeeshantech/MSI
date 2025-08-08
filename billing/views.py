from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
import json

from stock.models import InventoryItem, InventoryCategory
from .models import Bill, BillItem, Customer

def billing_home(request):
    categories = InventoryCategory.objects.values('id', 'name').distinct()
    context = {
        'selected_page': 'billing',
        'categories': categories,
    }
    return render(request, 'billing/home.html', context)

def bill_list(request):
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
        skus = InventoryItem.objects.filter(category_id=category_id).values('id', 'sku', 'name', 'sale_price', 'unit_of_measure')
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
            bill_items_data = json.loads(data.get('bill_items', '[]'))
            
            rent_amount = float(data.get('rent_amount', 0))
            rent_payer = data.get('rent_payer', 'customer')
            payment_method = data.get('payment_method', 'cash')
            cash_received = float(data.get('cash_received', 0))

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

                calculated_total_amount = 0
                for item_data in bill_items_data:
                    retail_price = float(item_data['retailPrice'])
                    quantity = int(item_data['quantity'])
                    item_discount_type = item_data.get('itemDiscountType', 'none')
                    item_discount_amount = float(item_data.get('itemDiscountAmount', 0))

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

                bill = Bill.objects.create(
                    customer=customer,
                    total_amount=final_total,
                    amount_paid=cash_received, # Assuming cash_received is the amount paid
                    rent_amount=rent_amount,
                    rent_payer=rent_payer,
                    payment_method=payment_method
                )

                for item_data in bill_items_data:
                    item_id = item_data['itemId']
                    quantity = item_data['quantity']
                    retail_price = item_data['retailPrice']
                    item_discount_type = item_data.get('itemDiscountType', 'none')
                    item_discount_amount = float(item_data.get('itemDiscountAmount', 0))

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
                    
                    # Reduce stock
                    inventory_item.total_stock_quantity -= quantity
                    inventory_item.save()

            return JsonResponse({'success': True, 'message': 'Bill generated successfully!'})
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'message': 'Invalid JSON data.'}, status=400)
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)
    return JsonResponse({'error': 'Invalid request method'}, status=400)
