import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace

from services.subscription_access import can_predict_pointcloud


class SubscriptionAccessTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 6, 7, 12, 0, 0)

    def user(self, **overrides):
        values = {
            "is_subscribed": False,
            "vip_expire_time": None,
            "register_time": self.now - timedelta(days=30),
        }
        values.update(overrides)
        return SimpleNamespace(**values)

    def test_active_subscription_allows_prediction_after_trial(self):
        user = self.user(
            is_subscribed=True,
            vip_expire_time=self.now + timedelta(days=1),
        )

        self.assertTrue(can_predict_pointcloud(user, self.now))

    def test_expired_subscription_does_not_bypass_trial_limit(self):
        user = self.user(
            is_subscribed=True,
            vip_expire_time=self.now - timedelta(seconds=1),
        )

        self.assertFalse(can_predict_pointcloud(user, self.now))

    def test_recent_registration_still_allows_trial_access(self):
        user = self.user(register_time=self.now - timedelta(days=14))

        self.assertTrue(can_predict_pointcloud(user, self.now))

    def test_trial_expires_after_fourteen_days(self):
        user = self.user(register_time=self.now - timedelta(days=15))

        self.assertFalse(can_predict_pointcloud(user, self.now))


if __name__ == "__main__":
    unittest.main()
