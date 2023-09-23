from rest_framework import status
from rest_framework.views import APIView
from rest_framework.viewsets import GenericViewSet
from rest_framework.permissions import IsAdminUser
from rest_framework.mixins import (
    CreateModelMixin,
    ListModelMixin,
    RetrieveModelMixin
)
from rest_framework.response import Response
from learn_python_server.api.permissions import (
    IsAuthorizedRepository,
    IsEngagementOwnerOrStaff,
    HasAuthorizedTutor
)
from learn_python_server.api.serializers import TutorEngagementSerializer
from learn_python_server.models import TutorEngagement, Student


class AuthorizeTutorView(APIView):

    permission_classes = [HasAuthorizedTutor]

    def get(self, request, format=None):
        return Response({
            'tutor': request.user.authorized_repository.get_tutor_key().backend.value,
            'secret': request.user.authorized_repository.get_tutor_key().secret,
        })


class TutorEngagementViewSet(
    CreateModelMixin,
    ListModelMixin,
    RetrieveModelMixin,
    GenericViewSet
):

    serializer_class = TutorEngagementSerializer

    def get_permissions(self):
        """
        Instantiates and returns the list of permissions that this view requires.
        """
        if self.action == 'create':  # For POST requests
            permission_classes = [IsAuthorizedRepository]
        elif self.action in ['list', 'retrieve']:  # For GET requests
            permission_classes = [IsEngagementOwnerOrStaff]
        else:
            permission_classes = [IsAdminUser]  # anything else
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        if self.request.user.is_superuser or self.request.user.is_staff:
            return TutorEngagement.objects.all()
        elif isinstance(self.request.user, Student):
            return TutorEngagement.objects.filter(
                repository=self.request.user.authorized_repository
            ).distinct()
        return TutorEngagement.objects.filter()
