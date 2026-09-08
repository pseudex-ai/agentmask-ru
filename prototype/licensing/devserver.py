"""Run the licensing server locally, exactly as it runs in production.

Two ASGI apps on two ports, so the admin surface is not merely unrouted but
unreachable from the public one.

    python3 -m licensing.devserver            # public :8443, admin :9443

Used by the e2e stand and by `test_perf_masking.py`. It starts the REAL
`licensing/server.py`; there is no test double anywhere in this repo, because a
stand that runs different code proves nothing about the code that ships
(docs/tz-license-packaging.md §4.1).
"""

import logging
import os
import threading

import uvicorn

from licensing import server

# КОРНЕВОЙ ЛОГГЕР НАСТРАИВАЕМ МЫ, ПОТОМУ ЧТО UVICORN ЭТОГО НЕ ДЕЛАЕТ.
#
# `uvicorn.Config(log_level="info")` настраивает ТОЛЬКО логгеры самого uvicorn
# (`uvicorn`, `uvicorn.error`, `uvicorn.access`) и корневой не трогает вовсе. У
# `logging.getLogger("licensing.server")` обработчика поэтому не было ни одного,
# и дальше срабатывало правило Python по умолчанию:
#
#   * всё уровня INFO ПРОПАДАЛО МОЛЧА — включая `RAW_LEASE_BODY`, на котором
#     стоит гейт L12, то есть проверка «на провод не уходят персональные
#     данные» удостоверялась над пустой строкой и не смотрела ни на одно тело;
#   * WARNING и ERROR печатались аварийным обработчиком `logging.lastResort` —
#     голым текстом, без времени, без уровня и без имени логгера. «отчёт о
#     расходе с неверной подписью» и «токен витрины использован не на своём
#     пути» приходили в общий лог неотличимо от чужого вывода и без ответа на
#     вопрос «когда».
#
# Двадцать четыре точки логирования в `server.py` и `store.py` — это весь
# оперативный след единственного сервера, который у нас есть.
logging.basicConfig(
    level=os.environ.get("PSEUDEX_LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


def serve(app: object, port: int, certfile: str, keyfile: str) -> uvicorn.Server:
    config = uvicorn.Config(
        app, host="0.0.0.0", port=port, log_level="info",
        ssl_certfile=certfile or None, ssl_keyfile=keyfile or None,
    )
    return uvicorn.Server(config)


def main() -> None:
    certfile = os.environ.get("PSEUDEX_LICENSE_CERT", "")
    keyfile = os.environ.get("PSEUDEX_LICENSE_KEYFILE", "")
    public_port = int(os.environ.get("PSEUDEX_LICENSE_PORT", "8443"))
    admin_port = int(os.environ.get("PSEUDEX_LICENSE_ADMIN_PORT", "9443"))

    # Admin is plain HTTP on a separate port: it is reachable only from inside
    # the deployment network and never published.
    admin = serve(server.admin_app, admin_port, "", "")
    threading.Thread(target=admin.run, name="licensing-admin", daemon=True).start()
    serve(server.app, public_port, certfile, keyfile).run()


if __name__ == "__main__":
    main()
