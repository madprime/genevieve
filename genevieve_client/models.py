from collections import OrderedDict

from django.conf import settings
from django.db import models

CHROMOSOMES = OrderedDict([
    (1, 'chr1'),
    (2, 'chr2'),
    (3, 'chr3'),
    (4, 'chr4'),
    (5, 'chr5'),
    (6, 'chr6'),
    (7, 'chr7'),
    (8, 'chr8'),
    (9, 'chr9'),
    (10, 'chr10'),
    (11, 'chr11'),
    (12, 'chr12'),
    (13, 'chr13'),
    (14, 'chr14'),
    (15, 'chr15'),
    (16, 'chr16'),
    (17, 'chr17'),
    (18, 'chr18'),
    (19, 'chr19'),
    (20, 'chr20'),
    (21, 'chr21'),
    (22, 'chr22'),
    (23, 'chrX'),
    (24, 'chrY'),
    (25, 'chrM'),
    ])


def get_upload_path(instance, filename=''):
    """
    Construct the upload path for a given DataFile and filename.
    """
    return '/'.join([instance.user.username, 'genomes', filename])


class Variant(models.Model):
    chromosome = models.PositiveSmallIntegerField(choices=CHROMOSOMES.items())
    pos = models.PositiveIntegerField()
    ref_allele = models.CharField(max_length=255)
    var_allele = models.CharField(max_length=255)

    @property
    def b37_id(self):
        return '-'.join([str(x) for x in [self.chromosome, self.pos,
                                          self.ref_allele, self.var_allele]])


class GenomeReport(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL)
    report_name = models.CharField(max_length=30)
    genome_file = models.FileField(upload_to=get_upload_path)
    genome_format = models.CharField(
        max_length=6,
        choices=[('vcf', 'VCF (Variant Call Format)'),
                 ('cgivar', 'Complete Genomics var file')])
    variants = models.ManyToManyField(Variant, through='GenomeVariant',
                                      through_fields=('genome', 'variant'))


class GenomeVariant(models.Model):
    genome = models.ForeignKey(GenomeReport)
    variant = models.ForeignKey(Variant)
    zygosity = models.CharField(max_length=3,
                                choices=(('Het', 'Heterozygous'),
                                         ('Hom', 'Homozygous'),
                                         ('Hem', 'Hemizygous')))
