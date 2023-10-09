from django.http import Http404
from learn_python_server.api.permissions import (
    CreateOrViewRepoItemPermission,
    HasAuthorizedTutor,
    IsEnrolled,
)
from learn_python_server.api.serializers import (
    LogFileSerializer,
    TutorEngagementSerializer,
    TimelinePolymorphicSerializer,
    ModuleSerializer
)
from learn_python_server.models import (
    LogFile,
    Student,
    TutorEngagement,
    TimelineEvent,
    StudentRepository,
    CourseRepository,
    Module
)
from rest_framework.permissions import IsAdminUser
from rest_framework.mixins import (
    CreateModelMixin,
    DestroyModelMixin,
    ListModelMixin,
    RetrieveModelMixin,
    UpdateModelMixin,
)
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.views import APIView
from rest_framework.viewsets import GenericViewSet
from rest_framework.generics import ListAPIView
from django.db.models import Q, Prefetch
import logging

api_logger = logging.getLogger('learn_python_server.api')

class AuthorizeTutorView(APIView):

    permission_classes = [HasAuthorizedTutor]

    def get(self, request, format=None):
        return Response({
            'tutor': request.user.authorized_repository.get_tutor_key().backend.value,
            'secret': request.user.authorized_repository.get_tutor_key().secret,
        })


class LogValidationErrors:

    def create(self, request, *args, **kwargs):
        try:
            super().create(request, *args, **kwargs)
        except ValidationError:
            api_logger.exception('create() error')
            raise

    def update(self, request, *args, **kwargs):
        try:
            super().update(request, *args, **kwargs)
        except ValidationError:
            api_logger.exception('update() error')
            raise


class TutorEngagementViewSet(
    CreateModelMixin,
    UpdateModelMixin,
    ListModelMixin,
    RetrieveModelMixin,
    GenericViewSet
):

    serializer_class = TutorEngagementSerializer
    permission_classes = [CreateOrViewRepoItemPermission, IsEnrolled]

    lookup_field = 'engagement_id'

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
            try:
                lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
                self.kwargs = {
                    **self.kwargs,
                    lookup_url_kwarg: request.data['engagement_id']
                }
                return self.update(
                    request,
                    *args,
                    **self.kwargs
                )
            except Http404:
                return super().create(request, *args, **kwargs)
        except ValidationError:
            api_logger.exception('TutorEngagementViewSet::create() error')
            raise


class LogFileViewSet(
    CreateModelMixin,
    ListModelMixin,
    RetrieveModelMixin,
    DestroyModelMixin,
    GenericViewSet
):
    
    serializer_class = LogFileSerializer
    permission_classes = [CreateOrViewRepoItemPermission, IsEnrolled]

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
    
    def create(self, request, *args, **kwargs):
        try:
            return super().create(request, *args, **kwargs)
        except ValidationError:
            api_logger.exception('LogFileViewSet::create() validation error')
            raise
    

class TimelineViewSet(ListAPIView):

    serializer_class = TimelinePolymorphicSerializer

    def get_queryset(self):
        uri = self.kwargs.get('uri', None)
        id = self.kwargs.get('id', None)
        timeline_q = Q()
        if uri or id is not None:
            if id:
                qry = Q(id=int(id))
            else:
                qry = Q(uri=uri)
            try:
                repository = StudentRepository.objects.get(qry)
                if not (self.request.user.is_staff or self.request.user.is_superuser):
                    if not((
                        repository in StudentRepository.objects.filter(
                            student__in=self.request.user.students.all()
                        )
                    ) or (
                        repository == getattr(self.request.user, 'authorized_repository', None)
                    )):
                        raise PermissionDenied()
                timeline_q = Q(repository=repository)
            except StudentRepository.DoesNotExist:
                raise Http404()
        elif not (self.request.user.is_superuser or self.request.user.is_staff):
            raise PermissionDenied()
        return TimelineEvent.objects.filter(timeline_q).select_related('repository')


class ModuleViewSet(ListAPIView):

    serializer_class = ModuleSerializer

    def get_queryset(self):
        uri = self.kwargs.get('uri', None)
        id = self.kwargs.get('id', None)
        timeline_q = Q()
        if uri or id is not None:
            if id:
                qry = Q(id=int(id))
            else:
                qry = Q(uri=uri)
            try:
                return Module.objects.filter(
                    repository=CourseRepository.objects.get(qry)
                ).prefetch_related('assignments')
            except CourseRepository.DoesNotExist:
                raise Http404()
