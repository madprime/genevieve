from django import forms
from django.conf import settings

from .models import GenomeReport


class GenomeUploadForm(forms.ModelForm):
    """
    Genome file upload form.
    """
    class Meta:
        model = GenomeReport
        fields = ['report_name', 'genome_file', 'genome_format']
