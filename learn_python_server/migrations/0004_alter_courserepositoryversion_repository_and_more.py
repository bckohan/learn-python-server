# Generated by Django 4.2.5 on 2023-09-23 06:37

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('learn_python_server', '0003_alter_enrollment_repository'),
    ]

    operations = [
        migrations.AlterField(
            model_name='courserepositoryversion',
            name='repository',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='versions', to='learn_python_server.courserepository'),
        ),
        migrations.AlterField(
            model_name='module',
            name='repository',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='modules', to='learn_python_server.courserepository'),
        ),
        migrations.AlterField(
            model_name='studentrepositoryversion',
            name='repository',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='versions', to='learn_python_server.studentrepository'),
        ),
    ]