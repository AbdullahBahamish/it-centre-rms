from django.db import connection
from django.http import JsonResponse


def health_check(request):
    db_ok = True

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception:
        db_ok = False

    return JsonResponse(
        {
            "status": "ok" if db_ok else "degraded",
            "database": db_ok,
        }
    )
