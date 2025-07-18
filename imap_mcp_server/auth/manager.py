from typing import Dict
from .backends import AuthBackend, PlainAuthBackend

class AuthManager:
    def __init__(self):
        self._backends: Dict[str, AuthBackend] = {}
        self.register_backend("PLAIN", PlainAuthBackend())

    def register_backend(self, name: str, backend: AuthBackend):
        self._backends[name.upper()] = backend

    async def authenticate(self, mechanism: str, username: str, password: str) -> bool:
        backend = self._backends.get(mechanism.upper())
        if not backend:
            return False
        return await backend.authenticate(username, password)
