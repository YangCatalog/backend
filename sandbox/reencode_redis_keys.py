from urllib.parse import quote, unquote

from redisConnections.redisConnection import RedisConnection


def main():
    vendors_db = RedisConnection().vendorsDB
    for key in vendors_db.scan_iter():
        key = key.decode()
        old_key = key
        key = key.replace('RSP2/RSP3', 'RSP2%2FRSP3')
        key = key.replace('#', ' ')
        key = '/'.join(quote(unquote(part), safe='') for part in key.split('/'))
        if key != old_key:
            try:
                vendors_db.rename(old_key, key)
                print(f'renamed {old_key} to {key}')
            except Exception:
                pass  # old_key doesn't exist anymore


if __name__ == '__main__':
    main()
