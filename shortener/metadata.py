"""Scrape open graph / twitter card metadata from a link target."""

import logging

import requests
from bs4 import BeautifulSoup
from django.conf import settings

logger = logging.getLogger(__name__)

# (meta property, Link field). Only fields that can hold a string live here;
# og_image / og_video are file fields and are filled from the *_url variants.
META_TAG_FIELDS = (
    ("og:title", "og_title"),
    ("og:type", "og_type"),
    ("og:description", "og_description"),
    ("og:image", "og_image_url"),
    ("og:image:width", "og_image_width"),
    ("og:image:height", "og_image_height"),
    ("og:video", "og_video_url"),
    ("og:video:width", "og_video_width"),
    ("og:video:height", "og_video_height"),
    ("og:url", "og_url"),
    ("twitter:card", "twitter_card"),
    ("twitter:site", "twitter_site"),
    ("twitter:creator", "twitter_creator"),
)

INTEGER_FIELDS = frozenset({"og_video_width", "og_video_height"})

# Longest CharField wins; anything longer is dropped rather than truncated so a
# bogus page can't silently corrupt a link.
MAX_FIELD_LENGTH = {
    "og_title": 500,
    "og_type": 40,
    "og_image_url": 800,
    "og_image_width": 30,
    "og_image_height": 30,
    "og_video_url": 800,
    "og_url": 300,
    "twitter_card": 20,
    "twitter_site": 30,
    "twitter_creator": 30,
    "title": 500,
}

TWITTER_CARD_VALUES = frozenset({"summary", "summary_large_image", "app", "player"})


def fetch_url_params(url, timeout=None):
    """Return a dict of Link field name -> value scraped from ``url``.

    Network and parse errors are swallowed: failing to read the preview tags of
    a target should never stop a short link from being created.
    """
    if timeout is None:
        timeout = getattr(settings, "LINK_METADATA_TIMEOUT", 10)

    try:
        response = requests.get(
            url,
            timeout=timeout,
            headers={"User-Agent": "link-shortener/1.0 (+metadata scraper)"},
        )
        response.raise_for_status()
    except requests.RequestException:
        logger.warning("Could not fetch metadata for %s", url, exc_info=True)
        return {}

    return parse_metadata(response.text)


def parse_metadata(html):
    """Extract the Link metadata fields from an HTML document."""
    soup = BeautifulSoup(html, "html.parser")
    head = soup.head or soup

    result = {}

    for prop, field in META_TAG_FIELDS:
        element = head.find("meta", attrs={"property": prop}) or head.find(
            "meta", attrs={"name": prop}
        )
        if element is None:
            continue

        value = _clean(field, element.get("content"))
        if value is not None:
            result[field] = value

    title = head.find("title")
    if title is not None:
        value = _clean("title", title.get_text(strip=True))
        if value is not None:
            result["title"] = value

    return result


def _clean(field, value):
    if value is None:
        return None

    value = value.strip()
    if not value:
        return None

    if field in INTEGER_FIELDS:
        try:
            return int(value)
        except ValueError:
            return None

    if field == "twitter_card" and value not in TWITTER_CARD_VALUES:
        return None

    max_length = MAX_FIELD_LENGTH.get(field)
    if max_length is not None and len(value) > max_length:
        return None

    return value
