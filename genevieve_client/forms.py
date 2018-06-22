from django import forms

from .models import GenomeReport

GENEVIEVE_EFFECT_CHOICES = (
    ('causal', 'Causes this trait or disease'),
    ('risk_factor', 'Increased risk of this trait or disease'),
    ('protective', 'Prevents or reduces risk of this trait or disease'),
)

GENEVIEVE_INHERITANCE_CHOICES = (
    ('recessive', 'Recessive'),
    ('dominant', 'Dominant'),
    ('additive', 'Additive'),
    ('unknown', 'Other, unknown, or not applicable'),
)

GENEVIEVE_EVIDENCE_CHOICES = (
    ('well_established', 'Well-established'),
    ('reported', 'Reported'),
    ('contradicted', 'Contradicted'),
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
