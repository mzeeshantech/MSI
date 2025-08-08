from django.shortcuts import render, redirect
from django.http import JsonResponse
from .models import Wallet, WalletEntry
from django.db import transaction
from django.contrib import messages
from datetime import date
from django.core.paginator import Paginator

def get_wallet_balance():
    wallet, created = Wallet.objects.get_or_create(pk=1)
    return wallet.current_balance

from decimal import Decimal

def update_wallet_balance(amount, is_deduction=True):
    wallet = Wallet.objects.get_or_create(pk=1)[0]
    amount_decimal = Decimal(str(amount)) # Convert float to Decimal
    if is_deduction:
        wallet.current_balance -= amount_decimal
    else:
        wallet.current_balance += amount_decimal
    wallet.save()
    return wallet.current_balance

def wallet_home(request):
    if request.method == 'POST':
        transaction_type = request.POST.get('transaction_type')
        amount = request.POST.get('amount')
        description = request.POST.get('description')
        entry_id = request.POST.get('entry_id')

        if not all([transaction_type, amount]):
            messages.error(request, "Transaction type and amount are required.")
            return redirect('wallet_home')

        try:
            amount = float(amount)
            if amount <= 0:
                messages.error(request, "Amount must be positive.")
                return redirect('wallet_home')
        except ValueError:
            messages.error(request, "Invalid amount.")
            return redirect('wallet_home')

        # Determine if the transaction is a deduction
        is_deduction = transaction_type in ['sale', 'salary', 'expense', 'advance_salary', 'other']

        with transaction.atomic():
            if entry_id:
                # Handle edit
                entry = WalletEntry.objects.get(id=entry_id)
                # Revert old balance change
                update_wallet_balance(entry.amount, is_deduction=not (entry.transaction_type in ['sale', 'deposit']))
                
                entry.transaction_type = transaction_type
                entry.amount = amount
                entry.description = description
                entry.balance_after_transaction = update_wallet_balance(amount, is_deduction)
                entry.save()
                messages.success(request, f"Wallet entry updated successfully.")
            else:
                # Handle new entry
                new_balance = update_wallet_balance(amount, is_deduction)
                WalletEntry.objects.create(
                    transaction_type=transaction_type,
                    amount=amount,
                    description=description,
                    balance_after_transaction=new_balance,
                    transaction_date=date.today()
                )
                messages.success(request, f"{transaction_type.capitalize()} transaction recorded successfully.")
        return redirect('wallet_home')

    from django.core.paginator import Paginator

    entries_list = WalletEntry.objects.all()
    paginator = Paginator(entries_list, 10) # Show 10 entries per page
    page_number = request.GET.get('page')
    entries = paginator.get_page(page_number)

    current_balance = get_wallet_balance()
    context = {
        'selected_page': 'wallet',
        'entries': entries, # Pass the Page object
        'current_balance': current_balance,
        'transaction_type_choices': WalletEntry.TRANSACTION_TYPE_CHOICES,
        'page_obj': entries, # Pass the Page object with a generic name for pagination.html
    }
    return render(request, 'wallet/home.html', context)

def wallet_entry_detail(request, pk):
    try:
        entry = WalletEntry.objects.get(pk=pk)
        return JsonResponse({
            'id': entry.id,
            'transaction_type': entry.transaction_type,
            'amount': float(entry.amount),
            'description': entry.description,
        })
    except WalletEntry.DoesNotExist:
        return JsonResponse({'error': 'Entry not found'}, status=404)

def delete_wallet_entry(request, pk):
    if request.method == 'POST':
        try:
            entry = WalletEntry.objects.get(pk=pk)
            with transaction.atomic():
                # Revert the balance change
                update_wallet_balance(entry.amount, is_deduction=not (entry.transaction_type in ['sale', 'deposit']))
                entry.delete()
                messages.success(request, "Wallet entry deleted successfully.")
                return JsonResponse({'success': True})
        except WalletEntry.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Entry not found'}, status=404)
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
    return JsonResponse({'success': False, 'error': 'Invalid request method'}, status=400)
