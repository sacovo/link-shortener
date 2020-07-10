from django.db import models
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.models import Group
import secrets

# Create your models here.


class Domain(models.Model):
    domain_name = models.CharField(max_length=40, unique=True)
    groups = models.ManyToManyField(Group)

    def __str__(self):
        return self.domain_name


def get_slug():
    return secrets.token_urlsafe(16).lower()

class Link(models.Model):
    target = models.URLField(verbose_name=_("target"), max_length=1200)

    domain = models.ForeignKey(Domain, models.CASCADE)
    slug = models.SlugField(default=get_slug)

    custom_tags = models.BooleanField(default=True)

    group = models.ForeignKey("auth.Group", models.CASCADE)

    title = models.CharField(max_length=500, blank=True)
    og_title = models.CharField(max_length=500, blank=True)
    og_type = models.CharField(max_length=40, blank=True)
    og_description = models.TextField(blank=True)

    og_image_url = models.CharField(max_length=800, blank=True)
    og_image = models.ImageField(blank=True, upload_to='images/')

    og_image_width = models.CharField(max_length=30, blank=True)
    og_image_height = models.CharField(max_length=30, blank=True)

    og_video_url = models.CharField(max_length=800, blank=True)
    og_video = models.FileField(upload_to='videos/', blank=True)

    og_video_width = models.IntegerField(default=1920, blank=True)
    og_video_height = models.IntegerField(default=1080, blank=True)

    og_url = models.CharField(max_length=300, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    twitter_card = models.CharField(max_length=20, blank=True, choices=(
        ('summary', 'summary'),
        ('summary_large_image', 'summary_large_image'),
        ('app', 'app'),
        ('player', 'player'),
    ))

    twitter_site = models.CharField(max_length=30, blank=True)
    twitter_creator = models.CharField(max_length=30, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['domain', 'slug'], name="domain_slug_unique"
            ),
        ]

    def __str__(self):
        return self.slug


    def get_absolute_url(self):
        return f"https://{self.domain.domain_name}/{self.slug}/"
