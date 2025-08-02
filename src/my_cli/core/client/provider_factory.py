"""
Provider factory for creating content generators based on model names.

This module provides a factory system that automatically detects the appropriate
provider for a given model and creates the corresponding content generator.
"""

import logging
from typing import Dict, List, Optional, Type, Union

from .providers import (
    BaseContentGenerator,
    BaseProviderConfig,
    GeminiProviderConfig,
    KimiProviderConfig,
    ModelProvider,
    AuthType,
    detect_provider_from_model,
    create_provider_config
)
from .content_generator import GeminiContentGenerator
from .kimi_generator import KimiContentGenerator
from .errors import ConfigurationError

logger = logging.getLogger(__name__)


class ContentGeneratorFactory:
    """Factory for creating content generators based on model and provider."""
    
    def __init__(self):
        self._generators: Dict[ModelProvider, Type[BaseContentGenerator]] = {
            ModelProvider.GEMINI: GeminiContentGenerator,
            ModelProvider.KIMI: KimiContentGenerator,
        }
    
    def register_provider(
        self,
        provider: ModelProvider,
        generator_class: Type[BaseContentGenerator]
    ) -> None:
        """Register a new provider and its generator class."""
        self._generators[provider] = generator_class
        logger.info(f"Registered provider {provider.value} with generator {generator_class.__name__}")
    
    def create_generator(
        self,
        model: str,
        provider: Optional[ModelProvider] = None,
        **kwargs
    ) -> BaseContentGenerator:
        """Create a content generator for the given model."""
        # Detect provider if not specified
        if provider is None:
            provider = detect_provider_from_model(model)
        
        # Get generator class
        if provider not in self._generators:
            raise ConfigurationError(f"No generator registered for provider {provider.value}")
        
        generator_class = self._generators[provider]
        
        # Create appropriate config
        config = self._create_config(model, provider, **kwargs)
        
        # Create and return generator
        logger.debug(f"Creating {provider.value} generator for model {model}")
        return generator_class(config)
    
    def _create_config(
        self,
        model: str,
        provider: ModelProvider,
        **kwargs
    ) -> BaseProviderConfig:
        """Create provider-specific configuration."""
        if provider == ModelProvider.GEMINI:
            return self._create_gemini_config(model, **kwargs)
        elif provider == ModelProvider.KIMI:
            return self._create_kimi_config(model, **kwargs)
        else:
            # Fallback to base config
            return create_provider_config(model, provider, **kwargs)
    
    def _create_gemini_config(self, model: str, **kwargs) -> GeminiProviderConfig:
        """Create Gemini-specific configuration."""
        # Set defaults for Gemini
        defaults = {
            "provider": ModelProvider.GEMINI,
            "auth_type": AuthType.API_KEY,
        }
        defaults.update(kwargs)
        
        return GeminiProviderConfig(
            model=model,
            **defaults
        )
    
    def _create_kimi_config(self, model: str, **kwargs) -> KimiProviderConfig:
        """Create Kimi-specific configuration."""
        # Set defaults for Kimi
        defaults = {
            "provider": ModelProvider.KIMI,
            "auth_type": AuthType.API_KEY,
            "kimi_provider": "moonshot",  # Default to official Moonshot API
        }
        defaults.update(kwargs)
        
        return KimiProviderConfig(
            model=model,
            **defaults
        )
    
    def get_supported_providers(self) -> List[ModelProvider]:
        """Get list of supported providers."""
        return list(self._generators.keys())
    
    def get_available_models(self, provider: Optional[ModelProvider] = None) -> List[str]:
        """Get available models for a provider or all providers."""
        models = []
        
        if provider:
            models.extend(self._get_provider_models(provider))
        else:
            for p in self._generators.keys():
                models.extend(self._get_provider_models(p))
        
        return sorted(models)
    
    def _get_provider_models(self, provider: ModelProvider) -> List[str]:
        """Get available models for a specific provider."""
        if provider == ModelProvider.GEMINI:
            # Import here to avoid circular imports
            from .content_generator import get_available_models
            return get_available_models()
        elif provider == ModelProvider.KIMI:
            from .kimi_generator import get_available_kimi_models
            return get_available_kimi_models()
        else:
            return []


# Global factory instance
_factory = ContentGeneratorFactory()


def create_content_generator(
    model: str,
    provider: Optional[ModelProvider] = None,
    **kwargs
) -> BaseContentGenerator:
    """Create a content generator for the given model."""
    return _factory.create_generator(model, provider, **kwargs)


def register_provider(
    provider: ModelProvider,
    generator_class: Type[BaseContentGenerator]
) -> None:
    """Register a new provider with the global factory."""
    _factory.register_provider(provider, generator_class)


def get_supported_providers() -> List[ModelProvider]:
    """Get list of supported providers."""
    return _factory.get_supported_providers()


def get_available_models(provider: Optional[ModelProvider] = None) -> List[str]:
    """Get available models for a provider or all providers."""
    return _factory.get_available_models(provider)


def is_model_supported(model: str) -> bool:
    """Check if a model is supported by any registered provider."""
    try:
        provider = detect_provider_from_model(model)
        # Check if the detected provider is actually supported
        supported_providers = _factory.get_supported_providers()
        return provider in supported_providers
    except Exception:
        return False


def get_model_provider(model: str) -> ModelProvider:
    """Get the provider for a given model."""
    return detect_provider_from_model(model)


def create_auto_config(
    model: str, 
    api_key: Optional[str] = None,
    **kwargs
) -> BaseProviderConfig:
    """Create a configuration automatically based on model name."""
    provider = detect_provider_from_model(model)
    return _factory._create_config(model, provider, api_key=api_key, **kwargs)


# Convenience functions for specific providers

def create_gemini_generator(
    model: str = "gemini-2.0-flash-exp",
    api_key: Optional[str] = None,
    **kwargs
) -> GeminiContentGenerator:
    """Create a Gemini content generator."""
    generator = create_content_generator(
        model=model, 
        provider=ModelProvider.GEMINI,
        api_key=api_key,
        **kwargs
    )
    return generator  # type: ignore


def create_kimi_generator(
    model: str = "kimi-k2-instruct",
    kimi_provider: str = "moonshot",
    api_key: Optional[str] = None,
    **kwargs
) -> KimiContentGenerator:
    """Create a Kimi content generator."""
    generator = create_content_generator(
        model=model,
        provider=ModelProvider.KIMI,
        kimi_provider=kimi_provider,
        api_key=api_key,
        **kwargs
    )
    return generator  # type: ignore