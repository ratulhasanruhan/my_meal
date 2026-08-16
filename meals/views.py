import calendar
import json
from collections import OrderedDict
from datetime import date, timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum
from django.db.models.functions import TruncMonth
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import MealRateForm, PaymentForm
from .models import MealEntry, MealRate, Payment, Slot

MONTH_NAMES = list(calendar.month_name)


def _today():
    return timezone.localdate()


def _month_bounds(year, month):
    first = date(year, month, 1)
    last = date(year, month, calendar.monthrange(year, month)[1])
    return first, last


def _shift_month(year, month, delta):
    index = (year * 12 + (month - 1)) + delta
    return index // 12, index % 12 + 1


def _decimal(value):
    return Decimal(value or 0)


@login_required
def dashboard(request):
    today = _today()
    try:
        year = int(request.GET.get("y", today.year))
        month = int(request.GET.get("m", today.month))
        date(year, month, 1)
    except (ValueError, TypeError):
        year, month = today.year, today.month

    first, last = _month_bounds(year, month)

    entries = MealEntry.objects.filter(date__range=(first, last))
    taken = {(e.date, e.slot): e for e in entries}

    cal = calendar.Calendar(firstweekday=6)  # weeks start on Sunday
    weeks = []
    for week in cal.monthdatescalendar(year, month):
        row = []
        for day in week:
            lunch = taken.get((day, Slot.LUNCH))
            dinner = taken.get((day, Slot.DINNER))
            row.append(
                {
                    "date": day,
                    "day": day.day,
                    "in_month": day.month == month,
                    "is_today": day == today,
                    "is_future": day > today,
                    "lunch": lunch is not None,
                    "dinner": dinner is not None,
                    "cost": (lunch.price if lunch else 0) + (dinner.price if dinner else 0),
                }
            )
        weeks.append(row)

    lunch_count = sum(1 for e in entries if e.slot == Slot.LUNCH)
    dinner_count = sum(1 for e in entries if e.slot == Slot.DINNER)
    total_meals = lunch_count + dinner_count
    total_cost = sum((e.price for e in entries), Decimal("0"))
    active_days = len({e.date for e in entries})

    days_elapsed = min((today - first).days + 1, (last - first).days + 1) if today >= first else 0
    days_in_month = (last - first).days + 1
    if days_elapsed > 0 and today <= last:
        projected = (total_cost / days_elapsed) * days_in_month
    else:
        projected = total_cost

    prev_y, prev_m = _shift_month(year, month, -1)
    next_y, next_m = _shift_month(year, month, 1)

    context = {
        "year": year,
        "month": month,
        "month_label": f"{MONTH_NAMES[month]} {year}",
        "weeks": weeks,
        "weekday_labels": ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],
        "prev_url": f"?y={prev_y}&m={prev_m}",
        "next_url": f"?y={next_y}&m={next_m}",
        "is_current_month": (year, month) == (today.year, today.month),
        "stats": {
            "total_meals": total_meals,
            "lunch_count": lunch_count,
            "dinner_count": dinner_count,
            "total_cost": total_cost,
            "active_days": active_days,
            "avg_per_day": (total_cost / active_days) if active_days else Decimal("0"),
            "projected": projected,
        },
        "current_rate": MealRate.price_on(today),
        "today": today,
        "today_lunch": MealEntry.objects.filter(date=today, slot=Slot.LUNCH).exists(),
        "today_dinner": MealEntry.objects.filter(date=today, slot=Slot.DINNER).exists(),
    }
    return render(request, "meals/dashboard.html", context)


@login_required
@require_POST
def toggle_meal(request):
    """Flip a single meal slot on/off. Returns the new state plus month totals."""
    try:
        payload = json.loads(request.body or "{}")
        day = date.fromisoformat(payload["date"])
        slot = payload["slot"]
    except (ValueError, KeyError, TypeError):
        return JsonResponse({"error": "Bad request"}, status=400)

    if slot not in Slot.values:
        return JsonResponse({"error": "Unknown slot"}, status=400)

    if day > _today():
        return JsonResponse({"error": "Cannot log a meal in the future"}, status=400)

    entry = MealEntry.objects.filter(date=day, slot=slot).first()
    if entry:
        entry.delete()
        active = False
    else:
        MealEntry.objects.create(date=day, slot=slot, price=MealRate.price_on(day))
        active = True

    first, last = _month_bounds(day.year, day.month)
    month_entries = MealEntry.objects.filter(date__range=(first, last))
    totals = month_entries.aggregate(cost=Sum("price"), count=Count("id"))

    return JsonResponse(
        {
            "active": active,
            "date": day.isoformat(),
            "slot": slot,
            "month_cost": float(_decimal(totals["cost"])),
            "month_meals": totals["count"] or 0,
            "day_cost": float(
                _decimal(
                    month_entries.filter(date=day).aggregate(c=Sum("price"))["c"]
                )
            ),
        }
    )


@login_required
def analytics(request):
    today = _today()
    entries = MealEntry.objects.all()

    if not entries.exists():
        return render(request, "meals/analytics.html", {"empty": True})

    # --- 12-month trend -------------------------------------------------
    start_month = date(*_shift_month(today.year, today.month, -11), 1)
    monthly_rows = (
        entries.filter(date__gte=start_month)
        .annotate(bucket=TruncMonth("date"))
        .values("bucket")
        .annotate(cost=Sum("price"), meals=Count("id"))
        .order_by("bucket")
    )
    by_month = {row["bucket"]: row for row in monthly_rows}

    trend = []
    y, m = start_month.year, start_month.month
    for _ in range(12):
        key = date(y, m, 1)
        row = by_month.get(key)
        trend.append(
            {
                "label": f"{calendar.month_abbr[m]}",
                "full_label": f"{calendar.month_abbr[m]} {y}",
                "cost": float(_decimal(row["cost"])) if row else 0.0,
                "meals": row["meals"] if row else 0,
            }
        )
        y, m = _shift_month(y, m, 1)

    max_cost = max((t["cost"] for t in trend), default=0) or 1

    # --- weekday pattern ------------------------------------------------
    weekday_counts = OrderedDict((d, 0) for d in ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"])
    labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    for entry in entries:
        weekday_counts[labels[entry.date.weekday()]] += 1
    max_weekday = max(weekday_counts.values()) or 1
    weekday = [
        {"label": k, "count": v, "pct": round(v / max_weekday * 100)}
        for k, v in weekday_counts.items()
    ]

    # --- slot split -----------------------------------------------------
    slot_rows = entries.values("slot").annotate(count=Count("id"), cost=Sum("price"))
    slot_map = {r["slot"]: r for r in slot_rows}
    lunch = slot_map.get(Slot.LUNCH, {"count": 0, "cost": 0})
    dinner = slot_map.get(Slot.DINNER, {"count": 0, "cost": 0})
    slot_total = (lunch["count"] or 0) + (dinner["count"] or 0) or 1

    # --- streaks --------------------------------------------------------
    days_with_meals = sorted({e.date for e in entries})
    best_streak = current_streak = 1
    for prev, curr in zip(days_with_meals, days_with_meals[1:]):
        current_streak = current_streak + 1 if (curr - prev).days == 1 else 1
        best_streak = max(best_streak, current_streak)

    running_streak = 0
    cursor = today
    day_set = set(days_with_meals)
    while cursor in day_set:
        running_streak += 1
        cursor -= timedelta(days=1)

    # --- money ----------------------------------------------------------
    lifetime_cost = _decimal(entries.aggregate(c=Sum("price"))["c"])
    paid = _decimal(Payment.objects.aggregate(c=Sum("amount"))["c"])
    first_day = days_with_meals[0]
    span_days = (today - first_day).days + 1

    context = {
        "empty": False,
        "trend": trend,
        "max_cost": max_cost,
        "weekday": weekday,
        "lunch_count": lunch["count"] or 0,
        "dinner_count": dinner["count"] or 0,
        "lunch_pct": round((lunch["count"] or 0) / slot_total * 100),
        "dinner_pct": round((dinner["count"] or 0) / slot_total * 100),
        "best_streak": best_streak,
        "running_streak": running_streak,
        "lifetime_cost": lifetime_cost,
        "lifetime_meals": entries.count(),
        "paid": paid,
        "balance": paid - lifetime_cost,
        "balance_abs": abs(paid - lifetime_cost),
        "tracking_since": first_day,
        "daily_avg": lifetime_cost / span_days if span_days else Decimal("0"),
        "skip_days": span_days - len(days_with_meals),
        "busiest_month": max(trend, key=lambda t: t["cost"]) if trend else None,
    }
    return render(request, "meals/analytics.html", context)


@login_required
def settings_view(request):
    rate_form = MealRateForm()
    payment_form = PaymentForm(initial={"date": _today()})

    if request.method == "POST":
        if "save_rate" in request.POST:
            rate_form = MealRateForm(request.POST)
            if rate_form.is_valid():
                rate_form.save()
                messages.success(request, "Meal rate updated.")
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
        elif "delete_payment" in request.POST:
            Payment.objects.filter(pk=request.POST.get("delete_payment")).delete()
            messages.success(request, "Payment removed.")
            return redirect("settings")

    lifetime_cost = _decimal(MealEntry.objects.aggregate(c=Sum("price"))["c"])
    paid = _decimal(Payment.objects.aggregate(c=Sum("amount"))["c"])

    return render(
        request,
        "meals/settings.html",
        {
            "rate_form": rate_form,
            "payment_form": payment_form,
            "rates": MealRate.objects.all(),
            "payments": Payment.objects.all()[:20],
            "current_rate": MealRate.price_on(_today()),
            "lifetime_cost": lifetime_cost,
            "paid": paid,
            "balance": paid - lifetime_cost,
            "balance_abs": abs(paid - lifetime_cost),
        },
    )
