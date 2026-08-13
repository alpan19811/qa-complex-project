import time
import pytest
import redis

REDIS_URL = "redis://localhost:6379/0"


@pytest.fixture
def redis_client():
    """Фикстура: подключение к Redis + очистка тестовых ключей после теста."""
    client = redis.from_url(REDIS_URL, decode_responses=True)
    yield client
    # Удаляем все ключи, начинающиеся с 'test:'
    for key in client.scan_iter(match="test:*"):
        client.delete(key)
    client.close()


# --- ТЕСТ 1: Базовые операции (SET/GET/TTL/DEL) ---

def test_redis_basic_operations(redis_client):
    """Проверяем основные операции с key-value и TTL."""
    r = redis_client

    # SET с TTL
    r.set("test:user:1", "John Doe", ex=60)

    # GET
    value = r.get("test:user:1")
    assert value == "John Doe"

    # TTL (сколько осталось жить ключу)
    ttl = r.ttl("test:user:1")
    assert 58 <= ttl <= 60, f"TTL должен быть около 60, получили {ttl}"

    # EXPIRE (изменить TTL)
    r.expire("test:user:1", 30)
    assert 28 <= r.ttl("test:user:1") <= 30

    # EXISTS (существует ли ключ)
    assert r.exists("test:user:1") == 1
    assert r.exists("test:nonexistent") == 0

    # DEL (удаление)
    r.delete("test:user:1")
    assert r.get("test:user:1") is None

    print("\n[REDIS] Базовые операции (SET/GET/TTL/DEL/EXISTS/EXPIRE) OK")


# --- ТЕСТ 2: Hash (структура для объектов) ---

def test_redis_hash(redis_client):
    """Hash — ключ-объект с полями, как dict в Python."""
    r = redis_client

    # HSET (установка полей)
    r.hset("test:user:2", mapping={
        "name": "Jane Smith",
        "email": "jane@example.com",
        "age": 28
    })

    # HGET (чтение одного поля)
    assert r.hget("test:user:2", "name") == "Jane Smith"

    # HGETALL (все поля)
    user = r.hgetall("test:user:2")
    assert user["email"] == "jane@example.com"
    assert int(user["age"]) == 28

    # HDEL (удаление поля)
    r.hdel("test:user:2", "age")
    assert r.hexists("test:user:2", "age") == 0

    print("\n[REDIS] Hash операции (HSET/HGET/HGETALL/HDEL) OK")


# --- ТЕСТ 3: Cache-Aside паттерн (имитация кэширования API) ---

def test_cache_aside_pattern(redis_client):
    """
    Классический сценарий кэширования:
    1. Первый запрос → MISS → данные из БД → сохранение в Redis с TTL
    2. Второй запрос → HIT → данные из Redis (БД не трогаем)
    3. UPDATE данных → инвалидация кэша (DEL)
    4. Третий запрос → MISS → снова читаем из БД
    """
    r = redis_client
    cache_key = "test:api:users:42"

    # Мок "БД"
    class FakeDB:
        def __init__(self):
            self.reads = 0

        def get_user(self, user_id):
            self.reads += 1
            return {"id": user_id, "name": "User from DB", "version": 1}

        def update_user(self, user_id):
            return {"id": user_id, "name": "Updated User", "version": 2}

    db = FakeDB()

    # --- Функция с кэшированием  ---
    def get_user_with_cache(user_id):
        # 1. Пробуем прочитать из кэша
        cached = r.get(cache_key)
        if cached:
            import json
            return json.loads(cached), "HIT"

        # 2. MISS: читаем из БД
        user = db.get_user(user_id)

        # 3. Сохраняем в кэш с TTL
        import json
        r.set(cache_key, json.dumps(user), ex=300)
        return user, "MISS"

    # --- Тестирование паттерна ---

    # Первый запрос → MISS
    user1, cache_status1 = get_user_with_cache(42)
    assert cache_status1 == "MISS"
    assert user1["version"] == 1
    assert db.reads == 1  # Одно чтение из БД

    # Проверяем, что ключ появился в Redis
    assert r.exists(cache_key) == 1

    # Второй запрос → HIT (из кэша)
    user2, cache_status2 = get_user_with_cache(42)
    assert cache_status2 == "HIT"
    assert db.reads == 1  # Чтений из БД НЕ прибавилось!

    # Имитация UPDATE данных
    db.update_user(42)

    # --- ИНВАЛИДАЦИЯ КЭША --- (это критичный момент!)
    r.delete(cache_key)

    # Третий запрос после UPDATE → снова MISS
    user3, cache_status3 = get_user_with_cache(42)
    assert cache_status3 == "MISS"
    # Здесь в реальном приложении мы бы уже читали обновлённые данные
    assert db.reads == 2  # Второе чтение из БД

    print("\n[REDIS] Cache-Aside: MISS → HIT → INVALIDATION → MISS OK")
    print(f"[REDIS] Всего чтений из БД: {db.reads} (без кэша было бы 3)")


# --- ТЕСТ 4: TTL и истечение ключа (stale data protection) ---

def test_redis_ttl_expiration(redis_client):
    """Проверяем, что ключ корректно удаляется после истечения TTL."""
    r = redis_client

    # Очень короткий TTL для теста
    r.set("test:temp", "value", ex=1)
    assert r.get("test:temp") == "value"

    # Ждём истечения TTL
    time.sleep(1.5)

    # Ключ должен исчезнуть
    assert r.get("test:temp") is None
    assert r.exists("test:temp") == 0

    print("\n[REDIS] TTL expiration OK")