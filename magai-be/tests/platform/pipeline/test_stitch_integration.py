from unittest.mock import patch

from app.platform.config.settings import settings
from app.platform.pipeline.engine import _make_agent


def test_stitch_api_key_settings_loaded():
    """Verify that MAGAI_STITCH_API_KEY from environment is loaded into settings."""
    assert hasattr(settings, "stitch_api_key")


def test_make_agent_uses_stitch_api_key_when_allow_tools_is_true():
    """Verify that _make_agent uses stitch_api_key when allow_tools=True."""
    with (
        patch.object(settings, "stitch_api_key", "test-stitch-key-12345"),
        patch.object(settings, "gemini_api_key", "test-gemini-key-67890"),
        patch("app.platform.pipeline.engine.LocalAgentConfig") as mock_config,
        patch("app.platform.pipeline.engine.Agent"),
    ):
        _make_agent("test instructions", allow_tools=True)

        assert mock_config.called
        _, kwargs = mock_config.call_args
        assert kwargs["api_key"] == "test-stitch-key-12345"


def test_make_agent_uses_gemini_api_key_when_allow_tools_is_false():
    """Verify that _make_agent uses gemini_api_key when allow_tools=False."""
    with (
        patch.object(settings, "stitch_api_key", "test-stitch-key-12345"),
        patch.object(settings, "gemini_api_key", "test-gemini-key-67890"),
        patch("app.platform.pipeline.engine.LocalAgentConfig") as mock_config,
        patch("app.platform.pipeline.engine.Agent"),
    ):
        _make_agent("test instructions", allow_tools=False)

        assert mock_config.called
        _, kwargs = mock_config.call_args
        assert kwargs["api_key"] == "test-gemini-key-67890"
