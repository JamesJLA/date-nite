from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("planner", "0002_plan_city"),
    ]

    operations = [
        migrations.AddField(
            model_name="vote",
            name="accessibility_notes",
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name="vote",
            name="dietary_notes",
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name="vote",
            name="duration_choice",
            field=models.CharField(
                choices=[
                    ("short", "2-3 hours"),
                    ("half", "Half evening"),
                    ("full", "Full evening"),
                ],
                default="half",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="vote",
            name="mood_choice",
            field=models.CharField(
                choices=[
                    ("playful", "Playful and light"),
                    ("classic", "Classic romantic"),
                    ("adventurous", "Adventurous"),
                    ("relaxed", "Relaxed and low-key"),
                ],
                default="classic",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="vote",
            name="transport_choice",
            field=models.CharField(
                choices=[
                    ("walk", "Walking or short rides"),
                    ("drive", "Driving is fine"),
                    ("mixed", "Mix of both"),
                ],
                default="mixed",
                max_length=20,
            ),
        ),
    ]
