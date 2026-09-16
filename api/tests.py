from unittest import mock

from django.contrib.auth.models import Group, User
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from api.models import UserAPIKey
from shortener.models import Domain, Link


class APITestBase(APITestCase):
    def setUp(self):
        self.group = Group.objects.create(name="team")
        self.other_group = Group.objects.create(name="other-team")

        self.domain = Domain.objects.create(domain_name="short.test")
        self.domain.groups.add(self.group)

        self.other_domain = Domain.objects.create(domain_name="other.test")
        self.other_domain.groups.add(self.other_group)

        self.user = User.objects.create_user("automation", password="x")
        self.user.groups.add(self.group)

        _, self.key = UserAPIKey.objects.create_key(name="ci", user=self.user)

    def authenticate(self, key=None):
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Api-Key {key or self.key}",
        )

    def make_link(self, **kwargs):
        kwargs.setdefault("target", "https://example.com/")
        kwargs.setdefault("domain", self.domain)
        kwargs.setdefault("group", self.group)
        return Link.objects.create(**kwargs)


class AuthenticationTests(APITestBase):
    def test_rejects_anonymous_requests(self):
        response = self.client.get("/api/v1/links/")

        self.assertEqual(response.status_code, 401)

    def test_rejects_an_unknown_key(self):
        self.authenticate("nope.nothing")

        self.assertEqual(self.client.get("/api/v1/links/").status_code, 401)

    def test_rejects_a_revoked_key(self):
        api_key, key = UserAPIKey.objects.create_key(name="old", user=self.user)
        api_key.revoked = True
        api_key.save()
        self.authenticate(key)

        self.assertEqual(self.client.get("/api/v1/links/").status_code, 401)

    def test_rejects_an_expired_key(self):
        api_key, key = UserAPIKey.objects.create_key(
            name="stale",
            user=self.user,
            expiry_date=timezone.now() - timezone.timedelta(days=1),
        )
        self.authenticate(key)

        self.assertEqual(self.client.get("/api/v1/links/").status_code, 401)

    def test_rejects_a_key_of_a_deactivated_user(self):
        self.user.is_active = False
        self.user.save()
        self.authenticate()

        self.assertEqual(self.client.get("/api/v1/links/").status_code, 401)

    def test_accepts_a_valid_key(self):
        self.authenticate()

        self.assertEqual(self.client.get("/api/v1/links/").status_code, 200)

    def test_whoami_reports_the_keys_reach(self):
        self.authenticate()

        response = self.client.get("/api/v1/whoami/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "username": "automation",
                "is_superuser": False,
                "groups": ["team"],
                "domains": ["short.test"],
            },
        )


class LinkListTests(APITestBase):
    def setUp(self):
        super().setUp()
        self.authenticate()

    def test_only_lists_links_of_the_users_groups(self):
        mine = self.make_link(slug="mine")
        self.make_link(slug="theirs", domain=self.other_domain, group=self.other_group)

        response = self.client.get("/api/v1/links/")

        self.assertEqual(response.json()["count"], 1)
        self.assertEqual(response.json()["results"][0]["id"], mine.pk)

    def test_cannot_retrieve_a_link_of_another_group(self):
        theirs = self.make_link(
            slug="theirs", domain=self.other_domain, group=self.other_group
        )

        response = self.client.get(f"/api/v1/links/{theirs.pk}/")

        self.assertEqual(response.status_code, 404)

    def test_filters_by_domain_and_slug(self):
        self.make_link(slug="alpha")
        self.make_link(slug="beta")

        response = self.client.get("/api/v1/links/?domain=short.test&slug=ALPHA")

        self.assertEqual(response.json()["count"], 1)
        self.assertEqual(response.json()["results"][0]["slug"], "alpha")

    def test_exposes_the_short_url(self):
        self.make_link(slug="alpha")

        response = self.client.get("/api/v1/links/")

        self.assertEqual(
            response.json()["results"][0]["short_url"],
            "https://short.test/alpha/",
        )

    def test_lists_only_reachable_domains_and_groups(self):
        self.assertEqual(
            [
                d["domain_name"]
                for d in self.client.get("/api/v1/domains/").json()["results"]
            ],
            ["short.test"],
        )
        self.assertEqual(
            [g["name"] for g in self.client.get("/api/v1/groups/").json()["results"]],
            ["team"],
        )


@mock.patch("api.serializers.fetch_url_params", return_value={})
class LinkCreateTests(APITestBase):
    def setUp(self):
        super().setUp()
        self.authenticate()

    def test_creates_a_link_with_a_generated_slug(self, fetch):
        response = self.client.post(
            "/api/v1/links/",
            {
                "target": "https://example.com/a",
                "domain": "short.test",
                "group": "team",
            },
        )

        self.assertEqual(response.status_code, 201, response.data)
        self.assertTrue(response.json()["slug"])
        self.assertEqual(Link.objects.count(), 1)

    def test_creates_a_link_with_an_explicit_slug(self, fetch):
        response = self.client.post(
            "/api/v1/links/",
            {
                "target": "https://example.com/a",
                "domain": "short.test",
                "group": "team",
                "slug": "MyLink",
            },
        )

        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.json()["slug"], "mylink")

    def test_rejects_a_duplicate_slug_on_the_same_domain(self, fetch):
        self.make_link(slug="taken")

        response = self.client.post(
            "/api/v1/links/",
            {
                "target": "https://example.com/a",
                "domain": "short.test",
                "group": "team",
                "slug": "taken",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("slug", response.json())

    def test_allows_the_same_slug_on_a_different_domain(self, fetch):
        self.make_link(slug="taken")
        self.domain2 = Domain.objects.create(domain_name="second.test")
        self.domain2.groups.add(self.group)

        response = self.client.post(
            "/api/v1/links/",
            {
                "target": "https://example.com/a",
                "domain": "second.test",
                "group": "team",
                "slug": "taken",
            },
        )

        self.assertEqual(response.status_code, 201, response.data)

    def test_rejects_a_domain_the_user_cannot_reach(self, fetch):
        response = self.client.post(
            "/api/v1/links/",
            {
                "target": "https://example.com/a",
                "domain": "other.test",
                "group": "team",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("domain", response.json())

    def test_rejects_a_group_the_user_is_not_in(self, fetch):
        response = self.client.post(
            "/api/v1/links/",
            {
                "target": "https://example.com/a",
                "domain": "short.test",
                "group": "other-team",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("group", response.json())

    def test_scrapes_metadata_by_default(self, fetch):
        fetch.return_value = {"og_title": "Scraped", "title": "Scraped page"}

        response = self.client.post(
            "/api/v1/links/",
            {
                "target": "https://example.com/a",
                "domain": "short.test",
                "group": "team",
            },
        )

        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.json()["og_title"], "Scraped")

    def test_does_not_overwrite_metadata_the_caller_supplied(self, fetch):
        fetch.return_value = {"og_title": "Scraped"}

        response = self.client.post(
            "/api/v1/links/",
            {
                "target": "https://example.com/a",
                "domain": "short.test",
                "group": "team",
                "og_title": "Mine",
            },
        )

        self.assertEqual(response.json()["og_title"], "Mine")

    def test_scraping_can_be_switched_off(self, fetch):
        self.client.post(
            "/api/v1/links/",
            {
                "target": "https://example.com/a",
                "domain": "short.test",
                "group": "team",
                "fetch_metadata": False,
            },
        )

        fetch.assert_not_called()

    def test_custom_tags_stay_on_when_omitted_from_a_form_post(self, fetch):
        # DRF reads an absent boolean in form data as False unless the field
        # carries an explicit default.
        response = self.client.post(
            "/api/v1/links/",
            {
                "target": "https://example.com/a",
                "domain": "short.test",
                "group": "team",
            },
        )

        self.assertIs(response.json()["custom_tags"], True)

    def test_accepts_json_bodies(self, fetch):
        response = self.client.post(
            "/api/v1/links/",
            {
                "target": "https://example.com/a",
                "domain": "short.test",
                "group": "team",
                "slug": "json-link",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.data)
        self.assertIs(response.json()["custom_tags"], True)

    def test_does_not_scrape_when_custom_tags_are_off(self, fetch):
        self.client.post(
            "/api/v1/links/",
            {
                "target": "https://example.com/a",
                "domain": "short.test",
                "group": "team",
                "custom_tags": False,
            },
        )

        fetch.assert_not_called()


class LinkWriteTests(APITestBase):
    def setUp(self):
        super().setUp()
        self.authenticate()
        self.link = self.make_link(slug="alpha")

    def test_updates_a_link(self):
        response = self.client.patch(
            f"/api/v1/links/{self.link.pk}/", {"target": "https://example.org/"}
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.link.refresh_from_db()
        self.assertEqual(self.link.target, "https://example.org/")

    def test_views_are_read_only(self):
        self.client.patch(f"/api/v1/links/{self.link.pk}/", {"views": 999})

        self.link.refresh_from_db()
        self.assertEqual(self.link.views, 0)

    def test_deletes_a_link(self):
        response = self.client.delete(f"/api/v1/links/{self.link.pk}/")

        self.assertEqual(response.status_code, 204)
        self.assertFalse(Link.objects.filter(pk=self.link.pk).exists())

    def test_cannot_delete_a_link_of_another_group(self):
        theirs = self.make_link(
            slug="theirs", domain=self.other_domain, group=self.other_group
        )

        response = self.client.delete(f"/api/v1/links/{theirs.pk}/")

        self.assertEqual(response.status_code, 404)
        self.assertTrue(Link.objects.filter(pk=theirs.pk).exists())

    @mock.patch("api.views.fetch_url_params")
    def test_refresh_metadata_rescrapes_the_target(self, fetch):
        fetch.return_value = {"og_title": "Fresh"}

        response = self.client.post(f"/api/v1/links/{self.link.pk}/refresh-metadata/")

        self.assertEqual(response.status_code, 200, response.data)
        self.link.refresh_from_db()
        self.assertEqual(self.link.og_title, "Fresh")

    @mock.patch("api.views.fetch_url_params", return_value={})
    def test_refresh_metadata_reports_a_target_that_says_nothing(self, fetch):
        response = self.client.post(f"/api/v1/links/{self.link.pk}/refresh-metadata/")

        self.assertEqual(response.status_code, 502)


class SuperuserTests(APITestBase):
    def setUp(self):
        super().setUp()
        self.admin = User.objects.create_superuser("root", password="x")
        _, key = UserAPIKey.objects.create_key(name="root-key", user=self.admin)
        self.authenticate(key)

    def test_sees_every_link(self):
        self.make_link(slug="mine")
        self.make_link(slug="theirs", domain=self.other_domain, group=self.other_group)

        self.assertEqual(self.client.get("/api/v1/links/").json()["count"], 2)


class SchemaTests(APITestBase):
    def test_schema_is_served(self):
        response = self.client.get(reverse("api-schema"))

        self.assertEqual(response.status_code, 200)

    def test_docs_are_served(self):
        response = self.client.get(reverse("api-docs"))

        self.assertEqual(response.status_code, 200)


class SlugRaceTests(APITestBase):
    """The serializer check can be raced; the DB constraint is the backstop."""

    def setUp(self):
        super().setUp()
        self.authenticate()

    @mock.patch("api.serializers.fetch_url_params", return_value={})
    @mock.patch(
        "api.serializers.LinkSerializer.validate", side_effect=lambda attrs: attrs
    )
    def test_a_constraint_violation_becomes_a_validation_error(self, validate, fetch):
        self.make_link(slug="taken")

        response = self.client.post(
            "/api/v1/links/",
            {
                "target": "https://example.com/a",
                "domain": "short.test",
                "group": "team",
                "slug": "taken",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("slug", response.json())
