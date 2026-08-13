from locust import HttpUser, task, between

class ApiUser(HttpUser):
    # Пауза между запросами от 0.5 до 5 секунд
    wait_time = between(0.5, 5)

    @task(3)
    def list_users(self):
        """Самая частая операция - чтение списка."""
        self.client.get("/users", name="GET /users")

    @task(1)
    def get_user(self):
        """Чтение конкретного пользователя."""
        self.client.get("/users/1", name="GET /users/1")

    @task(1)
    def health_check(self):
        """Проверка здоровья сервиса."""
        self.client.get("/health", name="GET /health")