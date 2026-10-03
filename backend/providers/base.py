"""Provider-neutral inference interface.

The gateway and the Mac client only ever see these types, so swapping Ollama
for vLLM means adding one subclass and nothing else.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import AsyncGenerator, Dict, List, Optional


class ProviderError(Exception):
    """The inference backend failed or rejected the request."""

    def __init__(self, detail: str, status_code: int = 502):
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


@dataclass
class ChatChunk:
    """One piece of a streamed reply. The last chunk has done=True and usage."""

    content: str = ''
    thinking: str = ''
    done: bool = False
    model: str = ''
    usage: Dict[str, int] = field(default_factory=dict)


@dataclass
class ModelInfo:
    name: str
    size_bytes: Optional[int] = None


class InferenceProvider(ABC):
    name = 'base'

    @abstractmethod
    def chat_stream(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> AsyncGenerator[ChatChunk, None]:
        """Yield chunks as they are generated. Raise ProviderError on failure."""

    @abstractmethod
    async def list_models(self) -> List[ModelInfo]:
        ...

    @abstractmethod
    async def health(self) -> bool:
        ...

    async def aclose(self) -> None:
        pass
