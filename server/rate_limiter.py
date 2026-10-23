import logging
from typing import Callable, Iterable, List, Optional, Tuple

import jwt
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from starlette.middleware.base import RequestResponseEndpoint
from starlette.routing import BaseRoute, Match

from server.config import settings

logger = logging.getLogger("PhyrexianForge.RateLimiter")


def get_real_ip(request: Request) -> str:
    """
    Extract real client IP from X-Forwarded-For header if present (useful behind reverse proxies),
    otherwise fallback to request client host or 127.0.0.1.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        ip = forwarded.split(",")[0].strip()
        if ip:
            return ip
    return get_remote_address(request)


def get_auth_key(request: Request) -> str:
    """
    Key function for auth endpoints (login, register, demo):
    Rate limits strictly per client IP address to prevent brute-force attacks.
    """
    return f"ip:{get_real_ip(request)}"


def get_user_or_ip_key(request: Request) -> str:
    """
    Key function for authenticated/AI endpoints:
    If Authorization Bearer token is provided, uses user ID/sub from the token.
    Otherwise falls back to client IP.
    """
    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer "):
        token = auth[7:].strip()
        try:
            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM],
                options={"verify_exp": False},
            )
            sub = payload.get("sub") or payload.get("username")
            if sub:
                return f"user:{sub}"
        except Exception:
            pass
    return f"ip:{get_real_ip(request)}"


class SafeLimiter(Limiter):
    """
    A Limiter subclass that safely handles header injection even if an endpoint
    returns a dict or Pydantic model without a declared `response: Response` parameter.
    """

    def _inject_headers(
        self, response: Response, current_limit: Tuple[object, List[str]]
    ) -> Response:
        if response is None or not isinstance(response, Response):
            return response
        return super()._inject_headers(response, current_limit)


# Initialize shared application limiter
default_limits = [settings.GLOBAL_RATE_LIMIT] if settings.GLOBAL_RATE_LIMIT else []
limiter = SafeLimiter(
    key_func=get_user_or_ip_key,
    default_limits=default_limits,
    headers_enabled=True,
    enabled=settings.RATE_LIMIT_ENABLED,
)


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> Response:
    """
    Custom 429 response handler returning standard detail/error fields and Retry-After / RateLimit headers.
    """
    response = JSONResponse(
        status_code=429,
        content={
            "detail": f"Rate limit exceeded: {exc.detail}",
            "error": f"Rate limit exceeded: {exc.detail}",
        },
    )
    view_rate_limit = getattr(request.state, "view_rate_limit", None)
    if limiter._headers_enabled and view_rate_limit:
        response = limiter._inject_headers(response, view_rate_limit)
    return response


def custom_find_route_handler(routes: Iterable[BaseRoute], scope: dict) -> Optional[Callable]:
    """
    Route handler lookup that supports both Starlette routes and modern FastAPI _IncludedRouter wrappers.
    """
    for route in routes:
        if hasattr(route, "_match"):
            try:
                res = route._match(scope)
                if res and res[0] == Match.FULL:
                    matched_route = res[2]
                    if hasattr(matched_route, "endpoint"):
                        return matched_route.endpoint
            except Exception:
                pass
        match, _ = route.matches(scope)
        if match == Match.FULL:
            if hasattr(route, "endpoint"):
                return route.endpoint
            if hasattr(route, "routes"):
                handler = custom_find_route_handler(route.routes, scope)
                if handler:
                    return handler
    return None


class PhyrexianSlowAPIMiddleware(SlowAPIMiddleware):
    """
    Extended SlowAPIMiddleware that supports nested routers and ensures rate limit headers
    (X-RateLimit-*, Retry-After) are injected on responses.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await super().dispatch(request, call_next)
        view_rate_limit = getattr(request.state, "view_rate_limit", None)
        if view_rate_limit and limiter._headers_enabled:
            if "x-ratelimit-limit" not in response.headers:
                response = limiter._inject_headers(response, view_rate_limit)
        return response
