import re

from django.template.defaulttags import register


@register.filter
def space_after_colon(string):
    return re.sub(r':', ': ', string)


@register.filter
def variant_flags(row_data):
    flags = []

    # Variant level contradicted flag: add only if there are notes, and all
    # notes are "contradicted".
    all_contradicted = True if row_data['gennotes_data'] else False
    for item in row_data['gennotes_data']:
        if item['tags']['evidence'] != 'contradicted':
            all_contradicted = False
    if all_contradicted:
        flags.append('flag-contradicted')

        # Default report is to hide all "contradicted" effects.
        if 'hidden' not in flags:
            flags.append('hidden')
    return ' '.join(flags)


@register.filter
def note_flags(item):
    flags = []

    # Note level contradicted flag.
    if item['tags']['evidence'] == 'contradicted':
        flags.append('flag-contradicted')
        # Default report is to hide all "contradicted" effects.
        if 'hidden' not in flags:
            flags.append('hidden')

    return ' '.join(flags)


@register.filter
def significance_display(significance):
    if significance == 'risk_factor':
        return 'risk factor'
    return significance


@register.filter
def inheritance_display(inheritance):
    if inheritance == 'other_or_unknown':
        return 'other/unknown'
    return inheritance
