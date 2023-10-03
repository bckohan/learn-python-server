import os
from pathlib import Path

from django.test import SimpleTestCase
import importlib

os.environ.setdefault('LEARN_PYTHON_RDBMS', 'postgres')

from learn_python_server.settings import *
import shutil

TEST_COURSE_REPO = 'https://github.com/bckohan/learn-python'
TEST_STUDENT_REPO = 'https://github.com/bckohan/learn-python-test'


class TestSettings(SimpleTestCase):

    def test_settings(self):
        shutil.rmtree(SECRETS_DIR, ignore_errors=True)
        os.environ['LEARN_PYTHON_SERVER_DIR'] = str(Path(__file__).parent)
        from learn_python_server import settings
        importlib.reload(settings)
        self.assertEqual(settings.BASE_DIR, Path(os.environ['LEARN_PYTHON_SERVER_DIR']))
        self.assertFalse(settings.DEBUG)

        os.environ['LEARN_PYTHON_SERVER_DEBUG'] = '1'
        importlib.reload(settings)
        self.assertTrue(settings.DEBUG)

    def test_wsgi(self):
        from learn_python_server import wsgi
        from django.core.handlers.wsgi import WSGIHandler
        self.assertIsInstance(wsgi.get_wsgi_application(), WSGIHandler)
