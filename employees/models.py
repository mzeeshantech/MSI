from django.db import models

class EmployeeAdvance(models.Model):
    employee_name = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    date_given = models.DateField(auto_now_add=True)
    paid_back = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.employee_name} - {self.amount}"
