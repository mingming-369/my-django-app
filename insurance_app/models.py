from django.db import models

class Customer(models.Model):
    id_customer = models.CharField(primary_key=True)
    customer_name = models.CharField(max_length=200)
    address = models.CharField(max_length=200, blank=True, default='')
    email = models.CharField(max_length=200, blank=True, default='')
    phone_num = models.CharField(max_length=50, blank=True, default='')
    IN_CHARGE_CHOICES = [
        ('Alwin', 'Alwin'),
        ('Henry', 'Henry'),
        ('Vanessa', 'Vanessa'),
        ('Loh', 'Loh'),
        ('Other', 'Other'),
    ]

    PROPOSAL_ENGINEER_CHOICES = [
        ('Haziq','Haziq'),
        ('Asyraf','Asyraf'),
        ('Faqihah','Faqihah'),
        ('Farah','Farah'),
        ('Loh','Loh'),
        ('Other','Other'),
    ]
    in_charge_person = models.CharField(max_length=100, choices=IN_CHARGE_CHOICES, blank=True, null=True, default=None)
    proposal_prepared_by = models.CharField(max_length=100, choices=PROPOSAL_ENGINEER_CHOICES, blank=True, null=True, default=None)
    engineers = models.CharField(max_length=500, blank=True, default='')
    installer = models.CharField(max_length=200, blank=True, default='')
    installed_on = models.DateField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'Customer'


class Insurance(models.Model):
    no_insurance = models.CharField(primary_key=True, max_length=100)
    sum_amount = models.DecimalField(max_digits=10, decimal_places=2)
    starting_period = models.DateField()
    end_period = models.DateField()
    id_customer = models.ForeignKey(Customer, on_delete=models.CASCADE, db_column='id_customer')
    total_payable = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=50)
    ins_co = models.CharField(max_length=200)

    class Meta:
        managed = False
        db_table = 'Insurance'

class Warranty(models.Model):
    warranty_id = models.AutoField(primary_key=True)
    id_customer = models.ForeignKey(Customer, on_delete=models.CASCADE, db_column='id_customer')
    product_name = models.CharField(max_length=200)
    start_date = models.DateField()
    end_date = models.DateField()
    details = models.TextField(blank=True)

    class Meta:
        managed = False
        db_table = 'Warranty'

class Defect(models.Model):
    defect_id = models.AutoField(primary_key=True)
    id_customer = models.ForeignKey(Customer, on_delete=models.CASCADE, db_column='id_customer')
    report_date = models.DateField(null=True, blank=True)
    accident_date = models.DateField(blank=True, null=True)
    resolution_deadline = models.DateField(null=True, blank=True)

    DEFECT_CHOICES = [
        ('Lighting Strike', 'Lighting Strike'),
        ('Fire Disaster', 'Fire Disaster'),
        ('Other', 'Other'),
    ] 
    defect_type = models.CharField(max_length=100, choices=DEFECT_CHOICES, default='Other')
    status = models.CharField(max_length=50, default='Pending')

    class Meta:
        managed = False
        db_table = 'Defect'

class CustomerFile(models.Model):
    file = models.FileField(upload_to='customer_files/')
    description = models.CharField(max_length=255, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    id_customer = models.ForeignKey(Customer, on_delete=models.CASCADE, db_column='id_customer')

    class Meta:
        managed = False
        db_table = 'CustomerFile' 
        verbose_name = 'Customer File'
        verbose_name_plural = 'Customer Files'

class InsuranceRenewalNotice(models.Model):
    id = models.AutoField(primary_key=True)
    insurance = models.ForeignKey(Insurance, on_delete=models.CASCADE, db_column='insurance_id')
    renewal_year = models.IntegerField()
    due_date = models.DateField()
    is_dismissed = models.BooleanField(default=False)

    class Meta:
        managed = False
        db_table = 'InsuranceRenewalNotice'
        unique_together = ('insurance', 'renewal_year')

    def __str__(self):
        return f"{self.insurance.no_insurance} - Renewal for {self.renewal_year}"