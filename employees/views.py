from django.shortcuts import render
from .models import EmployeeAdvance

def employees_home(request):
    context = {
        'selected_page': 'employees',
    }
    return render(request, 'employees/home.html', context)

def employee_advances(request):
    advances = EmployeeAdvance.objects.all()
    context = {
        'selected_page': 'employees',
        'advances' : advances
    }
    return render(request, 'employees/advances.html', context)
