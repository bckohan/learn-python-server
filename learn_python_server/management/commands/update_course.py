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
from learn_python_server.models import (
    Assignment,
    Course,
    CourseRepository,
    CourseRepositoryVersion,
    DocBuild,
    Module,
)
from learn_python_server.utils import TemporaryDirectory


class Command(BaseCommand):
    help = (
        'Clone the repository for the given course(s) and update the courses based on the repo. This includes '
        'updating the modules and assignments as well as rebuilding the documentation.'
    )

    def add_arguments(self, parser):

        group = parser.add_mutually_exclusive_group(required=False)

        group.add_argument(
            '-r',
            '--repository',
            dest='repository',
            default=getattr(
                settings,
                'DEFAULT_COURSE_REPOSITORY',
                'https://github.com/bckohan/learn-python'
            ),
            type=str,
            help=(
                'Clone and build the docs for the current version of the course repository. '
                'These will be served at /'
            )
        )

        group.add_argument(
            '-c',
            '--course',
            dest='course',
            type=str,
            help=(
                'Clone and build the docs for the specified course. Either the name or the '
                'ID of the course.'
            )
        )

        parser.add_argument(
            '-f',
            '--force',
            dest='force',
            action='store_true',
            default=False,
            help=(
                'Force the update even if the repository has not changed since the last update.'
            )
        )

    def handle(self, **options):
        with transaction.atomic():
            qry = Q()
            repository = None
            if options['repository']:
                repository = CourseRepository.objects.get_or_create(uri=options['repository'])[0]
                qry = Q(repository=repository) & (Q(ended__lte=now()) | Q(ended__isnull=True))
            elif options['course']:
                qry = Q(name=options['course'])
                try:
                    qry |= Q(pk=int(options['course']))
                except (TypeError, ValueError):
                    pass
            
            courses = Course.objects.filter(qry)
            if not courses.exists():
                if repository and input(('No courses found for repository {}. Would you like to create one? [y/N] ').format(repository)).strip().lower() in ['y', 'yes']:
                    course_name = input(('What is the name of the course? '))
                    course = Course.objects.create(
                        name=course_name,
                        repository=repository
                    )
                    courses = Course.objects.filter(pk=course.pk)
                else:
                    raise CommandError(('No course found matching {}').format(str(qry)))
            
            # should only ever be one! if this errors out there's something wrong with the data model
            repository = CourseRepository.objects.get(courses__in=courses)
            self.stdout.write(('Updating course repository {}...').format(repository.uri))

            with repository:

                repo_version, new_version = CourseRepositoryVersion.objects.get_or_create(
                    repository=repository,
                    git_hash=repository.commit_hash(),
                    git_branch=repository.cloned_branch(),
                    defaults={
                        'commit_count': repository.commit_count()
                    }
                )

                if not new_version and not options['force']:
                    self.stdout.write(('Repository has not changed since last update.'))
                    return

                repository.install()
                doc_html = repository.doc_build()
                if not doc_html.is_dir():
                    raise CommandError(('Could not find built documentation in {}').format(doc_html))
                
                course_structure = repository.course_structure()

                def list_to_str(list_or_str):
                    if not list_or_str:
                        return ''
                    if isinstance(list_or_str, str):
                        return list_or_str
                    return '\n'.join(list_or_str)

                modules = set()
                for course in courses:
                    for module, tasks in course_structure.items():
                        number = re.search(r'(?P<number>\d+)?$', module).groupdict().get('number', None)
                        number = int(number) if number else None
                        mod_obj, mod_is_new = Module.objects.get_or_create(
                            name=module,
                            repository=repository,
                            defaults={
                                'added': repo_version,
                                'number': number
                            }
                        )
                        if not mod_is_new and mod_obj.number != number:
                            mod_obj.number = number
                            mod_obj.save()
                        elif mod_is_new:
                            self.stdout.write(('Adding module {}').format(mod_obj))
                        modules.add(mod_obj.pk)

                        current_tasks = set()
                        for task_name, task_info in tasks.items():
                            test_parts = task_info['test'].split('::')
                            meta = {
                                'number': int(task_info['number']),
                                'todo': task_info['todo'],
                                'hints': list_to_str(task_info['hints']),
                                'requirements': list_to_str(task_info['requirements']),
                                'identifier': '::'.join([str(Path(test_parts[0]).resolve().relative_to(repository.local.resolve())), *test_parts[1:]])
                            }
                            task_obj, task_is_new = Assignment.objects.get_or_create(
                                name=task_name,
                                module=mod_obj,
                                defaults={
                                    'added': repo_version,
                                    **meta
                                }
                            )
                            current_tasks.add(task_obj.pk)
                            if not task_is_new:
                                for attr, val in meta.items():
                                    setattr(task_obj, attr, val)
                                task_obj.save()
                            else:
                                self.stdout.write(('Adding assignment {}').format(task_obj))

                    for removed_task in Assignment.objects.filter(module=mod_obj).exclude(pk__in=current_tasks):
                        self.stdout.write(('Removing assignment {}').format(removed_task))
                        removed_task.ended = repo_version
                        removed_task.save()

                for removed_module in Module.objects.filter(repository=repository).exclude(pk__in=modules):
                    self.stdout.write(('Removing module {}').format(removed_module))
                    removed_module.ended = repo_version
                    removed_module.save()

                doc_build, new_build = DocBuild.objects.get_or_create(
                    repository=repo_version
                )
                if not doc_build.path.is_dir() or new_build:
                    shutil.copytree(doc_html, doc_build.path, dirs_exist_ok=True)

                # delete older doc builds for this repo
                for old_build in DocBuild.objects.filter(repository__repository=repository).exclude(pk=doc_build.pk):
                    self.stdout.write(('Deleting old build {}').format(old_build))
                    if Path(old_build.path).is_dir():
                        shutil.rmtree(old_build.path)
                    old_build.delete()
