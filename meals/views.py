import calendar
import json
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from . import services
from .forms import MealPlanForm, MealRateForm, PaymentForm
from .models import MealEntry, MealPlan, MealRate, Payment, Slot

MONTH_NAMES = list(calendar.month_name)
MAX_QUANTITY = 20


def _today():
    return timezone.localdate()


def _requested_month(request, today):
    try:
        year = int(request.GET.get("y", today.year))
        month = int(request.GET.get("m", today.month))
        date(year, month, 1)
    except (ValueError, TypeError):
        return today.year, today.month
    return year, month


@login_required
def dashboard(request):
    today = _today()
    year, month = _requested_month(request, today)

    summary = services.month_summary(year, month, today)
    ledger = services.month_ledger(year, month, today)
    resolver = summary["resolver"]

    by_date = {d["date"]: d for d in summary["days"]}
    cal = calendar.Calendar(firstweekday=6)  # weeks start on Sunday
    weeks = []
    for week in cal.monthdatescalendar(year, month):
        row = []
        for day in week:
            info = by_date.get(day)
            row.append(
                {
                    "date": day,
                    "day": day.day,
                    "in_month": day.month == month,
                    "is_today": day == today,
                    "is_future": day > today,
                    "lunch": info["lunch"] if info else 0,
                    "dinner": info["dinner"] if info else 0,
                    "cost": info["cost"] if info else 0,
                    "overridden": info["overridden"] if info else False,
                }
            )
        weeks.append(row)

    prev_y, prev_m = services.shift_month(year, month, -1)
    next_y, next_m = services.shift_month(year, month, 1)

    return render(
        request,
        "meals/dashboard.html",
        {
            "year": year,
            "month": month,
            "month_label": f"{MONTH_NAMES[month]} {year}",
            "weeks": weeks,
            "weekday_labels": ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],
            "prev_url": f"?y={prev_y}&m={prev_m}",
            "next_url": f"?y={next_y}&m={next_m}",
            "is_current_month": (year, month) == (today.year, today.month),
            "summary": summary,
            "ledger": ledger,
            "current_rate": MealRate.price_on(today),
            "today": today,
            "today_lunch": resolver.quantity(today, Slot.LUNCH) if today <= summary["last"] and today >= summary["first"] else 0,
            "today_dinner": resolver.quantity(today, Slot.DINNER) if today <= summary["last"] and today >= summary["first"] else 0,
            "has_plan": services.tracking_start() is not None,
            "max_quantity": MAX_QUANTITY,
        },
    )


@login_required
@require_POST
def set_meal(request):
    """Set a slot's quantity, either for one day or as a standing rule.

    Body: {date, slot, quantity, scope} where scope is "once" | "onward".
    """
    try:
        payload = json.loads(request.body or "{}")
        day = date.fromisoformat(payload["date"])
        slot = payload["slot"]
        quantity = int(payload["quantity"])
        scope = payload.get("scope", "once")
    except (ValueError, KeyError, TypeError):
        return JsonResponse({"error": "Bad request"}, status=400)

    if slot not in Slot.values:
        return JsonResponse({"error": "Unknown slot"}, status=400)
    if not 0 <= quantity <= MAX_QUANTITY:
        return JsonResponse({"error": f"Quantity must be 0–{MAX_QUANTITY}"}, status=400)
    if scope not in {"once", "onward"}:
        return JsonResponse({"error": "Unknown scope"}, status=400)
    if scope == "once" and day > _today():
        return JsonResponse({"error": "Cannot log a meal in the future"}, status=400)

    if scope == "once":
        MealEntry.objects.update_or_create(
            date=day, slot=slot, defaults={"quantity": quantity}
        )
    else:
        services.set_plan_from(day, slot, quantity)

    today = _today()
    summary = services.month_summary(day.year, day.month, today)
    ledger = services.month_ledger(day.year, day.month, today)
    resolver = summary["resolver"]

    return JsonResponse(
        {
            "date": day.isoformat(),
            "slot": slot,
            "scope": scope,
            "quantity": resolver.quantity(day, slot),
            "day_cost": float(resolver.day_cost(day)),
            "month_cost": float(summary["cost"]),
            "month_meals": summary["total_meals"],
            "month_due": float(ledger["closing"]),
            "days": [
                {
                    "date": d["date"].isoformat(),
                    "lunch": d["lunch"],
                    "dinner": d["dinner"],
                    "cost": float(d["cost"]),
                }
                for d in summary["days"]
            ],
        }
    )


@login_required
def report(request):
    today = _today()
    year, month = _requested_month(request, today)

    summary = services.month_summary(year, month, today)
    ledger = services.month_ledger(year, month, today)

    taken_days = [d for d in summary["days"] if d["counted"] and d["meals"]]
    skipped = [d for d in summary["days"] if d["counted"] and not d["meals"]]

    # Contiguous runs of days with meals, and the gaps between them.
    runs = []
    for day in taken_days:
        if runs and (day["date"] - runs[-1][-1]["date"]).days == 1:
            runs[-1].append(day)
        else:
            runs.append([day])

    gaps = []
    for earlier, later in zip(runs, runs[1:]):
        gaps.append(
            {
                "start": earlier[-1]["date"],
                "end": later[0]["date"],
                "days": (later[0]["date"] - earlier[-1]["date"]).days - 1,
            }
        )

    prev_y, prev_m = services.shift_month(year, month, -1)
    next_y, next_m = services.shift_month(year, month, 1)

    return render(
        request,
        "meals/report.html",
        {
            "year": year,
            "month": month,
            "month_label": f"{MONTH_NAMES[month]} {year}",
            "prev_url": f"?y={prev_y}&m={prev_m}",
            "next_url": f"?y={next_y}&m={next_m}",
            "is_current_month": (year, month) == (today.year, today.month),
            "summary": summary,
            "ledger": ledger,
            "runs": [{"start": r[0]["date"], "end": r[-1]["date"], "days": len(r)} for r in runs],
            "gaps": gaps,
            "skipped": skipped,
            "taken_days": taken_days,
            "rate": MealRate.price_on(summary["last"]),
            "today": today,
        },
    )


@login_required
def analytics(request):
    today = _today()
    stats = services.lifetime_stats(today)

    if stats.get("empty"):
        return render(request, "meals/analytics.html", {"empty": True})

    trend = services.monthly_trend(12, today)
    max_cost = max((float(t["cost"]) for t in trend), default=0) or 1
    busiest = max(trend, key=lambda t: t["cost"])

    return render(
        request,
        "meals/analytics.html",
        {
            "empty": False,
            "stats": stats,
            "trend": trend,
            "max_cost": max_cost,
            "busiest_month": busiest if busiest["cost"] else None,
            "weekday": services.weekday_breakdown(today),
            "balance_abs": abs(stats["balance"]),
        },
    )


@login_required
def settings_view(request):
    today = _today()
    rate_form = MealRateForm()
    payment_form = PaymentForm(initial={"date": today})
    plan_form = MealPlanForm(initial={"effective_from": today, "quantity": 1})

    if request.method == "POST":
        if "save_rate" in request.POST:
            rate_form = MealRateForm(request.POST)
            if rate_form.is_valid():
                rate_form.save()
                messages.success(request, "Meal rate updated.")
                return redirect("settings")
        elif "save_plan" in request.POST:
            plan_form = MealPlanForm(request.POST)
            if plan_form.is_valid():
                data = plan_form.cleaned_data
                services.set_plan_from(
                    data["effective_from"], data["slot"], data["quantity"]
                )
                messages.success(request, "Meal plan updated.")
                return redirect("settings")
        elif "save_payment" in request.POST:
            payment_form = PaymentForm(request.POST)
            if payment_form.is_valid():
                payment_form.save()
                messages.success(request, "Payment recorded.")
                return redirect("settings")
        elif "delete_rate" in request.POST:
            MealRate.objects.filter(pk=request.POST.get("delete_rate")).delete()
            messages.success(request, "Rate removed.")
            return redirect("settings")
        elif "delete_plan" in request.POST:
            MealPlan.objects.filter(pk=request.POST.get("delete_plan")).delete()
            messages.success(request, "Plan rule removed.")
            return redirect("settings")
        elif "delete_payment" in request.POST:
            Payment.objects.filter(pk=request.POST.get("delete_payment")).delete()
            messages.success(request, "Payment removed.")
            return redirect("settings")

    stats = services.lifetime_stats(today)
    balance = stats["balance"] if not stats.get("empty") else services.ZERO

    return render(
        request,
        "meals/settings.html",
        {
            "rate_form": rate_form,
            "payment_form": payment_form,
            "plan_form": plan_form,
            "rates": MealRate.objects.all(),
            "plans": MealPlan.objects.all(),
            "payments": Payment.objects.all()[:20],
            "current_rate": MealRate.price_on(today),
            "lifetime_cost": services.ZERO if stats.get("empty") else stats["cost"],
            "paid": services.ZERO if stats.get("empty") else stats["paid"],
            "balance": balance,
            "balance_abs": abs(balance),
            "has_plan": services.tracking_start() is not None,
        },
    )
