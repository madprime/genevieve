"""Tasks for analyzing genome/genetic data files"""
# absolute_import prevents conflicts between project celery.py file
# and the celery package.
from __future__ import absolute_import
import bz2
import gzip
import json
import os
import re
try:
    import urlparse
except ImportError:
    import urllib.parse as urlparse

from celery import shared_task
from django.conf import settings
from django.utils import timezone as django_timezone
import requests
from vcf2clinvar import clinvar_update
from vcf2clinvar.common import CHROM_INDEX, REV_CHROM_INDEX
from vcf2clinvar.clinvar import ClinVarVCFLine
from vcf2clinvar.genome import GenomeVCFLine

from .models import Variant, GenomeVariant, CHROMOSOMES

CHROM_MAP = {'chr' + v: k for k, v in CHROMOSOMES.items()}


def get_remote_file(url, tempdir):
    """
    Get and save a remote file to temporary directory. Return filename used.
    """
    req = requests.get(url, stream=True)
    if not req.status_code == 200:
        msg = ('File URL not working! Data processing aborted: {}'.format(url))
        raise Exception(msg)
    orig_filename = ''
    if 'Content-Disposition' in req.headers:
        regex = re.match(r'attachment; filename="(.*)"$',
                         req.headers['Content-Disposition'])
        if regex:
            orig_filename = regex.groups()[0]
    if not orig_filename:
        orig_filename = urlparse.urlsplit(req.url)[2].split('/')[-1]
    tempf = open(os.path.join(tempdir, orig_filename), 'wb')
    for chunk in req.iter_content(chunk_size=512 * 1024):
        if chunk:
            tempf.write(chunk)
    tempf.close()
    return orig_filename


def open_genome_file(genome_report):
    local_file_dir = os.path.join(
        settings.LOCAL_STORAGE_ROOT,
        'local_genome_files',
        str(genome_report.id))
    if not os.path.exists(local_file_dir):
        os.makedirs(local_file_dir)
    if len(os.listdir(local_file_dir)) == 1:
        genome_filename = os.listdir(local_file_dir)[0]
    else:
        genome_filename = get_remote_file(
            genome_report.genome_file_url, local_file_dir)
    genome_filepath = os.path.join(local_file_dir, genome_filename)
    if genome_filepath.endswith('.bz2'):
        genome_in = bz2.BZ2File(genome_filepath, 'rb')
    elif genome_filepath.endswith('.gz'):
        genome_in = gzip.open(genome_filepath, 'rb')
    else:
        genome_in = open(genome_filepath)
    return genome_in


def _next_line(filebuffer):
    try:
        next_line = filebuffer.readline()
    except AttributeError:
        next_line = filebuffer.next()
    try:
        next_line = next_line.decode('utf-8')
        return next_line
    except AttributeError:
        return next_line


def generate_clinvar_sig(clinvar_filepath, clinvar_sig_filepath):
    print("Generating new ClinVar 'significant variants' list...")
    if clinvar_filepath.endswith('.bz2'):
        clinvar_file = bz2.BZ2File(clinvar_filepath, 'rt')
    elif clinvar_filepath.endswith('.gz'):
        clinvar_file = gzip.open(clinvar_filepath, 'rt')
    else:
        clinvar_file = open(clinvar_filepath)
    clinvar_sig = list()

    i = 0
    clin_curr_line = _next_line(clinvar_file)
    while clin_curr_line.startswith('#'):
        clin_curr_line = _next_line(clinvar_file)
    while clin_curr_line:
        i += 1
        if i % 10000 == 0:
            print("{} ClinVar lines processed...".format(i))
        clinvar_vcf_line = ClinVarVCFLine(vcf_line=clin_curr_line)
        for allele in clinvar_vcf_line.alleles:
            ignore_sigs = ['unknown', 'untested', 'non-pathogenic',
                           'not_provided', 'probably non-pathogenic', 'other',
                           'benign', 'benign/likely_benign', 'likely_benign']
            if allele.clnsig.lower() in ignore_sigs:
                continue
            if allele.clnsig.lower() == 'uncertain_significance':
                meaningful_diseases = [
                    x for x in allele.clndn if x.lower() not in
                    ['not_specified']
                ]
                if not meaningful_diseases:
                    continue
            varstring = '{}-{}-{}-{}'.format(
                clinvar_vcf_line.chrom,
                clinvar_vcf_line.start,
                clinvar_vcf_line.ref_allele,
                allele.sequence)
            clinvar_sig.append(varstring)

        clin_curr_line = _next_line(clinvar_file)

    assert clinvar_sig_filepath.endswith('.json.gz')
    with gzip.open(clinvar_sig_filepath, 'wt') as f:
        json.dump(clinvar_sig, f)
    return clinvar_sig


def setup_clinvar_data():
    local_storage = os.path.join(settings.LOCAL_STORAGE_ROOT,
                                 'genome_processing_files')
    if not os.path.exists(local_storage):
        os.makedirs(local_storage)
    clinvar_filepath = clinvar_update.get_latest_vcf_file(
        target_dir=local_storage, build='b37')
    clinvar_sig_filepath = '{}.sigposlist.json.gz'.format(clinvar_filepath)
    if os.path.exists(clinvar_sig_filepath):
        clinvar_sig_file = gzip.open(clinvar_sig_filepath, 'rt')
        clinvar_sig = json.load(clinvar_sig_file)
    else:
        clinvar_sig = generate_clinvar_sig(
            clinvar_filepath, clinvar_sig_filepath)
    return set(clinvar_sig)


def get_zyg(genome_vcf_line):
    genotype_allele_indexes = genome_vcf_line.genotype_allele_indexes
    genome_alleles = [genome_vcf_line.alleles[x] for
                      x in genotype_allele_indexes]
    if len(genome_alleles) == 1:
        return 'Hem'
    elif len(genome_alleles) == 2:
        if genome_alleles[0].sequence == genome_alleles[1].sequence:
            return 'Hom'
            genome_alleles = [genome_alleles[0]]
        else:
            return 'Het'


@shared_task
def produce_genome_report(genome_report, reprocess=False):
    # Try to locally store and reuse the genome file.
    # Retrieve again if not available (e.g. due to ephemeral file storage).
    print("Producing genome report for report ID: {}".format(genome_report.id))
    genome_in = open_genome_file(genome_report)
    clinvar_sig = setup_clinvar_data()

    genome_curr_line = _next_line(genome_in)

    # Skip header.
    while genome_curr_line.startswith('#'):
        genome_curr_line = _next_line(genome_in)

    while genome_curr_line:
        entries = genome_curr_line.split('\t')
        var_alleles = entries[4].split(',')
        alleles = [entries[3]] + var_alleles
        genotypes_idx = entries[8].split(':').index('GT')
        genotypes = set(re.split('[|/]', entries[9].split(':')[genotypes_idx]))
        for genotype in genotypes:
            try:
                var_allele = alleles[int(genotype)]
            except ValueError:
                continue
            pos = entries[1]
            chrom = CHROM_MAP[
                REV_CHROM_INDEX[CHROM_INDEX[entries[0]]]]
            ref_allele = entries[3]

            varstring = '{}-{}-{}-{}'.format(
                chrom, pos, ref_allele, var_allele)
            if varstring not in clinvar_sig:
                continue

            genome_vcf_line = GenomeVCFLine(vcf_line=genome_curr_line,
                                            skip_info=True)

            # If it appears to be significant, store this as a GenomeVariant.
            zygosity = get_zyg(genome_vcf_line)
            try:
                variant = Variant.objects.get(chromosome=chrom,
                                              pos=pos,
                                              ref_allele=ref_allele,
                                              var_allele=var_allele)
            except Variant.DoesNotExist:
                variant = Variant(chromosome=chrom,
                                  pos=pos,
                                  ref_allele=ref_allele,
                                  var_allele=var_allele,
                                  myvariant_clinvar={},
                                  myvariant_exac={})
                variant.save()

            genome_variant, _ = GenomeVariant.objects.get_or_create(
                genome=genome_report,
                variant=variant,
                zygosity=zygosity)

        genome_curr_line = _next_line(genome_in)

    genome_report.last_processed = django_timezone.now()
    genome_report.save()
    genome_report.refresh_myvariant_data()


@shared_task
def refresh_myvariant_data(report):
    report.refresh_myvariant_data()
