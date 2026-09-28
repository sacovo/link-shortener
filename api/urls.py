from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("links", views.LinkViewSet, basename="link")
router.register("shares", views.ShareViewSet, basename="share")
router.register("domains", views.DomainViewSet, basename="domain")
router.register("groups", views.GroupViewSet, basename="group")

urlpatterns = [
    path("v1/", include(router.urls)),
    path("v1/whoami/", views.WhoAmIView.as_view(), name="whoami"),
    path("v1/schema/", SpectacularAPIView.as_view(), name="api-schema"),
    path(
        "v1/docs/",
        SpectacularSwaggerView.as_view(url_name="api-schema"),
        name="api-docs",
    ),
    path(
        "v1/redoc/",
        SpectacularRedocView.as_view(url_name="api-schema"),
        name="api-redoc",
    ),
]
