from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm

from .constants import DEFAULT_GENERATED_QUESTIONS, DEFAULT_VOTE_QUESTION_LABELS
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

    def __init__(self, *args, question_labels=None, **kwargs):
        super().__init__(*args, **kwargs)
        labels = DEFAULT_VOTE_QUESTION_LABELS.copy()
        if isinstance(question_labels, dict):
            labels.update(question_labels)
        for name, label in labels.items():
            if name in self.fields and isinstance(label, str) and label.strip():
                self.fields[name].label = label.strip()


class GeneratedVoteForm(forms.Form):
    def __init__(self, *args, questions_schema=None, initial_answers=None, **kwargs):
        super().__init__(*args, **kwargs)
        schema = questions_schema or DEFAULT_GENERATED_QUESTIONS

        for question in schema.get("questions", []):
            field_name = question.get("id")
            if not field_name:
                continue
            label = question.get("text", field_name)
            required = bool(question.get("required", False))
            question_type = question.get("type", "single")

            if question_type == "text":
                self.fields[field_name] = forms.CharField(
                    label=label,
                    required=required,
                    widget=forms.TextInput(
                        attrs={"placeholder": question.get("placeholder", "")}
                    ),
                )
            else:
                choices = []
                for option in question.get("options", []):
                    value = option.get("value")
                    option_label = option.get("label", value)
                    if value:
                        choices.append((value, option_label))
                self.fields[field_name] = forms.ChoiceField(
                    label=label,
                    required=required,
                    choices=choices,
                    widget=forms.RadioSelect,
                )

        if initial_answers:
            for key, value in initial_answers.items():
                if key in self.fields:
                    self.initial[key] = value

    def cleaned_answers(self):
        cleaned = {}
        for name in self.fields:
            value = self.cleaned_data.get(name)
            if isinstance(value, str):
                value = value.strip()
            cleaned[name] = value
        return cleaned


class IdealDateForm(forms.Form):
    ideal_date = forms.CharField(
        label="Describe your ideal date night",
        widget=forms.Textarea(
            attrs={
                "rows": 5,
                "placeholder": "Describe your perfect night together: food, atmosphere, activities, pace, and anything to avoid.",
            }
        ),
    )


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
