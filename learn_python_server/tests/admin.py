from django.test import LiveServerTestCase, Client, override_settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.conf import settings
from learn_python_server.models import (
    Assignment,
    Course,
    CourseRepository,
    DocBuild,
    LogFile,
    Module,
    SpecialTopic,
    Student,
    StudentRepository,
    TutorAPIKey,
    TutorEngagement,
    TutorExchange,
    TutorSession,
    User,
)
from django.urls import reverse
from django.contrib.auth import get_user_model
import pytest


class AdminUserMixin:

    admin_user: get_user_model()


    def setUp(self):
        super().setUp()
        self.admin_user = get_user_model().objects.create_superuser(
            username='admin',
            password='testPassw0rd'
        )
        self.assertTrue(self.client.login(username='admin', password='testPassw0rd'))


class TestAdminListPages(AdminUserMixin, LiveServerTestCase):

    MODELS = [
        Assignment,
        Course,
        CourseRepository,
        DocBuild,
        LogFile,
        Module,
        SpecialTopic,
        Student,
        StudentRepository,
        TutorAPIKey,
        TutorEngagement,
        TutorExchange,
        TutorSession,
        User
    ]

    def test_admin_pages_load(self):
        """
        Test that tutor log file uploads work.
        """
        for model in self.MODELS:
            url = reverse(f'admin:{model._meta.label_lower.replace(".", "_")}_changelist')
            response = self.client.get(url, follow=True)
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, 'Learn Python Server')

    def test_admin_user_change_page(self):
        self.assertTrue(self.client.login(username='admin', password='testPassw0rd'))
        response = self.client.get(
            reverse(
                f'admin:{get_user_model()._meta.label_lower.replace(".", "_")}_change',
                args=[self.admin_user.id]
            )
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Learn Python Server')
        self.assertContains(response, str(self.admin_user))
