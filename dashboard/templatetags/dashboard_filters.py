from django import template
register = template.Library()

@register.filter
def goal_color(goal):
    if goal['pct'] >= 75:
        return 'c-green'
    if goal.get('is_overdue') or (goal.get('days_since_progress') or 0) > 7:
        return 'c-red'
    return ''