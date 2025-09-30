from django.shortcuts import render
from django.db.models import Sum, F, ExpressionWrapper, DecimalField
from django.db.models.functions import Coalesce
from billing.models import BillItem, Bill, Customer
from .models import DailySaleSummary
from wallet.models import *
from billing.models import *
from expenses.models import *
from datetime import date, timedelta
from django.utils import timezone
from decimal import Decimal
from django.http import HttpResponse
import csv
from django.http import HttpResponseBadRequest
from django.db.models import Sum, F, ExpressionWrapper, DecimalField, Q
from django.utils.timezone import now
from weasyprint import HTML
from django.template.loader import render_to_string
from stock.models import InventoryItem # Import InventoryItem for stock report
import json # Import json to parse category_ids
from django.http import JsonResponse
from stock.models import InventoryCategory # Import InventoryCategory
from django.db.models import Sum, Case, When, DecimalField, F, Value

def get_categories(request):
    categories = InventoryCategory.objects.all().values('id', 'name')
    return JsonResponse(list(categories), safe=False)

def reports_home(request):
    selected_date_str = request.GET.get('date')
    if selected_date_str:
        selected_date = date.fromisoformat(selected_date_str)
    else:
        selected_date = timezone.localdate() # Default to today's date

    context = {
        'selected_page': 'reports',
        'report_date': selected_date,
        'daily_summaries': None,
    }
    return render(request, 'reports/home.html', context)


def download_report(request):
    report_type = request.GET.get('report_type')
    
    
    if report_type == 'daily_sale':
        selected_date_str = request.GET.get('date')
        if selected_date_str:
            selected_date = date.fromisoformat(selected_date_str)
        else:
            selected_date = timezone.localdate() # Default to today's date

        daily_summaries = get_daily_sale_report(selected_date)
        
        context = {
            'report_date': selected_date,
            'daily_summaries': daily_summaries,
        }
        
        html_string = render_to_string('reports/daily_sale_report.html', context)
        
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="daily_sale_report_{selected_date.isoformat()}.pdf"'
        
        pdf_file = HTML(string=html_string, base_url=request.build_absolute_uri('/')).write_pdf()
        response.write(pdf_file)
        
        return response
    elif report_type == 'debit_credit':
        selected_date_str = request.GET.get('date')
        if selected_date_str:
            selected_date = date.fromisoformat(selected_date_str)
        else:
            selected_date = timezone.localdate() # Default to today's date

        debit_credit_data = generate_debit_credit_report(selected_date)
        print(f"debit_credit_data = {debit_credit_data}")
        context = {
            'report_date': selected_date,
            'debit_credit_data': debit_credit_data,
        }
        
        html_string = render_to_string('reports/debit_credit_report.html', context)
        
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="debit_credit_report_{selected_date.isoformat()}.pdf"'
        
        pdf_file = HTML(string=html_string, base_url=request.build_absolute_uri('/')).write_pdf()
        response.write(pdf_file)
        
        return response
    elif report_type == 'stock':
        category_ids = request.GET.getlist('categories') # Changed from 'category_ids' to 'categories'
        
        stock_data = generate_stock_report(category_ids)
        context = {
            'report_date': timezone.localdate(),
            'stock_data': stock_data,
        }
        
        html_string = render_to_string('reports/stock_report.html', context)
        
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="stock_report_{timezone.localdate().isoformat()}.pdf"'
        
        pdf_file = HTML(string=html_string, base_url=request.build_absolute_uri('/')).write_pdf()
        response.write(pdf_file)
        
        return response
    elif report_type == 'cnic_report':
        selected_date_str = request.GET.get('date')
        if selected_date_str:
            selected_date = date.fromisoformat(selected_date_str)
        else:
            selected_date = timezone.localdate() # Default to today's date

        cnic_data = generate_cnic_report(selected_date)
        
        context = {
            'report_date': selected_date,
            'cnic_data': cnic_data,
        }
        
        html_string = render_to_string('reports/cnic_report.html', context)
        
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="cnic_report_{selected_date.isoformat()}.pdf"'
        
        pdf_file = HTML(string=html_string, base_url=request.build_absolute_uri('/')).write_pdf()
        response.write(pdf_file)
        
        return response
    elif report_type == 'rent_report':
        return rent_report_pdf(request)
    else:
        return HttpResponseBadRequest("Invalid report type selected.")


def get_daily_sale_report(date=None):
    if date is None:
        date = now().date()

    # Query BillItems of the day
    bill_items = (
        BillItem.objects
        .filter(bill__created_at__date=date, bill__status='closed')
        .values(
            category=F('item__category__name'),  # assuming InventoryItem has category FK
            sku=F('item__name'),
        )
        .annotate(
            total_sale=Sum('quantity'),
            total_amount=Sum(
                ExpressionWrapper(
                    F('quantity') * F('price_per_unit'),
                    output_field=DecimalField(max_digits=12, decimal_places=2)
                )
            ),
            total_discount=Sum('discount_amount'),
            returned_qty=Sum('return__quantity_returned', default=0),
            returned_amount=Sum('return__amount_returned', default=0),
        )
    )

    results = []
    for entry in bill_items:
        # Net sales after subtracting returns
        # net_qty = (entry["total_sale"] or 0) - (entry["returned_qty"] or 0)
        # net_amount = (entry["total_amount"] or 0) - (entry["returned_amount"] or 0)

        net_qty = (entry["total_sale"] or 0) 
        net_amount = (entry["total_amount"] or 0)

        results.append({
            "category": entry["category"],
            "sku": entry["sku"],
            "total_sale": net_qty,
            "avg_rate": (net_amount / net_qty) if net_qty else 0,
            "amount": net_amount,
        })

    return results


def generate_debit_credit_report(report_date=None):
    if not report_date:
        report_date = date.today()


    entries = (
        WalletEntry.objects
        .filter(transaction_date=report_date)
        .aggregate(
            cash=Sum(
                Case(
                    When(payment_mode="cash", then=F("amount")),
                    When(payment_mode="both", then=F("cash_received")),
                    default=Value(0),
                    output_field=DecimalField(),
                )
            ),
            online=Sum(
                Case(
                    When(payment_mode="online", then=F("amount")),
                    When(payment_mode="both", then=F("online_received")),
                    default=Value(0),
                    output_field=DecimalField(),
                )
            ),
        )
    )

    print(f"entries = {entries}")

    total_expense_sum = (Expense.objects
        .filter(created_at__date=report_date)
        .aggregate(total_sum=Sum("amount"))["total_sum"] or Decimal('0.00')
    )

    rent_bills_amount = Bill.objects.filter(
        created_at__date=report_date,
        status='closed',
        rent_amount__isnull=False
    ).exclude(rent_amount=0).select_related('customer')

    total_rent_amount = rent_bills_amount.aggregate(total_rent=Sum('rent_amount'))['total_rent'] or Decimal('0.00')

    pending_bills = Bill.objects.filter(
        created_at__date=report_date,
        status='shipped_pending',
    ).exclude(total_amount=F('amount_paid')).select_related('customer')

    total_pending_amount = pending_bills.aggregate(
        total_pending=Sum(F('total_amount') - F('amount_paid'))
    )['total_pending'] or Decimal('0.00')

    return {"wallet_entries": entries, "total_expense_sum": total_expense_sum, "total_rent_amount": total_rent_amount, "total_pending_amount": total_pending_amount}

def generate_stock_report(category_ids):

    items = (InventoryItem.objects
        .filter(category_id__in=category_ids)
        .values(
            category_name=F("category__name"), # Renamed to avoid conflict
            item_sku=F("sku"), # Renamed to avoid conflict with model field
            item_name=F("name"),
            quantity=F("total_stock_quantity"),
            uom=F("unit_of_measure"),
            item_sale_price=F("sale_price"),
            item_last_system_sale_price=F("last_system_sale_price"),
        )
    )

    grouped_items = {}
    for item in items:
        category_name = item['category_name']
        if category_name not in grouped_items:
            grouped_items[category_name] = []
        grouped_items[category_name].append(item)

    return grouped_items


def generate_cnic_report(report_date=None):
    if not report_date:
        report_date = date.today()

    customers = (Bill.objects
        .filter(created_at__date=report_date, status="closed", customer__isnull=False)
        .values("customer__name", "customer__cnic", "customer__phone")
        .distinct()
    )
    return customers

def rent_report_pdf(request):
    selected_date_str = request.GET.get('date')
    if not selected_date_str:
        return HttpResponseBadRequest("Date is required for Rent Report.")

    selected_date = date.fromisoformat(selected_date_str)

    # Fetch closed bills for the selected date with rent details
    rent_bills = Bill.objects.filter(
        created_at__date=selected_date,
        status='closed',
        rent_amount__isnull=False
    ).exclude(rent_amount=0).select_related('customer')

    report_data = []
    for bill in rent_bills:
        report_data.append({
            'bill_number': bill.bill_number,
            'rent_total_amount': bill.rent_amount,
            'rent_payer': bill.rent_payer,
            'paid_by_client': bill.rent_customer_amount,
            'paid_by_company': bill.rent_company_amount,
            'address': bill.customer.address if bill.customer else 'N/A',
            'customer_name': bill.customer.name if bill.customer else 'N/A',
        })

    context = {
        'report_date': selected_date,
        'rent_data': report_data,
    }

    html_string = render_to_string('reports/rent_report.html', context)

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="rent_report_{selected_date.isoformat()}.pdf"'

    pdf_file = HTML(string=html_string, base_url=request.build_absolute_uri('/')).write_pdf()
    response.write(pdf_file)

    return response
