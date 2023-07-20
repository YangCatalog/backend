import logging

bind = 'unix:/var/run/yang/yang-catalog.sock'
# umask = os.umask('007')

workers = 5

max_requests = 10000
timeout = 1500
graceful_timeout = 1000
keep_alive = 2

user = 'yang'
group = 'yang'

preload = True

accesslog = '/var/yang/logs/uwsgi/yang-catalog-access.log'
errorlog = '/var/yang/logs/uwsgi/yang-catalog-error.log'
loglevel = 'debug'
# change log format
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'
worker_class = 'gevent'


class HealthcheckFilter(logging.Filter):
    def filter(self, record):
        return record.getMessage().find('Amazon-Route53-Health-Check-Service') == -1


def on_starting(server):
    server.log.access_log.addFilter(HealthcheckFilter())
    server.log.error_log.addFilter(HealthcheckFilter())
