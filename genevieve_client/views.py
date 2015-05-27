from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse_lazy
from django.utils.decorators import method_decorator
from django.views.generic.edit import FormView

from .models import GenomeReport
from .forms import GenomeUploadForm


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
        # Insert calling celery task for genome processing here.
        return super(GenomeImportView, self).form_valid(form)
