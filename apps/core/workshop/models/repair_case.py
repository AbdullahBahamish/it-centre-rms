from django.db import models 
from apps.core.models import TimeStampedModel, UUIDModel 
from apps.workshop.models.device import Device 
 
class RepairCase(TimeStampedModel, UUIDModel): 
    STATUS_CHOICES = [ 
        ('received', 'Received'), 
        ('diagnosing', 'Diagnosing'), 
        ('waiting_parts', 'Waiting for Parts'), 
        ('repairing', 'Repairing'), 
        ('testing', 'Testing'), 
        ('ready', 'Ready for Pickup'), 
        ('closed', 'Closed'), 
    ] 
 
    device = models.ForeignKey(Device, on_delete=models.CASCADE) 
    issue_description = models.TextField() 
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='received') 
    estimated_cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True) 
    actual_cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True) 
    technician_notes = models.TextField(blank=True) 
 
    def __str__(self): 
        return f'Repair #{self.id[:8]} - {self.device}' 
