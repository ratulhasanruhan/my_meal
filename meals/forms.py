from django import forms

from .models import MealRate, Payment


class MealRateForm(forms.ModelForm):
    class Meta:
        model = MealRate
        fields = ["price", "effective_from", "note"]
        widgets = {
            "price": forms.NumberInput(attrs={"step": "0.01", "min": "0", "placeholder": "70.00"}),
            "effective_from": forms.DateInput(attrs={"type": "date"}),
            "note": forms.TextInput(attrs={"placeholder": "e.g. rate hike from July"}),
        }


class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ["date", "amount", "note"]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "amount": forms.NumberInput(attrs={"step": "0.01", "min": "0", "placeholder": "2000"}),
            "note": forms.TextInput(attrs={"placeholder": "e.g. paid via bKash"}),
        }
