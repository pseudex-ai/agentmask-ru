"""Response headers the framework does not set for us.

Django's SecurityMiddleware covers nosniff, HSTS and the referrer policy. It has
no content security policy, and this site has two properties that make one worth
having beyond the usual: it is where a customer's credentials for a production
gateway are managed, and it must be demonstrably free of third-party beacons.
`default-src 'self'` with no reporting endpoint is that demonstration — there is
no origin the page could talk to even if something were injected into it.
"""

from django.utils.deprecation import MiddlewareMixin

_POLICY = "; ".join([
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self'",
    # The landing draws its diagrams inline; attributes only, never a <style>
    # block, for the same reason as the local interface.
    "style-src-attr 'unsafe-inline'",
    "img-src 'self' data:",
    "font-src 'self'",
    # Deliberately no third party. An analytics tag here would beacon from a
    # page a logged-in customer is looking at, which is exactly the shape of
    # data flow this product exists to prevent.
    "connect-src 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
    "base-uri 'none'",
])


class SecurityHeadersMiddleware(MiddlewareMixin):
    def process_response(self, request, response):
        response.setdefault("Content-Security-Policy", _POLICY)
        # Pages behind the login show a key prefix and billing detail. A shared
        # proxy holding a rendered copy is a copy nobody accounted for.
        if request.path.startswith("/app/") or request.path.startswith("/admin/"):
            response["Cache-Control"] = "no-store"
        return response
