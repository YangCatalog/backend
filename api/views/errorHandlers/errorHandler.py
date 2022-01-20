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

__author__ = 'Miroslav Kovac'
__copyright__ = 'Copyright The IETF Trust 2020, All Rights Reserved'
__license__ = 'Apache License, Version 2.0'
__email__ = 'miroslav.kovac@pantheon.tech'

from flask import Blueprint, jsonify, make_response

bp = Blueprint('error-handling', __name__)


@bp.app_errorhandler(404)
def not_found(e):
    """Error handler for 404"""
    return make_response(jsonify({'error': 'Not found -- in api code',
                                  'description': e.description}), 404)


@bp.app_errorhandler(401)
def unauthorized(e):
    """Return unauthorized error message"""
    return make_response(jsonify({'error': 'Unauthorized access',
                                  'description': e.description}), 401)


@bp.app_errorhandler(400)
def bad_request(e):
    """Return message that can not be resolved"""
    return make_response(jsonify({'error': 'YangCatalog did not understand the message you have sent',
                                  'description': e.description}), 400)


@bp.app_errorhandler(409)
def conflict(e):
    """Return conflict error message"""
    return make_response(jsonify({'error': 'Conflict',
                                  'description': e.description}), 409)
