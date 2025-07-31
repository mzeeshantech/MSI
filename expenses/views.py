from django.shortcuts import render
from .models import Expense

def expenses_home(request):
    context = {
        'selected_page': 'expenses',
    }
    return render(request, 'expenses/home.html', context)

def expense_list(request):
    expenses = Expense.objects.all()
    context = {
        'selected_page': 'expenses',
        'expenses' : expenses
    }
    return render(request, 'expenses/list.html', context)
