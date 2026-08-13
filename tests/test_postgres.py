import pytest
import psycopg2

DB_CONFIG = {
    "host": "host.docker.internal",
    "port": "5432",
    "database": "testdb",
    "user": "testuser",
    "password": "testpass"
}


@pytest.fixture
def db_connection():
    """Старая фикстура для тестов, которые только читают (SELECT)."""
    conn = psycopg2.connect(**DB_CONFIG)
    yield conn
    conn.close()


@pytest.fixture
def db_connection_with_rollback():
    """
    Новая фикстура для тестов, которые меняют данные (INSERT/UPDATE/DELETE).
    После теста делает ROLLBACK, чтобы база оставалась чистой.
    """
    conn = psycopg2.connect(**DB_CONFIG)
    # Отключаем автокоммит, чтобы управлять транзакциями вручную
    conn.autocommit = False

    yield conn

    # Откатываем все изменения, которые сделал тест
    conn.rollback()
    conn.close()


# --- СТАРЫЕ ТЕСТЫ ---

def test_users_count(db_connection):
    with db_connection.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM users;")
        count = cur.fetchone()[0]
    assert count == 3


def test_john_orders(db_connection):
    with db_connection.cursor() as cur:
        cur.execute("SELECT SUM(amount) FROM orders WHERE user_id = 1;")
        total_amount = cur.fetchone()[0]
    assert float(total_amount) == 1059.97


# --- НОВЫЕ ТЕСТЫ НА ТРАНЗАКЦИИ ---

def test_create_user_rollback(db_connection_with_rollback):
    """
    Создаем пользователя, проверяем, что он есть в базе.
    Но после завершения этого теста фикстура сделает ROLLBACK.
    """
    conn = db_connection_with_rollback
    with conn.cursor() as cur:
        # 1. Вставляем нового пользователя
        cur.execute("""
            INSERT INTO users (email, name, phone) 
            VALUES ('rollback_test@example.com', 'Rollback User', '+0000000000')
        """)

        # 2. Проверяем, что он появился (в рамках текущей транзакции он есть)
        cur.execute("SELECT COUNT(*) FROM users WHERE email = 'rollback_test@example.com';")
        count = cur.fetchone()[0]
        assert count == 1, "Пользователь должен существовать в рамках транзакции"


def test_user_still_gone_after_rollback(db_connection_with_rollback):
    """
    Проверяем, что предыдущий тест НЕ оставил мусора в базе!
    Этот тест использует новую транзакцию.
    """
    conn = db_connection_with_rollback
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM users WHERE email = 'rollback_test@example.com';")
        count = cur.fetchone()[0]
        assert count == 0, "Пользователь должен был исчезнуть после отката транзакции!"