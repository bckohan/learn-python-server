from urllib.parse import urlparse, urlunparse, urlencode, parse_qsl
from pathlib import Path
import tempfile
from django.conf import settings
from django.utils import timezone
import os


class TemporaryDirectory(tempfile.TemporaryDirectory):
    
    def __init__(self, **kwargs):
        dir = kwargs.pop('dir', getattr(settings, 'TMP_DIR', None))
        if dir:
            os.makedirs(dir, exist_ok=True)
        super().__init__(**kwargs)
        self.path = Path(self.name)


def normalize_repository(repository):
    norm_url = normalize_url(repository)
    if norm_url.endswith('.git'):
        norm_url = norm_url[:-4]
    return norm_url


def normalize_url(url):
    # Parse the URL into its components
    parsed = urlparse(url)

    # Normalize the path
    path = Path(parsed.path).resolve().as_posix()

    # Normalize the query parameters (sort them)
    query = urlencode(sorted(parse_qsl(parsed.query)))

    # Construct the normalized URL
    normalized = urlunparse((
        parsed.scheme.lower(),  # Scheme in lowercase
        parsed.netloc.lower(),  # Network location in lowercase
        path,
        parsed.params,
        query,
        parsed.fragment
    ))

    return normalized
