from typing import Dict, Any
from .base_processor import BaseProcessor

class DummyProcessor(BaseProcessor):
    async def process(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        content = message_data.get("content", b"")
        processed_content = b"X-Processed-By: DummyProcessor\r\n" + content
        message_data["content"] = processed_content
        return message_data
