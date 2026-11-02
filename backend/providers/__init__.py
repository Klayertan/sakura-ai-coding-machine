from .base import ChatChunk, InferenceProvider, ModelInfo, ProviderError, Relay
from .ollama import OllamaProvider
from .openai_compat import OpenAICompatProvider

__all__ = ['ChatChunk', 'InferenceProvider', 'ModelInfo', 'ProviderError', 'Relay',
           'OllamaProvider', 'OpenAICompatProvider', 'build_provider']


def build_provider(settings) -> InferenceProvider:
    if settings.provider == 'ollama':
        return OllamaProvider(settings.ollama_url, settings.provider_read_timeout_seconds)
    if settings.provider == 'openai':
        return OpenAICompatProvider(settings.inference_url, settings.provider_read_timeout_seconds)
    raise ValueError(f'Unknown INFERENCE_PROVIDER: {settings.provider!r}')
