import re
import secrets

from django.contrib.auth.models import Group
from django.db import models
from django.utils.translation import gettext_lazy as _

from shortener.share import (
    PLATFORM_CHOICES,
    build_desktop_share_url,
    build_share_url,
    needs_url,
)


class Domain(models.Model):
    domain_name = models.CharField(max_length=40, unique=True)
    groups = models.ManyToManyField(Group)

    class Meta:
        ordering = ("domain_name",)

    def __str__(self):
        return self.domain_name


MOBILE_USER_AGENT = re.compile(r"Mobi|Android|iPhone|iPad|iPod", re.IGNORECASE)


def is_desktop(request):
    # Chromium sends this client hint by default; Safari and Firefox don't.
    # iPadOS Safari claims to be a Mac, so iPads end up counted as desktops.
    hint = request.headers.get("Sec-CH-UA-Mobile")
    if hint is not None:
        return hint == "?0"
    return not MOBILE_USER_AGENT.search(request.headers.get("User-Agent", ""))


def get_slug():
    return secrets.token_urlsafe(16).lower()


SHORT_SLUG_ALPHABET = "abcdefghijklmnopqrstuvwxyz0123456789"


def get_free_slug(domain, prefix=""):
    """A short random slug that is unused on ``domain``, as ``<prefix>-<random>``."""
    for _attempt in range(10):
        suffix = "".join(secrets.choice(SHORT_SLUG_ALPHABET) for _i in range(6))
        slug = f"{prefix.lower()}-{suffix}" if prefix else suffix
        if not Link.objects.filter(domain=domain, slug=slug).exists():
            return slug
    raise RuntimeError(f"No free slug found on {domain} for prefix {prefix!r}")


class Link(models.Model):
    # Share URLs carry the whole percent-encoded message, hence the length.
    target = models.CharField(verbose_name=_("target"), max_length=4000)
    desktop_target = models.CharField(
        verbose_name=_("desktop target"),
        max_length=4000,
        blank=True,
        help_text=_(
            "Optional. Used instead of the target when the link is opened on a "
            "desktop computer."
        ),
    )

    domain = models.ForeignKey(Domain, models.CASCADE)
    slug = models.SlugField(default=get_slug)

    views = models.IntegerField(default=0)

    custom_tags = models.BooleanField(default=True)

    group = models.ForeignKey("auth.Group", models.CASCADE)

    title = models.CharField(max_length=500, blank=True)
    og_title = models.CharField(max_length=500, blank=True)
    og_type = models.CharField(max_length=40, blank=True)
    og_description = models.TextField(blank=True)

    og_image_url = models.CharField(max_length=800, blank=True)
    og_image = models.ImageField(blank=True, upload_to="images/")

    og_image_width = models.CharField(max_length=30, blank=True)
    og_image_height = models.CharField(max_length=30, blank=True)

    og_video_url = models.CharField(max_length=800, blank=True)
    og_video = models.FileField(upload_to="videos/", blank=True)

    og_video_width = models.IntegerField(default=1920, blank=True)
    og_video_height = models.IntegerField(default=1080, blank=True)

    og_url = models.CharField(max_length=300, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    twitter_card = models.CharField(
        max_length=20,
        blank=True,
        choices=(
            ("summary", "summary"),
            ("summary_large_image", "summary_large_image"),
            ("app", "app"),
            ("player", "player"),
        ),
    )

    twitter_site = models.CharField(max_length=30, blank=True)
    twitter_creator = models.CharField(max_length=30, blank=True)

    # Set for short links that are managed by a Share; their target is rebuilt
    # from the share's text whenever the share is saved.
    share = models.ForeignKey(
        "Share", models.CASCADE, null=True, blank=True, related_name="links"
    )
    share_platform = models.CharField(
        verbose_name=_("platform"),
        max_length=20,
        blank=True,
        choices=PLATFORM_CHOICES,
    )

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=["domain", "slug"], name="domain_slug_unique"
            ),
        ]

    def __str__(self):
        return self.slug

    def save(self, *args, **kwargs):
        self.slug = self.slug.lower()
        super().save(*args, **kwargs)

    def target_for(self, request):
        if self.desktop_target and is_desktop(request):
            return self.desktop_target
        return self.target

    def get_absolute_url(self):
        return f"https://{self.domain.domain_name}/{self.slug}/"


class Share(models.Model):
    """A message to share, with one short link per platform it is shared on."""

    text = models.TextField(verbose_name=_("text"))
    url = models.CharField(
        verbose_name=_("URL"),
        max_length=800,
        blank=True,
        help_text=_(
            "Optional link to share along with the text. "
            "Facebook and LinkedIn can only share a link."
        ),
    )

    domain = models.ForeignKey(Domain, models.CASCADE)
    group = models.ForeignKey("auth.Group", models.CASCADE)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        text = " ".join(self.text.split())
        return text if len(text) <= 60 else text[:57] + "…"

    def share_url(self, platform):
        return build_share_url(platform, self.text, self.url)

    def platform_error(self, platform):
        """Why no short link can be made for ``platform``, or None if it can."""
        if needs_url(platform) and not self.url:
            return _("This platform needs a URL to share.")

        max_length = Link._meta.get_field("target").max_length
        urls = [
            self.share_url(platform),
            build_desktop_share_url(platform, self.text, self.url),
        ]
        if any(url and len(url) > max_length for url in urls):
            return _("The text is too long for a share link on this platform.")

        return None

    def add_link(self, platform, slug):
        link = Link(share_platform=platform, slug=slug)
        self.apply_to(link)
        link.save()
        return link

    def apply_to(self, link):
        """Point ``link`` at this share's URL for its platform."""
        link.share = self
        link.domain = self.domain
        link.group = self.group
        link.target = self.share_url(link.share_platform) or ""
        link.desktop_target = (
            build_desktop_share_url(link.share_platform, self.text, self.url) or ""
        )
        # Share URLs are actions, not pages with a preview: redirect straight away.
        link.custom_tags = False

    def sync_links(self):
        for link in self.links.all():
            self.apply_to(link)
            link.save(
                update_fields=[
                    "domain",
                    "group",
                    "target",
                    "desktop_target",
                    "custom_tags",
                ]
            )
