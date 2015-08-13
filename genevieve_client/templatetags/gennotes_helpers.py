from django.template.defaulttags import register


@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)


@register.filter
def parse_gennotes_citations(clinvar_relation_data):
    citations = clinvar_relation_data['tags'].get('clinvar-rcva:citations')
    if citations:
        return citations.split(';')
    return citations
