from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("planner", "0005_plan_generated_questions_participant_ideal_date"),
    ]

    operations = [
        migrations.CreateModel(
            name="GeneratedVote",
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
                ("answers", models.JSONField(blank=True, default=dict)),
                ("submitted_at", models.DateTimeField(auto_now=True)),
                (
                    "participant",
                    models.OneToOneField(
                        on_delete=models.deletion.CASCADE,
                        related_name="generated_vote",
                        to="planner.participant",
                    ),
                ),
            ],
        ),
    ]
