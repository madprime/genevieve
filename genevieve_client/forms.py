from django import forms
from django.conf import settings

from .models import GenomeReport

GENEVIEVE_INHERITANCE_CHOICES = (
    ('recessive', 'Recessive'),
    ('dominant', 'Dominant'),
    ('additive', 'Additive'),
    ('unknown', 'Other, unknown, or not applicable'),
)

GENEVIEVE_EVIDENCE_CHOICES = (
    ('well-established', 'Well-established'),
    ('reported', 'Reported'),
    ('disputed', 'Disputed'),
    ('disproven', 'Disproven'),
)


class GenomeUploadForm(forms.ModelForm):
    """
    Genome file upload form.
    """
    class Meta:
        model = GenomeReport
        fields = ['report_name', 'genome_file', 'genome_format']


class GenevieveEditForm(forms.Form):
    genevieve_inheritance = forms.ChoiceField(
        choices=GENEVIEVE_INHERITANCE_CHOICES,
    )
    genevieve_evidence = forms.ChoiceField(
        choices=GENEVIEVE_EVIDENCE_CHOICES,
    )
    genevieve_notes = forms.CharField(widget=forms.Textarea)
