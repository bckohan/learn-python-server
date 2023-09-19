from learn_python_server.models import DocBuild
from django.http import HttpResponseRedirect, HttpResponse
from django.conf import settings


def redirect_latest_docs(request):
    latest = DocBuild.objects.latest('timestamp')
    if latest:
        return HttpResponseRedirect(redirect_to=latest.url)
    return HttpResponse()
