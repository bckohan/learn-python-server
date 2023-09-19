from collections.abc import MutableMapping
from typing import Any
from django.db import models
from django.conf import settings
from django_enum import EnumField
from enum_properties import EnumProperties, p, s
from django_enum import TextChoices
from django.utils.translation import gettext_lazy as _
from polymorphic.models import PolymorphicModel
from learn_python_server.utils import normalize_url
from django.core.exceptions import ValidationError, SuspiciousOperation
import subprocess
import os
from pathlib import Path
import re
import json
from django.utils.timezone import now
from django.utils.functional import cached_property
import tempfile
from cryptography.hazmat.primitives import serialization as crypto_serialization


class TutorBackend(TextChoices, p('uri')):

    OPEN_AI = 'openai', 'https://platform.openai.com/'

    def __str__(self):
        return self.value


class TutorRole(TextChoices, s('alt')):
    
    SYSTEM = 'system', ['system']
    TUTOR = 'tutor', ['assistant']
    STUDENT = 'student', ['user']


def datetime_now():
    return now()


def date_now():
    return now().date()


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

    BRANCH_RE = re.compile(r'(?:tree/(?P<branch>.*))?$')
    URI_RE = re.compile('https://github.com/(?P<handle>[^/]+)/(?P<repo>[^/]+)(?:/tree/(?P<branch>.*))?$')

    uri = models.URLField(
        max_length=255,
        db_index=True,
        unique=True,
        help_text=_('The Git repository URI. This may be a specific branch (i.e. tree/branch_name)')
    )

    # repo execution context cache
    _cwd = None
    _venv = None
    _in_context = False
    _virtualenvs_in_project = None

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
    timestamp = models.DateTimeField(default=datetime_now, db_index=True)

    def __str__(self):
        return f'[{self.git_branch}] ({self.timestamp.date()}) {self.git_hash[:10]}'

    class Meta:
        abstract = True
        ordering = ['-commit_count']
        unique_together = [('git_hash', 'git_branch')]


class TutorAPIKey(models.Model):

    name = models.CharField(max_length=64, null=False, unique=True)
    backend = EnumField(TutorBackend)
    secret = models.CharField(max_length=255)

    def __str__(self):
        return f'[{self.backend.value}] {self.name}'

    class Meta:
        verbose_name = _('Tutor API Key')
        verbose_name_plural = _('Tutor API Keys')


class CourseRepository(Repository):
    
    class Meta:
        verbose_name = _('Course Repository')
        verbose_name_plural = _('Course Repositories')


class CourseRepositoryVersion(RepositoryVersion):

    repository = models.ForeignKey(CourseRepository, on_delete=models.CASCADE)

    def __str__(self):
        return f'{self.repository}: {RepositoryVersion.__str__(self)}'
    
    class Meta:
        verbose_name = _('Course Repository Version')
        verbose_name_plural = _('Course Repository Versions')


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
        return f'[ {self.name} ]: {self.repository.uri}'
    
    class Meta:
        ordering = ['-started']
        verbose_name = _('Course')
        verbose_name_plural = _('Courses')


class Enrollment(models.Model):

    student = models.ForeignKey('Student', on_delete=models.CASCADE, related_name='enrollments')
    course = models.ForeignKey('Course', on_delete=models.CASCADE, related_name='enrollments')
    repository = models.ForeignKey('StudentRepository', on_delete=models.CASCADE, null=True, blank=True)
    joined = models.DateTimeField(default=datetime_now)
    last_activity = models.DateTimeField(null=True, blank=True)


    def clean(self):
        super().clean()
        if self.repository and self.repository.student != self.student:
            raise ValidationError({
                'repository': _('Repository does not belong to student.')
            })

    class Meta:
        unique_together = [('student', 'repository'), ('student', 'course')]
        verbose_name = _('Enrollment')
        verbose_name_plural = _('Enrollments')


class StudentRepository(Repository):

    student = models.ForeignKey(
        'Student',
        on_delete=models.CASCADE,
        related_name='repositories',
        blank=True
    )

    def clean(self):
        super().clean()
        if not hasattr(self, 'student'):
            uri_match = Repository.URI_RE.search(self.uri)
            if uri_match:
                self.student = Student.objects.get_or_create(
                    handle=uri_match.groupdict()['handle']
                )[0]
        if self.student and self.student.handle != self.handle:
            raise ValidationError({
                'handle': _('Handle {} does not belong to student {}.').format(self.handle, self.student.display)
            })
    
    def synchronize_keys(self):
        from cryptography.hazmat.backends import default_backend
        from cryptography.hazmat.primitives import serialization

        def get_keys():
            with open(self.local / 'public_keys.pem', 'rb') as f:
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

            return [
                serialization.load_pem_public_key(
                    pem.encode(),
                    backend=default_backend()
                ) for pem in pem_keys
            ]


        if self.local:
            keys = self.get_keys()
        else:
            tmp_root = getattr(settings, 'TMP_DIR', None)
            if tmp_root:
                os.makedirs(tmp_root, exist_ok=True)
            with tempfile.TemporaryDirectory(dir=tmp_root) as tmpdir:
                tmpdir = Path(tmpdir)
                self.clone(tmpdir) 
                keys = self.get_keys()

        all_keys = set()
        new_keys = set()
        for key in keys:
            key, created = StudentRepositoryPublicKey.objects.get_or_create(
                repository=self,
                key=key.public_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PublicFormat.SubjectPublicKeyInfo
                )
            )
            if created:
                new_keys.add(key)
            all_keys.add(key)
        
        # remove old keys
        removed = StudentRepositoryPublicKey.objects.filter(repository=self).exclude(all_keys)
        removed.delete()
        return all_keys, new_keys, set(removed)

    def verify(self, message, signature):
        return any((key.verify(message, signature) for key in self.keys.all()))

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

    def verify(self, message, signature):
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import padding
        from cryptography.hazmat.backends import default_backend

        try:
            # load public key from binary field
            public_key = crypto_serialization.load_pem_public_key(
                self.key,
                backend=default_backend()
            )
            public_key.verify(
                signature,
                message.encode(),
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            return True
        except:
            return False

    def __str__(self):
        return f'{self.repository}: {self.timestamp}'

    class Meta:
        ordering = ['-timestamp']
        verbose_name = _('Student Repository Public Key')
        verbose_name_plural = _('Student Repository Public Keys')


class StudentRepositoryVersion(RepositoryVersion):

    repository = models.ForeignKey('StudentRepository', on_delete=models.CASCADE)

    def __str__(self):
        return f'{self.repository}: {RepositoryVersion.__str__(self)}'
    
    class Meta:
        verbose_name = _('Student Repository Version')
        verbose_name_plural = _('Student Repository Versions')


class Student(models.Model):

    name = models.CharField(max_length=255, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    handle = models.CharField(
        max_length=255,
        null=False,
        unique=True,
        help_text=_('The student\'s GitHub handle.')
    )
    joined = models.DateTimeField(default=datetime_now)

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
    def display(self):
        return self.name or self.handle
    
    def __str__(self):
        return self.display

    class Meta:
        verbose_name = _('Student')
        verbose_name_plural = _('Students')


class TutorExchange(models.Model):

    role = EnumField(TutorRole)
    message = models.TextField(null=False)
    timestamp = models.DateTimeField(null=False, db_index=True)

    session = models.ForeignKey('TutorSession', on_delete=models.CASCADE)

    backend_extra = models.JSONField(null=True, blank=True)

    class Meta:
        ordering = ['timestamp']
        verbose_name = _('Tutor Exchange')
        verbose_name_plural = _('Tutor Exchanges')


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
        verbose_name = _('Tutor Session')
        verbose_name_plural = _('Tutor Sessions')


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
        verbose_name = _('Tutor Engagement')
        verbose_name_plural = _('Tutor Engagements')


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
        verbose_name = _('Module')
        verbose_name_plural = _('Modules')


class SpecialTopic(Module):

    uri = models.URLField(max_length=255, null=False)

    class Meta:
        verbose_name = _('Special Topic')
        verbose_name_plural = _('Special Topics')


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
        verbose_name = _('Assignment')
        verbose_name_plural = _('Assignments')
