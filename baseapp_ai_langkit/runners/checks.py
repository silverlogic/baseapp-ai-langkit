from django.core.checks import Tags, Warning, register


@register(Tags.compatibility)
def check_runners_have_default_model_metadata(app_configs, **kwargs):
    """Warn for any registered Runner subclass without `default_model_metadata`.

    The runner's topology payload emits null defaults when this classattr is missing,
    so admins see a non-populated model picker in the F02 edit modal. The check ships
    as a `Warning` (not an `Error`) so consumer projects on upgrade aren't blocked.

    See `e01-f02-s02-model-override-and-runtime` for context.
    """
    from baseapp_ai_langkit.runners.registry import RunnerRegistry

    warnings = []
    for runner_cls in RunnerRegistry.get_all():
        if getattr(runner_cls, "default_model_metadata", None) is None:
            warnings.append(
                Warning(
                    (
                        f"Runner {runner_cls.__module__}.{runner_cls.__name__} does not "
                        "declare `default_model_metadata`. Topology payload will emit "
                        "null defaults for this runner's nodes."
                    ),
                    hint=(
                        "Add a `default_model_metadata: LLMModelMetadata` class "
                        "attribute matching what `initialize_llm()` returns. See "
                        "`baseapp_ai_langkit.base.interfaces.llm_model_metadata`."
                    ),
                    obj=runner_cls,
                    id="baseapp_ai_langkit_runners.W001",
                )
            )
    return warnings
