# Generated by Django 5.2 on 2025-05-09 14:03

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('documents', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='client',
            name='tax_id',
            field=models.CharField(blank=True, default='', max_length=50, verbose_name='Client Tax ID'),
        ),
    ]
