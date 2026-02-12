# Custom validators 
from django.core.exceptions import ValidationError 
import re 
 
def validate_serial_number(value): 
    if not re.match(r'[A-Z0-9\-]{6,20}$', value): 
        raise ValidationError('Invalid serial number format') 
