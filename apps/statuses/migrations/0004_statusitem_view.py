from django.db import migrations, models
import django.db.models.deletion
import uuid
from django.utils import timezone


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0001_initial"),
        ("statuses", "0003_merge_20260105_2000"),
    ]

    operations = [
        migrations.CreateModel(
            name="StatusItemView",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("viewed_at", models.DateTimeField(db_index=True, default=timezone.now)),
                ("status", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="views", to="statuses.statusitem")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="status_views", to="accounts.user")),
            ],
        ),
        migrations.AddConstraint(
            model_name="statusitemview",
            constraint=models.UniqueConstraint(fields=("status", "user"), name="status_item_unique_view"),
        ),
        migrations.AddIndex(
            model_name="statusitemview",
            index=models.Index(fields=["status", "user"], name="statuses_st_status__8c4b0c_idx"),
        ),
        migrations.AddIndex(
            model_name="statusitemview",
            index=models.Index(fields=["user", "viewed_at"], name="statuses_st_user_i_8fd571_idx"),
        ),
    ]
