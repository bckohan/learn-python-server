"""
URL configuration for mysite project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.staticfiles import handlers
from django.urls import include, path, register_converter
from learn_python_server.api.views import (
    AuthorizeTutorView,
    LogFileViewSet,
    TutorEngagementViewSet,
    TimelineViewSet,
    ModuleViewSet
)
from learn_python_server.views import (
    StudentRepositoryTimelineView,
    course_docs,
    get_log,
    redirect_latest_docs,
    register,
    repository_docs,
)
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r'engagements', TutorEngagementViewSet, basename='engagements')
router.register(r'logs', LogFileViewSet, basename='logs')


class URLConverter:
    regex = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
    placeholder = 'http://example.com'

    def to_python(self, value):
        return value

    def to_url(self, value):
        return value


register_converter(URLConverter, 'url')


urlpatterns = [
    path('', redirect_latest_docs, name='redirect_latest_docs'),
    path('docs/<str:course>', course_docs, name='course_docs'),
    path('docs/<url:repository>', repository_docs, name='repository_docs'),
    path('register/<url:repository>', register, name='register'),
    path('api/authorize_tutor', AuthorizeTutorView.as_view(), name='authorize_tutor'),
    path('api/', include(router.urls)),
    path('api/timeline', TimelineViewSet.as_view(), name='timeline'),
    path('api/timeline/<url:uri>', TimelineViewSet.as_view(), name='timeline'),
    path('api/timeline/<int:id>', TimelineViewSet.as_view(), name='timeline'),
    path('api/modules/<url:uri>', ModuleViewSet.as_view(), name='modules'),
    path('api/modules/<int:id>', ModuleViewSet.as_view(), name='modules'),
    path('media/log_uploads/<str:log_name>', get_log, name='get_log'),
    path('timeline/<url:uri>', StudentRepositoryTimelineView.as_view(), name='student_timeline'),
    path('timeline/<int:id>', StudentRepositoryTimelineView.as_view(), name='student_timeline'),
    path('admin/', admin.site.urls)
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    import debug_toolbar
    urlpatterns.append(path('__debug__/', include(debug_toolbar.urls)))
