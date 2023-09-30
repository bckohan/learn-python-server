from django.test import TestCase, Client, override_settings
from django.contrib.staticfiles.testing import LiveServerTestCase
from django.conf import settings
from learn_python_server.models import (
    LogFile,
    TestEvent,
    LogEvent,
    Student,
    StudentRepository,
    Enrollment,
    TutorAPIKey,
    TutorBackend,
    TutorEngagement,
    TutorExchange,
    TutorSession
)
from learn_python_server.finders import DocBuildFinder
from learn_python_server.tests.register import AddStudentMixin
from django.core.management import call_command
from django.contrib.auth import get_user_model
from django.urls import reverse
from pathlib import Path
import subprocess
import shutil
import os



class TestLogUpload(AddStudentMixin, LiveServerTestCase):

    def setUp(self):
        super().setUp()
        key = TutorAPIKey.objects.create(
            name='Test Key',
            backend=TutorBackend.TEST,
            secret='ssssshhh!'
        )
        self.course.tutor_key = key
        self.course.save()
        self.student = Student.objects.get(handle=self.handle, domain=self.domain)
        self.student_repo = self.student.repositories.first()
        enrollment, created = Enrollment.objects.get_or_create(
            student=self.student,
            course=self.course,
            repository=self.student_repo
        )
        shutil.rmtree(settings.MEDIA_ROOT, ignore_errors=True)
        LogFile.objects.all().delete()

    def tearDown(self):
        super().tearDown()
        shutil.rmtree(settings.MEDIA_ROOT, ignore_errors=True)

    def test_log_upload(self):
        """
        Test that tutor log file uploads work.
        """
        # import ipdb
        with self.student_repo:
            self.configure(self.student_repo)
            self.student_repo.install()
            general_line_counts = []
            # ipdb.set_trace()
            subprocess.check_output(['poetry', 'run', 'register']).decode().strip()
            try:
                #ipdb.set_trace()
                subprocess.check_output(['poetry', 'run', 'pytest']).decode().strip()
                self.assertEqual(LogFile.objects.count(), 2)
                self.assertEqual(LogFile.objects.filter(type=LogFile.LogFileType.TESTING).count(), 1)
                self.assertEqual(LogFile.objects.filter(type=LogFile.LogFileType.GENERAL).count(), 1)
                general_line_counts.append(LogFile.objects.get(type=LogFile.LogFileType.GENERAL).num_lines)
            except subprocess.CalledProcessError as e:
                pass  # if tests fail we dont care
            
            #ipdb.set_trace()
            subprocess.check_output(['poetry', 'run', 'delphi']).decode().strip()
            self.assertEqual(LogFile.objects.filter(type=LogFile.LogFileType.GENERAL).count(), 1)
            general_line_counts.append(LogFile.objects.get(type=LogFile.LogFileType.GENERAL).num_lines)
            self.assertEqual(LogFile.objects.filter(type=LogFile.LogFileType.TUTOR).count(), 1)

            #ipdb.set_trace()
            subprocess.check_output(['poetry', 'run', 'delphi']).decode().strip()
            self.assertEqual(LogFile.objects.filter(type=LogFile.LogFileType.GENERAL).count(), 1)
            general_line_counts.append(LogFile.objects.get(type=LogFile.LogFileType.GENERAL).num_lines)
            self.assertEqual(LogFile.objects.filter(type=LogFile.LogFileType.TUTOR).count(), 2)

            #ipdb.set_trace()
            subprocess.check_output(['poetry', 'run', 'delphi']).decode().strip()
            self.assertEqual(LogFile.objects.filter(type=LogFile.LogFileType.GENERAL).count(), 1)
            general_line_counts.append(LogFile.objects.get(type=LogFile.LogFileType.GENERAL).num_lines)
            self.assertEqual(LogFile.objects.filter(type=LogFile.LogFileType.TUTOR).count(), 3)

            #ipdb.set_trace()
            subprocess.check_output(['poetry', 'run', 'delphi']).decode().strip()
            self.assertEqual(LogFile.objects.filter(type=LogFile.LogFileType.GENERAL).count(), 1)
            general_line_counts.append(LogFile.objects.get(type=LogFile.LogFileType.GENERAL).num_lines)
            self.assertEqual(LogFile.objects.filter(type=LogFile.LogFileType.TUTOR).count(), 4)

            #ipdb.set_trace()
            subprocess.check_output(['poetry', 'run', 'report']).decode().strip()
        
        #ipdb.set_trace()
        self.assertEqual(LogFile.objects.count(), 6)
        self.assertEqual(LogFile.objects.filter(type=LogFile.LogFileType.TESTING).count(), 1)
        self.assertEqual(LogFile.objects.filter(type=LogFile.LogFileType.GENERAL).count(), 1)
        self.assertEqual(LogFile.objects.filter(type=LogFile.LogFileType.TUTOR).count(), 4)

        files = set()
        for log_file in LogFile.objects.all():
            self.assertTrue(Path(log_file.log.path).is_file())
            files.add(log_file.log.path)

        self.assertEqual(LogFile.objects.count(), len(files))
        self.assertEqual(
            len(files),
            len(os.listdir(Path(settings.MEDIA_ROOT) / LogFile._meta.get_field('log').upload_to))
        )

        # should have been getting a new general log file at each report
        for idx, line_count in enumerate(general_line_counts[1:]):
            self.assertGreater(line_count, general_line_counts[idx])

        # test admins
        for model in [LogFile, TutorAPIKey, TutorEngagement, TutorExchange, TutorSession]:
            response = self.client.get(
                reverse(
                    f'admin:{model._meta.label_lower.replace(".", "_")}_change',
                    args=[model.objects.first().id]
                )
            )
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, 'Learn Python Server')
            self.assertContains(response, str(model.objects.first()))

        call_command('update_course', course=self.course.id)
        call_command('process_logs')

        self.assertGreater(TestEvent.objects.count(), 0)
        self.assertGreater(LogEvent.objects.count(), 0)
