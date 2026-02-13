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
    city = forms.CharField(
        required=False,
        label="City (optional)",
        widget=forms.TextInput(attrs={"placeholder": "Chicago, IL"}),
    )


class VoteForm(forms.ModelForm):
    class Meta:
        model = Vote
        fields = [
            "dinner_choice",
            "activity_choice",
            "sweet_choice",
            "budget_choice",
            "mood_choice",
            "duration_choice",
            "transport_choice",
            "dietary_notes",
            "accessibility_notes",
        ]
        widgets = {
            "dinner_choice": forms.RadioSelect,
            "activity_choice": forms.RadioSelect,
            "sweet_choice": forms.RadioSelect,
            "budget_choice": forms.RadioSelect,
            "mood_choice": forms.RadioSelect,
            "duration_choice": forms.RadioSelect,
            "transport_choice": forms.RadioSelect,
            "dietary_notes": forms.TextInput(
                attrs={"placeholder": "Any dietary needs or foods to avoid?"}
            ),
            "accessibility_notes": forms.TextInput(
                attrs={"placeholder": "Mobility, noise, or accessibility preferences"}
            ),
        }


class RefinePlanForm(forms.Form):
    feedback = forms.CharField(
        label="What would you like to change?",
        widget=forms.Textarea(
            attrs={
                "rows": 4,
                "placeholder": "Example: Less travel, quieter venue, and no seafood",
            }
        ),
    )
