import pytest
from pydantic import ValidationError
from app.config import Settings

def test_production_secret_key_validator():
    """Ensure that the default secret key cannot be used in production (debug=False)."""
    with pytest.raises(ValueError) as excinfo:
        # Trying to initialize Settings with debug=False and the default secret key
        Settings(debug=False, secret_key="ace-voice-controller-default-dev-secret-key-32x")
    
    assert "FATAL: Default secret_key detected in production" in str(excinfo.value)

def test_dev_secret_key_allowed():
    """Ensure the default secret key is allowed in dev mode (debug=True)."""
    # This should not raise an exception
    settings = Settings(debug=True, secret_key="ace-voice-controller-default-dev-secret-key-32x")
    assert settings.debug is True
    assert settings.secret_key == "ace-voice-controller-default-dev-secret-key-32x"

def test_custom_secret_key_allowed_in_prod():
    """Ensure a custom secret key works in production mode."""
    # This should not raise an exception
    settings = Settings(debug=False, secret_key="my-super-secret-production-key-12345")
    assert settings.debug is False
    assert settings.secret_key == "my-super-secret-production-key-12345"
