from django import template

register = template.Library()

@register.filter
def subtract(value, arg):
    """Subtract arg from value."""
    try:
        return float(value) - float(arg)
    except (ValueError, TypeError):
        try:
            return value - arg
        except Exception:
            return 0

@register.filter
def savings_amount(old_price, selling_price):
    """Calculate savings amount."""
    try:
        savings = float(old_price) - float(selling_price)
        return round(savings, 2)
    except (ValueError, TypeError):
        return 0

@register.filter
def savings_percentage(old_price, selling_price):
    """Calculate savings percentage."""
    try:
        savings = float(old_price) - float(selling_price)
        percentage = (savings / float(old_price)) * 100
        return round(percentage, 1)
    except (ValueError, TypeError, ZeroDivisionError):
        return 0