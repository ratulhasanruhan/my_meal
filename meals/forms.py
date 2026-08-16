from django import forms

from .models import MealPlan, MealRate, Payment, Slot, WEEKDAY_NAMES


class MealRateForm(forms.ModelForm):
    class Meta:
        model = MealRate
        fields = ["price", "effective_from", "note"]
        widgets = {
            "price": forms.NumberInput(attrs={"step": "0.01", "min": "0", "placeholder": "70.00"}),
            "effective_from": forms.DateInput(attrs={"type": "date"}),
            "note": forms.TextInput(attrs={"placeholder": "e.g. rate hike from July"}),
        }


class MealPlanForm(forms.Form):
    """A standing rule. `weekday` empty means it applies every day."""

    WEEKDAY_CHOICES = [("", "Every day")] + [(i, name) for i, name in enumerate(WEEKDAY_NAMES)]

    slot = forms.ChoiceField(choices=Slot.choices)
    weekday = forms.ChoiceField(choices=WEEKDAY_CHOICES, required=False)
    quantity = forms.IntegerField(
        min_value=0,
        max_value=20,
        help_text="0 means you skip this slot by default.",
        widget=forms.NumberInput(attrs={"min": "0", "max": "20"}),
    )
    effective_from = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))

    def clean_weekday(self):
        value = self.cleaned_data.get("weekday")
        return int(value) if value not in (None, "") else None


class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ["date", "amount", "note"]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "amount": forms.NumberInput(attrs={"step": "0.01", "min": "0", "placeholder": "4000"}),
            "note": forms.TextInput(attrs={"placeholder": "e.g. paid via bKash"}),
        }
