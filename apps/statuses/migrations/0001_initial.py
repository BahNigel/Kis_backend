from django.db import migrations, models
import django.db.models.deletion
import uuid
import apps.statuses.models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="StatusItem",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("type", models.CharField(choices=[("image", "Image"), ("video", "Video"), ("audio", "Audio"), ("text", "Text")], max_length=16)),
                ("text", models.TextField(blank=True)),
                ("file", models.FileField(blank=True, null=True, upload_to=apps.statuses.models.status_upload_path)),
                ("duration_ms", models.PositiveIntegerField(blank=True, null=True)),
                ("expires_at", models.DateTimeField(db_index=True)),
                ("is_deleted", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(db_index=True, default=apps.statuses.models.timezone.now)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="status_items", to="accounts.user")),
            ],
            options={
                "indexes": [
                    models.Index(fields=["user", "expires_at"], name="statuses_st_user_i_4ef6f1_idx"),
                    models.Index(fields=["user", "created_at"], name="statuses_st_user_i_2703c8_idx"),
                ],
            },
        ),
    ]
