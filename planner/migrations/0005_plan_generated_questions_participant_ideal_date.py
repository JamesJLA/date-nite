from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("planner", "0004_merge_0003_account_links_0003_vote_details"),
    ]

    operations = [
        migrations.AddField(
            model_name="participant",
            name="ideal_date",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="plan",
            name="generated_questions",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
