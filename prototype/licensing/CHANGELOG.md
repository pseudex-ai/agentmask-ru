# Changelog

## [0.3.21](https://github.com/Isk4R1oT/Obscura/compare/platform/v0.3.20...platform/v0.3.21) (2026-09-28)


### Прочее

* **platform:** Synchronize platform versions

## [0.3.20](https://github.com/Isk4R1oT/Obscura/compare/platform/v0.3.19...platform/v0.3.20) (2026-09-24)


### Новое

* **licensing:** объёмный лимит и PAYG-овередж вместо слот-счёта инстансов ([#24](https://github.com/Isk4R1oT/Obscura/issues/24)) ([69f1de1](https://github.com/Isk4R1oT/Obscura/commit/69f1de191c22b0f51f535b38c1fb2e40e384e10a))

## [0.3.19](https://github.com/Isk4R1oT/Obscura/compare/platform/v0.3.18...platform/v0.3.19) (2026-09-23)


### Новое

* **licensing:** слоты и поколения вместо счёта живых процессов ([#21](https://github.com/Isk4R1oT/Obscura/issues/21)) ([44f65fa](https://github.com/Isk4R1oT/Obscura/commit/44f65fa4928f72388bfa0370dfcc1950ae6a3235))


### Исправления

* **licensing:** два разных окна — слот контейнера по признаку жизни, места процессов по окну аренды; сервер называет причину освобождения; /admin/release помечает, а не удаляет ([9daaad1](https://github.com/Isk4R1oT/Obscura/commit/9daaad1963fe67eeca593cfea09e133931982fda))
* **licensing:** занятость по признаку жизни, бюджет перевыдач, честные отказы и экраны — третий заход ([6f258fd](https://github.com/Isk4R1oT/Obscura/commit/6f258fdde234508c52617ac12baad7dd83747df3))
* **licensing:** потолок стоит там, где процесс становится способен обслуживать — на ёмкости, а не только на аренде ([29f9801](https://github.com/Isk4R1oT/Obscura/commit/29f980137c1aaaeffb03b2e4f164de0f4cd05623))
* **licensing:** честный релиз освобождает место сразу — клиент пробного тарифа больше не заперт (10/10 стартов против блокировки на 6-м у выпущенного 0.3.17) ([c74be8f](https://github.com/Isk4R1oT/Obscura/commit/c74be8f1da4e4da3d807326e1b739a6582932dc3))

## [0.3.18](https://github.com/Isk4R1oT/Obscura/compare/platform/v0.3.17...platform/v0.3.18) (2026-09-21)


### Прочее

* **platform:** Synchronize platform versions

## [0.3.17](https://github.com/Isk4R1oT/Obscura/compare/platform/v0.3.16...platform/v0.3.17) (2026-09-21)


### Прочее

* **platform:** Synchronize platform versions

## [0.3.16](https://github.com/Isk4R1oT/Obscura/compare/platform/v0.3.15...platform/v0.3.16) (2026-09-20)


### Новое

* **license:** лестница версий в клиенте — «есть новее», устаревание, 426, баннер и doctor ([7e09bc7](https://github.com/Isk4R1oT/Obscura/commit/7e09bc7e690132560ae0e6c1da3260827a1269a4))
* **licensing:** реестр версий в аренде — вердикт «новее / устарела / закрыта», 426 и флот по версиям ([9ae6b51](https://github.com/Isk4R1oT/Obscura/commit/9ae6b51a5bd7b7442deb985a113d266605efa327))
* **localui:** экран «Версии» — циклы поддержки из подписанного блока аренды, команда обновления ([9ce8bae](https://github.com/Isk4R1oT/Obscura/commit/9ce8bae8b92466a16ebd1ce60f6849e106230bd1))


### Исправления

* **licensing:** десять дефектов ревью ветки — реестр не гниёт в день eol, новая версия не «старейшая», upgrade по тому контейнера ([04abb19](https://github.com/Isk4R1oT/Obscura/commit/04abb1985584571d34c6c20c53f37ce0c20fc146))
