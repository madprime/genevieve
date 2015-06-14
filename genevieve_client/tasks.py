"""Tasks for analyzing genome/genetic data files"""
# absolute_import prevents conflicts between project celery.py file
# and the celery package.
from __future__ import absolute_import
import bz2
from ftplib import FTP
import gzip
import os

from celery import shared_task
from django.conf import settings
import cgivar2vcf
import vcf2clinvar
from vcf2clinvar import clinvar_update
from vcf2clinvar.common import CHROM_INDEX, REV_CHROM_INDEX

from .models import Variant, GenomeVariant, CHROMOSOMES


def setup_twobit_file():
    local_storage = os.path.join(settings.LOCAL_STORAGE_ROOT,
                                 'genome_processing_files')
    if not os.path.exists(local_storage):
        os.makedirs(local_storage)
    twobit_filepath = os.path.join(local_storage, 'hg19.2bit')
    if not os.path.exists(twobit_filepath):
        with open(twobit_filepath, 'w') as fh:
            ftp = FTP('hgdownload.cse.ucsc.edu')
            ftp.login(user='anonymous', passwd=settings.SUPPORT_EMAIL)
            ftp.cwd('goldenPath/hg19/bigZips/')
            ftp.retrbinary('RETR hg19.2bit', fh.write)
    return twobit_filepath


def setup_clinvar_file():
    local_storage = os.path.join(settings.LOCAL_STORAGE_ROOT,
                                 'genome_processing_files')
    if not os.path.exists(local_storage):
        os.makedirs(local_storage)
    clinvar_filepath = clinvar_update.get_latest_vcf_file(
        target_dir=local_storage, build='b37')
    if clinvar_filepath.endswith('.bz2'):
        clinvar_file = bz2.BZ2File(clinvar_filepath, 'rb')
    elif clinvar_filepath.endswith('.gz'):
        clinvar_file = gzip.open(clinvar_filepath, 'rb')
    else:
        clinvar_file = open(clinvar_filepath)
    return clinvar_file


@shared_task
def produce_genome_report(genome_report):
    if genome_report.genome_format == 'vcf':
        if genome_report.genome_file.name.endswith('.bz2'):
            genome_in = bz2.BZ2File(genome_report.genome_file.path, 'rb')
        elif genome_report.genome_file.name.endswith('.gz'):
            genome_in = gzip.open(genome_report.genome_file.path, 'rb')
        else:
            genome_in = open(genome_report.genome_file.path)
    elif genome_report.genome_format == 'cgivar':
        twobit_filepath = setup_twobit_file()
        genome_in = cgivar2vcf.convert(cgi_data=genome_report.genome_file.path,
                                       twobit_ref=twobit_filepath)

    clinvar_file = setup_clinvar_file()
    clinvar_matches = vcf2clinvar.match_to_clinvar(genome_file=genome_in,
                                                   clin_file=clinvar_file)
    chrom_map = {v: k for k, v in CHROMOSOMES.items()}
    for genome_vcf_line, allele, zygosity in clinvar_matches:
        chrom = chrom_map[REV_CHROM_INDEX[CHROM_INDEX[genome_vcf_line.chrom]]]
        pos = genome_vcf_line.start
        ref_allele = genome_vcf_line.ref_allele
        var_allele = allele.sequence

        # Only record if has significance that isn't "not provided", "benign",
        # "likely benign", or "other".
        sigs = [r.sig for r in allele.records if
                r.sig != '1' and r.sig != '2' and
                r.sig != '3' and r.sig != '255']
        if not sigs:
            continue
        # Only record if a report with a disease name exists.
        dbns = [r.dbn for r in allele.records if r.dbn != 'not_provided']
        if not dbns:
            continue

        variant, _ = Variant.objects.get_or_create(chromosome=chrom,
                                                   pos=pos,
                                                   ref_allele=ref_allele,
                                                   var_allele=var_allele)
        genome_variant, _ = GenomeVariant.objects.get_or_create(
            genome=genome_report,
            variant=variant,
            zygosity=zygosity)
