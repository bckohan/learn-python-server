from rest_framework import permissions
from learn_python_server.models import (
    Student,
    StudentRepository
)


class IsAuthorizedRepository(permissions.BasePermission):
    """
    Custom permission to only allow authorized student repository users to access a view.
    It simply ensures that the student user is authenticated and has an authorized repository.
    """
    
    def has_permission(self, request, view):
        # Check if the user is authenticated and is a special user.
        if isinstance(request.user, Student) and request.user.is_authenticated:
            # Check if the user has an authorized repository.
            return request.user.authorized_repository.student == request.user
        return False


class IsRepositoryOwnerOrStaff(permissions.BasePermission):
    """
    Works for objects that have a repository field that is a ForeignKey to a StudentRepository.
    Grants access is the authenticated user is staff, a super user or the owner of the repository.
    """
    
    def has_object_permission(self, request, view, obj):
        if request.user.is_staff or request.user.is_superuser:
            return True
        return obj.repository in StudentRepository.objects.filter(
            student__in=request.user.students.all()
        ) or obj.repository == request.user.authorized_repository


class CreateOrViewRepoItemPermission(IsAuthorizedRepository, IsRepositoryOwnerOrStaff):
    
    def has_permission(self, request, view):
        if view.action == 'create':
            return super().has_permission(request, view)
        return True


class HasAuthorizedTutor(IsAuthorizedRepository):

    def has_permission(self, request, view):
        if super().has_permission(request, view):
            return bool(request.user.authorized_repository.get_tutor_key())
        return False
