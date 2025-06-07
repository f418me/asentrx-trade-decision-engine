# tests/conftest.py

import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient
import os

@pytest.fixture(scope="session", autouse=True)
def load_test_env():
    """
    This fixture is automatically executed for the entire test session.
    It loads the .env.test file before the app is imported, ensuring
    test-specific environment variables are used.
    """
    # Load test environment variables. `override=True` is crucial
    # in case any other .env files were loaded previously.
    env_path = os.path.join(os.path.dirname(__file__), '..', '.env.test')
    if os.path.exists(env_path):
        load_dotenv(dotenv_path=env_path, override=True)
    else:
        print(f"Warning: Test environment file not found at {env_path}. Using system environment variables.")


@pytest.fixture(scope="module")
def test_app_client():
    """
    Creates a TestClient for the FastAPI app.
    The `scope="module"` means the client is created only once per test file.
    """
    # Import the app only AFTER the test environment variables have been loaded.
    from app.main import app
    with TestClient(app) as client:
        yield client