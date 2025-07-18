from abc import ABC, abstractmethod

class AuthBackend(ABC):
    @abstractmethod
    async def authenticate(self, username: str, password: str) -> bool:
        """Authenticates a user with the given username and password."""
        pass

class PlainAuthBackend(AuthBackend):
    async def authenticate(self, username: str, password: str) -> bool:
        # This is a dummy authentication for demonstration purposes.
        # In a real application, this would involve hashing passwords, database lookups, etc.
        return username == "test" and password == "test"
