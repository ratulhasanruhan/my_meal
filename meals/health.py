"""Unauthenticated health check.

Reports which database the running instance is actually pointed at and how long
connecting takes. Deliberately prints no password. Kept because on serverless a
misconfigured host shows up as a killed function with no traceback, and this is
the only way to see the live configuration from outside.
"""

import time
import traceback

from django.conf import settings
from django.db import connection
from django.http import HttpResponse


def healthz(request):
    db = settings.DATABASES["default"]
    lines = [
        f"engine        {db['ENGINE'].rsplit('.', 1)[-1]}",
        f"host          {db.get('HOST')}",
        f"port          {db.get('PORT')}",
        f"user          {db.get('USER')}",
        f"password_set  {bool(db.get('PASSWORD'))}",
        f"options       {db.get('OPTIONS')}",
        f"conn_max_age  {db.get('CONN_MAX_AGE')}",
        f"debug         {settings.DEBUG}",
    ]

    for attempt in (1, 2):
        started = time.monotonic()
        try:
            with connection.cursor() as cursor:
                cursor.execute("select 1")
                cursor.fetchone()
            lines.append(f"query {attempt}       OK in {time.monotonic() - started:.2f}s")
        except Exception as exc:
            lines.append(
                f"query {attempt}       FAILED in {time.monotonic() - started:.2f}s "
                f"{type(exc).__name__}: {str(exc).strip()[:160]}"
            )

    started = time.monotonic()
    try:
        from django.contrib.auth import get_user_model

        count = get_user_model().objects.count()
        lines.append(f"auth_user     {count} rows in {time.monotonic() - started:.2f}s")
    except Exception as exc:
        lines.append(f"auth_user     FAILED {type(exc).__name__}: {str(exc).strip()[:160]}")

    started = time.monotonic()
    try:
        from .models import MealPlan

        count = MealPlan.objects.count()
        lines.append(f"meals_mealplan {count} rows in {time.monotonic() - started:.2f}s")
    except Exception as exc:
        lines.append(f"meals_mealplan FAILED {type(exc).__name__}: {str(exc).strip()[:160]}")

    # ?trace=/some/path renders that page in this same process, as a logged-in
    # user, and reports the traceback. A view that dies without one is being
    # killed by the platform rather than raising.
    target = request.GET.get("trace")
    if target:
        lines.append(f"\n=== rendering {target} ===")
        started = time.monotonic()
        try:
            from django.contrib.auth import get_user_model
            from django.test import Client

            user = get_user_model().objects.filter(is_superuser=True).first()
            client = Client()
            client.force_login(user)
            response = client.get(target)
            lines.append(
                f"status {response.status_code} in {time.monotonic() - started:.2f}s, "
                f"{len(response.content)} bytes"
            )
        except Exception:
            lines.append(f"raised after {time.monotonic() - started:.2f}s:")
            lines.append(traceback.format_exc(limit=25))

    return HttpResponse("\n".join(lines) + "\n", content_type="text/plain; charset=utf-8")
