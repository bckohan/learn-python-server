import base64
import gzip
import json
import os
import re
import subprocess
import time
from collections.abc import MutableMapping
from pathlib import Path
from typing import Any, Optional, TextIO

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives import (
    serialization as crypto_serialization,
)
from cryptography.hazmat.primitives.asymmetric import padding
from dateutil.parser import ParserError
from dateutil.parser import parse as ts_parse
from django.apps import apps
from django.conf import settings
from django.contrib.auth.models import (
    AbstractUser,
    PermissionsMixin,
    UserManager,
)
from django.core.exceptions import SuspiciousOperation, ValidationError
from django.core.validators import MaxLengthValidator, MinLengthValidator
from django.db import models
from django.utils.functional import cached_property
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from django_enum import EnumField, IntegerChoices, TextChoices
from enum_properties import p, s
from learn_python_server.utils import TemporaryDirectory, normalize_url
from polymorphic.models import PolymorphicManager, PolymorphicModel


def NON_POLYMORPHIC_CASCADE(collector, field, sub_objs, using):
    return models.CASCADE(collector, field, sub_objs.non_polymorphic(), using)


class Domain(IntegerChoices, s('url')):

    GITHUB = 0, 'github', 'https://github.com'
    #GITLAB = 1, 'gitlab', 'https://gitlab.com'


class PolymorphicUserManager(PolymorphicManager, UserManager):
    pass


class User(PolymorphicModel, AbstractUser, PermissionsMixin):
    """
    Adapt abstract django user to our purposes. first_name and last_name are not
    culturally universal so we smash them into a single full_name field. We also
    do not require an email address.
    """

    objects = PolymorphicUserManager()

    @property
    def first_name(self):
        if self.full_name:
            return self.full_name.split()[0]
        return ''
    
    @property
    def last_name(self):
        names = self.full_name.split()
        if len(names) > 1:
            return names[-1]
        return ''
    
    full_name = models.CharField(_("full name"), max_length=255, blank=True, default='')
    email = models.EmailField(_("email address"), blank=True, null=True)

    EMAIL_FIELD = 'email'
    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = []

    def get_full_name(self):
        return self.full_name.strip()

    def get_short_name(self):
        return self.first_name

    def email_user(self, subject, message, from_email=None, **kwargs):
        if self.email:
            super().send_mail(subject, message, from_email, [self.email], **kwargs)


class TutorBackend(TextChoices, p('uri')):

    TEST    = 'test',   None
    OPEN_AI = 'openai', 'https://platform.openai.com/'

    def __str__(self):
        return self.value


class TutorRole(TextChoices, s('alt')):
    
    SYSTEM  = 'system',  ['system']
    TUTOR   = 'tutor',   ['assistant']
    STUDENT = 'student', ['user']


def datetime_now():
    return now()


def date_now():
    return now().date()


def repo_guard(func):
    """
    Make sure any repository functions are called within the context of the repository and
    do not pollute the server's runtime environment.

    .. warning::

        Executing code from the wild on a server is extremely dangerous! In the future
        we should run this code in some sort of sandboxed environment like a highly
        secure container or VM. For now it is critical that if you're running a 
        learn-python-server that you have 100% confidence you know that the code in 
        the course repository is safe. NEVER run student code on the server without
        further safety precautions and at minimum isolating it's runtime from the network
        and host kernel.
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


class Repository:
    """
    A git repository. This is an abstract model that can be used to represent a git repository. It provides
    functions for cloning and retrieving basic information about the repo. The repository may be a specific
    branch on a repository. If that is the case the uri should be in the form of: <root_repo>/tree/<branch_name>

    Only tested on github right now but should probably also support gitlab.
    """

    BRANCH_RE = re.compile(r'(?:tree/(?P<branch>.*))?$')
    URI_RE = re.compile('https://(?P<domain>github).com/(?P<handle>[^/]+)/(?P<repo>[^/]+)(?:/tree/(?P<branch>.*))?$')

    @staticmethod
    def is_valid(uri):
        return Repository.URI_RE.match(uri)
    
    uri: str = ''

    def __init__(self, uri):
        self.uri = uri

    # repo execution context cache
    _cwd = None
    _venv = None
    _in_context = False
    _virtualenvs_in_project = None

    def path(self, stem):
        """
        Get a path relative to the repository root.
        
        :param args: The path segments to join.
        :return: The joined path.
        """
        assert self.local, 'Repository has not been cloned.'
        return self.local / Path(stem)

    @property
    def root(self):
        """Get's the root repository without any branches"""
        return self.BRANCH_RE.sub('', self.uri).rstrip('/')
    
    @cached_property
    def branch(self):
        """Get's the branch name from the uri"""
        self.BRANCH_RE.search(self.uri).groupdict()['branch']
    
    @cached_property
    def handle(self):
        """Get's the user handle name from the uri"""
        return self.URI_RE.search(self.uri).groupdict()['handle']

    @cached_property
    def name(self):
        """Get's the repo name from the uri"""
        return self.URI_RE.search(self.uri).groupdict()['repo']
    
    def clean(self):
        super().clean()
        self.uri = normalize_url(self.uri)
        if not self.URI_RE.match(self.uri):
            raise ValidationError({
                'uri': _('Invalid repository URI. Only github supported currently.')
            })

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
        subprocess.check_call(['git', 'clone', self.root, path])
        self._clone = Path(path)
        if self.branch:
            # todo checkout branch
            subprocess.check_call(['git', 'checkout', self.branch])
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
        if not self.local:
            self._tmp_dir = TemporaryDirectory()
            self.clone(self._tmp_dir.__enter__())
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
        return self
    
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
        if hasattr(self, '_tmp_dir'):
            self._tmp_dir.__exit__(exc_type, exc_val, exc_tb)
            del self._tmp_dir

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


class RepositoryModel(Repository, models.Model):

    def __init__(self, *args, **kwargs):
        models.Model.__init__(self, *args, **kwargs)

    uri = models.URLField(
        max_length=255,
        db_index=True,
        unique=True,
        help_text=_('The Git repository URI. This may be a specific branch (i.e. tree/branch_name)')
    )

    def __str__(self):
        return self.uri

    class Meta:
        abstract = True


class RepositoryVersion(models.Model):

    git_hash = models.CharField(max_length=255, null=False)
    git_branch = models.CharField(max_length=255, null=False, default='main')
    commit_count = models.PositiveIntegerField(null=False, default=0, db_index=True)
    timestamp = models.DateTimeField(default=datetime_now, db_index=True)

    def __str__(self):
        return f'[{self.git_branch}] ({self.timestamp.date()}) {self.git_hash[:10]}'

    class Meta:
        abstract = True
        ordering = ['-commit_count']


class TutorAPIKey(models.Model):

    name = models.CharField(max_length=64, null=False, unique=True)
    backend = EnumField(TutorBackend)
    secret = models.CharField(max_length=255)

    def __str__(self):
        return f'[{self.backend.value}] {self.name}'

    class Meta:
        verbose_name = _('Tutor API Key')
        verbose_name_plural = _('Tutor API Keys')


class CourseRepository(RepositoryModel):
    
    class Meta:
        verbose_name = _('Course Repository')
        verbose_name_plural = _('Course Repositories')


class CourseRepositoryVersion(RepositoryVersion):

    repository = models.ForeignKey(
        CourseRepository,
        on_delete=models.CASCADE,
        related_name='versions'
    )

    def __str__(self):
        return f'{self.repository}: {RepositoryVersion.__str__(self)}'
    
    class Meta:
        verbose_name = _('Course Repository Version')
        verbose_name_plural = _('Course Repository Versions')
        unique_together = [('repository', 'git_hash', 'git_branch')]


class DocBuild(models.Model):

    timestamp = models.DateTimeField(default=datetime_now, db_index=True)
    repository = models.ForeignKey(CourseRepositoryVersion, on_delete=models.PROTECT)

    @property
    def sub_dir(self):
        return f'docs/{self.id}'

    @property
    def path(self):
        return Path(settings.STATIC_ROOT) / self.sub_dir
    
    @property
    def url(self):
        root = str(Path(settings.STATIC_URL) / self.sub_dir)
        if settings.DEBUG:
            return f'{root}/index.html'
        return root

    def __str__(self):
        return f'[{self.repository}] {self.path}'

    class Meta:
        verbose_name = _('Doc Build')
        verbose_name_plural = _('Doc Builds')


class Course(models.Model):

    name = models.CharField(max_length=255, unique=True, db_index=True)
    description = models.TextField(null=False, default='', blank=True)
    started = models.DateField(default=date_now, editable=True)
    ended = models.DateField(null=True, blank=True, default=None)

    repository = models.ForeignKey(CourseRepository, on_delete=models.PROTECT, related_name='courses')

    students = models.ManyToManyField('Student', related_name='courses', through='Enrollment')

    tutor_key = models.ForeignKey(
        'TutorAPIKey',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text=_('API key for the Tutor backend, specifically for this course.')
    )

    @property
    def docs(self):
        return DocBuild.objects.filter(repository__repository=self.repository).latest('timestamp')

    def __str__(self):
        if self.name:
            return self.name
        return self.repository.uri
    
    class Meta:
        ordering = ['-started']
        verbose_name = _('Course')
        verbose_name_plural = _('Courses')


class Enrollment(models.Model):

    student = models.ForeignKey('Student', on_delete=models.CASCADE, related_name='enrollments')
    course = models.ForeignKey('Course', on_delete=models.CASCADE, related_name='enrollments')
    repository = models.OneToOneField(
        'StudentRepository',
        on_delete=models.CASCADE,
        related_name='enrollment'
    )
    joined = models.DateTimeField(default=datetime_now)
    last_activity = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        self.student = self.repository.student
        super().save(*args, **kwargs)

    class Meta:
        unique_together = [('student', 'repository'), ('student', 'course')]
        verbose_name = _('Enrollment')
        verbose_name_plural = _('Enrollments')


class StudentRepositoryManager(models.Manager):

    @staticmethod
    def student_from_uri(uri):
        uri_match = Repository.is_valid(uri)
        if uri_match:
            return Student.objects.get_or_create(
                domain=uri_match.groupdict()['domain'],
                handle=uri_match.groupdict()['handle']
            )[0]
        return None

    def get_or_create(self, **kwargs):
        if 'student' not in kwargs:
            kwargs['student'] = self.student_from_uri(kwargs.get('uri', None))
        return super().get_or_create(**kwargs)

    def create(self, **kwargs):
        if 'student' not in kwargs:
            kwargs['student'] = self.student_from_uri(kwargs.get('uri', None))
        return super().create(**kwargs)


class StudentRepository(RepositoryModel):

    student = models.ForeignKey(
        'Student',
        on_delete=models.CASCADE,
        related_name='repositories',
        blank=True
    )

    objects = StudentRepositoryManager()

    @cached_property
    def course_repository(self):
        if hasattr(self, 'enrollment') and self.enrollment:
            return self.enrollment.course.repository

    def clean(self):
        super().clean()
        if not hasattr(self, 'student') or self.student is None:
            self.student = StudentRepositoryManager.student_from_uri(self.uri)
        if self.student and self.student.handle != self.handle:
            raise ValidationError({
                'handle': _('Handle {} does not belong to student {}.').format(self.handle, self.student.display)
            })
    
    def synchronize_keys(self):
        keys = []
        with self:
            key_file = self.path('public_keys.pem')
            if key_file.is_file():
                with open(key_file, 'rb') as f:
                    pem_data = f.read().decode()
                
                # Splitting the keys based on PEM headers/footers
                pem_keys = [
                    f"-----BEGIN {m[1]}-----{m[2]}-----END {m[1]}-----"
                    for m in re.findall(
                        r"(-----BEGIN (.*?)-----)(.*?)(-----END \2-----)",
                        pem_data,
                        re.S
                    )
                ]

                keys = [
                    crypto_serialization.load_pem_public_key(
                        pem.encode(),
                        backend=default_backend()
                    ) for pem in pem_keys
                ]

        all_keys = set()
        new_keys = set()
        for key in keys:
            key, created = StudentRepositoryPublicKey.objects.get_or_create(
                repository=self,
                key=key.public_bytes(
                    encoding=crypto_serialization.Encoding.PEM,
                    format=crypto_serialization.PublicFormat.SubjectPublicKeyInfo
                )
            )
            if created:
                new_keys.add(key)
            all_keys.add(key)
        
        # remove old keys
        removed = StudentRepositoryPublicKey.objects.filter(
            repository=self
        ).exclude(pk__in=[key.pk for key in all_keys])
        removed.delete()
        return all_keys, new_keys, set(removed)

    def verify(self, request):
        """
        Verify that the request has been signed by a clone of this student's repository.
        We use a timestamp signing scheme to prevent replay attacks.
        """
        timestamp = request.META.get('HTTP_X_LEARN_PYTHON_TIMESTAMP', None)
        signature = request.META.get('HTTP_X_LEARN_PYTHON_SIGNATURE', None)
        if timestamp and signature:
            try:
                timestamp = int(timestamp)
            except (TypeError, ValueError):
                return False
            if abs(int(time.time()) - timestamp) > settings.LP_REQUEST_TIMEOUT:
                return False
            return any((key.verify(str(timestamp), signature) for key in self.keys.all()))
        return False

    def get_tutor_key(self):
        """Get the tutor backend and api key this repository should use, if any."""
        tutor_api_key = None
        if hasattr(self, 'enrollment') and self.enrollment:
            tutor_api_key = self.enrollment.course.tutor_key
        if self.student.tutor_key:
            tutor_api_key = self.student.tutor_key
        return tutor_api_key
    
    class Meta:
        verbose_name = _('Student Repository')
        verbose_name_plural = _('Student Repositories')


class StudentRepositoryPublicKey(models.Model):

    repository = models.ForeignKey(
        'StudentRepository',
        on_delete=models.CASCADE,
        related_name='keys'
    )
    key = models.BinaryField()
    timestamp = models.DateTimeField(default=datetime_now, db_index=True)

    @cached_property
    def key_str(self):
        return crypto_serialization.load_pem_public_key(
            self.key,
            backend=default_backend()
        ).public_bytes(
            encoding=crypto_serialization.Encoding.PEM,
            format=crypto_serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode('utf-8')

    def verify(self, message: str, signature: str) -> bool:
        """
        Verify that the given message has been signed by the corresponding private key.
        
        :param message: The str message to verify
        :param signature: The base64 encoded signature
        :return: True if the message was signed by the private key corresponding
            to this public key.
        """
        # load public key from binary field
        public_key = crypto_serialization.load_pem_public_key(
            self.key,
            backend=default_backend()
        )
        try:
            public_key.verify(
                base64.b64decode(signature),
                message.encode(),
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            return True
        except InvalidSignature:
            return False

    def __str__(self):
        return f'{self.repository}: {self.timestamp}'

    class Meta:
        ordering = ['-timestamp']
        verbose_name = _('Student Repository Public Key')
        verbose_name_plural = _('Student Repository Public Keys')


class Student(User):
    """
    This is a special user type that is used to authenticate student repositories using
    the repository attestation method.
    """
    domain = EnumField(Domain)

    handle = models.CharField(
        max_length=255,
        null=False,
        unique=True,
        help_text=_('The student\'s GitHub handle.')
    )

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

    login_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        default=None,
        related_name='students',
        help_text=_('The login user account associated with this student, if any.')
    )

    def clean(self):
        # student users cannot login via a password
        self.set_unusable_password()
        self.username = f'{self.domain.label}/{self.handle}'
        super().clean()

    @property
    def display(self):
        return self.full_name or self.handle
    
    @property
    def authorized_repository(self):
        """If this student is authenticated, this will be the StudentRepository they are authorized with."""
        return self._authorized_repository
    
    @authorized_repository.setter
    def authorized_repository(self, repo):
        if repo is not None:
            # some sanity checks
            assert isinstance(repo, StudentRepository)
            assert repo.student == self
        self._authorized_repository = repo

    def __str__(self):
        return self.display

    class Meta:
        verbose_name = _('Student')
        verbose_name_plural = _('Students')


class TimelineEvent(PolymorphicModel):

    timestamp = models.DateTimeField(null=False, db_index=True)
    repository = models.ForeignKey(
        'StudentRepository',
        on_delete=models.CASCADE,
        related_name='timeline_events'
    )

    class Meta:
        ordering = ('-timestamp',)
        index_together = [('timestamp', 'repository')]
        unique_together = [('timestamp', 'repository')]


class TutorExchange(models.Model):

    role = EnumField(TutorRole)
    content = models.TextField(null=False)
    is_function_call = models.BooleanField(null=False, default=False)
    timestamp = models.DateTimeField(null=False, db_index=True)

    session = models.ForeignKey(
        'TutorSession',
        on_delete=models.CASCADE,
        related_name='exchanges'
    )

    backend_extra = models.JSONField(null=True, blank=True)

    class Meta:
        ordering = ['timestamp']
        verbose_name = _('Tutor Exchange')
        verbose_name_plural = _('Tutor Exchanges')
        unique_together = [('timestamp', 'session')]
        ordering = ('timestamp',)


class ToolRun(TimelineEvent):

    class Tools(TextChoices, s('alt')):

        _symmetric_builtins_ = [
            s('name', case_fold=True),
            s('label', case_fold=True)
        ]

        TUTOR  = 'tutor',  'tutor',  ['delphi']
        PYTEST = 'pytest', 'pytest', []
        DOCS   = 'docs',   'docs',   []
    
    stop = models.DateTimeField(null=False)

    tool = EnumField(Tools, strict=False, db_index=True)

    @property
    def start(self):
        return self.timestamp


class TutorSession(TimelineEvent):
    
    session_id = models.PositiveSmallIntegerField(null=False, db_index=True)
    stop = models.DateTimeField(null=False)

    engagement = models.ForeignKey(
        'TutorEngagement',
        on_delete=models.CASCADE,
        related_name='sessions'
    )

    assignment = models.ForeignKey(
        'Assignment',
        on_delete=models.SET_NULL,
        null=True,
        default=None
    )

    class Meta:
        unique_together = [('engagement', 'session_id')]
        verbose_name = _('Tutor Session')
        verbose_name_plural = _('Tutor Sessions')

    def __str__(self):
        return str(self.session_id)


class TutorEngagement(ToolRun):

    engagement_id = models.UUIDField(null=False, unique=True)

    tz_name = models.CharField(max_length=64, default='')
    tz_offset = models.SmallIntegerField(null=True, default=None)

    log = models.ForeignKey(
        'LogFile',
        null=True,
        default=None,
        related_name='engagement',
        on_delete=models.SET_NULL
    )

    backend = EnumField(TutorBackend)
    backend_extra = models.JSONField(null=True, blank=True)
        
    def __str__(self):
        return f'[{self.timestamp}] {self.repository.student.display}'

    class Meta:
        verbose_name = _('Tutor Engagement')
        verbose_name_plural = _('Tutor Engagements')


class Module(PolymorphicModel):

    name = models.CharField(max_length=64, null=False, blank=True, default='')
    number = models.PositiveSmallIntegerField(null=True)
    topic = models.CharField(max_length=255, null=False, blank=True, default='')
    description = models.TextField(null=False, blank=True, default='')

    repository = models.ForeignKey(
        'CourseRepository',
        on_delete=models.CASCADE,
        related_name='modules'
    )

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
        verbose_name = _('Module')
        verbose_name_plural = _('Modules')


class SpecialTopic(Module):

    uri = models.URLField(max_length=255, null=False)

    class Meta:
        verbose_name = _('Special Topic')
        verbose_name_plural = _('Special Topics')


class Assignment(models.Model):

    module = models.ForeignKey('Module', on_delete=models.CASCADE, related_name='assignments')

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

    identifier = models.CharField(max_length=255, null=False)

    def __str__(self):
        return f'[{self.module}] ({self.number}) {self.name}'

    class Meta:
        ordering = ['number']
        unique_together = [('module', 'name')]
        verbose_name = _('Assignment')
        verbose_name_plural = _('Assignments')


class LogFileManager(models.Manager):
    pass


_DEFAULT_REGEX = re.compile(
    r'^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}.\d{6}[+-]{1}\d{4}) - '
    r'(?P<logger>\w+) - (?:\[(?P<level_no>\d+)\])?(?P<level>\w+) - (?P<message>.*)'
)

class LogFile(models.Model):

    objects = LogFileManager()

    class LogFileType(IntegerChoices, s('prefix'), p('regexes')):
        
        UNKNOWN = 0, 'Unknown', None,           [_DEFAULT_REGEX]
        GENERAL = 1, 'General', 'learn_python', [_DEFAULT_REGEX]
        TESTING = 2, 'Testing', 'testing',      [_DEFAULT_REGEX, 
                                                 re.compile(r'\[(?P<result>[\w]+)\] (?P<identifier>learn_python/tests/[\w]+.py::test_[\w]+)'),
                                                 re.compile(r'\[START\] (?P<start>[\w]+)'),
                                                 re.compile(r'\[STOP\] (?P<stop>[\w]+)')
                                                ]
        TUTOR   = 3, 'Tutor',   'delphi',       [_DEFAULT_REGEX]

        def unmarshall(self, params):
            if params:
                try:
                    params['timestamp'] = ts_parse(params['timestamp'])
                except ParserError:
                    pass
                try:
                    params['level'] = (
                        params.get('level_no', None) or
                        LogEvent.LogLevel(params.get('level', None)) or 
                        LogEvent.LogLevel(params.get('level_no', None))
                    )
                except ValueError:
                    params['level'] = LogEvent.LogLevel.NOTSET
                if isinstance(params['level'], str):
                    params['level'] = int(params['level'])
            return params

    sha256_hash = models.CharField(
        max_length=64,
        null=False,
        validators=[MinLengthValidator(64), MaxLengthValidator(64)]
    )

    repository = models.ForeignKey(StudentRepository, on_delete=models.CASCADE)
    type = EnumField(LogFileType, db_index=True, blank=True, default=LogFileType.UNKNOWN)
    log = models.FileField(upload_to='log_uploads', null=True, default=None)
    date = models.DateField(null=True, db_index=True, blank=True)
    uploaded_at = models.DateTimeField(default=datetime_now, db_index=True)
    num_lines = models.PositiveIntegerField(null=False, default=0)
    processed = models.BooleanField(
        null=False,
        default=False,
        db_index=True,
        blank=True,
        help_text=_('Whether or not the events have been scraped from the log file.')
    )

    class LogIterator:
        """
        Iterate over each message in the log file. Each message is a dictionary of 
        parameters returned by the corresponding log regex.
        """
        log_file = None

        file_handle: Optional[TextIO] = None

        # we need to lookhead b/c multi line messages are possible
        next_line: Optional[str] = None
        line_no: int = -1

        def __init__(self, log_file):
            self.log_file = log_file
            log_file = Path(log_file.log.path)
            if log_file.is_file():
                if str(log_file).endswith('.gz'):
                    self.file_handle = gzip.open(log_file, 'rt', encoding='utf-8')
                else:
                    self.file_handle = open(log_file, 'rt', encoding='utf-8')
                self.next_line = self.file_handle.readline()
                self.line_no += 1

        def readline(self):
            self.next_line = self.file_handle.readline()
            self.next_line_match = self.log_file.type.regexes[0].search(self.next_line)
            self.line_no += 1
            return self.next_line
        
        def __next__(self):
            if self.file_handle is None or not self.next_line:
                raise StopIteration
            
            match = self.log_file.type.regexes[0].search(self.next_line)
            if not match:
                self.readline()
                return {}
            
            def additional_params():
                for regex in self.log_file.type.regexes[1:]:
                    if match := regex.search(self.next_line):
                        params.update(match.groupdict())
                        break

            params = match.groupdict()
            additional_params()
            params['line_begin'] = self.line_no
            while (next_line := self.readline()) and self.next_line_match is None:
                params.setdefault('message', '')
                params['message'] += f'\n{next_line}'
                additional_params()
            
            params['line_end'] = self.line_no
            return self.log_file.type.unmarshall(params)
        
    def __iter__(self):
        return self.LogIterator(self)
    
    def __str__(self):
        return Path(self.log.path).name

    class Meta:
        ordering = ('-date', '-uploaded_at')
        verbose_name = _('Log File')
        verbose_name_plural = _('Log Files')
        index_together = (('repository', 'sha256_hash'),)
        unique_together = (('repository', 'sha256_hash'),)


class LogEvent(TimelineEvent):

    class LogLevel(IntegerChoices, p('color'), s('alts')):

        _symmetric_builtins_ = (s('label', case_fold=True),)

        NOTSET    = 0,  'NOTSET',   '#9c9c9c', []
        DEBUG     = 10, 'DEBUG',    '#e342f5', []
        INFO      = 20, 'INFO',     '#4287f5', []
        WARN      = 30, 'WARN',     '#f0d805', ['WARNING']
        ERROR     = 40, 'ERROR',    '#cc0000', ['EXCEPTION']
        CRITICAL  = 50, 'CRITICAL', '#cc0000', ['FATAL']

        def __str__(self):
            return self.label

        def __lt__(self, other):
            return self.value < other.value
        
        def __lte__(self, other):
            return self.value <= other.value
        
        def __gt__(self, other):
            return self.value > other.value
        
        def __gte__(self, other):
            return self.value >= other.value

    level = EnumField(LogLevel, db_index=True, strict=False)

    line_begin = models.PositiveIntegerField()
    line_end = models.PositiveIntegerField()

    log = models.ForeignKey(
        LogFile,
        on_delete=NON_POLYMORPHIC_CASCADE,
        related_name='events',
        null=True,
        default=None
    )
    message = models.TextField(null=False, blank=True, default='')
    logger = models.CharField(null=False, blank=True, default='', max_length=128)

    class Meta:
        verbose_name = 'Log Event'
        verbose_name_plural = 'Log Events'


class TestEvent(LogEvent):

    class Runner(IntegerChoices, s('alts', case_fold=True)):

        _symmetric_builtins_ = (s('label', case_fold=True),)

        TUTOR   = 1, 'Tutor',                  ['delphi']
        PYTEST  = 2, 'Pytest',                 ['test']
        DOCS    = 3, 'Docs',                   ['doc', 'sphinx']
        CI      = 4, 'Continuous Integration', ['ci']
        SERVER  = 5, 'Server',                 []

        def __str__(self):
            return self.label
        
    class Result(IntegerChoices, p('color'), s('alts', case_fold=True)):

        _symmetric_builtins_ = (s('label', case_fold=True),)

        PASSED   = 0, 'Passed',  '#02a102', ['pass']
        FAILED   = 1, 'Failed',  '#cc0000', ['fail', 'failure']
        ERRORED  = 2, 'Errored', '#cc0000', ['error']
        SKIPPED  = 3, 'Skipped', '#f0d805', ['skip']

        def __str__(self):
            return self.label
        
    runner = EnumField(Runner, db_index=True, null=True, default=None)
    result = EnumField(Result, db_index=True)

    assignment = models.ForeignKey(
        Assignment,
        related_name='tests',
        on_delete=models.CASCADE
    )

    class Meta:
        ordering = ['-timestamp']
        verbose_name = _('Test Event')
        verbose_name_plural = _('Test Events')
