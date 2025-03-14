from abc import ABC
import logging
import marqo

from biz.chunker import Chunker
from biz.repo_manager import RepositoryManager


class Embedder(ABC):
    def __init__(self, repo_manager: RepositoryManager, chunker: Chunker, index_name: str, url: str,
                 model="hf/e5-base-v2"):
        self.repo_manager = repo_manager
        self.chunker = chunker
        self.client = marqo.Client(url=url)
        self.index = self.client.index(index_name)

        all_index_names = [result["indexName"] for result in self.client.get_indexes()["results"]]
        if not index_name in all_index_names:
            self.client.create_index(index_name, model=model)

    def embed_dataset(self, chunks_per_batch: int):
        if chunks_per_batch > 64:
            raise ValueError("Marqo enforces a limit of 64 chunks per batch.")

        chunk_count = 0
        batch = []

        for content, metadata in self.repo_manager.walk():
            chunks = self.chunker.chunk(content, metadata)
            chunk_count += len(chunks)
            batch.extend(chunks)
            if len(batch) > chunks_per_batch:
                for i in range(0, len(batch), chunks_per_batch):
                    sub_batch = batch[i: i + chunks_per_batch]
                    logging.info("Indexing %d chunks...", len(sub_batch))
                    self.index.add_documents(
                        documents=[chunk.metadata for chunk in sub_batch],
                        tensor_fields=["text"],
                    )

                batch = []
        if batch:
            self.index.add_documents(documents=[chunk.metadata for chunk in batch], tensor_fields=["text"])

        logging.info(f"Successfully embedded {chunk_count} chunks.")
