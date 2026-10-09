# Admin control-plane UI — owner's concept (reference)

Owner-authored reference for the local admin interface of the Docker engine.
This is the binding UI source for the "must-have configurability core" (see
`docs/build-brief-must-core.md` §UI). It is a static design concept, NOT running
code — no handler here is a production backend contract.

## Provenance

- Original archive: `Оптимизация_UI_движка_Docker_контейнера.zip`
  (sha256 `4c38a9c14ed8baf49c283dcb10bda5d97200980d60335156bac847ea9d99932f`),
  read-only copy at
  `/Users/igor/.dsh/attachments/v1/files/4c/4c38a9c14ed8baf49c283dcb10bda5d97200980d60335156bac847ea9d99932f/Оптимизация_UI_движка_Docker_контейнера.zip`.
- Files here are copied for in-repo reference; `interface.dc.html` is the
  concept (original filename «Локальный интерфейс.dc.html»), `support.js` its
  design-concept runtime, `nocturne-design-system.md` the design system it uses
  (dark "Nocturne" theme: Inter, single blurple accent #9184d9, 8px radius,
  outlined buttons, Phosphor icons, dense 0.7× spacing).
- `schematic-1/2/3.png` are the three diagrams that ship with the concept.

## Screen inventory (concept labels, not backend capabilities)

Агенты и инструменты · Волт (vault) · Журнал · Интеграция · Политика ·
Качество детекции · Дрейф и аномалии · Инциденты · Регрессии · Библиотека
шаблонов · Лицензия · Настройки контейнера · Дежурный экран · Восстановление
в аргументах · Граница настройки · Отклонение от политики.

The build brief maps these to the F01–F19/W02–W13 must-have core; screens that
have no backend contract yet are `unsupported/not_available`, never a fake
success toast.
