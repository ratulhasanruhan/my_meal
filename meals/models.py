from datetime import date
from decimal import Decimal

from django.db import models


class Slot(models.TextChoices):
    LUNCH = "lunch", "Lunch"
    DINNER = "dinner", "Dinner"


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


class MealEntry(models.Model):
    """One taken meal. A row exists only when the meal was actually eaten."""

    date = models.DateField(db_index=True)
    slot = models.CharField(max_length=10, choices=Slot.choices)
    price = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        help_text="Price snapshotted when the meal was logged.",
    )
    note = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "slot"]
        constraints = [
            models.UniqueConstraint(fields=["date", "slot"], name="unique_meal_per_slot")
        ]

    def __str__(self):
        return f"{self.date} {self.get_slot_display()}"

    def save(self, *args, **kwargs):
        if self.price is None:
            self.price = MealRate.price_on(self.date)
        super().save(*args, **kwargs)


class Payment(models.Model):
    """Money handed to the catering service, so dues can be tracked against cost."""

    date = models.DateField(default=date.today)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    note = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return f"{self.amount} on {self.date}"
