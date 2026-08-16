from django.contrib import admin

from .models import MealEntry, MealRate, Payment


@admin.register(MealRate)
class MealRateAdmin(admin.ModelAdmin):
    list_display = ("price", "effective_from", "note")
    ordering = ("-effective_from",)


@admin.register(MealEntry)
class MealEntryAdmin(admin.ModelAdmin):
    list_display = ("date", "slot", "price", "note")
    list_filter = ("slot", "date")
    date_hierarchy = "date"


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("date", "amount", "note")
    date_hierarchy = "date"
