import django.db.models.deletion
import django.utils.timezone
import model_utils.fields
from django.db import migrations, models

SEED_LABEL = "GPT-4o mini"
SEED_INITIALIZER_KEY = "openai"
SEED_MODEL_ID = "gpt-4o-mini"
SEED_DEFAULT_PARAMS = {"temperature": 0}


def seed_default_catalog(apps, schema_editor):
    AvailableLLMModel = apps.get_model("baseapp_ai_langkit_runners", "AvailableLLMModel")
    AvailableLLMModel.objects.get_or_create(
        initializer_key=SEED_INITIALIZER_KEY,
        model_id=SEED_MODEL_ID,
        defaults={
            "label": SEED_LABEL,
            "default_params": SEED_DEFAULT_PARAMS,
        },
    )


class Migration(migrations.Migration):
    dependencies = [
        ("baseapp_ai_langkit_runners", "0002_add_topology_layout"),
    ]

    operations = [
        migrations.CreateModel(
            name="AvailableLLMModel",
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
                ("label", models.CharField(max_length=255)),
                (
                    "initializer_key",
                    models.CharField(
                        help_text=(
                            "Dispatch key matching a registered LLMModelInitializer "
                            "(e.g. 'openai', 'anthropic', 'gemini', 'openrouter', 'generic')."
                        ),
                        max_length=64,
                    ),
                ),
                ("model_id", models.CharField(max_length=255)),
                (
                    "default_params",
                    models.JSONField(
                        blank=True,
                        default=dict,
                        help_text=(
                            "Default params merged UNDER override params at runtime "
                            "(override wins per key). Subset of the matched "
                            "initializer's allowed_params."
                        ),
                    ),
                ),
            ],
            options={
                "verbose_name": "Available LLM model",
                "verbose_name_plural": "Available LLM models",
                "ordering": ["initializer_key", "model_id"],
                "unique_together": {("initializer_key", "model_id")},
            },
        ),
        migrations.CreateModel(
            name="LLMRunnerNodeModelOverride",
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
                    "runner_node",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="model_override",
                        to="baseapp_ai_langkit_runners.llmrunnernode",
                    ),
                ),
            ],
            options={
                "verbose_name": "Model override",
                "verbose_name_plural": "Model overrides",
            },
        ),
        migrations.RunPython(
            seed_default_catalog,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
