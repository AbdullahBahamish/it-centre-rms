from django.contrib import admin 
from .models.device import Device 
from .models.repair_case import RepairCase 
 
admin.site.register(Device) 
admin.site.register(RepairCase) 
