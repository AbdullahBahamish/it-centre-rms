from django.db import models 
from apps.core.models import TimeStampedModel, UUIDModel 
 
class Device(TimeStampedModel, UUIDModel): 
    DEVICE_TYPES = [ 
        ('laptop', 'Laptop'), 
        ('desktop', 'Desktop'), 
        ('tablet', 'Tablet'), 
        ('phone', 'Phone'), 
        ('printer', 'Printer'), 
    ] 
 
    serial_number = models.CharField(max_length=50, unique=True) 
    device_type = models.CharField(max_length=20, choices=DEVICE_TYPES) 
    brand = models.CharField(max_length=50) 
    model = models.CharField(max_length=50) 
    owner_name = models.CharField(max_length=100) 
    owner_email = models.EmailField() 
 
    def __str__(self): 
        return f'{self.brand} {self.model} ({self.serial_number})' 
