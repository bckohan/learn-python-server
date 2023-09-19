"""
Admin interface for all models in etc_player.
"""
from typing import Any
from django.contrib import admin
from django.db.models.query import QuerySet
from django.http.request import HttpRequest
from learn_python_server.models import (
    Course,
    Enrollment,
    StudentRepository,
    Student,
    CourseRepository,
    CourseRepositoryVersion,
    StudentRepositoryVersion,
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


class ReadOnlyMixin:
        
    def has_add_permission(self, request, obj=None):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
    

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

    def enrollment(self, obj):
        return obj.enrollments.count()
    
    def repo(self, obj):
        # return a link to obj.docs.url
        return format_html('<a href="{url}" target="_blank">{url}</a>', url=obj.repository) if obj.repository else None

    def docs(self, obj):
        # return a link to obj.docs.url
        return format_html('<a href="{url}" target="_blank">docs</a>', url=obj.docs.url) if obj.docs else None


# a tabular inline for enrollments
class StudentRepositoryInline(admin.TabularInline):
    model = StudentRepository
    extra = 0


# a custom admin for courses
@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):

    list_display = ('name', 'email', 'handle')
    search_fields = ('name', 'email', 'handle')
    ordering = ('name',)
    readonly_fields = ('joined',)
    inlines = [StudentRepositoryInline, EnrollmentInline]


@admin.register(CourseRepositoryVersion)
class CourseRepositoryVersionAdmin(ReadOnlyMixin, admin.ModelAdmin):

    list_display = ('repo', 'git_branch', 'git_hash', 'commit_count', 'timestamp')
    search_fields = ('repository__uri', 'repository__courses__name')
    ordering = ('-timestamp',)
    readonly_fields = ('timestamp', 'repository', 'git_branch', 'git_hash', 'commit_count')

    def repo(self, obj):
        return obj.repository.uri
    
    def get_queryset(self, request: HttpRequest) -> QuerySet[Any]:
        return super().get_queryset(request).select_related('repository')


@admin.register(StudentRepositoryVersion)
class StudentRepositoryVersionAdmin(ReadOnlyMixin, admin.ModelAdmin):

    list_display = ('repo', 'git_branch', 'git_hash', 'commit_count', 'timestamp')
    search_fields = ('repository__uri', 'repository__student__name')
    ordering = ('-timestamp',)
    readonly_fields = ('timestamp', 'repository', 'git_branch', 'git_hash', 'commit_count')

    def repo(self, obj):
        return obj.repository.uri
    
    def student(self, obj):
        return obj.repository.student.display
    
    def get_queryset(self, request: HttpRequest) -> QuerySet[Any]:
        return super().get_queryset(request).select_related('repository', 'repository__student')


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
        'todo', 'hints', 'requirements', 'test'
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

    def student_name(self, obj):
        return obj.student.display
    
    def get_queryset(self, request: HttpRequest) -> QuerySet[Any]:
        return super().get_queryset(request).select_related('student')

    def change_view(self, request, object_id, form_url='', extra_context=None):
        self.readonly_fields = ('student',)
        return super().change_view(request, object_id, form_url, extra_context)


admin.register(CourseRepository)(admin.ModelAdmin)
admin.register(TutorAPIKey)(admin.ModelAdmin)

admin.register(TutorExchange)(admin.ModelAdmin)
admin.register(TutorEngagement)(admin.ModelAdmin)
admin.register(TutorSession)(admin.ModelAdmin)
