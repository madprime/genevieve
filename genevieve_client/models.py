from collections import OrderedDict
import datetime
import requests

from django.conf import settings
from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

CHROMOSOMES = OrderedDict([
    (1, '1'),
    (2, '2'),
    (3, '3'),
    (4, '4'),
    (5, '5'),
    (6, '6'),
    (7, '7'),
    (8, '8'),
    (9, '9'),
    (10, '10'),
    (11, '11'),
    (12, '12'),
    (13, '13'),
    (14, '14'),
    (15, '15'),
    (16, '16'),
    (17, '17'),
    (18, '18'),
    (19, '19'),
    (20, '20'),
    (21, '21'),
    (22, '22'),
    (23, 'X'),
    (24, 'Y'),
    (25, 'M'),
    ])


def get_upload_path(instance, filename=''):
    """
    Construct the upload path for a given DataFile and filename.
    """
    return '/'.join([instance.user.username, 'genomes', filename])


class Variant(models.Model):
    chromosome = models.PositiveSmallIntegerField(choices=CHROMOSOMES.items())
    pos = models.PositiveIntegerField()
    ref_allele = models.CharField(max_length=255)
    var_allele = models.CharField(max_length=255)

    @property
    def b37_id(self):
        return '-'.join([str(x) for x in [self.chromosome, self.pos,
                                          self.ref_allele, self.var_allele]])


class GenomeReport(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL)
    report_name = models.CharField(max_length=30)
    genome_file = models.FileField(upload_to=get_upload_path)
    genome_format = models.CharField(
        max_length=6,
        choices=[('vcf', 'VCF (Variant Call Format)'),
                 ('cgivar', 'Complete Genomics var file')])
    variants = models.ManyToManyField(Variant, through='GenomeVariant',
                                      through_fields=('genome', 'variant'))


class GenomeVariant(models.Model):
    genome = models.ForeignKey(GenomeReport)
    variant = models.ForeignKey(Variant)
    zygosity = models.CharField(max_length=3,
                                choices=(('Het', 'Heterozygous'),
                                         ('Hom', 'Homozygous'),
                                         ('Hem', 'Hemizygous')))


class GennotesEditor(models.Model):
    user = models.OneToOneField(User)
    gennotes_username = models.CharField(max_length=30, blank=True)
    gennotes_userid = models.PositiveIntegerField(null=True)
    access_token = models.CharField(max_length=30, blank=True)
    refresh_token = models.CharField(max_length=30, blank=True)
    token_expiration = models.DateTimeField(null=True)

    GENNOTES_AUTH_URL = (
        settings.GENNOTES_SERVER + '/oauth2-app/authorize?client_id={}&'
        'response_type=code'.format(settings.GENNOTES_CLIENT_ID))
    GENNOTES_TOKEN_URL = settings.GENNOTES_SERVER + '/oauth2-app/token/'
    GENNOTES_USER_URL = settings.GENNOTES_SERVER + '/api/me/'

    def _refresh_tokens(self):
        response_refresh = requests.post(
            self.GENNOTES_TOKEN_URL,
            data={
                'grant_type': 'refresh_token',
                'refresh_token': self.refresh_token},
            auth=requests.auth.HTTPBasicAuth(
                settings.GENNOTES_CLIENT_ID, settings.GENNOTES_CLIENT_SECRET))
        token_data = response_refresh.json()
        self.access_token = token_data['access_token']
        self.refresh_token = token_data['refresh_token']
        self.token_expiration = (timezone.now() +
                                 datetime.timedelta(
                                     seconds=token_data['expires_in']))
        self.save()

    def _token_expired(self, offset=0):
        """
        True if token expired (or expires in offset seconds), otherwise False.
        """
        offset_expiration = (
            self.token_expiration - timezone.timedelta(seconds=offset))
        if timezone.now() >= offset_expiration:
            return True
        return False

    def get_access_token(self, offset=30):
        """
        Return access token fresh for at least offset seconds (default 30).
        """
        if self._token_expired(offset=30):
            self._refresh_tokens()
        return self.access_token

    def __unicode__(self):
        return self.gennotes_username
