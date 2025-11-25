import logging
from uuid import UUID

from celery import shared_task
from django.contrib.contenttypes.models import ContentType

from baseapp_ai_langkit.embeddings.model_utils import validate_content_type_for_model

logger = logging.getLogger(__name__)


@shared_task
def generate_vector_embeddings(
    content_type_app_label: str,
    content_type_model: str,
    embeddable_id: int | str | UUID,
    delay: int = 25,
):
    content_type = ContentType.objects.get(
        app_label=content_type_app_label, model=content_type_model
    )
    embeddable_type = content_type.model_class()
    validate_content_type_for_model(model_cls=embeddable_type)
    try:
        embeddable = embeddable_type.objects.get(id=embeddable_id)

        ChunkGenerator = embeddable.chunk_generator_class()
        chunk_generator = ChunkGenerator()
        chunk_generator.generate_chunks(embeddable=embeddable)
    except embeddable_type.DoesNotExist:
        # This exception might happen if the triggering model is saved during a long-running import task with transaction.atomic.
        # In this case, the saved object will only be available after the whole transaction is committed.
        if delay < 1000:
            logger.warning(
                f"Embeddable object with ID {embeddable_id} not found. Will retry in {12*delay} seconds."
            )
            # Retry after 5 minutes, then 1 hour
            generate_vector_embeddings.apply_async(
                (content_type_app_label, content_type_model, embeddable_id, 12 * delay),
                countdown=12 * delay,
            )
        else:
            logger.error(
                f"Embeddable object with ID {embeddable_id} still not found. I'm giving up."
            )
