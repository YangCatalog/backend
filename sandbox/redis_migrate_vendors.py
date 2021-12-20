"""
This script will copy all the vendors from Redis db=0 to db=4.
"""

import json

import redis
from redisConnections.redisConnection import RedisConnection


def main():
    redis_cache = redis.Redis(host='yc-redis', port=6379, db=0)
    redisConnection = RedisConnection()

    data = redis_cache.get('vendors-data')
    vendors_raw = (data or b'{}').decode('utf-8')
    vendors = json.loads(vendors_raw).get('vendor')

    redisConnection.populate_implementation(vendors)
    redisConnection.reload_vendors_cache()


if __name__ == '__main__':
    main()
