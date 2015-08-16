import datetime
import json
import re
import requests

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.urlresolvers import reverse_lazy, reverse
from django.utils.decorators import method_decorator
from django.views.generic.detail import (SingleObjectMixin,
                                         SingleObjectTemplateResponseMixin)
from django.views.generic import (DetailView, FormView, ListView,
                                  RedirectView, TemplateView)

from .models import GennotesEditor, GenomeReport, Variant
from .forms import GenomeUploadForm, GenevieveEditForm
from .tasks import produce_genome_report


class HomeView(TemplateView):
    template_name = 'genevieve_client/home.html'

    def get_context_data(self, **kwargs):
        kwargs['gennotes_auth_url'] = GennotesEditor.GENNOTES_AUTH_URL
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

    @method_decorator(login_required)
    def get(self, request, *args, **kwargs):
        if 'code' in request.GET:
            token_data = self._exchange_code(request.GET['code'])
            user_data = self._get_user_data(token_data['access_token'])

            gennotes_editor, _ = GennotesEditor.objects.get_or_create(
                user=request.user)
            gennotes_editor.access_token = token_data['access_token']
            gennotes_editor.refresh_token = token_data['refresh_token']
            gennotes_editor.token_expiration = (
                datetime.datetime.now() +
                datetime.timedelta(seconds=token_data['expires_in']))
            gennotes_editor.gennotes_userid = user_data['id']
            gennotes_editor.gennotes_username = user_data['username']
            gennotes_editor.save()
            messages.success(request,
                             'GenNotes edits now authorized as GenNotes user: '
                             '"{}"'.format(user_data['username']))
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
        form.user = self.request.user
        new_report = GenomeReport(
            genome_file=self.request.FILES['genome_file'],
            user=form.user,
            report_name=form.cleaned_data['report_name'],
            genome_format=form.cleaned_data['genome_format'])
        new_report.save()
        produce_genome_report.delay(genome_report=new_report)
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
    permanent = False

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super(GenomeReportDetailView, self).dispatch(*args, **kwargs)

    def get_queryset(self):
        """Return object info only if this report belongs to this user."""
        queryset = super(GenomeReportDetailView, self).get_queryset()
        return queryset.filter(user=self.request.user)


class GenevieveVariantEditView(SingleObjectMixin,
                               SingleObjectTemplateResponseMixin,
                               FormView):
    model = Variant
    form_class = GenevieveEditForm
    initial = {'genevieve_inheritance': 'unknown',
               'genevieve_evidence': 'reported'}

    def _get_gennotes_data(self):
        self.object = self.get_object()
        b37_lookup = '-'.join([str(x) for x in [
            'b37', self.object.chromosome, self.object.pos,
            self.object.ref_allele, self.object.var_allele]])
        gennotes_data = requests.get(
            'https://gennotes.herokuapp.com/api/variant/' + b37_lookup).json()
        relation_data = gennotes_data['relation_set'][0]
        if 'relation_id' in self.request.GET:
            relation_url = (
                'https://gennotes.herokuapp.com/api/'
                'relation/{}/'.format(self.request.GET['relation_id']))
            try:
                relation_data = [r for r in gennotes_data['relation_set'] if
                                 r['url'] == relation_url][0]
            except IndexError:
                relation_data = None
        re_relation_id = r'://[^/]+/api/relation/([0-9]+)/'
        relation_id = relation_version = None
        if relation_data:
            if re.search(re_relation_id, relation_data['url']):
                relation_id = re.search(
                    re_relation_id, relation_data['url']).groups()[0]
                relation_version = relation_data['current_version']
            else:
                relation_data = None
        self.gennotes_data = {
            'gennotes_data': gennotes_data,
            'relation_data': relation_data,
            'relation_id': relation_id,
            'relation_version': relation_version
        }

    def get_context_data(self, *args, **kwargs):
        self.object = self.get_object()
        kwargs.update(self.gennotes_data)
        return super(GenevieveVariantEditView,
                     self).get_context_data(*args, **kwargs)

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
        relation_uri = ('https://gennotes.herokuapp.com/api/relation/'
            '{}/'.format(relation_id))

        # Assemble updated Genevieve tag data.
        tags = {}
        tags['genevieve:inheritance'] = form.cleaned_data[
            'genevieve_inheritance']
        tags['genevieve:evidence'] = form.cleaned_data['genevieve_evidence']
        # Notes may be empty, but we'll set anyway.
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
