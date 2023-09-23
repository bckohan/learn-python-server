from learn_python_server.models import StudentRepository
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from learn_python_server.utils import normalize_repository
from django.utils.translation import gettext_lazy as _


class RepositorySignatureAuthentication(BaseAuthentication):

    def authenticate(self, request):
        repository = request.META.get('HTTP_X_LEARN_PYTHON_REPOSITORY', '')
        if repository:
            repository = normalize_repository(repository)

            try:
                repo = StudentRepository.objects.get(uri=repository)
                if repo.verify(request):
                    repo.student.authorized_repository = repo
                    return (repo.student, None)
                else:
                    raise AuthenticationFailed(
                        _('Repository {} does not have a valid signature.').format(repository)
                    )
            except StudentRepository.DoesNotExist:
                raise AuthenticationFailed(
                    _('Repository {} is not registered.'
                ).format(repository))
