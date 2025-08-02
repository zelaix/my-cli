"""
Integration tests for Kimi K2 model support.

This module tests the new multi-provider architecture with Kimi K2 models.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from my_cli.core.client.provider_factory import (
    create_content_generator,
    get_supported_providers,
    is_model_supported,
    get_model_provider
)
from my_cli.core.client.providers import ModelProvider, AuthType
from my_cli.core.client.kimi_generator import KimiContentGenerator
from my_cli.core.client.content_generator import GeminiContentGenerator
from my_cli.config.settings import MyCliSettings


class TestMultiProviderSystem:
    """Test the multi-provider architecture."""
    
    def test_provider_detection(self):
        """Test provider detection from model names."""
        assert get_model_provider("kimi-k2-instruct") == ModelProvider.KIMI
        assert get_model_provider("gemini-2.0-flash-exp") == ModelProvider.GEMINI
        assert get_model_provider("gpt-4") == ModelProvider.OPENAI
        assert get_model_provider("claude-3") == ModelProvider.ANTHROPIC
    
    def test_supported_providers(self):
        """Test getting supported providers."""
        providers = get_supported_providers()
        assert ModelProvider.GEMINI in providers
        assert ModelProvider.KIMI in providers
    
    def test_model_support_check(self):
        """Test checking if models are supported."""
        assert is_model_supported("kimi-k2-instruct") is True
        assert is_model_supported("gemini-2.0-flash-exp") is True
        assert is_model_supported("unknown-model") is False
    
    def test_generator_creation(self):
        """Test creating generators for different providers."""
        # Test Kimi generator creation
        kimi_gen = create_content_generator("kimi-k2-instruct")
        assert isinstance(kimi_gen, KimiContentGenerator)
        assert kimi_gen.provider == ModelProvider.KIMI
        assert kimi_gen.model == "kimi-k2-instruct"
        
        # Test Gemini generator creation
        gemini_gen = create_content_generator("gemini-2.0-flash-exp")
        assert isinstance(gemini_gen, GeminiContentGenerator)
        assert gemini_gen.provider == ModelProvider.GEMINI
        assert gemini_gen.model == "gemini-2.0-flash-exp"


class TestKimiConfiguration:
    """Test Kimi-specific configuration."""
    
    def test_kimi_settings_validation(self):
        """Test Kimi settings validation."""
        # Valid settings
        settings = MyCliSettings(
            model="kimi-k2-instruct",
            kimi_api_key="test-key",
            kimi_provider="moonshot"
        )
        assert settings.model == "kimi-k2-instruct"
        assert settings.kimi_provider == "moonshot"
        
        # Invalid provider
        with pytest.raises(ValueError):
            MyCliSettings(kimi_provider="invalid-provider")
    
    def test_api_key_selection(self):
        """Test API key selection based on model."""
        settings = MyCliSettings(
            api_key="gemini-key",
            kimi_api_key="kimi-key"
        )
        
        # Should return Gemini key for Gemini models
        assert settings.get_api_key_for_model("gemini-2.0-flash-exp") == "gemini-key"
        
        # Should return Kimi key for Kimi models
        assert settings.get_api_key_for_model("kimi-k2-instruct") == "kimi-key"
    
    def test_is_configured_for_kimi(self):
        """Test configuration check for Kimi models."""
        # Not configured for Kimi
        settings = MyCliSettings(model="kimi-k2-instruct")
        assert not settings.is_configured
        
        # Configured for Kimi
        settings_configured = MyCliSettings(
            model="kimi-k2-instruct",
            kimi_api_key="test-key"
        )
        assert settings_configured.is_configured


class TestKimiGenerator:
    """Test Kimi K2 generator functionality."""
    
    def test_kimi_generator_initialization(self):
        """Test Kimi generator initialization."""
        generator = create_content_generator(
            "kimi-k2-instruct",
            kimi_provider="moonshot",
            api_key="test-key"
        )
        
        assert generator.model == "kimi-k2-instruct"
        assert generator.provider == ModelProvider.KIMI
        assert generator.supports_streaming() is True
        assert generator.get_context_limit() == 128000
        assert generator.config.kimi_provider == "moonshot"
        assert generator.config.base_url == "https://api.moonshot.cn/v1"
    
    def test_different_kimi_providers(self):
        """Test different Kimi API providers."""
        providers_and_urls = {
            "moonshot": "https://api.moonshot.cn/v1",
            "deepinfra": "https://api.deepinfra.com/v1/openai",
            "together": "https://api.together.xyz/v1",
            "fireworks": "https://api.fireworks.ai/inference/v1",
            "groq": "https://api.groq.com/openai/v1",
            "openrouter": "https://openrouter.ai/api/v1"
        }
        
        for provider, expected_url in providers_and_urls.items():
            generator = create_content_generator(
                "kimi-k2-instruct",
                kimi_provider=provider,
                api_key="test-key"
            )
            assert generator.config.base_url == expected_url
    
    @pytest.mark.asyncio
    async def test_kimi_generator_methods(self):
        """Test Kimi generator method signatures."""
        generator = create_content_generator(
            "kimi-k2-instruct",
            kimi_provider="moonshot",
            api_key="test-key"
        )
        
        # Test that required methods exist
        assert hasattr(generator, 'initialize')
        assert hasattr(generator, 'generate_content')
        assert hasattr(generator, 'generate_content_stream')
        assert hasattr(generator, 'count_tokens')
        
        # Mock a simple message for token counting
        from my_cli.core.client.turn import Message, MessageRole, MessagePart
        messages = [Message(
            role=MessageRole.USER,
            parts=[MessagePart(text="Hello world")]
        )]
        
        # Test token counting (should not require API call)
        token_count = await generator.count_tokens(messages)
        assert isinstance(token_count, int)
        assert token_count > 0


@pytest.mark.integration
class TestEndToEndIntegration:
    """End-to-end integration tests."""
    
    def test_configuration_to_generator_flow(self):
        """Test the complete flow from configuration to generator."""
        # Create settings
        settings = MyCliSettings(
            model="kimi-k2-instruct",
            kimi_api_key="test-key",
            kimi_provider="deepinfra"
        )
        
        # Create generator using settings
        generator = create_content_generator(
            settings.model,
            api_key=settings.get_api_key_for_model(settings.model),
            kimi_provider=settings.kimi_provider
        )
        
        # Verify configuration flowed through correctly
        assert generator.model == "kimi-k2-instruct"
        assert generator.config.api_key == "test-key"
        assert generator.config.kimi_provider == "deepinfra"
        assert generator.config.base_url == "https://api.deepinfra.com/v1/openai"
    
    def test_backward_compatibility(self):
        """Test that old code still works with new system."""
        from my_cli.core.client import ContentGeneratorConfig
        
        # Old-style config creation should still work
        config = ContentGeneratorConfig(
            model="gemini-2.0-flash-exp",
            provider=ModelProvider.GEMINI,
            auth_type=AuthType.API_KEY,
            api_key="test-key"
        )
        
        # Should be the same as GeminiProviderConfig
        assert config.model == "gemini-2.0-flash-exp"
        assert config.provider == ModelProvider.GEMINI


if __name__ == "__main__":
    # Run basic tests
    import asyncio
    
    print("🧪 Testing Kimi K2 Integration...")
    
    # Test provider detection
    test_system = TestMultiProviderSystem()
    test_system.test_provider_detection()
    test_system.test_supported_providers()
    test_system.test_model_support_check()
    test_system.test_generator_creation()
    print("✅ Multi-provider system tests passed")
    
    # Test configuration
    test_config = TestKimiConfiguration()
    test_config.test_api_key_selection()
    print("✅ Kimi configuration tests passed")
    
    # Test generator
    test_generator = TestKimiGenerator()
    test_generator.test_kimi_generator_initialization()
    test_generator.test_different_kimi_providers()
    print("✅ Kimi generator tests passed")
    
    # Test async methods
    async def test_async():
        await test_generator.test_kimi_generator_methods()
        print("✅ Async generator tests passed")
    
    asyncio.run(test_async())
    
    # Test integration
    test_integration = TestEndToEndIntegration()
    test_integration.test_configuration_to_generator_flow()
    test_integration.test_backward_compatibility()
    print("✅ End-to-end integration tests passed")
    
    print("\n🎉 All Kimi K2 integration tests passed!")
    print("🌙 Kimi K2 support successfully added to My CLI")