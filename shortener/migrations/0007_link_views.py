# Generated by Django 4.2.4 on 2023-08-08 08:01

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("shortener", "0006_auto_20200710_2026"),
    ]

    operations = [
        migrations.AddField(
            model_name="link",
            name="views",
            field=models.IntegerField(default=0),
        ),
    ]
