# Generated by Django 4.2.5 on 2023-10-03 16:13

from django.conf import settings
import django.contrib.auth.validators
import django.core.validators
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import django_enum.fields
import learn_python_server.models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
        ('contenttypes', '0002_remove_content_type_name'),
    ]

    operations = [
        migrations.CreateModel(
            name='User',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('password', models.CharField(max_length=128, verbose_name='password')),
                ('last_login', models.DateTimeField(blank=True, null=True, verbose_name='last login')),
                ('is_superuser', models.BooleanField(default=False, help_text='Designates that this user has all permissions without explicitly assigning them.', verbose_name='superuser status')),
                ('username', models.CharField(error_messages={'unique': 'A user with that username already exists.'}, help_text='Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only.', max_length=150, unique=True, validators=[django.contrib.auth.validators.UnicodeUsernameValidator()], verbose_name='username')),
                ('is_staff', models.BooleanField(default=False, help_text='Designates whether the user can log into this admin site.', verbose_name='staff status')),
                ('is_active', models.BooleanField(default=True, help_text='Designates whether this user should be treated as active. Unselect this instead of deleting accounts.', verbose_name='active')),
                ('date_joined', models.DateTimeField(default=django.utils.timezone.now, verbose_name='date joined')),
                ('full_name', models.CharField(blank=True, default='', max_length=255, verbose_name='full name')),
                ('email', models.EmailField(blank=True, max_length=254, null=True, verbose_name='email address')),
                ('groups', models.ManyToManyField(blank=True, help_text='The groups this user belongs to. A user will get all permissions granted to each of their groups.', related_name='user_set', related_query_name='user', to='auth.group', verbose_name='groups')),
                ('polymorphic_ctype', models.ForeignKey(editable=False, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='polymorphic_%(app_label)s.%(class)s_set+', to='contenttypes.contenttype')),
                ('user_permissions', models.ManyToManyField(blank=True, help_text='Specific permissions for this user.', related_name='user_set', related_query_name='user', to='auth.permission', verbose_name='user permissions')),
            ],
            options={
                'abstract': False,
                'base_manager_name': 'objects',
            },
            managers=[
                ('objects', learn_python_server.models.PolymorphicUserManager()),
            ],
        ),
        migrations.CreateModel(
            name='Assignment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('number', models.PositiveSmallIntegerField(db_index=True)),
                ('name', models.CharField(db_index=True, max_length=255)),
                ('todo', models.TextField(blank=True, default='')),
                ('hints', models.TextField(blank=True, default='')),
                ('requirements', models.TextField(blank=True, default='')),
                ('identifier', models.CharField(max_length=255)),
            ],
            options={
                'verbose_name': 'Assignment',
                'verbose_name_plural': 'Assignments',
                'ordering': ['number'],
            },
        ),
        migrations.CreateModel(
            name='CourseRepository',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('uri', models.URLField(db_index=True, help_text='The Git repository URI. This may be a specific branch (i.e. tree/branch_name)', max_length=255, unique=True)),
            ],
            options={
                'verbose_name': 'Course Repository',
                'verbose_name_plural': 'Course Repositories',
            },
            bases=(learn_python_server.models.Repository, models.Model),
        ),
        migrations.CreateModel(
            name='CourseRepositoryVersion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('git_hash', models.CharField(max_length=255)),
                ('git_branch', models.CharField(default='main', max_length=255)),
                ('commit_count', models.PositiveIntegerField(db_index=True, default=0)),
                ('timestamp', models.DateTimeField(db_index=True, default=learn_python_server.models.datetime_now)),
                ('repository', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='versions', to='learn_python_server.courserepository')),
            ],
            options={
                'verbose_name': 'Course Repository Version',
                'verbose_name_plural': 'Course Repository Versions',
                'unique_together': {('repository', 'git_hash', 'git_branch')},
            },
        ),
        migrations.CreateModel(
            name='LogFile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('sha256_hash', models.CharField(max_length=64, validators=[django.core.validators.MinLengthValidator(64), django.core.validators.MaxLengthValidator(64)])),
                ('type', django_enum.fields.EnumPositiveSmallIntegerField(blank=True, choices=[(0, 'Unknown'), (1, 'General'), (2, 'Testing'), (3, 'Tutor')], db_index=True, default=0)),
                ('log', models.FileField(default=None, null=True, upload_to='log_uploads')),
                ('date', models.DateField(blank=True, db_index=True, null=True)),
                ('uploaded_at', models.DateTimeField(db_index=True, default=learn_python_server.models.datetime_now)),
                ('num_lines', models.PositiveIntegerField(default=0)),
                ('processed', models.BooleanField(blank=True, db_index=True, default=False, help_text='Whether or not the events have been scraped from the log file.')),
            ],
            options={
                'verbose_name': 'Log File',
                'verbose_name_plural': 'Log Files',
                'ordering': ('-date', '-uploaded_at'),
            },
        ),
        migrations.CreateModel(
            name='Module',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(blank=True, default='', max_length=64)),
                ('number', models.PositiveSmallIntegerField(null=True)),
                ('topic', models.CharField(blank=True, default='', max_length=255)),
                ('description', models.TextField(blank=True, default='')),
                ('added', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='modules_added', to='learn_python_server.courserepositoryversion')),
                ('polymorphic_ctype', models.ForeignKey(editable=False, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='polymorphic_%(app_label)s.%(class)s_set+', to='contenttypes.contenttype')),
                ('removed', models.ForeignKey(blank=True, default=None, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='modules_removed', to='learn_python_server.courserepositoryversion')),
                ('repository', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='modules', to='learn_python_server.courserepository')),
            ],
            options={
                'verbose_name': 'Module',
                'verbose_name_plural': 'Modules',
                'ordering': ['number'],
                'unique_together': {('repository', 'number')},
            },
        ),
        migrations.CreateModel(
            name='StudentRepository',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('uri', models.URLField(db_index=True, help_text='The Git repository URI. This may be a specific branch (i.e. tree/branch_name)', max_length=255, unique=True)),
            ],
            options={
                'verbose_name': 'Student Repository',
                'verbose_name_plural': 'Student Repositories',
            },
            bases=(learn_python_server.models.Repository, models.Model),
        ),
        migrations.CreateModel(
            name='TutorAPIKey',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=64, unique=True)),
                ('backend', django_enum.fields.EnumCharField(choices=[('test', 'Test'), ('openai', 'Open Ai')], max_length=6)),
                ('secret', models.CharField(max_length=255)),
            ],
            options={
                'verbose_name': 'Tutor API Key',
                'verbose_name_plural': 'Tutor API Keys',
            },
        ),
        migrations.CreateModel(
            name='TutorEngagement',
            fields=[
                ('id', models.UUIDField(primary_key=True, serialize=False)),
                ('start', models.DateTimeField(db_index=True)),
                ('end', models.DateTimeField()),
                ('tz_name', models.CharField(default='', max_length=64)),
                ('tz_offset', models.SmallIntegerField(default=None, null=True)),
                ('backend', django_enum.fields.EnumCharField(choices=[('test', 'Test'), ('openai', 'Open Ai')], max_length=6)),
                ('backend_extra', models.JSONField(blank=True, null=True)),
                ('log', models.ForeignKey(default=None, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='engagement', to='learn_python_server.logfile')),
                ('repository', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='learn_python_server.studentrepository')),
            ],
            options={
                'verbose_name': 'Tutor Engagement',
                'verbose_name_plural': 'Tutor Engagements',
                'ordering': ['-start'],
            },
        ),
        migrations.CreateModel(
            name='SpecialTopic',
            fields=[
                ('module_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='learn_python_server.module')),
                ('uri', models.URLField(max_length=255)),
            ],
            options={
                'verbose_name': 'Special Topic',
                'verbose_name_plural': 'Special Topics',
            },
            bases=('learn_python_server.module',),
        ),
        migrations.CreateModel(
            name='Student',
            fields=[
                ('user_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to=settings.AUTH_USER_MODEL)),
                ('domain', django_enum.fields.EnumPositiveSmallIntegerField(choices=[(0, 'github')])),
                ('handle', models.CharField(help_text="The student's GitHub handle.", max_length=255, unique=True)),
                ('login_user', models.ForeignKey(blank=True, default=None, help_text='The login user account associated with this student, if any.', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='students', to=settings.AUTH_USER_MODEL)),
                ('tutor_key', models.ForeignKey(blank=True, help_text='API key for the Tutor backend, specifically for this student - will override any associated class tutor key.', null=True, on_delete=django.db.models.deletion.CASCADE, to='learn_python_server.tutorapikey')),
            ],
            options={
                'verbose_name': 'Student',
                'verbose_name_plural': 'Students',
            },
            bases=('learn_python_server.user',),
            managers=[
                ('objects', learn_python_server.models.PolymorphicUserManager()),
            ],
        ),
        migrations.CreateModel(
            name='TutorSession',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('session_id', models.PositiveSmallIntegerField(db_index=True)),
                ('start', models.DateTimeField(db_index=True)),
                ('end', models.DateTimeField()),
                ('assignment', models.ForeignKey(default=None, null=True, on_delete=django.db.models.deletion.SET_NULL, to='learn_python_server.assignment')),
                ('engagement', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sessions', to='learn_python_server.tutorengagement')),
            ],
            options={
                'verbose_name': 'Tutor Session',
                'verbose_name_plural': 'Tutor Sessions',
                'ordering': ['start'],
                'unique_together': {('engagement', 'session_id')},
            },
        ),
        migrations.CreateModel(
            name='StudentRepositoryPublicKey',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('key', models.BinaryField()),
                ('timestamp', models.DateTimeField(db_index=True, default=learn_python_server.models.datetime_now)),
                ('repository', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='keys', to='learn_python_server.studentrepository')),
            ],
            options={
                'verbose_name': 'Student Repository Public Key',
                'verbose_name_plural': 'Student Repository Public Keys',
                'ordering': ['-timestamp'],
            },
        ),
        migrations.AddField(
            model_name='logfile',
            name='repository',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='learn_python_server.studentrepository'),
        ),
        migrations.CreateModel(
            name='LogEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('timestamp', models.DateTimeField(db_index=True)),
                ('level', django_enum.fields.EnumPositiveSmallIntegerField(choices=[(0, 'NOTSET'), (10, 'DEBUG'), (20, 'INFO'), (30, 'WARN'), (40, 'ERROR'), (50, 'CRITICAL')], db_index=True)),
                ('line_begin', models.PositiveIntegerField()),
                ('line_end', models.PositiveIntegerField()),
                ('message', models.TextField(blank=True, default='')),
                ('logger', models.CharField(blank=True, default='', max_length=128)),
                ('log', models.ForeignKey(default=None, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='events', to='learn_python_server.logfile')),
                ('polymorphic_ctype', models.ForeignKey(editable=False, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='polymorphic_%(app_label)s.%(class)s_set+', to='contenttypes.contenttype')),
            ],
            options={
                'verbose_name': 'Log Event',
                'verbose_name_plural': 'Log Events',
                'unique_together': {('timestamp', 'log')},
            },
        ),
        migrations.CreateModel(
            name='DocBuild',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('timestamp', models.DateTimeField(db_index=True, default=learn_python_server.models.datetime_now)),
                ('repository', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='learn_python_server.courserepositoryversion')),
            ],
            options={
                'verbose_name': 'Doc Build',
                'verbose_name_plural': 'Doc Builds',
            },
        ),
        migrations.CreateModel(
            name='Course',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(db_index=True, max_length=255, unique=True)),
                ('description', models.TextField(blank=True, default='')),
                ('started', models.DateField(default=learn_python_server.models.date_now)),
                ('ended', models.DateField(blank=True, default=None, null=True)),
                ('repository', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='courses', to='learn_python_server.courserepository')),
                ('tutor_key', models.ForeignKey(blank=True, help_text='API key for the Tutor backend, specifically for this course.', null=True, on_delete=django.db.models.deletion.CASCADE, to='learn_python_server.tutorapikey')),
            ],
            options={
                'verbose_name': 'Course',
                'verbose_name_plural': 'Courses',
                'ordering': ['-started'],
            },
        ),
        migrations.AddField(
            model_name='assignment',
            name='added',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='assignments_added', to='learn_python_server.courserepositoryversion'),
        ),
        migrations.AddField(
            model_name='assignment',
            name='module',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='assignments', to='learn_python_server.module'),
        ),
        migrations.AddField(
            model_name='assignment',
            name='removed',
            field=models.ForeignKey(blank=True, default=None, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='assignments_removed', to='learn_python_server.courserepositoryversion'),
        ),
        migrations.CreateModel(
            name='TutorExchange',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('role', django_enum.fields.EnumCharField(choices=[('system', 'System'), ('tutor', 'Tutor'), ('student', 'Student')], max_length=7)),
                ('content', models.TextField()),
                ('is_function_call', models.BooleanField(default=False)),
                ('timestamp', models.DateTimeField(db_index=True)),
                ('backend_extra', models.JSONField(blank=True, null=True)),
                ('session', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='exchanges', to='learn_python_server.tutorsession')),
            ],
            options={
                'verbose_name': 'Tutor Exchange',
                'verbose_name_plural': 'Tutor Exchanges',
                'ordering': ('timestamp',),
                'unique_together': {('timestamp', 'session')},
            },
        ),
        migrations.CreateModel(
            name='TestEvent',
            fields=[
                ('logevent_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='learn_python_server.logevent')),
                ('runner', django_enum.fields.EnumPositiveSmallIntegerField(choices=[(1, 'Tutor'), (2, 'Pytest'), (3, 'Docs'), (4, 'Continuous Integration'), (5, 'Server')], db_index=True, default=None, null=True)),
                ('result', django_enum.fields.EnumPositiveSmallIntegerField(choices=[(0, 'Passed'), (1, 'Failed'), (2, 'Errored'), (3, 'Skipped')], db_index=True)),
                ('assignment', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='tests', to='learn_python_server.assignment')),
            ],
            options={
                'verbose_name': 'Test Event',
                'verbose_name_plural': 'Test Events',
                'ordering': ['-timestamp'],
            },
            bases=('learn_python_server.logevent',),
        ),
        migrations.AddField(
            model_name='studentrepository',
            name='student',
            field=models.ForeignKey(blank=True, on_delete=django.db.models.deletion.CASCADE, related_name='repositories', to='learn_python_server.student'),
        ),
        migrations.AlterUniqueTogether(
            name='logfile',
            unique_together={('repository', 'sha256_hash')},
        ),
        migrations.AlterIndexTogether(
            name='logfile',
            index_together={('repository', 'sha256_hash')},
        ),
        migrations.CreateModel(
            name='Enrollment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('joined', models.DateTimeField(default=learn_python_server.models.datetime_now)),
                ('last_activity', models.DateTimeField(blank=True, null=True)),
                ('course', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='enrollments', to='learn_python_server.course')),
                ('repository', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='enrollment', to='learn_python_server.studentrepository')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='enrollments', to='learn_python_server.student')),
            ],
            options={
                'verbose_name': 'Enrollment',
                'verbose_name_plural': 'Enrollments',
                'unique_together': {('student', 'repository'), ('student', 'course')},
            },
        ),
        migrations.AddField(
            model_name='course',
            name='students',
            field=models.ManyToManyField(related_name='courses', through='learn_python_server.Enrollment', to='learn_python_server.student'),
        ),
        migrations.AlterUniqueTogether(
            name='assignment',
            unique_together={('module', 'name')},
        ),
    ]
