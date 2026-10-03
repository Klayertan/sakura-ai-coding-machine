from .base import ChatChunk, InferenceProvider, ModelInfo, ProviderError
from .ollama import OllamaProvider

__all__ = ['ChatChunk', 'InferenceProvider', 'ModelInfo', 'ProviderError',
           'OllamaProvider', 'build_provider']


def build_provider(settings) -> InferenceProvider:
    if settings.provider == 'ollama':
        return OllamaProvider(settings.ollama_url, settings.provider_read_timeout_seconds)
    # A VLLMProvider (OpenAI-compatible /v1/chat/completions) plugs in here.
    raise ValueError(f'Unknown INFERENCE_PROVIDER: {settings.provider!r}')
