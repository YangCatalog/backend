"""
This script will copy all the modules from Redis db=0 to db=1.
"""

import json

import redis
from redisConnections.redisConnection import RedisConnection


def main():
    redis_cache = redis.Redis(host='yc-redis', port=6379, db=0)
    redisConnection = RedisConnection()

    data = redis_cache.get('modules-data')
    modules_raw = (data or b'{}').decode('utf-8')
    modules = json.loads(modules_raw).get('module')

    redisConnection.populate_modules(modules)
    redisConnection.reload_modules_cache()


if __name__ == '__main__':
    main()
