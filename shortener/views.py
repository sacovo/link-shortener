from django.shortcuts import render, get_object_or_404, redirect
from .models import Link

# Create your views here.

def index(request):
    return redirect('https://github.com/sacovo/link-shortener')


def link_detail(request, slug):
    domain = request.get_host()

    link = get_object_or_404(Link, slug__iexact=slug, domain__domain_name__iexact=domain)

    if link.custom_tags:
        return render(request, 'shortener/link_detail.html', {
            'link': link
        })
    else:
        return redirect(link.target)
