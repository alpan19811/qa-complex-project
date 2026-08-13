import logging
import uuid
from contextlib import contextmanager

import psycopg2
import psycopg2.extras
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel

# ---------- Логирование ----------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("users_api")

# ---------- БД ----------
DB_CONFIG = {
    "host": "localhost",
    "port": "5432",
    "database": "testdb",
    "user": "testuser",
    "password": "testpass",
}


@contextmanager
def db_cursor(dict_cursor=False):
    """Соединение + курсор: commit при успехе, rollback при ошибке."""
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        if dict_cursor:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        else:
            cur = conn.cursor()
        yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


app = FastAPI(title="Users API", version="1.0")


# ---------- Middleware: request_id + логи ----------
@app.middleware("http")
async def log_requests(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    logger.info("request_id=%s %s %s started",
                request_id, request.method, request.url.path)
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("request_id=%s %s %s failed",
                         request_id, request.method, request.url.path)
        raise
    logger.info("request_id=%s %s %s finished status=%s",
                request_id, request.method, request.url.path, response.status_code)
    response.headers["X-Request-ID"] = request_id
    return response


# ---------- Pydantic-модели (валидация запросов) ----------
class UserCreate(BaseModel):
    email: str
    name: str
    phone: str | None = None


class UserUpdate(BaseModel):
    name: str | None = None
    phone: str | None = None


# ---------- Эндпоинты ----------
@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/users")
def list_users():
    with db_cursor(dict_cursor=True) as cur:
        cur.execute("SELECT id, email, name, phone FROM users ORDER BY id")
        return cur.fetchall()


@app.get("/users/{user_id}")
def get_user(user_id: int):
    with db_cursor(dict_cursor=True) as cur:
        cur.execute("SELECT id, email, name, phone FROM users WHERE id = %s", (user_id,))
        row = cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="User not found")
    return row


@app.post("/users", status_code=201)
def create_user(user: UserCreate):
    with db_cursor() as cur:
        try:
            cur.execute(
                "INSERT INTO users (email, name, phone) VALUES (%s, %s, %s) RETURNING id",
                (user.email, user.name, user.phone),
            )
            new_id = cur.fetchone()[0]
        except psycopg2.errors.UniqueViolation:
            raise HTTPException(status_code=409, detail="Email already exists")
    return {"id": new_id, "email": user.email, "name": user.name}


@app.patch("/users/{user_id}")
def update_user(user_id: int, payload: UserUpdate):
    fields = {}
    if payload.name is not None:
        fields["name"] = payload.name
    if payload.phone is not None:
        fields["phone"] = payload.phone
    if not fields:
        raise HTTPException(status_code=400, detail="Nothing to update")

    set_clause = ", ".join(f"{key} = %s" for key in fields)
    values = list(fields.values()) + [user_id]

    with db_cursor() as cur:
        cur.execute(f"UPDATE users SET {set_clause} WHERE id = %s", values)
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="User not found")
    return {"id": user_id, **fields}


@app.delete("/users/{user_id}", status_code=204)
def delete_user(user_id: int):
    with db_cursor() as cur:
        cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="User not found")
