import unittest
from unittest import mock

from api.yangCatalogApi import app
from redisConnections.redis_user_notifications_connection import RedisUserNotificationsConnection
from utility.create_config import create_config


class TestUserNotificationsClass(unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.client = app.test_client()
        config = create_config()
        self.redis_user_notifications_connection = RedisUserNotificationsConnection(db=12, config=config)
        self.redis_user_notifications_db = self.redis_user_notifications_connection.redis

    def tearDown(self):
        super().tearDown()
        self.redis_user_notifications_db.flushdb()

    def test_unsubscription_from_draft_notifications(self):
        draft_name_without_revision = 'test-draft-name'
        email = 'test@example.com'
        self.redis_user_notifications_connection.unsubscribe_from_draft_errors_emails(
            draft_name_without_revision, email
        )
        self.assertListEqual(
            self.redis_user_notifications_connection.get_emails_unsubscribed_from_draft_errors_emails(
                draft_name_without_revision
            ),
            [email]
        )

    def test_unsubscription_from_draft_notifications_via_api(self):
        draft_name_without_revision = 'test-draft-name'
        email = 'test@example.com'
        mock.patch('api.views.notifications.notifications.user_notifications', self.redis_user_notifications_connection)
        self.redis_user_notifications_connection.unsubscribe_from_draft_errors_emails(
            draft_name_without_revision, email
        )
        response = self.client.get(
            f'api/notifications/unsubscribe_from_draft_errors_emails/{draft_name_without_revision}/{email}'
        )
        self.assertEqual(response.status_code, 200)
        self.assertListEqual(
            self.redis_user_notifications_connection.get_emails_unsubscribed_from_draft_errors_emails(
                draft_name_without_revision
            ),
            [email]
        )
