"""
Comprehensive configuration system for Grivredr
Supports multiple AI providers, browsers, and granular task-specific settings
"""

import os
from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()


class AIProvider(str, Enum):
    """Supported AI providers"""

    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    GEMINI = "gemini"
    OPENROUTER = "openrouter"


class BrowserType(str, Enum):
    """Supported browser types"""

    CHROMIUM = "chromium"
    FIREFOX = "firefox"
    WEBKIT = "webkit"


class TaskType(str, Enum):
    """Different task types that require AI"""

    FORM_DISCOVERY = "form_discovery"
    JS_ANALYSIS = "js_analysis"
    TESTING = "testing"
    CODE_GENERATION = "code_generation"
    VALIDATION = "validation"
    HEALING = "healing"
    VISION = "vision"  # For AI vision analysis (screenshots, form understanding)


class ModelConfig(BaseModel):
    """Configuration for a specific model"""

    provider: AIProvider
    model_name: str
    temperature: float = 0.7
    max_tokens: int = 4096
    timeout: int = 120


class TaskModelMapping(BaseModel):
    """Maps task types to specific models - reads from environment variables"""

    form_discovery: ModelConfig = Field(default=None)
    js_analysis: ModelConfig = Field(default=None)
    testing: ModelConfig = Field(default=None)
    code_generation: ModelConfig = Field(default=None)
    validation: ModelConfig = Field(default=None)
    healing: ModelConfig = Field(default=None)
    vision: ModelConfig = Field(default=None)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Load each task config from environment variables
        self.form_discovery = self._load_task_config("FORM_DISCOVERY", default_temp=0.5)
        self.js_analysis = self._load_task_config("JS_ANALYSIS", default_temp=0.3)
        self.testing = self._load_task_config("TESTING", default_temp=0.4)
        self.code_generation = self._load_task_config("CODE_GENERATION", default_temp=0.2, default_tokens=8192)
        self.validation = self._load_task_config("VALIDATION", default_temp=0.3)
        self.healing = self._load_task_config("HEALING", default_temp=0.2, default_tokens=8192)
        self.vision = self._load_task_config("VISION", default_temp=0.4)

    def _load_task_config(
        self, 
        task_prefix: str, 
        default_temp: float = 0.5,
        default_tokens: int = 4096
    ) -> ModelConfig:
        """Load a task's model config from environment variables"""
        provider_str = os.getenv(f"{task_prefix}_PROVIDER", "anthropic").lower()
        model_name = os.getenv(f"{task_prefix}_MODEL", "claude-sonnet-4.5")
        temperature = float(os.getenv(f"{task_prefix}_TEMPERATURE", str(default_temp)))
        max_tokens = int(os.getenv(f"{task_prefix}_MAX_TOKENS", str(default_tokens)))

        # Map provider string to enum
        provider_map = {
            "anthropic": AIProvider.ANTHROPIC,
            "openai": AIProvider.OPENAI,
            "gemini": AIProvider.GEMINI,
            "openrouter": AIProvider.OPENROUTER,
        }
        provider = provider_map.get(provider_str, AIProvider.ANTHROPIC)

        return ModelConfig(
            provider=provider,
            model_name=model_name,
            temperature=temperature,
            max_tokens=max_tokens,
        )


class BrowserConfig(BaseModel):
    """Browser automation configuration"""

    browser_type: BrowserType = BrowserType.CHROMIUM
    headless: bool = True
    viewport_width: int = 1920
    viewport_height: int = 1080
    user_agent: Optional[str] = None
    timeout: int = 30000  # 30 seconds


class AIProviderKeys(BaseModel):
    """API keys for different providers"""

    anthropic_api_key: Optional[str] = Field(default=None, alias="api_key")
    openai_api_key: Optional[str] = Field(default=None)
    gemini_api_key: Optional[str] = Field(default=None)
    openrouter_api_key: Optional[str] = Field(default=None)

    class Config:
        populate_by_name = True


class GrivredrSettings(BaseSettings):
    """Main settings class for Grivredr"""

    # AI Provider Configuration
    ai_provider_keys: AIProviderKeys = Field(default_factory=AIProviderKeys)
    task_models: TaskModelMapping = Field(default_factory=TaskModelMapping)

    # Browser Configuration
    browser: BrowserConfig = Field(default_factory=BrowserConfig)

    # Cache Configuration
    enable_ai_cache: bool = True
    cache_dir: str = "./data/ai_cache"

    # Training Configuration
    max_retries: int = 3
    validation_enabled: bool = True
    save_screenshots: bool = True
    screenshot_dir: str = "./outputs/screenshots"

    # Output Configuration
    output_dir: str = "./scrapers"
    training_session_dir: str = "./data/training_sessions"

    # Logging
    log_level: str = "INFO"
    log_file: Optional[str] = "./logs/grivredr.log"

    class Config:
        env_file = ".env"
        env_nested_delimiter = "__"
        extra = "allow"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Load API keys from environment
        self.ai_provider_keys.anthropic_api_key = os.getenv("api_key") or os.getenv(
            "ANTHROPIC_API_KEY"
        )
        self.ai_provider_keys.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.ai_provider_keys.gemini_api_key = os.getenv("GEMINI_API_KEY")
        self.ai_provider_keys.openrouter_api_key = os.getenv("OPENROUTER_API_KEY")

    def get_model_for_task(self, task: TaskType) -> ModelConfig:
        """Get the configured model for a specific task"""
        task_to_attr = {
            TaskType.FORM_DISCOVERY: self.task_models.form_discovery,
            TaskType.JS_ANALYSIS: self.task_models.js_analysis,
            TaskType.TESTING: self.task_models.testing,
            TaskType.CODE_GENERATION: self.task_models.code_generation,
            TaskType.VALIDATION: self.task_models.validation,
            TaskType.HEALING: self.task_models.healing,
            TaskType.VISION: self.task_models.vision,
        }
        return task_to_attr.get(task)

    def get_api_key_for_provider(self, provider: AIProvider) -> Optional[str]:
        """Get API key for a specific provider"""
        provider_to_key = {
            AIProvider.ANTHROPIC: self.ai_provider_keys.anthropic_api_key,
            AIProvider.OPENAI: self.ai_provider_keys.openai_api_key,
            AIProvider.GEMINI: self.ai_provider_keys.gemini_api_key,
            AIProvider.OPENROUTER: self.ai_provider_keys.openrouter_api_key,
        }
        return provider_to_key.get(provider)

    def update_task_model(self, task: TaskType, model_config: ModelConfig):
        """Update model configuration for a specific task"""
        if task == TaskType.FORM_DISCOVERY:
            self.task_models.form_discovery = model_config
        elif task == TaskType.JS_ANALYSIS:
            self.task_models.js_analysis = model_config
        elif task == TaskType.TESTING:
            self.task_models.testing = model_config
        elif task == TaskType.CODE_GENERATION:
            self.task_models.code_generation = model_config
        elif task == TaskType.VALIDATION:
            self.task_models.validation = model_config
        elif task == TaskType.HEALING:
            self.task_models.healing = model_config
        elif task == TaskType.VISION:
            self.task_models.vision = model_config

    def to_dict(self) -> Dict[str, Any]:
        """Convert settings to dictionary"""
        return self.model_dump()


# Global settings instance
settings = GrivredrSettings()
