# Creating the First Administrator

## Create a new administrator

Run this from the project directory with the virtual environment activated:

```powershell
python manage.py createsuperuser
```

Enter the requested username, email address, and password.

## Promote an existing user

If the account already exists, replace `admin` with its actual username:

```powershell
python manage.py shell -c "from django.contrib.auth import get_user_model; from apps.accounts.models import Role; u=get_user_model().objects.get(username='admin'); u.is_staff=True; u.is_superuser=True; u.is_active=True; u.save(update_fields=['is_staff','is_superuser','is_active']); u.userprofile.role=Role.objects.get(name=Role.ADMIN); u.userprofile.save(update_fields=['role']); print('Admin access enabled')"
```

## Verify administrator access

```powershell
python manage.py shell -c "from django.contrib.auth import get_user_model; from apps.core.services import AccessService; u=get_user_model().objects.get(username='admin'); print(u.is_superuser, AccessService.get_role_name(u), AccessService.can(u, 'access_admin_panel'))"
```

Expected output:

```text
True ADMIN True
```

If you do not know the username, list all accounts:

```powershell
python manage.py shell -c "from django.contrib.auth import get_user_model; print(list(get_user_model().objects.values_list('username','is_superuser','is_staff')))"
```

Log out and sign in again after changing an account’s permissions. The RMS administration interface is available at:

```text
/admin-panel/
```

The Django technical administration interface is available at:

```text
/admin/
```

## Troubleshooting role changes

If changing a role displays a `404 Page not found`, the URL may be valid but the access policy rejected the operation. This is intentional security behavior.

Check the current administrator status:

```powershell
python manage.py shell -c "from django.contrib.auth import get_user_model; from apps.core.services import AccessService; u=get_user_model().objects.get(username='admin'); print(u.is_superuser, AccessService.get_role_name(u), AccessService.can(u, 'access_admin_panel'), AccessService.can(u, 'can_assign_roles'))"
```

Expected output:

```text
True ADMIN True True
```

If the account is still `STAFF`, promote it:

```powershell
python manage.py shell -c "from django.contrib.auth import get_user_model; from apps.accounts.models import Role; u=get_user_model().objects.get(username='admin'); u.is_staff=True; u.is_superuser=True; u.is_active=True; u.save(); u.userprofile.role=Role.objects.get(name=Role.ADMIN); u.userprofile.save(update_fields=['role']); print('Admin access enabled')"
```

After changing the account, log out and sign in again. An `ADMIN` can assign `MANAGER`, `STAFF`, and `VIEWER` roles, but cannot assign another user the `ADMIN` role, change their own role, or assign an equal or higher role.
