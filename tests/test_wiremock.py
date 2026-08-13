import time
import requests
import pytest

WIREMOCK_URL = "http://host.docker.internal:8080"


def test_sms_send_success():
    """Проверяем успешную отправку SMS через мок."""
    response = requests.post(f"{WIREMOCK_URL}/api/sms/send", json={"phone": "+79990000000"})

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "sent"
    assert "message_id" in data


def test_payment_gateway_unavailable():
    """
    Проверяем сценарий, когда внешний платежный шлюз недоступен (502 Bad Gateway).
    Также проверяем, что мок симулирует сетевую задержку (latency).
    """
    start_time = time.time()

    # Ходим в мок, который должен вернуть 502 и задержаться на 1.5 секунды
    response = requests.post(
        f"{WIREMOCK_URL}/api/payment/process",
        json={"amount": 100, "currency": "RUB"}
    )
    duration = time.time() - start_time

    # 1. Проверяем статус и тело ответа
    assert response.status_code == 502
    data = response.json()
    assert data["error"] == "Bad Gateway"

    # 2. Проверяем симуляцию задержки (должно занять >= 1.5 секунды)
    assert duration >= 1.5, f"Ожидалась задержка >= 1.5с, но прошло {duration:.2f}с"
    print(f"\n[MOCK DELAY] Запрос занял {duration:.2f} секунд (симуляция медленного API)")