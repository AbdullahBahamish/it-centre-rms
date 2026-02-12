# Workshop signals 
from django.db.models.signals import post_save 
from django.dispatch import receiver 
from .models.repair_case import RepairCase 
 
@receiver(post_save, sender=RepairCase) 
def log_repair_status_change(sender, instance, created, **kwargs): 
    if not created:  # Only log updates 
        # TODO: Add audit logging 
        pass 
