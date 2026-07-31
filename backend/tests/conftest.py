import pytest
from fastapi.testclient import TestClient

from alphapilot.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)
