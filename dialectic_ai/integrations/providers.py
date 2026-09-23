"""Explicit provider routing shared by CLI and API; unknown names never simulate success."""
import os

from dialectic_ai.core.llm import FallbackLLM, MockLLM
from dialectic_ai.integrations.gemini.llm import GeminiLLM
from dialectic_ai.integrations.gigachat.llm import GigaChatLLM
from dialectic_ai.integrations.openai.llm import OpenAILLM

# name -> env var that must be set for that provider to be usable.
PROVIDER_KEYS = [
    ('gigachat', 'GIGACHAT_AUTH_KEY'), ('gemini', 'GEMINI_API_KEY'),
    ('openai', 'OPENAI_API_KEY'), ('groq', 'GROQ_API_KEY'),
    ('cerebras', 'CEREBRAS_API_KEY'), ('openrouter', 'OPENROUTER_API_KEY'),
]


def available_providers() -> list[str]:
    """Real (non-mock) providers whose required env var is actually set."""
    return [name for name, key in PROVIDER_KEYS if os.getenv(key)]


def _tagged(llm, provider: str):
    llm.provider_name = provider
    return llm


def build_llm(provider: str):
    provider = provider.strip().lower()
    if provider == 'mock':
        return _tagged(MockLLM(), 'mock')
    if provider in ('auto', 'fallback'):
        available = available_providers()
        if not available:
            raise ValueError('No configured providers for fallback; choose mock explicitly for simulation')
        return _tagged(FallbackLLM([build_llm(name) for name in available]), 'fallback')
    if provider == 'gigachat':
        return _tagged(GigaChatLLM(model=os.getenv('GIGACHAT_MODEL', 'GigaChat')), 'gigachat')
    if provider == 'gemini':
        return _tagged(GeminiLLM(), 'gemini')
    if provider == 'openai':
        return _tagged(OpenAILLM(api_key=os.getenv('OPENAI_API_KEY', ''),
                         base_url=os.getenv('OPENAI_BASE_URL', 'https://api.openai.com/v1'),
                         model=os.getenv('OPENAI_MODEL', 'gpt-4o-mini')), 'openai')
    defaults = {
        'groq': ('https://api.groq.com/openai/v1', 'llama-3.3-70b-versatile'),
        'cerebras': ('https://api.cerebras.ai/v1', 'gpt-oss-120b'),
        'openrouter': ('https://openrouter.ai/api/v1', 'meta-llama/llama-3.1-8b-instruct'),
    }
    if provider in defaults:
        url, _ = defaults[provider]
        prefix = provider.upper()
        key = os.getenv(prefix + '_API_KEY')
        if not key:
            raise ValueError(prefix + '_API_KEY is not configured')
        model = os.getenv(prefix + '_MODEL')
        if not model:
            raise ValueError(prefix + '_MODEL must name a model available to your account')
        return _tagged(OpenAILLM(api_key=key, base_url=os.getenv(prefix + '_BASE_URL', url), model=model), provider)
    raise ValueError(f'Unknown LLM provider: {provider}')
