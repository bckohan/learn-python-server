from rest_framework.serializers import ModelSerializer, CharField, IntegerField
from learn_python_server.models import (
    TutorEngagement,
    TutorSession,
    TutorExchange,
    Student,
    Assignment,
    LogFile
)
from django_enum.drf import EnumField as DRFEnumField
from django.db import transaction
from django.db.models import Q
import os
import gzip
import re
from dateutil.parser import parse as parse_date
from django.urls.converters import get_converter
from uuid import UUID
from learn_python_server.utils import (
    calculate_sha256,
    num_lines,
    headers_match
)
from io import BytesIO
from django.core.files.uploadedfile import InMemoryUploadedFile


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
        fields = ('id', 'engagement', 'session_id', 'start', 'end', 'assignment', 'exchanges')
        read_only_fields = ('id', 'engagement')


class TutorEngagementSerializer(ModelSerializer):

    sessions = TutorSessionSerializer(many=True, read_only=False)
    repository = CharField(source='repository.uri', read_only=True)

    def update(self, instance, validated_data):
        return self.create(validated_data)

    def create(self, validated_data):
        with transaction.atomic():
            sessions = validated_data.pop('sessions', [])
            engagement = TutorEngagement.objects.get_or_create(
                **validated_data,
                repository=self.context['request'].user.authorized_repository
            )[0]
            sessions_field = self.get_fields()['sessions']
            sessions_field.create([
                {
                    **session, 'engagement': engagement,
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
                if not self.is_gzip(log):
                    # Compress file and replace the original file in validated_data
                    validated_data['log'] = self.compress_file(log)
            
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
                        engagement = TutorEngagement.objects.get(id=UUID(match.group(0)))
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
                ):
                    with (
                        gzip.open(other_log.log.path, 'rb') as file1, 
                        gzip.open(log_file.log.path, 'rb') as file2
                    ):
                        if headers_match(file1, file2, min(other_log.num_lines, log_file.num_lines)):
                            if other_log.num_lines > log_file.num_lines:
                                other_log, log_file = log_file, other_log
                            other_log.delete()

            return log_file

    def is_gzip(self, file):
        is_gz = file.read(2) == b'\x1f\x8b'
        file.seek(0)
        return is_gz

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
