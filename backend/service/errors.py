class ServiceError(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        self.code, self.message, self.status = code, message, status
        super().__init__(message)


def extractor_error(error: Exception) -> ServiceError:
    # Classify privately: never publish stderr, cookie paths or signed media URLs.
    text = str(error).lower()
    if "there is no video in this post" in text:
        return ServiceError(
            "instagram_photo_planned",
            "This Instagram post contains photos. Photo and carousel selection is the next Instagram stage. Use one Reel or video post for now.",
        )
    if "drm protected" in text or "drm-protected" in text:
        return ServiceError(
            "drm_protected",
            "The source offers this item only in DRM-protected formats. Choose a track or video with an available unprotected download, or use the creator's official download.",
        )
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
    if "unable to extract client id" in text:
        return ServiceError(
            "soundcloud_client_id",
            "SoundCloud's public API credentials could not be retrieved. Retry after checking the server's SoundCloud access and runtime versions.",
        )
    if any(
        word in text for word in ("http error 429", "too many requests", "rate limit", "rate-limit")
    ):
        return ServiceError(
            "source_rate_limited",
            "The source is limiting requests. Wait before trying this item again.",
        )
    if any(
        word in text
        for word in ("not available in your country", "geo restricted", "geographic restriction")
    ):
        return ServiceError(
            "source_region",
            "This item is not available in the server's region. Choose another available item.",
        )
    if any(
        word in text
        for word in (
            "unexpected response from webpage",
            "unable to extract challenge",
            "unable to solve js challenge",
            "universal data for rehydration",
            "unable to extract webpage video data",
        )
    ):
        return ServiceError(
            "source_page_unreadable",
            "The source returned a page its extractor could not read. Retry; if it persists, check browser transport support in Settings and source access from the server.",
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
