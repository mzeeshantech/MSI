from django.shortcuts import render, redirect
from django.core.paginator import Paginator
from django.template.loader import render_to_string
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.core.paginator import Paginator
from django.template.loader import render_to_string
from django.http import JsonResponse
from django.db.models import Q # Import Q object
from .models import Expense
import datetime
from django.urls import reverse
from wallet.models import Wallet, WalletEntry
from decimal import Decimal
from datetime import date

def update_wallet_balance(amount, is_deduction=True):
    wallet = Wallet.objects.get_or_create(pk=1)[0]
    amount_decimal = Decimal(str(amount)) # Convert float to Decimal
    if is_deduction:
        wallet.current_balance -= amount_decimal
    else:
        wallet.current_balance += amount_decimal
    wallet.save()
    return wallet.current_balance

def expenses_home(request):
    if request.method == 'POST':
        expense_id = request.POST.get('expense_id')
        description = request.POST.get('description')
        amount = request.POST.get('amount')
        receipt = request.FILES.get('receipt')
        created_at = request.POST.get('created_at')
        approved_by = request.POST.get('approved_by')

        if expense_id: # Editing an existing expense
            expense = get_object_or_404(Expense, pk=expense_id)
            expense.description = description
            expense.amount = amount
            if receipt:
                expense.receipt = receipt
            expense.created_at = created_at
            expense.approved_by = approved_by
            expense.save()
        else: # Adding a new expense
            Expense.objects.create(
                description=description,
                amount=amount,
                receipt=receipt,
                created_at=created_at,
                approved_by=approved_by
            )

            # Handle new entry
            new_balance = update_wallet_balance(amount, True)
            WalletEntry.objects.create(
                transaction_type="expense",
                amount=amount,
                description=description,
                balance_after_transaction=new_balance,
                transaction_date=date.today()
            )



        return redirect('expenses_home')

    query = request.GET.get('query', '')
    page_number = request.GET.get('page')

    expenses_list = Expense.objects.all().order_by('-created_at')

    if query:
        expenses_list = expenses_list.filter(
            Q(description__icontains=query) | Q(approved_by__icontains=query),
            created_at__date=datetime.date.today()
        )

    paginator = Paginator(expenses_list, 10) 
    page_obj = paginator.get_page(page_number)

    if request.headers.get('x-requested-with') == 'XMLHttpRequest': 
        html = render_to_string('expenses/expense_table_rows.html', {'expenses': page_obj.object_list})
        return JsonResponse({'html': html, 'has_next': page_obj.has_next(), 'has_previous': page_obj.has_previous(), 'num_pages': paginator.num_pages, 'current_page': page_obj.number})

    context = {
        'selected_page': 'expenses',
        'today': datetime.date.today(),
        'page_obj': page_obj,
    }
    return render(request, 'expenses/home.html', context)

import logging

logger = logging.getLogger(__name__)

def edit_expense(request, expense_id):
    try:
        expense = get_object_or_404(Expense, pk=expense_id)
        if request.method == 'GET':
            data = {
                'id': expense.id,
                'description': expense.description,
                'amount': str(expense.amount), # Convert Decimal to string for JSON
                'created_at': expense.created_at.strftime('%Y-%m-%d'),
                'approved_by': expense.approved_by,
                'receipt_url': expense.receipt.url if expense.receipt else ''
            }
            return JsonResponse(data)
        elif request.method == 'POST':
            delete_flag = request.POST.get('delete_flag')
            if delete_flag == 'true':
                expense.delete()
                return JsonResponse({'success': True, 'message': 'Expense deleted successfully.'})
            else:
                # This part is for actual editing, though currently handled by expenses_home
                # If we were to fully move edit here, we'd process form data.
                return JsonResponse({'success': False, 'error': 'Invalid POST request for edit_expense.'}, status=400)
    except Exception as e:
        logger.exception("Error in edit_expense view for expense_id: %s", expense_id)
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


def expense_list(request):
    expenses = Expense.objects.all()
    context = {
        'selected_page': 'expenses',
        'expenses' : expenses
    }
    return render(request, 'expenses/list.html', context)
