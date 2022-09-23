import time
import logging
import typing as t
import requests
from datetime import datetime

from parseAndPopulate.resolvers.resolver import Resolver
from redisConnections.redisConnection import RedisConnection


class ExpirationResolver(Resolver):
    def __init__(self, module: dict, logger: logging.Logger, datatracker_failures: list,
                 redis_connection: RedisConnection) -> None:
        """Walks through all the modules and updates them if necessary

        Arguments:
            :param module               (dict) Module with all the metadata
            :param LOGGER               (logging.Logger) formated logger with the specified name
            :param datatracker_failures (list) list of url that failed to get data from Datatracker
            :param redis_connection     (RedisConnection) Connection used to communication with Redis
        """
        self.module = module
        self.logger = logger
        self.datatracker_failures = datatracker_failures
        self.redis_connection = redis_connection
        self.__datatracker_url = 'https://datatracker.ietf.org/api/v1/doc/document/?name={}&states__type=draft&states__slug__in=active,RFC&format=json'

    def resolve(self) -> t.Optional[bool]:
        reference = self.module.get('reference')
        expired = 'not-applicable'
        expires = None
        if self.module.get('maturity-level') == 'ratified':
            expired = False
            expires = None
        if reference is not None and 'datatracker.ietf.org' in reference:
            ref = reference.split('/')[-1]
            rev = None
            if ref.isdigit():
                ref = reference.split('/')[-2]
                rev = reference.split('/')[-1]
            url = self.__datatracker_url.format(ref)
            retry = 6
            while True:
                try:
                    response = requests.get(url)
                    break
                except Exception as e:
                    retry -= 1
                    self.logger.warning(
                        f'Failed to fetch file content of {ref}')
                    time.sleep(10)
                    if retry == 0:
                        self.logger.error(
                            f'Failed to fetch file content of {ref} for 6 times in a row - SKIPPING.')
                        self.logger.error(e)
                        self.datatracker_failures.append(url)
                        return None

            if response.status_code == 200:
                data = response.json()
                objs = data.get('objects', [])

                expired = True
                expires = None
                if len(objs) == 1:
                    if rev == objs[0].get('rev'):
                        rfc = objs[0].get('rfc')
                        if rfc is None:
                            expires = objs[0]['expires']
                            expired = False

        expired_changed = self.__expired_change(
            self.module.get('expired'), expired)
        expires_changed = self.__expires_change(
            self.module.get('expires'), expires)

        if not expires_changed and not expired_changed:  # nothing changed
            return False

        yang_name_rev = f'{self.module["name"]}@{self.module["revision"]}'
        self.logger.info(
            f'Module {yang_name_rev} changing expiration\n'
            f'FROM: expires: {self.module.get("expires")} expired: {self.module.get("expired")}\n'
            f'TO: expires: {expires} expired: {expired}'
        )

        if expires is not None:
            self.module['expires'] = expires
        self.module['expired'] = expired

        if expires is None and self.module.get('expires') is not None:
            # If the 'expires' property no longer contains a value,
            # delete request need to be done to the Redis to the 'expires' property
            result = self.redis_connection.delete_expires(self.module)
            self.module.pop('expires', None)

            if result:
                self.logger.info(
                    f'expires property removed from {yang_name_rev}')
            else:
                self.logger.error(
                    f'Error while removing expires property from {yang_name_rev}')
        return True

    def __expires_change(self, expires_from_module: t.Optional[str], expires_from_datatracker: t.Optional[str]) -> bool:
        expires_changed = expires_from_module != expires_from_datatracker

        if expires_changed:
            if expires_from_module is None or expires_from_datatracker is None:
                return expires_changed
            # If both values are represented by datetime, compare datetime objets
            elif len(expires_from_module) > 0 and len(expires_from_datatracker) > 0:
                date_format = '%Y-%m-%dT%H:%M:%S'
                return datetime.strptime(expires_from_module[0:19], date_format) != datetime.strptime(expires_from_datatracker[0:19], date_format)

        return expires_changed

    def __expired_change(self, expired_from_module: t.Optional[str], expired_from_datatracker: t.Union[str, bool]) -> bool:
        return expired_from_module != expired_from_datatracker
