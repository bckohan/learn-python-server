# Generated by Django 4.2.5 on 2023-09-28 00:02

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('learn_python_server', '0001_initial'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='assignment',
            unique_together={('module', 'name')},
        ),
    ]
