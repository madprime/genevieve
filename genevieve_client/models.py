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
    genome_file_created = models.TextField()
    last_processed = models.DateTimeField(null=True)
    report_type = models.CharField(max_length=80, blank=True)
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
            variant.myvariant_last_update = django_timezone.now()
            variant.save()

    def new_clinvar_available(self):
        cv_year, cv_month, cv_day = [int(x) for x in re.search(
            r'_(20[0-9][0-9])([01][0-9])([0-3][0-9])\.vcf',
            clinvar_update.latest_vcf_filename('b37')).groups()]
        cv_latest = datetime.datetime(
            cv_year, cv_month, cv_day + 1, 0, 0, 0,
            tzinfo=pytz_timezone('US/Eastern'))
        if self.last_processed and self.last_processed > cv_latest:
            return False
        return True

    def refresh_oh_report_file_url(self, user_data=None):
        if self.report_type.startswith('openhumans-'):
            source = re.match(
                r'openhumans-(.*)$', self.report_type).groups()[0]
            new_url, created = self.user.openhumansuser.file_url_for_source(
                source, user_data=user_data)
            if new_url:
                self.file_url = new_url
                # Changed creation indicates a fresh file for processing.
                if created != self.created:
                    self.created = created
                    self.last_processed = None
                self.save()

    def refresh(self, oh_user_data=None):
        if self.new_clinvar_available():
            # Refresh file URL for Open Humans data.
            if self.report_type.startswith('openhumans-'):
                self.refresh_oh_report_file_url(user_data=oh_user_data)
            # Refresh object to ensure up-to-date file URL.
            report = GenomeReport.objects.get(pk=self.pk)

            # Avoid circular import.
            from .tasks import produce_genome_report
            produce_genome_report.delay(report)
        else:
            self.refresh_myvariant_data()


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
    AUTH_URL = (
        BASE_URL + '/direct-sharing/projects/oauth2/authorize/'
        '?client_id={}&response_type=code'.format(CLIENT_ID))
    SIGNUP_URL = BASE_URL + '/account/signup/'
    TOKEN_URL = BASE_URL + '/oauth2/token/'
    REDIRECT_URI = settings.OPENHUMANS_REDIRECT_URI
    OPENHUMANS_PROJECTMEMBERID_URL = BASE_URL + ''
    USER_URL = BASE_URL + '/api/direct-sharing/project/exchange-member/'

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
            if report.report_type.startswith('openhumans-'):
                source = re.match(
                    r'openhumans-(.*)$', report.report_type).groups()[0]
                ohreports_by_source[source] = report
        return ohreports_by_source

    def file_url_for_source(self, source, user_data=None):
        if not user_data:
            user_data = self.get_user_data()
        candidate_datafiles = []
        for datafile in user_data['data']:
            if (datafile['source'] == source and
                    'tags' in datafile['metadata'] and
                    'vcf' in datafile['metadata']['tags']):
                candidate_datafiles.append(datafile)
        if len(candidate_datafiles) >= 1:
            return (candidate_datafiles[0]['download_url'],
                    candidate_datafiles[0]['created'])
        return None, None

    def perform_genome_reports(self, request=None):
        """
        Refresh genome reports or produce new ones. Only one per source.
        """
        user_data = self.get_user_data()
        # Sources removed: 'twenty_three_and_me', 'ancestry_dna',
        sources = ['pgp']
        source_names = {#'twenty_three_and_me': '23andMe',
                        #'ancestry_dna': 'AncestryDNA',
                        'pgp': 'Harvard PGP'}
        current_reports = self.get_current_ohreports_by_source()

        # Refresh current reports
        for source in current_reports:
            if source in sources:
                sources.remove(source)
            current_reports[source].refresh(oh_user_data=user_data)

        # Look for new onse to create, and start them.
        for datafile in user_data['data']:
            if (datafile['source'] in sources and
                    'tags' in datafile['metadata'] and
                    'vcf' in datafile['metadata']['tags']):
                new_report = GenomeReport(
                    genome_file_url=datafile['download_url'],
                    user=self.user,
                    report_name="Report for {}'s {} data".format(
                        user_data['username'],
                        source_names[datafile['source']]),
                    report_type='openhumans-{}'.format(datafile['source']),
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
                sources.remove(datafile['source'])


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
