import unittest

from redisConnections.redis_user_notifications_connection import RedisUserNotificationsConnection
from utility.create_config import create_config


class TestUserNotificationsClass(unittest.TestCase):
    def setUp(self):
        super().setUp()
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
