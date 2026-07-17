import logging
import time

import httpx

logger = logging.getLogger(__name__)


def call_with_retry(fn, max_retries=3):
    last_exc = None
    for attempt in range(max_retries + 1):
        try:
            return fn()
        except httpx.HTTPStatusError as exc:
            last_exc = exc
            status = exc.response.status_code
            if status == 429 or status >= 500:
                if attempt < max_retries:
                    wait = 2 ** (attempt + 1)
                    logger.warning(
                        "API call failed with status %d (attempt %d/%d), retrying in %ds...",
                        status, attempt + 1, max_retries + 1, wait,
                    )
                    time.sleep(wait)
                else:
                    raise
            else:
                raise
        except Exception as exc:
            last_exc = exc
            if attempt < max_retries:
                wait = 2 ** (attempt + 1)
                logger.warning(
                    "API call failed (attempt %d/%d), retrying in %ds: %s",
                    attempt + 1, max_retries + 1, wait, exc,
                )
                time.sleep(wait)
            else:
                raise
    raise last_exc
