from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.db.models import Q
from django.db import transaction
from django.utils.timezone import now
from learn_python_server.models import (
    LogFile,
    LogEvent,
    TestEvent
)
from learn_python_server.utils import TemporaryDirectory
import re
from pathlib import Path
import shutil
import readline  # don't remove, this helps input() work better


class Command(BaseCommand):
    help = _('Process unprocessed log files.')

    def add_arguments(self, parser):

        parser.add_argument(
            '-l',
            '--level',
            dest='level',
            default=LogEvent.LogLevel.ERROR,
            type=int,
            help=_(
                'The minimum log level to process. Defaults to {}.'
            ).format(LogEvent.LogLevel.ERROR)
        )


    def handle(self, **options):
        with transaction.atomic():
            for log_file in LogFile.objects.filter(processed=False):
                events = self.process_log(log_file, options['level'])
                self.stdout.write(self.style.SUCCESS(_('{} were processed from {}').format(events, log_file)))
                log_file.processed = True
                log_file.save()

    def process_log(self, log_file, level):
        events = 0
        for log_record in log_file:
            if log_record['level'] >= level:
                EventType = LogEvent
                LogEvent.objects.create(
                    log_file=log_file,
                    level=log_record['level'],
                    message=log_record.get('message', ''),
                    timestamp=log_record['timestamp']
                )
                if log_file.type is LogFile.LogFileType.TESTING:
                    EventType = TestEvent

                EventType.objects.create(**log_record, log=log_file)
                events += 1
        return events
