"""Маршруты операторской консоли.

СОБСТВЕННЫЙ `urls.py` И `include()`, хотя остальные страницы витрины перечислены
плоско в `pseudex_site/urls.py`. Причина в префиксе: он берётся из
`settings.ADMIN_PATH`, потому что фиксированный `/admin/` первым пробует любой
сканер, — и пять маршрутов, каждый из которых пришлось бы собирать f-строкой на
месте, это ровно то, ради чего `include()` существует. Django-админка рядом
смонтирована так же.
"""

from django.urls import path

from ops import views

urlpatterns = [
    path("", views.fleet, name="ops_fleet"),
    path("chains/", views.chains, name="ops_chains"),
    path("plans/", views.plans, name="ops_plans"),
    path("plans/<str:code>/", views.edit_plan, name="ops_edit_plan"),
    # Последним: `org_` — свободная строка, и маршрут выше по конкретному пути
    # иначе был бы съеден им.
    path("<str:org_id>/", views.customer, name="ops_customer"),
]
