import os

from flask_caching import Cache

cache = Cache(
    config={
        'CACHE_TYPE': 'FileSystemCache',
        'CACHE_DIR': os.path.join(os.path.dirname(os.path.abspath(__file__)), 'flask_cache_dir'),
        'CACHE_THRESHOLD': 10,
        'CACHE_DEFAULT_TIMEOUT': 60 * 20,
    },
)
