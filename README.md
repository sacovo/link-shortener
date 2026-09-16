# Link shortener

Works like bit.ly, but has the ability to customize preview images and other open graph tags. So you can customize how a link looks if you share it on facebook, twitter and co.

Runs on Django 5.2 LTS, with a [django-unfold](https://unfoldadmin.com/) admin and a
REST API for automation.

## Setup

Clone repository

```
docker compose up -d
docker compose exec web python manage.py createsuperuser
```

The admin is at http://127.0.0.1:8000/admin/, the API docs at
http://127.0.0.1:8000/api/v1/docs/.

To make a short link resolve you first need a **Domain** whose name matches the
host the request arrives on (`127.0.0.1:8000` when developing), and a **Group**
that both the domain and your user belong to.

## Deployment

```
docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml exec web python manage.py migrate
docker compose -f docker-compose.prod.yml exec web python manage.py collectstatic --no-input
docker compose -f docker-compose.prod.yml exec web python manage.py createsuperuser
```

For production copy .env.dev to .env.prod and change passwords and keys.
Change traefik labels to fit domain.

Once the service is behind TLS, switch the security settings on in `.env.prod`:

```
SESSION_COOKIE_SECURE=1
CSRF_COOKIE_SECURE=1
USE_X_FORWARDED_PROTO=1
SECURE_HSTS_SECONDS=31536000
```

## CI / images

`.github/workflows/ci.yml` runs the test suite against PostgreSQL on every push
and pull request, and — once tests pass — builds `Dockerfile.prod` and pushes it
to `ghcr.io/sacovo/link-shortener`. Pull requests build the image but do not push
it. No secrets to configure: the workflow signs in with the automatic
`GITHUB_TOKEN`.

Tags produced:

| Trigger | Tag |
| --- | --- |
| push to `master` | `latest`, `master`, `sha-<commit>` |
| push of tag `v1.2.3` | `1.2.3`, `1.2`, `1`, `sha-<commit>` |

So cutting a release is `git tag v1.2.3 && git push --tags`.

The first push creates the GHCR package as **private**. To pull it on a server
without credentials, open the package on GitHub → *Package settings* → *Change
visibility* → Public. Otherwise `docker login ghcr.io` with a token that has
`read:packages` on the host.

Images are `linux/amd64`. For arm64 too, add it to `platforms` in the workflow —
the QEMU setup step is already there. Cross-builds under emulation are
noticeably slower.

## API

The API lives under `/api/v1/` and is meant for automation.

| Endpoint | Description |
| --- | --- |
| `GET/POST /api/v1/links/` | List and create short links |
| `GET/PUT/PATCH/DELETE /api/v1/links/{id}/` | Read and change a single link |
| `POST /api/v1/links/{id}/refresh-metadata/` | Re-scrape the target's open graph tags |
| `GET /api/v1/domains/` | Domains you may create links on |
| `GET /api/v1/groups/` | Groups you may file links under |
| `GET /api/v1/whoami/` | What the key you are using can reach |
| `GET /api/v1/schema/` | OpenAPI 3 schema |
| `GET /api/v1/docs/` | Swagger UI (also `/api/v1/redoc/`) |

### Authentication

Create a key under *API keys* in the admin. The secret is shown **once**, right
after saving — store it then, it is only kept hashed. Keys belong to a user and
can only reach what that user can reach; they can be given an expiry date and
revoked at any time.

```
curl -H "Authorization: Api-Key <prefix>.<secret>" https://example.com/api/v1/whoami/
```

### Creating a link

`domain` and `group` are addressed by name, not by id. `slug` is optional; leave
it out and a random one is generated. Unless you pass `"fetch_metadata": false`,
the target is scraped for open graph tags and anything you did not set yourself
is filled in from it.

```
curl -X POST https://example.com/api/v1/links/ \
  -H "Authorization: Api-Key <prefix>.<secret>" \
  -H "Content-Type: application/json" \
  -d '{
        "target": "https://example.org/a-long-url",
        "domain": "example.com",
        "group": "marketing",
        "slug": "launch"
      }'
```

```json
{
  "id": 1,
  "slug": "launch",
  "short_url": "https://example.com/launch/",
  "target": "https://example.org/a-long-url",
  "views": 0,
  "...": "the scraped og_* and twitter_* fields"
}
```

### Listing and filtering

Results are paginated (`limit`/`offset`). Filters: `domain`, `group`, `slug`,
`target`, `custom_tags`, `created_after`, `created_before`; plus `search=` over
slug, title and target and `ordering=` over `created_at`, `views`, `slug`.

```
curl -H "Authorization: Api-Key <prefix>.<secret>" \
  "https://example.com/api/v1/links/?domain=example.com&ordering=-views"
```

View counts are also readable without a key, per link, at
`https://<domain>/<slug>/count/`.

## Structure

Configuration is in the top-directory: `settings.py`, `urls.py`

- `shortener/` — models, the redirect/preview views and the admin
- `shortener/metadata.py` — the open graph scraper, shared by the admin and the API
- `api/` — REST API, the user-bound API key model and its admin

docker-compose.prod.yml is prepared for use with the traefik load balancer.

## Tests

```
docker compose exec web python manage.py test
```
