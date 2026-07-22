"""
Null byte query parameter middleware.

Rejects requests whose query string contains null bytes (encoded as %00 or
literal \\x00).  PostgreSQL refuses to store or match strings containing null
bytes, so such requests would otherwise propagate as an unhandled 500 error.

This middleware intercepts those requests early and returns 400 Bad Request
with a descriptive JSON error body.

See: AAP-74806
"""

import logging

from django.http import JsonResponse

logger = logging.getLogger(__name__)


class NullByteQueryParamMiddleware:
    """
    Middleware that returns 400 for requests containing null bytes in query parameters.

    PostgreSQL rejects queries that include null bytes (\\x00) in string
    parameters with a DataError.  Without this guard, the DAB FieldLookupBackend
    passes the value to the database and the resulting DatabaseError is not caught,
    producing a 500 Internal Server Error.

    This middleware sits early in the middleware stack and returns a 400 before
    the request reaches any view or filter backend.
    """

    def __init__(self, get_response) -> None:
        self.get_response = get_response

    def __call__(self, request):
        raw_qs = request.META.get("QUERY_STRING", "")
        if self._contains_null_byte(raw_qs):
            logger.warning(
                "Rejected request with null byte in query string: %s %s",
                request.method,
                request.path,
            )
            return JsonResponse(
                {"detail": "Query parameters must not contain null bytes."},
                status=400,
            )
        return self.get_response(request)

    @staticmethod
    def _contains_null_byte(query_string: str) -> bool:
        """Return True if *query_string* contains a null byte, encoded or literal.

        Checks for:
        - ``%00`` — the percent-encoded form (``%00`` is all digits; no case variants exist)
        - A literal ``\\x00`` character (rare in HTTP but defensive)
        """
        if "%00" in query_string:
            return True
        # Check for a literal null byte (unlikely in HTTP but defensive)
        return "\x00" in query_string
