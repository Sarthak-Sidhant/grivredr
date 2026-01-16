"""
Multi-Provider AI Client
Supports Anthropic, OpenAI, Gemini, and OpenRouter with granular model selection
"""

import os
from typing import Optional, List, Dict, Any, Union
import logging
from abc import ABC, abstractmethod

from anthropic import Anthropic
import openai
from openai import OpenAI
from dotenv import load_dotenv

from config.settings import settings, AIProvider, TaskType, ModelConfig
from utils.ai_cache import AICache

load_dotenv()
logger = logging.getLogger(__name__)


class BaseAIProvider(ABC):
    """Base class for AI providers"""

    @abstractmethod
    def create_message(
        self,
        messages: List[Dict[str, Any]],
        model_config: ModelConfig,
        system: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Create a message completion"""
        pass

    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """Estimate token count"""
        pass


class AnthropicProvider(BaseAIProvider):
    """Anthropic Claude provider"""

    def __init__(self, api_key: str):
        base_url = os.getenv("ANTHROPIC_API_URL", "https://ai.megallm.io")
        self.client = Anthropic(base_url=base_url, api_key=api_key)
        logger.info(f"Initialized Anthropic provider with base URL: {base_url}")

    def create_message(
        self,
        messages: List[Dict[str, Any]],
        model_config: ModelConfig,
        system: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Create message using Anthropic API"""
        params = {
            "model": model_config.model_name,
            "messages": messages,
            "max_tokens": model_config.max_tokens,
            "temperature": model_config.temperature,
        }

        if system:
            params["system"] = system

        params.update(kwargs)

        response = self.client.messages.create(**params)

        # Convert to standard format
        return {
            "content": response.content[0].text if response.content else "",
            "usage": {
                "prompt_tokens": response.usage.input_tokens,
                "completion_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.input_tokens
                + response.usage.output_tokens,
            },
            "model": response.model,
            "finish_reason": response.stop_reason,
        }

    def count_tokens(self, text: str) -> int:
        """Estimate tokens (roughly 4 chars per token for Claude)"""
        return len(text) // 4


class OpenAIProvider(BaseAIProvider):
    """OpenAI GPT provider"""

    def __init__(self, api_key: str):
        self.client = OpenAI(api_key=api_key)
        logger.info("Initialized OpenAI provider")

    def create_message(
        self,
        messages: List[Dict[str, Any]],
        model_config: ModelConfig,
        system: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Create message using OpenAI API"""
        # Format messages for OpenAI (convert Anthropic image format if needed)
        formatted_messages = []
        
        # Add system message if provided
        if system:
            formatted_messages.append({"role": "system", "content": system})
            
        for msg in messages:
            content = msg["content"]
            new_content = content
            
            # Handle list content (potentially with images)
            if isinstance(content, list):
                new_content = []
                for part in content:
                    if isinstance(part, dict):
                        if part.get("type") == "text":
                            new_content.append({"type": "text", "text": part["text"]})
                        elif part.get("type") == "image":
                            # Convert Anthropic image format to OpenAI
                            source = part.get("source", {})
                            if source.get("type") == "base64":
                                media_type = source.get("media_type", "image/png")
                                data = source.get("data", "")
                                new_content.append({
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:{media_type};base64,{data}"
                                    }
                                })
                    else:
                        # String or other format
                        new_content.append(part)
            
            formatted_messages.append({"role": msg["role"], "content": new_content})

        response = self.client.chat.completions.create(
            model=model_config.model_name,
            messages=formatted_messages,
            max_tokens=model_config.max_tokens,
            temperature=model_config.temperature,
            **kwargs,
        )

        # Convert to standard format
        return {
            "content": response.choices[0].message.content or "",
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            },
            "model": response.model,
            "finish_reason": response.choices[0].finish_reason,
        }

    def count_tokens(self, text: str) -> int:
        """Estimate tokens (roughly 4 chars per token)"""
        return len(text) // 4


class AnthropicCompatResponse:
    """Mimics Anthropic response object structure"""
    def __init__(self, content: str, input_tokens: int = 0, output_tokens: int = 0, model: str = "", stop_reason: str = "stop"):
        self.content = [type('ContentBlock', (), {'text': content})()]
        self.usage = type('Usage', (), {'input_tokens': input_tokens, 'output_tokens': output_tokens})()
        self.model = model
        self.stop_reason = stop_reason


class AnthropicCompatMessages:
    """Mimics Anthropic client.messages interface but uses Gemini"""
    def __init__(self, genai_module, default_model: str = "gemini-2.0-flash"):
        self.genai = genai_module
        self.default_model = default_model
    
    def create(self, model: str, messages: List[Dict], max_tokens: int = 4096, 
               temperature: float = 0.5, **kwargs) -> AnthropicCompatResponse:
        """Create a message using Gemini, mimicking Anthropic's interface"""
        import base64 as b64
        
        # Convert messages to Gemini format
        gemini_model = self.genai.GenerativeModel(
            model or self.default_model,
            generation_config={
                "temperature": temperature,
                "max_output_tokens": max_tokens,
            }
        )
        
        # Build Gemini parts from Anthropic-style messages
        parts = []
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, str):
                parts.append(content)
            elif isinstance(content, list):
                for item in content:
                    if isinstance(item, dict):
                        if item.get("type") == "text":
                            parts.append(item["text"])
                        elif item.get("type") == "image":
                            source = item.get("source", {})
                            if source.get("type") == "base64":
                                try:
                                    data_bytes = b64.b64decode(source.get("data", ""))
                                    parts.append({
                                        "mime_type": source.get("media_type", "image/png"),
                                        "data": data_bytes
                                    })
                                except Exception:
                                    pass
        
        # Generate response
        response = gemini_model.generate_content(parts)
        
        # Extract usage if available
        input_tokens = 0
        output_tokens = 0
        if hasattr(response, 'usage_metadata'):
            input_tokens = getattr(response.usage_metadata, 'prompt_token_count', 0)
            output_tokens = getattr(response.usage_metadata, 'candidates_token_count', 0)
        
        return AnthropicCompatResponse(
            content=response.text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model=model or self.default_model
        )


class AnthropicCompatWrapper:
    """Wrapper that mimics Anthropic client interface but uses Gemini"""
    def __init__(self, genai_module, default_model: str = "gemini-2.0-flash"):
        self.messages = AnthropicCompatMessages(genai_module, default_model)


class GeminiProvider(BaseAIProvider):
    """Google Gemini provider"""

    def __init__(self, api_key: str):
        try:
            import google.generativeai as genai

            genai.configure(api_key=api_key)
            self.genai = genai
            logger.info("Initialized Gemini provider")
        except ImportError:
            raise ImportError(
                "google-generativeai package not installed. "
                "Install it with: pip install google-generativeai"
            )

    def create_message(
        self,
        messages: List[Dict[str, Any]],
        model_config: ModelConfig,
        system: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Create message using Gemini API"""
        model = self.genai.GenerativeModel(
            model_config.model_name,
            generation_config={
                "temperature": model_config.temperature,
                "max_output_tokens": model_config.max_tokens,
            },
        )

        # Convert messages to Gemini format
        chat_history = []
        for msg in messages[:-1]:
            role = "user" if msg["role"] == "user" else "model"
            content = msg["content"]
            parts = []
            
            if isinstance(content, str):
                parts.append(content)
            elif isinstance(content, list):
                for part in content:
                    if isinstance(part, dict):
                        if part.get("type") == "text":
                            parts.append(part["text"])
                        elif part.get("type") == "image":
                            # Convert Anthropic image format to Gemini
                            source = part.get("source", {})
                            if source.get("type") == "base64":
                                import base64
                                # Gemini expects raw bytes for blob
                                try:
                                    data_bytes = base64.b64decode(source.get("data", ""))
                                    parts.append({
                                        "mime_type": source.get("media_type", "image/png"),
                                        "data": data_bytes
                                    })
                                except Exception as e:
                                    logger.warning(f"Failed to decode image for Gemini: {e}")
            
            if parts:
                chat_history.append({"role": role, "parts": parts})

        # Start chat
        chat = model.start_chat(history=chat_history)

        # Get last message content
        last_msg_content = messages[-1]["content"]
        last_message_parts = []
        
        if isinstance(last_msg_content, str):
            last_message_parts.append(last_msg_content)
        elif isinstance(last_msg_content, list):
            for part in last_msg_content:
                if isinstance(part, dict):
                    if part.get("type") == "text":
                        last_message_parts.append(part["text"])
                    elif part.get("type") == "image":
                        # Convert Anthropic image format to Gemini
                        source = part.get("source", {})
                        if source.get("type") == "base64":
                            import base64
                            try:
                                data_bytes = base64.b64decode(source.get("data", ""))
                                last_message_parts.append({
                                    "mime_type": source.get("media_type", "image/png"),
                                    "data": data_bytes
                                })
                            except Exception as e:
                                logger.warning(f"Failed to decode image for Gemini: {e}")

        # Add system instruction if provided (prepend to last message)
        if system:
            # Check if first part is text, if so prepend system
            if last_message_parts and isinstance(last_message_parts[0], str):
                last_message_parts[0] = f"{system}\n\n{last_message_parts[0]}"
            else:
                last_message_parts.insert(0, system)

        response = chat.send_message(last_message_parts)

        # Convert to standard format
        return {
            "content": response.text,
            "usage": {
                "prompt_tokens": response.usage_metadata.prompt_token_count
                if hasattr(response, "usage_metadata")
                else 0,
                "completion_tokens": response.usage_metadata.candidates_token_count
                if hasattr(response, "usage_metadata")
                else 0,
                "total_tokens": response.usage_metadata.total_token_count
                if hasattr(response, "usage_metadata")
                else 0,
            },
            "model": model_config.model_name,
            "finish_reason": "stop",
        }

    def count_tokens(self, text: str) -> int:
        """Estimate tokens"""
        return len(text) // 4


class OpenRouterProvider(BaseAIProvider):
    """OpenRouter provider (supports multiple models)"""

    def __init__(self, api_key: str):
        self.client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)
        logger.info("Initialized OpenRouter provider")

    def create_message(
        self,
        messages: List[Dict[str, Any]],
        model_config: ModelConfig,
        system: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Create message using OpenRouter API"""
        # Add system message if provided
        formatted_messages = []
        if system:
            formatted_messages.append({"role": "system", "content": system})
        formatted_messages.extend(messages)

        response = self.client.chat.completions.create(
            model=model_config.model_name,
            messages=formatted_messages,
            max_tokens=model_config.max_tokens,
            temperature=model_config.temperature,
            **kwargs,
        )

        # Convert to standard format
        return {
            "content": response.choices[0].message.content or "",
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens
                if response.usage
                else 0,
                "total_tokens": response.usage.total_tokens if response.usage else 0,
            },
            "model": response.model,
            "finish_reason": response.choices[0].finish_reason,
        }

    def count_tokens(self, text: str) -> int:
        """Estimate tokens"""
        return len(text) // 4


class MultiProviderAIClient:
    """
    Multi-provider AI client with granular task-specific model selection
    """

    def __init__(self, enable_cache: bool = True):
        """Initialize multi-provider AI client"""
        self.providers: Dict[AIProvider, BaseAIProvider] = {}
        self.enable_cache = enable_cache
        self.cache = AICache() if enable_cache else None

        # Initialize available providers
        self._initialize_providers()

        logger.info(
            f"Initialized MultiProviderAIClient with providers: {list(self.providers.keys())}"
        )

    @property
    def client(self):
        """
        Backward compatibility property for agents that use ai_client.client.messages.create()
        Returns an Anthropic-compatible interface (uses Gemini if that's the default provider)
        """
        # Check what provider is configured for form_discovery (most common task)
        default_provider = settings.task_models.form_discovery.provider
        
        # If Gemini is the default provider, return the compatibility wrapper
        if default_provider == AIProvider.GEMINI and AIProvider.GEMINI in self.providers:
            gemini_provider = self.providers[AIProvider.GEMINI]
            return AnthropicCompatWrapper(gemini_provider.genai)
        
        # Otherwise use Anthropic if available
        if AIProvider.ANTHROPIC in self.providers:
            return self.providers[AIProvider.ANTHROPIC].client
        
        # Fallback to first available provider's client
        for provider in self.providers.values():
            if hasattr(provider, 'client'):
                return provider.client
        raise AttributeError("No AI provider with a direct client available")

    @property
    def models(self):
        """
        Backward compatibility property for agents that use ai_client.models["powerful"]
        Returns model names from settings
        """
        return {
            "fast": settings.task_models.form_discovery.model_name,
            "balanced": settings.task_models.code_generation.model_name,
            "powerful": settings.task_models.code_generation.model_name,
        }

    def _initialize_providers(self):
        """Initialize all available AI providers based on API keys"""
        # Anthropic
        anthropic_key = settings.get_api_key_for_provider(AIProvider.ANTHROPIC)
        if anthropic_key:
            try:
                self.providers[AIProvider.ANTHROPIC] = AnthropicProvider(anthropic_key)
                logger.info("✅ Anthropic provider initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Anthropic provider: {e}")

        # OpenAI
        openai_key = settings.get_api_key_for_provider(AIProvider.OPENAI)
        if openai_key:
            try:
                self.providers[AIProvider.OPENAI] = OpenAIProvider(openai_key)
                logger.info("✅ OpenAI provider initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize OpenAI provider: {e}")

        # Gemini
        gemini_key = settings.get_api_key_for_provider(AIProvider.GEMINI)
        if gemini_key:
            try:
                self.providers[AIProvider.GEMINI] = GeminiProvider(gemini_key)
                logger.info("✅ Gemini provider initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Gemini provider: {e}")

        # OpenRouter
        openrouter_key = settings.get_api_key_for_provider(AIProvider.OPENROUTER)
        if openrouter_key:
            try:
                self.providers[AIProvider.OPENROUTER] = OpenRouterProvider(
                    openrouter_key
                )
                logger.info("✅ OpenRouter provider initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize OpenRouter provider: {e}")

        if not self.providers:
            raise ValueError(
                "No AI providers available. Please set at least one API key:\n"
                "  - api_key or ANTHROPIC_API_KEY for Anthropic\n"
                "  - OPENAI_API_KEY for OpenAI\n"
                "  - GEMINI_API_KEY for Gemini\n"
                "  - OPENROUTER_API_KEY for OpenRouter"
            )

    def create_message(
        self,
        messages: List[Dict[str, Any]],
        task_type: TaskType,
        system: Optional[str] = None,
        use_cache: bool = True,
        override_model: Optional[ModelConfig] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Create a message using the configured model for the task type

        Args:
            messages: List of message dicts with 'role' and 'content'
            task_type: Type of task (determines which model to use)
            system: Optional system message
            use_cache: Whether to use AI cache
            override_model: Optional model config to override default
            **kwargs: Additional provider-specific parameters

        Returns:
            Dict with 'content', 'usage', 'model', 'finish_reason'
        """
        # Get model config for this task
        model_config = override_model or settings.get_model_for_task(task_type)

        # Check cache if enabled
        if use_cache and self.cache:
            # Build cache key from messages + model + system
            cache_input = f"{str(messages)}:{model_config.model_name}:{system or ''}:{model_config.temperature}"
            cache_key = self.cache.generate_cache_key(
                cache_input,
                model_config.model_name,
            )
            cached = self.cache.get(cache_key)
            if cached:
                logger.debug(f"Cache hit for task {task_type}")
                return cached

        # Get provider
        provider = self.providers.get(model_config.provider)
        if not provider:
            raise ValueError(
                f"Provider {model_config.provider} not available. "
                f"Available providers: {list(self.providers.keys())}"
            )

        # Create message
        logger.info(
            f"Creating message for task {task_type} using "
            f"{model_config.provider}:{model_config.model_name}"
        )

        try:
            response = provider.create_message(
                messages=messages, model_config=model_config, system=system, **kwargs
            )

            # Cache response
            if use_cache and self.cache:
                self.cache.set(cache_key, response)

            return response

        except Exception as e:
            logger.error(f"Error creating message with {model_config.provider}: {e}")
            raise

    def count_tokens(
        self, text: str, provider: AIProvider = AIProvider.ANTHROPIC
    ) -> int:
        """Count tokens for given text using specified provider"""
        provider_instance = self.providers.get(provider)
        if provider_instance:
            return provider_instance.count_tokens(text)
        return len(text) // 4  # Fallback estimate

    def list_available_providers(self) -> List[AIProvider]:
        """List all available providers"""
        return list(self.providers.keys())

    def clear_cache(self) -> int:
        """Clear AI cache"""
        if self.cache:
            return self.cache.clear_all()
        return 0


# Singleton instance
ai_client = MultiProviderAIClient(enable_cache=settings.enable_ai_cache)
