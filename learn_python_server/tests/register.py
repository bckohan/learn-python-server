from django.test import TestCase, Client, override_settings
from django.contrib.staticfiles.testing import LiveServerTestCase
from django.conf import settings
from learn_python_server.models import (
    Repository,
    Student,
    StudentRepository,
    Enrollment
)
from learn_python_server.finders import DocBuildFinder
from learn_python_server.tests.course import AddCourseMixin
from django.core.management import call_command
from django.contrib.auth import get_user_model
from django.urls import reverse
from pathlib import Path
import subprocess
import yaml


class AddStudentMixin(AddCourseMixin):
    
    def setUp(self):
        super().setUp()

        match = Repository.URI_RE.search(settings.TEST_STUDENT_REPO)
        self.assertTrue(match)
        self.domain = match.group('domain')
        self.handle = match.group('handle')

        with Repository(settings.TEST_STUDENT_REPO) as repo:
            repo.install()
            self.configure(repo)
            subprocess.check_output(['poetry', 'run', 'register']).decode().strip()

    def configure(self, repo):
        with open(repo.path('.config.yaml'), 'w') as file:
            yaml.dump({
                'enrollment': None,
                'registered': False,
                'server': self.live_server_url,
                'tutor': None
            }, file, default_flow_style=False)


class TestStudentRegistration(AddStudentMixin, LiveServerTestCase):


    def test_register_student(self):
        """
        Test that tutor log file uploads work.
        """
        student = Student.objects.get(handle=self.handle, domain=self.domain)
        repo = student.repositories.first()
        self.assertTrue(student)

        # test admins
        for model in [Student, StudentRepository]:
            response = self.client.get(
                reverse(
                    f'admin:{model._meta.label_lower.replace(".", "_")}_change',
                    args=[model.objects.first().id]
                )
            )
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, 'Learn Python Server')
            self.assertContains(response, str(model.objects.first()))

        enrollment, created = Enrollment.objects.get_or_create(
            student=student,
            course=self.course,
            repository=repo
        )

        self.assertEqual(repo.course_repository, self.course.repository)
        self.assertIsNone(repo.get_tutor_key())
