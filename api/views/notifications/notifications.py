from flask import Blueprint, make_response, jsonify

from api.my_flask import app


class NotificationsBlueprint(Blueprint):
    pass


bp = NotificationsBlueprint('notifications', __name__)


@bp.before_request
def set_config():
    global app_config, users
    app_config = app.config
    users = app_config.redis_users


@bp.route('/unsubscribe_from_emails/<path:emails_type>/><path:email>', methods=['GET'])
def unsubscribe_from_emails(emails_type: str, email: str):
    users.unsubscribe_from_emails(emails_type, email)
    return make_response(jsonify({'status': 'success'}), 200)


@bp.route('/cancel_unsubscribing_from_emails/<path:emails_type>/<path:email>', methods=['GET'])
def cancel_unsubscribing_from_emails(emails_type: str, email: str):
    users.cancel_unsubscribing_from_emails(emails_type, email)
    return make_response(jsonify({'status': 'success'}), 200)
