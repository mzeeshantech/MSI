from django.shortcuts import render
from django.db.models import Sum, F, ExpressionWrapper, DecimalField
from django.db.models.functions import Coalesce
from billing.models import BillItem, Bill
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
        category_ids_str = request.GET.get('category_ids')
        category_ids = []
        if category_ids_str:
            try:
                category_ids = json.loads(category_ids_str)
            except json.JSONDecodeError:
                return HttpResponseBadRequest("Invalid category_ids format.")
        
        stock_data = generate_stock_report(category_ids)
        
        context = {
            'stock_data': stock_data,
        }
        
        html_string = render_to_string('reports/stock_report.html', context)
        
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="stock_report_{timezone.localdate().isoformat()}.pdf"'
        
        pdf_file = HTML(string=html_string, base_url=request.build_absolute_uri('/')).write_pdf()
        response.write(pdf_file)
        
        return response
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
        net_qty = (entry["total_sale"] or 0) - (entry["returned_qty"] or 0)
        net_amount = (entry["total_amount"] or 0) - (entry["returned_amount"] or 0)

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


    entries = (WalletEntry.objects
        .all()
        .values("transaction_type", "payment_mode")
        .annotate(total_amount=Sum("amount"))
    )

    print(f"entries = {entries}")

    expenses = (Expense.objects
        .filter(created_at__date=report_date)
        .values("description")
        .annotate(total_amount=Sum("amount"))
    )

    return {"wallet_entries": list(entries), "expenses": list(expenses)}

def generate_stock_report(category_ids):
    items = (InventoryItem.objects
        .filter(category_id__in=category_ids)
        .values(
            category=F("category__name"),
            sku=F("sku"),
            name=F("name"),
            quantity=F("total_stock_quantity"),
            uom=F("unit_of_measure"),
        )
    )
    return items


def generate_cnic_report(report_date=None):
    if not report_date:
        report_date = date.today()

    customers = (Bill.objects
        .filter(created_at__date=report_date, status="closed", customer__isnull=False)
        .values("customer__name", "customer__cnic", "customer__phone")
        .distinct()
    )
    return customers
