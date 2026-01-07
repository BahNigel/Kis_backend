from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("statuses", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="statusitem",
            name="style",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
