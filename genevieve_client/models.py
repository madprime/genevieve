from collections import OrderedDict
import datetime
import requests

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.postgres.fields import JSONField
from django.db import models
from django.utils import timezone

import myvariant

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
    (25, 'MT'),
    ])


class Variant(models.Model):
    chromosome = models.PositiveSmallIntegerField(choices=CHROMOSOMES.items())
    pos = models.PositiveIntegerField()
    ref_allele = models.CharField(max_length=255)
    var_allele = models.CharField(max_length=255)

    myvariant_clinvar = JSONField(default={})
    myvariant_exac = JSONField(default={})
    myvariant_dbsnp = JSONField(default={})
    myvariant_last_update = models.DateTimeField(null=True)

    def __unicode__(self):
        return self.b37_id

    @property
    def allele_frequency(self):
        if self.myvariant_exac:
            ac = self.myvariant_exac['ac']['ac']
            an = self.myvariant_exac['an']['an']
            return ac * 1.0 / an
        elif self.myvariant_dbsnp:
            for item in self.myvariant_dbsnp['alleles']:
                try:
                    if item['allele'] == self.var_allele:
                        return item['freq']
                except KeyError:
                    pass
        return None

    @property
    def b37_id(self):
        return '-'.join([str(x) for x in [self.chromosome, self.pos,
                                          self.ref_allele, self.var_allele]])

    @property
    def b37_exac_id(self):
        return '-'.join([str(x) for x in [
            self.get_chromosome_display(), self.pos,
            self.ref_allele, self.var_allele]])

    @property
    def b37_hgvs_id(self):
        return myvariant.format_hgvs(
            self.get_chromosome_display(),
            self.pos,
            self.ref_allele,
            self.var_allele
        )

    @property
    def b37_gennotes_id(self):
        return 'b37-{}-{}-{}-{}'.format(
            self.chromosome, self.pos, self.ref_allele, self.var_allele)


class GenomeReport(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL)
    report_name = models.CharField(max_length=80)
    genome_file_url = models.TextField()
    last_processed = models.DateTimeField(null=True)
    variants = models.ManyToManyField(Variant, through='GenomeVariant',
                                      through_fields=('genome', 'variant'))

    def refresh_myvariant_data(self):
        vars_by_hgvs = {
            v.b37_hgvs_id: v for v in self.variants.all()}
        mv = myvariant.MyVariantInfo()
        mv_data = mv.getvariants(vars_by_hgvs.keys(), fields=['clinvar', 'dbsnp', 'exac'])
        for var_data in mv_data:
            variant = vars_by_hgvs[var_data['_id']]
            try:
                clinvar_data = var_data['clinvar']
                # Always as list - makes downstream code much easier.
                if not type(clinvar_data['rcv']) == list:
                    clinvar_data['rcv'] = [clinvar_data['rcv']]
                variant.myvariant_clinvar = var_data['clinvar']
            except KeyError:
                variant.myvariant_clivar = {}
            try:
                variant.myvariant_exac = var_data['exac']
            except KeyError:
                variant.myvariant_exac = {}
            try:
                variant.myvariant_dbsnp = var_data['dbsnp']
            except KeyError:
                variant.myvariant_dbsnp = {}
            variant.myvariant_last_update = timezone.now()
            variant.save()


class GenomeVariant(models.Model):
    genome = models.ForeignKey(GenomeReport)
    variant = models.ForeignKey(Variant)
    zygosity = models.CharField(max_length=3,
                                choices=(('Het', 'Heterozygous'),
                                         ('Hom', 'Homozygous'),
                                         ('Hem', 'Hemizygous')))


class ConnectedUser(models.Model):
    user = models.OneToOneField(User)
    access_token = models.CharField(max_length=30, blank=True)
    refresh_token = models.CharField(max_length=30, blank=True)
    token_expiration = models.DateTimeField(null=True)
    connected_id = models.CharField(null=False, max_length=30, unique=True)

    class Meta:
        abstract = True

    def _refresh_tokens(self):
        response_refresh = requests.post(
            self.TOKEN_URL,
            data={
                'grant_type': 'refresh_token',
                'refresh_token': self.refresh_token},
            auth=requests.auth.HTTPBasicAuth(
                self.CLIENT_ID, self.CLIENT_SECRET))
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


class OpenHumansUser(ConnectedUser):
    """
    Connect an Open Humans member account.

    The project_member_id is stored in the 'connected_id' model field.
    """
    openhumans_username = models.CharField(max_length=30, blank=True)
    genome_upload_enabled = models.BooleanField(default=False)
    genome_storage_enabled = models.BooleanField(default=False)

    CLIENT_ID = settings.OPENHUMANS_CLIENT_ID
    CLIENT_SECRET = settings.OPENHUMANS_CLIENT_SECRET
    BASE_URL = settings.OPENHUMANS_URL
    AUTH_URL = (
        BASE_URL + '/direct-sharing/projects/oauth2/authorize/'
        '?client_id={}&response_type=code'.format(CLIENT_ID))
    SIGNUP_URL = BASE_URL + '/account/signup/'
    TOKEN_URL = BASE_URL + '/oauth2/token/'
    REDIRECT_URI = settings.OPENHUMANS_REDIRECT_URI
    OPENHUMANS_PROJECTMEMBERID_URL = BASE_URL + ''

    def __unicode__(self):
        return self.openhumans_username

    @property
    def project_member_id(self):
        return self.connected_id


class GennotesEditor(ConnectedUser):
    """
    Connect a GenNotes account.

    The GenNotes user ID is stored in the 'connected_id' model field.
    """
    gennotes_username = models.CharField(max_length=30, blank=True)
    gennotes_email = models.EmailField()

    CLIENT_ID = settings.GENNOTES_CLIENT_ID
    CLIENT_SECRET = settings.GENNOTES_CLIENT_SECRET
    BASE_URL = settings.GENNOTES_SERVER
    AUTH_URL = (
        BASE_URL + '/oauth2-app/authorize?client_id={}&'
        'response_type=code'.format(CLIENT_ID))
    SIGNUP_URL = BASE_URL + '/accounts/signup/'
    TOKEN_URL = BASE_URL + '/oauth2-app/token/'
    REDIRECT_URI = settings.GENNOTES_REDIRECT_URI
    GENNOTES_USER_URL = BASE_URL + '/api/me/'

    def __unicode__(self):
        return self.gennotes_username
