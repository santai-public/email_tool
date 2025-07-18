import re

class IMAPCommandParser:
    @staticmethod
    def parse(data: str):
        """
        Parses a raw IMAP command string into its components: tag, command, and arguments.
        Example: 'A001 LOGIN user@example.com password'
        Returns: ('A001', 'LOGIN', ['user@example.com', 'password'])
        """
        parts = data.strip().split(' ', 2)
        if len(parts) < 2:
            raise ValueError("Invalid IMAP command format")

        tag = parts[0]
        command = parts[1].upper()
        args = []
        if len(parts) > 2:
            # Simple split for now, will need more robust parsing for quoted strings/literals
            args = re.findall(r'"([^"]*)"|(\S+)', parts[2])
            args = [item[0] if item[0] else item[1] for item in args]

        return tag, command, args
