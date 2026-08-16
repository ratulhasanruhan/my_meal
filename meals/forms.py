from django import forms

from .models import MealRate, Payment, Slot


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
    """A standing rule: how many meals in a slot, from a date onward."""

    slot = forms.ChoiceField(choices=Slot.choices)
    quantity = forms.IntegerField(
        min_value=0,
        max_value=20,
        widget=forms.NumberInput(attrs={"min": "0", "max": "20"}),
    )
    effective_from = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))


class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ["date", "amount", "note"]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "amount": forms.NumberInput(attrs={"step": "0.01", "min": "0", "placeholder": "4000"}),
            "note": forms.TextInput(attrs={"placeholder": "e.g. paid via bKash"}),
        }
