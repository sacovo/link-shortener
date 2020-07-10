# Generated by Django 3.0.7 on 2020-07-10 18:45

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("auth", "0011_update_proxy_permissions"),
        ("shortener", "0003_auto_20200710_1841"),
    ]

    operations = [
        migrations.AddField(
            model_name="link",
            name="group",
            field=models.ForeignKey(
                default=1, on_delete=django.db.models.deletion.CASCADE, to="auth.Group"
            ),
            preserve_default=False,
        ),
    ]
