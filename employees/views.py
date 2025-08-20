from django.shortcuts import render, get_object_or_404
from .models import Employee, EmployeeAdvance
from django.http import JsonResponse
import json

def employees_home(request):
    employees = Employee.objects.all()
    context = {
        'selected_page': 'employees',
        'employees': employees
    }
    return render(request, 'employees/home.html', context)

def add_employee(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        employee = Employee.objects.create(
            name=data['name'],
            cnic=data['cnic'],
            job_title=data['job_title'],
            email=data.get('email')
        )
        return JsonResponse({'success': True, 'employee': {'id': employee.id, 'name': employee.name, 'cnic': employee.cnic, 'job_title': employee.job_title, 'email': employee.email}})
    return JsonResponse({'success': False, 'message': 'Invalid request method'})

def edit_employee(request, employee_id):
    employee = get_object_or_404(Employee, id=employee_id)
    if request.method == 'POST':
        data = json.loads(request.body)
        employee.name = data['name']
        employee.cnic = data['cnic']
        employee.job_title = data['job_title']
        employee.email = data.get('email')
        employee.save()
        return JsonResponse({'success': True, 'employee': {'id': employee.id, 'name': employee.name, 'cnic': employee.cnic, 'job_title': employee.job_title, 'email': employee.email}})
    
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'employee': {'id': employee.id, 'name': employee.name, 'cnic': employee.cnic, 'job_title': employee.job_title, 'email': employee.email}})
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})

def delete_employee(request, employee_id):
    employee = get_object_or_404(Employee, id=employee_id)
    employee.delete()
    return JsonResponse({'success': True})

def employee_advances(request):
    advances = EmployeeAdvance.objects.all()
    context = {
        'selected_page': 'employees',
        'advances' : advances
    }
    return render(request, 'employees/advances.html', context)
