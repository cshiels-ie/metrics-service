from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("dashboard_reports", "0003_add_dashboard_collection_telemetry"),
    ]

    operations = [
        migrations.AddField(
            model_name="jobdata",
            name="launch_type",
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text="AWX launch type, used to filter sync/workflow jobs at read time",
                max_length=50,
                null=True,
            ),
        ),
    ]
