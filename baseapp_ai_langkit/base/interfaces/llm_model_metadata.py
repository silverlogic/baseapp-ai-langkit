from typing import Any, Dict

from pydantic import BaseModel, ConfigDict, Field


class LLMModelMetadata(BaseModel):
    """Declarative description of the LLM model a Runner subclass uses by default.

    Read by `runners.topology.extractor` to populate the topology payload's per-node
    `model.{initializer_key, model_id, params}` fields without instantiating an LLM
    (the F01-S01 "no production side effects" guarantee).

    Runner subclasses set this as a class attribute:

        from baseapp_ai_langkit.base.interfaces.llm_model_metadata import LLMModelMetadata

        class MyRunner(BaseRunnerInterface):
            default_model_metadata = LLMModelMetadata(
                initializer_key="openai",
                model_id="gpt-4o-mini",
                params={"temperature": 0},
            )

    A registered runner without `default_model_metadata` triggers a Django system check
    warning at startup (see `runners.checks`).
    """

    initializer_key: str
    model_id: str
    params: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True)
