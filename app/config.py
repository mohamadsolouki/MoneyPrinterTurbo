import os
import tomli
from typing import Dict, Any, Optional
from pathlib import Path

class Config:
    def __init__(self):
        self.app: Dict[str, Any] = {}
        self.LLM_PROVIDERS: Dict[str, Dict[str, Any]] = {
            "openai": {
                "api_key": "",
                "base_url": "https://api.openai.com/v1",
                "models": ["gpt-3.5-turbo", "gpt-4"]
            },
            "g4f": {
                "models": ["gpt-3.5-turbo", "gpt-4"]
            },
            "pollinations": {
                "base_url": "https://text.pollinations.ai/openai",
                "models": ["openai-fast"]
            }
        }
        self._load_config()
        
    def _load_config(self):
        """Load configuration from config.toml file."""
        try:
            config_path = Path("config.toml")
            if not config_path.exists():
                logger.warning("config.toml not found, using default configuration")
                return
                
            with open(config_path, "rb") as f:
                config_data = tomli.load(f)
                
            # Validate and update app configuration
            if "app" in config_data:
                self._validate_app_config(config_data["app"])
                self.app.update(config_data["app"])
                
            # Validate and update LLM provider configurations
            if "llm_providers" in config_data:
                self._validate_llm_providers(config_data["llm_providers"])
                self.LLM_PROVIDERS.update(config_data["llm_providers"])
                
        except Exception as e:
            logger.error(f"Error loading configuration: {str(e)}")
            raise
            
    def _validate_app_config(self, config: Dict[str, Any]):
        """Validate application configuration."""
        required_fields = ["version", "language"]
        for field in required_fields:
            if field not in config:
                raise ValueError(f"Missing required field in app config: {field}")
                
        # Validate version format
        version = config.get("version", "")
        if not isinstance(version, str) or not version.strip():
            raise ValueError("Invalid version format in app config")
            
        # Validate language
        language = config.get("language", "")
        if not isinstance(language, str) or not language.strip():
            raise ValueError("Invalid language format in app config")
            
    def _validate_llm_providers(self, providers: Dict[str, Dict[str, Any]]):
        """Validate LLM provider configurations."""
        for provider, config in providers.items():
            if provider not in self.LLM_PROVIDERS:
                raise ValueError(f"Unsupported LLM provider: {provider}")
                
            # Validate required fields for each provider
            if provider == "openai":
                if "api_key" not in config:
                    raise ValueError("OpenAI configuration missing api_key")
                if "base_url" not in config:
                    raise ValueError("OpenAI configuration missing base_url")
                if "models" not in config:
                    raise ValueError("OpenAI configuration missing models")
                    
            elif provider == "pollinations":
                if "base_url" not in config:
                    raise ValueError("Pollinations configuration missing base_url")
                if "models" not in config:
                    raise ValueError("Pollinations configuration missing models")
                    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value with type checking."""
        value = self.app.get(key, default)
        
        # Type checking for common configuration values
        if key == "version" and not isinstance(value, str):
            raise TypeError("Version must be a string")
        elif key == "language" and not isinstance(value, str):
            raise TypeError("Language must be a string")
        elif key == "api_key" and not isinstance(value, str):
            raise TypeError("API key must be a string")
        elif key == "base_url" and not isinstance(value, str):
            raise TypeError("Base URL must be a string")
            
        return value
        
    def get_provider_config(self, provider: str) -> Dict[str, Any]:
        """Get LLM provider configuration."""
        if provider not in self.LLM_PROVIDERS:
            raise ValueError(f"Unsupported LLM provider: {provider}")
        return self.LLM_PROVIDERS[provider]
        
    def get_provider_models(self, provider: str) -> list:
        """Get available models for an LLM provider."""
        provider_config = self.get_provider_config(provider)
        return provider_config.get("models", [])
        
    def is_provider_configured(self, provider: str) -> bool:
        """Check if an LLM provider is properly configured."""
        try:
            provider_config = self.get_provider_config(provider)
            
            if provider == "openai":
                return bool(provider_config.get("api_key"))
            elif provider == "pollinations":
                return bool(provider_config.get("base_url"))
            elif provider == "g4f":
                return True
                
            return False
        except ValueError:
            return False

# Initialize configuration
config = Config() 