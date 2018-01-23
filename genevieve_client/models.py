from collections import OrderedDict
import datetime
import re
import requests

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.postgres.fields import JSONField
from django.db import models
from django.utils import timezone as django_timezone

from pytz import timezone as pytz_timezone
import myvariant
from vcf2clinvar import clinvar_update


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
    myvariant_gnomad_genome = JSONField(default={})
    myvariant_last_update = models.DateTimeField(null=True)

    def __unicode__(self):
        return self.b37_id

    @property
    def allele_frequency(self):
        if self.myvariant_gnomad_genome:
            return float(self.myvariant_gnomad_genome['af']['af'])
        elif self.myvariant_exac:
            ac = None
            if type(self.myvariant_exac['alleles']) == list:
                try:
                    idx = self.myvariant_exac['alleles'].index(self.var_allele)
                    ac = self.myvariant_exac['ac']['ac'][idx]
                except Exception:
                    pass
            else:
                ac = self.myvariant_exac['ac']['ac']
            if ac:
                an = self.myvariant_exac['an']['an']
                return ac * 1.0 / an
        elif self.myvariant_dbsnp:
            for item in self.myvariant_dbsnp['alleles']:
                try:
                    if item['allele'] == self.var_allele:
                        return item['freq']
                except KeyError:
                    continue
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
    report_name = models.CharField(max_length=120)
    genome_file_url = models.TextField()
    genome_file_created = models.TextField()
    last_processed = models.DateTimeField(null=True)
    report_source = models.CharField(max_length=80, blank=True)
    variants = models.ManyToManyField(Variant, through='GenomeVariant',
                                      through_fields=('genome', 'variant'))

    def refresh_myvariant_data(self):
        vars_by_hgvs = {
            v.b37_hgvs_id: v for v in self.variants.all()}
        mv = myvariant.MyVariantInfo()
        mv_data = mv.getvariants(vars_by_hgvs.keys(), fields=[
            'clinvar', 'dbsnp', 'exac', 'gnomad_genome'])
        for var_data in mv_data:
            if '_id' not in var_data:
                variant = vars_by_hgvs[var_data['query']]
                variant.myvariant_clinvar = {}
                variant.myvariant_exac = {}
                variant.myvariant_dbsnp = {}
                variant.save()
                continue
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
            try:
                variant.myvariant_gnomad_genome = var_data['gnomad_genome']
            except KeyError:
                variant.myvariant_gnomad_genome = {}
            variant.myvariant_last_update = django_timezone.now()
            variant.save()

    def new_clinvar_available(self):
        cv_year, cv_month, cv_day = [int(x) for x in re.search(
            r'_(20[0-9][0-9])([01][0-9])([0-3][0-9])\.vcf',
            clinvar_update.latest_vcf_filename('b37')).groups()]
        try:
            cv_latest = datetime.datetime(
                cv_year, cv_month, cv_day + 1, 0, 0, 0,
                tzinfo=pytz_timezone('US/Eastern'))
        except ValueError:
            try:
                cv_latest = datetime.datetime(
                    cv_year, cv_month + 1, 1, 0, 0, 0,
                    tzinfo=pytz_timezone('US/Eastern'))
            except ValueError:
                cv_latest = datetime.datetime(
                    cv_year + 1, 1, 1, 0, 0, 0,
                    tzinfo=pytz_timezone('US/Eastern'))
        if self.last_processed and self.last_processed > cv_latest:
            return False
        return True

    def refresh_oh_report_file_url(self, user_data=None):
        if self.report_source.startswith('openhumans-'):
            new_url, created = self.user.openhumansuser.file_url_for_source(
                self.report_source, user_data=user_data)
            if new_url:
                self.file_url = new_url
                # Changed creation indicates a fresh file for processing.
                if created != self.genome_file_created:
                    self.genome_file_created = created
                    self.last_processed = None
                self.save()

    def refresh(self, oh_user_data=None, force=False):
        if self.new_clinvar_available() or force:
            # Refresh file URL for Open Humans data.
            if self.report_source.startswith('openhumans-'):
                self.refresh_oh_report_file_url(user_data=oh_user_data)

            # Refresh object to ensure up-to-date file URL.
            report = GenomeReport.objects.get(pk=self.pk)

            # Avoid circular import.
            from .tasks import produce_genome_report

            # Delete old variants and create a new list.
            report.genomevariant_set.all().delete()
            produce_genome_report.delay(report)
        else:
            from .tasks import refresh_myvariant_data
            refresh_myvariant_data.delay(self)


class GenomeVariant(models.Model):
    genome = models.ForeignKey(GenomeReport)
    variant = models.ForeignKey(Variant)
    zygosity = models.CharField(max_length=3,
                                choices=(('Het', 'Heterozygous'),
                                         ('Hom', 'Homozygous'),
                                         ('Hem', 'Hemizygous')))


class GenevieveUser(models.Model):
    user = models.OneToOneField(User)
    genome_upload_enabled = models.BooleanField(default=False)
    passed_quiz = models.BooleanField(default=False)
    agreed_to_terms = models.BooleanField(default=False)


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
        self.token_expiration = (django_timezone.now() +
                                 datetime.timedelta(
                                     seconds=token_data['expires_in']))
        self.save()

    def _token_expired(self, offset=0):
        """
        True if token expired (or expires in offset seconds), otherwise False.
        """
        offset_expiration = (
            self.token_expiration - django_timezone.timedelta(seconds=offset))
        if django_timezone.now() >= offset_expiration:
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

    CLIENT_ID = settings.OPENHUMANS_CLIENT_ID
    CLIENT_SECRET = settings.OPENHUMANS_CLIENT_SECRET
    BASE_URL = settings.OPENHUMANS_URL
    SIGNUP_URL = BASE_URL + '/account/signup/'
    TOKEN_URL = BASE_URL + '/oauth2/token/'
    REDIRECT_URI = settings.OPENHUMANS_REDIRECT_URI
    AUTH_URL = (
        BASE_URL + '/direct-sharing/projects/oauth2/authorize/'
        '?client_id={}&response_type=code&redirect_uri={}'.format(
            CLIENT_ID, REDIRECT_URI))
    OPENHUMANS_PROJECTMEMBERID_URL = BASE_URL + ''
    USER_URL = BASE_URL + '/api/direct-sharing/project/exchange-member/'
    SOURCES = ['pgp', 'twenty_three_and_me', 'vcf_data']

    def __unicode__(self):
        return self.openhumans_username

    @property
    def project_member_id(self):
        return self.connected_id

    def get_user_data(self):
        access_token = self.get_access_token()
        user_data_response = requests.get(
            self.USER_URL,
            headers={'Authorization': 'Bearer {}'.format(access_token)})
        return user_data_response.json()

    def get_current_ohreports_by_source(self):
        ohreports_by_source = {}
        reports = GenomeReport.objects.filter(user=self.user)
        for report in reports:
            if report.report_source.startswith('openhumans-'):
                ohreports_by_source[report.report_source] = report
        return ohreports_by_source

    def file_url_for_source(self, source, user_data=None):
        if not user_data:
            user_data = self.get_user_data()
        for datafile in user_data['data']:
            datafile_source = 'openhumans-{}-{}'.format(
                datafile['source'],
                datafile['id'])
            if datafile_source == source:
                return (datafile['download_url'], datafile['created'])
        return None, None

    def make_report_name(self, username, file_info):
        SOURCE_TO_NAME = {
            'pgp': 'Harvard PGP',
            'twenty_three_and_me': '23andMe',
            'dna_land': 'DNA.land',
            'genes_for_good': "Genes For Good",
            'veritas_genetics': 'Veritas Genetics',
            'genos_exome': 'Genos',
            'full_genomes_corp': 'Full Genomes Corp.',
        }
        source_slug = file_info['source']
        if (file_info['source'] == 'vcf_data' and
                'metadata' in file_info and
                'vcf_source' in file_info['metadata']):
            source_slug = file_info['metadata']['vcf_source']
        if source_slug in SOURCE_TO_NAME:
            source_name = SOURCE_TO_NAME[source_slug]
        else:
            source_name = source_slug
        return "{}'s {} data (filename: \"{}\")".format(
            username, source_name, file_info['basename'])

    def perform_genome_reports(self, request=None):
        """
        Refresh genome reports or produce new ones. Only one per source.
        """
        user_data = self.get_user_data()

        import json

        current_reports = self.get_current_ohreports_by_source()

        oh_sources = dict()
        for item in user_data['data']:
            if not ('source' in item and
                    'basename' in item and
                    'metadata' in item and
                    'tags' in item['metadata'] and
                    'vcf' in item['metadata']['tags']):
                continue
            if item['source'] not in self.SOURCES:
                continue
            if not (item['basename'].endswith('.vcf') or
                    item['basename'].endswith('.vcf.gz') or
                    item['basename'].endswith('.vcf.bz2')):
                continue
            source = 'openhumans-{}-{}'.format(
                item['source'],
                item['id'])

            oh_sources[source] = item

        # Refresh current reports
        current_reports = self.get_current_ohreports_by_source()
        for source in current_reports:
            if source in oh_sources:
                del(oh_sources[source])
                current_reports[source].refresh(oh_user_data=user_data)
            else:
                current_reports[source].delete()

        # Look for new ones to create, and start them.
        for source in oh_sources.keys():
            datafile = oh_sources[source]
            report_name = self.make_report_name(username=user_data['username'],
                                                file_info=datafile)
            new_report = GenomeReport(
                genome_file_url=datafile['download_url'],
                user=self.user,
                report_name=report_name,
                report_source=source,
            )
            new_report.save()

            # Avoid circular import.
            from .tasks import produce_genome_report
            produce_genome_report.delay(new_report)
            if request:
                messages.success(request, (
                    '"{}" started processing! Please give reports up to '
                    "fifteen minutes to complete.".format(
                        new_report.report_name)))


class GennotesEditor(ConnectedUser):
    """
    Connect a GenNotes account.

    The GenNotes user ID is stored in the 'connected_id' model field.
    """
    gennotes_username = models.CharField(max_length=30, blank=True)
    gennotes_email = models.EmailField()

    CLIENT_ID = settings.GENNOTES_CLIENT_ID
    CLIENT_SECRET = settings.GENNOTES_CLIENT_SECRET
    BASE_URL = settings.GENNOTES_URL
    AUTH_URL = (
        BASE_URL + '/oauth2-app/authorize?client_id={}&'
        'response_type=code'.format(CLIENT_ID))
    SIGNUP_URL = BASE_URL + '/accounts/signup/'
    TOKEN_URL = BASE_URL + '/oauth2-app/token/'
    REDIRECT_URI = settings.GENNOTES_REDIRECT_URI
    USER_URL = BASE_URL + '/api/me/'

    def __unicode__(self):
        return self.gennotes_username
