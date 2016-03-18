# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='GennotesEditor',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('gennotes_username', models.CharField(max_length=30, blank=True)),
                ('gennotes_id', models.PositiveIntegerField(unique=True)),
                ('gennotes_email', models.EmailField(max_length=254)),
                ('access_token', models.CharField(max_length=30, blank=True)),
                ('refresh_token', models.CharField(max_length=30, blank=True)),
                ('token_expiration', models.DateTimeField(null=True)),
                ('genome_upload_enabled', models.BooleanField(default=False)),
                ('genome_storage_enabled', models.BooleanField(default=False)),
                ('user', models.OneToOneField(to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='GenomeReport',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('report_name', models.CharField(max_length=80)),
                ('genome_file_url', models.TextField()),
                ('last_processed', models.DateTimeField(null=True)),
                ('user', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='GenomeVariant',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('zygosity', models.CharField(max_length=3, choices=[(b'Het', b'Heterozygous'), (b'Hom', b'Homozygous'), (b'Hem', b'Hemizygous')])),
                ('genome', models.ForeignKey(to='genevieve_client.GenomeReport')),
            ],
        ),
        migrations.CreateModel(
            name='Variant',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('chromosome', models.PositiveSmallIntegerField(choices=[(1, b'1'), (2, b'2'), (3, b'3'), (4, b'4'), (5, b'5'), (6, b'6'), (7, b'7'), (8, b'8'), (9, b'9'), (10, b'10'), (11, b'11'), (12, b'12'), (13, b'13'), (14, b'14'), (15, b'15'), (16, b'16'), (17, b'17'), (18, b'18'), (19, b'19'), (20, b'20'), (21, b'21'), (22, b'22'), (23, b'X'), (24, b'Y'), (25, b'M')])),
                ('pos', models.PositiveIntegerField()),
                ('ref_allele', models.CharField(max_length=255)),
                ('var_allele', models.CharField(max_length=255)),
            ],
        ),
        migrations.AddField(
            model_name='genomevariant',
            name='variant',
            field=models.ForeignKey(to='genevieve_client.Variant'),
        ),
        migrations.AddField(
            model_name='genomereport',
            name='variants',
            field=models.ManyToManyField(to='genevieve_client.Variant', through='genevieve_client.GenomeVariant'),
        ),
    ]
