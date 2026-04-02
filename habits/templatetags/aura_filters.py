from django import template
from django.template.defaultfilters import stringfilter

register = template.Library()

@register.filter
def split(value, delimiter=","):
    """
    Splits a string by delimiter.
    Usage: {{ "a,b,c"|split:"," }}
    """
    try:
        return value.split(delimiter) if value else []
    except (AttributeError, TypeError):
        return []