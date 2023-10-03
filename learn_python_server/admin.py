"""
Admin interface for all models in etc_player.
"""
import os
from pathlib import Path
from typing import Any

from django import forms
from django.conf import settings
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm
from django.core.management import call_command
from django.db.models import Count
from django.db.models.query import QuerySet
from django.http.request import HttpRequest
from django.http.response import HttpResponseRedirect, HttpResponse
from django.urls import path, reverse
from django.utils.html import format_html, mark_safe
from django.utils.timezone import localtime
from django.utils.translation import gettext_lazy as _
from learn_python_server.models import (
    Assignment,
    Course,
    CourseRepository,
    CourseRepositoryVersion,
    DocBuild,
    Enrollment,
    LogEvent,
    LogFile,
    Module,
    SpecialTopic,
    Student,
    StudentRepository,
    StudentRepositoryPublicKey,
    TestEvent,
    TutorAPIKey,
    TutorEngagement,
    TutorExchange,
    TutorSession,
    User,
    TimelineEvent
)


class ReadOnlyMixin:
        
    def has_add_permission(self, request, obj=None):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(User)
class LPUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'full_name', 'last_name', 'is_staff')

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal info', {'fields': ('full_name',)}),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        ('Dates', {'fields': ('date_joined',)}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2'),
        }),
    )
    ordering = ('email',)

    readonly_fields = ('date_joined', 'last_login')


# a tabular inline for enrollments
class EnrollmentInline(admin.TabularInline):
    model = Enrollment
    extra = 0
    readonly_fields = ('student', 'joined', 'last_activity')
    #raw_id_fields = ('repository',)


# a custom admin for courses
@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):

    list_display = ('name', 'started', 'ended', 'enrollment', 'repo', 'docs')
    list_filter = ('repository',)
    search_fields = ('name', 'repository__uri')
    ordering = ('-started',)
    inlines = [EnrollmentInline]

    change_form_template = 'admin/course_change_form.html'

    def enrollment(self, obj):
        return obj.enrollments.count()
    
    def repo(self, obj):
        # return a link to obj.docs.url
        return format_html('<a href="{url}" target="_blank">{url}</a>', url=obj.repository) if obj.repository else None

    def docs(self, obj):
        # return a link to obj.docs.url
        return format_html('<a href="{url}" target="_blank">docs</a>', url=obj.docs.url) if obj.docs else None

    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path('<object_id>/build_docs/', self.admin_site.admin_view(self.build_docs), name='learn_python_server_course_build-docs'),
        ]
        return my_urls + urls

    def build_docs(self, request, object_id):
        course = Course.objects.get(pk=object_id)
        call_command('update_course', [], course=str(course.pk))
        self.message_user(request, f'{course.name} documentation was rebuilt.')
        return HttpResponseRedirect(redirect_to=reverse('course_docs', kwargs={'course': object_id}))


# a tabular inline for enrollments
class StudentRepositoryInline(admin.TabularInline):
    model = StudentRepository
    extra = 0


class StudentRepositoryPublicKey(ReadOnlyMixin, admin.TabularInline):
    model = StudentRepositoryPublicKey
    extra = 0

    readonly_fields = ('key_str',)

    def key_str(self, obj):
        return obj.key_str
    key_str.short_description = 'RSA Key'



# need to override the default UserChangeForm to make the password fields not required
class StudentChangeForm(UserChangeForm):
    password = forms.CharField(widget=forms.HiddenInput(), required=False)


class StudentCreationForm(UserCreationForm):
    password1 = forms.CharField(
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
        required=False
    )
    password2 = forms.CharField(
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
        required=False
    )


# a custom admin for courses
@admin.register(Student)
class StudentAdmin(LPUserAdmin):

    form = StudentChangeForm
    add_form = StudentCreationForm

    list_display = ('handle', 'email', 'full_name', 'last_login')
    search_fields = ('full_name', 'email', 'handle')
    ordering = ('handle',)

    fieldsets = (
        (None, {'fields': ('handle', 'email',)}),
        ('Personal info', {'fields': ('full_name',)}),
        ('Dates', {'fields': ('date_joined', 'last_login')}),
        ('Credentials', {'fields': ('tutor_key',)})
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('handle', 'email'),
        }),
        ('Personal info', {'fields': ('full_name',)}),
        ('Credentials', {'fields': ('tutor_key',)}),
    )
    ordering = ('handle',)

    inlines = [StudentRepositoryInline, EnrollmentInline]


class CourseRepositoryVersionAdmin(ReadOnlyMixin, admin.TabularInline):

    model = CourseRepositoryVersion
    ordering = ('-timestamp',)
    readonly_fields = ('timestamp', 'repository', 'git_branch', 'git_hash', 'commit_count')

    def repo(self, obj):
        return obj.repository.uri
    
    def get_queryset(self, request: HttpRequest) -> QuerySet[Any]:
        return super().get_queryset(request).select_related('repository')


@admin.register(DocBuild)
class DocBuildAdmin(ReadOnlyMixin, admin.ModelAdmin):

    list_display = ('repo', 'timestamp', 'docs')
    search_fields = ('repository__repository__uri', 'repository__repository__courses__name')
    ordering = ('-timestamp',)
    readonly_fields = ('timestamp', 'repository', 'docs')

    def docs(self, obj):
        # return a link to obj.docs.url
        return format_html('<a href="{url}" target="_blank">docs</a>', url=obj.url)

    def repo(self, obj):
        return obj.repository.repository.uri
    
    def get_queryset(self, request: HttpRequest) -> QuerySet[Any]:
        return super().get_queryset(request).select_related('repository', 'repository__repository')


@admin.register(Assignment)
class AssignmentAdmin(ReadOnlyMixin, admin.ModelAdmin):

    list_display = ('module', 'number', 'name', 'repo')
    search_fields = ('name', 'module__name')
    ordering = ('module__name', 'number')
    readonly_fields = (
        'added', 'removed', 'module', 'number', 'name', 
        'todo', 'hints', 'requirements', 'identifier'
    )
    list_filter = ('module', 'module__repository')

    def repo(self, obj):
        return obj.module.repository.uri
    
    def get_queryset(self, request: HttpRequest) -> QuerySet[Any]:
        return super().get_queryset(request).select_related('module', 'module__repository')


@admin.register(Module)
class ModuleAdmin(ReadOnlyMixin, admin.ModelAdmin):

    list_display = ('name', 'number', 'added')
    search_fields = ('name',)
    ordering = ('name',)
    readonly_fields = ('added', 'removed', 'name', 'number', 'repository')
    list_filter = ('repository',)

    def repo(self, obj):
        return obj.repository.uri
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('repository')
    
    def has_change_permission(self, request, obj=None):
        return admin.ModelAdmin.has_change_permission(self, request, obj)


@admin.register(SpecialTopic)
class SpecialTopicAdmin(ModuleAdmin):
    pass


@admin.register(StudentRepository)
class StudentRepositoryAdmin(admin.ModelAdmin):

    list_display = ('student_name', 'uri')
    search_fields = ('student__name', 'student__handle', 'student__email', 'uri')
    readonly_fields = ('student',)
    inlines = [StudentRepositoryPublicKey]

    def student_name(self, obj):
        return obj.student.display
    
    def get_queryset(self, request: HttpRequest) -> QuerySet[Any]:
        return super().get_queryset(request).select_related(
            'student'
        ).prefetch_related('keys')

    def change_view(self, request, object_id, form_url='', extra_context=None):
        self.readonly_fields = ('student',)
        return super().change_view(request, object_id, form_url, extra_context)

class CourseInlineAdmin(ReadOnlyMixin, admin.TabularInline):

    model = Course
    extra = 0


@admin.register(CourseRepository)
class CourseRepositoryAdmin(admin.ModelAdmin):

    list_display = ('uri',)
    search_fields = ('courses__name', 'uri')

    inlines = [CourseInlineAdmin, CourseRepositoryVersionAdmin]

    def get_queryset(self, request: HttpRequest) -> QuerySet[Any]:
        return super().get_queryset(request).prefetch_related('versions', 'courses')


@admin.register(TutorExchange)
class TutorExchangeAdmin(ReadOnlyMixin, admin.ModelAdmin):
    pass


class TutorExchangeInlineAdmin(ReadOnlyMixin, admin.TabularInline):
    model = TutorExchange
    extra = 0
    fk_name = 'session'

    fields = ('exchange', 'role', 'content')
    readonly_fields = ('exchange',)

    def has_delete_permission(self, request, obj=None):
        return True
    
    def exchange(self, instance):
        url = reverse('admin:learn_python_server_tutorexchange_change', args=[instance.pk])
        return format_html('<a href="{}">{}</a>', url, localtime(instance.timestamp))
        
    exchange.short_description = 'Timestamp'
    
@admin.register(TutorSession)
class TutorSessionAdmin(ReadOnlyMixin, admin.ModelAdmin):
    
    list_display = ('engagement', 'timestamp', 'stop', 'assignment', 'num_exchanges')
    search_fields = (
        'engagement__repository__student__full_name',
        'engagement__repository__student__email',
        'engagement__repository__student__handle',
        'assignment__name',
        'assignment__module__name',
    )
    list_filter = (
        'engagement__repository__enrollment__course__name',
        'engagement__repository__enrollment__course__repository__modules__name',
        'engagement__repository__enrollment__course__repository__modules__assignments__name',
    )
    
    def engagement(self, obj):
        return obj.engagement.repository.student.display
    
    def num_exchanges(self, obj):
        return obj.exchanges.count()

    inlines = [TutorExchangeInlineAdmin,]

    def get_queryset(self, request: HttpRequest) -> QuerySet[Any]:
        return super().get_queryset(request).select_related(
            'assignment'
        ).prefetch_related('exchanges').annotate(num_exchanges=Count('exchanges'))


class TutorSessionInlineAdmin(ReadOnlyMixin, admin.TabularInline):
    model = TutorSession
    extra = 0
    fk_name = 'engagement'

    fields = ('session', 'timestamp', 'stop', 'assignment', 'num_exchanges')
    readonly_fields = ('session', 'num_exchanges')

    def has_delete_permission(self, request, obj=None):
        return True
    
    def session(self, instance):
        url = reverse('admin:learn_python_server_tutorsession_change', args=[instance.pk])
        return format_html('<a href="{}">{}</a>', url, instance.session_id)
        
    session.short_description = 'Session ID'

    def num_exchanges(self, instance):
        return instance.num_exchanges

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'assignment',
            'assignment__module',
            'engagement'
        ).prefetch_related(
            'exchanges'
        ).annotate(num_exchanges=Count('exchanges'))


@admin.register(TutorEngagement)
class TutorEngagementAdmin(ReadOnlyMixin, admin.ModelAdmin):

    list_display = ('student', 'timestamp', 'sessions', 'tasks', 'duration', 'log_file')
    search_fields = (
        'repository__student__full_name',
        'repository__student__email',
        'repository__student__handle',
        'sessions__assignment__name',
        'sessions__assignment__module__name',
    )
    # list_filter = (
    #     'repository__enrollment__course__name',
    #     'repository__enrollment__course__repository__modules__name',
    #     'repository__enrollment__course__repository__modules__assignments__name',
    # )
    
    def student(self, obj):
        return obj.repository.student.display

    def duration(self, obj):
        if obj.stop:
            return obj.stop - obj.timestamp
        
    def sessions(self, obj):
        return obj.sessions.count()

    def tasks(self, obj):
        return obj.tasks

    inlines = [TutorSessionInlineAdmin,]

    def get_queryset(self, request: HttpRequest) -> QuerySet[Any]:
        return super().get_queryset(request).select_related(
            'repository',
            'repository__student',
            'log'
        ).prefetch_related('sessions').annotate(tasks=Count('sessions__assignment', unique=True))

    def has_delete_permission(self, request, obj=None):
        return True
    
    def log_file(self, obj):
        if obj.log:
            url = reverse('admin:learn_python_server_logfile_change', args=[obj.log.id])
            return format_html('<a href="{}">{}</a>', url, os.path.basename(obj.log.log.name))
    
    log_file.short_description = _('Log File')


@admin.register(LogFile)
class LogFileAdmin(ReadOnlyMixin, admin.ModelAdmin):

    list_display = ('student', 'date', 'type', 'log', 'uploaded_at', 'num_lines', 'processed')
    search_fields = (
        'repository__student__full_name',
        'repository__student__email',
        'repository__student__handle',
        'repository__uri'
    )
    list_filter = (
        'type',
        'processed'
    )
    change_form_template = 'admin/logfile_change_form.html'
    
    def student(self, obj):
        return obj.repository.student.display

    def get_queryset(self, request: HttpRequest) -> QuerySet[Any]:
        return super().get_queryset(request).select_related(
            'repository',
            'repository__student'
        )
    
    def has_delete_permission(self, request, obj=None):
        return True
    
    def log_file(self, obj):
        url = reverse('admin:learn_python_server_logfile_change', args=[obj.log.id])
        return format_html('<a href="{}">{}</a>', url, os.path.basename(obj.log.name))
    
    log_file.short_description = _('Log File')

    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path('<object_id>/process_log/', self.admin_site.admin_view(self.process_log), name='learn_python_server_logfile_process-log'),
        ]
        return my_urls + urls

    def process_log(self, request, object_id):
        log = LogFile.objects.get(pk=object_id)
        call_command('process_logs', [log.pk], reset=True)
        self.message_user(request, f'{os.path.basename(log.log.name)} log was processed.')
        return HttpResponse(status=200)
    
    def process_logs(self, request, queryset):
        call_command('process_logs', [log.pk for log in queryset], reset=True)
        self.message_user(request, f'{queryset.count()} logs were processed.')
    
    process_logs.short_description = "(Re)Process Logs"

    actions = [process_logs]


@admin.register(LogEvent)
class LogEventAdmin(ReadOnlyMixin, admin.ModelAdmin):

    list_display = ('timestamp', 'level_colored', 'student', 'log_file', 'lines', 'message_preview')
    search_fields = (
        'log__repository__student__full_name',
        'log__repository__student__handle',
        'log__repository__student__email'
    )
    list_filter = (
        'level',
    )
    
    def student(self, obj):
        if obj.log:
            return obj.log.repository.student.display
        
    def lines(self, obj):
        return mark_safe(f'{obj.line_begin} - {obj.line_end}')
        
    def log_file(self, obj):
        return format_html(
            '<a href="{}">{}</a>',
            Path(settings.MEDIA_URL) / obj.log.log.name,
            os.path.basename(obj.log.log.name)
        )
    
    log_file.short_description = _('Log')

    def has_delete_permission(self, request, obj=None):
        return True

    def get_queryset(self, request: HttpRequest) -> QuerySet[Any]:
        return super().get_queryset(request).select_related(
            'log__repository',
            'log__repository__student'
        )
    
    exclude = ('message',)

    readonly_fields = ['message2']

    def message2(self, obj):
        return format_html('<pre>{}</pre>', obj.message)
    message2.short_description = 'Message'
    
    log_file.short_description = _('Log File')

    def level_colored(self, obj):
        return format_html(
            f'<div style="font-weight: bold;text-align: center; background-color: '
            f'{obj.level.color};color: white;">{str(obj.level).upper()}</div>'
        )

    level_colored.short_description = 'Level'

    def message_preview(self, obj):
        return obj.message.split('\n')[0].strip()

    message_preview.short_description = 'Message'


@admin.register(TestEvent)
class TestEventAdmin(LogEventAdmin):

    list_display = ('timestamp', 'level_colored', 'student', 'result_colored', 'runner', 'assignment')
    
    list_filter = (
        *LogEventAdmin.list_filter,
        'result',
        'runner',
    )

    def result_colored(self, obj):
        return format_html(f'<div style="font-weight: bold;text-align: center; background-color: {obj.result.color};color: white;">{str(obj.result).upper()}</div>')

    result_colored.short_description = 'Result'

    def get_queryset(self, request: HttpRequest) -> QuerySet[Any]:
        return super().get_queryset(request).select_related(
            'log__repository',
            'log__repository__student',
            'assignment'
        ).prefetch_related('assignment__module')

admin.register(TutorAPIKey)(admin.ModelAdmin)
