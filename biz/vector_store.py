from abc import ABC
from typing import Dict, Generator, List, Tuple, Any, Optional

import marqo


class Document:
    def __init__(self, page_content: str, metadata: Dict[str, Any]):
        self.page_content = page_content
        self.metadata = metadata


class VectorStore(ABC):
    def __init__(self, url: str, index_name: str = None):
        self.client = marqo.Client(url=url)
        self.index_name = index_name

    def search(self, query: str, top_k: int = 5, index_name: Optional[str] = None) -> list:
        """
        Perform a search on the Marqo index and return a list of documents.
        """
        search_index = index_name if index_name is not None else self.index_name
        results = self.client.index(search_index).search(
            q=query,
            limit=top_k
        )

        documents = []
        for result in results["hits"]:
            content = result.pop("text")
            documents.append(Document(page_content=content, metadata=result))
        return documents

    def index_exists(self, index_name: Optional[str] = None) -> bool:
        """
        Check if the index exists in Marqo.

        :param index_name: The name of the index to check. If not provided, uses the default index_name.
        :return: True if the index exists, False otherwise.
        """
        index_name = index_name if index_name is not None else self.index_name

        try:
            # Get the list of all indexes
            indexes_info = self.client.get_indexes()
            # Check if the provided index_name exists in the result
            return any(index["indexName"] == index_name for index in indexes_info["results"])
        except marqo.errors.MarqoError as e:
            # If an error occurs when listing indexes, consider that the index doesn't exist
            return False
    def delete_index(self, index_name: Optional[str] = None) -> None:
        """
        Delete the index from Marqo.

        :param index_name: The name of the index to delete. If not provided, uses the default index_name.
        """
        index_name = index_name if index_name is not None else self.index_name
        self.client.delete_index(index_name)
