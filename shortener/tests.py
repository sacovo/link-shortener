from django.contrib.auth.models import Group, User
from django.test import TestCase

from shortener.metadata import parse_metadata
from shortener.models import Domain, Link, Share
from shortener.share import build_desktop_share_url, build_share_url

HTML = """
<html><head>
  <title>  A page  </title>
  <meta property="og:title" content="OG title">
  <meta property="og:description" content="OG description">
  <meta property="og:image" content="https://example.com/i.png">
  <meta property="og:video:width" content="640">
  <meta property="twitter:card" content="summary_large_image">
  <meta name="twitter:site" content="@example">
</head><body></body></html>
"""


DESKTOP_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)
IPHONE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/18.5 Mobile/15E148 Safari/604.1"
)


class MetadataTests(TestCase):
    def test_parses_open_graph_and_twitter_tags(self):
        result = parse_metadata(HTML)

        self.assertEqual(result["title"], "A page")
        self.assertEqual(result["og_title"], "OG title")
        self.assertEqual(result["og_description"], "OG description")
        # og:image is a URL, so it belongs on the *_url field, not the ImageField.
        self.assertEqual(result["og_image_url"], "https://example.com/i.png")
        self.assertEqual(result["og_video_width"], 640)
        self.assertEqual(result["twitter_card"], "summary_large_image")
        self.assertEqual(result["twitter_site"], "@example")
        self.assertNotIn("og_image", result)

    def test_drops_values_that_do_not_fit_the_model(self):
        html = (
            '<html><head><meta property="twitter:card" content="nonsense">'
            '<meta property="og:type" content="{}"></head></html>'.format("x" * 100)
        )
        result = parse_metadata(html)

        self.assertNotIn("twitter_card", result)
        self.assertNotIn("og_type", result)

    def test_missing_head_is_not_an_error(self):
        self.assertEqual(parse_metadata(""), {})


class RedirectTests(TestCase):
    def setUp(self):
        self.group = Group.objects.create(name="team")
        self.domain = Domain.objects.create(domain_name="short.test")
        self.domain.groups.add(self.group)

    def make_link(self, **kwargs):
        kwargs.setdefault("target", "https://example.com/")
        return Link.objects.create(domain=self.domain, group=self.group, **kwargs)

    def test_renders_preview_page_when_custom_tags_are_on(self):
        link = self.make_link(slug="abc", custom_tags=True, og_title="Hi")

        response = self.client.get("/abc/", headers={"host": "short.test"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Hi")

    def test_redirects_when_custom_tags_are_off(self):
        self.make_link(slug="abc", custom_tags=False)

        response = self.client.get("/abc/", headers={"host": "short.test"})

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "https://example.com/")

    def test_allows_non_http_schemes(self):
        self.make_link(slug="abc", custom_tags=False, target="mailto:a@example.com")

        response = self.client.get("/abc/", headers={"host": "short.test"})

        self.assertEqual(response["Location"], "mailto:a@example.com")

    def test_slug_is_matched_case_insensitively(self):
        self.make_link(slug="abc", custom_tags=False)

        response = self.client.get("/ABC/", headers={"host": "short.test"})

        self.assertEqual(response.status_code, 302)

    def test_link_is_scoped_to_its_domain(self):
        self.make_link(slug="abc")
        Domain.objects.create(domain_name="other.test")

        response = self.client.get("/abc/", headers={"host": "other.test"})

        self.assertEqual(response.status_code, 404)

    def test_view_counter_increments(self):
        link = self.make_link(slug="abc", custom_tags=False)

        self.client.get("/abc/", headers={"host": "short.test"})
        self.client.get("/abc/", headers={"host": "short.test"})

        link.refresh_from_db()
        self.assertEqual(link.views, 2)

    def test_count_endpoint_reports_views(self):
        self.make_link(slug="abc", custom_tags=False, views=7)

        response = self.client.get("/abc/count/", headers={"host": "short.test"})

        self.assertEqual(response.json(), {"count": 7})

    def test_desktop_target_for_desktop_user_agent(self):
        self.make_link(
            slug="abc", custom_tags=False, desktop_target="https://desktop.example/"
        )

        response = self.client.get(
            "/abc/", headers={"host": "short.test", "user-agent": DESKTOP_UA}
        )

        self.assertEqual(response["Location"], "https://desktop.example/")
        self.assertIn("User-Agent", response["Vary"])
        self.assertIn("Sec-CH-UA-Mobile", response["Vary"])

    def test_target_for_mobile_user_agent(self):
        self.make_link(
            slug="abc", custom_tags=False, desktop_target="https://desktop.example/"
        )

        response = self.client.get(
            "/abc/", headers={"host": "short.test", "user-agent": IPHONE_UA}
        )

        self.assertEqual(response["Location"], "https://example.com/")

    def test_client_hint_wins_over_user_agent(self):
        self.make_link(
            slug="abc", custom_tags=False, desktop_target="https://desktop.example/"
        )

        response = self.client.get(
            "/abc/",
            headers={
                "host": "short.test",
                "user-agent": DESKTOP_UA,
                "sec-ch-ua-mobile": "?1",
            },
        )

        self.assertEqual(response["Location"], "https://example.com/")

    def test_preview_page_redirects_to_desktop_target(self):
        self.make_link(slug="abc", desktop_target="https://desktop.example/")

        response = self.client.get(
            "/abc/", headers={"host": "short.test", "user-agent": DESKTOP_UA}
        )

        self.assertContains(response, 'window.location = "https://desktop.example/"')

    def test_no_vary_without_desktop_target(self):
        self.make_link(slug="abc", custom_tags=False)

        response = self.client.get("/abc/", headers={"host": "short.test"})

        self.assertNotIn("Sec-CH-UA-Mobile", response.get("Vary", ""))

    def test_slug_is_stored_lowercase(self):
        link = self.make_link(slug="MiXeD")

        self.assertEqual(link.slug, "mixed")


class ShareUrlTests(TestCase):
    def test_whatsapp_puts_text_and_url_into_one_message(self):
        self.assertEqual(
            build_share_url("whatsapp", "Hallo Welt & Co", "https://example.com/?a=1"),
            "https://wa.me/?text=Hallo%20Welt%20%26%20Co%0Ahttps%3A%2F%2Fexample.com%2F%3Fa%3D1",
        )

    def test_encodes_non_ascii(self):
        self.assertEqual(
            build_share_url("whatsapp", "Grüezi 👋"),
            "https://wa.me/?text=Gr%C3%BCezi%20%F0%9F%91%8B",
        )

    def test_x_keeps_text_and_url_apart(self):
        self.assertEqual(
            build_share_url("x", "Hi", "https://example.com/"),
            "https://x.com/intent/tweet?text=Hi&url=https%3A%2F%2Fexample.com%2F",
        )

    def test_telegram_without_url_shares_the_text(self):
        self.assertEqual(
            build_share_url("telegram", "Hi there"),
            "https://t.me/share/url?url=Hi%20there",
        )

    def test_email_and_sms_encode_spaces_as_percent_20(self):
        self.assertEqual(build_share_url("email", "a b"), "mailto:?body=a%20b")
        self.assertEqual(build_share_url("sms", "a b"), "sms:?body=a%20b")

    def test_url_only_platforms_need_a_url(self):
        self.assertIsNone(build_share_url("facebook", "Hi"))
        self.assertEqual(
            build_share_url("facebook", "Hi", "https://example.com/"),
            "https://www.facebook.com/sharer/sharer.php?u=https%3A%2F%2Fexample.com%2F",
        )

    def test_whatsapp_has_a_desktop_url(self):
        self.assertEqual(
            build_desktop_share_url("whatsapp", "Hi you"),
            "https://web.whatsapp.com/send?text=Hi%20you",
        )
        self.assertIsNone(build_desktop_share_url("telegram", "Hi you"))
        self.assertIsNone(build_desktop_share_url("whatsapp", ""))

    def test_nothing_to_share(self):
        self.assertIsNone(build_share_url("whatsapp", ""))


class ShareAdminTests(TestCase):
    def setUp(self):
        self.group = Group.objects.create(name="team")
        self.domain = Domain.objects.create(domain_name="short.test")
        self.domain.groups.add(self.group)
        self.user = User.objects.create_user("editor", is_staff=True)
        self.user.groups.add(self.group)
        self.client.force_login(self.user)

    def post_share(self, url, links, existing=(), **data):
        """POST the share change form with ``links`` as [(platform, slug)]."""
        rows = [*existing, *[(None, platform, slug) for platform, slug in links]]
        data = {
            "text": "Hello",
            "url": "",
            "domain": self.domain.pk,
            "group": self.group.pk,
            "links-TOTAL_FORMS": len(rows),
            "links-INITIAL_FORMS": len(existing),
            **data,
        }
        for i, (pk, platform, slug) in enumerate(rows):
            data[f"links-{i}-id"] = pk or ""
            data[f"links-{i}-share_platform"] = platform
            data[f"links-{i}-slug"] = slug
        return self.client.post(url, data)

    def test_creates_a_short_link_per_platform(self):
        response = self.post_share(
            "/admin/shortener/share/add/",
            [("whatsapp", "Share-WA"), ("sms", "share-sms")],
        )
        self.assertEqual(response.status_code, 302)

        share = Share.objects.get()
        wa = share.links.get(share_platform="whatsapp")
        self.assertEqual(wa.slug, "share-wa")
        self.assertEqual(wa.target, "https://wa.me/?text=Hello")
        self.assertEqual(wa.desktop_target, "https://web.whatsapp.com/send?text=Hello")
        self.assertEqual(wa.domain, self.domain)
        self.assertEqual(wa.group, self.group)
        self.assertFalse(wa.custom_tags)

        response = self.client.get("/share-sms/", headers={"host": "short.test"})
        self.assertEqual(response["Location"], "sms:?body=Hello")
        self.assertEqual(share.links.get(share_platform="sms").desktop_target, "")

    def test_editing_the_text_updates_every_link(self):
        share = Share.objects.create(text="Old", domain=self.domain, group=self.group)
        link = Link(share_platform="whatsapp", slug="wa")
        share.apply_to(link)
        link.save()

        response = self.post_share(
            f"/admin/shortener/share/{share.pk}/change/",
            [],
            existing=[(link.pk, "whatsapp", "wa")],
            text="New text",
        )
        self.assertEqual(response.status_code, 302)

        link.refresh_from_db()
        self.assertEqual(link.target, "https://wa.me/?text=New%20text")
        self.assertEqual(
            link.desktop_target, "https://web.whatsapp.com/send?text=New%20text"
        )

    def test_rejects_a_slug_that_is_taken_on_the_domain(self):
        Link.objects.create(
            target="https://example.com/",
            slug="taken",
            domain=self.domain,
            group=self.group,
        )

        response = self.post_share(
            "/admin/shortener/share/add/", [("whatsapp", "taken")]
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "already used on short.test")
        self.assertFalse(Share.objects.exists())

    def test_rejects_the_same_slug_twice(self):
        response = self.post_share(
            "/admin/shortener/share/add/", [("whatsapp", "dup"), ("sms", "DUP")]
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Share.objects.exists())

    def test_rejects_url_only_platform_without_url(self):
        response = self.post_share("/admin/shortener/share/add/", [("facebook", "fb")])

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "needs a URL")

    def test_preview_renders_links_without_saving(self):
        response = self.client.post(
            "/admin/shortener/share/preview/", {"text": "Hi you", "url": ""}
        )

        self.assertContains(response, "https://wa.me/?text=Hi%20you")
        self.assertContains(response, "https://web.whatsapp.com/send?text=Hi%20you")
        self.assertFalse(Share.objects.exists())
        self.assertFalse(Link.objects.exists())
