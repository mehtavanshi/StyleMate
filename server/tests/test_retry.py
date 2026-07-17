import time
from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.retry import call_with_retry


def _make_http_status(code, text="error"):
    resp = httpx.Response(code, text=text)
    return httpx.HTTPStatusError(f"{code}", request=MagicMock(), response=resp)


class TestCallWithRetry:
    def test_success_on_first_try(self):
        fn = MagicMock(return_value="ok")
        assert call_with_retry(fn, max_retries=3) == "ok"
        assert fn.call_count == 1

    @patch("app.retry.time.sleep")
    def test_retries_on_429_then_succeeds(self, mock_sleep):
        fn = MagicMock(side_effect=[
            _make_http_status(429, "rate limited"),
            _make_http_status(429, "rate limited"),
            "ok",
        ])
        assert call_with_retry(fn, max_retries=3) == "ok"
        assert fn.call_count == 3
        assert mock_sleep.call_count == 2
        mock_sleep.assert_any_call(2)
        mock_sleep.assert_any_call(4)

    @patch("app.retry.time.sleep")
    def test_retries_on_500_then_succeeds(self, mock_sleep):
        fn = MagicMock(side_effect=[
            _make_http_status(500, "server error"),
            "ok",
        ])
        assert call_with_retry(fn, max_retries=3) == "ok"
        assert fn.call_count == 2
        mock_sleep.assert_called_once_with(2)

    def test_fails_immediately_on_400(self):
        fn = MagicMock(side_effect=_make_http_status(400, "bad request"))
        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            call_with_retry(fn, max_retries=3)
        assert exc_info.value.response.status_code == 400
        assert fn.call_count == 1

    def test_fails_immediately_on_401(self):
        fn = MagicMock(side_effect=_make_http_status(401, "unauthorized"))
        with pytest.raises(httpx.HTTPStatusError):
            call_with_retry(fn, max_retries=3)
        assert fn.call_count == 1

    @patch("app.retry.time.sleep")
    def test_fails_after_max_retries_exhausted(self, mock_sleep):
        fn = MagicMock(side_effect=_make_http_status(429, "rate limited"))
        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            call_with_retry(fn, max_retries=2)
        assert exc_info.value.response.status_code == 429
        assert fn.call_count == 3
        assert mock_sleep.call_count == 2

    @patch("app.retry.time.sleep")
    def test_retries_on_network_error(self, mock_sleep):
        fn = MagicMock(side_effect=[
            httpx.ConnectError("connection refused"),
            "ok",
        ])
        assert call_with_retry(fn, max_retries=3) == "ok"
        assert fn.call_count == 2
        mock_sleep.assert_called_once_with(2)

    @patch("app.retry.time.sleep")
    def test_backoff_is_exponential(self, mock_sleep):
        fn = MagicMock(side_effect=[
            _make_http_status(429),
            _make_http_status(429),
            _make_http_status(429),
            "ok",
        ])
        call_with_retry(fn, max_retries=3)
        waits = [call.args[0] for call in mock_sleep.call_args_list]
        assert waits == [2, 4, 8]
