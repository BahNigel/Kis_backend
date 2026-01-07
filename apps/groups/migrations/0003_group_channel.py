from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("groups", "0002_group_advanced"),
        ("channels", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="group",
            name="channel",
            field=models.ForeignKey(
                blank=True,
                help_text="Owning channel (optional).",
                null=True,
                on_delete=models.CASCADE,
                related_name="groups",
                to="channels.channel",
            ),
        ),
    ]
