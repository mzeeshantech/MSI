from django.shortcuts import render, get_object_or_404
from .models import Bill

def billing_home(request):
    context = {
        'selected_page': 'billing'
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
