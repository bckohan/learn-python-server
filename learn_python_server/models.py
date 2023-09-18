from typing import Any
from django.db import models
from django.conf import settings
from django_enum import EnumField
from enum_properties import EnumProperties, p, s
from django.utils.translation import gettext_lazy as _
from polymorphic.models import PolymorphicModel
from learn_python_server.utils import normalize_url
from django.core.exceptions import ValidationError, SuspiciousOperation
import subprocess
import os
from pathlib import Path
import re
import json


class TutorBackend(EnumProperties, p('uri')):

    OPEN_AI = 'openai', 'https://platform.openai.com/'


class TutorRole(EnumProperties, s('alt')):
    
    SYSTEM = 'system', ['system']
    TUTOR = 'tutor', ['assistant']
    STUDENT = 'student', ['user']


def repo_guard(func):
    """
    Make sure any repository functions are called within the context of the repository and
    do not pollute the server's runtime environment.
    """
    def wrapper(self, *args, **kwargs):

        # can't use the repo_guarded version b/c infinite recursion
        def venv():
            try:
                return Path(subprocess.check_output(
                    ['poetry', 'env', 'info', '--path']
                    ).decode().strip()
                )
            except subprocess.CalledProcessError:
                # this means poetry has not created a venv yet and since its
                # clearly not using the server runtime, we just return the local
                # repo clone directory so that our check can pass
                return self.local

        def security_check():
            repo_path = self.local
            repo_venv = venv()
            if not str(Path(repo_venv).resolve()).startswith(str(Path(repo_path).resolve())):
                raise SuspiciousOperation(_(
                    'Attempted to use virtual environment {} for repository at: {}'
                ).format(repo_venv, repo_path)
            )

        if self._in_context:
            security_check()
            return func(self, *args, **kwargs)
        else:
            with self:
                security_check()
                return func(self, *args, **kwargs)

    return wrapper


class Repository(models.Model):
    """
    A git repository. This is an abstract model that can be used to represent a git repository. It provides
    functions for cloning and retrieving basic information about the repo. The repository may be a specific
    branch on a repository. If that is the case the uri should be in the form of: <root_repo>/tree/<branch_name>

    Only tested on github right now but should probably also support gitlab.
    """

    BRANCH_RE = re.compile(r'tree/(?P<branch>.*)$')

    uri = models.URLField(
        max_length=255,
        db_index=True,
        unique=True,
        help_text=_('The Git repository URI. This may be a specific branch (i.e. tree/branch_name)')
    )

    branch = models.CharField(max_length=64, null=True)

    # repo execution context cache
    _cwd = None
    _venv = None
    _in_context = False
    _virtualenvs_in_project = None

    @property
    def root(self):
        """Get's the root repository without any branches"""
        return self.BRANCH_RE.sub('', self.uri).rstrip('/')

    def clean(self):
        super().clean()
        self.uri = normalize_url(self.uri)
        branch_match = self.BRANCH_RE.search(self.uri)
        if branch_match:
            if self.branch and self.branch != branch_match.groupdict()['branch']:
                raise ValidationError({
                    'branch': (
                        _('Branch value (%s) does not match uri branch: %s') % 
                        (self.branch, branch_match.groupdict()['branch'])
                    )
                })
            self.branch = branch_match.groupdict()['branch']

    _clone = None

    @property
    def local(self):
        return self._clone
    
    def clone(self, path):
        """
        Clone a Git repository into the specified directory.
        
        :param path: The path to clone the repository into.
        :return: The path to the cloned repository.
        :raises: subprocess.CalledProcessError if the Git command fails.
        """
        subprocess.check_call(['git', 'clone', self.uri, path])
        self._clone = Path(path)
        return self
    
    def commit_count(self):
        if not self.local or not self.local.exists():
            raise RuntimeError('Repository has not been cloned.')
        return int(
            subprocess.check_output(
                ['git', 'rev-list', '--all', '--count'],
                cwd=self.local
            ).strip()
        )
    
    def commit_hash(self):
        if not self.local or not self.local.exists():
            raise RuntimeError('Repository has not been cloned.')
        return subprocess.check_output(
            ['git', 'rev-parse', 'HEAD'],
            cwd=self.local
        ).strip().decode('utf-8')

    def cloned_branch(self):
        if not self.local or not self.local.exists():
            raise RuntimeError('Repository has not been cloned.')
        return subprocess.check_output(
            ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
            cwd=self.local
        ).strip().decode('utf-8')

    def __enter__(self):
        self._cwd = os.getcwd()
        os.chdir(self.local)
        self._venv = os.environ.pop('VIRTUAL_ENV', None)
        self._virtualenvs_in_project = subprocess.check_output(
            ['poetry', 'config', 'virtualenvs.in-project']
        ).strip().decode().lower() == 'true'
        subprocess.check_output(
            ['poetry', 'config', 'virtualenvs.in-project', 'true']
        )
        self._in_context = True
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        subprocess.check_output([
            'poetry',
            'config',
            'virtualenvs.in-project',
            'true' if self._virtualenvs_in_project else 'false'
        ])
        os.chdir(self._cwd)
        if self._venv:
            os.environ['VIRTUAL_ENV'] = self._venv
        self._in_context = False

    @repo_guard
    def venv(self):
        return Path(subprocess.check_output(
            ['poetry', 'env', 'info', '--path']
            ).decode().strip()
        )

    @repo_guard
    def install(self):
        return subprocess.check_output(['poetry', 'install']).decode().strip()

    @repo_guard
    def doc_build(self, *args):
        return Path(subprocess.check_output(
            ['poetry', 'run', 'doc', 'build', *(args or ['--detached'])
        ]).decode().strip().split('\n')[-1])

    @repo_guard
    def course_structure(self):
        # sphinx is extremely chatty and despite best efforts it might pollute stdout with some
        # garbage - it caches lots of things so if we error out the first time, try once more 
        # just incase, caching eliminates the problem
        def do_get():
            return json.loads(
                subprocess.check_output(
                    ['poetry', 'run', 'doc', 'structure']
                ).decode().strip() or '{}'
            )
        try:
            return do_get()
        except json.JSONDecodeError:
            return do_get()

    def __str__(self):
        return self.uri

    class Meta:
        abstract = True


class RepositoryVersion(models.Model):

    git_hash = models.CharField(max_length=255, null=False)
    git_branch = models.CharField(max_length=255, null=False, default='main')
    commit_count = models.PositiveIntegerField(null=False, default=0, db_index=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    def __str__(self):
        return f'[{self.git_branch}] ({self.timestamp}) {self.git_hash}'

    class Meta:
        abstract = True
        ordering = ['-commit_count']
        unique_together = [('git_hash', 'git_branch')]


class TutorAPIKey(models.Model):

    backend = EnumField(TutorBackend)
    secret = models.CharField(max_length=255)


class CourseRepository(Repository):
    pass


class CourseRepositoryVersion(RepositoryVersion):

    repository = models.ForeignKey('CourseRepository', on_delete=models.CASCADE)


class DocBuild(models.Model):

    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    repository = models.ForeignKey('CourseRepositoryVersion', on_delete=models.PROTECT)

    @property
    def path(self):
        return Path(settings.STATIC_ROOT) / 'docs' / str(self.id)

    def __str__(self):
        return f'[{self.repository}] {self.path}'

class Course(models.Model):

    name = models.CharField(max_length=255, unique=True, db_index=True)
    description = models.TextField(null=False, default='', blank=True)
    started = models.DateTimeField(auto_now_add=True)
    ended = models.DateTimeField(null=True, blank=True, default=None)

    repository = models.ForeignKey(CourseRepository, on_delete=models.PROTECT, related_name='courses')
    docs = models.ForeignKey(DocBuild, on_delete=models.SET_NULL, null=True, blank=True)

    students = models.ManyToManyField('Student', related_name='courses', through='Enrollment')

    tutor_key = models.ForeignKey(
        'TutorAPIKey',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text=_('API key for the Tutor backend, specifically for this course.')
    )

    def __str__(self):
        return f'[{self.id}] {self.name}: {self.repository.uri}'
    
    class Meta:
        ordering = ['-started']


class Enrollment(models.Model):

    student = models.ForeignKey('Student', on_delete=models.CASCADE)
    course = models.ForeignKey('Course', on_delete=models.CASCADE)
    repository = models.ForeignKey('StudentRepository', on_delete=models.CASCADE, null=True, blank=True)
    joined = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        unique_together = [('student', 'repository'), ('student', 'course')]


class StudentRepository(Repository):
    student = models.ForeignKey('Student', on_delete=models.CASCADE, related_name='repositories')


class StudentRepositoryVersion(RepositoryVersion):

    repository = models.ForeignKey('StudentRepository', on_delete=models.CASCADE)


class Student(models.Model):

    name = models.CharField(max_length=255, null=True)
    email = models.EmailField(null=True)
    github = models.CharField(max_length=255, null=False, unique=True)
    joined = models.DateTimeField(auto_now_add=True)

    tutor_key = models.ForeignKey(
        'TutorAPIKey',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text=_(
            'API key for the Tutor backend, specifically for this student '
            '- will override any associated class tutor key.'
        )
    )

    @property
    def name(self):
        return self.name or self.github


class TutorExchange(models.Model):

    role = EnumField(TutorRole)
    message = models.TextField(null=False, editable=False)
    timestamp = models.DateTimeField(null=False, db_index=True)

    session = models.ForeignKey('TutorSession', on_delete=models.CASCADE)

    backend_extra = models.JSONField(null=True, blank=True)

    class Meta:
        ordering = ['timestamp']


class TutorSession(models.Model):
    
    session_id = models.PositiveSmallIntegerField(null=False, db_index=True)
    start = models.DateTimeField(null=False, db_index=True)
    end = models.DateTimeField(null=False)

    engagement = models.ForeignKey('TutorEngagement', on_delete=models.CASCADE)

    assignment = models.ForeignKey(
        'Assignment',
        on_delete=models.SET_NULL,
        null=True,
        default=None
    )

    class Meta:
        ordering = ['start']
        unique_together = [('engagement', 'session_id')]


class TutorEngagement(models.Model):

    id = models.UUIDField(primary_key=True)
    start = models.DateTimeField(null=False, db_index=True)
    end = models.DateTimeField(null=False)

    log = models.FileField(null=True, blank=True)

    backend = EnumField(TutorBackend)
    backend_extra = models.JSONField(null=True, blank=True)

    repository = models.ForeignKey('StudentRepositoryVersion', on_delete=models.CASCADE)

    class Meta:
        ordering = ['-start']


class Module(PolymorphicModel):

    name = models.CharField(max_length=64, null=False, blank=True, default='')
    number = models.PositiveSmallIntegerField(null=True)
    topic = models.CharField(max_length=255, null=False, blank=True, default='')
    description = models.TextField(null=False, blank=True, default='')

    repository = models.ForeignKey('CourseRepository', on_delete=models.CASCADE)

    added = models.ForeignKey(
        CourseRepositoryVersion,
        on_delete=models.PROTECT,
        related_name='modules_added'
    )
    removed = models.ForeignKey(
        CourseRepositoryVersion,
        on_delete=models.PROTECT,
        null=True,
        default=None,
        blank=True,
        related_name='modules_removed'
    )

    def __str__(self):
        return self.name
    
    class Meta:
        ordering = ['number']
        unique_together = [('repository', 'number')]


class SpecialTopic(Module):

    uri = models.URLField(max_length=255, null=False)


class Assignment(models.Model):

    module = models.ForeignKey('Module', on_delete=models.CASCADE)

    added = models.ForeignKey(
        CourseRepositoryVersion,
        on_delete=models.PROTECT,
        related_name='assignments_added'
    )

    removed = models.ForeignKey(
        CourseRepositoryVersion,
        on_delete=models.PROTECT,
        null=True,
        default=None,
        blank=True,
        related_name='assignments_removed'
    )

    # the number can change!
    number = models.PositiveSmallIntegerField(null=False, db_index=True)
    name = models.CharField(max_length=255, null=False, db_index=True)

    todo = models.TextField(null=False, blank=True, default='')
    hints = models.TextField(null=False, blank=True, default='')
    requirements = models.TextField(null=False, blank=True, default='')

    test = models.CharField(max_length=255, null=False)

    def __str__(self):
        return f'[{self.module}] ({self.number}) {self.name}'

    class Meta:
        ordering = ['number']
        unique_together = [('module', 'name')]
