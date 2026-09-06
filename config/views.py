from django.db import connection
from django.http import HttpResponse


def healthcheck(request):
    """
    Liveness/readiness check for a container orchestrator (see
    deploy/docker-compose.yml). Confirms the app can actually reach its
    database, not just that the process is running.
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception:
        return HttpResponse("unavailable", status=503)

    return HttpResponse("ok")
