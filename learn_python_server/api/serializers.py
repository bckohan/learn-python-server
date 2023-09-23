from rest_framework.serializers import ModelSerializer, CharField
from learn_python_server.models import (
    TutorEngagement,
    TutorSession,
    TutorExchange,
    StudentRepository,
    StudentRepositoryVersion,
    Student
)

class StudentSerializer(ModelSerializer):
    
    class Meta:
        model = Student
        fields = ('domain', 'handle', 'email')



class StudentRepositoryVersionSerializer(ModelSerializer):
    
    uri = CharField(source='repository.uri', read_only=True)
    student = StudentSerializer(read_only=True)

    def create(self, validated_data):
        # todo
        repository = StudentRepository.objects.get(
            **validated_data.pop('uri')
        )
        return StudentRepositoryVersion.objects.get_or_create(
            **validated_data,
            repository=repository
        )

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

    class Meta:
        model = TutorExchange
        fields = '__all__'


class TutorSessionSerializer(ModelSerializer):

    exchanges = TutorExchangeSerializer(many=True, read_only=False)

    def create(self, validated_data):
        
        exchanges = validated_data.pop('exchanges', [])
        session = TutorSession.objects.get_or_create(
            **validated_data
        )
        for exchange in exchanges:
            self.exchanges.create(exchange)
        return session
    
    class Meta:
        model = TutorSession
        fields = '__all__'


class TutorEngagementSerializer(ModelSerializer):

    sessions = TutorSessionSerializer(many=True, read_only=False)
    repository = StudentRepositoryVersionSerializer(read_only=False)

    def create(self, validated_data):
        
        sessions = validated_data.pop('sessions', [])
        repository = self.repository.create(
            validated_data.pop('repository')
        )
        engagement = TutorEngagement.objects.get_or_create(
            **validated_data,
            repository=repository
        )
        for session in sessions:
            self.sessions.create(session)
        return engagement

    class Meta:
        model = TutorEngagement
        fields = '__all__'
