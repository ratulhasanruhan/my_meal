"""Turning the plan + overrides into concrete days, meals and money.

The rule everywhere: an override for a date wins; otherwise the newest
applicable plan rule wins (a weekday rule beats an every-day rule set on the
same date); before your first plan starts, nothing is counted.
"""

import calendar
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Sum

from .models import MealEntry, MealPlan, MealRate, Payment, Slot

ZERO = Decimal("0")


def month_bounds(year: int, month: int):
    return date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])


def shift_month(year: int, month: int, delta: int):
    index = (year * 12 + (month - 1)) + delta
    return index // 12, index % 12 + 1


def daterange(start: date, end: date):
    day = start
    while day <= end:
        yield day
        day += timedelta(days=1)


class Resolver:
    """Resolves meal quantities for a date range in a fixed number of queries."""

    def __init__(self, start: date, end: date):
        self.start = start
        self.end = end

        plans = list(MealPlan.objects.filter(effective_from__lte=end))
        # Newest rule wins; on the same date a weekday rule beats an every-day one.
        plans.sort(key=lambda p: (p.effective_from, p.weekday is not None), reverse=True)
        self._plans = defaultdict(list)
        for plan in plans:
            self._plans[plan.slot].append(plan)

        self.tracking_start = min((p.effective_from for p in plans), default=None)

        self._overrides = {
            (e.date, e.slot): e.quantity
            for e in MealEntry.objects.filter(date__range=(start, end))
        }

        rates = list(MealRate.objects.order_by("effective_from"))
        self._rates = rates
        self._fallback_rate = rates[0].price if rates else ZERO

    def price_on(self, day: date) -> Decimal:
        price = None
        for rate in self._rates:
            if rate.effective_from <= day:
                price = rate.price
            else:
                break
        return price if price is not None else self._fallback_rate

    def planned_quantity(self, day: date, slot: str) -> int:
        """What the standing plan says for this slot, ignoring any override."""
        if self.tracking_start is None or day < self.tracking_start:
            return 0
        for plan in self._plans.get(slot, ()):
            if plan.effective_from <= day and plan.weekday in (None, day.weekday()):
                return plan.quantity
        return 0

    def quantity(self, day: date, slot: str) -> int:
        override = self._overrides.get((day, slot))
        if override is not None:
            return override
        return self.planned_quantity(day, slot)

    def is_override(self, day: date, slot: str) -> bool:
        return (day, slot) in self._overrides

    def day_cost(self, day: date) -> Decimal:
        price = self.price_on(day)
        return price * sum(self.quantity(day, slot) for slot in Slot.values)


def month_summary(year: int, month: int, today: date) -> dict:
    """Everything the dashboard and the monthly report need for one month."""
    first, last = month_bounds(year, month)
    resolver = Resolver(first, last)

    counted_end = min(last, today)

    totals = {Slot.LUNCH: 0, Slot.DINNER: 0}
    guest_meals = 0
    cost = ZERO
    guest_cost = ZERO
    active_days = 0
    skipped_days = 0
    days = []

    for day in daterange(first, last):
        price = resolver.price_on(day)
        qty = {slot: resolver.quantity(day, slot) for slot in Slot.values}
        day_total = sum(qty.values())
        # Guest meals are everything beyond your own single meal in a slot.
        day_guests = sum(max(0, q - 1) for q in qty.values())
        day_cost = price * day_total

        counted = day <= counted_end
        if counted:
            for slot in Slot.values:
                totals[slot] += qty[slot]
            guest_meals += day_guests
            cost += day_cost
            guest_cost += price * day_guests
            if day_total:
                active_days += 1
            elif resolver.tracking_start and day >= resolver.tracking_start:
                skipped_days += 1

        days.append(
            {
                "date": day,
                "day": day.day,
                "lunch": qty[Slot.LUNCH],
                "dinner": qty[Slot.DINNER],
                "meals": day_total,
                "guests": day_guests,
                "cost": day_cost,
                "counted": counted,
                "is_future": day > today,
                "is_today": day == today,
                "overridden": any(resolver.is_override(day, s) for s in Slot.values),
            }
        )

    # Projection: what is already counted, plus what the plan says is still coming.
    projected = cost
    if last > counted_end:
        for day in daterange(counted_end + timedelta(days=1), last):
            projected += resolver.price_on(day) * sum(
                resolver.quantity(day, slot) for slot in Slot.values
            )

    total_meals = totals[Slot.LUNCH] + totals[Slot.DINNER]
    return {
        "first": first,
        "last": last,
        "resolver": resolver,
        "days": days,
        "lunch_count": totals[Slot.LUNCH],
        "dinner_count": totals[Slot.DINNER],
        "total_meals": total_meals,
        "guest_meals": guest_meals,
        "own_meals": total_meals - guest_meals,
        "cost": cost,
        "guest_cost": guest_cost,
        "own_cost": cost - guest_cost,
        "active_days": active_days,
        "skipped_days": skipped_days,
        "projected": projected,
        "avg_per_active_day": (cost / active_days) if active_days else ZERO,
    }


def cost_between(start: date, end: date) -> Decimal:
    """Total meal cost over a closed date range."""
    if start > end:
        return ZERO
    resolver = Resolver(start, end)
    return sum((resolver.day_cost(day) for day in daterange(start, end)), ZERO)


def tracking_start() -> date | None:
    return MealPlan.objects.order_by("effective_from").values_list(
        "effective_from", flat=True
    ).first()


def opening_balance(first_of_month: date) -> Decimal:
    """What you owed (positive) or had in credit (negative) entering the month.

    This is the due/advance that rolls into the current month's bill.
    """
    start = tracking_start()
    if start is None or start >= first_of_month:
        prior_cost = ZERO
    else:
        prior_cost = cost_between(start, first_of_month - timedelta(days=1))

    prior_paid = Payment.objects.filter(date__lt=first_of_month).aggregate(
        total=Sum("amount")
    )["total"] or ZERO
    return prior_cost - prior_paid


def month_ledger(year: int, month: int, today: date) -> dict:
    """Opening due/advance, this month's charges and payments, closing balance."""
    first, last = month_bounds(year, month)
    summary = month_summary(year, month, today)

    opening = opening_balance(first)
    paid = Payment.objects.filter(date__range=(first, last)).aggregate(
        total=Sum("amount")
    )["total"] or ZERO

    closing = opening + summary["cost"] - paid
    return {
        "opening": opening,
        "charges": summary["cost"],
        "paid": paid,
        "closing": closing,
        "payments": list(Payment.objects.filter(date__range=(first, last)).order_by("date")),
        "projected_closing": opening + summary["projected"] - paid,
    }


def monthly_trend(months: int, today: date) -> list[dict]:
    """Cost and meal count per month for the last `months` months.

    Uses a single Resolver over the whole span rather than one per month.
    """
    start_year, start_month = shift_month(today.year, today.month, -(months - 1))
    first = date(start_year, start_month, 1)
    _, last = month_bounds(today.year, today.month)
    resolver = Resolver(first, last)

    buckets = {}
    y, m = start_year, start_month
    for _ in range(months):
        buckets[(y, m)] = {
            "year": y,
            "month": m,
            "label": calendar.month_abbr[m],
            "full_label": f"{calendar.month_abbr[m]} {y}",
            "cost": ZERO,
            "meals": 0,
        }
        y, m = shift_month(y, m, 1)

    for day in daterange(first, min(last, today)):
        bucket = buckets[(day.year, day.month)]
        price = resolver.price_on(day)
        for slot in Slot.values:
            qty = resolver.quantity(day, slot)
            bucket["meals"] += qty
            bucket["cost"] += price * qty

    return list(buckets.values())


def lifetime_stats(today: date) -> dict:
    """All-time totals, streaks and gaps since tracking began."""
    start = tracking_start()
    if start is None or start > today:
        return {"empty": True}

    resolver = Resolver(start, today)

    total_meals = guest_meals = 0
    cost = guest_cost = ZERO
    active_days: list[date] = []
    skipped_days = 0
    per_slot = {Slot.LUNCH: 0, Slot.DINNER: 0}

    for day in daterange(start, today):
        price = resolver.price_on(day)
        qty = {slot: resolver.quantity(day, slot) for slot in Slot.values}
        day_total = sum(qty.values())
        day_guests = sum(max(0, q - 1) for q in qty.values())

        for slot in Slot.values:
            per_slot[slot] += qty[slot]
        total_meals += day_total
        guest_meals += day_guests
        cost += price * day_total
        guest_cost += price * day_guests
        if day_total:
            active_days.append(day)
        else:
            skipped_days += 1

    best_streak = current = 0
    longest_gap = gap = 0
    active_set = set(active_days)
    for day in daterange(start, today):
        if day in active_set:
            current += 1
            best_streak = max(best_streak, current)
            gap = 0
        else:
            current = 0
            gap += 1
            longest_gap = max(longest_gap, gap)

    running = 0
    cursor = today
    while cursor >= start and cursor in active_set:
        running += 1
        cursor -= timedelta(days=1)

    span_days = (today - start).days + 1
    paid = Payment.objects.aggregate(total=Sum("amount"))["total"] or ZERO

    return {
        "empty": False,
        "tracking_since": start,
        "total_meals": total_meals,
        "guest_meals": guest_meals,
        "own_meals": total_meals - guest_meals,
        "lunch_count": per_slot[Slot.LUNCH],
        "dinner_count": per_slot[Slot.DINNER],
        "lunch_pct": round(per_slot[Slot.LUNCH] / total_meals * 100) if total_meals else 0,
        "dinner_pct": round(per_slot[Slot.DINNER] / total_meals * 100) if total_meals else 0,
        "cost": cost,
        "guest_cost": guest_cost,
        "paid": paid,
        "balance": cost - paid,
        "active_days": len(active_days),
        "skipped_days": skipped_days,
        "best_streak": best_streak,
        "running_streak": running,
        "longest_gap": longest_gap,
        "daily_avg": cost / span_days if span_days else ZERO,
    }


def weekday_breakdown(today: date) -> list[dict]:
    """Meals taken per weekday, Sunday first."""
    start = tracking_start()
    order = [6, 0, 1, 2, 3, 4, 5]  # Sun, Mon … Sat
    counts = {w: 0 for w in range(7)}
    if start and start <= today:
        resolver = Resolver(start, today)
        for day in daterange(start, today):
            counts[day.weekday()] += sum(
                resolver.quantity(day, slot) for slot in Slot.values
            )
    peak = max(counts.values()) or 1
    return [
        {
            "label": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][w],
            "count": counts[w],
            "pct": round(counts[w] / peak * 100),
        }
        for w in order
    ]


def set_plan_from(day: date, slot: str, quantity: int, weekday: int | None) -> MealPlan:
    """Make `quantity` the standing rule for `slot` from `day` onward.

    Replaces any rule with the same scope and start date, and clears per-day
    overrides after `day` so the new rule actually takes effect.
    """
    MealPlan.objects.filter(slot=slot, weekday=weekday, effective_from=day).delete()
    plan = MealPlan.objects.create(
        slot=slot, weekday=weekday, quantity=quantity, effective_from=day
    )

    stale = MealEntry.objects.filter(date__gte=day, slot=slot)
    if weekday is not None:
        # Django's week_day is 1=Sunday..7=Saturday; Python's is 0=Monday..6=Sunday.
        stale = stale.filter(date__week_day=(weekday + 1) % 7 + 1)
    stale.delete()
    return plan
