from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("channels", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="channel",
            name="invite_messages",
            field=models.JSONField(blank=True, default=list, help_text="Optional invite-only messages shown before subscription."),
        ),
    ]
