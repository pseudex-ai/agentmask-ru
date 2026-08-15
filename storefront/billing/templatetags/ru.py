"""Russian plural forms for numbers rendered on the public site.

Django's built-in `pluralize` chooses between two forms. Russian needs three,
selected by the last digits: "1 контейнер", "4 контейнера", "12 контейнеров".
The usual shortcut — writing "контейнер(ов)" — reads like an unfinished page,
and it sits on the pricing card, which is the one screen where a visitor is
deciding whether this looks like a product worth paying for.
"""

from django import template

register = template.Library()


@register.filter
def plural(count: int, forms: str) -> str:
    """Pick a form: `{{ n }} {{ n|plural:"ключ,ключа,ключей" }}`.

    `forms` is "one,few,many" — the nominative singular, the genitive singular
    and the genitive plural, in that order.
    """
    one, few, many = forms.split(",")
    n = abs(int(count))
    # 11-14 take the "many" form regardless of their last digit, which is why
    # testing the last digit alone gives "11 контейнера".
    if 11 <= n % 100 <= 14:
        return many
    last = n % 10
    if last == 1:
        return one
    if last in (2, 3, 4):
        return few
    return many
