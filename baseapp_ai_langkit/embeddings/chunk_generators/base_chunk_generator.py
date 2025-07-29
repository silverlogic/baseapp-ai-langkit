import typing
from abc import ABC, abstractmethod

from baseapp_ai_langkit.embeddings.models import EmbeddableModelMixin, GenericChunk


class BaseChunkGenerator(ABC):
    """
    Abstract base class for chunk generators.

    This class defines the interface that all chunk generators must implement.
    Chunk generators are responsible splitting content into GenericChunks
    """

    @abstractmethod
    def generate_chunks(self, embeddable: EmbeddableModelMixin) -> typing.List[GenericChunk]:
        """
        Generate chunks from the given content.

        Args:
            content: A list of texts

        Returns:
            List[GenericChunk]: A list of GenericChunks.
        """
        pass
