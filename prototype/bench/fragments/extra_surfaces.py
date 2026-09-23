"""Шов: третья и четвёртая поверхности прибора, подхватываемые `surfaces.available`.

Файл существует, потому что шов знает ровно одно имя модуля и ровно одну
функцию в нём (`surfaces.py::_extra`). Больше здесь ничего и не должно быть:
поверхности живут в своих модулях — `surfaces_stream.py` и `surfaces_proxy.py`, —
а тут только их сборка, чтобы «что подключено» читалось одной строкой.

ПОРЯДОК ИМЕЕТ ЦЕНУ, И ОНА ОДНА: прокси поднимает два сервера и берёт аренду,
поэтому строится последним — если он не встанет, поток уже стоит, и ошибка
называет виновника, а не «поверхностей нет».
"""

from bench.fragments.engine import Engine
from bench.fragments.surfaces import Surface
from bench.fragments.surfaces_proxy import ProxySurface
from bench.fragments.surfaces_stream import StreamSurface


def surfaces(engine: Engine) -> tuple[Surface, ...]:
    return (StreamSurface(engine), ProxySurface(engine))
