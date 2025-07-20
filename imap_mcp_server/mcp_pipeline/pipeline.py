import importlib
import logging
from typing import List, Dict, Any
from .processors.base_processor import BaseProcessor

logger = logging.getLogger(__name__)

class MCPPipeline:
    def __init__(self, processor_configs: List[Dict[str, Any]] = None):
        self.processors: List[BaseProcessor] = []
        if processor_configs:
            for config in processor_configs:
                try:
                    processor_name = config["name"]
                    module_path = f"imap_mcp_server.mcp_pipeline.processors.{processor_name.lower()}"
                    module = importlib.import_module(module_path)
                    processor_class = getattr(module, processor_name)
                    processor_instance = processor_class(**config.get("params", {}))
                    self.processors.append(processor_instance)
                    logger.info(f"Loaded MCP processor: {processor_name}")
                except Exception as e:
                    logger.error(
                        f"Failed to load MCP processor {config.get('name', 'Unknown')}: {e}"
                    )

    async def process_message(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        processed_data = message_data
        for processor in self.processors:
            try:
                processed_data = await processor.process(processed_data)
                logger.debug(f"Message processed by {processor.__class__.__name__}")
            except Exception as e:
                logger.error(f"Error processing message with {processor.__class__.__name__}: {e}")
                # Depending on policy, might re-raise or continue with original data
        return processed_data
