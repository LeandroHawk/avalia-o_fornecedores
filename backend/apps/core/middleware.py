from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.http import JsonResponse
from django.shortcuts import resolve_url
from django.urls import Resolver404, resolve


class SecurityHeadersMiddleware:
    """Adds conservative headers that complement Django's built-in security middleware."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        response.setdefault("Referrer-Policy", "same-origin")
        if not response.has_header("Content-Security-Policy"):
            response["Content-Security-Policy"] = (
                "default-src 'self'; "
                "img-src 'self' data:; "
                "style-src 'self' 'unsafe-inline'; "
                "script-src 'self' 'unsafe-inline'; "
                "font-src 'self' data:; "
                "frame-ancestors 'none'; "
                "base-uri 'self'; "
                "form-action 'self'"
            )
        return response


class LoginRequiredMiddleware:
    """Requires authentication for private routes while leaving public entrypoints open."""

    public_url_names = {"home", "login"}
    public_prefixes = ("/admin/",)

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if self._is_public_request(request) or getattr(request.user, "is_authenticated", False):
            return self.get_response(request)
        if request.path_info.startswith("/api/"):
            return JsonResponse({"detail": "Authentication credentials were not provided."}, status=401)
        return redirect_to_login(request.get_full_path(), resolve_url(settings.LOGIN_URL))

    def _is_public_request(self, request):
        path = request.path_info
        if any(path.startswith(prefix) for prefix in self.public_prefixes):
            return True
        static_url = getattr(settings, "STATIC_URL", "")
        if static_url and path.startswith(f"/{static_url.lstrip('/')}"):
            return True
        try:
            match = resolve(path)
        except Resolver404:
            return False
        return match.url_name in self.public_url_names
