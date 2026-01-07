from django.shortcuts import render, get_object_or_404, redirect
from .models import Customer, Insurance, Warranty, Defect, CustomerFile, InsuranceRenewalNotice 
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q, Max
from django.contrib import messages
from django.utils import timezone
from django.db import transaction
from itertools import chain
from django.contrib.auth.decorators import login_required, permission_required
import os
import json
from datetime import date 

def get_status_color(end_date):
    today = timezone.now().date()
    thirty_days_from_now = today + timezone.timedelta(days=30)
    
    if end_date < today:
        return 'red' 
    if today <= end_date <= thirty_days_from_now:
        return 'yellow'
    return 'green'

def get_detailed_group_status(items, date_field_name):
    if not items:
        return {'color': 'gray', 'green': 0, 'yellow': 0, 'red': 0, 'gray': 0, 'total': 0}

    status_counts = {'green': 0, 'yellow': 0, 'red': 0, 'gray': 0}
    for item in items:
        color = get_status_color(getattr(item, date_field_name)) 
        status_counts[color] += 1
    
    summary_color = 'green' 
    statuses_present = {s for s, count in status_counts.items() if count > 0}
    
    if 'yellow' in statuses_present:
        summary_color = 'yellow'
    elif 'red' in statuses_present and 'green' in statuses_present:
        summary_color = 'yellow'
    elif statuses_present == {'green'}:
        summary_color = 'green'
    elif statuses_present == {'red'}:
        summary_color = 'red'

    return {
        'color': summary_color,
        'green': status_counts['green'],
        'yellow': status_counts['yellow'],
        'red': status_counts['red'],
        'total': len(items)
    }

@login_required
def main_page(request):
    today = timezone.now().date()
    thirty_days_from_now = today + timezone.timedelta(days=30)
    expired_insurances = Insurance.objects.filter(end_period__lt=today).count()
    expired_warranties = Warranty.objects.filter(end_date__lt=today).count()
    expired_defects = Defect.objects.filter(resolution_deadline__lt=today, accident_date__isnull=True).count()
    total_expired_count = expired_insurances + expired_warranties + expired_defects
    expiring_insurances = Insurance.objects.filter(end_period__gte=today, end_period__lte=thirty_days_from_now).count()
    expiring_warranties = Warranty.objects.filter(end_date__gte=today, end_date__lte=thirty_days_from_now).count()
    expiring_defects = Defect.objects.filter(resolution_deadline__gte=today, resolution_deadline__lte=thirty_days_from_now, accident_date__isnull=True).count()
    total_expiring_soon_count = expiring_insurances + expiring_warranties + expiring_defects

    total_customers_count = Customer.objects.count()
    active_policies_count = Insurance.objects.filter(end_period__gte=today).count()
    
    context = {
        'total_expired_count': total_expired_count,
        'expiring_items_count': total_expiring_soon_count,
        'total_customers_count': total_customers_count,
        'active_policies_count': active_policies_count, 
    }
    return render(request, 'insurance_app/main_page.html', context)

@login_required
def notification_page(request):
    today = timezone.now().date()
    thirty_days_from_now = today + timezone.timedelta(days=30)
    
    insurances = Insurance.objects.filter(end_period__lte=thirty_days_from_now)
    warranties = Warranty.objects.filter(end_date__lte=thirty_days_from_now)
    defects = Defect.objects.filter(resolution_deadline__lte=thirty_days_from_now, accident_date__isnull=True)

    expiring_items = []
    
    for item in insurances:
        expiring_items.append({
            'type': 'Insurance',
            'customer': item.id_customer,
            'end_date': item.end_period,
            'status_color': get_status_color(item.end_period)
        })
    for item in warranties:
        expiring_items.append({
            'type': 'Warranty',
            'customer': item.id_customer,
            'end_date': item.end_date,
            'status_color': get_status_color(item.end_date)
        })
    for item in defects:
        expiring_items.append({
            'type': 'Defect Liability',
            'customer': item.id_customer,
            'end_date': item.resolution_deadline,
            'status_color': get_status_color(item.resolution_deadline)
        })
    sorted_expiring_items = sorted(expiring_items, key=lambda x: x['end_date'])
    
    context = {
        'items': sorted_expiring_items,
    }
    return render(request, 'insurance_app/notification_page.html', context)


@login_required
@permission_required('insurance_app.change_insurance', raise_exception=True) 
def renewal_notices_page(request):
    today = timezone.now().date()
    active_policies = Insurance.objects.filter(end_period__gt=today)
    
    for policy in active_policies:
        start_year = policy.starting_period.year
        end_year = policy.end_period.year

        for year in range(start_year + 1, end_year + 1):
            renewal_due_date = policy.end_period.replace(year=year)

            if renewal_due_date <= today and today < policy.end_period:
                InsuranceRenewalNotice.objects.get_or_create(
                    insurance=policy,
                    renewal_year=year,
                    defaults={'due_date': renewal_due_date, 'is_dismissed': False}
                )

    renewal_notices_to_show = InsuranceRenewalNotice.objects.filter(
        is_dismissed=False,
        due_date__lte=today 
    ).order_by('due_date')

    context = {
        'renewal_notices': renewal_notices_to_show,
    }
    return render(request, 'insurance_app/renewal_notices.html', context)

@login_required
@permission_required('insurance_app.change_insurance', raise_exception=True)
def dismiss_renewal(request, notice_pk):
    if request.method == 'POST':
        notice = get_object_or_404(InsuranceRenewalNotice, pk=notice_pk)
        notice.is_dismissed = True
        notice.save()
        messages.success(request, f"Renewal for {notice.insurance.no_insurance} (Year {notice.renewal_year}) has been marked as complete.")
    
    return redirect('renewal_notices_page') 

@login_required
@permission_required('insurance_app.view_customer', raise_exception=True)
def customer_list(request):
    query = request.GET.get('query', '')
    search_field = request.GET.get('search_field', 'all')
    sort_by = request.GET.get('sort_by', 'customer_name')

    customers_list = Customer.objects.all()

    if query:
        if search_field == 'name': customers_list = customers_list.filter(customer_name__icontains=query)
        elif search_field == 'id': customers_list = customers_list.filter(id_customer__icontains=query)
        elif search_field == 'email': customers_list = customers_list.filter(email__icontains=query)
        elif search_field == 'address': customers_list = customers_list.filter(address__icontains=query)
        elif search_field == 'phone': customers_list = customers_list.filter(phone_num__icontains=query)
        else:
            customers_list = customers_list.filter(
                Q(id_customer__icontains=query) | 
                Q(customer_name__icontains=query) | 
                Q(address__icontains=query) | 
                Q(email__icontains=query) | 
                Q(phone_num__icontains=query)
            )
    valid_sort_fields = ['id_customer', 'customer_name', 'email', 'phone_num']
    if sort_by.lstrip('-') in valid_sort_fields:
        customers_list = customers_list.order_by(sort_by)

    paginator = Paginator(customers_list, 10) 
    page_number = request.GET.get('page')
    
    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    for customer in page_obj:
        insurances = list(Insurance.objects.filter(id_customer=customer))
        warranties = list(Warranty.objects.filter(id_customer=customer))
        defects = list(Defect.objects.filter(id_customer=customer, accident_date__isnull=True))
        customer.insurance_status = get_detailed_group_status(insurances, 'end_period')
        customer.warranty_status = get_detailed_group_status(warranties, 'end_date')
        customer.defect_status = get_detailed_group_status(defects, 'resolution_deadline')

    context = {
        'page_obj': page_obj, 
        'is_paginated': page_obj.has_other_pages(),
        'query': query,
        'search_field': search_field,
        'current_sort': sort_by,
    }
    return render(request, 'insurance_app/customer_list.html', context)


@login_required
@permission_required('insurance_app.view_customer', raise_exception=True)
def customer_detail(request, pk):
    customer = get_object_or_404(Customer, pk=pk)

    insurances = Insurance.objects.filter(id_customer=customer)
    for item in insurances:
        item.status_color = get_status_color(item.end_period)
        item.generic_end_date = item.end_period
        
    warranties = Warranty.objects.filter(id_customer=customer)
    for item in warranties:
        item.status_color = get_status_color(item.end_date)
        item.generic_end_date = item.end_date

    defects = Defect.objects.filter(id_customer=customer, accident_date__isnull=True)
    for item in defects:
        item.status_color = get_status_color(item.resolution_deadline)
        item.generic_end_date = item.resolution_deadline

    customer_files = CustomerFile.objects.filter(id_customer=customer)
    all_items_for_status = list(insurances) + list(warranties) + list(defects)
    
    if not all_items_for_status:
        customer.status_color, customer.status_text = 'gray', 'No Items'
    else:
        status_details = get_detailed_group_status(all_items_for_status, 'generic_end_date')
        customer.status_color = status_details['color'] 
        
        if customer.status_color == 'green': customer.status_text = 'Active'
        elif customer.status_color == 'yellow': customer.status_text = 'Attention Needed'
        elif customer.status_color == 'red': customer.status_text = 'Expired'
        else: customer.status_text = 'No Items'

    context = {
        'customer': customer,
        'insurances': insurances,
        'warranties': warranties,
        'defects': defects,
        'customer_files': customer_files,
    }
    return render(request, 'insurance_app/customer_detail.html', context)

@login_required
@permission_required('insurance_app.add_customer', raise_exception=True)
def add_customer(request):
    if request.method == 'POST':
        try:
            with transaction.atomic():
                in_charge = request.POST.get('in_charge_person')
                if in_charge == 'Other':
                    in_charge = request.POST.get('in_charge_other')

                proposal = request.POST.get('proposal_prepared_by')
                if proposal == 'Other':
                    proposal = request.POST.get('proposal_other')

                engineer_list = request.POST.getlist('engineers')
                engineers_other = request.POST.get('engineers_other')
                if engineers_other:
                    extras = [e.strip() for e in engineers_other.split(',') if e.strip()]
                    engineer_list.extend(extras)
                
                engineers_str = ",".join(engineer_list)

                Customer.objects.create(
                    id_customer=request.POST.get('id_customer'),
                    customer_name=request.POST.get('customer_name'),
                    address=request.POST.get('address', ''), 
                    email=request.POST.get('email', ''), 
                    phone_num=request.POST.get('phone_num', ''), 
                    in_charge_person=in_charge,
                    proposal_prepared_by=proposal,
                    engineers=engineers_str,
                    installer=request.POST.get('installer', ''),
                    installed_on=request.POST.get('installed_on') or None
                )
                messages.success(request, f"Customer '{request.POST.get('customer_name')}' was added successfully!")
            return redirect('main_page')
        except Exception as e:
            messages.error(request, f"Error saving customer: {e}")
            return redirect('add_customer')
            
    context = {
        'in_charge_choices': Customer.IN_CHARGE_CHOICES,
        'proposal_choices': Customer.PROPOSAL_ENGINEER_CHOICES,
        'engineer_choices': Customer.PROPOSAL_ENGINEER_CHOICES,
    }
    return render(request, 'insurance_app/add_customer.html', context)


@login_required
@permission_required('insurance_app.change_customer', raise_exception=True)
def edit_customer(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    
    in_charge_values = [c[0] for c in Customer.IN_CHARGE_CHOICES]
    proposal_values = [c[0] for c in Customer.PROPOSAL_ENGINEER_CHOICES]
    engineer_values = [c[0] for c in Customer.PROPOSAL_ENGINEER_CHOICES] 

    if request.method == 'POST':

        in_charge = request.POST.get('in_charge_person')
        if in_charge == 'Other':
            in_charge = request.POST.get('in_charge_other')

        proposal = request.POST.get('proposal_prepared_by')
        if proposal == 'Other':
            proposal = request.POST.get('proposal_other')

        engineer_list = request.POST.getlist('engineers')
        engineers_other = request.POST.get('engineers_other')
        if engineers_other:
            extras = [e.strip() for e in engineers_other.split(',') if e.strip()]
            engineer_list.extend(extras)
        
        engineers_str = ",".join(engineer_list)

        customer.customer_name = request.POST.get('customer_name')
        customer.address = request.POST.get('address', '') 
        customer.email = request.POST.get('email', '') 
        customer.phone_num = request.POST.get('phone_num', '') 
        
        customer.in_charge_person = in_charge
        customer.proposal_prepared_by = proposal
        customer.engineers = engineers_str
        customer.installer = request.POST.get('installer', '')
        installed_on_val = request.POST.get('installed_on')
        customer.installed_on = installed_on_val if installed_on_val else None

        customer.save()
        messages.success(request, "Customer details updated successfully.")
        return redirect('customer_detail', pk=customer.id_customer)
    
    saved_engineers_all = []
    if customer.engineers:
        saved_engineers_all = customer.engineers.split(',')
    
    saved_engineers = [e for e in saved_engineers_all if e in engineer_values]
    custom_engineers = [e for e in saved_engineers_all if e not in engineer_values]
    custom_engineers_str = ", ".join(custom_engineers)

    context = {
        'customer': customer,
        'in_charge_choices': Customer.IN_CHARGE_CHOICES,
        'in_charge_values': in_charge_values, 
        'proposal_choices': Customer.PROPOSAL_ENGINEER_CHOICES,
        'proposal_values': proposal_values,   
        'engineer_choices': Customer.PROPOSAL_ENGINEER_CHOICES,
        'saved_engineers': saved_engineers,
        'custom_engineers_str': custom_engineers_str, 
    }
    return render(request, 'insurance_app/edit_customer.html', context)

@login_required
@permission_required('insurance_app.delete_customer', raise_exception=True)
def delete_customer(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    if request.method == 'POST':
        customer_name = customer.customer_name
        customer.delete()
        messages.success(request, f"Customer '{customer_name}' and all related records have been deleted.")
        return redirect('customer_list')
    return render(request, 'insurance_app/delete_customer_confirm.html', {'customer': customer})

@login_required
@permission_required('insurance_app.add_insurance', raise_exception=True)
def add_insurance(request):
    customers = Customer.objects.all()
    if request.method == 'POST':
        customer_id = request.POST.get('id_customer')

        if not customer_id:
            messages.error(request, "Please search and select a valid customer from the list.")
            return render(request, 'insurance_app/add_insurance.html', {'customers': customers})

        try:
            customer = Customer.objects.get(pk=customer_id)
        except Customer.DoesNotExist:
            messages.error(request, f"Customer with ID '{customer_id}' not found. Please select a valid customer.")
            return render(request, 'insurance_app/add_insurance.html', {'customers': customers})

        try:
            Insurance.objects.create(
                no_insurance=request.POST.get('no_insurance'),
                sum_amount=request.POST.get('sum_amount'),
                starting_period=request.POST.get('starting_period'),
                end_period=request.POST.get('end_period'),
                id_customer=customer,
                total_payable=request.POST.get('total_payable'),
                status=request.POST.get('status'),
                ins_co=request.POST.get('ins_co')
            )
            messages.success(request, "New insurance policy added successfully.")
            return redirect('main_page')
        except Exception as e:
            messages.error(request, f"Error saving policy: {e}")
            return render(request, 'insurance_app/add_insurance.html', {'customers': customers})
        
    return render(request, 'insurance_app/add_insurance.html', {'customers': customers})


@login_required
@permission_required('insurance_app.change_insurance', raise_exception=True)
def edit_insurance(request, pk):
    insurance = get_object_or_404(Insurance, pk=pk)
    if request.method == 'POST':
        insurance.sum_amount = request.POST.get('sum_amount')
        insurance.starting_period = request.POST.get('starting_period')
        insurance.end_period = request.POST.get('end_period')
        insurance.total_payable = request.POST.get('total_payable')
        insurance.status = request.POST.get('status')
        insurance.ins_co = request.POST.get('ins_co')
        insurance.save()
        messages.success(request, f"Insurance policy '{insurance.no_insurance}' updated successfully.")
        return redirect('customer_detail', pk=insurance.id_customer.id_customer)
    return render(request, 'insurance_app/edit_insurance.html', {'insurance': insurance})

@login_required
@permission_required('insurance_app.delete_insurance', raise_exception=True)
def delete_insurance(request, pk):
    insurance = get_object_or_404(Insurance, pk=pk)
    customer_pk = insurance.id_customer.id_customer
    
    if request.method == 'POST':
        insurance_no = insurance.no_insurance
        insurance.delete()
        messages.success(request, f"Insurance policy '{insurance_no}' has been deleted.")
        return redirect('customer_detail', pk=customer_pk)
    
    return render(request, 'insurance_app/delete_insurance_confirm.html', {'insurance': insurance})

@login_required
@permission_required('insurance_app.add_warranty', raise_exception=True)
def add_warranty(request, customer_pk):
    customer = get_object_or_404(Customer, pk=customer_pk)
    if request.method == 'POST':
        product_choice = request.POST.get('product_select')
        other_product = request.POST.get('product_other', '').strip()
        final_product_name = ""

        if product_choice == 'other':
            if other_product:
                final_product_name = other_product
            else:
                messages.error(request, "You selected 'Other' but did not specify a product name.")
                return redirect('add_warranty', customer_pk=customer_pk)
        elif product_choice:
            final_product_name = product_choice
        else:
            messages.error(request, "You must select a product name.")
            return redirect('add_warranty', customer_pk=customer_pk)

        Warranty.objects.create(
            id_customer=customer,
            product_name=final_product_name,
            start_date=request.POST.get('start_date'),
            end_date=request.POST.get('end_date'),
            details=request.POST.get('details')
        )
        messages.success(request, "New warranty added successfully.")
        return redirect('customer_detail', pk=customer.id_customer)
    
    predefined_items = [
        "Inverter", "String Inverter", "Hybrid Inverter", 
        "Battery-based Inverter", "Micro Inverter", "Central Optimiser", "Central Inverter"
    ]
    context = {
        'customer': customer,
        'predefined_items': predefined_items,
    }
    return render(request, 'insurance_app/add_warranty.html', context)


@login_required
@permission_required('insurance_app.change_warranty', raise_exception=True)
def edit_warranty(request, pk):
    warranty = get_object_or_404(Warranty, pk=pk)
    
    predefined_items = [
        "Inverter", "String Inverter", "Hybrid Inverter", 
        "Battery-based Inverter", "Micro Inverter", "Central Optimiser", "Central Inverter"
    ]
    
    if request.method == 'POST':
        product_choice = request.POST.get('product_select')
        other_product = request.POST.get('product_other', '').strip()
        final_product_name = ""

        if product_choice == 'other':
            if other_product:
                final_product_name = other_product
            else:
                messages.error(request, "You selected 'Other' but did not specify a product name.")
                context = {'warranty': warranty, 'predefined_items': predefined_items, 'is_other': True}
                return render(request, 'insurance_app/edit_warranty.html', context)
        elif product_choice:
            final_product_name = product_choice
        else:
            messages.error(request, "You must select a product name.")
            context = {'warranty': warranty, 'predefined_items': predefined_items, 'is_other': False}
            return render(request, 'insurance_app/edit_warranty.html', context)
        
        warranty.product_name = final_product_name
        warranty.start_date = request.POST.get('start_date')
        warranty.end_date = request.POST.get('end_date')
        warranty.details = request.POST.get('details')
        warranty.save()
        messages.success(request, "Warranty details updated successfully.")
        return redirect('customer_detail', pk=warranty.id_customer.id_customer)
    
    is_other = warranty.product_name not in predefined_items
    context = {
        'warranty': warranty,
        'predefined_items': predefined_items,
        'is_other': is_other
    }
    return render(request, 'insurance_app/edit_warranty.html', context)

@login_required
@permission_required('insurance_app.delete_warranty', raise_exception=True)
def delete_warranty(request, pk):
    warranty = get_object_or_404(Warranty, pk=pk)
    customer_pk = warranty.id_customer.id_customer
    if request.method == 'POST':
        warranty.delete()
        messages.success(request, "Warranty has been deleted.")
        return redirect('customer_detail', pk=customer_pk)
    return render(request, 'insurance_app/delete_warranty_confirm.html', {'warranty': warranty})

@login_required
@permission_required('insurance_app.add_defect', raise_exception=True)
def add_defect(request, customer_pk):
    customer = get_object_or_404(Customer, pk=customer_pk)
    if request.method == 'POST':
        Defect.objects.create(
            id_customer=customer,
            report_date=request.POST.get('report_date'),
            resolution_deadline=request.POST.get('resolution_deadline')
        )
        messages.success(request, "New defect liability period added successfully.")
        return redirect('customer_detail', pk=customer.id_customer)
    return render(request, 'insurance_app/add_defect.html', {'customer': customer})


@login_required
@permission_required('insurance_app.change_defect', raise_exception=True)
def edit_defect(request, pk):
    defect = get_object_or_404(Defect, pk=pk)
    if request.method == 'POST':

        r_date = request.POST.get('report_date')
        if r_date: 
            defect.report_date = r_date 
   
        a_date = request.POST.get('accident_date')
        if a_date:
            defect.accident_date = a_date

        defect.resolution_deadline = request.POST.get('resolution_deadline')
        
        defect.save()
        messages.success(request, "Defect record updated successfully.")
        
        if defect.accident_date:
             return redirect('defect_list')
        return redirect('customer_detail', pk=defect.id_customer.id_customer)
        
    return render(request, 'insurance_app/edit_defect.html', {'defect': defect})

@login_required
@permission_required('insurance_app.delete_defect', raise_exception=True)
def delete_defect(request, pk):
    defect = get_object_or_404(Defect, pk=pk)
    customer_pk = defect.id_customer.id_customer
    if request.method == 'POST':
        defect.delete()
        messages.success(request, "Defect report has been deleted.")
        return redirect('customer_detail', pk=customer_pk)
    return render(request, 'insurance_app/delete_defect_confirm.html', {'defect': defect})

@login_required
@permission_required('insurance_app.add_customerfile', raise_exception=True)
def upload_customer_file(request, customer_pk):
    customer = get_object_or_404(Customer, pk=customer_pk)
    if request.method == 'POST' and 'file' in request.FILES:
        try:
            with transaction.atomic():
                CustomerFile.objects.create(
                    id_customer=customer,
                    file=request.FILES['file'],
                    description=request.POST.get('description', '')
                )
            messages.success(request, "File uploaded successfully.")
        except Exception as e:
            messages.error(request, f"Error uploading file: {e}")
    return redirect('customer_detail', pk=customer.id_customer)


@login_required
@permission_required('insurance_app.delete_customerfile', raise_exception=True)
def delete_customer_file(request, file_pk):
    customer_file = get_object_or_404(CustomerFile, pk=file_pk)
    customer_pk = customer_file.id_customer.id_customer

    if request.method == 'POST':
        try:
            if os.path.exists(customer_file.file.path):
                os.remove(customer_file.file.path)
            
            customer_file.delete()
            messages.success(request, f"File '{os.path.basename(customer_file.file.name)}' was deleted successfully.")
        except Exception as e:
            messages.error(request, f"Error deleting file: {e}")    
    return redirect('customer_detail', pk=customer_pk)

@login_required
def defect_list(request):
    defects = Defect.objects.filter(accident_date__isnull=False).order_by('status', '-accident_date')
    context = {'defects': defects}
    return render(request, 'insurance_app/defect_list.html', context)

@login_required
@permission_required('insurance_app.add_defect', raise_exception=True)
def add_defect_record(request):
    customers = Customer.objects.all()

    latest_deadlines = {}
    liability_periods = Defect.objects.filter(resolution_deadline__isnull=False, accident_date__isnull=True)
    
    for d in liability_periods:
        cid = d.id_customer.id_customer
        if cid not in latest_deadlines or d.resolution_deadline > latest_deadlines[cid]:
            latest_deadlines[cid] = d.resolution_deadline

    deadlines_json = json.dumps({k: v.isoformat() for k, v in latest_deadlines.items()})

    if request.method == 'POST':
        customer_id = request.POST.get('id_customer')
        defect_type_selection = request.POST.get('defect_type_select')
        defect_type_other = request.POST.get('defect_type_other')
        accident_date = request.POST.get('report_date')
        resolution_deadline = request.POST.get('resolution_deadline') 

        if not customer_id:
            messages.error(request, "Please search and select a valid customer.")
            return render(request, 'insurance_app/add_defect_record.html', {'customers': customers, 'deadlines_json': deadlines_json})
        
        try:
            customer = Customer.objects.get(pk=customer_id)
        except Customer.DoesNotExist:
            messages.error(request, "Customer not found.")
            return render(request, 'insurance_app/add_defect_record.html', {'customers': customers, 'deadlines_json': deadlines_json})

        final_defect_type = defect_type_selection
        if defect_type_selection == 'Other':
            if defect_type_other:
                final_defect_type = defect_type_other 
            else:
                final_defect_type = 'Other' 

        try:
            Defect.objects.create(
                id_customer=customer,
                defect_type=final_defect_type,
                accident_date=accident_date,
                resolution_deadline=resolution_deadline,
                status='Pending' 
            )
            messages.success(request, "Defect record added successfully.")
            return redirect('defect_list') 
        except Exception as e:
            messages.error(request, f"Error adding defect: {e}")

    return render(request, 'insurance_app/add_defect_record.html', {'customers': customers, 'deadlines_json': deadlines_json})


@login_required
@permission_required('insurance_app.change_defect', raise_exception=True)
def edit_defect_record(request, pk):
    defect = get_object_or_404(Defect, pk=pk)
    
    context = {
        'defect': defect
    }

    if request.method == 'POST':
        defect_type_selection = request.POST.get('defect_type_select')
        defect_type_other = request.POST.get('defect_type_other')
        
        final_defect_type = defect_type_selection
        if defect_type_selection == 'Other':
            if defect_type_other:
                final_defect_type = defect_type_other 
            else:
                final_defect_type = 'Other' 
        
        defect.defect_type = final_defect_type
        
        a_date = request.POST.get('report_date')
        if a_date:
             defect.accident_date = a_date

        defect.resolution_deadline = request.POST.get('resolution_deadline')
        
        try:
            defect.save()
            messages.success(request, "Defect record updated successfully.")
            return redirect('defect_list')
        except Exception as e:
            messages.error(request, f"Error updating defect: {e}")
            
    return render(request, 'insurance_app/edit_defect_record.html', context)


@login_required
@permission_required('insurance_app.delete_defect', raise_exception=True)
def delete_defect_record(request, pk):
    defect = get_object_or_404(Defect, pk=pk)
    
    if request.method == 'POST':
        try:
            defect.delete()
            messages.success(request, "Defect record deleted successfully.")
            return redirect('defect_list')
        except Exception as e:
            messages.error(request, f"Error deleting defect record: {e}")
            
    return render(request, 'insurance_app/delete_defect_record.html', {'defect': defect})


@login_required
@permission_required('insurance_app.change_defect', raise_exception=True)
def solve_defect(request, pk):
    defect = get_object_or_404(Defect, pk=pk)
    if request.method == 'POST':
        defect.status = 'Solved'
        defect.save()
        messages.success(request, f"Defect record for {defect.id_customer.customer_name} marked as Solved.")
    return redirect('defect_list')