import datetime
import json
import re
import requests

from django.conf import settings
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.urlresolvers import reverse_lazy, reverse
from django.http import HttpResponseRedirect
from django.utils.decorators import method_decorator
from django.views.generic.detail import (SingleObjectMixin,
                                         SingleObjectTemplateResponseMixin)
from django.views.generic import (DetailView, FormView, ListView,
                                  RedirectView, TemplateView, UpdateView)

from .models import GennotesEditor, GenomeReport, Variant
from .forms import GenomeUploadForm
from .tasks import produce_genome_report

User = get_user_model()


def make_unique_username(base):
    """
    Ensure a unique username. Almost always identical to the GenNotes username.

    It's theoretically possible for username changes on GenNotes to result in a
    collision. This method ensures that the Genevieve username is unique.
    Probably this function never actually gets used.
    """
    try:
        User.objects.get(username=base)
    except User.DoesNotExist:
        return base
    else:
        n = 2
        while True:
            name = base + str(n)
            try:
                User.objects.get(username=name)
                n += 1
            except User.DoesNotExist:
                return name


class HomeView(TemplateView):
    template_name = 'genevieve_client/home.html'

    def get_context_data(self, **kwargs):
        kwargs.update({
            'genevieve_admin_email': settings.GENEVIEVE_ADMIN_EMAIL,
            'gennotes_auth_url': GennotesEditor.GENNOTES_AUTH_URL,
            'gennotes_server': GennotesEditor.GENNOTES_SERVER,
            'gennotes_signup_url': GennotesEditor.GENNOTES_SIGNUP_URL,
        })
        return super(HomeView, self).get_context_data(**kwargs)


class AuthorizeGennotesView(RedirectView):
    template_name = 'genevieve_client/complete_gennotes_auth'
    pattern_name = 'home'

    @staticmethod
    def _exchange_code(code):
        token_response = requests.post(
            GennotesEditor.GENNOTES_TOKEN_URL,
            data={
                'grant_type': 'authorization_code',
                'code': code,
                'redirect_uri': settings.GENNOTES_REDIRECT_URI
            },
            auth=requests.auth.HTTPBasicAuth(
                settings.GENNOTES_CLIENT_ID, settings.GENNOTES_CLIENT_SECRET
            )
        )
        return token_response.json()

    @staticmethod
    def _get_user_data(access_token):
        user_data_response = requests.get(
            GennotesEditor.GENNOTES_USER_URL,
            headers={'Authorization': 'Bearer {}'.format(access_token)})
        return user_data_response.json()

    def get(self, request, *args, **kwargs):
        if 'code' in request.GET:
            token_data = self._exchange_code(request.GET['code'])
            user_data = self._get_user_data(token_data['access_token'])

            try:
                gennotes_editor = GennotesEditor.objects.get(
                    gennotes_id=user_data['id'])
                gennotes_editor.access_token = token_data['access_token']
                gennotes_editor.refresh_token = token_data['refresh_token']
                gennotes_editor.token_expiration = (
                    datetime.datetime.now() +
                    datetime.timedelta(seconds=token_data['expires_in']))
                gennotes_editor.gennotes_username = user_data['username']
                gennotes_editor.gennotes_email = user_data['email']
                gennotes_editor.save()
                user = gennotes_editor.user
                user.backend = (
                    'genevieve_client.auth_backends.AuthenticationBackend')
                login(request, user)
                messages.success(
                    request, ('Logged in as GenNotes user "{}".'.format(
                              user_data['username'])))
            except GennotesEditor.DoesNotExist:
                new_username = make_unique_username(base=user_data['username'])
                new_user = User(username=new_username,
                                email=user_data['email'])
                new_user.save()
                gennotes_editor = GennotesEditor(
                    user=new_user,
                    gennotes_id=user_data['id'],
                    gennotes_username=user_data['username'],
                    gennotes_email=user_data['email'],
                    access_token=token_data['access_token'],
                    refresh_token=token_data['refresh_token'],
                    token_expiration=(
                        datetime.datetime.now() +
                        datetime.timedelta(seconds=token_data['expires_in'])))
                messages.success(
                    request,
                    ('Account created for GenNotes user "{}" and authorized '
                     'for edit submissions.'.format(user_data['username'])))
                gennotes_editor.save()
                new_user.backend = (
                    'genevieve_client.auth_backends.AuthenticationBackend')
                login(request, new_user)
        else:
            messages.error(request, 'Failed to authorize GenNotes!')
        return super(AuthorizeGennotesView, self).get(
            request, *args, **kwargs)


class GenomeImportView(FormView):
    form_class = GenomeUploadForm
    success_url = reverse_lazy('home')
    template_name = 'genevieve_client/genome_import.html'

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super(GenomeImportView, self).dispatch(*args, **kwargs)

    def form_valid(self, form):
        # Double-check that user has permission to upload genome.
        if not self.request.user.gennoteseditor.genome_upload_enabled:
            print "Not authorized for genome upload??"
            messages.error(self.request,
                           'Account not authorized to upload genomes.')
            return self.form_invalid(form)
        form.user = self.request.user
        new_report = GenomeReport(
            genome_file_url=form.cleaned_data['genome_file_url'],
            user=form.user,
            report_name=form.cleaned_data['report_name'])
        new_report.save()
        produce_genome_report.delay(
            genome_report=GenomeReport.objects.get(pk=new_report.id))
        # Insert calling celery task for genome processing here.
        return super(GenomeImportView, self).form_valid(form)


class GenomeReportListView(ListView):
    model = GenomeReport

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super(GenomeReportListView, self).dispatch(*args, **kwargs)

    def get_queryset(self):
        """Only list reports belonging to this user."""
        queryset = super(GenomeReportListView, self).get_queryset()
        return queryset.filter(user=self.request.user)


class GenomeReportDetailView(DetailView):
    model = GenomeReport

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super(GenomeReportDetailView, self).dispatch(*args, **kwargs)

    def get_queryset(self):
        """Return object info only if this report belongs to this user."""
        queryset = super(GenomeReportDetailView, self).get_queryset()
        return queryset.filter(user=self.request.user)

    def get_context_data(self, **kwargs):
        """
        Add GenomeReport variants to context, sorted by allele frequency.

        Sorting by allele frequency behaves "smartly" with respect to
        missing frequency information. If the variant allele matches reference
        sequence, the frequency is "Unknown" but sorted as if it were 1
        (i.e. probably high and uninteresting). But if the variant doesn't
        match reference, the "Unknown" frequency is sorted as if it were 0
        (because it may actually be quite rare).

        Also, filter out any variants that don't have ClinVar data from
        MyVariant.info. (Inconsistency may be due to lag and changes within
        ClinVar monthly updates.)
        """
        context = super(GenomeReportDetailView, self).get_context_data(**kwargs)
        genome_variants = [gv for gv in self.object.genomevariant_set.all() if
                           gv.variant.myvariant_clinvar]
        context['genomevariants'] = sorted(
            genome_variants,
            key=lambda gv: (
                gv.variant.allele_frequency if gv.variant.allele_frequency else
                1 if gv.variant.ref_allele == gv.variant.var_allele else 0))
        return context


class GenomeReportReprocessView(DetailView):
    model = GenomeReport
    template_name = 'genevieve_client/genomereport_reprocess.html'

    def post(self, request, *args, **kwargs):
        genome_report = self.get_object()
        for genomevar in genome_report.genomevariant_set.all():
            genomevar.delete()
        produce_genome_report.delay(
            genome_report=GenomeReport.objects.get(pk=genome_report.id))
        messages.success(request,
                         'Reprocessing initiated for "{}".'.format(
                             genome_report.report_name))
        return_url = reverse('genome_report_detail', args=[genome_report.id])
        return HttpResponseRedirect(return_url)


class GenevieveNotesEditView(SingleObjectMixin, TemplateView):
    model = Variant
    initial = {'genevieve_effect': 'causal',
               'genevieve_inheritance': 'unknown',
               'genevieve_evidence': 'reported'}
    template_name = 'genevieve_client/notes_edit.html'
    CHOICES = {
        'genevieve_effect': (
            ('causal', 'Causes this trait or disease'),
            ('risk_factor', 'Increased risk of this trait or disease'),
            ('protective', 'Prevents or reduces risk of this trait or disease'),
        ),
        'genevieve_inheritance': (
            ('recessive', 'Recessive'),
            ('dominant', 'Dominant'),
            ('additive', 'Additive'),
            ('unknown', 'Other, unknown, or not applicable'),
        ),
        'genevieve_evidence': (
            ('well_established', 'Well-established'),
            ('reported', 'Reported'),
            ('contradicted', 'Contradicted'),
        )
    }

    def _get_genevieve_relations(self):
        self.genevieve_other_relations = []
        self.genevieve_notes_data = {}
        if self.gennotes_var_data:
            for relation in self.gennotes_var_data['relation_set']:
                if relation['tags']['type'] == 'genevieve-notes':
                    if self.relid != '0' and relation['url'].endswith(
                            '/api/relation/{}/'.format(self.relid)):
                        self.genevieve_genevieve_relation = relation
                    else:
                        self.genevieve_other_relations.append(relation)

    def _get_gennotes_variant(self):
        b37_lookup = 'b37-{}-{}-{}-{}'.format(
            self.object.chromosome, self.object.pos,
            self.object.ref_allele, self.object.var_allele)
        gennotes_var_req = requests.get(
            '{}/api/variant/{}'.format(
                settings.GENNOTES_SERVER, b37_lookup))
        if gennotes_var_req.status_code == 200:
            self.gennotes_var_data = gennotes_var_req.json()
        self.gennotes_var_data = None

    def _get_gennotes_data(self):
        self.object = self.get_object()
        self._get_gennotes_variant()
        self._get_genevieve_relations()

    def get_context_data(self, *args, **kwargs):
        self.object = self.get_object()
        context = super(GenevieveNotesEditView,
                        self).get_context_data(*args, **kwargs)
        self._get_gennotes_data()
        kwargs.update({
            'gennotes_data': self.gennotes_var_data,
            'genevieve_other_relations': self.genevieve_other_relations,
            'genevieve_relation': self.genevieve_notes_data,
        })
        return context

    """
    def get_success_url(self):
        self.object = self.get_object()
        return reverse('variant_edit', args=[self.object.id])

    def get_initial(self):
        initial = super(GenevieveVariantEditView, self).get_initial()
        try:
            relation_tags = self.gennotes_data['relation_data']['tags']
        except AttributeError:
            self._get_gennotes_data()
            relation_tags = self.gennotes_data['relation_data']['tags']
        if 'genevieve:inheritance' in relation_tags:
            initial['genevieve_inheritance'] = relation_tags[
                'genevieve:inheritance']
        if 'genevieve:evidence' in relation_tags:
            initial['genevieve_evidence'] = relation_tags['genevieve:evidence']
        if 'genevieve:notes' in relation_tags:
            initial['genevieve_notes'] = relation_tags['genevieve:notes']
        if 'genevieve:allele-frequency' in relation_tags:
            initial['genevieve_allele_freq'] = relation_tags[
                'genevieve:allele-frequency']
        if 'genevieve:allele-frequency-source' in relation_tags:
            initial['genevieve_allele_freq_source'] = relation_tags[
                'genevieve:allele-frequency-source']
        return initial

    def form_valid(self, form):
        relation_id = self.request.POST['relation_id']
        relation_version = self.request.POST['relation_version']
        access_token = self.request.user.gennoteseditor.get_access_token()
        relation_uri = ('{}/api/relation/{}/'.format(settings.GENNOTES_SERVER,
                                                     relation_id))

        # Assemble updated Genevieve tag data.
        tags = {}
        tags['genevieve:inheritance'] = form.cleaned_data[
            'genevieve_inheritance']
        tags['genevieve:evidence'] = form.cleaned_data['genevieve_evidence']
        tags['genevieve:notes'] = form.cleaned_data['genevieve_notes']
        # Set frequency if we got it
        if form.cleaned_data['genevieve_allele_freq']:
            tags['genevieve:allele-frequency'] = float(form.cleaned_data[
                'genevieve_allele_freq'])
            if form.cleaned_data['genevieve_allele_freq_source']:
                tags['genevieve:allele-frequency-source'] = form.cleaned_data[
                    'genevieve_allele_freq_source']

        # Send edit to the GenNotes API.
        print tags
        data = json.dumps({
            'tags': tags,
            'edited-version': int(relation_version)
        })
        print data
        response_patch = requests.patch(
            relation_uri,
            data=data,
            headers={'Content-type': 'application/json',
                     'Authorization': 'Bearer {}'.format(access_token)})
        print response_patch.status_code
        print response_patch.text
        return super(GenevieveVariantEditView, self).form_valid(form)
    """
