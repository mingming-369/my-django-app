from .models import Insurance, Warranty, Defect, InsuranceRenewalNotice
from django.utils import timezone
from datetime import date

def notification_counters(request):   
    if not request.user.is_authenticated:
        return {} 

    today = timezone.now().date()
    thirty_days_from_now = today + timezone.timedelta(days=30)
       
    expiring_insurances = Insurance.objects.filter(
        end_period__lte=thirty_days_from_now
    ).count()
    
    expiring_warranties = Warranty.objects.filter(
        end_date__lte=thirty_days_from_now
    ).count()
    
    expiring_defects = Defect.objects.filter(
        resolution_deadline__lte=thirty_days_from_now
    ).count()
    
    total_expiring_count = expiring_insurances + expiring_warranties + expiring_defects

    pending_renewal_count = 0
    if request.user.has_perm('insurance_app.change_insurance'):
        
        active_policies = Insurance.objects.filter(end_period__gt=today)
        
        for policy in active_policies:
            start_year = policy.starting_period.year
            end_year = policy.end_period.year

            for year in range(start_year + 1, end_year + 1):
                renewal_due_date = policy.end_period.replace(year=year)

                if renewal_due_date <= today and today < policy.end_period:
                    notice, created = InsuranceRenewalNotice.objects.get_or_create(
                        insurance=policy,
                        renewal_year=year,
                        defaults={'due_date': renewal_due_date, 'is_dismissed': False}
                    )
                    if not notice.is_dismissed:
                        pending_renewal_count += 1

    return {
        'expiring_items_count': total_expiring_count,
        'pending_renewal_count': pending_renewal_count,
    }