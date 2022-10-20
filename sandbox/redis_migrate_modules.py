"""
This script will copy all the modules from Redis db=0 to db=1.
"""

import json

import redis

from redisConnections.redisConnection import RedisConnection


def main():
    redis_cache = redis.Redis(host='yc-redis', port=6379, db=0)
    redis_connection = RedisConnection()

    data = redis_cache.get('modules-data')
    modules_raw = (data or b'{}').decode('utf-8')
    modules = json.loads(modules_raw).get('module')

    redis_connection.populate_modules(modules)
    redis_connection.reload_modules_cache()


if __name__ == '__main__':
    main()
