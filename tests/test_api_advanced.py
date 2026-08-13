import pytest
import requests

BASE_URL = "http://host.docker.internal:8000"

# --- PARAMETRIZATION ---

@pytest.mark.parametrize("user_id, expected_status", [
    (1, 200),  # Существующий
    (2, 200),  # Существующий
    (3, 200),  # Существующий
    (999, 404), # Несуществующий
])
def test_get_users_parametrized(user_id, expected_status):
    """Один тест проверяет сразу несколько сценариев."""
    response = requests.get(f"{BASE_URL}/users/{user_id}")
    assert response.status_code == expected_status


@pytest.mark.parametrize("payload, expected_status", [
    # Негативные сценарии (422 от Pydantic)
    ({"email": "a@a.com"}, 422), # Нет name
    ({"name": "Test"}, 422),    # Нет email
    ({"email": 123, "name": "Test"}, 422), # email не строка
    ({"email": "a@a.com", "name": 123}, 422), # name не строка
])
def test_create_user_invalid_payloads_parametrized(payload, expected_status):
    """Проверяем различные варианты невалидного тела запроса."""
    response = requests.post(f"{BASE_URL}/users", json=payload)
    assert response.status_code == expected_status


# --- FIXTURES SCOPES ---

@pytest.fixture(scope="session")
def session_client():
    """
    Фикстура уровня сессии.
    Создается ОДИН раз за весь прогон тестов.
    """
    print("\n[SESSION FIXTURE] Creating requests session...")
    session = requests.Session()
    yield session
    print("\n[SESSION FIXTURE] Closing requests session...")
    session.close()

@pytest.fixture(scope="function")
def function_client():
    """
    Фикстура уровня функции (по умолчанию).
    Создается ПЕРЕД КАЖДЫМ тестом.
    """
    print("\n[FUNCTION FIXTURE] Creating new session for test...")
    session = requests.Session()
    yield session
    session.close()

def test_scope_session_1(session_client):
    assert session_client is not None

def test_scope_session_2(session_client):
    assert session_client is not None

def test_scope_function_1(function_client):
    assert function_client is not None

def test_scope_function_2(function_client):
    assert function_client is not None