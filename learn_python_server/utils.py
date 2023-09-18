from urllib.parse import urlparse, urlunparse, urlencode, parse_qsl
from pathlib import Path


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
