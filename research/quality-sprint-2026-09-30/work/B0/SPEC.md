# B0 — текущая база и сохранность WIP

Разрешение: утверждённый sprint-plan и новый goal запуска исполнения. Здесь нет правки engine/scorer/corpus или нового платного прогона.

## Приёмка

- Заархивировать authored dirty/untracked работу и существующие evidence, отдельно от производных dependency/cache деревьев; не менять исходники. Каждый файл архива перепроверить SHA256 с источником.
- Dependency/cache — явно reference-only по хешам; ничего не удалять. Credential/DB paths не копировать молча; все исключения вывести. Из первоначального списка исключённых secret paths оказалось0.
- Сверить88 pinned planning baseline files и17 исходных файлов платного run с прежним manifest.
- Зафиксировать commit/branch/v6 ref, source/scorer hashes, Python/libs и идентичность development bundle в памяти.
- Повторить лишь технический census paidrun802complete/11excluded и membership intersection с существующим holdout359, не оценивать/tune holdout.
- Получить независимую read-only проверку исполнения и ограничений перед B0 PASS.

## Граница G1

G1 для начала локальной design/RED-волны закрывает источник, WIP, среду и raw evidence. Production digest **NOT_VERIFIED** — отдельное требование G1/RG перед release-A/B; это явно следует из плана «production digest подтверждён для release-A/B». Никакого заявления о сравнении с фактически развёрнутым артефактом сейчас нет. Не блокировать read-only/design работу неизвестным deployment, но не пропускать RG с этим пробелом.

## Команды и результаты

- `PYTHONDONTWRITEBYTECODE=1 prototype/.venv/bin/python research/quality-sprint-2026-09-30/work/B0/checkpoint.py` → job bash-1188, exit0; результаты в checkpoint.log.
- Runtime pin: `.venv/bin/python` из prototype, `build_payload/build_plaintext` без org/watermark и без записи bundle → exit0; RUNTIME.json.

Архив private-wip-checkpoint.tar.gz — приватная локальная копия, не git commit и не deliverable для публичного распространения. В нём441проверенных файла, dependency/cache3554файла reference-only, archive bytes21968795. Source/run pinned198, prior88/raw17совпали. Не путать snapshotcopied с committed/pushed.

Нет RED/GREEN для product mechanism: задача сохранения данных, не исправление engine. Её отрицательные проверки — assertions missing/changed hash, duplicate existingarchive refusal, population mismatch и holdoutintersection; mutation engine тут неприменима.
