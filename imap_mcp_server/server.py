import asyncio
import logging
from imap_mcp_server.imap_protocol.session import IMAPSession
from imap_mcp_server.mailbox_store.filesystem import FilesystemMailboxStore
from imap_mcp_server.auth.manager import AuthManager
from imap_mcp_server.mcp_pipeline.pipeline import MCPPipeline

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class IMAPServer:
    def __init__(self, host='127.0.0.1', port=143):
        self.host = host
        self.port = port
        self.server = None
        self.mailbox_store = FilesystemMailboxStore() # Initialize the mailbox store
        self.auth_manager = AuthManager() # Initialize the authentication manager
        # Example processor configuration (can be loaded from a config file later)
        processor_configs = [
            {"name": "DummyProcessor", "params": {}}, # Added DummyProcessor
            # {"name": "VirusScanProcessor", "params": {"api_key": "your_key"}},
            # {"name": "DLPProcessor", "params": {"rules_path": "./dlp_rules.json"}},
            # {"name": "HeaderRewriteProcessor", "params": {"rules": {"From": "new@example.com"}}},
        ]
        self.mcp_pipeline = MCPPipeline(processor_configs) # Initialize the MCP pipeline
        logging.info(f"IMAP Server initialized on {self.host}:{self.port}")

    async def handle_client(self, reader, writer):
        session = IMAPSession(reader, writer, self.mailbox_store, self.auth_manager, self.mcp_pipeline) # Pass the MCP pipeline to the session
        await session.run()

    async def start(self):
        self.server = await asyncio.start_server(
            self.handle_client, self.host, self.port
        )
        addrs = ', '.join(str(sock.getsockname()) for sock in self.server.sockets)
        logging.info(f"Serving on {addrs}")
        async with self.server:
            await self.server.serve_forever()

    async def stop(self):
        if self.server:
            logging.info("Stopping IMAP server...")
            self.server.close()
            await self.server.wait_closed()
            logging.info("IMAP server stopped.")

if __name__ == "__main__":
    server = IMAPServer()
    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        logging.info("Server interrupted by user. Shutting down...")
        asyncio.run(server.stop())
    except Exception as e:
        logging.critical(f"Unhandled exception in main server loop: {e}")
