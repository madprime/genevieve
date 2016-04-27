import datetime
import json
import re
import requests

from django.conf import settings
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.urlresolvers import reverse_lazy, reverse
from django.http import HttpResponseRedirect
from django.shortcuts import redirect
from django.utils import timezone as django_timezone
from django.utils.decorators import method_decorator
from django.views.generic.detail import SingleObjectMixin
from django.views.generic import (DetailView, FormView, ListView,
                                  RedirectView, TemplateView)

from .models import (GennotesEditor, GenomeReport, GenevieveUser,
                     OpenHumansUser, Variant)
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
            'gennotes_auth_url': GennotesEditor.AUTH_URL,
            'gennotes_url': GennotesEditor.BASE_URL,
            'gennotes_signup_url': GennotesEditor.SIGNUP_URL,
            'openhumans_auth_url': OpenHumansUser.AUTH_URL,
            'genomereport_list': (
                GenomeReport.objects.filter(user=self.request.user) if
                self.request.user.is_authenticated() else []),
        })
        return super(HomeView, self).get_context_data(**kwargs)

    def post(self, request, **kwargs):
        terms_categories = ['education_and_research', 'contains_errors',
                            'incomplete', 'public', 'terms']

        # SECRETCODE code.
        secret_code = request.POST['secretcode']
        if secret_code != settings.SECRETCODE:
            messages.error(
                request, 'Please give enter the secret code! '
                'Genevieve is currently invite-only.')

        elif all([item in request.POST and request.POST[item] == 'on' for
                  item in terms_categories]):
            gvuser, _ = GenevieveUser.objects.get_or_create(user=request.user)
            gvuser.agreed_to_terms = True
            gvuser.save()
            try:
                ohuser = OpenHumansUser.objects.get(user=request.user)
                ohuser.perform_genome_reports(request=request)
            except OpenHumansUser.DoesNotExist:
                pass
        else:
            messages.error(
                request, 'Please agree to our terms of use and indicate you '
                'understand important aspects of Genevieve.')
        return super(HomeView, self).get(request, **kwargs)


class DeleteAccountView(TemplateView):
    template_name = 'genevieve_client/delete_account.html'

    def post(self, request, **kwargs):
        user = request.user
        logout(request)
        user.delete()
        messages.success(request, "Your account has been deleted, as have "
                         "associated genome reports.")
        return redirect('home')


class ManageAccountView(TemplateView):
    template_name = 'genevieve_client/manage_account.html'

    def post(self, request, **kwargs):
        request.user.openhumansuser.perform_genome_reports()
        messages.success(request, "Open Humans data and reports refreshed! "
                         "Please give reports up to fifteen minutes for "
                         "processing.")
        return redirect('home')


class AuthorizeOpenHumansView(RedirectView):
    template_name = 'genevieve_client/complete_openhumans_auth'
    pattern_name = 'home'

    @staticmethod
    def _exchange_code(code):
        data = {
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': OpenHumansUser.REDIRECT_URI
        }
        token_response = requests.post(
            OpenHumansUser.TOKEN_URL,
            data=data,
            auth=requests.auth.HTTPBasicAuth(
                OpenHumansUser.CLIENT_ID, OpenHumansUser.CLIENT_SECRET
            )
        )
        return token_response.json()

    @staticmethod
    def _get_user_data(access_token):
        user_data_response = requests.get(
            OpenHumansUser.USER_URL,
            headers={'Authorization': 'Bearer {}'.format(access_token)})
        return user_data_response.json()

    def get(self, request, *args, **kwargs):
        if 'code' in request.GET:
            token_data = self._exchange_code(request.GET['code'])
            user_data = self._get_user_data(token_data['access_token'])

            try:
                openhumansuser = OpenHumansUser.objects.get(
                    connected_id=user_data['project_member_id'])
                openhumansuser.access_token = token_data['access_token']
                openhumansuser.refresh_token = token_data['refresh_token']
                openhumansuser.token_expiration = (
                    datetime.datetime.now() +
                    datetime.timedelta(seconds=token_data['expires_in']))
                openhumansuser.save()
                user = openhumansuser.user
                user.backend = (
                    'genevieve_client.auth_backends.AuthenticationBackend')
                login(request, user)
                messages.success(request, ('Logged in via Open Humans.'))
            except OpenHumansUser.DoesNotExist:
                if request.user.is_authenticated():
                    user = request.user
                else:
                    new_username = make_unique_username(
                        base='openhumans_{}'.format(user_data['project_member_id']))
                    new_user = User(username=new_username)
                    new_user.save()
                    user = new_user
                openhumansuser = OpenHumansUser(
                    user=user,
                    connected_id=user_data['project_member_id'],
                    openhumans_username=user_data['username'],
                    access_token=token_data['access_token'],
                    refresh_token=token_data['refresh_token'],
                    token_expiration=(
                        django_timezone.now() +
                        datetime.timedelta(seconds=token_data['expires_in'])))
                openhumansuser.save()
                user.backend = (
                    'genevieve_client.auth_backends.AuthenticationBackend')
                login(request, user)
                messages.success(request, 'Open Humans account connected!')
                try:
                    gvuser = GenevieveUser.objects.get(user=user)
                    if gvuser.agreed_to_terms:
                        openhumansuser.perform_genome_reports()
                except GenevieveUser.DoesNotExist:
                    pass
        else:
            messages.error(request, 'Failed to authorize Open Humans!')
        return super(AuthorizeOpenHumansView, self).get(
            request, *args, **kwargs)


class AuthorizeGennotesView(RedirectView):
    template_name = 'genevieve_client/complete_gennotes_auth'
    pattern_name = 'home'

    @staticmethod
    def _exchange_code(code):
        token_response = requests.post(
            GennotesEditor.TOKEN_URL,
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
            GennotesEditor.USER_URL,
            headers={'Authorization': 'Bearer {}'.format(access_token)})
        return user_data_response.json()

    def get(self, request, *args, **kwargs):
        if 'code' in request.GET:
            token_data = self._exchange_code(request.GET['code'])
            user_data = self._get_user_data(token_data['access_token'])

            try:
                gennotes_editor = GennotesEditor.objects.get(
                    connected_id=user_data['id'])
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
                user = request.user
                new_user = None
                if not user.is_authenticated():
                    new_username = make_unique_username(base=user_data['username'])
                    new_user = User(username=new_username,
                                    email=user_data['email'])
                    new_user.save()
                    user = new_user
                gennotes_editor = GennotesEditor(
                    user=user,
                    connected_id=user_data['id'],
                    gennotes_username=user_data['username'],
                    gennotes_email=user_data['email'],
                    access_token=token_data['access_token'],
                    refresh_token=token_data['refresh_token'],
                    token_expiration=(
                        datetime.datetime.now() +
                        datetime.timedelta(seconds=token_data['expires_in'])))
                gennotes_editor.save()
                if new_user:
                    success_msg = (
                        'Account created for GenNotes user "{}" and authorized '
                        'for edit submissions.'.format(user_data['username']))
                else:
                    success_msg = ('Account connected for GenNotes user '
                                   '"{}".'.format(user_data['username']))
                messages.success(request, success_msg)
                user.backend = (
                    'genevieve_client.auth_backends.AuthenticationBackend')
                login(request, user)
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
        if not self.request.user.genevieveuser.genome_upload_enabled:
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


class PublicGenomeReportListView(TemplateView):
    template_name = 'genevieve_client/public_genomereport_list.html'

    @staticmethod
    def public_oh_username_sources():
        public_data = []
        for source in ['pgp', 'twenty_three_and_me', 'ancestry_dna']:
            params = {'source': source, 'limit': '1000'}
            url = OpenHumansUser.BASE_URL + '/api/public-data/'
            public_data += requests.get(url, params=params).json()['results']
        public_oh_username_sources = {}
        for item in public_data:
            username = item['user']['username']
            source = 'openhumans-' + item['source']
            if username not in public_oh_username_sources:
                public_oh_username_sources[username] = []
            if source not in public_oh_username_sources[username]:
                public_oh_username_sources[username].append(source)
        return public_oh_username_sources

    def get_context_data(self, **kwargs):
        context = super(PublicGenomeReportListView, self).get_context_data(
            **kwargs)
        oh_reports = GenomeReport.objects.filter(
            report_type__startswith='openhumans-')
        public_username_sources = self.public_oh_username_sources()
        public_reports = []
        for gr in oh_reports:
            oh_username = gr.user.openhumansuser.openhumans_username
            if oh_username not in public_username_sources:
                continue
            if gr.report_type in public_username_sources[oh_username]:
                public_reports.append(gr)
        context['public_reports'] = public_reports
        return context


class GenomeReportDetailView(TemplateView):
    template_name = 'genevieve_client/genomereport_detail.html'

    def is_public(self):
        report_type = self.genomereport.report_type
        if not report_type.startswith('openhumans-'):
            return False
        oh_username = self.genomereport.user.openhumansuser.openhumans_username
        source = re.match(r'openhumans-(.*)$', report_type).groups()[0]
        params = {'source': source, 'username': oh_username}
        public_data = requests.get(OpenHumansUser.BASE_URL + '/api/public-data/',
                                   params=params).json()['results']
        if (public_data and public_data[0]['user']['username'] == oh_username and
                public_data[0]['source'] == source):
            return True
        return False

    def dispatch(self, request, *args, **kwargs):
        self.genomereport = GenomeReport.objects.get(pk=kwargs['pk'])
        if request.user == self.genomereport.user or self.is_public():
            return super(GenomeReportDetailView, self).dispatch(
                request, *args, **kwargs)
        return redirect('home')

    def get_context_data(self, **kwargs):
        """
        Add GenomeReport and variants to context, sorted by allele frequency.

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
        context = {'genomereport': self.genomereport}

        # Get local and GenNotes data, organized according to b37_gennotes_id
        genome_variants = {gv.variant.b37_gennotes_id: gv for gv in
                           self.genomereport.genomevariant_set.all()}
        if not genome_variants:
            return context
        gennotes_data = {}
        genome_variant_list = genome_variants.keys()
        while genome_variant_list:
            if len(genome_variant_list) > 100:
                sub_list = genome_variant_list[0:100]
                genome_variant_list = genome_variant_list[100:]
                gennotes_data.update({
                    res['b37_id']: res for res in
                    requests.get('{}/api/variant/'.format(settings.GENNOTES_URL),
                                 params={'variant_list': json.dumps(
                                         sub_list),
                                         'page_size': 10000}
                                 ).json()['results']
                    })
            else:
                gennotes_data.update({
                    res['b37_id']: res for res in
                    requests.get('{}/api/variant/'.format(settings.GENNOTES_URL),
                                 params={'variant_list': json.dumps(
                                         genome_variant_list),
                                         'page_size': 10000}
                                 ).json()['results']
                    })
                genome_variant_list = []
        variants_by_freq = sorted(
            genome_variants.keys(),
            key=lambda k: (
                genome_variants[k].variant.allele_frequency if
                genome_variants[k].variant.allele_frequency else
                1 if (genome_variants[k].variant.ref_allele ==
                      genome_variants[k].variant.var_allele or
                      genome_variants[k].variant.chromosome == 25) else 0))
        report_rows = []
        for var in variants_by_freq:
            genome_variant = genome_variants[var]
            variant = genome_variant.variant
            row_data = {}
            if not variant.myvariant_clinvar:
                continue
            rcvs = {rcv['accession']: rcv for rcv in
                    variant.myvariant_clinvar['rcv']
                    if not (rcv['clinical_significance'] == 'not provided' and
                    rcv['conditions']['name'] == 'not specified')}
            if not rcvs:
                continue
            unclaimed_rcvs = rcvs.copy()
            gennotes_items = []
            if var in gennotes_data:
                for item in gennotes_data[var]['relation_set']:
                    if item['tags']['type'] == 'genevieve_effect':
                        for rcv in item['tags']['clinvar_rcv_records']:
                            if rcv in unclaimed_rcvs:
                                del unclaimed_rcvs[rcv]
                        rcv_list = item['tags']['clinvar_rcv_records']
                        rcv_dict = {rcv: rcvs[rcv] if rcv in rcvs else None
                                    for rcv in rcv_list}
                        item['tags']['clinvar_rcv_records'] = rcv_dict
                        item['relation_id'] = re.search(
                            r'/api/relation/([0-9]*)/', item['url']).groups()[0]
                        gennotes_items.append(item)
            row_data['genome_variant'] = genome_variant
            row_data['variant'] = variant
            row_data['zyg'] = genome_variant.get_zygosity_display()
            row_data['frequency'] = variant.allele_frequency
            row_data['unclaimed_rcvs'] = unclaimed_rcvs
            row_data['gennotes_data'] = gennotes_items
            report_rows.append(row_data)
        context.update({
            'report_rows': report_rows,
            })
        return context


class GenomeReportReprocessView(DetailView):
    model = GenomeReport
    template_name = 'genevieve_client/genomereport_reprocess.html'

    def post(self, request, *args, **kwargs):
        genome_report = self.get_object()
        produce_genome_report.delay(
            genome_report=GenomeReport.objects.get(pk=genome_report.id))
        messages.success(request,
                         'Reprocessing initiated for "{}".'.format(
                             genome_report.report_name))
        return_url = reverse('genome_report_detail', args=[genome_report.id])
        return HttpResponseRedirect(return_url)


class GenevieveNotesEditView(SingleObjectMixin, TemplateView):
    model = Variant
    template_name = 'genevieve_client/notes_edit.html'

    def create_gennotes_variant(self):
        self.object = self.get_object()
        requests.post(
            '{}/api/variant/'.format(settings.GENNOTES_URL),
            data=json.dumps({
                'tags': {
                    'chrom_b37': str(self.object.chromosome),
                    'pos_b37': str(self.object.pos),
                    'ref_allele_b37': self.object.ref_allele,
                    'var_allele_b37': self.object.var_allele
                }}),
            headers={'Content-type': 'application/json',
                     'Authorization': 'Bearer {}'.format(
                         self.request.user.gennoteseditor.get_access_token())})

    def create_genevieve_effect_relation(self, genevieve_effect_data):
        genevieve_effect_data.update({'type': 'genevieve_effect'})
        out = requests.post(
            '{}/api/relation/'.format(settings.GENNOTES_URL),
            data=json.dumps({
                'variant': self.gennotes_var_data['url'],
                'tags': genevieve_effect_data}),
            headers={'Content-type': 'application/json',
                     'Authorization': 'Bearer {}'.format(
                         self.request.user.gennoteseditor.get_access_token())})
        if out.status_code == 201:
            messages.success(self.request, "Effect notes created!")
        else:
            messages.error(self.request, "Effect notes creation failed.")

    def update_genevieve_effect_relation(self, genevieve_effect_data):
        genevieve_effect_data.update({'type': 'genevieve_effect'})
        out = requests.patch(
            '{}/api/relation/{}/'.format(settings.GENNOTES_URL, self.relid),
            data=json.dumps({
                'edited_version': int(self.request.POST['relation_version']),
                'tags': genevieve_effect_data}),
            headers={'Content-type': 'application/json',
                     'Authorization': 'Bearer {}'.format(
                         self.request.user.gennoteseditor.get_access_token())})
        if out.status_code == 200:
            messages.success(self.request, "Effect notes updated!")
        else:
            messages.error(self.request, "Effect notes update failed.")

    def _get_genevieve_relations(self):
        self.genevieve_other_relations = []
        self.genevieve_relation = None
        if self.gennotes_var_data:
            for relation in self.gennotes_var_data['relation_set']:
                if relation['tags']['type'] == 'genevieve_effect':
                    if self.relid != '0' and relation['url'].endswith(
                            '/api/relation/{}/'.format(self.relid)):
                        self.genevieve_relation = relation
                    else:
                        self.genevieve_other_relations.append(relation)

    def _get_gennotes_variant(self):
        gennotes_var_req = requests.get(
            '{}/api/variant/{}/'.format(
                settings.GENNOTES_URL, self.object.b37_gennotes_id))
        if gennotes_var_req.status_code == 200:
            self.gennotes_var_data = gennotes_var_req.json()
            return
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
        context.update({
            'relid': self.relid,
            'gennotes_data': self.gennotes_var_data,
            'genevieve_other_relations': self.genevieve_other_relations,
            'genevieve_relation': self.genevieve_relation,
            'effect_data': ((self.genevieve_relation['tags'] if
                            self.genevieve_relation else None) if not
                            self.effect_data else self.effect_data),
        })
        if 'report' in self.request.GET:
            context.update({
                'genome_report': self.request.GET['report']
            })
        return context

    def dispatch(self, request, *args, **kwargs):
        self.relid = kwargs['relid']
        self.effect_data = None
        return super(GenevieveNotesEditView, self).dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        genevieve_effect_data = {
            'category': request.POST['genevieve_effect_category'],
            'significance': request.POST['genevieve_effect_significance'],
            'name': request.POST['genevieve_effect_name'],
            'inheritance': request.POST['genevieve_effect_inheritance'],
            'evidence': request.POST['genevieve_effect_evidence'],
            'notes': request.POST['genevieve_effect_notes'],
            'clinvar_rcv_records': request.POST.getlist(
                'genevieve_effect_clinvar_rcv_records'),
        }
        self.effect_data = genevieve_effect_data
        self._get_gennotes_data()
        if not self.gennotes_var_data:
            self.create_gennotes_variant()
            self._get_gennotes_variant()
            assert self.gennotes_var_data
        if self.relid == '0' and not self.genevieve_relation:
            self.create_genevieve_effect_relation(genevieve_effect_data)
        else:
            self.update_genevieve_effect_relation(genevieve_effect_data)
        if 'genome_report' in request.POST:
            return redirect('genome_report_detail', pk=request.POST['genome_report'])
        return redirect('home')
