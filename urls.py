"""Root URL configuration.

Note the ordering: everything that is not `admin/` or `api/` falls through to
the shortener, whose `<slug:slug>/` pattern matches any single path segment.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("api.urls")),
    path("", include("shortener.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
