from __future__ import annotations

import os
from urllib.parse import quote_plus


def build_google_shopping_link(query: str) -> str:
    encoded = quote_plus(query)
    return f"https://www.google.com/search?tbm=shop&q={encoded}"


def build_meesho_search_link(query: str) -> str:
    template = os.getenv(
        "MEESHO_SEARCH_URL_TEMPLATE",
        "https://www.meesho.com/search?q=",
    )
    return f"{template}{quote_plus(query)}"
