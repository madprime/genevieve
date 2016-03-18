from django import forms
from django.conf import settings

from .models import GenomeReport

GENEVIEVE_ALLELE_FREQUENCY_SOURCE_CHOICES = (
    ('', ''),
    ('dbnp', 'Single Nucleotide Polymorphism database (dbSNP)'),
    ('exac', 'Exome Aggregation Consortium (ExAC)'),
    ('esp', 'Exome Sequencing Project'),
    ('other', 'Other'),
)

GENEVIEVE_INHERITANCE_CHOICES = (
    ('recessive', 'Recessive'),
    ('dominant', 'Dominant'),
    ('additive', 'Additive'),
    ('unknown', 'Other, unknown, or not applicable'),
)

GENEVIEVE_EVIDENCE_CHOICES = (
    ('well-established', 'Well-established'),
    ('reported', 'Reported'),
    ('contradicted', 'Contradicted'),
    ('misreported', 'Misreported'),
)


class GenomeUploadForm(forms.ModelForm):
    """
    Genome file upload form.
    """
    class Meta:
        model = GenomeReport
        fields = ['report_name', 'genome_file_url']
        widgets = {
            'genome_file_url': forms.Textarea(attrs={'cols': 80, 'rows': 1}),
        }


class GenevieveEditForm(forms.Form):
    genevieve_allele_freq = forms.FloatField(
        max_value=1.0, min_value=0.0, required=False)
    genevieve_allele_freq_source = forms.ChoiceField(
        choices=GENEVIEVE_ALLELE_FREQUENCY_SOURCE_CHOICES,
        required=False,
    )
    genevieve_inheritance = forms.ChoiceField(
        choices=GENEVIEVE_INHERITANCE_CHOICES,
    )
    genevieve_evidence = forms.ChoiceField(
        choices=GENEVIEVE_EVIDENCE_CHOICES,
    )
    genevieve_notes = forms.CharField(widget=forms.Textarea, required=False)

    def clean(self):
        cleaned_data = super(GenevieveEditForm, self).clean()
        genevieve_allele_freq = cleaned_data.get("genevieve_allele_freq")
        genevieve_allele_freq_source = cleaned_data.get(
            "genevieve_allele_freq_source")

        if genevieve_allele_freq_source and not genevieve_allele_freq:
            raise forms.ValidationError(
                'Allele frequency source specified, but no allele frequency!')
