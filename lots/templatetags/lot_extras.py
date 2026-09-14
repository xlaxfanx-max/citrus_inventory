from django import template

register = template.Library()


@register.filter
def get_item(mapping, key):
    """Dictionary lookup by a variable key: {{ forms|get_item:packout.pk }}."""
    if mapping is None:
        return None
    return mapping.get(key)


@register.filter
def iso_date(value):
    """Parse a YYYY-MM-DD string so the date filter can format it."""
    from datetime import date

    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return value
