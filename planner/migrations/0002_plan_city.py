from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("planner", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="plan",
            name="city",
            field=models.CharField(blank=True, max_length=120),
        ),
    ]
