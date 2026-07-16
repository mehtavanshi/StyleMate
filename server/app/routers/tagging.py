import base64
import json
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv
from fastapi import APIRouter
from pydantic import BaseModel

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

router = APIRouter(tags=["tagging"])

AI_API_KEY = os.environ.get("OPENAI_API_KEY")
AI_MODEL = os.environ.get("AI_MODEL", "gpt-4o")
AI_API_URL = os.environ.get("AI_API_URL", "https://api.openai.com/v1/chat/completions")

FALLBACK_TAGS = {
    "category": "unclassified",
    "dominant_color": "unclassified",
    "pattern": "unclassified",
    "occasion_tag": "unclassified",
    "season": "unclassified",
}

SYSTEM_PROMPT = (
    "You are a fashion analyst. Analyze the clothing item in the image and respond "
    "with ONLY valid JSON (no markdown, no commentary) using this exact schema:\n"
    "{\n"
    '  "category": "top/bottom/dress/outerwear/footwear/accessory",\n'
    '  "dominant_color": "<color>",\n'
    '  "pattern": "solid/striped/printed/checked/other",\n'
    '  "occasion_tag": "casual/office/ethnic/party/formal/loungewear",\n'
    '  "season": "<season>"\n'
    "}"
)


class TagItemRequest(BaseModel):
    image_url: str


SERVER_DIR = Path(__file__).resolve().parents[2]

MIME_MAP = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
}


def _read_image(image_url: str) -> tuple[bytes, str]:
    if image_url.startswith("/"):
        path = SERVER_DIR / image_url.lstrip("/")
        ext = path.suffix.lower()
        content_type = MIME_MAP.get(ext, "image/jpeg")
        with open(path, "rb") as f:
            return f.read(), content_type
    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        resp = client.get(image_url)
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "image/jpeg")
        return resp.content, content_type


def _call_vision_api(image_url: str) -> str:
    if not AI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY environment variable is not set")

    image_data, content_type = _read_image(image_url)
    b64 = base64.b64encode(image_data).decode()
    data_url = f"data:{content_type.split(';')[0]};base64,{b64}"

    payload = {
        "model": AI_MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": SYSTEM_PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {"url": data_url},
                    },
                ],
            }
        ],
        "max_tokens": 300,
        "temperature": 0.1,
    }

    headers = {
        "Authorization": f"Bearer {AI_API_KEY}",
        "Content-Type": "application/json",
    }

    with httpx.Client(timeout=60.0) as client:
        resp = client.post(AI_API_URL, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]


def _parse_tags(raw: str) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    tags = json.loads(text)
    required = {"category", "dominant_color", "pattern", "occasion_tag", "season"}
    missing = required - tags.keys()
    if missing:
        raise ValueError(f"Missing required fields: {missing}")
    return tags


def _tag_item(image_url: str) -> dict:
    last_error = None
    for attempt in range(2):
        try:
            raw = _call_vision_api(image_url)
            return _parse_tags(raw)
        except (json.JSONDecodeError, ValueError, KeyError, httpx.HTTPError, RuntimeError) as exc:
            last_error = exc
            print(f"AI tagging attempt {attempt + 1} failed: {exc}", file=sys.stderr)
    return {**FALLBACK_TAGS, "_error": str(last_error)}


@router.post("/tag-item")
def tag_item(body: TagItemRequest):
    tags = _tag_item(body.image_url)
    return tags
