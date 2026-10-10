"""Anonymous, signed visitor sessions for the bounded public demo."""

import hashlib
import hmac
import os
import secrets
import time
from collections import OrderedDict, deque
from contextvars import ContextVar
from pathlib import Path
from threading import Lock

from fastapi.responses import JSONResponse

from .db import Database
from .documents import seed


class VisitorDatabases:
    def __init__(self, local):
        self.local = local
        self.active = ContextVar("visitor_database", default=local)
        self.public = os.getenv("EVIDRA_PUBLIC", "0") == "1"
        self.key = os.getenv(
            "EVIDRA_SESSION_SECRET", ""
        ).encode() or secrets.token_bytes(32)
        self.cache = OrderedDict()
        self.lock = Lock()
        self.limits = OrderedDict()

    def current(self):
        return self.active.get()

    def __getattr__(self, name):
        return getattr(self.current(), name)

    def issue(self):
        payload = f"{secrets.token_hex(16)}.{int(time.time()) + 86400}"
        signature = hmac.new(self.key, payload.encode(), hashlib.sha256).hexdigest()
        return f"{payload}.{signature}"

    def verify(self, token):
        try:
            visitor, expiry, signature = token.split(".")
            if len(visitor) != 32 or any(c not in "0123456789abcdef" for c in visitor):
                return None
            expected = hmac.new(
                self.key, f"{visitor}.{expiry}".encode(), hashlib.sha256
            ).hexdigest()
            if (
                not hmac.compare_digest(expected, signature)
                or int(expiry) <= time.time()
            ):
                return None
            return visitor
        except (ValueError, TypeError):
            return None

    def allowed(self, key, count=20, seconds=60):
        with self.lock:
            now = time.monotonic()
            events = self.limits.setdefault(key, deque())
            while events and events[0] <= now - seconds:
                events.popleft()
            if len(events) >= count:
                return False
            events.append(now)
            self.limits.move_to_end(key)
            while len(self.limits) > 2048:
                self.limits.popitem(last=False)
            return True

    def visitor_database(self, visitor):
        with self.lock:
            if visitor in self.cache:
                return self.cache[visitor]
            root = Path("data/visitors")
            root.mkdir(parents=True, exist_ok=True)
            # Only this demo's expired databases are removed; local workspace data is separate.
            for path in root.glob("*.db"):
                if (
                    time.time() - path.stat().st_mtime > 86400
                    and path.stem not in self.cache
                ):
                    path.unlink(missing_ok=True)
            if (
                not (root / (visitor + ".db")).exists()
                and len(list(root.glob("*.db"))) >= 128
            ):
                raise ValueError(
                    "The demo has reached its visitor capacity. Please try later."
                )
            database = Database(f"sqlite:///{root / (visitor + '.db')}")
            seed(database)
            self.cache[visitor] = database
            while len(self.cache) > 32:
                _, old = self.cache.popitem(last=False)
                old.engine.dispose()
            return database

    def install(self, app):
        @app.middleware("http")
        async def visitor_scope(request, call_next):
            if not self.public or not request.url.path.startswith("/api/"):
                return await call_next(request)
            if request.url.path == "/api/health":
                return await call_next(request)
            if request.url.path == "/api/session":
                peer = request.client.host if request.client else "unknown"
                if not self.allowed("session:" + peer, 30, 300):
                    return JSONResponse(
                        {"detail": "Please wait before starting another session."}, 429
                    )
                return await call_next(request)
            visitor = self.verify(
                request.headers.get("Authorization", "").removeprefix("Bearer ")
            )
            if not visitor:
                return JSONResponse(
                    {"detail": "Your demo session expired. Refresh to start again."},
                    401,
                )
            if request.method != "GET" and not self.allowed(visitor):
                return JSONResponse(
                    {"detail": "Please wait a moment before your next request."}, 429
                )
            try:
                length = int(request.headers.get("content-length", "0"))
            except ValueError:
                return JSONResponse({"detail": "Invalid request length."}, 400)
            if length > 9 * 1024 * 1024:
                return JSONResponse({"detail": "Keep requests smaller than 9 MB."}, 413)
            # Enforce the same bound for chunked or misleading Content-Length requests.
            if request.method in ("POST", "PATCH", "PUT"):
                payload = bytearray()
                async for chunk in request.stream():
                    payload.extend(chunk)
                    if len(payload) > 9 * 1024 * 1024:
                        return JSONResponse(
                            {"detail": "Keep requests smaller than 9 MB."}, 413
                        )
                request._body = bytes(payload)
            try:
                database = self.visitor_database(visitor)
            except ValueError as error:
                return JSONResponse({"detail": str(error)}, 503)
            token = self.active.set(database)
            try:
                response = await call_next(request)
                response.headers["Cache-Control"] = "no-store"
                return response
            finally:
                self.active.reset(token)

        @app.post("/api/session")
        def session():
            return {
                "public": self.public,
                "token": self.issue() if self.public else "",
                "expires_in": 86400,
            }
