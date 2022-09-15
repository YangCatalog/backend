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


@bp.route('/unsubscribe_from_draft_errors_emails/<path:draft_name>/<path:email>', methods=['GET'])
def unsubscribe_from_emails(draft_name: str, email: str):
    user_notifications.unsubscribe_from_draft_errors_emails(draft_name, email)
    return make_response(jsonify({'status': 'success'}), 200)
