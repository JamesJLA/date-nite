from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm

from .models import Vote

User = get_user_model()


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


class SignUpForm(UserCreationForm):
    email = forms.EmailField(
        label="Email",
        widget=forms.EmailInput(attrs={"placeholder": "you@example.com"}),
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("email", "password1", "password2")

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account already exists for this email.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        email = self.cleaned_data["email"]
        user.email = email
        user.username = email
        if commit:
            user.save()
        return user
