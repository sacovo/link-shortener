# Generated by Django 3.0.7 on 2020-07-10 20:26

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("shortener", "0005_auto_20200710_2014"),
    ]

    operations = [
        migrations.AlterField(
            model_name="link",
            name="custom_tags",
            field=models.BooleanField(default=True),
        ),
        migrations.AlterField(
            model_name="link",
            name="og_title",
            field=models.CharField(blank=True, max_length=500),
        ),
        migrations.AlterField(
            model_name="link",
            name="title",
            field=models.CharField(blank=True, max_length=500),
        ),
    ]
