import json

from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand

from baseapp_ai_langkit.embeddings.embedding_utils import find_similar_chunks
from baseapp_ai_langkit.embeddings.model_utils import available_content_types_query
from baseapp_ai_langkit.embeddings.models import GenericChunk


class Command(BaseCommand):
    help = "Embeddings Management"

    def __init__(self, *args, **kwargs):
        super(Command, self).__init__(*args, **kwargs)

    def add_arguments(self, parser):
        parser.add_argument("--regenerate_embeddings", action="store_true", default=False)
        parser.add_argument("--find_similar", action="store_true", default=False)

    def handle(self, *args, **options):
        try:
            self._handle(*args, **options)
        except BaseException as e:
            self.stdout.write("\r\n")
            if isinstance(e, KeyboardInterrupt):
                return
            raise e

    def _handle(self, *args, **options):
        if options.get("regenerate_embeddings"):
            content_type_app_label: str | None = None
            content_type_model: str | None = None
            embeddable_id: str | None = None

            content_type_app_label = input("Enter app_label: ")
            content_type_model = input("Enter model: ")
            embeddable_id = input("Enter id: ")

            self.regenerate_embeddings(
                content_type_app_label=content_type_app_label,
                content_type_model=content_type_model,
                embeddable_id=embeddable_id,
            )
        if options.get("find_similar"):
            query: str | None = None
            query = input("Enter query: ")

            cosine_distance_filter: float | None = None
            while cosine_distance_filter is None:
                try:
                    cosine_distance_filter = float(
                        input("Enter Cosine Distance Filter (0.0 - 1.0): ")
                    )
                    if not 0.0 <= cosine_distance_filter <= 1.0:
                        self.stdout.write(self.style.ERROR("Must be between 0.0 and 1.0"))
                        cosine_distance_filter = None
                except ValueError:
                    self.stdout.write(self.style.ERROR("Please enter a valid number"))

            self.find_similar(query=query, cosine_distance_filter=cosine_distance_filter)

    def regenerate_embeddings(
        self, content_type_app_label: str, content_type_model: str, embeddable_id: str
    ):
        from ...tasks import generate_vector_embeddings

        generate_vector_embeddings(
            content_type_app_label=content_type_app_label,
            content_type_model=content_type_model,
            embeddable_id=embeddable_id,
        )

    def find_similar(self, query: str, cosine_distance_filter: float):
        similar_chunks = find_similar_chunks(
            query=query, cosine_distance_filter=cosine_distance_filter
        )
        self.stdout.write(
            self.style.NOTICE(f"Similar {GenericChunk._meta.verbose_name_plural.title()}".upper())
        )
        for chunk in similar_chunks[:10]:
            self.stdout.write(
                self.style.SUCCESS(
                    json.dumps(
                        dict(
                            chunk_id=chunk.id,
                            object=str(chunk.content_object),
                            cosine_distance=chunk.cosine_distance,
                        ),
                        indent=4,
                    )
                )
            )
        for content_type in ContentType.objects.all().filter(available_content_types_query()):
            self.stdout.write(
                self.style.NOTICE(
                    f"Similar {content_type.model_class()._meta.verbose_name_plural.title()}".upper()
                )
            )
            _similar_chunks = (
                similar_chunks.filter(content_type=content_type)
                .distinct("cosine_distance", "content_type", "object_id")
                .order_by("cosine_distance", "content_type", "object_id")
            )
            for chunk in _similar_chunks:
                self.stdout.write(
                    self.style.SUCCESS(
                        json.dumps(
                            dict(
                                chunk_id=chunk.id,
                                object=str(chunk.content_object),
                                cosine_distance=chunk.cosine_distance,
                            ),
                            indent=4,
                        )
                    )
                )
