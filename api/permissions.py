from django.contrib.auth.models import Group

from shortener.models import Domain


def groups_for(user):
    """The groups a user may file links under."""
    if not user.is_authenticated:
        return Group.objects.none()
    if user.is_superuser:
        return Group.objects.all()
    return user.groups.all()


def domains_for(user):
    """The domains a user may create links on."""
    if not user.is_authenticated:
        return Domain.objects.none()
    if user.is_superuser:
        return Domain.objects.all()
    return Domain.objects.filter(groups__user=user).distinct()
