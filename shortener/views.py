from django.db.models import F
from django.http import JsonResponse
from django.shortcuts import HttpResponseRedirect, get_object_or_404, redirect, render

from .models import Link


def index(request):
    return redirect("https://digitalorganizing.ch")


class CustomSchemeRedirect(HttpResponseRedirect):
    allowed_schemes = ["http", "https", "ftp", "mailto"]


def _get_link(request, slug):
    return get_object_or_404(
        Link, slug__iexact=slug, domain__domain_name__iexact=request.get_host()
    )


def link_detail(request, slug):
    link = _get_link(request, slug)

    # Counted with an UPDATE so that concurrent hits don't overwrite each other.
    Link.objects.filter(pk=link.pk).update(views=F("views") + 1)

    if link.custom_tags:
        return render(request, "shortener/link_detail.html", {"link": link})

    return CustomSchemeRedirect(link.target)


def link_count(request, slug):
    return JsonResponse({"count": _get_link(request, slug).views})
