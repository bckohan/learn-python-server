from learn_python_server.models import (
    DocBuild,
    StudentRepository,
    TutorEngagement
)
from django.http import (
    HttpResponseRedirect,
    HttpResponse,
    HttpResponseForbidden,
    HttpResponseNotFound,
    JsonResponse,
    FileResponse
)
from django.http import Http404
from django.conf import settings
from learn_python_server.utils import normalize_repository
from django.db.models import Q
from django.views.generic import DetailView
import os
from django.utils.translation import gettext_lazy as _


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
    if repository.isdigit():
        qry |= Q(repository__repository__id=int(repository))
    
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


def get_engagement_log(request, engagement_id, ext):
    try:
        log_file = TutorEngagement.objects.get(id=engagement_id).log
        if log_file and os.path.exists(log_file.path):
            return FileResponse(log_file.open(), content_type='application/octet-stream')
        raise Http404()
    except TutorEngagement.DoesNotExist as err:
        raise Http404() from err


class TutorEngagementDetailView(DetailView):
    model = TutorEngagement
    template_name = 'learn_python_server/engagement_detail.html'
    context_object_name = 'engagement'