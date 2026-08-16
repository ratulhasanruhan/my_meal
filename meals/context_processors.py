from django.conf import settings


def site(request):
    return {
        "CURRENCY": settings.CURRENCY_SYMBOL,
        "APP_NAME": "My Meal",
    }
