import pytest
import requests

BASE_URL = "http://host.docker.internal:8000"


@pytest.fixture
def api_client():
    """Фикстура для работы с API."""
    session = requests.Session()
    # Можно добавить общие заголовки, например авторизацию
    # session.headers.update({"Authorization": "Bearer token"})
    yield session
    session.close()


# --- Health check ---

def test_health_check(api_client):
    """Проверяем, что сервис жив."""
    response = api_client.get(f"{BASE_URL}/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# --- GET /users ---

def test_list_users(api_client):
    """Получаем список всех пользователей."""
    response = api_client.get(f"{BASE_URL}/users")
    assert response.status_code == 200

    users = response.json()
    assert isinstance(users, list)
    assert len(users) == 3  # У нас 3 пользователя из пункта 1

    # Проверяем структуру первого пользователя
    first_user = users[0]
    assert "id" in first_user
    assert "email" in first_user
    assert "name" in first_user


def test_get_user_by_id(api_client):
    """Получаем конкретного пользователя по ID."""
    response = api_client.get(f"{BASE_URL}/users/1")
    assert response.status_code == 200

    user = response.json()
    assert user["id"] == 1
    assert user["email"] == "john@example.com"
    assert user["name"] == "John Doe"


def test_get_user_not_found(api_client):
    """Пытаемся получить несуществующего пользователя — 404."""
    response = api_client.get(f"{BASE_URL}/users/99999")
    assert response.status_code == 404
    assert "User not found" in response.text


# --- POST /users ---

def test_create_user_success(api_client):
    """Создаём нового пользователя — 201 Created."""
    payload = {
        "email": "newuser@example.com",
        "name": "New User",
        "phone": "+1111111111"
    }
    response = api_client.post(f"{BASE_URL}/users", json=payload)

    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["email"] == "newuser@example.com"
    assert data["name"] == "New User"

    # Проверяем, что пользователь реально создан в БД
    user_id = data["id"]
    get_response = api_client.get(f"{BASE_URL}/users/{user_id}")
    assert get_response.status_code == 200

    # Очищаем после теста (DELETE)
    delete_response = api_client.delete(f"{BASE_URL}/users/{user_id}")
    assert delete_response.status_code == 204


def test_create_user_duplicate_email(api_client):
    """Пытаемся создать пользователя с существующим email — 409 Conflict."""
    payload = {
        "email": "john@example.com",  # Уже существует
        "name": "Duplicate John"
    }
    response = api_client.post(f"{BASE_URL}/users", json=payload)
    assert response.status_code == 409
    assert "Email already exists" in response.text


def test_create_user_invalid_payload(api_client):
    """Отправляем кривое тело запроса — 422 Unprocessable Entity."""
    # Нет обязательного поля name
    payload = {"email": "test@example.com"}
    response = api_client.post(f"{BASE_URL}/users", json=payload)
    assert response.status_code == 422


def test_create_user_invalid_email(api_client):
    """Email должен быть строкой, отправляем число — 422."""
    payload = {
        "email": 12345,  # Должна быть строка
        "name": "Test"
    }
    response = api_client.post(f"{BASE_URL}/users", json=payload)
    assert response.status_code == 422


# --- PATCH /users/{id} ---

def test_update_user_success(api_client):
    """Обновляем имя пользователя — 200 OK."""
    payload = {"name": "Updated Name"}
    response = api_client.patch(f"{BASE_URL}/users/1", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 1
    assert data["name"] == "Updated Name"

    # Проверяем, что изменение сохранилось
    get_response = api_client.get(f"{BASE_URL}/users/1")
    assert get_response.json()["name"] == "Updated Name"

    # Откатываем изменение (восстанавливаем оригинальное имя)
    api_client.patch(f"{BASE_URL}/users/1", json={"name": "John Doe"})


def test_update_user_empty_payload(api_client):
    """Отправляем пустое тело — 400 Bad Request."""
    payload = {}
    response = api_client.patch(f"{BASE_URL}/users/1", json=payload)
    assert response.status_code == 400
    assert "Nothing to update" in response.text


def test_update_user_not_found(api_client):
    """Пытаемся обновить несуществующего — 404."""
    payload = {"name": "Ghost"}
    response = api_client.patch(f"{BASE_URL}/users/99999", json=payload)
    assert response.status_code == 404


# --- DELETE /users/{id} ---

def test_delete_user_success(api_client):
    """Удаляем пользователя — 204 No Content."""
    # Сначала создаём пользователя
    create_payload = {
        "email": "todelete@example.com",
        "name": "To Delete"
    }
    create_response = api_client.post(f"{BASE_URL}/users", json=create_payload)
    user_id = create_response.json()["id"]

    # Удаляем
    delete_response = api_client.delete(f"{BASE_URL}/users/{user_id}")
    assert delete_response.status_code == 204
    assert delete_response.text == ""  # No Content

    # Проверяем, что пользователь удалён
    get_response = api_client.get(f"{BASE_URL}/users/{user_id}")
    assert get_response.status_code == 404


def test_delete_user_not_found(api_client):
    """Пытаемся удалить несуществующего — 404."""
    response = api_client.delete(f"{BASE_URL}/users/99999")
    assert response.status_code == 404


def test_delete_user_idempotent(api_client):
    """
    Проверяем идемпотентность DELETE: повторный вызов должен вернуть 404,
    а не ошибку или 200.
    """
    # Создаём пользователя
    create_payload = {
        "email": "idempotent@example.com",
        "name": "Idempotent"
    }
    create_response = api_client.post(f"{BASE_URL}/users", json=create_payload)
    user_id = create_response.json()["id"]

    # Удаляем первый раз — 204
    response1 = api_client.delete(f"{BASE_URL}/users/{user_id}")
    assert response1.status_code == 204

    # Удаляем второй раз — 404 (уже удалён)
    response2 = api_client.delete(f"{BASE_URL}/users/{user_id}")
    assert response2.status_code == 404