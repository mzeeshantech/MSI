from django.db import models
import datetime

class Employee(models.Model):
    name = models.CharField(max_length=100)
    cnic = models.CharField(max_length=15, unique=True)
    job_title = models.CharField(max_length=100)
    email = models.EmailField(blank=True, null=True)

    def __str__(self):
        return self.name

class EmployeeAdvance(models.Model):
    employee_name = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    date_given = models.DateField(default=datetime.date.today)
    month = models.CharField(max_length=20, blank=True, null=True)
    paid_back = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.employee_name} - {self.amount}"
