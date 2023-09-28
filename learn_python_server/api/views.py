from rest_framework.views import APIView
from rest_framework.viewsets import GenericViewSet
from rest_framework.mixins import (
    CreateModelMixin,
    UpdateModelMixin,
    ListModelMixin,
    RetrieveModelMixin,
    DestroyModelMixin
)
from django.http import Http404
from rest_framework.response import Response
from learn_python_server.api.permissions import (
    CreateOrViewRepoItemPermission,
    HasAuthorizedTutor
)
from learn_python_server.api.serializers import (
    TutorEngagementSerializer,
    LogFileSerializer
)
from learn_python_server.models import (
    TutorEngagement,
    Student,
    LogFile
)


class AuthorizeTutorView(APIView):

    permission_classes = [HasAuthorizedTutor]

    def get(self, request, format=None):
        return Response({
            'tutor': request.user.authorized_repository.get_tutor_key().backend.value,
            'secret': request.user.authorized_repository.get_tutor_key().secret,
        })


class TutorEngagementViewSet(
    CreateModelMixin,
    UpdateModelMixin,
    ListModelMixin,
    RetrieveModelMixin,
    GenericViewSet
):

    serializer_class = TutorEngagementSerializer
    permission_classes = [CreateOrViewRepoItemPermission]

    def get_serializer_context(self):
        return {
            **super().get_serializer_context(),
            'request': self.request
        }

    def get_queryset(self):
        if self.request.user.is_superuser or self.request.user.is_staff:
            return TutorEngagement.objects.all()
        elif isinstance(self.request.user, Student):
            return TutorEngagement.objects.filter(
                repository=self.request.user.authorized_repository
            ).distinct()
        return TutorEngagement.objects.none()
    
    def create(self, request, *args, **kwargs):
        try:
            lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
            self.kwargs = {
                **self.kwargs,
                lookup_url_kwarg: request.data['id']
            }
            return self.update(
                request,
                *args,
                **self.kwargs
            )
        except Http404:
            return super().create(request, *args, **kwargs)


class LogFileViewSet(
    CreateModelMixin,
    ListModelMixin,
    RetrieveModelMixin,
    DestroyModelMixin,
    GenericViewSet
):
    
    serializer_class = LogFileSerializer
    permission_classes = [CreateOrViewRepoItemPermission]

    def get_serializer_context(self):
        return {
            **super().get_serializer_context(),
            'request': self.request
        }

    def get_queryset(self):
        if self.request.user.is_superuser or self.request.user.is_staff:
            return LogFile.objects.all()
        elif isinstance(self.request.user, Student):
            return LogFile.objects.filter(
                repository=self.request.user.authorized_repository
            ).distinct()
        return LogFile.objects.none()
    
    # def create(self, request, *args, **kwargs):
    #     import ipdb
    #     ipdb.set_trace()
    #     ret = super().create(request, *args, **kwargs)
    #     return ret