import re
import readline  # don't remove, this helps input() work better
import shutil
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from learn_python_server.models import Assignment, LogEvent, LogFile, TestEvent
from learn_python_server.utils import TemporaryDirectory


class Command(BaseCommand):
    help = _('Process unprocessed log files.')

    FIELD_NAMES = {
        LogEvent: [
            field.name for field in LogEvent._meta.get_fields()
        ],
        TestEvent: [
            field.name for field in TestEvent._meta.get_fields()
        ]
    }

    def add_arguments(self, parser):

        parser.add_argument(
            '--level',
            dest='level',
            default=LogEvent.LogLevel.ERROR,
            type=int,
            help=_(
                'The minimum log level to process. Defaults to {}.'
            ).format(LogEvent.LogLevel.ERROR)
        )

        parser.add_argument(
            '--reset',
            dest='reset',
            action='store_true',
            help=_(
                'Reprocess the log files.'
            )
        )

        filter_group = parser.add_mutually_exclusive_group()

        filter_group.add_argument(
            '--repository',
            dest='repository',
            type=int,
            help=_(
                'The id of the student repository to process.'
            )
        )

        filter_group.add_argument(
            '--log',
            dest='log',
            type=int,
            help=_(
                'The id of the log to process.'
            )
        )

    def handle(self, **options):
        with transaction.atomic():
            qry = Q()
            if not options['reset']:
                qry &= Q(processed=False)
            if options['repository']:
                qry &= Q(repository__id=options['repository'])
            if options['log']:
                qry &= Q(id=options['log'])
            logs = LogFile.objects.filter(qry)
            if options['reset']:
                TestEvent.objects.filter(log__in=logs).delete()
                LogEvent.objects.filter(log__in=logs).delete()
            for log_file in LogFile.objects.filter(qry).select_for_update():
                events = self.process_log(log_file, options['level'])
                self.stdout.write(self.style.SUCCESS(_('{} were processed from {}').format(events, log_file)))
                log_file.processed = True
                log_file.save()

    def process_log(self, log_file, level):
        events = 0
        course = log_file.repository.enrollment.course
        runner_stack = []
        for log_record in log_file:
            if (
                log_record and 
                (
                    log_record['level'] >= level or
                    log_file.type is LogFile.LogFileType.TESTING
                )
            ):
                EventType = LogEvent
                if log_file.type is LogFile.LogFileType.TESTING:
                    # todo handle day-boundary problem 
                    # (will have to look at the previous day's log) and read backwards
                    # until stack is empty
                    if 'start' in log_record:
                        runner_stack.append(log_record['start'])
                        continue
                    if 'stop' in log_record:
                        if runner_stack and runner_stack[-1] == log_record['stop']:
                            runner_stack.pop()
                        continue
                    if 'result' in log_record and 'identifier' in log_record:
                        log_record['assignment'] = Assignment.objects.filter(
                            Q(module__repository__courses=course) &
                            Q(identifier=log_record['identifier'])
                        ).distinct().first()
                        if log_record['assignment']:
                            EventType = TestEvent
                            if runner_stack:
                                log_record['runner'] = runner_stack[0]
                    else:
                        continue
                try:
                    EventType.objects.create(
                        **{
                            key: value
                            for key, value in log_record.items()
                            if key in self.FIELD_NAMES[EventType]
                        },
                        log=log_file
                    )
                except Exception as e:
                    self.stderr.write(self.style.ERROR(_('Error processing log record: {}').format(e)))
                    self.stderr.write(self.style.ERROR(_('Log record: {}').format(log_record)))
                    continue
                events += 1
        return events