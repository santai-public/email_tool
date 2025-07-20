class IMAPResponseSerializer:
    @staticmethod
    def ok(tag: str, message: str = "OK") -> bytes:
        return f"{tag} {message}\r\n".encode()

    @staticmethod
    def bad(tag: str, message: str = "BAD Command Error") -> bytes:
        return f"{tag} {message}\r\n".encode()

    @staticmethod
    def untagged_ok(message: str = "OK") -> bytes:
        return f"* {message}\r\n".encode()

    @staticmethod
    def capability(capabilities: list[str]) -> bytes:
        return f"* CAPABILITY {' '.join(capabilities)}\r\n".encode()

    @staticmethod
    def bye(message: str = "BYE IMAP4rev1 Server shutting down") -> bytes:
        return f"* {message}\r\n".encode()
