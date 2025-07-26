
import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient
import os
from unittest.mock import MagicMock, AsyncMock
from contextlib import asynccontextmanager

@pytest.fixture(scope="session", autouse=True)
def load_test_env():
    """Loads test environment variables for the entire session."""
    env_path = os.path.join(os.path.dirname(__file__), '..', '.env.test')
    if os.path.exists(env_path):
        load_dotenv(dotenv_path=env_path, override=True)

@pytest.fixture(scope="function")
def test_app_client(mocker):
    """
    Creates a TestClient for the FastAPI app with a completely mocked lifespan.
    This ensures total control over state-managed services for testing.
    """
    from app.main import app

    # Create mock instances for all services managed by the lifespan context
    mock_fed_analyzer = MagicMock()
    mock_fed_analyzer.analyze_content = AsyncMock()
    
    mock_social_analyzer = MagicMock()
    mock_social_analyzer.analyze_content = AsyncMock()

    mock_trade_manager = MagicMock()
    
    # Create a mock lifespan manager
    @asynccontextmanager
    async def mock_lifespan(app):
        # Populate app.state with our mocks
        app.state.fed_decision_analyzer = mock_fed_analyzer
        app.state.social_media_analyzer = mock_social_analyzer
        app.state.trade_decision_manager = mock_trade_manager
        app.state.processed_content_ids = set() # Ensure a clean set for each test
        yield
        # No shutdown logic needed for mocks

    # Override the app's lifespan with our mock version
    app.router.lifespan_context = mock_lifespan
    
    with TestClient(app) as client:
        yield client, {
            "fed_analyzer": mock_fed_analyzer,
            "social_analyzer": mock_social_analyzer,
            "trade_manager": mock_trade_manager
        }
    
    # Clean up by restoring the original lifespan
    from app.main import lifespan
    app.router.lifespan_context = lifespan
