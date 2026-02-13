from django import forms

from .models import Vote


class CreatePlanForm(forms.Form):
    inviter_email = forms.EmailField(
        label="Your email",
        widget=forms.EmailInput(attrs={"placeholder": "you@example.com"}),
    )
    invitee_email = forms.EmailField(
        label="Partner email",
        widget=forms.EmailInput(attrs={"placeholder": "partner@example.com"}),
    )


class VoteForm(forms.ModelForm):
    class Meta:
        model = Vote
        fields = ["dinner_choice", "activity_choice", "sweet_choice", "budget_choice"]
        widgets = {
            "dinner_choice": forms.RadioSelect,
            "activity_choice": forms.RadioSelect,
            "sweet_choice": forms.RadioSelect,
            "budget_choice": forms.RadioSelect,
        }
