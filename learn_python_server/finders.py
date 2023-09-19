from django.contrib.staticfiles.finders import BaseFinder, FileSystemFinder
from django.core.files.storage import FileSystemStorage
from learn_python_server.models import DocBuild
from django.conf import settings


class DocBuildFinder(FileSystemFinder):
    """
    For the development server - makes documentation builds visible to the static file finders
    which are used during static file serving via Django.
    """
    def __init__(self, *args, **kwargs):
        self.locations = [('', settings.STATIC_ROOT)]
        self.storages = {}
        # for prefix, root in [('', build.path) for build in DocBuild.objects.all()]:
        #     if (prefix, root) not in self.locations:
        #         self.locations.append((prefix, root))
        for prefix, root in self.locations:
            filesystem_storage = FileSystemStorage(location=root)
            filesystem_storage.prefix = prefix
            self.storages[root] = filesystem_storage
        BaseFinder.__init__(self, *args, **kwargs)

    def check(self, **kwargs):
        return []
