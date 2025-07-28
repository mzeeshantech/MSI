from django.db import models
from django.contrib.auth.models import User # Import Django's built-in User model

class ParentCategory(models.Model):
    category_id = models.AutoField(primary_key=True)
    category_name = models.CharField(max_length=255, null=False)
    parent_category = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='children')
    description = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'ParentCategories'
        verbose_name = 'Parent Category'
        verbose_name_plural = 'Parent Categories'

    def __str__(self):
        return self.category_name

class Item(models.Model):
    UNIT_OF_MEASURE_CHOICES = [
        ('KG', 'Kilogram'),
        ('PIECE', 'Piece'),
    ]

    item_id = models.AutoField(primary_key=True)
    sku_number = models.CharField(max_length=100, unique=True, null=False)
    category = models.ForeignKey(ParentCategory, on_delete=models.CASCADE, null=False)
    item_name = models.CharField(max_length=255, null=False)
    unit_of_measure = models.CharField(max_length=10, choices=UNIT_OF_MEASURE_CHOICES, null=False)
    sold_in_kgs = models.BooleanField(default=True, null=False)
    retail_price_per_unit = models.DecimalField(max_digits=10, decimal_places=2, null=False)
    current_stock_quantity = models.DecimalField(max_digits=10, decimal_places=3, default=0.000, null=False)
    description = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'Items'
        verbose_name = 'Item'
        verbose_name_plural = 'Items'

    def __str__(self):
        return self.item_name

class StockMovement(models.Model):
    MOVEMENT_TYPE_CHOICES = [
        ('IN_OPENING', 'In - Opening Stock'),
        ('IN_PURCHASE', 'In - Purchase'),
        ('OUT_SALE', 'Out - Sale'),
        ('OUT_ADJUSTMENT', 'Out - Adjustment'),
    ]

    movement_id = models.AutoField(primary_key=True)
    item = models.ForeignKey(Item, on_delete=models.CASCADE, null=False)
    movement_type = models.CharField(max_length=20, choices=MOVEMENT_TYPE_CHOICES, null=False)
    quantity_changed = models.DecimalField(max_digits=10, decimal_places=3, null=False)
    movement_date = models.DateTimeField(auto_now_add=True)
    reference_document = models.CharField(max_length=255, null=True, blank=True)
    notes = models.TextField(null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True) # Link to Django's built-in User model

    class Meta:
        db_table = 'StockMovements'
        verbose_name = 'Stock Movement'
        verbose_name_plural = 'Stock Movements'

    def __str__(self):
        return f"{self.movement_type} for {self.item.item_name} - {self.quantity_changed}"

class Customer(models.Model):
    customer_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255, null=False)
    cnic = models.CharField(max_length=20, unique=True, null=True, blank=True)
    phone_number = models.CharField(max_length=50, null=True, blank=True)
    address = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'Customers'
        verbose_name = 'Customer'
        verbose_name_plural = 'Customers'

    def __str__(self):
        return self.name

class Bill(models.Model):
    STATUS_CHOICES = [
        ('FINALIZED', 'Finalized'),
        ('DRAFT', 'Draft'),
        ('CANCELLED', 'Cancelled'),
    ]

    bill_id = models.AutoField(primary_key=True)
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True)
    bill_date = models.DateTimeField(auto_now_add=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, null=False)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, null=False)
    final_payable_amount = models.DecimalField(max_digits=10, decimal_places=2, null=False)
    rent_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, null=False)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='DRAFT', null=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=False)

    class Meta:
        db_table = 'Bills'
        verbose_name = 'Bill'
        verbose_name_plural = 'Bills'

    def __str__(self):
        return f"Bill #{self.bill_id} - {self.final_payable_amount}"

class BillItem(models.Model):
    bill_item_id = models.AutoField(primary_key=True)
    bill = models.ForeignKey(Bill, on_delete=models.CASCADE, null=False)
    item = models.ForeignKey(Item, on_delete=models.CASCADE, null=False)
    quantity = models.DecimalField(max_digits=10, decimal_places=3, null=False)
    unit_price_at_sale = models.DecimalField(max_digits=10, decimal_places=2, null=False)
    line_total = models.DecimalField(max_digits=10, decimal_places=2, null=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'BillItems'
        verbose_name = 'Bill Item'
        verbose_name_plural = 'Bill Items'

    def __str__(self):
        return f"Bill {self.bill.bill_id} - {self.item.item_name}"

class Payment(models.Model):
    PAYMENT_METHOD_CHOICES = [
        ('CASH', 'Cash'),
        ('ONLINE', 'Online'),
    ]

    payment_id = models.AutoField(primary_key=True)
    bill = models.ForeignKey(Bill, on_delete=models.CASCADE, null=False)
    payment_method = models.CharField(max_length=10, choices=PAYMENT_METHOD_CHOICES, null=False)
    amount = models.DecimalField(max_digits=10, decimal_places=2, null=False)
    payment_date = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=False)

    class Meta:
        db_table = 'Payments'
        verbose_name = 'Payment'
        verbose_name_plural = 'Payments'

    def __str__(self):
        return f"Payment for Bill #{self.bill.bill_id} - {self.amount}"

class RentReport(models.Model):
    rent_report_id = models.AutoField(primary_key=True)
    bill = models.OneToOneField(Bill, on_delete=models.CASCADE, null=True, blank=True, unique=True)
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True)
    delivery_address = models.TextField(null=False)
    total_rent_amount = models.DecimalField(max_digits=10, decimal_places=2, null=False)
    customer_paid_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, null=False)
    company_paid_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, null=False)
    rent_date = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=False)

    class Meta:
        db_table = 'RentReports'
        verbose_name = 'Rent Report'
        verbose_name_plural = 'Rent Reports'

    def __str__(self):
        return f"Rent Report #{self.rent_report_id} for Bill #{self.bill.bill_id if self.bill else 'N/A'}"

class Expense(models.Model):
    expense_id = models.AutoField(primary_key=True)
    description = models.TextField(null=False)
    amount = models.DecimalField(max_digits=10, decimal_places=2, null=False)
    expense_date = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=False)

    class Meta:
        db_table = 'Expenses'
        verbose_name = 'Expense'
        verbose_name_plural = 'Expenses'

    def __str__(self):
        return f"Expense #{self.expense_id} - {self.amount}"

class Employee(models.Model):
    employee_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255, null=False)
    contact_info = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'Employees'
        verbose_name = 'Employee'
        verbose_name_plural = 'Employees'

    def __str__(self):
        return self.name

class EmployeeAdvance(models.Model):
    advance_id = models.AutoField(primary_key=True)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, null=False)
    advance_amount = models.DecimalField(max_digits=10, decimal_places=2, null=False)
    advance_date = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=False)

    class Meta:
        db_table = 'EmployeeAdvances'
        verbose_name = 'Employee Advance'
        verbose_name_plural = 'Employee Advances'

    def __str__(self):
        return f"Advance for {self.employee.name} - {self.advance_amount}"

class Return(models.Model):
    return_id = models.AutoField(primary_key=True)
    bill = models.ForeignKey(Bill, on_delete=models.SET_NULL, null=True, blank=True)
    item = models.ForeignKey(Item, on_delete=models.CASCADE, null=False)
    quantity_returned = models.DecimalField(max_digits=10, decimal_places=3, null=False)
    return_price_per_unit = models.DecimalField(max_digits=10, decimal_places=2, null=False)
    return_total_amount = models.DecimalField(max_digits=10, decimal_places=2, null=False)
    return_date = models.DateTimeField(auto_now_add=True)
    reason = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=False)

    class Meta:
        db_table = 'Returns'
        verbose_name = 'Return'
        verbose_name_plural = 'Returns'

    def __str__(self):
        return f"Return #{self.return_id} - {self.item.item_name}"

class WalletTransaction(models.Model):
    TRANSACTION_TYPE_CHOICES = [
        ('SALE_INCOME', 'Sale Income'),
        ('EXPENSE_OUT', 'Expense Out'),
        ('RETURN_OUT', 'Return Out'),
        ('ADVANCE_OUT', 'Advance Out'),
        ('ADVANCE_REPAYMENT_IN', 'Advance Repayment In'),
        ('OTHER_IN', 'Other In'),
        ('OTHER_OUT', 'Other Out'),
    ]

    transaction_id = models.AutoField(primary_key=True)
    transaction_date = models.DateTimeField(auto_now_add=True)
    transaction_type = models.CharField(max_length=30, choices=TRANSACTION_TYPE_CHOICES, null=False)
    amount = models.DecimalField(max_digits=10, decimal_places=2, null=False)
    description = models.TextField(null=True, blank=True)
    reference_id = models.IntegerField(null=True, blank=True)
    reference_table = models.CharField(max_length=50, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=False)

    class Meta:
        db_table = 'WalletTransactions'
        verbose_name = 'Wallet Transaction'
        verbose_name_plural = 'Wallet Transactions'

    def __str__(self):
        return f"Transaction #{self.transaction_id} - {self.transaction_type} - {self.amount}"
