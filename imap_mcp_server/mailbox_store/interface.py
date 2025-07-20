from abc import ABC, abstractmethod
from typing import List, Dict, Any

class MailboxStore(ABC):
    @abstractmethod
    async def create_mailbox(self, user: str, mailbox_name: str) -> bool:
        """Creates a new mailbox for a given user."""
        pass

    @abstractmethod
    async def delete_mailbox(self, user: str, mailbox_name: str) -> bool:
        """Deletes an existing mailbox for a given user."""
        pass

    @abstractmethod
    async def list_mailboxes(self, user: str, pattern: str = '') -> List[str]:
        """Lists mailboxes for a given user, optionally filtered by a pattern."""
        pass

    @abstractmethod
    async def get_message(self, user: str, mailbox_name: str, uid: int) -> Dict[str, Any]:
        """Retrieves a specific message by UID from a mailbox."""
        pass

    @abstractmethod
    async def append_message(self, user: str, mailbox_name: str, message_content: bytes, flags: List[str] = None) -> int:
        """Appends a new message to a mailbox, returning its UID."""
        pass

    @abstractmethod
    async def search_messages(self, user: str, mailbox_name: str, criteria: Dict[str, Any]) -> List[int]:
        """Searches for messages in a mailbox based on criteria, returning UIDs."""
        pass

    @abstractmethod
    async def update_flags(self, user: str, mailbox_name: str, uids: List[int], flags: List[str], mode: str) -> bool:
        """Updates flags for messages in a mailbox."""
        pass

    @abstractmethod
    async def get_mailbox_status(self, user: str, mailbox_name: str) -> Dict[str, Any]:
        """Gets status information for a mailbox (e.g., total messages, unseen count)."""
        pass
