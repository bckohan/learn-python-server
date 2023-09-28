from urllib.parse import urlparse, urlunparse, urlencode, parse_qsl
from pathlib import Path
import tempfile
from django.conf import settings
from django.utils import timezone
import os
import hashlib


def num_lines(file):
    def blocks(files, size=65536):
        while True:
            b = files.read(size)
            if not b:
                break
            yield b

    count = sum(buffer.count('\n') for buffer in blocks(file))
    file.seek(0)
    return count


def calculate_sha256(file_handle):
    sha256_hash = hashlib.sha256()
    for byte_block in iter(lambda: file_handle.read(4096), b''):
        sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def headers_match(file1, file2, check_size):
    while check_size > 0:
        if file1.readline() != file2.readline():
            break
        check_size -= 1
    return check_size == 0


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
