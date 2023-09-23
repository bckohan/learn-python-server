from learn_python_server.utils import normalize_repository


class NormalizeRepositoryMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        if 'HTTP_X_LEARN_PYTHON_REPOSITORY' in request.META:
            try:
                request.META['HTTP_X_LEARN_PYTHON_REPOSITORY'] = normalize_repository(
                    request.META.get['HTTP_X_LEARN_PYTHON_REPOSITORY']
                )
            except Exception:
                pass
        response = self.get_response(request)
        return response
