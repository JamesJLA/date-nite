import uuid

from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()


class Plan(models.Model):
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_date_plans",
    )
    inviter_email = models.EmailField()
    invitee_email = models.EmailField()
    city = models.CharField(max_length=120, blank=True)
    ai_summary = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"Date plan {self.pk}: {self.inviter_email} + {self.invitee_email}"


class Participant(models.Model):
    INVITER = "inviter"
    INVITEE = "invitee"
    ROLE_CHOICES = [
        (INVITER, "You"),
        (INVITEE, "Partner"),
    ]

    plan = models.ForeignKey(
        Plan, on_delete=models.CASCADE, related_name="participants"
    )
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="date_participations",
    )
    email = models.EmailField()
    role = models.CharField(max_length=16, choices=ROLE_CHOICES)
    token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["plan", "role"], name="unique_role_per_plan"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.get_role_display()} ({self.email})"


class Vote(models.Model):
    DINNER_CHOICES = [
        ("italian", "Cozy Italian spot"),
        ("sushi", "Sushi and candlelight"),
        ("tapas", "Tapas and shared plates"),
        ("home", "Cook a candlelit dinner at home"),
    ]
    ACTIVITY_CHOICES = [
        ("movie", "Rom-com movie night"),
        ("music", "Live music"),
        ("art", "Museum or art walk"),
        ("dance", "Dancing"),
    ]
    SWEET_CHOICES = [
        ("chocolate", "Chocolate tasting"),
        ("dessert", "Dessert crawl"),
        ("cocktail", "Cocktails or mocktails"),
        ("coffee", "Late-night coffee date"),
    ]
    BUDGET_CHOICES = [
        ("cozy", "Budget-friendly and cozy"),
        ("mid", "Moderate splurge"),
        ("fancy", "Full romance splurge"),
    ]
    MOOD_CHOICES = [
        ("playful", "Playful and light"),
        ("classic", "Classic romantic"),
        ("adventurous", "Adventurous"),
        ("relaxed", "Relaxed and low-key"),
    ]
    DURATION_CHOICES = [
        ("short", "2-3 hours"),
        ("half", "Half evening"),
        ("full", "Full evening"),
    ]
    TRANSPORT_CHOICES = [
        ("walk", "Walking or short rides"),
        ("drive", "Driving is fine"),
        ("mixed", "Mix of both"),
    ]

    participant = models.OneToOneField(
        Participant, on_delete=models.CASCADE, related_name="vote"
    )
    dinner_choice = models.CharField(max_length=20, choices=DINNER_CHOICES)
    activity_choice = models.CharField(max_length=20, choices=ACTIVITY_CHOICES)
    sweet_choice = models.CharField(max_length=20, choices=SWEET_CHOICES)
    budget_choice = models.CharField(max_length=20, choices=BUDGET_CHOICES)
    mood_choice = models.CharField(
        max_length=20, choices=MOOD_CHOICES, default="classic"
    )
    duration_choice = models.CharField(
        max_length=20, choices=DURATION_CHOICES, default="half"
    )
    transport_choice = models.CharField(
        max_length=20, choices=TRANSPORT_CHOICES, default="mixed"
    )
    dietary_notes = models.CharField(max_length=200, blank=True)
    accessibility_notes = models.CharField(max_length=200, blank=True)
    submitted_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"Vote from {self.participant.email}"
