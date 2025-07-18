from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseProcessor(ABC):
    @abstractmethod
    async def process(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processes the email message data.
        message_data is a dictionary containing message content and metadata.
        Returns the modified message_data.
        """
        pass
