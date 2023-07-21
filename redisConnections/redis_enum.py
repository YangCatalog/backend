import json
import os.path
from enum import IntEnum

from utility.create_config import create_config

config = create_config()
redis_dir = config.get('Directory-Section', 'redis-dir', fallback='')
with open(os.path.join(redis_dir, 'redis_databases.json'), 'r') as f:
    redis_db_config = json.load(f)

RedisEnum = IntEnum('RedisEnum', redis_db_config)
