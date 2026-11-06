import os
import unittest
from decimal import Decimal
from unittest.mock import Mock, patch

import checkin as app
import random_delay


class CheckinTests(unittest.TestCase):
    def setUp(self):
        env = patch.dict(os.environ, {"GLADOS_COOKIES": "test-cookie"}, clear=True)
        env.start()
        self.addCleanup(env.stop)
        # Fail closed if a test accidentally tries to use the real network.
        network = patch("requests.sessions.Session.request", side_effect=AssertionError("network disabled"))
        network.start()
        self.addCleanup(network.stop)

    def test_linux_default_single_domain_and_all_requests(self):
        config = app.Config()
        self.assertEqual(config.DOMAINS, ["glados.cloud"])
        self.assertEqual(config.user_agent, app.PLATFORM_UA["Linux"])
        with app.API("glados.cloud", user_agent=config.user_agent) as api:
            response = Mock(ok=True)
            with patch.object(api.session, "get", return_value=response) as get, patch.object(api.session, "post", return_value=response) as post:
                api._make_request("https://glados.cloud/api/user/status", "GET", cookies="fake")
                api._make_request("https://glados.cloud/api/user/checkin", "POST", {}, "fake")
            self.assertEqual(get.call_args.kwargs["headers"]["user-agent"], config.user_agent)
            self.assertEqual(post.call_args.kwargs["headers"]["user-agent"], config.user_agent)
            self.assertNotIn("POST", api.session.get_adapter("https://").max_retries.allowed_methods)

    def test_custom_identity_and_domain(self):
        with patch.dict(os.environ, {"GLADOS_DOMAIN": "railgun.info", "GLADOS_USER_AGENT": "my Linux browser"}):
            config = app.Config()
        self.assertEqual(config.DOMAINS, ["railgun.info"])
        with app.API(config.DOMAINS[0], user_agent=config.user_agent) as api:
            self.assertEqual(api.headers["user-agent"], "my Linux browser")

    def test_invalid_domain_rejected(self):
        with patch.dict(os.environ, {"GLADOS_DOMAIN": "example.com"}), self.assertRaises(ValueError):
            app.Config()

    def test_device_mismatch_not_retried(self):
        with app.API("glados.cloud") as api:
            with patch.object(api, "_checkin_attempt", return_value={"code": 4, "reason": "device-mismatch", "loginDevice": "Windows"}) as attempt:
                result = api.checkin("fake")
            self.assertEqual(attempt.call_count, 1)
            self.assertEqual(result["code"], app.CheckinStatus.FAILURE)

    def test_decimal_points_and_failed_response(self):
        with app.API("glados.cloud") as api:
            response = Mock()
            response.json.return_value = {"code": 0, "points": "54.125"}
            with patch.object(api, "_make_request", return_value=response):
                self.assertEqual(api.get_points("fake")[1], Decimal("54.125"))
                response.json.return_value = {"code": -2, "points": 100}
                self.assertIsNone(api.get_points("fake")[1])

    def run_check(self, before, after, code=app.CheckinStatus.SUCCESS, status_code=0):
        config = app.Config()
        config.exchange_plan = "plan100"
        with patch.object(app, "API") as api_class:
            api = api_class.return_value.__enter__.return_value
            api.get_status.return_value = ("10 天", status_code)
            api.get_points.side_effect = [(str(before), before), (str(after), after)]
            api.checkin.return_value = {"status": "签到成功", "code": code, "points": "0.125", "message": "ok"}
            result = app.Checker(config)._checkin_on_domain("fake", 1, "glados.cloud")
        return result, api

    def test_award_preserved_and_balance_verified(self):
        result, api = self.run_check(Decimal("54"), Decimal("54.125"))
        self.assertEqual(result.code, app.CheckinStatus.SUCCESS)
        self.assertEqual(result.points, "0.125")
        self.assertEqual(result.points_delta, "0.125")
        api.exchange.assert_not_called()

    def test_confirmed_success_can_exchange_when_balance_sufficient(self):
        result, api = self.run_check(Decimal("100"), Decimal("101"))
        self.assertEqual(result.code, app.CheckinStatus.SUCCESS)
        api.exchange.assert_called_once_with("fake", "plan100", 100)

    def test_missing_award_field_remains_unknown(self):
        with app.API("glados.cloud") as api:
            self.assertEqual(api._parse_checkin({"code": 0})["points"], "未知")

    def test_malformed_checkin_response_is_failure(self):
        with app.API("glados.cloud") as api:
            response = Mock()
            response.json.return_value = []
            with patch.object(api, "_make_request", return_value=response):
                self.assertEqual(api.checkin("fake")["code"], app.CheckinStatus.FAILURE)

    def test_no_growth_or_unknown_balance_not_success(self):
        for before, after in [(Decimal("54"), Decimal("54")), (None, Decimal("55")), (Decimal("54"), None)]:
            with self.subTest(before=before, after=after):
                result, api = self.run_check(before, after)
                self.assertEqual(result.code, app.CheckinStatus.FAILURE)
                api.exchange.assert_not_called()

    def test_invalid_session_stops_checkin(self):
        result, api = self.run_check(None, None, status_code=-2)
        self.assertEqual(result.code, app.CheckinStatus.FAILURE)
        api.checkin.assert_not_called()
        api.exchange.assert_not_called()

    def test_repeated_checkin_with_unchanged_balance_is_valid(self):
        result, _ = self.run_check(Decimal("54"), Decimal("54"), app.CheckinStatus.REPEAT)
        self.assertEqual(result.code, app.CheckinStatus.REPEAT)

    def test_failed_checkin_never_exchanges_even_with_balance(self):
        result, api = self.run_check(Decimal("500"), Decimal("500"), app.CheckinStatus.FAILURE)
        api.exchange.assert_not_called()

    def test_main_exit_status(self):
        for code, expected in [(app.CheckinStatus.SUCCESS, 0), (app.CheckinStatus.REPEAT, 0), (app.CheckinStatus.FAILURE, 1)]:
            with self.subTest(code=code), patch.object(app, "Checker") as checker, patch.object(app.PushService, "send"):
                checker.return_value.results = [app.CheckinResult(1, "glados.cloud", code=code)]
                checker.return_value.format_results.return_value = ("title", "body", "log")
                self.assertEqual(app.main(), expected)
        with patch.dict(os.environ, {"GLADOS_COOKIES": ""}):
            self.assertEqual(app.main(), 1)
        with patch.dict(os.environ, {"GLADOS_DOMAIN": "invalid"}):
            self.assertEqual(app.main(), 1)

    def test_delay_defaults_bounds_and_zero(self):
        for raw, maximum in [("", 1800), ("0", 0), ("60", 60)]:
            with patch.dict(os.environ, {"GLADOS_MAX_DELAY_SECONDS": raw}), patch.object(random_delay.random, "randint", return_value=0) as randint, patch.object(random_delay.time, "sleep") as sleep:
                random_delay.main()
                randint.assert_called_once_with(0, maximum)
                sleep.assert_called_once_with(0)
        for raw in ["-1", "1801", "bad"]:
            with patch.dict(os.environ, {"GLADOS_MAX_DELAY_SECONDS": raw}), self.assertRaises(ValueError):
                random_delay.main()


if __name__ == "__main__":
    unittest.main()
