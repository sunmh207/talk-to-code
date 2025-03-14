from typing import Literal


class ChatChunk:
    """ A chunk of text. """
    type = Literal["chunk", "stop"]

    def __init__(self, type: Literal["chunk", "stop"], content: str = None):
        self.type = type
        self.content = content

    def is_chunk(self):
        return self.type == "chunk"

    def is_stop(self):
        return self.type == "stop"