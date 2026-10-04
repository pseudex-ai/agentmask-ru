# Changelog

## [0.3.20](https://github.com/Isk4R1oT/Obscura/compare/v0.3.19...v0.3.20) (2026-10-04)


### Новое

* **agent-pii:** deterministic token mint (--seed) + city+bare-street restore ([66da5ee](https://github.com/Isk4R1oT/Obscura/commit/66da5eee09b2d4987da82721d028117ee3b620a1))
* **bench:** layer-3 attribution judge over artifact_parity flags ([517bf79](https://github.com/Isk4R1oT/Obscura/commit/517bf79cd54ffffee0e7ccc6e0ea3f201351eac0))
* **hop-format:** pseudex hop-format adaptation — engine fixes + v5 hop-format measurement ([820bdae](https://github.com/Isk4R1oT/Obscura/commit/820bdae002521c27f90050aacb71660ea990ed68))
* **pseudex:** thread the tool-schema notation into the OUT leg (class Ж.2) ([b891b03](https://github.com/Isk4R1oT/Obscura/commit/b891b03d15e5bbf94606102571f128c615fc5411))


### Исправления

* **address:** recognise a settlement the morphology reads only as a surname ([0471f85](https://github.com/Isk4R1oT/Obscura/commit/0471f85e16caba6561747c95202ace97c74b2fa2))
* **agent-pii:** corpus/building is a mutable address part too (D-081 completeness) ([fa4bdd1](https://github.com/Isk4R1oT/Obscura/commit/fa4bdd10aa7182018bd9d98148cb987791efdc05))
* **agent-pii:** one address = one fake across surfaces — drop mutable parts from identity ([b77773b](https://github.com/Isk4R1oT/Obscura/commit/b77773bf1b2e5e46b9665ae8ca38f485277f360f))
* **agent-pii:** P1 phantom flat + P2 «N лет» street — both at the root ([7c56fa8](https://github.com/Isk4R1oT/Obscura/commit/7c56fa8d8699f5d84c2284b4d705207b7b958640))
* **agent-pii:** project a linked short address into the mention's own form ([768d54b](https://github.com/Isk4R1oT/Obscura/commit/768d54b1f871b7885f0c00f2659fa5f5eaada01b))
* **agent-pii:** repair agent-hop integrity — address/name/datetype/harness + objective judge ([a4e3ca3](https://github.com/Isk4R1oT/Obscura/commit/a4e3ca376e09ccd964539e0660d8c88c1302be3c))
* **agent-pii:** unify dictated house litera into the same address identity ([fde83b5](https://github.com/Isk4R1oT/Obscura/commit/fde83b5bda4e39a24e432ed8a71d858df5510d8e))
* **agent-pii:** кабинет/офис/помещение as mutable parts; projection keeps the real street type ([26f97a3](https://github.com/Isk4R1oT/Obscura/commit/26f97a32232402796a879ead167f54e74f997367))
* **agent-pii:** одна сущность — один фейк + дата/возраст + судьи + v6 ([334a89d](https://github.com/Isk4R1oT/Obscura/commit/334a89d879c2034e6c890ab8bab2d03bcaa93bc4))
* **agent-pii:** одна сущность — один фейк + дата/возраст + судьи + v6 ([334a89d](https://github.com/Isk4R1oT/Obscura/commit/334a89d879c2034e6c890ab8bab2d03bcaa93bc4))
* **detect:** «N лет моложе/старше» is a comparison, not an age ([0e7149f](https://github.com/Isk4R1oT/Obscura/commit/0e7149fd7f8da448fe01c6a67949a0870f2d0cdd))
* **detect:** «N лет» street prefix is not a duration — deny tenure markers ([09eb4d4](https://github.com/Isk4R1oT/Obscura/commit/09eb4d4acafeee2c3884a88900d315304278267f))
* **detect:** age is PII by person context, not by value (152-ФЗ) ([1cc4a98](https://github.com/Isk4R1oT/Obscura/commit/1cc4a9864ea4ef8f73a8734b0a1fa9819899854f))
* **detect:** an operational slot date is not a date of birth (152-ФЗ) ([7a7057f](https://github.com/Isk4R1oT/Obscura/commit/7a7057f1b08c85dbf31994356bb5dbfd4f30672b))
* **envelope:** keep a reserved echo marker out of detection ([c67e5a5](https://github.com/Isk4R1oT/Obscura/commit/c67e5a55845e317d9871290412229d1b23b375fc))
* **envelope:** leave a bare settlement real in the unbound privacy leg ([19eecf4](https://github.com/Isk4R1oT/Obscura/commit/19eecf4fe9e8aa8f2399973fe0910a25a672ae72))
* **envelope:** project a full echoed word as the full substitute, not a cut ([06f09e3](https://github.com/Isk4R1oT/Obscura/commit/06f09e3664b237650e3b88d3accc599166adfb17))
* keep meeting dates and bare settlements real; type associated dates DOB ([05e7bea](https://github.com/Isk4R1oT/Obscura/commit/05e7bea82feee526d95fb22f7c10b8427871b862))
* phase 4b — W1/W2/W3/W4/W5/W6/W7 (5 clusters, edge-case 44-&gt;58/66) ([2aaae23](https://github.com/Isk4R1oT/Obscura/commit/2aaae2398e7f97e2c7216f9660f19ee1cb6af277))
* production/counting masking divergence — shared recorded_values (echo part-leg substitute) ([a810bf8](https://github.com/Isk4R1oT/Obscura/commit/a810bf85fbb7f6fe5e12c73323ff42a0d8cc38bf))
* **pseudex:** close the five leak vectors (class Г) ([da8953b](https://github.com/Isk4R1oT/Obscura/commit/da8953bf34094342476b37fd2f0006314c727fe4))
* **pseudex:** close the four review-found owner-decision gaps ([f803876](https://github.com/Isk4R1oT/Obscura/commit/f80387639c7da8de370da7ba8cfdd0b8486917ca))
* **pseudex:** close the six remaining review gaps (Г-3/Г-4/Ж.2 + Б/В/Г) ([ff2a350](https://github.com/Isk4R1oT/Obscura/commit/ff2a350cd2a622abaa2f477cf6ce50c471e89dee))
* **pseudex:** compose addresses by parts, type is identity (class Б) ([af07579](https://github.com/Isk4R1oT/Obscura/commit/af07579182d1d10142cd6216e6acd4c2c67219b7))
* **pseudex:** echoed result inherits the CURRENT hop's form (class А parity) ([19e7b29](https://github.com/Isk4R1oT/Obscura/commit/19e7b291d6736af68a6c3af807765b809c54b40f))
* **pseudex:** leading-zero truncation restores the whole number (class Д) ([096941f](https://github.com/Isk4R1oT/Obscura/commit/096941fd820f05a84ab2fdebaa74e7f6b5369250))
* **pseudex:** mirror the source notation end-to-end (class А) ([341d5a6](https://github.com/Isk4R1oT/Obscura/commit/341d5a688b600044298893466ea3376e05122497))
* **pseudex:** own substitutes are a fixed point, one person one name (class В) ([e63967e](https://github.com/Isk4R1oT/Obscura/commit/e63967e3ac503437b156027ebabfd3dfbbd9d16a))
* **pseudex:** whole-address echo reservation keeps the substitute intact (class Б parity) ([0e61d92](https://github.com/Isk4R1oT/Obscura/commit/0e61d92010b1a124c1965c33294b209e0dbb5168))
* **vault:** age mints a format-preserving fake, not «REDACTED&lt;hex&gt;» ([77a4bcc](https://github.com/Isk4R1oT/Obscura/commit/77a4bccf0c95a44e5ec7d9aa190c2cee79e01d4b))
* **vault:** AGE token matches TOKEN_RE — default fake + recognizer pattern ([e9bb6a0](https://github.com/Isk4R1oT/Obscura/commit/e9bb6a0cfbb490d5fbcecccff753fd4ddf4e9da2))
* **vault:** close the random-mint class — one object, one substitute ([2f4a73c](https://github.com/Isk4R1oT/Obscura/commit/2f4a73c386834aae1a21fa89614d348b0e3028ed))
* **vault:** reuse minted name parts — one person, one substitute across hops ([5ebc4b2](https://github.com/Isk4R1oT/Obscura/commit/5ebc4b23d100c85496f7df9e0cc8dfde8ae0508c))
* W8 compositional address parts — identity=street+house, parts distinct (edge-case 65/66) ([4e8ded8](https://github.com/Isk4R1oT/Obscura/commit/4e8ded80092ca4508a8dc72f64c0ca9f6e51b657))

## [0.3.19](https://github.com/Isk4R1oT/Obscura/compare/v0.3.18...v0.3.19) (2026-09-24)


### Новое

* **licensing:** объёмный лимит и PAYG-овередж вместо слот-счёта инстансов ([#24](https://github.com/Isk4R1oT/Obscura/issues/24)) ([69f1de1](https://github.com/Isk4R1oT/Obscura/commit/69f1de191c22b0f51f535b38c1fb2e40e384e10a))
* **licensing:** слоты и поколения вместо счёта живых процессов ([#21](https://github.com/Isk4R1oT/Obscura/issues/21)) ([44f65fa](https://github.com/Isk4R1oT/Obscura/commit/44f65fa4928f72388bfa0370dfcc1950ae6a3235))

## [0.3.18](https://github.com/Isk4R1oT/Obscura/compare/v0.3.17...v0.3.18) (2026-09-23)


### Исправления

* **redact:** адреса — зеркало формы вместо равенства ключей, замёрзший родительный не косвенный падеж, нумерованная улица не дом, вырожденный ключ улицы отвечает только своему диалогу ([af030d3](https://github.com/Isk4R1oT/Obscura/commit/af030d3a8b114992e29e7e0ee9bc7f912fee3a2c))
* **redact:** кусок подмены возвращается настоящим только в НАЗВАННОЙ роли — порча чужих чисел −93%, ложные тревоги −92% ([95957f9](https://github.com/Isk4R1oT/Obscura/commit/95957f9f4c30c59982c09d1be782e2c751d02eeb))
* **vault:** видимость отказа на всех классах фрагментов плеча аргументов; двусмысленность спрашивается о подмене; pseudonym_scope доходит до фрагментов в два шага ([a346c5e](https://github.com/Isk4R1oT/Obscura/commit/a346c5eca8fe1e0eba5bf03a123fdf2276fc1ffb))
* **vault:** область разговора на ВСЕХ плечах восстановления — пять мест роняли условие, когда разговор не назван; отказ теперь видим через residual_tokens, а не молчалив ([902bf8b](https://github.com/Isk4R1oT/Obscura/commit/902bf8bb366d55a950f89f6a7409ea6a08c6e077))
* **vault:** остаток — это НАША отчеканенная подмена, которая всё ещё стоит; вопрос задаётся по роли поля, а не по форме значения ([ecf8d56](https://github.com/Isk4R1oT/Obscura/commit/ecf8d567ea6e162975368c52283c653afb100e96))
* **vault:** правило единственного кандидата для фрагмента без названного разговора; pseudonym_scope принимается на плечах восстановления; отказ по улице стал видимым ([b06d658](https://github.com/Isk4R1oT/Obscura/commit/b06d6584653e802b0214f5081f6f610514a52cd2))

## [0.3.17](https://github.com/Isk4R1oT/Obscura/compare/v0.3.16...v0.3.17) (2026-09-22)


### Исправления

* **redact:** адрес — форма агента, содержимое клиента, ни одного исправления ([1bc064d](https://github.com/Isk4R1oT/Obscura/commit/1bc064d12af4efedac9fa5e7b5aa9323a77712cc))
* **redact:** Б24 — форма принадлежит агенту для КАЖДОГО типа, в обе стороны; именительный в инструмент больше не навязывается ([a2e7921](https://github.com/Isk4R1oT/Obscura/commit/a2e7921bd3f7b08a66fefae66b8da3430e054f39))
* **redact:** дословно — значит дословно: волт помнит, что показали диалогу, и агент-копия получает строку клиента символ в символ; обратный путь в той же области разговора, что и прямой ([5af9356](https://github.com/Isk4R1oT/Obscura/commit/5af93564b565f47e82fb9883da46cebd73f2f5e9))
* **redact:** подмена адреса показывается в ФОРМЕ КЛИЕНТА на входе ([915a365](https://github.com/Isk4R1oT/Obscura/commit/915a36523c53bdc7072e51e7233b9ff32d35081f))
* **vault:** Б23 — кусок подмены разрешается только в диалоге, которому её показали; чужое слово клиента остаётся словом ([0fec1bc](https://github.com/Isk4R1oT/Obscura/commit/0fec1bce033b73f5460dc13adc4b37ff8be83a8c))

## [0.3.16](https://github.com/Isk4R1oT/Obscura/compare/v0.3.15...v0.3.16) (2026-09-21)


### Новое

* **license:** лестница версий в клиенте — «есть новее», устаревание, 426, баннер и doctor ([7e09bc7](https://github.com/Isk4R1oT/Obscura/commit/7e09bc7e690132560ae0e6c1da3260827a1269a4))
* **localui:** экран «Версии» — циклы поддержки из подписанного блока аренды, команда обновления ([9ce8bae](https://github.com/Isk4R1oT/Obscura/commit/9ce8bae8b92466a16ebd1ce60f6849e106230bd1))
* **pseudexctl:** upgrade — новый образ, тот же том, откат сам или снимком; инструмент едет в образе ([a98abbb](https://github.com/Isk4R1oT/Obscura/commit/a98abbb4d4f392913f0fcdccf97207550b4caa8a))
* **vault:** схема тома с номером — снимок до миграции, отказ тому из будущего, роль migrate ([b84bc9b](https://github.com/Isk4R1oT/Obscura/commit/b84bc9b001ede99048ef967efa080448651b3d92))


### Исправления

* **licensing:** десять дефектов ревью ветки — реестр не гниёт в день eol, новая версия не «старейшая», upgrade по тому контейнера ([04abb19](https://github.com/Isk4R1oT/Obscura/commit/04abb1985584571d34c6c20c53f37ce0c20fc146))
* **names:** Б21 — «София» склоняется, «Вера Мещерякова» женского рода, обратный путь в падеже клиента ([466b88a](https://github.com/Isk4R1oT/Obscura/commit/466b88a0d58be977c799626039d08bddf139f866))
* **redact:** Б22 — четырёхсловная подмена («Ахмед оглы») возвращается целиком, даже когда двое делят фейковую фамилию ([6cd1fd5](https://github.com/Isk4R1oT/Obscura/commit/6cd1fd57644622a42a2960ec5faceae05a93143b))

## Changelog

История движка `pseudex` (поток `vX.Y.Z`). Пишется release-please из типов коммитов; руками не правится.
