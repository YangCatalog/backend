from flask import Blueprint, make_response, jsonify

from api.my_flask import app


class NotificationsBlueprint(Blueprint):
    pass


bp = NotificationsBlueprint('notifications', __name__)


@bp.before_request
def set_config():
    global app_config, user_notifications
    app_config = app.config
    user_notifications = app_config.redis_user_notifications


@bp.route('/unsubscribe_from_emails/<path:emails_type>/<path:email>', methods=['GET'])
def unsubscribe_from_emails(emails_type: str, email: str):
    user_notifications.unsubscribe_from_emails(emails_type, email)
    # TODO: return a jinja template instead of a pure json response
    return make_response(jsonify({'status': 'success'}), 200)
