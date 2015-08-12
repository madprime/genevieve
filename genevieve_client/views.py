import datetime
import requests

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.urlresolvers import reverse_lazy
from django.utils.decorators import method_decorator
from django.views.generic import (DetailView, FormView, ListView,
                                  RedirectView, TemplateView)

from .models import GennotesEditor, GenomeReport
from .forms import GenomeUploadForm
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
                'redirect_uri': 'http://localhost:8000/authorize_gennotes/'
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
