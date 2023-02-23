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

import json
import os

import requests
from flask.blueprints import Blueprint
from flask.globals import request
from werkzeug.exceptions import abort

from api.authentication.auth import auth
from api.my_flask import app
from utility import message_factory, repoutil
from utility.staticVariables import github_api
from utility.util import create_signature


class YcJobs(Blueprint):
    pass


bp = YcJobs('ycJobs', __name__)


@bp.before_request
def set_config():
    global app_config
    app_config = app.config


@bp.route('/ietf', methods=['GET'])
@auth.login_required
def trigger_ietf_pull():
    assert request.authorization
    username = request.authorization['username']
    if username != 'admin':
        abort(401, description='User must be admin')
    job_id = app_config.sender.send('run_ietf')
    app.logger.info(f'job_id {job_id}')
    return {'job-id': job_id}, 202


@bp.route('/checkCompleteGithub', methods=['POST'])
def check_github():
    app.logger.info('Starting Github Actions check')
    body = json.loads(request.data)
    app.logger.info(f'Body of Github Actions:\n{json.dumps(body)}')

    # Request Authorization
    request_signature = request.headers['X_HUB_SIGNATURE'].split('sha1=')[-1]
    computed_signature = create_signature(app_config.s_secret_key, request.data.decode())

    if request_signature == computed_signature:
        app.logger.info('Authorization successful')
    else:
        app.logger.error('Authorization failed. Request did not come from Github')
        abort(401)

    # Check run result - if completed successfully
    if body.get('check_run', {}).get('status') != 'completed':
        app.logger.error('Github Actions run not completed yet')
        return {'info': 'Run not completed yet - no action was taken'}, 200
    if (conclusion := body.get('check_run', {}).get('conclusion')) != 'success':
        html_url = body.get('check_run', {}).get('html_url')
        app.logger.error(f'Github Actions run finished with conclusion {conclusion}\nMore info: {html_url}')

        # Sending email notification to developers team
        mf = message_factory.MessageFactory()
        mf.send_github_action_email(conclusion, html_url)

        return {'info': f'Run finished with conclusion {conclusion}'}, 200

    # Commit verification
    verify_commit = False
    app.logger.info('Checking commit SHA if it is the commit sent by yang-catalog user.')

    commit_sha = body['check_run']['head_sha']
    if body['repository']['full_name'] == 'yang-catalog/yang' or body['repository']['full_name'] == 'YangModels/yang':
        try:
            with open(app_config.d_commit_dir, 'r') as commit_file:
                for line in commit_file:
                    if commit_sha in line:
                        verify_commit = True
                        break
        except FileNotFoundError:
            abort(404)
    if not verify_commit:
        app.logger.info('Commit verification failed.' ' Commit sent by someone else - not doing anything.')
        return {'info': 'Commit verification failed - sent by someone else'}, 200

    github_repos_url = f'{github_api}/repos'
    yang_models_url = f'{github_repos_url}/YangModels/yang'
    pull_requests_url = f'{yang_models_url}/pulls'

    token_header_value = f'token {app_config.s_yang_catalog_token}'
    app.logger.info(f'Commit {body["check_run"]["head_sha"]} verified')
    # Create PR to YangModels/yang if sent from yang-catalog/yang
    if body['repository']['full_name'] == 'yang-catalog/yang':
        response = repoutil.create_pull_request(
            owner='YangModels',
            repo='yang',
            head_branch='yang-catalog:main',
            base_branch='main',
            headers={'Authorization': token_header_value},
            request_body=repoutil.PullRequestCreationDetail(
                title='Cronjob - daily update of yang files.',
                body='ietf extracted yang modules',
            ),
        )
        if response.status_code == 201:
            app.logger.info('Pull request created successfully')
            return {'info': 'Success'}, 201
        message = f'Could not create a pull request.\nGithub responded with status code {response.status_code}'
        app.logger.error(message)
        return {'info': message}, 200
    # Automatically merge PR if sent from YangModels/yang
    if body['repository']['full_name'] == 'YangModels/yang':
        headers = {'Authorization': f'token {app_config.s_admin_token}', 'accept': 'application/vnd.github+json'}
        pull_requests = requests.get(pull_requests_url, headers=headers).json()
        for pull_request in pull_requests:
            head_sha = pull_request['head']['sha']
            if head_sha != commit_sha:
                continue
            pull_number = pull_request['number']
            app.logger.info(f'Pull request {pull_number} was successful - sending review.')
            approval_response = repoutil.approve_pull_request(
                'YangModels',
                'yang',
                pull_number,
                headers=headers,
                request_body=repoutil.PullRequestApprovingDetail(body='AUTOMATED YANG CATALOG APPROVAL'),
            )
            app.logger.info(f'Review response code {approval_response.status_code}')
            merging_response = repoutil.merge_pull_request(
                'YangModels',
                'yang',
                pull_number,
                headers=headers,
                request_body=repoutil.PullRequestMergingDetail(
                    commit_title='Github Actions job passed',
                    sha=body['check_run']['head_sha'],
                ),
            )
            app.logger.info(
                f'Merge response code {merging_response.status_code}\nMerge response {merging_response.text}',
            )
            return {'info': 'Success'}, 201
        else:
            message = f'No opened pull request found with head sha: {commit_sha}'
            return {'info': message}, 200
    message = f'Owner name verification failed. Owner -> {body["sender"]["login"]}'
    app.logger.warning(message)
    return {'Error': message}, 401


@bp.route('/check-platform-metadata', methods=['POST'])
def trigger_populate():
    app.logger.info('Trigger populate if necessary')
    repoutil.pull(app_config.d_yang_models_dir)
    try:
        assert request.json
        body = json.loads(request.data)
        app.logger.info(f'Body of request:\n{json.dumps(body)}')
        commits = request.json.get('commits') if request.is_json else None
        paths = set()
        new = []
        mod = []
        if commits:
            for commit in commits:
                added = commit.get('added')
                if added:
                    for add in added:
                        if 'platform-metadata.json' in add:
                            paths.add('/'.join(add.split('/')[:-1]))
                            new.append('/'.join(add.split('/')[:-1]))
                modified = commit.get('modified')
                if modified:
                    for m in modified:
                        if 'platform-metadata.json' in m:
                            paths.add('/'.join(m.split('/')[:-1]))
                            mod.append('/'.join(m.split('/')[:-1]))
        if len(paths) > 0:
            mf = message_factory.MessageFactory()
            mf.send_new_modified_platform_metadata(new, mod)
            app.logger.info('Forking the repo')
            try:
                populate_path = os.path.join(os.environ['BACKEND'], 'parseAndPopulate/populate.py')
                arguments = [
                    'python',
                    populate_path,
                    '--result-html-dir',
                    app_config.w_result_html_dir,
                    '--credentials',
                    app_config.s_confd_credentials[0],
                    app_config.s_confd_credentials[1],
                    '--save-file-dir',
                    app_config.d_save_file_dir,
                    'repoLocalDir',
                ]
                arguments = arguments + list(paths) + [app_config.d_yang_models_dir, 'github']
                app_config.sender.send('#'.join(arguments))
            except Exception:
                app.logger.exception('Could not populate after git push')
    except Exception as e:
        app.logger.error(f'Automated github webhook failure - {e}')

    return {'info': 'Success'}


@bp.route('/get-statistics', methods=['GET'])
def get_statistics():
    stats_path = f'{app_config.w_private_directory}/stats/stats.json'
    if os.path.exists(stats_path):
        with open(stats_path, 'r') as reader:
            return reader.read()
    abort(404, description='Statistics file has not been generated yet')


@bp.route('/problematic-drafts', methods=['GET'])
def get_problematic_drafts():
    problematic_drafts_path = f'{app_config.w_public_directory}/drafts/problematic_drafts.json'
    if os.path.exists(problematic_drafts_path):
        with open(problematic_drafts_path, 'r') as reader:
            return reader.read()
    abort(404, description='Problematic drafts file has not been generated yet')
