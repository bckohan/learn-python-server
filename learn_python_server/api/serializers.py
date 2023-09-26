from rest_framework.serializers import ModelSerializer, CharField, IntegerField
from learn_python_server.models import (
    TutorEngagement,
    TutorSession,
    TutorExchange,
    StudentRepositoryVersion,
    Student,
    Assignment,
    Module
)
from django_enum.drf import EnumField as DRFEnumField
from django.db import transaction
from django.db.models import Q


class StudentSerializer(ModelSerializer):
    
    class Meta:
        model = Student
        fields = ('domain', 'handle', 'email')



class StudentRepositoryVersionSerializer(ModelSerializer):
    
    uri = CharField(source='repository.uri', read_only=True)
    student = StudentSerializer(read_only=True)

    def update(self, instance, validated_data):
        return self.create(validated_data)

    def create(self, validated_data):
        return StudentRepositoryVersion.objects.get_or_create(
            repository=validated_data.pop('repository'),
            git_hash=validated_data.pop('git_hash'),
            git_branch=validated_data.pop('git_branch'),
            defaults=validated_data
        )[0]

    class Meta:
        model = StudentRepositoryVersion
        fields = (
            'uri',
            'student',
            'git_hash',
            'git_branch',
            'timestamp',
            'commit_count'
        )


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
    repository = StudentRepositoryVersionSerializer(read_only=False)

    def update(self, instance, validated_data):
        return self.create(validated_data)

    def create(self, validated_data):
        with transaction.atomic():
            sessions = validated_data.pop('sessions', [])
            repository = self.get_fields()['repository'].create({
                **validated_data.pop('repository'),
                'repository': self.context['request'].user.authorized_repository
            })
            engagement = TutorEngagement.objects.get_or_create(
                **validated_data,
                repository=repository
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
