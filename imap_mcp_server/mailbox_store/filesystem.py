import asyncio
import os
import aiofiles
import json
from typing import List, Dict, Any
from .interface import MailboxStore

class FilesystemMailboxStore(MailboxStore):
    def __init__(self, base_path: str = "./imap_mcp_server/data"):
        self.base_path = os.path.abspath(base_path)
        os.makedirs(self.base_path, exist_ok=True)

    def _get_user_path(self, user: str) -> str:
        return os.path.join(self.base_path, user)

    def _get_mailbox_path(self, user: str, mailbox_name: str) -> str:
        return os.path.join(self._get_user_path(user), mailbox_name)

    async def create_mailbox(self, user: str, mailbox_name: str) -> bool:
        mailbox_path = self._get_mailbox_path(user, mailbox_name)
        try:
            os.makedirs(mailbox_path, exist_ok=True)
            # Create a simple metadata file for UIDNEXT, etc.
            metadata_path = os.path.join(mailbox_path, ".metadata.json")
            if not os.path.exists(metadata_path):
                async with aiofiles.open(metadata_path, 'w') as f:
                    await f.write(json.dumps({"uidnext": 1, "uidvalidity": 1}))
            return True
        except Exception:
            return False

    async def delete_mailbox(self, user: str, mailbox_name: str) -> bool:
        mailbox_path = self._get_mailbox_path(user, mailbox_name)
        if os.path.exists(mailbox_path) and os.path.isdir(mailbox_path):
            try:
                # This is a dangerous operation in a real server, needs careful handling
                # For simplicity, we'll remove recursively. In production, move to trash or similar.
                for root, dirs, files in os.walk(mailbox_path, topdown=False):
                    for name in files:
                        os.remove(os.path.join(root, name))
                    for name in dirs:
                        os.rmdir(os.path.join(root, name))
                os.rmdir(mailbox_path)
                return True
            except Exception:
                return False
        return False

    async def list_mailboxes(self, user: str, pattern: str = '') -> List[str]:
        user_path = self._get_user_path(user)
        if not os.path.exists(user_path):
            return []
        mailboxes = []
        for entry in await asyncio.to_thread(os.listdir, user_path):
            full_path = os.path.join(user_path, entry)
            if os.path.isdir(full_path) and not entry.startswith('.'): # Ignore hidden dirs like .metadata
                # Simple pattern matching for now, glob/regex would be better
                if not pattern or entry.startswith(pattern.replace('%', '').replace('*', '')):
                    mailboxes.append(entry)
        return mailboxes

    async def _read_metadata(self, mailbox_path: str) -> Dict[str, Any]:
        metadata_path = os.path.join(mailbox_path, ".metadata.json")
        if os.path.exists(metadata_path):
            async with aiofiles.open(metadata_path, 'r') as f:
                content = await f.read()
                return json.loads(content)
        return {"uidnext": 1, "uidvalidity": 1}

    async def _write_metadata(self, mailbox_path: str, metadata: Dict[str, Any]):
        metadata_path = os.path.join(mailbox_path, ".metadata.json")
        async with aiofiles.open(metadata_path, 'w') as f:
            await f.write(json.dumps(metadata))

    async def get_message(self, user: str, mailbox_name: str, uid: int) -> Dict[str, Any]:
        mailbox_path = self._get_mailbox_path(user, mailbox_name)
        message_file = os.path.join(mailbox_path, f"{uid}.eml")
        if os.path.exists(message_file):
            async with aiofiles.open(message_file, 'rb') as f:
                content = await f.read()
                # In a real scenario, parse EML for headers, body, etc.
                return {"uid": uid, "content": content, "flags": []} # Simplified
        return {}

    async def append_message(self, user: str, mailbox_name: str, message_content: bytes, flags: List[str] = None) -> int:
        mailbox_path = self._get_mailbox_path(user, mailbox_name)
        if not os.path.exists(mailbox_path):
            await self.create_mailbox(user, mailbox_name) # Ensure mailbox exists

        metadata = await self._read_metadata(mailbox_path)
        uid = metadata["uidnext"]
        metadata["uidnext"] += 1
        await self._write_metadata(mailbox_path, metadata)

        message_file = os.path.join(mailbox_path, f"{uid}.eml")
        async with aiofiles.open(message_file, 'wb') as f:
            await f.write(message_content)

        # Store flags separately or within message file metadata in a real system
        return uid

    async def search_messages(self, user: str, mailbox_name: str, criteria: Dict[str, Any]) -> List[int]:
        mailbox_path = self._get_mailbox_path(user, mailbox_name)
        if not os.path.exists(mailbox_path):
            return []

        uids = []
        for entry in await asyncio.to_thread(os.listdir, mailbox_path):
            if entry.endswith(".eml"):
                try:
                    uid = int(entry.split('.')[0])
                    # Very basic search: just return all UIDs for now. Real search is complex.
                    uids.append(uid)
                except ValueError:
                    continue
        return sorted(uids)

    async def update_flags(self, user: str, mailbox_name: str, uids: List[int], flags: List[str], mode: str) -> bool:
        # This is a placeholder. Real flag management requires parsing .eml or separate flag storage.
        # For now, always return True, assuming success.
        return True

    async def get_mailbox_status(self, user: str, mailbox_name: str) -> Dict[str, Any]:
        mailbox_path = self._get_mailbox_path(user, mailbox_name)
        if not os.path.exists(mailbox_path):
            return {}

        metadata = await self._read_metadata(mailbox_path)
        message_count = 0
        for entry in await asyncio.to_thread(os.listdir, mailbox_path):
            if entry.endswith(".eml"):
                message_count += 1

        # Simplified status. Real status includes UIDNEXT, UIDVALIDITY, MESSAGES, RECENT, UNSEEN, etc.
        return {
            "messages": message_count,
            "uidnext": metadata.get("uidnext", 1),
            "uidvalidity": metadata.get("uidvalidity", 1),
            "unseen": 0, # Placeholder
            "recent": 0  # Placeholder
        }
