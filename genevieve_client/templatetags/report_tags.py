import re

from django.template.defaulttags import register


@register.filter
def space_after_colon(string):
    return re.sub(r':', ': ', string)
