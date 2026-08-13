import asyncio
import pytest
from nats.aio.client import Client as NATS
import json
import psycopg2


DB_CONFIG = {
    "host": "localhost",
    "port": "5432",
    "database": "testdb",
    "user": "testuser",
    "password": "testpass",
}

# Пока запускаем тесты с хоста (из IDE/терминала), поэтому используем localhost
NATS_URL = "nats://localhost:4222"


@pytest.mark.asyncio
async def test_nats_pub_sub():
    """
    Проверяем базовый паттерн Pub/Sub (Издатель-Подписчик):
    1. Подписываемся на тему (subject) 'order.created'
    2. Публикуем сообщение в эту тему
    3. Проверяем, что подписчик его получил
    """
    # 1. Создаем клиент и подключаемся к NATS
    nc = NATS()
    await nc.connect(servers=[NATS_URL])

    received_messages = []

    # 2. Функция-обработчик (callback), которая сработает при получении сообщения
    async def message_handler(msg):
        # msg.data - это байты, декодируем их в строку
        received_messages.append(msg.data.decode())

    # 3. Подписываемся на тему 'order.created'
    sub = await nc.subscribe("order.created", cb=message_handler)

    # Небольшая пауза, чтобы брокер успел зарегистрировать подписку
    await asyncio.sleep(0.1)

    # 4. Публикуем сообщение (payload должен быть в байтах)
    payload = b'{"order_id": 123, "item": "Laptop", "status": "new"}'
    await nc.publish("order.created", payload)

    # Ждем, пока сообщение дойдет от брокера до нашего подписчика
    await asyncio.sleep(0.1)

    # 5. Отписываемся и закрываем соединение (cleanup)
    await sub.unsubscribe()
    await nc.close()

    # 6. Проверки (Asserts)
    assert len(received_messages) == 1, "Должно прийти ровно одно сообщение"

    received_data = received_messages[0]
    assert "order_id" in received_data
    assert "123" in received_data
    print(f"\n[NATS] Успешно получено сообщение: {received_data}")


@pytest.mark.asyncio
async def test_nats_queue_groups():
    """
    Проверяем Queue Groups: каждое сообщение должно быть обработано
    ровно ОДНИМ воркером из группы (load balancing).
    """
    nc = NATS()
    await nc.connect(servers=[NATS_URL])

    worker1_messages = []
    worker2_messages = []

    async def handler1(msg):
        worker1_messages.append(msg.data.decode())

    async def handler2(msg):
        worker2_messages.append(msg.data.decode())

    # Оба подписчика в ОДНОЙ queue group "workers"
    sub1 = await nc.subscribe("orders.new", queue="workers", cb=handler1)
    sub2 = await nc.subscribe("orders.new", queue="workers", cb=handler2)
    await asyncio.sleep(0.1)

    # Публикуем 4 сообщения
    for i in range(1, 5):
        await nc.publish("orders.new", f'{{"order_id": {i}}}'.encode())

    # Ждем доставки
    await asyncio.sleep(0.3)

    await sub1.unsubscribe()
    await sub2.unsubscribe()
    await nc.close()

    total = len(worker1_messages) + len(worker2_messages)

    # Каждое сообщение обработано ровно один раз (суммарно 4)
    assert total == 4, f"Ожидалось 4 обработки суммарно, получено: {total}"
    # И оба воркера поучаствовали (при 4 сообщениях почти наверняка)
    print(f"\n[NATS QUEUE] worker1 обработал: {len(worker1_messages)}, "
          f"worker2 обработал: {len(worker2_messages)}")


@pytest.mark.asyncio
async def test_async_order_processing_eventual_consistency():
    """
    Сквозной асинхронный сценарий:
    1. Создаем заказ со статусом 'pending' в PostgreSQL
    2. Запускаем consumer, который по событию обновляет статус в БД
    3. Producer публикует событие order.created
    4. Тест ПОЛЛИНГОМ с таймаутом дожидается статуса 'processed'
    """
    conn = psycopg2.connect(**DB_CONFIG)
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO orders (user_id, amount, status) "
            "VALUES (1, 500.00, 'pending') RETURNING id"
        )
        order_id = cur.fetchone()[0]
        conn.commit()

    # --- Consumer: получает событие и обновляет БД ---
    async def order_consumer(msg):
        data = json.loads(msg.data.decode())
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE orders SET status = 'processed' WHERE id = %s",
                (data["order_id"],),
            )
            conn.commit()

    nc = NATS()
    await nc.connect(servers=[NATS_URL])
    sub = await nc.subscribe("order.created", cb=order_consumer)
    await asyncio.sleep(0.1)

    # --- Producer: публикуем событие ---
    await nc.publish("order.created", json.dumps({"order_id": order_id}).encode())

    # --- Assert: polling с таймаутом (никаких фиксированных sleep!) ---
    async def wait_for_status(expected, timeout=5.0):
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        while loop.time() < deadline:
            with conn.cursor() as cur:
                cur.execute("SELECT status FROM orders WHERE id = %s", (order_id,))
                status = cur.fetchone()[0]
            if status == expected:
                return status
            await asyncio.sleep(0.2)
        raise TimeoutError(f"Не дождались статуса {expected} за {timeout} сек")

    try:
        status = await wait_for_status("processed")
        assert status == "processed"
        print(f"\n[ASYNC] Заказ {order_id} обработан consumer'ом через NATS")
    finally:
        # --- Cleanup ---
        await sub.unsubscribe()
        await nc.close()
        with conn.cursor() as cur:
            cur.execute("DELETE FROM orders WHERE id = %s", (order_id,))
            conn.commit()
        conn.close()