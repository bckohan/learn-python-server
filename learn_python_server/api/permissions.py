from rest_framework import permissions
from learn_python_server.models import Student, StudentRepositoryVersion


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
    

class IsEngagementOwnerOrStaff(permissions.BasePermission):
    """
    Only works for TutorEngagement objects. Allows access if the user is a staff member, 
    a super user or the owner of the tutor engagement record.
    """
    
    def has_object_permission(self, request, view, tutor_engagement):
        if request.user.is_staff or request.user.is_superuser:
            return True
        return tutor_engagement.repository in StudentRepositoryVersion.objects.filter(
            repository__student__in=request.user.students
        )


class HasAuthorizedTutor(IsAuthorizedRepository):

    def has_permission(self, request, view):
        if super().has_permission(request, view):
            return bool(request.user.authorized_repository.get_tutor_key())
        return False
