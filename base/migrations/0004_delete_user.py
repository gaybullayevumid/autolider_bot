# Generated by Django 5.1.5 on 2025-01-26 08:48

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0003_user'),
    ]

    operations = [
        migrations.DeleteModel(
            name='User',
        ),
    ]
