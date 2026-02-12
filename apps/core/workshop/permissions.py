# Workshop permissions 
from rest_framework.permissions import BasePermission 
 
class IsTechnician(BasePermission): 
    def has_permission(self, request, view): 
        return request.user.groups.filter(name='Technicians').exists() 
