import asyncio
import logging

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DEFAULT_IMAP_PORT = 143
DEFAULT_HOST = "0.0.0.0"

async def handle_client_connection(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    """
    Handles a single client connection.
    """
    peername = writer.get_extra_info('peername')
    logger.info(f"New connection from {peername}")

    # Send IMAP greeting
    greeting = "* OK IMAP4rev1 server ready\r\n"
    writer.write(greeting.encode('utf-8'))
    await writer.drain()
    logger.info(f"Sent greeting to {peername}")

    try:
        while True:
            data = await reader.read(1024) # Read up to 1024 bytes
            if not data:
                logger.info(f"Client {peername} disconnected (EOF).")
                break

            message = data.decode('utf-8', errors='ignore').strip()
            logger.info(f"Received from {peername}: {message}")

            # Placeholder for command processing
            # For now, we'll just echo a generic response or log
            # In a real server, we'd parse the command and act accordingly
            # e.g., writer.write(b"A001 OK SOME_COMMAND completed\r\n")

            if message.upper() == "QUIT": # A very basic way to close connection for testing
                logger.info(f"Client {peername} sent QUIT. Closing connection.")
                writer.write(b"* BYE IMAP server shutting down connection\r\n")
                writer.write(b"A001 OK QUIT completed\r\n") # Assuming A001 is the tag
                await writer.drain()
                break

    except ConnectionResetError:
        logger.warning(f"Connection reset by {peername}")
    except Exception as e:
        logger.error(f"Error handling client {peername}: {e}", exc_info=True)
    finally:
        logger.info(f"Closing connection for {peername}")
        writer.close()
        await writer.wait_closed()

async def main(host=DEFAULT_HOST, port=DEFAULT_IMAP_PORT):
    """
    Starts the IMAP server.
    """
    server = await asyncio.start_server(
        handle_client_connection, host, port)

    addr = server.sockets[0].getsockname()
    logger.info(f"IMAP Gateway Server listening on {addr}")

    async with server:
        await server.serve_forever()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("IMAP Gateway Server shutting down.")
