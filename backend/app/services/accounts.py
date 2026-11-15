from __future__ import annotations

import hashlib
import hmac
import secrets
import sqlite3
import time
import uuid
from contextlib import contextmanager

from fastapi import HTTPException

from app.services.user_context import storage_root


@contextmanager
def connection():
    root = storage_root()
    root.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(root / "accounts.sqlite3", timeout=15)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY, username TEXT UNIQUE NOT NULL, display_name TEXT NOT NULL,
            salt TEXT NOT NULL, password_hash TEXT NOT NULL, created_at REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS sessions (
            token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            expires_at REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS login_attempts (username TEXT PRIMARY KEY, count INTEGER, since REAL);
    """)
    try:
        yield db
        db.commit()
    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()


def password_hash(password: str, salt: str) -> str:
    return hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()


def public_user(row) -> dict:
    return {key: row[key] for key in ("id", "username", "display_name")}


def register(username: str, display_name: str, password: str) -> dict:
    salt = secrets.token_hex(16)
    hashed = password_hash(password, salt)
    with connection() as db:
        try:
            db.execute("INSERT INTO users VALUES (?, ?, ?, ?, ?, ?)",
                       (uuid.uuid4().hex, username.casefold(), display_name.strip(), salt, hashed, time.time()))
        except sqlite3.IntegrityError as exc:
            raise HTTPException(409, "That username is already registered on this computer.") from exc
    return login(username, password)


def login(username: str, password: str) -> dict:
    name = username.casefold()
    now = time.time()
    with connection() as db:
        attempt = db.execute("SELECT * FROM login_attempts WHERE username=?", (name,)).fetchone()
        if attempt and now - attempt["since"] < 300 and attempt["count"] >= 8:
            raise HTTPException(429, "Too many sign-in attempts. Try again in five minutes.")
        row = db.execute("SELECT * FROM users WHERE username=?", (name,)).fetchone()
        actual = password_hash(password, row["salt"] if row else "00" * 16)
        valid = row is not None and hmac.compare_digest(actual, row["password_hash"])
        if not valid:
            count = attempt["count"] + 1 if attempt and now - attempt["since"] < 300 else 1
            since = attempt["since"] if count > 1 else now
            db.execute("INSERT OR REPLACE INTO login_attempts VALUES (?, ?, ?)", (name, count, since))
        else:
            db.execute("DELETE FROM login_attempts WHERE username=?", (name,))
            db.execute("DELETE FROM sessions WHERE expires_at < ?", (now,))
            token = secrets.token_urlsafe(48)
            db.execute("INSERT INTO sessions VALUES (?, ?, ?)",
                       (hashlib.sha256(token.encode()).hexdigest(), row["id"], now + 12 * 3600))
            result = {"token": token, "user": public_user(row)}
    if not valid:
        raise HTTPException(401, "Username or password is incorrect.")
    return result


def authenticate(token: str) -> dict | None:
    if not token:
        return None
    with connection() as db:
        row = db.execute("""SELECT u.* FROM users u JOIN sessions s ON u.id=s.user_id
                            WHERE s.token_hash=? AND s.expires_at>?""",
                         (hashlib.sha256(token.encode()).hexdigest(), time.time())).fetchone()
    return public_user(row) if row else None


def logout(token: str) -> None:
    with connection() as db:
        db.execute("DELETE FROM sessions WHERE token_hash=?", (hashlib.sha256(token.encode()).hexdigest(),))
