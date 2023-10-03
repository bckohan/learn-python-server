import gzip
import os
import re
from io import BytesIO
from uuid import UUID

from dateutil.parser import parse as parse_date
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.db import transaction
from django.db.models import Q
from django.urls.converters import get_converter
from django_enum.drf import EnumField as DRFEnumField
from learn_python_server.models import (
    Assignment,
    LogFile,
    Student,
    TutorEngagement,
    TutorExchange,
    TutorSession,
    ToolRun,
    TimelineEvent,
    TestEvent,
    LogEvent,
    Module
)
from learn_python_server.utils import (
    calculate_sha256,
    headers_match,
    is_gzip,
    num_lines,
)
from rest_framework.serializers import (
    CharField,
    IntegerField,
    ModelSerializer
)
from rest_polymorphic.serializers import PolymorphicSerializer


class StudentSerializer(ModelSerializer):
    
    class Meta:
        model = Student
        fields = ('domain', 'handle', 'email')


class TutorExchangeSerializer(ModelSerializer):

    role = DRFEnumField(enum=TutorExchange._meta.get_field('role').enum)

    def update(self, instance, validated_data):
        return self.create(validated_data)

    def create(self, validated_data):
        return TutorExchange.objects.get_or_create(
            timestamp=validated_data.pop('timestamp'),
            session=validated_data.pop('session'),
            defaults=validated_data
        )[0]

    class Meta:
        model = TutorExchange
        fields = ('id', 'role', 'content', 'timestamp', 'is_function_call', 'backend_extra')
        read_only_fields = ('id',)


class AssignmentSerializer(ModelSerializer):

    module = IntegerField(source='module.number')

    def update(self, instance, validated_data):
        return self.create(validated_data)

    def create(self, validated_data):
        student = validated_data.pop('student')
        course_repo = student.authorized_repository.course_repository
        if course_repo and validated_data:
            return Assignment.objects.filter(
                Q(module__number=validated_data.pop('module')['number']) &
                Q(module__repository=course_repo) &
                Q(identifier=validated_data['identifier'])
            ).first()
        return None
    
    class Meta:
        model = Assignment
        fields = ('id', 'module', 'identifier')
        read_only_fields = ('id',)


class TutorSessionSerializer(ModelSerializer):

    exchanges = TutorExchangeSerializer(many=True, read_only=False)
    assignment = AssignmentSerializer(read_only=False, required=False)

    def update(self, instance, validated_data):
        return self.create(validated_data)

    def create(self, validated_data):
        student = validated_data.pop('student')
        exchanges = validated_data.pop('exchanges', [])
        assignment = validated_data.pop('assignment', {})
        session = TutorSession.objects.get_or_create(
            timestamp=validated_data.pop('timestamp'),
            repository=validated_data.pop('repository'),
            session_id=validated_data.pop('session_id'),
            engagement=validated_data.pop('engagement'),
            defaults={
                **validated_data,
                'assignment': self.get_fields()['assignment'].create({
                    **assignment,
                    'student': student
                })
            }
        )[0]
        self.get_fields()['exchanges'].create([
            {**exchange, 'session': session} for exchange in exchanges
        ])
        
        return session

    class Meta:
        model = TutorSession
        fields = ('id', 'engagement', 'session_id', 'timestamp', 'stop', 'assignment', 'exchanges')
        read_only_fields = ('id', 'engagement')


class TutorEngagementSerializer(ModelSerializer):

    sessions = TutorSessionSerializer(many=True, read_only=False)
    repository = CharField(source='repository.uri', read_only=True)

    tool = CharField(read_only=True)

    def update(self, instance, validated_data):
        return self.create(validated_data)

    def create(self, validated_data):
        with transaction.atomic():
            sessions = validated_data.pop('sessions', [])
            engagement = TutorEngagement.objects.get_or_create(
                **validated_data,
                repository=self.context['request'].user.authorized_repository,
                tool=TutorEngagement.Tools.TUTOR
            )[0]
            sessions_field = self.get_fields()['sessions']
            sessions_field.create([
                {
                    **session,
                    'engagement': engagement,
                    'repository': self.context['request'].user.authorized_repository,
                    'student': self.context['request'].user
                } for session in sessions
            ])
            return engagement

    class Meta:
        model = TutorEngagement
        fields = '__all__'


class TutorEngagementLogSerializer(ModelSerializer):

    class Meta:
        model = TutorEngagement
        fields = ('id', 'log')
        read_only_fields = ('id',)


class LogFileSerializer(ModelSerializer):

    repository = CharField(
        source='repository.uri',
        read_only=True,
        required=False
    )

    type = DRFEnumField(
        enum=LogFile._meta.get_field('type').enum,
        read_only=True,
        required=False
    )
    
    ENGAGEMENT_ID_RGX = re.compile(get_converter('uuid').regex)
    LOG_NAME_DATE_RGX = re.compile(r'(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})')

    def create(self, validated_data):
        with transaction.atomic():
            log = validated_data.get('log')
            if log:
                # Check if file is not gzip compressed
                if not is_gzip(log):
                    # Compress file and replace the original file in validated_data
                    log = self.compress_file(log)
                    validated_data['log'] = log
            
            date = validated_data.pop('date', None)
            if date is None:
                # Extract date from log file name
                match = self.LOG_NAME_DATE_RGX.search(log.name)
                if match:
                    dt = parse_date(match.group(0))
                    if dt:
                        date = dt.date()

            for type in reversed(LogFile.LogFileType):
                if log.name.lower().startswith(type.prefix.lower()):
                    break

            # if the log file is not created, the in memory uploaded file is
            # never saved which is what we want
            log_file, created = LogFile.objects.get_or_create(
                sha256_hash=calculate_sha256(log),
                repository=self.context['request'].user.authorized_repository,
                defaults={
                    **validated_data,
                    'type': type,
                    'date': date,
                    'num_lines': num_lines(log)
                }
            )

            if type is LogFile.LogFileType.TUTOR:
                match = self.ENGAGEMENT_ID_RGX.search(log.name)
                if match:
                    try:
                        engagement = TutorEngagement.objects.get(engagement_id=UUID(match.group(0)))
                        engagement.log = log_file
                        engagement.save()
                        log_file.date = engagement.start.date()
                        log_file.save()
                    except TutorEngagement.DoesNotExist:
                        pass
            else:
                # delete any partial versions of this log that were previously uploaded
                for other_log in LogFile.objects.filter(
                    Q(repository=log_file.repository) & 
                    Q(type=type) & 
                    (Q(date=log_file.date) | Q(date__isnull=True))
                ).exclude(pk=log_file.pk).select_for_update():
                    with (
                        gzip.open(other_log.log.path, 'rb') as file1, 
                        gzip.open(log_file.log.path, 'rb') as file2
                    ):
                        if headers_match(file1, file2, min(other_log.num_lines, log_file.num_lines)):
                            if other_log.num_lines > log_file.num_lines:
                                other_log, log_file = log_file, other_log
                            if os.path.exists(other_log.log.path):
                                os.remove(other_log.log.path)
                            other_log.delete()

            return log_file

    def compress_file(self, file: InMemoryUploadedFile):
        buffer = BytesIO()
        file.seek(0)
        with gzip.GzipFile(fileobj=buffer, mode='wb') as gz_file:
            gz_file.write(file.read())
        return InMemoryUploadedFile(
            buffer,
            file.field_name,
            f'{file.name}.gz',
            'application/gzip',
            buffer.getbuffer().nbytes,
            file.charset
        )
    
    class Meta:
        model = LogFile
        fields = ('id', 'sha256_hash', 'repository', 'type', 'log', 'date', 'processed')
        read_only_fields = ('id', 'sha256_hash', 'repository', 'type', 'processed')


class TimelineEventSerializer(ModelSerializer):

    repository = CharField(source='repository.uri', read_only=True)

    class Meta:
        model = TimelineEvent
        fields = ('id', 'timestamp', 'repository')
        read_only_fields = fields

class ToolRunSerializer(TimelineEventSerializer):
    
    class Meta:
        model = ToolRun
        fields = (*TimelineEventSerializer.Meta.fields, 'tool', 'stop')
        read_only_fields = fields


class TutorEngagementTLSerializer(ToolRunSerializer):

    class Meta:
        model = TutorEngagement
        fields = (*ToolRunSerializer.Meta.fields, 'log', 'engagement_id', 'backend')
        read_only_fields = fields


class ModuleTLSerializer(ModelSerializer):

    class Meta:
        model = Module
        fields = ('id', 'number', 'name', 'topic')
        read_only_fields = fields


class AssignmentTLSerializer(ModelSerializer):

    module = ModuleTLSerializer(read_only=True)

    class Meta:
        model = Assignment
        fields = ('id', 'module', 'number', 'name', 'identifier')
        read_only_fields = fields


class TutorExchangeTLSerializer(ModelSerializer):

    class Meta:
        model = TutorExchange
        fields = ('id', 'role', 'content', 'timestamp', 'is_function_call')
        read_only_fields = fields


class TutorSessionTLSerializer(TimelineEventSerializer):

    assignment = AssignmentTLSerializer(read_only=True)
    exchanges = TutorExchangeTLSerializer(many=True, read_only=False)

    class Meta:
        model = TutorSession
        fields = (*TimelineEventSerializer.Meta.fields, 'timestamp', 'stop', 'session_id', 'assignment')
        read_only_fields = fields


class LogEventSerializer(TimelineEventSerializer):
    
    class Meta:
        model = LogEvent
        fields = (*TimelineEventSerializer.Meta.fields, 'level', 'message')
        read_only_fields = fields


class TestEventSerializer(LogEventSerializer):
        
    class Meta:
        model = TestEvent
        fields = (*LogEventSerializer.Meta.fields, 'identifier', 'result')
        read_only_fields = fields


class TimelinePolymorphicSerializer(PolymorphicSerializer):
    model_serializer_mapping = {
        TimelineEvent: TimelineEventSerializer,
        ToolRun: ToolRunSerializer,
        TutorEngagement: TutorEngagementTLSerializer,
        TutorSession: TutorSessionTLSerializer,
        LogEvent: LogEventSerializer,
        TestEvent: TestEventSerializer
    }
