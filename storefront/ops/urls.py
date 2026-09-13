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
    # Конструктор — про ДЕНЬГИ и живёт только у нас; `plans/` — про ёмкость и
    # сверку с лицензионным сервером. Два экрана, потому что это два разных
    # вопроса и у них разные последствия: цена дойдёт до клиента при продлении,
    # потолок инстансов — сразу.
    path("tariffs/", views.constructor, name="ops_constructor"),
    path("demand/", views.demand, name="ops_demand"),
    path("analytics/", views.analytics, name="ops_analytics"),
    path("plans/<str:code>/", views.edit_plan, name="ops_edit_plan"),
    # Последними: `org_` — свободная строка, и маршруты выше по конкретному пути
    # иначе были бы съедены ими. Внутри этой пары порядок тоже значим — более
    # длинный путь первым.
    path("<str:org_id>/reconcile/", views.reconcile, name="ops_reconcile"),
    path("<str:org_id>/usage.csv", views.usage_csv, name="ops_usage_csv"),
    path("<str:org_id>/", views.customer, name="ops_customer"),
]
