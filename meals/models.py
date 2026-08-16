from datetime import date
from decimal import Decimal

from django.core.validators import MaxValueValidator
from django.db import models


class Slot(models.TextChoices):
    LUNCH = "lunch", "Lunch"
    DINNER = "dinner", "Dinner"


WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


class MealRate(models.Model):
    """Price of a single meal, versioned so past months keep their real cost."""

    price = models.DecimalField(max_digits=8, decimal_places=2)
    effective_from = models.DateField(
        help_text="This price applies to meals on or after this date."
    )
    note = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-effective_from"]

    def __str__(self):
        return f"{self.price} from {self.effective_from}"

    @classmethod
    def price_on(cls, day: date) -> Decimal:
        """Rate in force on `day`, falling back to the earliest rate ever set."""
        rate = cls.objects.filter(effective_from__lte=day).order_by("-effective_from").first()
        if rate is None:
            rate = cls.objects.order_by("effective_from").first()
        return rate.price if rate else Decimal("0")


class MealPlan(models.Model):
    """A standing rule: how many meals you take in a slot, from a date onward.

    This is what makes the tracker hands-off — you set it once and every day
    follows it until you say otherwise. `weekday` narrows a rule to one day of
    the week (e.g. no lunch on Fridays); null means every day.
    """

    slot = models.CharField(max_length=10, choices=Slot.choices)
    weekday = models.SmallIntegerField(
        null=True,
        blank=True,
        help_text="0=Monday … 6=Sunday. Leave empty to apply to every day.",
    )
    quantity = models.PositiveSmallIntegerField(
        default=1,
        validators=[MaxValueValidator(20)],
        help_text="0 means you skip this slot by default.",
    )
    effective_from = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-effective_from", "slot"]

    def __str__(self):
        scope = "every day" if self.weekday is None else f"every {WEEKDAY_NAMES[self.weekday]}"
        return f"{self.get_slot_display()} ×{self.quantity} {scope} from {self.effective_from}"

    @property
    def scope_label(self):
        return "Every day" if self.weekday is None else f"Every {WEEKDAY_NAMES[self.weekday]}"


class MealEntry(models.Model):
    """A one-day override of the plan for a single slot.

    No row means "follow the plan". `quantity=0` means an explicit skip;
    anything above 1 is guest meals on top of your own.
    """

    date = models.DateField(db_index=True)
    slot = models.CharField(max_length=10, choices=Slot.choices)
    quantity = models.PositiveSmallIntegerField(
        default=1, validators=[MaxValueValidator(20)]
    )
    note = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "slot"]
        constraints = [
            models.UniqueConstraint(fields=["date", "slot"], name="unique_meal_per_slot")
        ]

    def __str__(self):
        return f"{self.date} {self.get_slot_display()} ×{self.quantity}"


class Payment(models.Model):
    """Money handed to the catering service. Drives the running due/advance."""

    date = models.DateField(default=date.today)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    note = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return f"{self.amount} on {self.date}"
