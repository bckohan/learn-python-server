"""
WSGI config for learn-python-server project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

# todo none of this should be packaged for the public - also look at manage.py
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'learn_python_server.settings')
os.environ.setdefault('LEARN_PYTHON_RDBMS', 'postgres')
os.environ.setdefault('LEARN_PYTHON_SERVER_DIR', '/var/www/demoply.org/learn-python')

application = get_wsgi_application()
