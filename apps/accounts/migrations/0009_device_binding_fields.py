from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0008_alter_user_country"),
    ]

    operations = [
        migrations.AddField(
            model_name="device",
            name="device_id",
            field=models.CharField(db_index=True, max_length=128, default=""),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="device",
            name="name",
            field=models.CharField(blank=True, max_length=200, null=True),
        ),
        migrations.AddField(
            model_name="device",
            name="user_agent",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="device",
            name="last_ip",
            field=models.GenericIPAddressField(blank=True, null=True),
        ),
        migrations.AddIndex(
            model_name="device",
            index=models.Index(fields=["user", "device_id"], name="accounts_de_user_id_1c2e42_idx"),
        ),
    ]
