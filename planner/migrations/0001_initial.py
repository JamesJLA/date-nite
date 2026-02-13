import uuid

from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Plan",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("inviter_email", models.EmailField(max_length=254)),
                ("invitee_email", models.EmailField(max_length=254)),
                ("ai_summary", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name="Participant",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("email", models.EmailField(max_length=254)),
                (
                    "role",
                    models.CharField(
                        choices=[("inviter", "You"), ("invitee", "Partner")],
                        max_length=16,
                    ),
                ),
                (
                    "token",
                    models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
                ),
                (
                    "plan",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="participants",
                        to="planner.plan",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="Vote",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "dinner_choice",
                    models.CharField(
                        choices=[
                            ("italian", "Cozy Italian spot"),
                            ("sushi", "Sushi and candlelight"),
                            ("tapas", "Tapas and shared plates"),
                            ("home", "Cook a candlelit dinner at home"),
                        ],
                        max_length=20,
                    ),
                ),
                (
                    "activity_choice",
                    models.CharField(
                        choices=[
                            ("movie", "Rom-com movie night"),
                            ("music", "Live music"),
                            ("art", "Museum or art walk"),
                            ("dance", "Dancing"),
                        ],
                        max_length=20,
                    ),
                ),
                (
                    "sweet_choice",
                    models.CharField(
                        choices=[
                            ("chocolate", "Chocolate tasting"),
                            ("dessert", "Dessert crawl"),
                            ("cocktail", "Cocktails or mocktails"),
                            ("coffee", "Late-night coffee date"),
                        ],
                        max_length=20,
                    ),
                ),
                (
                    "budget_choice",
                    models.CharField(
                        choices=[
                            ("cozy", "Budget-friendly and cozy"),
                            ("mid", "Moderate splurge"),
                            ("fancy", "Full romance splurge"),
                        ],
                        max_length=20,
                    ),
                ),
                ("submitted_at", models.DateTimeField(auto_now=True)),
                (
                    "participant",
                    models.OneToOneField(
                        on_delete=models.deletion.CASCADE,
                        related_name="vote",
                        to="planner.participant",
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="participant",
            constraint=models.UniqueConstraint(
                fields=("plan", "role"), name="unique_role_per_plan"
            ),
        ),
    ]
