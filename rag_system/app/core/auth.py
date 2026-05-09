"""Authentication helpers for request-level user identity."""
from fastapi import Header, HTTPException, status


async def get_authenticated_user_id(
    x_authenticated_user_id: str | None = Header(
        default=None,
        alias="X-Authenticated-User-Id",
        description="Authenticated user ID provided by trusted auth layer",
    ),
) -> str:
    """Return authenticated user ID from a trusted upstream header."""
    user_id = (x_authenticated_user_id or "").strip()
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authenticated user identity",
        )
    return user_id
