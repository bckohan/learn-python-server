from django.apps import AppConfig


class LearnPythonServerConfig(AppConfig):
    name = 'learn_python_server'
    verbose_name = 'Learn Python Server'

    def ready(self):
        pass
