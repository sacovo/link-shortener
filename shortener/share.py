"""Build "share this" URLs (wa.me/?text=… and friends) for a text and a URL.

This is the only place that knows the URL formats: the admin preview and the
short links stored for a Share both go through ``build_share_url``.
"""

from urllib.parse import quote, urlencode

from django.utils.translation import gettext_lazy as _


def _query(params):
    # %20 instead of +: mailto: and sms: don't decode + as a space.
    return urlencode(params, quote_via=quote)


def _message(text, url):
    """Text and URL as a single message, for platforms with only one field."""
    return "\n".join(part for part in (text, url) if part)


def _whatsapp(text, url):
    return "https://wa.me/?" + _query({"text": _message(text, url)})


def _whatsapp_desktop(text, url):
    # wa.me shows a "Continue to chat" page on desktop before opening WhatsApp Web.
    return "https://web.whatsapp.com/send?" + _query({"text": _message(text, url)})


def _telegram(text, url):
    # Telegram insists on a url parameter; without one the text goes there.
    if not url:
        return "https://t.me/share/url?" + _query({"url": text})
    return "https://t.me/share/url?" + _query({"url": url, "text": text})


def _x(text, url):
    params = {"text": text}
    if url:
        params["url"] = url
    return "https://x.com/intent/tweet?" + _query(params)


def _bluesky(text, url):
    return "https://bsky.app/intent/compose?" + _query({"text": _message(text, url)})


def _threads(text, url):
    return "https://www.threads.com/intent/post?" + _query(
        {"text": _message(text, url)}
    )


def _facebook(text, url):
    return "https://www.facebook.com/sharer/sharer.php?" + _query({"u": url})


def _linkedin(text, url):
    return "https://www.linkedin.com/sharing/share-offsite/?" + _query({"url": url})


def _email(text, url):
    return "mailto:?" + _query({"body": _message(text, url)})


def _sms(text, url):
    return "sms:?" + _query({"body": _message(text, url)})


# key: (label, builder, needs a URL)
PLATFORMS = {
    "whatsapp": (_("WhatsApp"), _whatsapp, False),
    "telegram": (_("Telegram"), _telegram, False),
    "x": (_("X / Twitter"), _x, False),
    "bluesky": (_("Bluesky"), _bluesky, False),
    "threads": (_("Threads"), _threads, False),
    "facebook": (_("Facebook"), _facebook, True),
    "linkedin": (_("LinkedIn"), _linkedin, True),
    "email": (_("E-mail"), _email, False),
    "sms": (_("SMS"), _sms, False),
}

# Platforms with a better URL for desktop browsers than their default one.
DESKTOP_BUILDERS = {
    "whatsapp": _whatsapp_desktop,
}

PLATFORM_CHOICES = [(key, label) for key, (label, _b, _u) in PLATFORMS.items()]


def needs_url(platform):
    return PLATFORMS[platform][2]


def build_share_url(platform, text, url=""):
    """Share URL for ``platform``, or None if it can't be built from the input."""
    _label, builder, requires_url = PLATFORMS[platform]
    if requires_url and not url:
        return None
    if not text and not url:
        return None
    return builder(text, url)


def build_desktop_share_url(platform, text, url=""):
    """Desktop variant of ``build_share_url``, or None if the platform has none."""
    builder = DESKTOP_BUILDERS.get(platform)
    if builder is None or build_share_url(platform, text, url) is None:
        return None
    return builder(text, url)


def build_share_urls(text, url=""):
    """[(platform, label, share URL or None, desktop URL or None)] for every platform."""
    return [
        (
            key,
            label,
            build_share_url(key, text, url),
            build_desktop_share_url(key, text, url),
        )
        for key, (label, _b, _u) in PLATFORMS.items()
    ]
