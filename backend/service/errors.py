class ServiceError(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        self.code, self.message, self.status = code, message, status
        super().__init__(message)


def extractor_error(error: Exception) -> ServiceError:
    # Classify privately: never publish stderr, cookie paths or signed media URLs.
    text = str(error).lower()
    if "invalid data found" in text:
        return ServiceError(
            "invalid_source_media",
            "The source returned invalid media data. Check source access and connectivity, then analyze again.",
        )
    if "certificate verify failed" in text or "certificate_verify_failed" in text:
        return ServiceError(
            "tls_error",
            "The server could not verify the source certificate. Check its trusted certificates and proxy configuration.",
        )
    if "ip address is blocked" in text or "blocked from accessing" in text:
        return ServiceError(
            "network_blocked",
            "The source blocked access from this server's network. Check source availability from the server or try another public item.",
        )
    if any(word in text for word in ("sign in", "login", "cookies", "private", "age-restricted")):
        return ServiceError(
            "access_required",
            "This source requires access. The owner can configure server-side cookies, then analyze again.",
        )
    if "requested format" in text:
        return ServiceError(
            "format_unavailable", "This format is no longer available. Analyze the link again."
        )
    if any(word in text for word in ("unavailable", "not available", "removed", "404")):
        return ServiceError(
            "source_unavailable",
            "This material is unavailable. Check the link and its access permissions.",
        )
    return ServiceError(
        "source_error",
        "The source could not be processed. Check connectivity and tool versions, then analyze again.",
    )
