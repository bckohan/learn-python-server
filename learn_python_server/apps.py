from django.apps import AppConfig
from django.db import transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver
from learn_python_server.utils import is_in_transaction
import os


class LearnPythonServerConfig(AppConfig):
    name = 'learn_python_server'
    verbose_name = 'Learn Python Server'

    def ready(self):
        from learn_python_server.models import LogFile
        @receiver(post_delete, sender=LogFile)
        def delete_file(sender, instance, **kwargs):
            if instance.log and os.path.exists(instance.log.path):
                # Delay the file delete until after the transaction commits
                if is_in_transaction():
                    transaction.on_commit(lambda: instance.log.delete(False))
                else:
                    instance.log.delete(False)
