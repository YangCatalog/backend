# Copyright The IETF Trust 2020, All Rights Reserved
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

__author__ = "Slavomir Mazur"
__copyright__ = "Copyright The IETF Trust 2020, All Rights Reserved"
__license__ = "Apache License, Version 2.0"
__email__ = "slavomir.mazur@pantheon.tech"

import json
import time

import requests
import utility.log as log
from elasticsearch import Elasticsearch
from flask import Blueprint
from flask import current_app as app
from flask import jsonify, make_response
from sqlalchemy.exc import SQLAlchemyError
from utility.staticVariables import confd_headers, json_headers
from utility.util import create_signature


class HealthcheckBlueprint(Blueprint):

    def __init__(self, name, import_name, static_folder=None, static_url_path=None, template_folder=None,
                 url_prefix=None, subdomain=None, url_defaults=None, root_path=None):
        super().__init__(name, import_name, static_folder, static_url_path, template_folder, url_prefix, subdomain,
                         url_defaults, root_path)


bp = HealthcheckBlueprint('healthcheck', __name__)


@bp.record
def init_logger(state):
    bp.LOGGER = log.get_logger('healthcheck', '{}/healthcheck.log'.format(state.app.config.d_logs))


@bp.before_request
def set_config():
    global ac, db
    ac = app.config
    db = ac.sqlalchemy


### ROUTE ENDPOINT DEFINITIONS ###
@bp.route('/services-list', methods=['GET'])
def get_services_list():
    response_body = []
    service_endpoints = ['my-sql', 'elk', 'confd', 'yang-search-admin', 'yang-validator-admin',
                         'yangre-admin', 'nginx', 'rabbitmq', 'yangcatalog']
    service_names = ['MySQL', 'Elasticsearch', 'ConfD', 'YANG search', 'YANG validator', 'YANGre', 'NGINX', 'RabbitMQ', 'YangCatalog']
    for name, endpoint in zip(service_names, service_endpoints):
        pair = {'name': name, 'endpoint': endpoint}
        response_body.append(pair)
    return make_response(jsonify(response_body), 200)


@bp.route('/my-sql', methods=['GET'])
def health_check_mysql():
    try:
        if db is not None:
            bp.LOGGER.info('Successfully connected to database: {}'.format(ac.db_name_users))
            tables = db.inspect(db.engine).get_table_names()
            if len(tables):
                response = {'info': 'MySQL is running',
                            'status': 'running',
                            'message': '{} tables available in the database: {}'.format(len(tables), ac.db_name_users)}
            else:
                response = {'info': 'MySQL is running',
                            'status': 'problem',
                            'message': 'No tables found in the database: {}'.format(ac.db_name_users)}
            bp.LOGGER.info('{} tables available in the database: {}'.format(len(tables), ac.db_name_users))
            return make_response(jsonify(response), 200)
    except SQLAlchemyError as err:
        bp.LOGGER.error('Cannot connect to database. MySQL error: {}'.format(err))
        if err.args[0] in [1044, 1045]:
            return make_response(jsonify({'info': 'Not OK - Access denied',
                                          'status': 'down',
                                          'error': 'MySQL error: {}'.format(err)}), 200)
        else:
            return make_response(jsonify({'info': 'Not OK - MySQL is not running',
                                          'status': 'down',
                                          'error': 'MySQL error: {}'.format(err)}), 200)


@bp.route('/elk', methods=['GET'])
def health_check_elk():
    service_name = 'Elasticsearch'
    try:
        if ac.db_es_aws:
            es = Elasticsearch([ac.db_es_host], http_auth=(ac.s_elk_credentials[0], ac.s_elk_credentials[1]),
                               scheme="https", port=443)
        else:
            es = Elasticsearch([{'host': '{}'.format(ac.db_es_host), 'port': ac.db_es_port}])

        # try to ping Elasticsearch
        if es.ping():
            bp.LOGGER.info('Successfully connected to Elasticsearch')
            # get health of cluster
            health = es.cluster.health()
            health_status = health.get('status')
            bp.LOGGER.info('Health status of cluster: {}'.format(health_status))
            # get list of indices
            indices = es.indices.get_alias().keys()
            if len(indices) > 0:
                return make_response(jsonify({'info': 'Elasticsearch is running',
                                              'status': 'running',
                                              'message': 'Cluster status: {}'.format(health_status)}), 200)
            else:
                return make_response(jsonify({'info': 'Elasticsearch is running',
                                              'status': 'problem',
                                              'message': 'Cluster status: {} Number of indices: {}'
                                              .format(health_status, len(indices))}), 200)
        else:
            bp.LOGGER.info('Cannot connect to Elasticsearch database')
            return make_response(jsonify({'info': 'Not OK - Elasticsearch is not running',
                                          'status': 'down',
                                          'error': 'Cannot ping Elasticsearch'}), 200)
    except Exception as err:
        bp.LOGGER.error('Cannot connect to Elasticsearch database. Error: {}'.format(err))
        return make_response(jsonify(error_response(service_name, err)), 200)


@bp.route('/confd', methods=['GET'])
def health_check_confd():
    service_name = 'ConfD'
    confd_prefix = '{}://{}:{}'.format(ac.g_protocol_confd, ac.w_confd_ip, ac.w_confd_port)

    try:
        # Check if ConfD is running
        response = requests.get('{}/restconf'.format(confd_prefix),
                                auth=(ac.s_confd_credentials[0], ac.s_confd_credentials[1]), headers=confd_headers)
        if response.status_code == 200:
            bp.LOGGER.info('ConfD is running')
            # Check if ConfD is filled with data
            module_name = 'ietf-syslog,2018-03-15,ietf'
            response = requests.get('{}/restconf/data/yang-catalog:catalog/modules/module={}'.format(confd_prefix, module_name),
                                    auth=(ac.s_confd_credentials[0], ac.s_confd_credentials[1]), headers=confd_headers)
            bp.LOGGER.info('Status code {} while getting data of {} module'.format(response.status_code, module_name))
            if response.status_code != 200 and response.status_code != 201 and response.status_code != 204:
                response = {'info': 'Not OK - ConfD is not filled',
                            'status': 'problem',
                            'message': 'Cannot get data of yang-catalog:modules'}
                return make_response(jsonify(response), 200)
            else:
                module_data = response.json()
                num_of_modules = len(module_data['yang-catalog:module'])
                bp.LOGGER.info('{} module successfully loaded from ConfD'.format(module_name))
                if num_of_modules > 0:
                    return make_response(jsonify({'info': 'ConfD is running',
                                                  'status': 'running',
                                                  'message': '{} module successfully loaded from ConfD'.format(module_name)}), 200)
                else:
                    return make_response(jsonify({'info': 'ConfD is running',
                                                  'status': 'problem',
                                                  'message': 'ConfD is running but no modules loaded'}), 200)
        else:
            bp.LOGGER.info('Cannot get data from /restconf/data')
            err = 'Cannot get data from /restconf/data'
            return make_response(jsonify(error_response(service_name, err)), 200)
    except Exception as err:
        bp.LOGGER.error('Cannot ping {}. Error: {}'.format(service_name, err))
        return make_response(jsonify(error_response(service_name, err)), 200)


@bp.route('/yang-search', methods=['GET'])
def health_check_yang_search():
    service_name = 'yang-search'
    yang_search_preffix = '{}://{}/yang-search'.format(ac.g_protocol_api, ac.w_ip)
    body = json.dumps({'input': {'data': 'ping'}})
    signature = create_signature(ac.s_flask_secret_key, body)
    headers = {**json_headers,
               'X-YC-Signature': 'sha1={}'.format(signature)}
    try:
        response = requests.post('{}/ping'.format(yang_search_preffix), data=body, headers=headers)
        bp.LOGGER.info('yang-search responded with a code {}'.format(response.status_code))
        if response.status_code == 200:
            return make_response(jsonify({'info': '{} is available'.format(service_name),
                                          'status': 'running',
                                          'message': '{} responded with a code {}'.format(service_name, response.status_code)}), 200)
        elif response.status_code == 400 or response.status_code == 404:
            err = json.loads(response.text).get('error')
            return make_response(jsonify({'info': '{} is available'.format(service_name),
                                          'status': 'problem',
                                          'message': '{} responded with a message: {}'.format(service_name, err)}), 200)
        else:
            err = '{} responded with a code {}'.format(service_name, response.status_code)
            return make_response(jsonify(error_response(service_name, err)), 200)
    except Exception as err:
        bp.LOGGER.error('Cannot ping {}. Error: {}'.format(service_name, err))
        return make_response(jsonify(error_response(service_name, err)), 200)


@bp.route('/yang-validator', methods=['GET'])
def health_check_yang_validator():
    service_name = 'yang-validator'
    yang_validator_preffix = '{}://{}/yangvalidator'.format(ac.g_protocol_api, ac.w_ip)
    body = json.dumps({'input': {'data': 'ping'}})
    try:
        response = requests.post('{}/ping'.format(yang_validator_preffix), data=body, headers=json_headers)
        bp.LOGGER.info('yang-validator responded with a code {}'.format(response.status_code))
        if response.status_code == 200:
            return make_response(jsonify({'info': '{} is available'.format(service_name),
                                          'status': 'running',
                                          'message': '{} responded with a code {}'.format(service_name, response.status_code)}), 200)
        elif response.status_code == 400 or response.status_code == 404:
            return make_response(jsonify({'info': '{} is available'.format(service_name),
                                          'status': 'problem',
                                          'message': '{} responded with a code {}'.format(service_name, response.status_code)}), 200)
        else:
            err = '{} responded with a code {}'.format(service_name, response.status_code)
            return make_response(jsonify(error_response(service_name, err)), 200)
    except Exception as err:
        bp.LOGGER.error('Cannot ping {}. Error: {}'.format(service_name, err))
        return make_response(jsonify(error_response(service_name, err)), 200)


@bp.route('/yangre', methods=['GET'])
def health_check_yangre():
    service_name = 'yangre'
    yangre_preffix = '{}://{}/yangre'.format(ac.g_protocol_api, ac.w_ip)
    body = json.dumps({'input': {'data': 'ping'}})
    try:
        response = requests.post('{}/ping'.format(yangre_preffix), data=body, headers=json_headers)
        bp.LOGGER.info('yangre responded with a code {}'.format(response.status_code))
        if response.status_code == 200:
            return make_response(jsonify({'info': '{} is available'.format(service_name),
                                          'status': 'running',
                                          'message': 'yangre responded with a code {}'.format(response.status_code)}), 200)
        elif response.status_code == 400 or response.status_code == 404:
            return make_response(jsonify({'info': '{} is available'.format(service_name),
                                          'status': 'problem',
                                          'message': 'yangre responded with a code {}'.format(response.status_code)}), 200)
        else:
            err = 'yangre responded with a code {}'.format(response.status_code)
            return make_response(jsonify(error_response(service_name, err)), 200)
    except Exception as err:
        bp.LOGGER.error('Cannot ping {}. Error: {}'.format(service_name, err))
        return make_response(jsonify(error_response(service_name, err)), 200)


@bp.route('/nginx', methods=['GET'])
def health_check_nginx():
    service_name = 'NGINX'
    preffix = '{}://{}'.format(ac.g_protocol_api, ac.w_ip)
    try:
        response = requests.get('{}/nginx-health'.format(preffix), headers=json_headers)
        bp.LOGGER.info('NGINX responded with a code {}'.format(response.status_code))
        if response.status_code == 200 and response.text == 'healthy':
            return make_response(jsonify({'info': 'NGINX is available',
                                          'status': 'running',
                                          'message': 'NGINX responded with a code {}'.format(response.status_code)}), 200)
        else:
            return make_response(jsonify({'info': 'Not OK - NGINX is not available',
                                          'status': 'problem',
                                          'message': 'NGINX responded with a code {}'.format(response.status_code)}), 200)
    except Exception as err:
        bp.LOGGER.error('Cannot ping {}. Error: {}'.format(service_name, err))
        return make_response(jsonify(error_response(service_name, err)), 200)


@bp.route('/rabbitmq', methods=['GET'])
def health_check_rabbitmq():
    service_name = 'RabbitMQ'

    arguments = ['run_ping', 'ping']
    preffix = '{}://{}/api/job'.format(ac.g_protocol_api, ac.w_ip)
    try:
        job_id = ac.sender.send('#'.join(arguments))
        if job_id:
            bp.LOGGER.info('Sender successfully connected to RabbitMQ')
        response_type = 'In progress'
        while response_type == 'In progress':
            response = requests.get('{}/{}'.format(preffix, job_id), headers=json_headers)
            response_type = response.json()['info']['result']
            if response.status_code == 200 and response_type == 'Finished successfully':
                break
            else:
                time.sleep(2)
        bp.LOGGER.info('Ping job responded with a message: {}'.format(response_type))
        return make_response(jsonify({'info': '{} is available'.format(service_name),
                                      'status': 'running',
                                      'message': 'Ping job responded with a message: {}'.format(response_type)}), 200)
    except Exception as err:
        if len(err) == 0:
            err = 'Check yang.log file for more details!'
        bp.LOGGER.error('Cannot ping {}. Error: {}'.format(service_name, err))
        return make_response(jsonify(error_response(service_name, err)), 200)


### ROUTE ENDPOINT DEFINITIONS - ADMIN SPECIFIC ###
@bp.route('/yangre-admin', methods=['GET'])
def health_check_yangre_admin():
    service_name = 'yangre'
    yangre_preffix = '{}://{}/yangre'.format(ac.g_protocol_api, ac.w_ip)

    pattern = '[0-9]*'
    content = '123456789'
    body = json.dumps({'pattern': pattern, 'content': content, 'inverted': False, 'pattern_nb': '1'})
    try:
        response = requests.post('{}/v1/yangre'.format(yangre_preffix), data=body, headers=json_headers)
        bp.LOGGER.info('yangre responded with a code {}'.format(response.status_code))
        if response.status_code == 200:
            response_message = response.json()
            if response_message['yangre_output'] == '':
                return make_response(jsonify({'info': '{} is available'.format(service_name),
                                              'status': 'running',
                                              'message': 'yangre successfully validated string'}), 200)
            else:
                return make_response(jsonify({'info': '{} is available'.format(service_name),
                                              'status': 'problem',
                                              'message': response_message['yangre_output']}), 200)
        elif response.status_code == 400 or response.status_code == 404:
            return make_response(jsonify({'info': '{} is available'.format(service_name),
                                          'status': 'problem',
                                          'message': 'yangre responded with a code {}'.format(response.status_code)}), 200)
        else:
            err = 'yangre responded with a code {}'.format(response.status_code)
            return make_response(jsonify(error_response(service_name, err)), 200)
    except Exception as err:
        bp.LOGGER.error('Cannot ping {}. Error: {}'.format(service_name, err))
        return make_response(jsonify(error_response(service_name, err)), 200)


@bp.route('/yang-validator-admin', methods=['GET'])
def health_check_yang_validator_admin():
    service_name = 'yang-validator'
    yang_validator_preffix = '{}://{}/yangvalidator'.format(ac.g_protocol_api, ac.w_ip)

    rfc_number = '7223'
    body = json.dumps({'rfc': rfc_number, 'latest': True})
    try:
        response = requests.post('{}/v2/rfc'.format(yang_validator_preffix), data=body, headers=json_headers)
        bp.LOGGER.info('yang-validator responded with a code {}'.format(response.status_code))
        if response.status_code == 200:
            response_message = response.json()
            if response_message:
                return make_response(jsonify({'info': '{} is available'.format(service_name),
                                              'status': 'running',
                                              'message': '{} successfully fetched and validated RFC{}'.format(service_name, rfc_number)}), 200)
            else:
                return make_response(jsonify({'info': '{} is available'.format(service_name),
                                              'status': 'problem',
                                              'message': 'RFC{} responded with empty body'.format(rfc_number)}), 200)
        elif response.status_code == 400 or response.status_code == 404:
            return make_response(jsonify({'info': '{} is available'.format(service_name),
                                          'status': 'problem',
                                          'message': '{} responded with a code {}'.format(service_name, response.status_code)}), 200)
        else:
            err = '{} responded with a code {}'.format(service_name, response.status_code)
            return make_response(jsonify(error_response(service_name, err)), 200)
    except Exception as err:
        bp.LOGGER.error('Cannot ping {}. Error: {}'.format(service_name, err))
        return make_response(jsonify(error_response(service_name, err)), 200)


@bp.route('/yang-search-admin', methods=['GET'])
def health_check_yang_search_admin():
    service_name = 'yang-search'
    yang_search_preffix = '{}://{}/api/search'.format(ac.g_protocol_api, ac.w_ip)
    module_name = 'ietf-syslog,2018-03-15,ietf'
    try:
        response = requests.get('{}/modules/{}'.format(yang_search_preffix, module_name), headers=json_headers)
        bp.LOGGER.info('yang-search responded with a code {}'.format(response.status_code))
        if response.status_code == 200:
            response_message = response.json()
            if response_message['module'] and len(response_message['module']) > 0:
                return make_response(jsonify({'info': '{} is available'.format(service_name),
                                              'status': 'running',
                                              'message': '{} module successfully found'.format(module_name)}), 200)
            else:
                return make_response(jsonify({'info': '{} is available'.format(service_name),
                                              'status': 'problem',
                                              'message': 'Module {} not found'.format(module_name)}), 200)
        elif response.status_code == 400 or response.status_code == 404:
            err = json.loads(response.text).get('error')
            return make_response(jsonify({'info': '{} is available'.format(service_name),
                                          'status': 'problem',
                                          'message': '{} responded with a message: {}'.format(service_name, err)}), 200)
        else:
            err = '{} responded with a code {}'.format(service_name, response.status_code)
            return make_response(jsonify(error_response(service_name, err)), 200)
    except Exception as err:
        bp.LOGGER.error('Cannot ping {}. Error: {}'.format(service_name, err))
        return make_response(jsonify(error_response(service_name, err)), 200)


@bp.route('/yangcatalog', methods=['GET'])
def health_check_yangcatalog():
    service_name = 'yangcatalog'
    status = 'running'
    message = 'All URLs responded with status code 200'
    additional_info = []

    urls = [{'url': 'http://yangcatalog.org', 'verify': True},
            {'url': 'http://www.yangcatalog.org', 'verify': True},
            {'url': 'https://yangcatalog.org', 'verify': True},
            {'url': 'https://www.yangcatalog.org', 'verify': True},
            {'url': 'http://yangvalidator.com', 'verify': True},
            {'url': 'http://www.yangvalidator.com', 'verify': True},
            {'url': 'https://yangvalidator.com', 'verify': True},
            {'url': 'https://www.yangvalidator.com', 'verify': True},
            {'url': 'http://18.224.127.129', 'verify': False},
            {'url': 'https://18.224.127.129', 'verify': False},
            {'url': 'http://[2600:1f16:ba:200:a10d:3212:e763:e720]', 'verify': False},
            {'url': 'https://[2600:1f16:ba:200:a10d:3212:e763:e720]', 'verify': False}
            ]

    for item in urls:
        url = item.get('url')
        result = {}
        result['label'] = url
        try:
            response = requests.get(url, verify=item.get('verify', True))
            status_code = response.status_code
            bp.LOGGER.info('URl: {} Status code: {}'.format(url, status_code))
            result['message'] = '{} OK'.format(status_code)
        except:
            result['message'] = '500 NOT OK'
            status = 'problem'
            message = 'Problem occured, see additional info'
        additional_info.append(result)

    return make_response(jsonify({'info': '{} is available'.format(service_name),
                                  'status': status,
                                  'message': message,
                                  'additional_info': additional_info}), 200)


@bp.route('/cronjobs', methods=['GET'])
def check_cronjobs():
    try:
        with open('{}/cronjob.json'.format(ac.d_temp), 'r') as f:
            file_content = json.load(f)
    except:
        return make_response(jsonify({'error': 'Data about cronjobs are not available.'}), 400)
    return make_response(jsonify({'data': file_content}), 200)


### HELPER DEFINITIONS ###
def error_response(service_name, err):
    return {'info': 'Not OK - {} is not available'.format(service_name),
            'status': 'down',
            'error': 'Cannot ping {}. Error: {}'.format(service_name, err)
            }
