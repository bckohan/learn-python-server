import os

from django.conf import settings
from django.db.models import Q
from django.http import (
    FileResponse,
    Http404,
    HttpResponse,
    HttpResponseForbidden,
    HttpResponseNotFound,
    HttpResponseRedirect,
    JsonResponse,
)
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView
from learn_python_server.models import (
    DocBuild,
    LogFile,
    StudentRepository,
    TutorEngagement,
)
from learn_python_server.utils import normalize_repository


def course_docs(request, course):
    qry = Q(repository__repository__courses__name=course)
    if course.isdigit():
        qry |= Q(repository__repository__courses__id=int(course))
    
    docs = DocBuild.objects.filter(qry).order_by('-timestamp').distinct().first()
    if docs:
        return HttpResponseRedirect(redirect_to=docs.url)
    return HttpResponseNotFound()


def repository_docs(request, repository):
    qry = Q(repository__repository__uri=repository)
    docs = DocBuild.objects.filter(qry).order_by('-timestamp').first()
    if docs:
        return HttpResponseRedirect(redirect_to=docs.url)
    return HttpResponseNotFound()


def redirect_latest_docs(request):
    latest = DocBuild.objects.order_by('-timestamp').first()
    if latest:
        return HttpResponseRedirect(redirect_to=latest.url)
    return HttpResponse()


def register(request, repository):
    """
    The main student repository registration workflow. This view is called by the student
    repository when it is ready to be registered. It will verify that the public API keys
    exist and that the signature of the request is valid.
    """
    repository = normalize_repository(repository)
    if not StudentRepository.is_valid(repository):
        return HttpResponse(
            status=400,
            content=_('{} is not a supported repository.').format(repository)
        )
    
    repo, _1 = StudentRepository.objects.get_or_create(uri=repository)

    all_keys, _1, _1 = repo.synchronize_keys()
    if not all_keys:
        return HttpResponse(status=400, content=_('No public keys found.'))
    
    repo.refresh_from_db()
    if not repo.verify(request):
        return HttpResponseForbidden(
            _('Registration of {} has invalid signature.').format(repository)
        )
    
    # if there is a single pending enrollment for this student - meaning an enrollment
    # object associating this student with a course, but their is no repository associated
    # with the course, then we can assume we should automatically enroll this repository/student
    # in the course
    pending_enrollments = repo.student.enrollments.filter(repository__isnull=True)
    if pending_enrollments.count() == 1:
        enroll = pending_enrollments.first()
        enroll.repository = repo
        enroll.save()
        repo.refresh_from_db()

    tutor_api_key = repo.get_tutor_key()

    if repo.verify(request):
        return JsonResponse(
            data={
                'server': f'{request.scheme}://{request.get_host()}',
                'registered': True,
                'enrollment': (
                    repo.enrollment.course.name
                    if hasattr(repo, 'enrollment') and repo.enrollment else
                    None
                ),
                'tutor': tutor_api_key.backend.value if tutor_api_key else None,
            },
            status=201
        )
    return HttpResponseForbidden(
        _('Registration of {} has invalid signature.').format(repository)
    )


def get_log(request, log_name):
    try:
        if log_name.isdigit():
            log_file = LogFile.objects.get(id=int(log_name))
        else:
            log_file = LogFile.objects.get(log__icontains=log_name)
        if (
            os.path.exists(log_file.log.path) and (
                (request.user.is_staff or request.user.is_superuser)
                or (
                    log_file.repository in StudentRepository.objects.filter(student__in=request.user.students.all())
                    or log_file.repository == request.user.authorized_repository
                )
            )
        ):
            return FileResponse(log_file.log.open(), content_type='application/gzip')
        raise Http404()
    except LogFile.DoesNotExist as err:
        raise Http404() from err


class StudentRepositoryTimelineView(TemplateView):

    template_name = 'learn_python_server/student_repository_timeline.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            if 'uri' in kwargs:
                context['repository'] = StudentRepository.objects.get(uri=kwargs['uri'])
            elif 'id' in kwargs:
                context['repository'] = StudentRepository.objects.get(id=kwargs['id'])
            else:
                # todo - unified timeline?
                raise Http404()
            if hasattr(context['repository'], 'enrollment'):
                context['course'] = context['repository'].enrollment.course
        except StudentRepository.DoesNotExist:
            raise Http404()
        return context
