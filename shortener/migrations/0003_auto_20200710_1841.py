# Generated by Django 3.0.7 on 2020-07-10 18:41

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shortener', '0002_link_created_at'),
    ]

    operations = [
        migrations.AlterField(
            model_name='link',
            name='og_image_height',
            field=models.CharField(blank=True, max_length=30),
        ),
        migrations.AlterField(
            model_name='link',
            name='og_image_width',
            field=models.CharField(blank=True, max_length=30),
        ),
        migrations.AlterField(
            model_name='link',
            name='og_video_height',
            field=models.IntegerField(blank=True, default=1080),
        ),
        migrations.AlterField(
            model_name='link',
            name='og_video_width',
            field=models.IntegerField(blank=True, default=1920),
        ),
        migrations.AlterField(
            model_name='link',
            name='twitter_card',
            field=models.CharField(blank=True, choices=[('summary', 'summary'), ('summary_large_image', 'summary_large_image'), ('app', 'app'), ('player', 'player')], max_length=20),
        ),
    ]
