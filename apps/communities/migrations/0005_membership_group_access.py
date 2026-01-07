from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("communities", "0004_community_advanced"),
    ]

    operations = [
        migrations.AddField(
            model_name="communitymembership",
            name="can_access_all_groups",
            field=models.BooleanField(
                default=False,
                help_text="If true, member can access all groups in the community.",
            ),
        ),
    ]
