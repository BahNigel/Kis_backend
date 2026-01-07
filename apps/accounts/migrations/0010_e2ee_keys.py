import uuid
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0009_device_binding_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="E2EDeviceKey",
            fields=[
                ("id", models.UUIDField(primary_key=True, serialize=False, editable=False, default=uuid.uuid4)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_deleted", models.BooleanField(default=False)),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
                ("identity_key", models.TextField()),
                ("signed_prekey_id", models.IntegerField()),
                ("signed_prekey", models.TextField()),
                ("signed_prekey_signature", models.TextField()),
                ("registration_id", models.IntegerField(blank=True, null=True)),
                ("device", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="e2ee_keys", to="accounts.device")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="e2ee_devices", to="accounts.user")),
            ],
            options={
                "indexes": [
                    models.Index(fields=["user", "device"], name="accounts_e2_user_id_39c74a_idx"),
                    models.Index(fields=["user", "device", "signed_prekey_id"], name="accounts_e2_user_id_6b4b7b_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="E2EPreKey",
            fields=[
                ("id", models.UUIDField(primary_key=True, serialize=False, editable=False, default=uuid.uuid4)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_deleted", models.BooleanField(default=False)),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
                ("prekey_id", models.IntegerField()),
                ("prekey", models.TextField()),
                ("consumed_at", models.DateTimeField(blank=True, null=True)),
                ("device", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="e2ee_prekeys", to="accounts.device")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="e2ee_prekeys", to="accounts.user")),
            ],
            options={
                "indexes": [
                    models.Index(fields=["user", "device", "prekey_id"], name="accounts_e2_user_id_2d3b11_idx"),
                    models.Index(fields=["user", "device", "consumed_at"], name="accounts_e2_user_id_0f6d54_idx"),
                ],
            },
        ),
    ]
