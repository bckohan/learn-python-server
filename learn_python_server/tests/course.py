import shutil
from pathlib import Path

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from learn_python_server.finders import DocBuildFinder
from learn_python_server.models import (
    Assignment,
    Course,
    CourseRepository,
    Module,
)
from learn_python_server.tests.admin import AdminUserMixin


class AddCourseMixin(AdminUserMixin):

    repo: CourseRepository
    course: Course

    def setUp(self):
        super().setUp()
        self.repo = CourseRepository.objects.create(
            uri=settings.TEST_COURSE_REPO,
        )
        self.course = Course.objects.create(
            name='Test Course',
            repository=self.repo
        )
        shutil.rmtree(settings.STATIC_ROOT, ignore_errors=True)
        self.assertTrue(self.client.login(username='admin', password='testPassw0rd'))

    def tearDown(self):
        super().tearDown()
        shutil.rmtree(settings.STATIC_ROOT, ignore_errors=True)


class TestCourseRegistration(AddCourseMixin, StaticLiveServerTestCase):

    def test_register_course(self):
        """
        Test that course registration and update works.
        """
        # Make a GET request to the desired URL
        assert(self.repo)
        assert(self.course)
        call_command('update_course', course=self.course.id)
        finder = DocBuildFinder()
        for url in [
            reverse('course_docs', kwargs={'course': str(self.course.id)}),
            reverse('course_docs', kwargs={'course': self.course.name}),
            reverse('repository_docs', kwargs={'repository': self.repo.uri})
        ]:
            response = self.client.get(url, follow=False)
            # there is some bug where I cant get static files to serve in test - so we're
            # just going to check that index.html exists at the root of the docs
            self.assertEqual(response.status_code, 302)
            doc_idx = Path(finder.find(settings.STATIC_ROOT / response.url.lstrip('/static') / 'index.html'))
            self.assertTrue('Read the Docs' in doc_idx.read_text())

        for model in [Course, CourseRepository, Module, Assignment]:
            response = self.client.get(
                reverse(
                    f'admin:{model._meta.label_lower.replace(".", "_")}_change',
                    args=[model.objects.first().id]
                )
            )
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, 'Learn Python Server')
            self.assertContains(response, str(model.objects.first()))
