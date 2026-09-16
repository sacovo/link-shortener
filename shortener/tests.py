from django.contrib.auth.models import Group
from django.test import TestCase

from shortener.metadata import parse_metadata
from shortener.models import Domain, Link

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

    def test_slug_is_stored_lowercase(self):
        link = self.make_link(slug="MiXeD")

        self.assertEqual(link.slug, "mixed")
