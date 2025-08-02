"""Tests for configuration settings."""

import pytest
from pydantic import ValidationError

from my_cli.config.settings import MyCliSettings


class TestMyCliSettings:
    """Test cases for MyCliSettings."""
    
    def test_default_values(self) -> None:
        """Test that default values are set correctly."""
        settings = MyCliSettings()
        
        assert settings.model == "gemini-2.0-flash-exp"
        assert settings.theme == "default"
        assert settings.auto_confirm is False
        assert settings.max_tokens == 8192
        assert settings.temperature == 0.7
        assert settings.timeout == 30
        assert "read_file" in settings.allowed_tools
    
    def test_api_key_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test API key loading from environment variable."""
        monkeypatch.setenv("MY_CLI_API_KEY", "test-key-123")
        settings = MyCliSettings()
        assert settings.api_key == "test-key-123"
    
    def test_invalid_theme(self) -> None:
        """Test validation of invalid theme."""
        with pytest.raises(ValidationError):
            MyCliSettings(theme="invalid-theme")
    
    def test_valid_theme(self) -> None:
        """Test validation of valid themes."""
        valid_themes = ["default", "dracula", "github", "ansi"]
        for theme in valid_themes:
            settings = MyCliSettings(theme=theme)
            assert settings.theme == theme
    
    def test_invalid_log_level(self) -> None:
        """Test validation of invalid log level."""
        with pytest.raises(ValidationError):
            MyCliSettings(log_level="INVALID")
    
    def test_valid_log_level(self) -> None:
        """Test validation of valid log levels."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        for level in valid_levels:
            settings = MyCliSettings(log_level=level)
            assert settings.log_level == level
    
    def test_temperature_validation(self) -> None:
        """Test temperature validation."""
        # Valid temperatures
        MyCliSettings(temperature=0.0)
        MyCliSettings(temperature=0.5)
        MyCliSettings(temperature=1.0)
        
        # Invalid temperatures
        with pytest.raises(ValidationError):
            MyCliSettings(temperature=-0.1)
        with pytest.raises(ValidationError):
            MyCliSettings(temperature=1.1)
    
    def test_max_tokens_validation(self) -> None:
        """Test max_tokens validation."""
        # Valid values
        MyCliSettings(max_tokens=1)
        MyCliSettings(max_tokens=32768)
        
        # Invalid values
        with pytest.raises(ValidationError):
            MyCliSettings(max_tokens=0)
        with pytest.raises(ValidationError):
            MyCliSettings(max_tokens=32769)
    
    def test_is_configured(self) -> None:
        """Test is_configured property."""
        settings = MyCliSettings()
        assert not settings.is_configured
        
        settings = MyCliSettings(api_key="test-key")
        assert settings.is_configured
    
    def test_to_dict_masks_api_key(self) -> None:
        """Test that to_dict masks sensitive data."""
        settings = MyCliSettings(api_key="secret-key-123")
        data = settings.to_dict()
        assert data["api_key"] == "***masked***"