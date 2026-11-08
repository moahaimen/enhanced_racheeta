"""One error family for every commerce write; the API maps `code` to an HTTP status."""


class CommerceError(Exception):
    code = "commerce_error"

    def __init__(self, message: str = "", code: str | None = None):
        super().__init__(message)
        if code:
            self.code = code
