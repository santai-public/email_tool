import asyncio
import logging
import re
from .parser import IMAPCommandParser
from .serializer import IMAPResponseSerializer
from imap_mcp_server.mailbox_store.interface import MailboxStore
from imap_mcp_server.auth.manager import AuthManager
from imap_mcp_server.mcp_pipeline.pipeline import MCPPipeline

class IMAPSession:
    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, mailbox_store: MailboxStore, auth_manager: AuthManager, mcp_pipeline: MCPPipeline):
        self.reader = reader
        self.writer = writer
        self.peername = writer.get_extra_info('peername')
        self.mailbox_store = mailbox_store
        self.auth_manager = auth_manager
        self.mcp_pipeline = mcp_pipeline
        self.authenticated = False
        self.current_user = None
        self.selected_mailbox = None
        self.read_only = False # For EXAMINE command
        logging.info(f"Session initialized for {self.peername}")

    async def send_response(self, response: bytes):
        self.writer.write(response)
        await self.writer.drain()

    async def handle_command(self, tag: str, command: str, args: list):
        logging.info(f"Handling command: {command} with args {args} for {self.peername}")
        handler_name = f"handle_{command.lower()}"
        handler = getattr(self, handler_name, self.handle_unknown_command)
        await handler(tag, args)

    async def handle_capability(self, tag: str, args: list):
        capabilities = ["IMAP4rev1", "AUTH=PLAIN", "IDLE", "LITERAL+", "UIDPLUS"] # Added UIDPLUS
        await self.send_response(IMAPResponseSerializer.capability(capabilities))
        await self.send_response(IMAPResponseSerializer.ok(tag, "CAPABILITY completed"))

    async def handle_login(self, tag: str, args: list):
        if len(args) != 2:
            await self.send_response(IMAPResponseSerializer.bad(tag, "LOGIN requires username and password"))
            return
        username, password = args
        logging.info(f"Attempting login for user: {username}")
        if await self.auth_manager.authenticate("PLAIN", username, password):
            self.authenticated = True
            self.current_user = username
            await self.send_response(IMAPResponseSerializer.ok(tag, "LOGIN completed"))
            logging.info(f"User {username} authenticated successfully.")
        else:
            await self.send_response(IMAPResponseSerializer.bad(tag, "LOGIN failed: Invalid credentials"))
            logging.warning(f"Login failed for user: {username}")

    async def handle_logout(self, tag: str, args: list):
        await self.send_response(IMAPResponseSerializer.bye())
        await self.send_response(IMAPResponseSerializer.ok(tag, "LOGOUT completed"))
        logging.info(f"User {self.peername} logged out.")
        # Signal to close connection
        raise asyncio.IncompleteReadError(None, None) # Simulate disconnect

    async def handle_select(self, tag: str, args: list):
        if not self.authenticated:
            await self.send_response(IMAPResponseSerializer.bad(tag, "SELECT failed: Not authenticated"))
            return
        if len(args) != 1:
            await self.send_response(IMAPResponseSerializer.bad(tag, "SELECT requires a mailbox name"))
            return
        mailbox_name = args[0]
        logging.info(f"Attempting to select mailbox: {mailbox_name} for user {self.current_user}")
        status = await self.mailbox_store.get_mailbox_status(self.current_user, mailbox_name)
        if status:
            self.selected_mailbox = mailbox_name
            self.read_only = False # SELECT implies read-write
            await self.send_response(IMAPResponseSerializer.untagged_ok(f"[READ-WRITE] {mailbox_name} selected"))
            await self.send_response(IMAPResponseSerializer.untagged_ok(f"{status.get('messages', 0)} EXISTS"))
            await self.send_response(IMAPResponseSerializer.untagged_ok(f"{status.get('recent', 0)} RECENT"))
            await self.send_response(IMAPResponseSerializer.untagged_ok(f"OK [UIDVALIDITY {status.get('uidvalidity', 1)}] UIDVALIDITY"))
            await self.send_response(IMAPResponseSerializer.untagged_ok(f"OK [UIDNEXT {status.get('uidnext', 1)}] UIDNEXT"))
            await self.send_response(IMAPResponseSerializer.ok(tag, "SELECT completed"))
            logging.info(f"Mailbox {mailbox_name} selected by {self.peername}.")
        else:
            await self.send_response(IMAPResponseSerializer.bad(tag, f"SELECT failed: Mailbox {mailbox_name} not found"))
            logging.warning(f"Mailbox {mailbox_name} not found for {self.peername}.")

    async def handle_examine(self, tag: str, args: list):
        if not self.authenticated:
            await self.send_response(IMAPResponseSerializer.bad(tag, "EXAMINE failed: Not authenticated"))
            return
        if len(args) != 1:
            await self.send_response(IMAPResponseSerializer.bad(tag, "EXAMINE requires a mailbox name"))
            return
        mailbox_name = args[0]
        logging.info(f"Attempting to examine mailbox: {mailbox_name} for user {self.current_user}")
        status = await self.mailbox_store.get_mailbox_status(self.current_user, mailbox_name)
        if status:
            self.selected_mailbox = mailbox_name
            self.read_only = True # EXAMINE implies read-only
            await self.send_response(IMAPResponseSerializer.untagged_ok(f"[READ-ONLY] {mailbox_name} selected"))
            await self.send_response(IMAPResponseSerializer.untagged_ok(f"{status.get('messages', 0)} EXISTS"))
            await self.send_response(IMAPResponseSerializer.untagged_ok(f"{status.get('recent', 0)} RECENT"))
            await self.send_response(IMAPResponseSerializer.untagged_ok(f"OK [UIDVALIDITY {status.get('uidvalidity', 1)}] UIDVALIDITY"))
            await self.send_response(IMAPResponseSerializer.untagged_ok(f"OK [UIDNEXT {status.get('uidnext', 1)}] UIDNEXT"))
            await self.send_response(IMAPResponseSerializer.ok(tag, "EXAMINE completed"))
            logging.info(f"Mailbox {mailbox_name} examined by {self.peername}.")
        else:
            await self.send_response(IMAPResponseSerializer.bad(tag, f"EXAMINE failed: Mailbox {mailbox_name} not found"))
            logging.warning(f"Mailbox {mailbox_name} not found for {self.peername}.")

    async def handle_create(self, tag: str, args: list):
        if not self.authenticated:
            await self.send_response(IMAPResponseSerializer.bad(tag, "CREATE failed: Not authenticated"))
            return
        if len(args) != 1:
            await self.send_response(IMAPResponseSerializer.bad(tag, "CREATE requires a mailbox name"))
            return
        mailbox_name = args[0]
        logging.info(f"Attempting to create mailbox: {mailbox_name} for user {self.current_user}")
        success = await self.mailbox_store.create_mailbox(self.current_user, mailbox_name)
        if success:
            await self.send_response(IMAPResponseSerializer.ok(tag, "CREATE completed"))
            logging.info(f"Mailbox {mailbox_name} created for {self.current_user}.")
        else:
            await self.send_response(IMAPResponseSerializer.bad(tag, f"CREATE failed: Could not create mailbox {mailbox_name}"))
            logging.warning(f"Failed to create mailbox {mailbox_name} for {self.current_user}.")

    async def handle_delete(self, tag: str, args: list):
        if not self.authenticated:
            await self.send_response(IMAPResponseSerializer.bad(tag, "DELETE failed: Not authenticated"))
            return
        if len(args) != 1:
            await self.send_response(IMAPResponseSerializer.bad(tag, "DELETE requires a mailbox name"))
            return
        mailbox_name = args[0]
        logging.info(f"Attempting to delete mailbox: {mailbox_name} for user {self.current_user}")
        success = await self.mailbox_store.delete_mailbox(self.current_user, mailbox_name)
        if success:
            await self.send_response(IMAPResponseSerializer.ok(tag, "DELETE completed"))
            logging.info(f"Mailbox {mailbox_name} deleted for {self.current_user}.")
        else:
            await self.send_response(IMAPResponseSerializer.bad(tag, f"DELETE failed: Could not delete mailbox {mailbox_name}"))
            logging.warning(f"Failed to delete mailbox {mailbox_name} for {self.current_user}.")

    async def handle_list(self, tag: str, args: list):
        if not self.authenticated:
            await self.send_response(IMAPResponseSerializer.bad(tag, "LIST failed: Not authenticated"))
            return
        if len(args) != 2:
            await self.send_response(IMAPResponseSerializer.bad(tag, "LIST requires a reference and a mailbox pattern"))
            return
        # reference = args[0] # Not used for now
        pattern = args[1]
        logging.info(f"Attempting to list mailboxes for user {self.current_user} with pattern {pattern}")
        mailboxes = await self.mailbox_store.list_mailboxes(self.current_user, pattern)
        for mailbox in mailboxes:
            # Flags: \Noselect for mailboxes that cannot be selected, \Noinferiors for mailboxes that have no children
            await self.send_response(IMAPResponseSerializer.untagged_ok(f"LIST (\\Noinferiors) \"/\" \"{mailbox}\""))
        await self.send_response(IMAPResponseSerializer.ok(tag, "LIST completed"))

    async def handle_lsub(self, tag: str, args: list):
        # LSUB is for subscribed mailboxes. For now, we'll just return all mailboxes as if subscribed.
        await self.handle_list(tag, args) # Re-use LIST logic for simplicity

    async def handle_status(self, tag: str, args: list):
        if not self.authenticated:
            await self.send_response(IMAPResponseSerializer.bad(tag, "STATUS failed: Not authenticated"))
            return
        if len(args) != 2:
            await self.send_response(IMAPResponseSerializer.bad(tag, "STATUS requires a mailbox name and a list of items"))
            return
        mailbox_name = args[0]
        items_str = args[1].strip('()') # Remove parentheses
        requested_items = [item.upper() for item in items_str.split(' ') if item]

        logging.info(f"Getting status for mailbox {mailbox_name} with items {requested_items}")
        status = await self.mailbox_store.get_mailbox_status(self.current_user, mailbox_name)

        if status:
            response_parts = []
            for item in requested_items:
                if item == "MESSAGES":
                    response_parts.append(f"MESSAGES {status.get('messages', 0)}")
                elif item == "RECENT":
                    response_parts.append(f"RECENT {status.get('recent', 0)}")
                elif item == "UIDNEXT":
                    response_parts.append(f"UIDNEXT {status.get('uidnext', 1)}")
                elif item == "UIDVALIDITY":
                    response_parts.append(f"UIDVALIDITY {status.get('uidvalidity', 1)}")
                elif item == "UNSEEN":
                    response_parts.append(f"UNSEEN {status.get('unseen', 0)}")
                # Add other status items as needed
            status_response = f"* STATUS {mailbox_name} ({ ' '.join(response_parts) })"
            await self.send_response(IMAPResponseSerializer.untagged_ok(status_response))
            await self.send_response(IMAPResponseSerializer.ok(tag, "STATUS completed"))
        else:
            await self.send_response(IMAPResponseSerializer.bad(tag, f"STATUS failed: Mailbox {mailbox_name} not found"))

    async def handle_append(self, tag: str, args: list):
        if not self.authenticated:
            await self.send_response(IMAPResponseSerializer.bad(tag, "APPEND failed: Not authenticated"))
            return
        if len(args) < 2:
            await self.send_response(IMAPResponseSerializer.bad(tag, "APPEND requires mailbox and literal"))
            return

        mailbox_name = args[0]
        # The message content is expected as a literal, which means it comes after a {size} line.
        # For simplicity, we're assuming the last argument is the message content for now.
        # A real IMAP server needs to handle literal parsing carefully.
        message_content_str = args[-1] # This is a simplification

        # Check if the message content is a literal (e.g., {123}\r\nmessage_data)
        # This basic parser doesn't fully handle literals, so we'll look for a common pattern.
        match = re.match(r'\{(\d+)\}', message_content_str)
        if match:
            size = int(match.group(1))
            # Send continuation request for literal
            await self.send_response(b"+\r\n")
            # Read the exact number of bytes for the literal
            message_content_bytes = await self.reader.readexactly(size + 2) # +2 for CRLF
            message_content = message_content_bytes[:-2] # Remove CRLF
        else:
            # If not a literal, assume it's directly provided (less common for full messages)
            message_content = message_content_str.encode('utf-8')

        # Process message through MCP pipeline before appending
        processed_message_data = await self.mcp_pipeline.process_message({"content": message_content, "mailbox": mailbox_name, "user": self.current_user})
        final_message_content = processed_message_data["content"]

        logging.info(f"Appending message to {mailbox_name} for user {self.current_user}")
        uid = await self.mailbox_store.append_message(self.current_user, mailbox_name, final_message_content)
        if uid:
            await self.send_response(IMAPResponseSerializer.ok(tag, f"APPEND completed [UID {uid}]"))
            logging.info(f"Message appended with UID {uid} to {mailbox_name}.")
        else:
            await self.send_response(IMAPResponseSerializer.bad(tag, "APPEND failed"))
            logging.warning(f"Failed to append message to {mailbox_name}.")

    async def handle_fetch(self, tag: str, args: list):
        if not self.authenticated or not self.selected_mailbox:
            await self.send_response(IMAPResponseSerializer.bad(tag, "FETCH failed: Not authenticated or no mailbox selected"))
            return
        if len(args) < 2:
            await self.send_response(IMAPResponseSerializer.bad(tag, "FETCH requires message sequence/UID set and data items"))
            return

        # This is a very simplified FETCH handler. Real FETCH is complex.
        # It assumes args[0] is a single UID and args[1] is a single data item like BODY[]
        uid_or_seq = args[0]
        fetch_item = args[1].upper()

        try:
            uid = int(uid_or_seq) # Assuming UID for simplicity
        except ValueError:
            await self.send_response(IMAPResponseSerializer.bad(tag, "FETCH failed: Invalid message sequence/UID"))
            return

        message_data = await self.mailbox_store.get_message(self.current_user, self.selected_mailbox, uid)

        if message_data:
            response_parts = []
            if fetch_item == "BODY[]":
                content = message_data.get("content", b"")
                response_parts.append(f"BODY[] {{{len(content)}}}")
                await self.send_response(IMAPResponseSerializer.untagged_ok(f"FETCH {uid} ({ ' '.join(response_parts) })"))
                self.writer.write(content + b"\r\n") # Send literal content
                await self.writer.drain()
            elif fetch_item == "UID":
                response_parts.append(f"UID {uid}")
                await self.send_response(IMAPResponseSerializer.untagged_ok(f"FETCH {uid} ({ ' '.join(response_parts) })"))
            else:
                await self.send_response(IMAPResponseSerializer.bad(tag, f"FETCH failed: Unsupported fetch item {fetch_item}"))
                return

            await self.send_response(IMAPResponseSerializer.ok(tag, "FETCH completed"))
        else:
            await self.send_response(IMAPResponseSerializer.bad(tag, f"FETCH failed: Message {uid} not found"))

    async def handle_search(self, tag: str, args: list):
        if not self.authenticated or not self.selected_mailbox:
            await self.send_response(IMAPResponseSerializer.bad(tag, "SEARCH failed: Not authenticated or no mailbox selected"))
            return

        # Very simplified search. Assumes args are search criteria directly.
        # A real implementation would parse complex search criteria.
        criteria = {"ALL": True} # Default to ALL if no specific criteria
        if args:
            # For now, just take the first arg as a keyword, e.g., 'ALL' or 'UNSEEN'
            if args[0].upper() == "UNSEEN":
                criteria = {"UNSEEN": True}
            elif args[0].upper() == "ALL":
                criteria = {"ALL": True}
            # Add more complex parsing here later

        logging.info(f"Searching mailbox {self.selected_mailbox} for user {self.current_user} with criteria {criteria}")
        uids = await self.mailbox_store.search_messages(self.current_user, self.selected_mailbox, criteria)

        if uids is not None:
            await self.send_response(IMAPResponseSerializer.untagged_ok(f"SEARCH {' '.join(map(str, uids))}"))
            await self.send_response(IMAPResponseSerializer.ok(tag, "SEARCH completed"))
        else:
            await self.send_response(IMAPResponseSerializer.bad(tag, "SEARCH failed"))

    async def handle_unknown_command(self, tag: str, args: list):
        logging.warning(f"Unknown command received: {tag} {args}")
        await self.send_response(IMAPResponseSerializer.bad(tag, "Command not recognized or supported"))

    async def run(self):
        await self.send_response(IMAPResponseSerializer.untagged_ok("IMAP4rev1 Service Ready"))

        while True:
            try:
                data = await self.reader.readline()
                if not data:
                    break
                message = data.decode('utf-8', errors='ignore').strip()
                logging.info(f"Received from {self.peername}: {message}")

                try:
                    tag, command, args = IMAPCommandParser.parse(message)
                    await self.handle_command(tag, command, args)
                except ValueError as e:
                    logging.error(f"Parsing error for {self.peername}: {e} - Raw: {message}")
                    # Send a BAD response for malformed commands without a tag
                    if message and ' ' in message:
                        tag_part = message.split(' ', 1)[0]
                        await self.send_response(IMAPResponseSerializer.bad(tag_part, str(e)))
                    else:
                        # If no tag can be extracted, just close connection or send generic error
                        logging.error(f"Could not extract tag from malformed command: {message}")
                        break # Close connection for unparseable commands

            except asyncio.IncompleteReadError:
                logging.info(f"Client {self.peername} disconnected.")
                break
            except Exception as e:
                logging.error(f"Error in session for {self.peername}: {e}", exc_info=True)
                break

        logging.info(f"Closing connection for {self.peername}")
        self.writer.close()
        await self.writer.wait_closed()
