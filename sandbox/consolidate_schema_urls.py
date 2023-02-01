"""
Make sure the schema URLs in the "dependents" and "dependencies" fields match those in the main record.

Each module can optionally contain information on modules that are it's dependents and dependencies.
This information is limited to the module name and optionally it's revision and schema URL.
This URL should be the same as the one found in the module's own record.
"""

import json

import requests

from redisConnections.redisConnection import RedisConnection
from utility.create_config import create_config


def main():
    config = create_config()
    credentials = config.get('Secrets-Section', 'confd-credentials', fallback='admin admin').strip('"').split()
    yangcatalog_api_prefix = config.get('Web-Section', 'yangcatalog-api-prefix')
    redis = RedisConnection()
    redis_json = json.loads(redis.get_all_modules()).values()

    name_rev_dict = {f'{i["name"]}@{i["revision"]}': i for i in redis_json}

    for k, v in name_rev_dict.items():
        changed = False
        for relationship in ('dependents', 'dependencies'):
            for relative in v.get(relationship, []):
                if 'revision' not in relative:
                    continue
                if (
                    relative.get('schema')
                    != (
                        real_schema := name_rev_dict.get(f'{relative["name"]}@{relative["revision"]}', {}).get('schema')
                    )
                    and real_schema
                ):
                    relative['schema'] = real_schema
                    changed = True
        if changed:
            redis.set_redis_module(v, f'{k}/{v["organization"]}')

    requests.post(f'{yangcatalog_api_prefix}/load-cache', None, auth=(credentials[0], credentials[1]))


if __name__ == '__main__':
    main()
