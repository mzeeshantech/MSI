from django.shortcuts import render, get_object_or_404
from .models import Employee, EmployeeAdvance
from django.http import JsonResponse
import json
import datetime
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
    advances = EmployeeAdvance.objects.all().order_by('-id')
    employees = Employee.objects.all()
    context = {
        'selected_page': 'employee_advances',
        'advances' : advances,
        'employees': employees,
    }
    return render(request, 'employees/advances.html', context)

def grant_advance_salary(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        employee_id = data.get('employee')
        amount = data.get('amount')
        date_given_str = data.get('date')
        
        try:
            employee = Employee.objects.get(id=employee_id)
            date_obj = datetime.datetime.strptime(date_given_str, '%Y-%m-%d').date()
            month_name = data.get('month') # Get month from frontend

            EmployeeAdvance.objects.create(
                employee_name=employee.name, 
                amount=amount,
                date_given=date_obj,
                month=month_name,
                paid_back=False 
            )
            return JsonResponse({'success': True, 'message': 'Advance salary granted successfully.'})
        except Employee.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Employee not found.'}, status=404)
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=400)
    return JsonResponse({'success': False, 'message': 'Invalid request method.'}, status=405)

def advance_detail(request, advance_id):
    advance = get_object_or_404(EmployeeAdvance, id=advance_id)

    if request.method == 'GET':
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({
                'advance': {
                    'id': advance.id,
                    'employee_id': Employee.objects.get(name=advance.employee_name).id,
                    'amount': advance.amount,
                    'date_given': advance.date_given.strftime('%Y-%m-%d'),
                    'month': advance.month,
                    'paid_back': advance.paid_back
                }
            })
        return JsonResponse({'success': False, 'message': 'Invalid request method.'}, status=405)

    elif request.method == 'PUT':
        data = json.loads(request.body)
        employee_id = data.get('employee')
        amount = data.get('amount')
        date_given_str = data.get('date')

        try:
            employee = Employee.objects.get(id=employee_id)
            date_obj = datetime.datetime.strptime(date_given_str, '%Y-%m-%d').date()
            month_name = data.get('month')

            advance.employee_name = employee.name
            advance.amount = amount
            advance.date_given = date_obj
            advance.month = month_name
            advance.paid_back = data.get('paid_back', advance.paid_back)
            advance.save()
            return JsonResponse({'success': True, 'message': 'Advance updated successfully.'})
        except Employee.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Employee not found.'}, status=404)
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=400)

    elif request.method == 'DELETE':
        try:
            advance.delete()
            return JsonResponse({'success': True, 'message': 'Advance deleted successfully.'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=400)
            
    return JsonResponse({'success': False, 'message': 'Invalid request method.'}, status=405)
