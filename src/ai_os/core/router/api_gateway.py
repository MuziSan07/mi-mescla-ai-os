"""
AI-OS Unified API Gateway - Wrapper around multiple LLM providers
Supports: OpenAI, Anthropic, Ollama, Azure, Google AI, HuggingFace, Cohere, etc.
"""

import os
import httpx
from typing import Optional, Dict, List, Any
from dataclasses import dataclass
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class ProviderConfig:
    """Configuration for each LLM provider"""
    
    PROVIDERS = {
        "openai": {
            "base_url": "https://api.openai.com/v1",
            "models": ["gpt-4o", "gpt-4-turbo", "gpt-3.5-turbo", "gpt-4"],
            "supports": ["chat", "embeddings", "images"],
        },
        "anthropic": {
            "base_url": "https://api.anthropic.com/v1",
            "models": ["claude-3-5-sonnet-20241022", "claude-3-opus-20240229", "claude-3-sonnet-20240229"],
            "supports": ["chat", "vision"],
        },
        "ollama": {
            "base_url": os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            "models": ["llama2", "mistral", "codellama", "phi"],
            "supports": ["chat", "embeddings"],
        },
        "azure": {
            "base_url": os.getenv("AZURE_OPENAI_ENDPOINT", ""),
            "models": ["gpt-4", "gpt-35-turbo"],
            "supports": ["chat", "embeddings"],
        },
        "google": {
            "base_url": "https://generativelanguage.googleapis.com/v1beta",
            "models": ["gemini-1.5-pro", "gemini-1.5-flash"],
            "supports": ["chat", "vision"],
        },
        "huggingface": {
            "base_url": "https://api-inference.huggingface.co",
            "models": ["*"],
            "supports": ["chat", "embeddings", "text-to-image"],
        },
        "cohere": {
            "base_url": "https://api.cohere.ai/v1",
            "models": ["command-r-plus", "command-r"],
            "supports": ["chat", "embeddings"],
        },
        "local": {
            "base_url": os.getenv("LOCAL_API_ENDPOINT", "http://localhost:8000"),
            "models": ["*"],
            "supports": ["chat", "embeddings"],
        },
        # Free-tier, OpenAI-compatible cloud providers.
        "groq": {
            "base_url": "https://api.groq.com/openai/v1",
            "models": ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768"],
            "supports": ["chat"],
        },
        "openrouter": {
            "base_url": "https://openrouter.ai/api/v1",
            "models": ["*"],
            "supports": ["chat"],
        },
    }
    
    @classmethod
    def get_provider(cls, name: str) -> Optional[Dict]:
        return cls.PROVIDERS.get(name)


@dataclass
class ChatMessage:
    """Chat message structure"""
    role: str
    content: str
    name: Optional[str] = None


@dataclass
class ChatCompletionRequest:
    """Request for chat completion"""
    model: str
    messages: List[ChatMessage]
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    stream: bool = False
    seed: Optional[int] = None
    top_p: Optional[float] = None
    frequency_penalty: Optional[float] = None
    presence_penalty: Optional[float] = None
    stop: Optional[List[str]] = None


@dataclass
class ChatCompletionResponse:
    """Response from chat completion"""
    id: str
    created: int
    model: str
    choices: List[Dict]
    usage: Dict
    provider: str
    object: str = "chat.completion"


class UnifiedAPIGateway:
    """
    Unified API Gateway that wraps multiple LLM providers.
    Works like LiteLLM - single interface for all providers.
    """
    
    def __init__(self):
        self.providers = ProviderConfig.PROVIDERS
        self.fallback_models = self._build_fallback_map()
        self.cache = {}
        self.request_count = 0
        
    def _build_fallback_map(self) -> Dict[str, List[str]]:
        """Build fallback chain for each provider"""
        return {
            "gpt-4": ["claude-3-5-sonnet", "gemini-1.5-pro", "gpt-3.5-turbo"],
            "claude-3-opus": ["claude-3-sonnet", "gemini-1.5-pro", "gpt-4"],
            "gpt-3.5-turbo": ["llama2", "mistral"],
            "default": ["gpt-3.5-turbo", "claude-3-sonnet", "llama2"],
        }
    
    def _detect_provider(self, model: str) -> tuple[str, str]:
        """Detect provider from model name"""
        # Explicit "provider:model" syntax wins (e.g. "groq:llama-3.3-70b-versatile").
        if ":" in model:
            prefix, _, rest = model.partition(":")
            if prefix in self.providers and rest:
                return prefix, rest
        # Check explicit prefix
        if "-" in model:
            provider, _, rest = model.partition("-")
            if provider in self.providers:
                return provider, model
        
        # Auto-detect from model name patterns
        if model.startswith("gpt"):
            return "openai", model
        elif model.startswith("claude"):
            return "anthropic", model
        elif model.startswith("gemini"):
            return "google", model
        elif model.startswith("llama") or model in ["mistral", "codellama"]:
            return "ollama", model
        elif model.startswith("command"):
            return "cohere", model
        
        return "openai", "gpt-3.5-turbo"
    
    # ---- Hybrid routing helpers ------------------------------------------

    # Env var(s) that must be set for a cloud provider to be usable.
    _CREDENTIAL_ENV = {
        "openai": ["OPENAI_API_KEY"],
        "anthropic": ["ANTHROPIC_API_KEY", "ANTHROPIC_KEY"],
        "google": ["GOOGLE_API_KEY"],
        "cohere": ["COHERE_API_KEY"],
        "huggingface": ["HUGGING_FACE_TOKEN", "HUGGINGFACE_TOKEN"],
        "azure": ["AZURE_OPENAI_API_KEY"],
        "groq": ["GROQ_API_KEY"],
        "openrouter": ["OPENROUTER_API_KEY"],
    }
    # Primary key env per OpenAI-compatible provider (for request auth).
    _KEY_ENV = {
        "openai": "OPENAI_API_KEY",
        "groq": "GROQ_API_KEY",
        "openrouter": "OPENROUTER_API_KEY",
        "local": "LOCAL_API_KEY",
    }

    def _provider_available(self, provider: str) -> bool:
        """A provider is usable if it is local (ollama/local) or has a credential set."""
        if provider in ("ollama", "local"):
            return True
        return any(os.getenv(n) for n in self._CREDENTIAL_ENV.get(provider, []))

    def _candidate_chain(self, model: str) -> List[str]:
        """Ordered list of concrete models to try: requested first, then fallbacks.

        Always ends with a local Ollama model so a hybrid box with no cloud
        keys still has a working last-resort option.
        """
        chain: List[str] = []
        if model:
            chain.append(model)
        chain += self.fallback_models.get(model, self.fallback_models.get("default", []))
        # Always end with the configured local model — the one that is actually
        # pulled in Ollama — so the box works even if the hard-coded fallback
        # chain names models (llama2/mistral) that aren't installed.
        chain.append(os.getenv("DEFAULT_LOCAL_MODEL", "llama3.2"))
        # de-duplicate while preserving order
        seen, ordered = set(), []
        for m in chain:
            if m not in seen:
                seen.add(m)
                ordered.append(m)
        return ordered

    def provider_status(self) -> Dict[str, Dict[str, Any]]:
        """Report which providers are currently usable (for health/dashboard)."""
        return {
            name: {
                "available": self._provider_available(name),
                "type": "local" if name in ("ollama", "local") else "cloud",
                "models": cfg.get("models", []),
            }
            for name, cfg in self.providers.items()
        }

    async def chat(
        self,
        model: str,
        messages: List[Dict],
        **kwargs
    ) -> ChatCompletionResponse:
        """
        Main chat completion endpoint — hybrid (local + cloud) with fallback.

        Tries the requested model, then its fallback chain, skipping any provider
        that has no credentials configured, until one succeeds. Local Ollama is
        always the final fallback so an offline box still works.
        """
        errors: List[str] = []
        for candidate in self._candidate_chain(model):
            provider_name, concrete = self._detect_provider(candidate)
            config = self.providers.get(provider_name)
            if not config:
                continue
            if not self._provider_available(provider_name):
                errors.append(f"{provider_name}: no credentials configured")
                continue
            self.request_count += 1
            try:
                return await self._dispatch(provider_name, config, concrete, messages, **kwargs)
            except Exception as e:  # try the next provider in the chain
                logger.warning(f"Provider {provider_name} ({concrete}) failed: {e}")
                errors.append(f"{provider_name}/{concrete}: {e}")
        raise RuntimeError(
            "All providers failed or unavailable. Tried: " + " | ".join(errors)
            + ". Configure a cloud API key or start Ollama with a pulled model."
        )

    async def _dispatch(
        self,
        provider_name: str,
        config: Dict,
        model: str,
        messages: List[Dict],
        **kwargs
    ) -> ChatCompletionResponse:
        """Route a single request to the concrete provider implementation."""
        # OpenAI-compatible providers share one handler (differ only in base_url + key).
        if provider_name in ("openai", "groq", "openrouter", "local"):
            return await self._openai_request(config, model, messages,
                                              provider_name=provider_name, **kwargs)
        elif provider_name == "anthropic":
            return await self._anthropic_request(config, model, messages, **kwargs)
        elif provider_name == "ollama":
            return await self._ollama_request(config, model, messages, **kwargs)
        elif provider_name == "azure":
            return await self._azure_request(config, model, messages, **kwargs)
        elif provider_name == "google":
            return await self._google_request(config, model, messages, **kwargs)
        elif provider_name == "huggingface":
            return await self._hf_request(config, model, messages, **kwargs)
        elif provider_name == "cohere":
            return await self._cohere_request(config, model, messages, **kwargs)
        return await self._openai_request(config, model, messages,
                                          provider_name="openai", **kwargs)

    async def _openai_request(self, config: Dict, model: str, messages: List[Dict],
                              provider_name: str = "openai", **kwargs) -> ChatCompletionResponse:
        """Handle any OpenAI-compatible API (OpenAI, Groq, OpenRouter, local)."""
        key_env = self._KEY_ENV.get(provider_name, "OPENAI_API_KEY")
        headers = {
            "Authorization": f"Bearer {os.getenv(key_env, '')}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": model,
            "messages": messages,
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens", 4096),
            "stream": kwargs.get("stream", False),
        }
        
        optional_params = ["seed", "top_p", "frequency_penalty", "presence_penalty", "stop"]
        for p in optional_params:
            if p in kwargs:
                data[p] = kwargs[p]
        
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(
                    f"{config['base_url']}/chat/completions",
                    headers=headers,
                    json=data,
                    timeout=120.0
                )
                resp.raise_for_status()
                result = resp.json()
                
                return ChatCompletionResponse(
                    id=result.get("id", f"chatcmpl-{self.request_count}"),
                    created=int(datetime.now().timestamp()),
                    model=model,
                    choices=result.get("choices", []),
                    usage=result.get("usage", {}),
                    provider=provider_name
                )
            except httpx.HTTPError as e:
                logger.error(f"{provider_name} request failed: {e}")
                raise
    
    async def _anthropic_request(self, config: Dict, model: str, messages: List[Dict], **kwargs) -> ChatCompletionResponse:
        """Handle Anthropic API requests"""
        headers = {
            "x-api-key": os.getenv("ANTHROPIC_API_KEY", os.getenv("ANTHROPIC_KEY", "")),
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json"
        }
        
        # Convert messages to Anthropic format
        system = ""
        anthropic_messages = []
        for msg in messages:
            if msg.get("role") == "system":
                system = msg.get("content", "")
            else:
                anthropic_messages.append(msg)
        
        data = {
            "model": model,
            "messages": anthropic_messages,
            "max_tokens": kwargs.get("max_tokens", 4096),
            "temperature": kwargs.get("temperature", 0.7),
        }
        
        if system:
            data["system"] = system
        
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(
                    f"{config['base_url']}/messages",
                    headers=headers,
                    json=data,
                    timeout=120.0
                )
                resp.raise_for_status()
                result = resp.json()
                
                content = result.get("content", [])
                message_content = content[0].get("text", "") if content else ""
                
                return ChatCompletionResponse(
                    id=f"anthropic-{self.request_count}",
                    created=int(datetime.now().timestamp()),
                    model=model,
                    choices=[{"message": {"role": "assistant", "content": message_content}}],
                    usage={
                        "prompt_tokens": result.get("usage", {}).get("input_tokens", 0),
                        "completion_tokens": result.get("usage", {}).get("output_tokens", 0),
                        "total_tokens": result.get("usage", {}).get("total_tokens", 0),
                    },
                    provider="anthropic"
                )
            except httpx.HTTPError as e:
                logger.error(f"Anthropic request failed: {e}")
                raise
    
    async def _ollama_request(self, config: Dict, model: str, messages: List[Dict], **kwargs) -> ChatCompletionResponse:
        """Handle Ollama API requests"""
        data = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": kwargs.get("temperature", 0.7),
                "num_predict": kwargs.get("max_tokens", 4096),
            }
        }
        
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(
                    f"{config['base_url']}/api/chat",
                    json=data,
                    timeout=180.0
                )
                resp.raise_for_status()
                result = resp.json()
                
                return ChatCompletionResponse(
                    id=f"ollama-{self.request_count}",
                    created=int(datetime.now().timestamp()),
                    model=model,
                    choices=[{"message": result.get("message", {})}],
                    usage={},
                    provider="ollama"
                )
            except httpx.HTTPError as e:
                logger.error(f"Ollama request failed: {e}")
                raise
    
    async def _azure_request(self, config: Dict, model: str, messages: List[Dict], **kwargs) -> ChatCompletionResponse:
        """Handle Azure OpenAI API requests"""
        azure_key = os.getenv("AZURE_OPENAI_API_KEY", "")
        deployment = os.getenv("AZURE_DEPLOYMENT_NAME", model)
        
        headers = {
            "api-key": azure_key,
            "Content-Type": "application/json"
        }
        
        data = {
            "messages": messages,
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens", 4096),
        }
        
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(
                    f"{config['base_url']}/deployments/{deployment}/chat/completions?api-version=2024-02-01",
                    headers=headers,
                    json=data,
                    timeout=120.0
                )
                resp.raise_for_status()
                result = resp.json()
                
                return ChatCompletionResponse(
                    id=result.get("id", f"azure-{self.request_count}"),
                    created=int(datetime.now().timestamp()),
                    model=model,
                    choices=result.get("choices", []),
                    usage=result.get("usage", {}),
                    provider="azure"
                )
            except httpx.HTTPError as e:
                logger.error(f"Azure request failed: {e}")
                raise
    
    async def _google_request(self, config: Dict, model: str, messages: List[Dict], **kwargs) -> ChatCompletionResponse:
        """Handle Google AI API requests"""
        google_key = os.getenv("GOOGLE_API_KEY", "")
        
        # Convert to Google format
        contents = []
        for msg in messages:
            parts = [{"text": msg.get("content", "")}]
            parts_dict = {
                "role": "model" if msg.get("role") == "assistant" else "user",
                "parts": parts
            }
            contents.append(parts_dict)
        
        data = {
            "contents": contents,
            "generationConfig": {
                "temperature": kwargs.get("temperature", 0.7),
                "maxOutputTokens": kwargs.get("max_tokens", 4096),
            }
        }
        
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(
                    f"{config['base_url']}/models/{model}:generateContent?key={google_key}",
                    json=data,
                    timeout=120.0
                )
                resp.raise_for_status()
                result = resp.json()
                
                candidates = result.get("candidates", [])
                content = candidates[0].get("content", {}) if candidates else {}
                parts = content.get("parts", [])
                text = parts[0].get("text", "") if parts else ""
                
                return ChatCompletionResponse(
                    id=f"google-{self.request_count}",
                    created=int(datetime.now().timestamp()),
                    model=model,
                    choices=[{"message": {"role": "assistant", "content": text}}],
                    usage={},
                    provider="google"
                )
            except httpx.HTTPError as e:
                logger.error(f"Google request failed: {e}")
                raise
    
    async def _hf_request(self, config: Dict, model: str, messages: List[Dict], **kwargs) -> ChatCompletionResponse:
        """Handle HuggingFace Inference API requests"""
        hf_token = os.getenv("HUGGING_FACE_TOKEN", "")
        
        headers = {
            "Authorization": f"Bearer {hf_token}",
            "Content-Type": "application/json"
        }
        
        # Get last message as input
        prompt = messages[-1].get("content", "") if messages else ""
        
        data = {
            "inputs": prompt,
            "parameters": {
                "temperature": kwargs.get("temperature", 0.7),
                "max_new_tokens": kwargs.get("max_tokens", 512),
            }
        }
        
        async with httpx.AsyncClient() as client:
            try:
                base = config["base_url"].replace("/v1", "")
                resp = await client.post(
                    f"{base}/models/{model}",
                    headers=headers,
                    json=data,
                    timeout=120.0
                )
                resp.raise_for_status()
                
                return ChatCompletionResponse(
                    id=f"hf-{self.request_count}",
                    created=int(datetime.now().timestamp()),
                    model=model,
                    choices=[{"message": {"role": "assistant", "content": resp.text}}],
                    usage={},
                    provider="huggingface"
                )
            except httpx.HTTPError as e:
                logger.error(f"HuggingFace request failed: {e}")
                raise
    
    async def _cohere_request(self, config: Dict, model: str, messages: List[Dict], **kwargs) -> ChatCompletionResponse:
        """Handle Cohere API requests"""
        cohere_key = os.getenv("COHERE_API_KEY", "")
        
        headers = {
            "Authorization": f"Bearer {cohere_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": model,
            "chat_history": [msg for msg in messages[:-1]],
            "message": messages[-1].get("content", "") if messages else "",
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens", 4096),
        }
        
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(
                    f"{config['base_url']}/chat",
                    headers=headers,
                    json=data,
                    timeout=120.0
                )
                resp.raise_for_status()
                result = resp.json()
                
                return ChatCompletionResponse(
                    id=f"cohere-{self.request_count}",
                    created=int(datetime.now().timestamp()),
                    model=model,
                    choices=[{"message": {"role": "assistant", "content": result.get("text", "")}}],
                    usage={},
                    provider="cohere"
                )
            except httpx.HTTPError as e:
                logger.error(f"Cohere request failed: {e}")
                raise
    
    async def embed(self, model: str, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings from texts.
        Supports: openai, cohere, ollama, huggingface
        """
        provider, _ = self._detect_provider(model)
        
        if provider in ["openai"]:
            headers = {
                "Authorization": f"Bearer {os.getenv('OPENAI_API_KEY', '')}",
                "Content-Type": "application/json"
            }
            data = {"input": texts, "model": "text-embedding-3-small"}
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    "https://api.openai.com/v1/embeddings",
                    headers=headers,
                    json=data,
                    timeout=60.0
                )
                resp.raise_for_status()
                result = resp.json()
                return [item["embedding"] for item in result["data"]]
        
        elif provider in ["cohere"]:
            headers = {
                "Authorization": f"Bearer {os.getenv('COHERE_API_KEY', '')}",
                "Content-Type": "application/json"
            }
            data = {"texts": texts, "model": "embed-english-v3.0"}
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    "https://api.cohere.ai/v1/embeddings",
                    headers=headers,
                    json=data,
                    timeout=60.0
                )
                resp.raise_for_status()
                result = resp.json()
                return result["embeddings"]
        
        # Fallback for local/ollama
        base_url = self.providers.get(provider, {}).get("base_url", "http://localhost:11434")
        embeddings = []
        for text in texts:
            data = {"model": model, "prompt": text}
            async with httpx.AsyncClient() as client:
                resp = await client.post(f"{base_url}/api/embeddings", json=data, timeout=60.0)
                result = resp.json()
                embeddings.append(result.get("embedding", []))
        return embeddings
    
    async def list_models(self) -> Dict[str, List[str]]:
        """List all available models"""
        models = {}
        for provider, config in self.providers.items():
            models[provider] = config.get("models", [])
        return models
    
    def get_provider_info(self, provider: str) -> Optional[Dict]:
        """Get provider info"""
        return self.providers.get(provider)


# Singleton instance
_unified_gateway: Optional[UnifiedAPIGateway] = None


def get_unified_gateway() -> UnifiedAPIGateway:
    global _unified_gateway
    if _unified_gateway is None:
        _unified_gateway = UnifiedAPIGateway()
    return _unified_gateway