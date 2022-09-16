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

    def test_unsubscription_from_emails(self):
        email_type = 'test-email-type'
        email = 'test@example.com'
        self.redis_user_notifications_connection.unsubscribe_from_emails(email_type, email)
        self.assertListEqual(self.redis_user_notifications_connection.get_unsubscribed_emails(email_type), [email])

    def test_unsubscription_from_emails_via_api(self):
        email_type = 'test-email-type'
        email = 'test@example.com'
        mock.patch('api.views.notifications.notifications.user_notifications', self.redis_user_notifications_connection)
        self.redis_user_notifications_connection.unsubscribe_from_emails(email_type, email)
        response = self.client.get(f'api/notifications/unsubscribe_from_emails/{email_type}/{email}')
        self.assertEqual(response.status_code, 200)
        self.assertListEqual(self.redis_user_notifications_connection.get_unsubscribed_emails(email_type), [email])
