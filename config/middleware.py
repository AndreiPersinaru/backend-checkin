"""
Custom middleware for Fly.io health checks
"""

class BypassAllowedHostsForHealthCheckMiddleware:
    """
    Bypass ALLOWED_HOSTS validation for health check endpoint.
    This allows internal Fly.io health checks to work properly.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # If this is a health check request, temporarily allow any host
        if request.path == '/api/health/':
            # Store the original HTTP_HOST and set to localhost to bypass validation
            original_host = request.META.get('HTTP_HOST')
            request.META['HTTP_HOST'] = 'localhost'
            
        response = self.get_response(request)
        return response
