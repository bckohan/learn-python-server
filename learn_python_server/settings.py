"""
Django settings for learn_python_server project.

Generated by 'django-admin startproject' using Django 4.2.1.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/4.2/ref/settings/
"""

import os
from pathlib import Path

from split_settings.tools import include, optional

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(
    os.environ.get('LEARN_PYTHON_SERVER_DIR', Path(__file__).resolve().parent)
)


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/


# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = bool(int(os.environ.get('LEARN_PYTHON_SERVER_DEBUG', 0)))

ALLOWED_HOSTS = ['*']


# Application definition

INSTALLED_APPS = [
    'rest_framework',
    'learn_python_server',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'learn_python_server.middleware.NormalizeRepositoryMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'learn_python_server.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'learn_python_server.wsgi.application'

AUTH_USER_MODEL = 'learn_python_server.User'


# Password validation
# https://docs.djangoproject.com/en/4.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/4.2/topics/i18n/

LANGUAGE_CODE = 'en-us'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.2/howto/static-files/

STATIC_URL = 'static/'

# Default primary key field type
# https://docs.djangoproject.com/en/4.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

STATIC_ROOT = BASE_DIR / 'static'
MEDIA_ROOT = BASE_DIR / 'media'
MEDIA_URL = 'media/'

# rwx for user and group
FILE_UPLOAD_PERMISSIONS = 0o770
FILE_UPLOAD_DIRECTORY_PERMISSIONS = 0o770

SECRETS_DIR = Path(BASE_DIR) / 'secrets'


def generate_secret_key(filename):
    from django.core.management.utils import get_random_secret_key
    with open(filename, 'w') as f:
        f.write("%s\n" % get_random_secret_key())
    os.chmod(filename, 0o640)


def get_secret_key(filename):
    if os.path.exists(filename):
        with open(filename, 'r') as f:
            return f.readlines()[0]
    return ''


if not os.path.exists(SECRETS_DIR):
    os.makedirs(SECRETS_DIR)


sk_file = os.path.join(SECRETS_DIR, 'secret_key')

if not os.path.exists(sk_file):
    generate_secret_key(sk_file)

SECRET_KEY = get_secret_key(sk_file)

if len(SECRET_KEY) == 0:
    generate_secret_key(sk_file)
    SECRET_KEY = get_secret_key(sk_file)


# Database
# https://docs.djangoproject.com/en/4.2/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'learn_python',
        'USER': 'learn_python',
        'PASSWORD': get_secret_key(os.path.join(SECRETS_DIR, 'db_password')),
        'HOST': 'localhost',
        'PORT': '',
    }
}


DEFAULT_COURSE_REPOSITORY = 'https://github.com/bckohan/learn-python'

# The base directory where the course repositories will be cloned - will default to python's
# tempfile.TemporaryDirectory() if not set
# TMP_DIR = BASE_DIR / 'tmp'

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
        'learn_python_server.auth.RepositorySignatureAuthentication',
    ]
}

include(optional(BASE_DIR / 'local.py'))


# student repository requests must be signed and timestamped within this 
# many seconds, or they will be rejected
LP_REQUEST_TIMEOUT = 300

if DEBUG:
    STATICFILES_FINDERS = [
        'django.contrib.staticfiles.finders.FileSystemFinder',
        'django.contrib.staticfiles.finders.AppDirectoriesFinder',
        'learn_python_server.finders.DocBuildFinder',
    ]

    INSTALLED_APPS.insert(0, 'debug_toolbar')
    MIDDLEWARE.insert(0, 'debug_toolbar.middleware.DebugToolbarMiddleware')
    INTERNAL_IPS = [
        '127.0.0.1',
    ]
else:
    # security settings
    
    # you can override security settings by providing this file
    include(optional(BASE_DIR / 'security.py'))
