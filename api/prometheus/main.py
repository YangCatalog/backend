# Copyright The IETF Trust 2019, All Rights Reserved
# Copyright 2018 Cisco and its affiliates
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

__author__ = 'Miroslav Kovac'
__copyright__ = 'Copyright 2018 Cisco and its affiliates, Copyright The IETF Trust 2019, All Rights Reserved'
__license__ = 'Apache License, Version 2.0'
__email__ = 'miroslav.kovac@pantheon.tech'

import sys
import time

import requests
from flask.globals import g, request
from flask.helpers import make_response
from prometheus_client import (CONTENT_TYPE_LATEST, Counter, Gauge, Histogram,
                               core, generate_latest)

if sys.version_info >= (3, 4):
    from urllib.parse import parse_qs, urlparse
else:
    from urlparse import parse_qs, urlparse


def monitor(app):
    def before_request():
        g.start_time = time.time()
        http_concurrent_request_count.inc()
        content_length = request.content_length
        if (content_length):
            http_request_size_bytes.labels(request.method, request.path).observe(content_length)

    def after_request(response):
        request_latency = time.time() - g.start_time
        http_request_latency_ms.labels(request.method, request.path).observe(request_latency)

        http_concurrent_request_count.dec()

        username = 'Unknown'
        if request.authorization:
            username = request.authorization.get('username')

        http_request_count.labels(request.method, request.path, response.status_code, username).inc()
        http_response_size_bytes.labels(request.method, request.path).observe(response.calculate_content_length())
        return response

    http_request_latency_ms = Histogram('http_request_latency_ms', 'HTTP Request Latency',
                                        ['method', 'endpoint'])

    http_request_size_bytes = Histogram('http_request_size_bytes', 'HTTP request size in bytes',
                                        ['method', 'endpoint'])

    http_response_size_bytes = Histogram('http_response_size_bytes', 'HTTP response size in bytes',
                                         ['method', 'endpoint'])

    http_request_count = Counter('http_request_count', 'HTTP Request Count', ['method', 'endpoint', 'http_status', 'user'])
    http_concurrent_request_count = Gauge('http_concurrent_request_count', 'Flask Concurrent Request Count')
    app.before_request(before_request)
    app.after_request(after_request)

    app.add_url_rule('/metrics', 'prometheus_metrics', view_func=metrics)
    res = requests.get('http://localhost:9090/api/v1/query?query=http_request_count',
                       headers={'Accept': 'application/json'})

    results = res.json()['data']['result']
    for result in results:
        val = int(result['value'][1])
        method = result['metric'].get('method') or 0
        endpoint = result['metric'].get('endpoint') or 0
        http_status = result['metric'].get('http_status') or 0
        user = result['metric'].get('user') or 0
        http_request_count.labels(method, endpoint, http_status, user).inc(val)


def metrics():
    registry = core.REGISTRY
    params = parse_qs(urlparse(request.path).query)
    if 'name[]' in params:
        registry = registry.restricted_registry(params['name[]'])
    output = generate_latest(registry)  # pyright: ignore
    response = make_response(output)
    response.headers['Content-Type'] = CONTENT_TYPE_LATEST
    return response
