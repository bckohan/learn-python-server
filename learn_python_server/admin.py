"""
Admin interface for all models in etc_player.
"""
from typing import Any
from django.urls import path
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm
from django.db.models.query import QuerySet
from django.db.models import Count
from django.core.management import call_command
from django.urls import reverse
from django.http.request import HttpRequest
from django.http.response import HttpResponseRedirect
from learn_python_server.models import (
    User,
    Course,
    Enrollment,
    StudentRepository,
    Student,
    CourseRepository,
    CourseRepositoryVersion,
    StudentRepositoryPublicKey,
    Module,
    Assignment,
    DocBuild,
    TutorAPIKey,
    TutorExchange,
    TutorEngagement,
    TutorSession,
    SpecialTopic
)
from django import forms
from django.utils.html import format_html
from django.utils.timezone import localtime


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
    readonly_fields = ('joined', 'last_activity')
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
    
    list_display = ('engagement', 'start', 'end', 'assignment', 'num_exchanges')
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

    fields = ('session', 'start', 'end', 'assignment', 'num_exchanges')
    readonly_fields = ('session', 'num_exchanges')

    def has_delete_permission(self, request, obj=None):
        return True
    
    def session(self, instance):
        url = reverse('admin:learn_python_server_tutorsession_change', args=[instance.pk])
        return format_html('<a href="{}">{}</a>', url, instance.session_id)
        
    session.short_description = 'Session ID'

    def num_exchanges(self, instance):
        return instance.num_exchanges

    def get_queryset(self, request: HttpRequest) -> QuerySet[Any]:
        return super().get_queryset(request).select_related(
            'assignment'
        ).prefetch_related('exchanges').annotate(num_exchanges=Count('exchanges'))


@admin.register(TutorEngagement)
class TutorEngagementAdmin(ReadOnlyMixin, admin.ModelAdmin):

    list_display = ('student', 'start', 'sessions', 'tasks', 'duration', 'view')
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
    
    def view(self, obj):
        return format_html(
            '<a href="{url}" target="_blank">view</a>',
            url=reverse('tutor_engagement_detail', kwargs={'pk': obj.pk})
        )


    def duration(self, obj):
        if obj.end:
            return obj.end - obj.start
        
    def sessions(self, obj):
        return obj.sessions.count()

    def tasks(self, obj):
        return obj.tasks

    inlines = [TutorSessionInlineAdmin,]

    def get_queryset(self, request: HttpRequest) -> QuerySet[Any]:
        return super().get_queryset(request).select_related(
            'repository',
            'repository__student'
        ).prefetch_related('sessions').annotate(tasks=Count('sessions__assignment', unique=True))

    def has_delete_permission(self, request, obj=None):
        return True


admin.register(TutorAPIKey)(admin.ModelAdmin)
