import django.db.models.deletion
import django.utils.timezone
import model_utils.fields
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("baseapp_ai_langkit_runners", "0003_add_model_catalog_and_override"),
    ]

    operations = [
        migrations.CreateModel(
            name="LLMRunnerDefaultModelOverride",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "created",
                    model_utils.fields.AutoCreatedField(
                        default=django.utils.timezone.now,
                        editable=False,
                        verbose_name="created",
                    ),
                ),
                (
                    "modified",
                    model_utils.fields.AutoLastModifiedField(
                        default=django.utils.timezone.now,
                        editable=False,
                        verbose_name="modified",
                    ),
                ),
                ("initializer_key", models.CharField(max_length=64)),
                ("model_id", models.CharField(max_length=255)),
                ("params", models.JSONField(blank=True, default=dict)),
                (
                    "runner",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="default_model_override",
                        to="baseapp_ai_langkit_runners.llmrunner",
                    ),
                ),
            ],
            options={
                "verbose_name": "Runner default model override",
                "verbose_name_plural": "Runner default model overrides",
            },
        ),
    ]
