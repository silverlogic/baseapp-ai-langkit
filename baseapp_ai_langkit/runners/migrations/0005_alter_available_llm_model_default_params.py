from django.db import migrations, models

import baseapp_ai_langkit.runners.models


class Migration(migrations.Migration):
    dependencies = [
        ("baseapp_ai_langkit_runners", "0004_add_runner_default_model_override"),
    ]

    operations = [
        migrations.AlterField(
            model_name="availablellmmodel",
            name="default_params",
            field=models.JSONField(
                blank=True,
                default=baseapp_ai_langkit.runners.models._default_available_llm_model_params,
                help_text=(
                    "Default params merged UNDER override params at runtime "
                    "(override wins per key). The keys present here are also the only "
                    "params the model edit modal will offer to admins for tuning; "
                    "remove a key to hide it, add one (with a sensible default) to "
                    "expose it. The value's type drives the modal's input control type "
                    "(number / boolean / text)."
                ),
            ),
        ),
    ]
