# Deep Dive — как считать инстансы самоустановленного продукта: обход, перезапуск и то, чего нельзя купить одновременно

> Дата: 2026-09-23 · Режим: breadth fan-out (пять ветвей раскопок) + собственная сверка
> первоисточников и кода · Строится ПОВЕРХ `research/2026-09-22-instance-liveness-and-slots.md`
> и записей `docs/known-issues.md` Б26 … Б26sexies, не повторяя их.
> **В репозитории не изменено ничего, кроме этого файла.** Код читался на рабочем дереве
> (`main`, 68e58eb + незакоммиченные правки бенчмарка); ни один прод-запрос не сделан.
> Бюджет веб-поиска сессии исчерпан (200/200) к концу работы; где до первоисточника дойти
> не удалось, это сказано и оценка снижена.

---

## 1. Вопрос и границы

**Настоящий вопрос одной фразой.** Существует ли конструкция, при которой сервер лицензий
знает число одновременно обслуживающих процессов клиента ТОЧНО, обход невозможен, а честный
клиент не платит ничем за перезапуск — включая перезапуск после OOM-килла?

**Полный ответ обязан установить:**

- что именно делает «сосчитать живые инстансы» нерешаемым, и является ли это теоремой или
  инженерной трудностью;
- существует ли переформулировка задачи, в которой ответ становится точным;
- что делают те, кто прошёл это раньше — плавающие лицензии, self-hosted-вендоры, системы
  координации, — и что из этого механизм, а не маркетинг;
- какую ЕДИНИЦУ считать, если процессы считать нельзя;
- чем удостоверяется «это та же установка» и где удостоверение невозможно;
- какой класс обхода остаётся открытым при ЛЮБОЙ конструкции и чем отрасль его закрывает.

**Подвопросы (шесть, по заданию владельца).** 1 — теория отказа детектора. 2 — конструкция
вытеснения вместо отказа. 3 — что делают вживую. 4 — единица счёта. 5 — удостоверение
установки. 6 — опыт клиента при перезапуске и OOM.

**Гипотезы, с которыми заходил (оставлены, чтобы было видно, где я ошибся).**

| # | гипотеза | чем кончилось |
|---|---|---|
| Г1 | «обход невозможен» недостижим технически; достижимо «обход бессмыслен» | **подтвердилась**, и теперь у неё есть теорема, а не ощущение (§4.1, §5) |
| Г2 | нужна не седьмая заплатка, а монотонный эпох/фенсинг-токен на удостоверение | **подтвердилась и уточнилась в главном месте**: фенсинг работает ТОЛЬКО если его проверяет ресурс, и у нас такой ресурс уже есть — `/v1/meter` (§4.2, §4.3) |
| Г3 | перезапуск бесплатен, если старый держатель фенсится | **подтвердилась по форме, но неверна по механизму**: фенсинг сам по себе не делает перезапуск бесплатным — бесплатным его делает то, что новое поколение НАСЛЕДУЕТ леджер слота, а не заводит свой (§4.3) |
| Г4 | шесть заходов на сервере провалились, потому что сервер видит одинаковые сообщения | **подтвердилась, но причина глубже**: они провалились, потому что потолок стоял в валюте ВРЕМЕНИ, а платил клиент ВРЕМЕНЕМ ПРОСТОЯ; в валюте ЁМКОСТИ обе стороны сходятся (§5) |
| Г5 | вывод прошлого исследования «потолок обхода = темп × T_offline = 216» остаётся в силе | **неверна**: после шестого захода связывающая величина — не окно аренды (72 ч), а РЕЗЕРВ ёмкости (48 ч трафика). Это другая величина и другая ручка (§4.2, F13) |

---

## 2. Ответ (BLUF)

**«Сосчитать живые инстансы» — не трудная задача, а запрещённая.** Chandra–Toueg доказали,
что даже ◇W — слабейший полезный детектор отказов, которому разрешено ошибаться бесконечно
часто, — **нереализуем** в асинхронной системе, потому что его существование противоречило бы
FLP `[A]`. Всё, что сервер лицензий может построить, — это таймерная эвристика в одежде
булева значения. Шесть заходов провалились не из-за ошибок: они пытались получить ответ,
которого в модели нет.

**Отрасль это знает и давно не решает эту задачу — она её ОБХОДИТ, и ровно одним приёмом.**
Монотонный эпох (ballot в Paxos, term в Raft, view в VR, lock generation в Chubby, revision в
etcd, LockIndex в Consul, producer epoch в Kafka) прикрепляется не к актору, а к ПРАВУ
ДЕЙСТВОВАТЬ, и место действия отказывает всему, что ниже наибольшего виденного номера. Тогда
новому держателю не нужно, чтобы старого признали мёртвым: инвариант звучит не «старый умер»,
а «**в каждый момент операционен не более чем один раунд**» `[A]` — утверждение о том, СКОЛЬКО
может действовать, а не о том, ЖИВ ЛИ КТО-ТО. Вопрос о жизни из конструкции исчезает.

**И у этого приёма есть ровно одно предусловие, которое почти никто из лицензионных вендоров
выполнить не может, а мы уже выполнили.** Фенсинг работает, только если ПРОВЕРЯЕТ САМ РЕСУРС:
«*Note this requires the storage server to take an active role in checking tokens*»
(Kleppmann) `[B]`, «*The recipient server is expected to test whether the sequencer is still
valid... if not, it should reject the request*» (Burrows) `[B]`, «*the resources must provide
the version number validation mechanism... The lock feature of etcd itself cannot be used for
protecting external resources*» (etcd) `[B]`. У плавающей лицензии ресурс — чужой бинарник, до которого вендор не
дотягивается, поэтому вся категория живёт на суррогатах: FlexNet — на открытом TCP-соединении с
запасным путём в виде **двухчасового** таймаута, остальные — на интервале пульса, после которого
молчание читается как отсутствие. **У нас ресурс — наш собственный `/v1/meter`**: шестой заход (`capacity_admission`, Б26sexies) сделал право обслуживать
непрерывно выдаваемым нами разрешением, и тем самым, не зная того, построил именно ту точку
проверки, которой фенсингу не хватает.

**Поэтому рекомендация — не седьмая заплатка, а смена ключа леджера.** Ёмкость перестаёт
считаться по ключу процесса и начинает считаться по СЛОТУ, который выдаём мы; поколение
контейнера предъявляет `(slot, epoch)`, старший эпох фенсит младший НА ПОКУПКЕ ЁМКОСТИ, а
новое поколение НАСЛЕДУЕТ остаток слота вместо того, чтобы покупать свой. Перезапуск после
OOM становится бесплатным по построению — не «прощённым», а бесплатным: он не заводит новой
строки. Кольцо «аренда → релиз → аренда» становится бессмысленным по той же причине: все его
обороты делят один остаток. **И это не изобретение: RLM продаёт ту же идею под именем
`min_checkout` с прошлого века** — «only if the license did not remain checked out for the
minimum interval… in order to provide a “fairer” measure of concurrent usage» `[A]`. Вся наша
новизна — перенести минимальную занятость из ВРЕМЕНИ в ОБЪЁМ, отчего она перестаёт наказывать
честного (§5.1bis). Из кода уходят `T_alive`, остывание, эхо, бюджет перевыдач и
`holds_place` — весь инвентарь шести заходов.

**И самое неожиданное: требование владельца «не наказывать за перезапуск» — вообще не уступка
клиенту, а вынужденность платформы.** Однорепличный Deployment в Kubernetes **удваивается при
каждом обновлении по умолчанию** и обойти это нельзя: `maxUnavailable` (25 %, округление ВНИЗ)
при `replicas ≤ 3` даёт ноль, поэтому новый под обязан подняться раньше, чем погаснет старый
`[A]`. А **OOM-килл — это SIGKILL**: ни сигнала, ни обработчика, ни единого шанса позвать
`/v1/release`; graceful node shutdown в Kubernetes по умолчанию выключен `[A]`. Отсюда
приговор нашему же пятому заходу: правило Б26quinquies («честный релиз освобождает место
сразу, молчание — нет») правильно для `docker stop` и **бьёт ровно по тому пути выхода,
который владелец назвал главным.** Любая конструкция, зависящая от прощания, сломана на двух
самых частых выходах.

**Честный предел называется прямо: «обход невозможен в любом случае» недостижим, и это
теорема, а не недоработка.** Barak et al. доказали невозможность обфускации даже в очень
слабых формализациях `[A]`; академическое имя нашей задачи — **remote entrusting**, и
собственный вывод европейского проекта RE-TRUST: локальная проверка неподделываемости
недостижима, работает только перенос состояния на сервер `[B]`. Остаётся класс, который
техника не закрывает: **параллелизм бесплатен, объём оплачен.** Root может клонировать процесс
вместе с предоплаченным резервом и получить (N−1) × резерв бесплатного трафика — единожды за
клонирование, наблюдаемо как `ack_regressions`. Закрывается это не счётом инстансов, а
**размером резерва**, и резерв — это наша собственная доступность. Одна величина, два имени.

---

## 3. Самые ценные выводы

1. **Потолок обхода и окно офлайна — ОДНО ЧИСЛО, и после шестого захода это уже не 72 часа
   аренды, а 48 часов резерва.** Прошлое исследование связало `обход ≈ темп × T_offline` и
   мерило `T_offline` окном аренды. Но обслуживать без кванта нельзя (Б26sexies §1), значит
   связывающая величина — **резерв**, и он ИЗМЕРЯЕТСЯ В ЗАПРОСАХ, а не в часах:
   `reserve = min(max(rate × RESERVE_SECONDS, quantum), RESERVE_MAX[plan])`, где
   `RESERVE_SECONDS = 48*3600` (`store.py:1095,1582`), а `RESERVE_MAX` = {старт **20 000**,
   рабочий 100 000, промышленный 400 000, enterprise 8 000 000} (`store.py:1117`). Для
   сравнения: ориентир объёма тарифа «Старт» — 10 000 запросов в месяц
   (`metering-integrity.md` §9). То есть **один занятой процесс на младшем тарифе может носить
   в памяти вдвое больше запросов, чем весь его месячный объём**, и потратить их, не спросив
   нас ни разу. Комментарий в коде уже называет цену каждого часа страховки: 6 ч → 0.84 %
   худшей погрешности счёта, 24 ч → 3.34 %, 48 ч → 6.68 %. **Это и есть единственная настоящая
   ручка потолка обхода, и она не имеет никакого отношения к числу инстансов.** Шесть заходов
   крутили не ту. `[A — из кода]` `[D — связывание моё]`
2. **Та же строка, которая делает перезапуск бесплатным, делает бесплатным и оборот кольца, —
   и это одна строка SQL.** `billable = clamp(acked, granted − Q − R, granted)` по
   `(org, pubkey)`. Холодный старт: `quantum_seq == 0` → резерв 0, квант 200, нижняя граница
   `200 − 200 − 0 = 0` → воркер, умерший сразу, стоит НОЛЬ. Оборот кольца: новый ключ, покупка,
   релиз, никогда не подтверждает → та же нижняя граница 0 → 200 запросов БЕСПЛАТНО. Пока
   леджер ключуется процессом, отличить их нельзя НИКАКИМ правилом — они не различаются в
   данных. `[A — прочитано в `store.py::issue_quantum`/`billable` и `docs/metering-integrity.md`
   §4.3]`
3. **Замена порога на ПОРЯДОК убирает необходимость в детекторе вообще.** «Молчит дольше
   T_alive» — это утверждение о мире, и оно бывает ложным. «Из занятых слотов этот
   разговаривал с нами позже всех» — это ранжирование, оно не утверждает ничего и ложным быть
   не может. Ford et al. измерили, ПОЧЕМУ это важно: **свыше 90 % событий недоступности узла
   длятся менее 15 минут**, и ответом Google был не лучший детектор, а пятнадцатиминутная
   задержка перед действием `[A]`. Перезапуск после OOM выглядит ровно как эти 90 %; любое
   правило, действующее по молчанию, наказывает типичный случай ради редкого.
4. **Инверсия бенефициара — вот почему каждый из шести заходов приземлился на честного
   клиента.** Chubby ограничивает свой `lock-delay` одной минутой и говорит зачем: «*this
   limit prevents a faulty client from making a lock (and thus some resource) unavailable for
   an arbitrarily long time*» — задержка КАПИРУЕТСЯ, чтобы неисправный клиент не лишил себя
   ресурса. Consul: 15 с по умолчанию. У нас место рабочего процесса держится молчанием до
   конца суточного окна аренды — это примерно **1440× потолка Chubby**, и стоит оно не нашего
   риска, а простоя клиента. Один и тот же механизм, противоположный выгодоприобретатель.
   `[B — Chubby §2.4, Consul docs]` `[D — инверсия мой вывод]`
5. **Приём, который стоит украсть целиком, сформулирован в документации etcd одной фразой:**
   «*Actually, the lease mechanism itself doesn't guarantee mutual exclusion... **leases provide
   an optimization mechanism for reducing a number of aborted requests**.*» Аренда — это не
   гарантия, а способ удешевить обычный случай; гарантию даёт проверка номера версии у ресурса.
   Переведено на нас: **признак жизни оставить как ОПТИМИЗАЦИЮ экранов и подсказок, а
   принуждение унести на эпох в `/v1/meter`.** Система, у которой есть только первое, не имеет
   истории безопасности вовсе — у неё есть вероятность. `[B — etcd docs]`

---
6. **Единственный вендор, который документировал нашу проблему, рекомендует НЕ ОТКАЗЫВАТЬ.**
   Keygen.sh про раскатки: «**Rather than deny new node activations**, the license will
   temporarily become invalid… validations during the overage will return validation code
   `TOO_MANY_MACHINES`, which can be uniquely handled in your application code» — то есть
   отвечать различимым кодом, а не 409. «Различимо и обслуживает» лучше, чем «корректно и
   сломано». `[B]` И наоборот, их же совет для контейнеров — «generating a secure random UUID
   as a fingerprint **each time the application boots**» — делает каждый перезапуск новой
   машиной и вынуждает спасаться выбраковкой и двукратным овердрафтом. **Мы можем лучше,
   потому что у нас личность переживает перезапуск (том), а Kafka показала, как этим
   пользоваться** (KIP-345: «prioritizing “state persistence” over “liveness”»). `[A]`
7. **Число, которого не было ни в одном нашем расчёте: Docker сбрасывает бэкофф перезапуска
   после 10 СЕКУНД, Kubernetes — после 10 МИНУТ.** Один и тот же контейнер, падающий от OOM,
   генерирует обращения к нашему серверу примерно **в 3000 раз чаще** под Docker. Ёмкость
   лицензионного сервера планируется по числу Docker, а ладдер 402/403/426 не должен быть
   достижим для того, кто просто быстро перезапускается. И **ни Docker, ни Kubernetes не
   добавляют джиттер** — стадо, упавшее по общей причине, вернётся синхронно. `[A — документация
   и исходники обоих]`

## 4. Механизмы и находки

### 4.1 Почему «посчитать живые инстансы» не решается детектором отказов

**FLP (Fischer, Lynch, Paterson, JACM 32(2), апрель 1985, с. 374–382).** Модель нарочно
выбрана максимально благоприятной для алгоритма: процессы детерминированы, сообщения не
теряются и не дублируются, атомарный бродкаст ДАН. Запрещены ровно две вещи, и обе — наши:

> «Finally, we do not postulate the ability to detect the death of a process, so it is
> impossible for one process to tell whether another has died (stopped entirely) or is just
> running very slowly.» (§1, с. 375)

> **«THEOREM 1. No consensus protocol is totally correct in spite of one fault.»** (§3, с. 377)

И то, чего FLP НЕ говорит — сказано самими авторами, и это важнее теоремы для нашей задачи:

> «These results do not show that such problems cannot be “solved” in practice; rather, they
> point up the need for more refined models of distributed computing that better reflect
> realistic assumptions about processor and communication timings, and for less stringent
> requirements on the solution to such problems.» (§5)

То есть FLP — не «нельзя считать инстансы». FLP — «нельзя решить «мёртв или медленный» БЕЗ
допущения о времени». Аренда и есть это допущение. `[A]`

**Chandra–Toueg (JACM 43(2), 1996) — и сноска, ради которой стоит открывать статью.**
Детектор задаётся не реализацией, а свойствами: полнота (*strong/weak completeness*) и
точность (*perpetual/eventual accuracy*). Авторы сразу отрезают соблазн:

> «However, completeness by itself is not a useful property. To see this, consider a failure
> detector which causes every process to permanently suspect every other process… Such a
> failure detector trivially satisfies strong completeness but is clearly useless.» (§2.3)

Дальше они разбирают ровно ту схему, которая стоит у нас (пульс + таймаут + увеличение
таймаута после ложной тревоги), и говорят:

> «In an asynchronous system, this scheme does not implement a failure detector with the
> properties of ◇W: an unbounded sequence of premature time-outs may cause every correct
> process to be repeatedly added and then removed from the list of suspects…»

> «⁶ Indeed, **no algorithm can implement such a failure detector in an asynchronous system**:
> as we show in Section 6.2, this implementation could be used to solve Consensus in such a
> system, contradicting the impossibility result of Fischer et al. [1985].»

Читать это надо буквально: нереализуем не «идеальный» детектор, а **слабейший полезный** — тот,
которому разрешено ошибаться бесконечное число раз и вечно клеветать на часть живых. И §9.1
формулирует это как тезис:

> «The fundamental reason why Consensus cannot be solved in completely asynchronous systems is
> the fact that, in such systems, **it is impossible to reliably distinguish a process that has
> crashed from one that is merely very slow.**»

Цена допущения названа там же: ◇P реализуем в частичной синхронности Dwork–Lynch–Stockmeyer,
включая слабейший вариант, где границы СУЩЕСТВУЮТ, но неизвестны и начинают действовать после
неизвестного момента стабилизации. Знать их не нужно; нужно, чтобы они существовали. `[A]`

**Слабейший детектор — Ω, и он выдаёт не свидетельство о смерти.**
Chandra–Hadzilacos–Toueg (JACM 43(4), 1996): всякий детектор, которым решается консенсус, не
слабее ◇W₀. Эквивалентная форма — Ω, оракул лидера: «*outputs, when queried, a process
identifier, such that, eventually, the same correct process identifier is output at all
correct processes*». Заметьте, чего Ω не обещает: **когда** это «eventually» наступит, — и
изнутри системы этот момент ненаблюдаем. Сервер лицензий никогда не может знать, что он
прошёл. `[A]` для теорем; `[B]` для точной формулировки Ω — до PDF CHT дойти не удалось
(ACM DL 403), формулировка взята из двух рецензированных первоисточников, её повторяющих.

**Аренда: Gray & Cheriton (SOSP 1989) — и асимметрия, о которой все забывают.** Аренда меняет
неограниченное ожидание («дождись ответа держателя») на ограниченное («дождись числа на
часах»), то есть **переводит проблему живости в проблему времени**. §5 называет цену дословно:

> «**Leases depend on well-behaved clocks.** In particular, a server clock that advances too
> quickly can cause errors because it may allow a write before the term of a lease held by a
> previous client has expired at that client. Similarly, if a client clock fails by advancing
> too slowly, it may continue using a lease which the server regards as having expired. The
> opposite errors — a slow server clock or fast client clock — do not result in
> inconsistencies, but do generate extra traffic.»

Для нас это конкретное правило проектирования: **небезопасное направление — НАШИ часы, идущие
быстрее клиентских**, потому что тогда мы переоткрываем место, которое контейнер ещё считает
своим. Ошибаться надо в сторону «освободить ПОЗЖЕ». `[A]` для механизма; `[C]` для
эмпирического «сбои часов реже отказов» — заявлено как обоснование, не измерено.

**Chubby (Burrows, OSDI 2006) — три вещи, каждая из которых у нас уже есть или должна быть.**

*(а) Секвенсер — фенсинг-токен за десять лет до термина.* Сначала точная формулировка нашей
же проблемы:

> «a process holding a lock L may issue a request R, but then fail. Another process may acquire
> L and perform some action before R arrives at its destination. If R later arrives, it may be
> acted on without the protection of L…» (§2.4)

Потом механизм — и, что важнее, его ЦЕНА:

> «It is costly to introduce sequence numbers into all the interactions in an existing complex
> system. Instead, Chubby provides a means by which sequence numbers can be introduced into
> only those interactions that make use of locks. At any time, a lock holder may request a
> **sequencer**… It contains the name of the lock, the mode in which it was acquired… and **the
> lock generation number**. The client passes the sequencer to servers (such as file servers)…
> **The recipient server is expected to test whether the sequencer is still valid and has the
> appropriate mode; if not, it should reject the request.** The validity of a sequencer can be
> checked… **against the most recent sequencer that the server has observed.**»

Последняя оговорка — подарок: ресурс может принуждать монотонность **вообще без связи со
службой блокировок**, просто помня наибольший виденный номер.

*(б) `lock-delay` — то, что мы называли остыванием, и признание автора, что это подпорка.*

> «If a client releases a lock in the normal way, it is immediately available for other clients
> to claim, as one would expect. However, if a lock becomes free because the holder has failed
> or become inaccessible, the lock server will prevent other clients from claiming the lock for
> a period called the lock-delay. Clients may specify any lock-delay up to some bound,
> **currently one minute; this limit prevents a faulty client from making a lock (and thus some
> resource) unavailable for an arbitrarily long time. While imperfect**, the lock-delay
> protects unmodified servers and clients from everyday problems caused by message delays and
> restarts.»

Асимметрия первой фразы — это в точности правило Б26quinquies, к которому пятый заход пришёл
своим путём: **добровольный уход доверяется мгновенно, выведенный — нет.** Chubby явно ставит
«держатель сказал» выше «мы заключили». Вторая фраза — приговор нашему сроку: потолок задержки
существует, чтобы НЕИСПРАВНЫЙ клиент не лишил себя ресурса надолго, и равен минуте.

*(в) Отказ закрыто при неуверенности, и второй эпох, который никто не цитирует.*

> «During this period, the client cannot be sure whether its lease has expired at the master.
> It does not tear down its session, but it **blocks all application calls on its API** to
> prevent the application from observing inconsistent data.» (§2.9)

> «It first picks a new client epoch number, which clients are required to present on every
> call. **The master rejects calls from clients using older epoch numbers**… This ensures that
> the new master will not respond to a very old packet that was sent to a previous master,
> **even one running on the same machine.**» (§2.9)

Последняя оговорка — прямо про нас: «жив ли этот хост» может дать ВЕРНЫЙ ответ и всё равно
быть НЕ ТЕМ вопросом. Личности недостаточно; поколения разделяет эпох. `[B]` для механизмов,
`[C]` для обоснований (минута, 12 с, 45 с — заявлены, не измерены).

**Фенсинг — Kleppmann (2016), и одно предложение, на котором держится вся рекомендация.**

> «**Note this requires the storage server to take an active role in checking tokens, and
> rejecting any writes on which the token has gone backwards.** But this is not particularly
> hard, once you know the trick. And provided that the lock service generates strictly
> monotonically increasing tokens, this makes the lock safe.»

Гарантия: при (i) строго монотонных токенах и (ii) ресурсе, который durable помнит наибольший
принятый, действие устаревшего держателя не вступает в силу — **независимо от длины паузы,
дрейфа часов и задержек сети.** Это свойство безопасности, переживающее произвольную
асинхронность, то есть именно то, чего аренда дать не может. Не-гарантия: фенсинг не мешает
пытаться и не защищает ничего, что ресурс не опосредует. `[B]` для поста как первоисточника
авторского аргумента; сам механизм `[A]` (тот же аргумент монотонного бюллетеня доказан в
Paxos). Антирез (antirez.com/news/101) спорит не с архитектурой, а с необходимостью
МОНОТОННОСТИ против простой уникальности; его собственное предложение (большой случайный токен
+ check-and-set) тоже требует проверки НА РЕСУРСЕ. Ни одна сторона не уступила.

**ZooKeeper, etcd, Consul — три независимых подтверждения одной и той же границы.**

| система | что гарантирует | что НЕ гарантирует, её собственными словами |
|---|---|---|
| ZooKeeper | «Session expiration is managed by the ZooKeeper cluster itself, not by the client»; zxid — тотальный порядок; условная запись по версии | «At this point **the client of the expired session is still disconnected** from the cluster, **it will not be notified of the session expiration** until/unless it is able to re-establish a connection» — исключённый узнаёт последним, по построению |
| etcd | revision как логические часы; `Txn` по `CreateRevision`/`ModRevision` | «**Actually, the lease mechanism itself doesn't guarantee mutual exclusion. Owning a lease cannot guarantee the owner holds a lock of the resource.**» · «**the resources must provide the version number validation mechanism**… The lock feature of etcd itself cannot be used for protecting external resources.» |
| Consul | инвалидация по пяти условиям; монотонный `LockIndex`; TTL — НИЖНЯЯ граница | «the contract of a TTL is that it represents **a lower bound for invalidation**; that is, Consul will not expire the session before the TTL is reached, **but it is allowed to delay the expiration past the TTL**» · про `lock-delay`: «**While not a bulletproof method**» |

И самая честная фраза из всех трёх документаций — про дилемму, а не про механизм (Consul):

> «This **removes the possibility of a false positive and trades liveness for safety.** You can
> be absolutely certain Consul will not release the lock even if the existing owner has failed.»

Настройки, покупающей обе стороны, нет, и HashiCorp это пишет. `[B]`

**Переформулировка, и она доказана, а не предложена.** van Renesse, Schiper & Schneider
(arXiv:1309.5671) показывают уточняющими отображениями, что ballot (Paxos), view (VR) и epoch
(Zab) — одно устройство под тремя именами, и что все три принуждают один инвариант:

> «This implies that **at any time at most one round is operational** and that wedged rounds can
> never become unwedged.» (§3.1)

Это и есть ответ на переформулированный вопрос: не «жив ли прежний», а «сколько может
действовать» — и в формулировке нет ни одного предиката живости. Подтверждения по отдельности:
Paxos P1ᵃ («An acceptor can accept a proposal numbered n iff it has not responded to a prepare
request having a number greater than n») плюс требование durable-памяти («an acceptor must
remember this information even if it fails and then restarts»); Raft §5.1 («Terms act as a
logical clock… **If a server receives a request with a stale term number, it rejects the
request**»); VR §4 («Replicas only process normal protocol messages containing a view-number
that matches the view-number they know»). И Raft §8 называет цену альтернативы вслух:

> «Alternatively, the leader could rely on the heartbeat mechanism to provide a form of lease,
> but **this would rely on timing for safety** (it assumes bounded clock skew).»

Онгаро и Оустерхаут отказываются от аренды ИМЕННО потому, что она переносит безопасность на
допущение о времени, и платят лишним раунд-трипом. `[A]`

**Эмпирика, которая решает спор про OOM (Ford et al., OSDI 2010, Google).**

> «**The vast majority of such unavailability events are transient and do not result in
> permanent data loss.** Figure 1 plots the CDF of node unavailability duration, showing that
> **less than 10% of events last longer than 15 minutes.** This data is gathered from tens of
> Google storage cells, each with 1000 to 7000 nodes, over a one year period.»

> «**We observe that initiating recovery after transient failures is inefficient**… For these
> reasons, GFS typically **waits 15 minutes** before commencing recovery of data on unavailable
> nodes.»

Два вывода, и оба наши. (i) «Перестал отвечать» в девяти случаях из десяти — не смерть;
детектор, действующий по первому молчанию, ошибается девять раз из десяти. (ii) Ответом Google
был **не лучший детектор, а задержка перед действием**. Когда детектор нельзя сделать верным,
действие делают поздним. `[A]` — измерено за год на десятках кластеров по 1000–7000 узлов.

### 4.2 Что на самом деле стоит в нашем дереве сегодня — и где протекает

Прошлое исследование разобрало пять заходов; шестой (Б26sexies) перенёс потолок с аренды на
ёмкость, и это изменило арифметику сильнее, чем где-либо записано. Ниже — то, что я прочитал в
коде на рабочем дереве, а не пересказ.

**Связывающая величина — больше не окно аренды.** Обслуживать без кванта нельзя
(`license.has_capacity` — одно условие `_consumed < _granted`, `metering-integrity.md` §4.6), а
квант выдаём мы. Значит `T_offline` — это не `ttl + grace = 72 ч`, а **резерв**:

```python
# licensing/store.py:1095
RESERVE_SECONDS = int(os.environ.get("PSEUDEX_RESERVE_SECONDS", str(48 * 3600)))
# :1582
reserve = min(max(int(rate * self.RESERVE_SECONDS), quantum), reserve_max)
```

`RESERVE_MAX` = {start 20 000, work 100 000, industrial 400 000, enterprise 8 000 000}
(`store.py:1117`). Комментарий рядом уже назвал цену часа страховки: **6 ч → 0.84 % худшей
погрешности счёта, 24 ч → 3.34 %, 48 ч → 6.68 %**, и объяснил, почему выбрано 48: «наша авария
не должна останавливать прод клиента». Всё верно — и из этого следует то, чего в комментарии
нет: **резерв и есть потолок обхода**, потому что это ровно тот объём, который любой процесс
может потратить, не спросив нас. Прошлое исследование мерило `T_offline` часами аренды и
получило множитель 216; в валюте ёмкости величина другая, ручка другая, и к числу инстансов
она отношения не имеет. `[A — код]` `[D — связывание моё]`

**Две вещи, которые нельзя развести, потому что они одна строка.** Счёт строится как
`billable = Σ clamp(acked, granted − Q − R, granted)` по `(org_id, pubkey)`
(`store.py::billable`, PK таблицы `meter` — `store.py:274`). Разберём два события:

| событие | что происходит в леджере | к счёту |
|---|---|---|
| **воркер стартовал и умер от OOM, ничего не обслужив** | §4.3 метода: `acquire()` сразу зовёт `_meter_once()`. `quantum_seq == 0` → резерв 0, квант = нижняя граница (200 на «старте»). `granted = 0 + 200 + 0 = 200`. Нижняя граница счёта `200 − 200 − 0 = 0` | **0** — перезапуск бесплатен |
| **оборот кольца: новый ключ → аренда → покупка → `/v1/release` → исчез** | ровно то же самое, число в число | **0** — и 200 запросов ёмкости, которые он унёс |

Это не две похожие ситуации. Это **одна строка арифметики, прочитанная с двух сторон**, и
именно поэтому шесть заходов не смогли их развести: в данных они не различаются. Владелец
назвал этот остаток точно («квант, купленный ДО релиза, неотличим от кванта честного
воркера»); здесь он локализован до одного выражения. `[A — код + `docs/metering-integrity.md`
§4.3]`

**Ограничитель частоты мимо кольца.** `server.py:934` отказывает «one grant per second», но
`metered_too_recently(org_id, pubkey, …)` ключуется ПАРОЙ. Кольцо чеканит новый `pubkey`
каждый оборот, поэтому этот потолок его не касается вовсе; темп кольца ограничен только ценой
аренды (2 034 351 байт, медиана 18.1 мс — замеры E5/E10 прошлого исследования). `[A — код]`

**Что шестой заход всё-таки закрыл, и это надо сказать.** `capacity_admission`
(`store.py:1436`) не пускает к ёмкости ключ, чьё место закрыто его же релизом, если чужие
места уже заняли весь потолок `instances_allowed × processes_allowed`; покупка после релиза
заводит аномалию (`release_echoes`). Пятый заход мерил 500 вооружённых процессов при
разрешённых 32 — этого больше нет. Дыра, которая осталась, УЖЕ, чем была: она не в числе
одновременно вооружённых, а в объёме, который каждый оборот уносит бесплатно.

**Удостоверение установки.** `instance_id` = `AUDIT.installation_id()` — `uuid4`, записанный в
таблицу `meta` тома (`pseudex/audit.py:136`, и докстрока там честно рассказывает, почему он
переехал в том: раньше `entrypoint.sh` чеканил его из `/dev/urandom` на каждом старте, и
клиент с 500k запросов после одного редеплоя получал счёт на миллион). Клиент может
переопределить его `PSEUDEX_INSTANCE_ID` (`service.py:125`) — это замер E7: **32 контейнера на
тарифе в один**. `docker compose down -v` рождает новую установку. `[A — код]`

**И принцип, который у нас уже записан — но только для офлайнового SKU.**
`docs/tz-offline-license.md` §6:

> «Наша сторона знает, сколько ключей названо: **это и есть потолок инстансов, честно
> посчитанный ПРИ ВЫДАЧЕ, а не в чужом контуре.**»

Там же — осознанный отказ от привязки к железу (MAC/серийник/`machine-id`) в пользу
`deployment.key` в томе, с честной оговоркой «клон тома = клон лицензии». **Онлайновый SKU
этого принципа не применяет: слот там не выдаётся, а выводится из того, что сказал клиент.**
Вся разница между шестью заходами и седьмым — в том, чтобы применить к аренде тот принцип,
который для офлайна уже сформулирован. `[A — документ проекта]`

### 4.3 Что делают вживую: никто не детектирует падение, и почти никто не принуждает счёт

Раскопка по ~21 серверному self-hosted-продукту и четырём системам плавающих десктопных
лицензий дала результат, которого я не ожидал и который меняет постановку задачи.

**Находка 1. Потолок ЧИСЛА принуждают шестеро из двадцати одного.**

Принуждают: Redis Enterprise (шарды — числа лежат прямо в лицензии, `shards_limit`,
`PUT /v1/license` → **406 «License violation»**); Grafana Enterprise в стандартном режиме
(активные пользователи); Veeam (инстансы, после двухполосного допуска); Atlassian DC
(пользователи, но как ДЕГРАДАЦИЯ); Oracle SE2 (16 потоков CPU); Splunk (ГБ/сутки, только ниже
100 ГБ/сутки и только после 45 предупреждений за 60 дней).

Не принуждают: HashiCorp (Vault/Consul/Nomad), Elastic (по числам), Neo4j, MongoDB, Confluent
(по числам), Camunda, Portainer, Sentry, GitLab (по умолчанию), Docker, Kong, Red Hat, Oracle
EE, Mattermost, NGINX Plus, n8n, CockroachDB. `[A]`

**Находка 2. Граница проходит по НАБЛЮДАЕМОСТИ, и договорная оговорка тем жёстче, чем слабее
техника.** Oracle, у которого единица наименее наблюдаема, имеет самый агрессивный аудит: 45
дней уведомления, **без ограничения частоты**, и право «running of Oracle data measurement
tools on Your servers». GitLab, у которого единица самая наблюдаемая, — самый узкий: только
финансовые записи, «only to verify the amounts payable». `[A]` Это прямая рекомендация для
нас: **чем точнее мы считаем, тем мягче может быть оферта** — и наоборот.

**Находка 3 — и это ответ на вопрос владельца про перезапуск. НИКТО НЕ ПЫТАЕТСЯ ОБНАРУЖИТЬ
ПАДЕНИЕ.** Все четыре системы плавающих лицензий делают одно и то же: интервал обновления,
молчание читается как отсутствие, срок называется в документации.

| вендор | интервал обновления | срок освобождения | добровольный уход |
|---|---|---|---|
| JetBrains License Vault | 10 мин | **20 мин** без обновления; «20 to 30 minutes from the moment the user's machine goes offline» | «Immediately» |
| Unity Licensing Server | `floatingLeaseRenewIntervalInMinutes` = **15 мин** | тогда же; отдельно `floatingLicenseExpirationInMinutes` = **8 ч** — срок жизни самого токена | — |
| Tableau | `REPORTINGFREQUENCYSECONDS` = 1 ч | аренда ATR по умолчанию **14 суток**, минимум 4 ч; для VDI рекомендуют 4–12 ч | возврат токена |
| 10Duke Enterprise | — | **мгновенно** | **cooldown**, чтобы «license hopping» не работал |

**Unity держит ДВА ЧАСА отдельно, и это стоит украсть:** короткий интервал переоткрытия
(15 мин) и долгая валидность самого токена (8 ч) — ровно наша пара «признак жизни» и «резерв»,
но названная явно.

**А 10Duke сформулировал наше правило Б26quinquies почти дословно, и в обе стороны:**

> «**If a lease expires without being released, the cooldown period is not applied, and the
> license becomes available immediately.**»
> «**If a license is requested from the same device using the same hardware fingerprint, the
> original end user can re-consume the license without interruption.** For example, if a user
> releases a license but attempts to consume it again on the same machine 15 minutes later, the
> request succeeds.»

То есть: падение освобождает МГНОВЕННО, а добровольный релиз получает остывание — чтобы
лицензия не прыгала между машинами. У Chubby асимметрия обратная (добровольный уход доверяется
мгновенно, выведенный — нет), потому что Chubby боится зомби, а 10Duke боится перепродажи
места. **Нам нужны обе половины, и именно их пятый заход и нащупал руками.** `[A]`

**Находка 4. Ближайший к нам по конструкции продукт — F5 NGINX Plus R33+, и он принуждает
ОТЧЁТ, а не счёт.** Self-hosted data-plane, подписка на инстансы, подписанный токен на диске,
обязательная отчётность вендору, документированное офлайн-реле:

> «The license: **Is tied to your subscription (not to individual instances).**»
> «Processing traffic requires: **A successful initial usage report.** If the F5 licensing
> endpoint does not receive the initial report, **NGINX Plus will not process traffic until the
> report is received.**»
> «**Ongoing usage reports, at least every 180 days.** If reporting stops, NGINX Plus keeps
> running but **stops processing traffic once 180 days have passed without a report.**»

Плюс переключатель `enforce_initial_report off` (превращает первое требование в 180-дневную
грацию), 90-дневная грация на просроченную лицензию, `usage_report interval=1h`, и реле
(NGINX Instance Manager) для закрытых контуров. **Число инстансов F5 узнаёт из отчётов,
помеченных UUID, и сводит КОММЕРЧЕСКИ.** `[A]`

Это важно для нас дважды. Во-первых, это независимое подтверждение нашей конструкции: право
обслуживать трафик выдаётся вендором непрерывно, и именно оно, а не счёт инстансов, является
рычагом. Во-вторых, это указание на масштаб: F5 считает приемлемым сроком **180 дней**, мы
держим 48 часов. Мы строже своего ближайшего аналога в 90 раз.

**Находка 5. Продуктов с оплатой ПО ЗАПРОСАМ для self-hosted не найдено ни одного.** Причина
структурная и её стоит записать: вендор не видит запросов, пока софт о них не доложит, — а
тогда единица на самом деле называется «доложенный объём», то есть модель Splunk.
`[A — отрицательный результат раскопки]`

**Находка 6. Двое вендоров ПРОДАЮТ режим принуждения как выбор покупателя.** Grafana: жёсткий
потолок — «if you prefer a predictable bill»; оплата по факту — «when it's critical that no
user ever be prevented from logging in». ISL Online прямым текстом: **Hard Limit** — «a
technical limitation of the maximum number of users»; **Soft Limit** — «technically unlimited.
A monthly service fee will be calculated based on the usage report.» Один и тот же софт.
`[A]` Для нас это прямо применимо: если часть клиентов хочет предсказуемого счёта, а часть —
чтобы их никогда не остановили, это две строки прайса, а не один компромисс.

**Находка 7. Кто деградирует — деградирует ФУНКЦИЮ, и ни один не гасит продукт.** Splunk
блокирует поиск, но никогда индексацию. Bitbucket блокирует push, но не clone. Confluence
переходит в read-only. Veeam прекращает новые бэкапы, но восстановление работает даже за
грацией. Nomad оставляет чтение, отказывает записи. Grafana **первым делом выключает сам
потолок пользователей**. CockroachDB душит до 5 одновременных SQL-транзакций. `[A]`

**И ладдер Veeam — лучший найденный, потому что он платит за связь:** при включённом
автообновлении лицензии полосы «<10 % — тихо», «10–20 % — предупреждение раз в неделю»,
«>20 % — не обрабатывается только избыток»; при выключенном те же полосы идут по 5 / 5–10 /
>10 %. **Оставаться на связи удваивает допуск.** `[A]`

**Находка 8. Юридическая оговорка, которой у нас может не быть, а стоит.** Elastic License 2.0,
Limitations §2:

> «**You may not move, change, disable, or circumvent the license key functionality in the
> software, and you may not remove or obscure any functionality in the software that is
> protected by the license key.**»

Она превращает снятие проверки из нарушения договора (убытки по ожиданию) в **прекращение
авторской лицензии**, то есть в нарушение исключительного права. Каждый вендор в раскопке,
который ОТГРУЖАЕТ КЛЮЧ и при этом продолжает работать при сбое, имеет такую оговорку. У нас
оферта (раздел 5bis) закрывает самоотчёт и проверку, но это другая норма. `[A]`

**Находка 9, структурная, и она ровно про нашу конструкцию.** Bitbucket может ограничить число
одновременных сборок на ЖЕЛЕЗЕ КЛИЕНТА только потому, что диспетчер — облако Atlassian; раннер
тянет работу у вендора. JetBrains, Unity, Tableau и 10Duke могут ограничить места только
потому, что аренду выдаёт сервер. Сформулировано раскопкой так:

> «Concurrency on customer hardware is enforceable only if the vendor hands out the slot.»

Это независимое подтверждение П1 из §4.5 и объяснение, почему шесть заходов буксовали:
`instance_id` **выбирает клиент**, то есть слот у нас не выдаётся, а выводится. `[B — вывод
раскопки из совокупности первоисточников]`

**Находка 10 — и это ПРЯМОЙ ПРЕДШЕСТВЕННИК нашей конструкции. Reprise RLM: `min_checkout`.**

> «`min_checkout` specifies that a license is to be “held” checked-out by the license server
> after the application performs a check-in call or exits, **only if the license did not remain
> checked out for the minimum interval specified by n**. … The license will remain checked-out
> such that the total checkout time is n seconds.»
> «`hold` is typically used in the case of licenses that have a very short duty-cycle, **in
> order to provide a “fairer” measure of concurrent usage**.» `[A]`

Это **минимальная оплачиваемая занятость**: процесс, проживший две секунды, всё равно стоит `n`
секунд места. **Кольцо не даёт ничего — и это ровно то, чего добивается наследование леджера
слота (§4.7, П4), только в другой валюте: у RLM минимум в СЕКУНДАХ, у нас — в ЗАПРОСАХ.**
Идея не новая, и это хорошо: у неё есть двадцатилетняя проверка в продакшене.

**Находка 11. Овердрафт отгружают пятеро из одиннадцати, и это штатная функция, а не поблажка.**
FlexNet `OVERDRAFT=n` («**This allows your users to not be denied service when in a “temporary
overdraft” state.** Usage above the license limit is reported by the FlexNet Manager reporting
tool»); RLM `soft_limit` (выдаётся, но помечается `RLM_EL_OVERSOFT`); LM-X `SOFTLIMIT`; Keygen
`overageStrategy` («Giving a license an overage allowance may be beneficial in environments
where **rolling restarts of the application are common**»); Zentitle2 Overdraft Tracker —
причём в его опубликованной лестнице распределения овердрафт стоит на рангах 1 и 0, то есть
выдаётся ПОСЛЕДНИМ, после переиспользования. `[A]`

**И у Zentitle2 первым рангом стоит ровно то, что владелец просит:**

> «**Rank 4 — Highest Priority: Existing Users** • Users who already have an active seat keep it
> when refreshing • **Prevents disruption to ongoing work**» `[A]`

**Находка 12. Против карусели у старой гвардии есть три примитива, и НИ ОДНОГО у современных
SaaS-вендоров.** (а) минимальная занятость — RLM `min_checkout`, FlexNet `LINGER`, CodeMeter
Linger Time; (б) лимит на сам рычаг принудительного отъёма — FlexNet ошибка **−64** «lmremove
request before the minimum lmremove interval», RLM `min_remove` = 120 с, LM-X
`MIN_USER_REMOVE_TIME` = 120 с, **и администратор может его только ПОВЫСИТЬ**; (в) остывание
повторной грации — LM-X: «**To prevent fraud and over-licensing, LM-X does not allow the user to
obtain a new grace license for 7 days after the expiration of the previously activated grace
license.**» `[A]/[C]`

Wibu называет цель своего Linger Time прямым текстом — и это единственный вендор, который
называет перезапуск как объект управления: «This allows you to implement license models which
are to **time-control the restart of protected applications**», причём программирование этого
параметра «requires a Firm Security Box», то есть клиент его не снимет. `[A]` **Нам эта
формулировка нужна как предупреждение, а не как образец: мы хотим противоположного —
перезапуск не контролировать, а сделать бесплатным.**

**Находка 13. Единственное опубликованное обоснование минимального интервала — бюджет
транзакций сервера, с замерами.** Reprise:

> «In our testing (non-shared licenses on a 2007-vintage server machine), the license server is
> capable of processing ~100 transactions/second with a load of 10k clients… **If you tried to
> send heartbeats every 10 minutes, however, the server could do little more than process
> heartbeats (at 42/second) from the 25k clients.**» `[C]`

И Cryptlex формулирует нашу дилемму одним предложением, лучше, чем она сформулирована у нас:

> «**The lease duration is a tradeoff. A long lease holds a seat for its full duration after an
> app crashes, so stale seats come back slowly. A short lease reclaims them sooner, but forces
> more frequent syncs and a higher volume of API requests.**» `[C]`

Это ровно §5.4 прошлого исследования (лиза 2 034 351 байт против отчёта 472 байта), только
вычисленное вендором для себя и опубликованное.

**Находка 14. «Тот же клиент забирает своё место» документируют ДЕВЯТЬ вендоров из
одиннадцати.** Это норма, а не экзотика, и у неё три формы:

* **идемпотентный захват по личности** — Keygen Relay: «**If a lease already exists for the
  node, the lease is extended** by `--ttl` and the server will return `202 Accepted`». TTL по
  умолчанию 60 с, интервал выбраковки 15 с → худший случай возврата действительно мёртвого узла
  **75 секунд**. `[A]`
* **схлопывание личностей при чекауте** — FlexNet `DUP_GROUP`, RLM `share=`, LM-X `SHARE=HOST`,
  Cryptlex `leasingStrategy: Per-Machine` («Each machine will only consume a single floating
  license/activation, **irrespective of the number of instances (processes)**»), и — важнее
  всего — **Sentinel LDK `Count Each` со значением по умолчанию `Station`**: «All login requests
  from the same machine are counted as a single instance. **(Default)**» `[A]` **То есть у
  Thales перезапуск бесплатен ИЗ КОРОБКИ, потому что единицей счёта является машина, а не
  процесс.** Это в точности наш вывод §4.4 про единицу.
* **клиентская жатва своих же сирот** — Sentinel RMS `VLScleanupIssuedKeys`, API, чья
  документированная цель — ровно наш сценарий: «The licensed application gets terminated
  abnormally… **The licensed application is restarted. It sends a request for the same feature,
  while the previous session is still active.** This scenario can cause: • Feature/license
  overuse • Denial of license… To avoid such scenarios, the licensed application can use this
  API… to clean previously issued keys or active sessions.» `[A]`

**Находка 15. Как выглядит «падение» у эталона категории, и почему это не наша модель.**
FlexNet держит постоянное TCP-соединение, и нормальный выход освобождает место мгновенно
закрытием сокета: «**This is only needed when a client node crashes, since that's the only
condition where a license is not automatically freed.**» `[A]` Когда FIN не приходит —
жёсткое выключение, разрыв сети, `kill -9` машины — работает запасной путь, **TCP-таймаут по
умолчанию 7200 с (два часа)**, а минимум `TIMEOUTALL`, вкомпилированный вендором, равен 900 с
(и IBM Rational подняла свой до 7200 с). `[A]/[B]`

**У нас такого соединения нет и быть не может** — сайдкар соединения не держит, — поэтому вся
категория «освобождение по закрытию сокета» нам недоступна, а её запасной путь (два часа) мы бы
и не приняли. Это объясняет, почему копировать FlexNet бессмысленно, и почему аналогом является
не он, а NGINX Plus (находка 4).

**И честная отрицательная находка.** LM-X делает свой таймаут клиента **константой времени
компиляции ISV**: «The vendor file `lmx_server_conf.c` customizes the behavior of the LM-X
license server at build time. **The file's settings and callbacks cannot be changed after the
vendor library has been compiled.**», `GetClientTimeout` по умолчанию 5 минут, и ни в одном из
двух форматов конфигурации сервера такой настройки нет. `[A]` Клиент не может ни удлинить его,
чтобы сидеть на месте, ни укоротить, чтобы возвращаться быстрее. **Это единственный найденный
вендор, который сделал срок недоступным ОБЕИМ сторонам, и это стоит держать в уме как способ
закрыть спор о числе раз и навсегда.**

### 4.4 Единица счёта: может, мы считаем не то

Сводная оценка по осям, которые задал владелец. Источники — лицензионные соглашения и
документация вендоров (§4.3), поведение при перезапуске — их же документированные сроки.

| единица | вендор-первоисточник | наблюдаема нашим сервером? | подделывается рутом? | понятна покупателю? | поведение при перезапуске / OOM |
|---|---|---|---|---|---|
| **процессы / инстансы** | ISL Online (hard/soft) `[A]`, Veeam VUL `[A]`, Bitbucket runners `[B]` | только если каждый процесс отчитывается, ИЛИ вендор сам раздаёт работу | **тривиально**: рут владеет и числом процессов, и отчётчиком | хорошо — ложится на мощность | **худшая из всех.** Падение оставляет фантомное место; перезапущенный после OOM контейнер выглядит новым инстансом |
| **узлы / хосты** | Consul `billable.nodes`, Portainer EULA, Elastic Billable Nodes `[A]` | только по отчёту | да | хорошо | Elastic в K8s: автоскейлинг умножает обязательство без человека в цикле. Oracle: **сам факт затягивания образа на узел** создаёт обязательство |
| **ядра / vCPU** | Oracle core factor, Red Hat vCPU `[A]` | нет — нужен аудит или инструмент замера | не проверяется в рантайме | **плохо**: вендор правит коэффициент односторонне | стабильно, но растворяется под виртуализацией — весь спор Oracle/VMware |
| **сокеты** | Red Hat «Socket-pair — up to two Sockets» `[A]` | нет | — | средне; односокетные машины переплачивают по построению | стабильно |
| **запросы** | **не найдено ни одного для self-hosted** | только по самоотчёту — тогда это «доложенный объём» | да | хорошо | — |
| **объём данных** | Splunk ГБ/сутки `[A]` | только по отчёту | да | очень хорошо | необратимо после индексации; **принуждение срабатывает во время инцидента, ради которого продукт и куплен** — Splunk по этой причине убирал его в 6.5–8.0 |
| **активные / именованные пользователи** | Grafana (30-дневное скользящее окно), GitLab billable users `[A]` | да — ежедневная выгрузка хешей (Grafana) или CSV (GitLab) | да | **отлично** | **лучшее из всех.** Окно само переоткрывает место; аренды, которая могла бы застрять, не существует |
| **«клиенты»** (HashiCorp) | «Anything that connects and authenticates to Vault» `[A]` | только по отчёту | да | средне — известны трудности сайзинга | **намеренно устойчива к перезапуску**: «counted once, no matter how many times it has been active… unlimited access… for the remainder of the month» |
| **шарды / объекты мощности** | Redis `shards_limit` `[A]` | да — число лежит в лицензии И в Prometheus | только сломав ключ | хорошо | состояние кластера, не аренда — перезапуск безопасен |
| **плавающие места** | JetBrains, Unity, Tableau, 10Duke `[A]` | да — аренду выдаёт сервер | нет, если выдаёт сервер | хорошо | **решено, и всегда одинаково**: интервал обновления, молчание = отсутствие. Никто не пытается детектировать падение |
| **ЁМКОСТЬ (наш квант)** | — *аналогов в self-hosted не найдено; ближайшее — NGINX Plus, где принуждается отчёт* | **да, идеально: это НАША запись о выдаче** | **нет**: занизить нельзя, завысить — значит поднять свой счёт | хорошо: «объём» | **лучшее вместе с активными пользователями**, и по той же причине: холодный старт стоит ноль (§4.2) |

**Прямой ответ на «может, отказаться от счёта инстансов».** Да — **от ПРИНУЖДЕНИЯ по нему**, и
нет — от самого счёта. Три довода, каждый из первоисточника:

1. **Пятнадцать вендоров из двадцати одного уже так и делают** (§4.3, находка 1). Это не
   смелость, это норма отрасли.
2. **Наша собственная единица ёмкости — лучшая в таблице по трём осям из пяти** и
   единственная, которая наблюдаема нами БЕЗ доверия к клиенту: число выданных грантов — наша
   запись, занизить её невозможно, а завысить невыгодно (`server.py:929`: «Инфляция ёмкости
   атакующему бесполезна — она только поднимает его же счёт»).
3. **Единица «одновременные процессы» имеет худшее поведение при перезапуске из всех
   существующих**, и это не наша неудача, а свойство единицы: «a crash leaves a phantom slot,
   and an OOM-restarted container looks like a new instance». Шесть заходов боролись со
   свойством единицы, а не с ошибкой реализации.

**Цена перехода, честно.** Число контейнеров остаётся в тарифе — как УПАКОВКА (по нему
считается цена) и как наблюдаемое (мы его знаем точнее прежнего: слот и эпох чеканим мы). Оно
перестаёт быть тем, по чему приходит 409. Что теряется: клиент на тарифе в один контейнер
физически сможет поднять три. Что он при этом получит — см. §4.5: три поколения, делящие один
баланс слота и фенсящие друг друга, то есть суммарно один контейнер, размазанный по трём
процессам. Потолок принуждается, просто не отказом. Grafana и ISL Online показывают, что это
ещё и можно продать как выбор режима.

### 4.5 Перезапуск и OOM: требование владельца не «мягкость», а вынужденность платформы

Здесь раскопка дала результат, который переворачивает постановку. «Не наказывать за
перезапуск» — не наша доброта, а **вынужденное следствие документированных поведений
платформы по умолчанию.**

**Три механизма гарантируют, что безупречный клиент периодически держит БОЛЬШЕ контейнеров,
чем купил.**

1. **`maxSurge` в Kubernetes, и он хуже, чем кажется, именно на маленьких деплойментах.**
   `maxSurge` по умолчанию 25 % и округляется ВВЕРХ; `maxUnavailable` тоже 25 %, но округляется
   ВНИЗ. Значит при `replicas ≤ 3` `maxUnavailable` даёт **ноль**, и Kubernetes ОБЯЗАН поднять
   новый под раньше, чем погасит старый:

   | replicas | maxUnavailable (вниз) | maxSurge (вверх) | одновременно | превышение |
   |---|---|---|---|---|
   | **1** | **0** | 1 | **2** | **+100 %** |
   | **2** | **0** | 1 | **3** | **+50 %** |
   | 3 | 0 | 1 | 4 | +33 % |

   **Однорепличный деплоймент удваивается при КАЖДОМ обновлении, по умолчанию, и обойти это
   можно только явно выставив `maxUnavailable: 1`.** И документация Kubernetes добавляет, что
   реальное число ещё выше: «Kubernetes doesn't count terminating Pods when calculating the
   number of `availableReplicas`… **you might notice that there are more Pods than expected
   during a rollout, and that the total resources consumed by the Deployment is more than
   `replicas + maxSurge`** until the `terminationGracePeriodSeconds` of the terminating Pods
   expires.» `[A]`
2. **`terminationGracePeriodSeconds` = 30 с по умолчанию** — старый под всё это время работает
   и держит аренду. `[A]`
3. **Узел недоступен, но жив.** Обнаружение `--node-monitor-grace-period` = 50 с плюс
   `tolerationSeconds = 300` — ≈350 с до появления замены; а если узел просто отрезан сетью,
   старый контейнер работает и арендует **неограниченно долго**: «Immediate deletion does not
   wait for confirmation that the running resource has been terminated. **The resource may
   continue to run on the cluster indefinitely.**» `[A]`

**И два механизма гарантируют, что клиент НЕ МОЖЕТ попрощаться.**

* **OOM-килл — это SIGKILL.** Ни сигнала, ни обработчика, ни единого шанса что-либо
  освободить. Kubernetes: «**Unlike pod eviction, if a container is OOM killed, the kubelet can
  restart it based on its `restartPolicy`**», репортуется как `exitCode: 137, reason:
  OOMKilled`. `[A]`
* **Graceful node shutdown по умолчанию ВЫКЛЮЧЕН**: «by default, both configuration options…
  are **set to zero, thus not activating the graceful node shutdown functionality**». Обычная
  перезагрузка узла не даёт контейнерам корректного выхода. `[A]`

**Отсюда — приговор одному из правил нашего пятого захода.** Б26quinquies установил: место,
освобождённое ЧЕСТНЫМ `/v1/release`, доступно немедленно; **молчание место не освобождает до
конца окна аренды**. Это правильное правило для `docker stop`. Но **OOM — это ровно тот путь
выхода, на котором `/v1/release` невозможен по построению**, а значит на нём действует вторая
половина правила: место держится до конца окна. **Путь, который владелец назвал главным,
попадает в худшую ветку нашей же конструкции.** Сформулировано раскопкой одной фразой: «*Any
licensing design that depends on the client saying goodbye is broken on exactly the exit path
the owner cares most about.*» `[A — из документации платформ]` `[D — приложение к нашему коду
моё]`

**Темп, который увидит наш сервер, и разница в три тысячи раз.**

| платформа | задержка перезапуска | сброс счётчика |
|---|---|---|
| **Docker** | 100 мс → 200 → 400 … потолок **60 с** (`maxRestartTimeout = 1 * time.Minute`, `moby/daemon/internal/restartmanager`) | после **10 СЕКУНД** непрерывной работы |
| **Kubernetes** | 10 с → 20 → 40 … потолок **300 с** | после **10 МИНУТ** чистой работы |

Контейнер, падающий от OOM раз в пять минут, для Docker — здоровый контейнер, стартующий через
100 мс каждый раз; для Kubernetes — крэшлупер, который дошёл до потолка 300 с и там остался.
**Одна и та же нагрузка, ~3000× разница в темпе обращений к нашему серверу.** Планировать
ёмкость лицензионного сервера надо по числу Docker. `[A — документация + исходники обоих]`

**И ни Docker, ни Kubernetes НЕ добавляют джиттер к задержке перезапуска** (в kubelet
`NewBackOff(...)` → `maxJitterFactor = 0`; у Docker — детерминированный таймер). Значит стадо,
упавшее по общей причине — плохой конфиг, изменение лимита памяти, `apt upgrade docker-ce`, —
возвращается **синхронно**, и никакими указаниями клиенту первую волну не размазать. Перезапуск
демона Docker вообще поднимает все контейнеры **параллельно**, без бэкоффа и без джиттера
(семафор `128 × NumCPU`). `[A — исходники]`

Отсюда два проектных требования, которые не вытекают ни из чего другого:

* **сервер лицензий обязан переживать синхронную первую волну**, и сброшенный им запрос аренды
  обязан стоить клиенту НОЛЬ — платформа просто перезапустит контейнер и попробует снова;
* **ладдер 402/403/426 не должен быть достижим контейнером, который просто быстро
  перезапускается.** Сегодня 409 `instance_limit` минует grace (`_ANSWER_CODES`) — и это ровно
  тот отказ, в который упирается крэшлупер.

**Приём, который стоит украсть у Nomad — «мы только что перезапустились, поэтому никого не
судим».** Nomad: TTL = `<число клиентов> / max_heartbeats_per_second`, «**A random factor up to
2x is added to the base TTL to prevent the thundering herd problem**», плюс
`failover_heartbeat_ttl` = 5 мин — после выборов лидера **всем** клиентам даётся расширенное
окно. Kafka поднял `group.max.session.timeout.ms` до 30 минут по той же причине. `[A]`
Переведено на нас: **после перезапуска лицензионного сервера окна расширяются для всего парка,
а не парк массово объявляется мёртвым.**

**И прямое вендорское указание — единственное найденное по нашей теме.** Keygen.sh,
«Floating licenses»:

> «When licensing cloud applications where **rolling deployments are common, which may cause
> licenses to temporarily exceed their node limit**, we recommend **allowing machine overages**
> (i.e. setting an overage strategy on the policy to something like **`ALLOW_2X_OVERAGE`**).
> **Rather than deny new node activations**, the license will temporarily become invalid…
> License validations during the overage will return validation code `TOO_MANY_MACHINES`, which
> can be uniquely handled in your application code.»

То есть: **во время раскатки не отказывать, а отвечать различимым кодом.** «Различимо и
обслуживает» лучше, чем «корректно и сломано». `[B — один вендор]`

**Но у Keygen же — внутреннее противоречие, и оно показывает, что мы можем лучше.** Они
рекомендуют для контейнеров «generating a **secure random UUID as a fingerprint each time the
application boots**», то есть делают каждый перезапуск НОВОЙ машиной, — и затем вынуждены
спасать себя выбраковкой по пульсу (по умолчанию 10 минут) и двукратным овердрафтом. Это
**противоположность** KIP-345 (стабильный `group.instance.id`, мгновенный перехват) и строго
хуже. У нас идентичность есть и переживает перезапуск — это смонтированный том. `[B]`

**Kafka: обе половины требования владельца, реализованные и нормативно описанные.**

*Перехват без таймаута* — KIP-98: «**Bumps up the epoch of the PID, so that the any previous
zombie instance of the producer is fenced off and cannot move forward with its transaction.**»
Никакого срока ожидания перед перехватом не требуется. Отфенсенный получает
`ProducerFencedException` — фатально.

*Перезапуск, который не стоит ничего* — KIP-345, статическое членство, существующее ровно ради
нашего требования: «one process restart will trigger one rebalance» → «broker will maintain an
in-memory mapping of `{group.instance.id → member.id}`… **When receiving a known member's
rejoin request, broker will return the cached assignment back to the member, without doing any
rebalance.**» И — критически — **статический член НЕ шлёт прощания**: «consumer with
`group.instance.id` set will **not send leave group request** when they go offline». Идея
названа авторами прямо: «**prioritizing “state persistence” over “liveness”**». `[A]`

Цена, названная самим KIP-98: «we cannot prevent a malicious producer from hijacking the PID of
another producer… This would allow the attacker to… **fence the authorized producer by forcing
an epoch bump**». Внутри одного клиента это его собственная нога; наружу не ведёт. Kafka
отвечает на это громкой ошибкой `FENCED_INSTANCE_ID`: «The client should immediately fail
itself to inform end user that there is a configuration bug.» **Копировать надо и это:
громкий, названный, исполнимый отказ лучше тихого недосчёта.**

### 4.6 Удостоверение установки: правильный вопрос не «что нельзя подделать», а «что нельзя сбросить случайно»

Конструкция §4.7 требует личности, которая переживает перезапуск и которую клиент не выбирает
сам. Раскопка по спецификациям, ядру, исходникам и пяти лицензионным SDK дала один
переформулирующий вывод и одну неожиданную находку для нашего рынка.

**Переформулировка, и она важнее всей таблицы.** Неподделываемого рутом идентификатора не
существует — это уже записано в проекте как теорема про RAM. Полезный вопрос другой:
**какой идентификатор нельзя сбросить СЛУЧАЙНО, так чтобы для сброса потребовалось намеренное,
видимое, атрибутируемое действие?** `docker compose down -v` — рутинная команда, а не атака, и
наша сегодняшняя личность ломается именно ею. `[D — формулировка раскопки, принимаю]`

**Мы не совершили ошибки, которой другие избежали; мы упёрлись в стену, в которую упираются
все.** Cryptlex документирует наш дефект нашими же словами:

> «**Containers and virtual machines can make device fingerprinting unreliable, so
> fingerprint-based node-locked licensing is a poor fit for apps deployed in them.**»
> «For containers, **persist the activation data across container restarts by mounting a
> volume**… **Without a mounted volume, every new container starts with no activation data, so
> it activates again and consumes another activation from the license. A deployment that
> recreates containers regularly will exhaust its allowed activations, which is the most common
> way container licensing goes wrong.**» `[B]`

Их средство — то же, что у нас (том), с той же дырой. Архивная версия той же страницы
формулировала резче: «**This makes node-locked licensing almost useless in case of apps running
inside Docker.**» `[C — архив]`

**И вывод, который прямо поддерживает §4.4:** двое из пяти вендоров лицензирования **перестают
чинить личность и подменяют её СЧИТАЕМЫМ ПАРАЛЛЕЛИЗМОМ**. Параллелизм принуждается против рута
(можно отказаться обслуживать N+1-й живой процесс), а личность — нет. `[B — вывод раскопки]`

**Что измерено, а не пересказано.**

| идентификатор | в Docker | переживает `down -v` | переживает легальную миграцию | подделывается рутом | проверяемо нами криптографически |
|---|---|---|---|---|---|
| наш `installation_id` (uuid4 в `audit.db`) | да | **НЕТ — это и есть дефект** | да | да, плюс `PSEUDEX_INSTANCE_ID` перебивает | нет |
| `/etc/machine-id` | **обычно отсутствует или нулевой** (измерено: `debian:12`, `alpine`, `python:slim` — нет файла; `ubuntu:24.04`, `ubi9` — файл нулевой длины) | да (не в томе) | нет | да — обычный файл | нет |
| DMI `product_uuid` | **НЕТ** — `/sys/class/dmi` отсутствует даже под `--privileged`; на ARM `/sys/firmware/` пуст вовсе | — | нет | да (на ВМ его задаёт хост в XML домена) | нет |
| MAC | да, но **перегенерируется при каждом старте** (измерено: `86:15:…` → `f6:18:…` после `docker restart`) | да | нет | да | нет |
| `/proc/self/cgroup` | **`0::/` — мёртв под cgroup v2** (moby принудительно разворачивает cgroup namespace) | — | — | да | нет |
| host `boot_id` | да, но это загрузка **ХОСТА**, общая для всех контейнеров на машине | да | нет (умирает при ребуте хоста) | не через `-v` (runc отказывается монтировать внутрь `/proc`) | нет |
| **bind-mount хостового файла** | да | **ДА — `-v` его не трогает** | нет | да | нет |
| K8s `kube-system` namespace UID | только K8s | да | нет (пересборка кластера = новый) | **выбрать нельзя**, но значение в транзите контролируется атакующим | нет |
| **подписанный identity-документ облака** | да | да | нет | подпись — нет; транспорт — да; **повтор — да** | **да** |
| **номер слота, выданный нами** (§4.7) | да | **да** | **да** | **нет** | **да, по определению** |

`[A-obs — замеры раскопки на Docker 29.4.0, cgroup v2, aarch64]`

**Попутно опровергнут распространённый фольклор:** «контейнеры наследуют `machine-id`,
зашитый в образ». Пять расхожих базовых образов измерены — файла либо нет, либо он нулевой
длины, ровно как предписывает `machine-id(5)`: «For operating system images which are created
once and used on multiple machines, for example for containers or in the cloud,
`/etc/machine-id` should be either missing or an empty file». Утверждение верно только для
плохо собранных образов. `[A-obs + A — man-страница]` И отдельно — правило, которое мы
нарушили бы, если бы вообще его читали: «**must not be exposed in untrusted environments, in
particular on the network… the machine ID or any part of it must not be used directly.
Instead the machine ID should be hashed with a cryptographic, keyed hash function**». `[A]`

**Находка, которой я не ожидал и которая касается ровно нашего рынка: у Yandex Cloud ЕСТЬ
подписанный идентификационный документ инстанса.** Эндпоинты
`instance/vendor/identity/{document,base64,dsa,rsa}`; документ несёт `instanceId`, `imageId`,
`productIds`, `createdAt`; сертификаты для проверки **опубликованы в документации**:

> «Сервис метаданных виртуальной машины кроме самого идентификационного документа предоставляет
> его криптографические подписи. Вы можете использовать эти подписи для проверки происхождения,
> подлинности и целостности документа.» `[B]`

Сертификаты декодированы раскопкой: три PEM, самоподписанные корни с ПУСТЫМИ subject/issuer DN,
RSA-2048 и DSA-2048, `notAfter 2033-06-04` — значит пинить придётся по отпечатку ключа, проверка
по имени невозможна. Поле `productIds` несёт идентификаторы Маркетплейса — сильное свидетельство
того, что механизм строился ровно под наш сценарий. `[A-obs]`

**И его потолок, названный в трёх местах.** (1) **Нонса нет** — грепы по документации на
`nonce|challenge|audience|expir|одноразов` дали ноль: документ статичен и повторяется до 2033
года. (2) **Клиент выключает IMDS одним флагом** (`gce-http-endpoint=disabled` → 400). (3) Даже
там, где нонс есть (Azure), его бьёт живой релей с одной честно арендованной ВМ. Потолок
механизма: «такой облачный инстанс существует и только что ответил» — и **никогда** «процесс,
который с вами говорит, находится на нём». `[B]`

**VK Cloud, Selectel, Timeweb — первоисточника не найдено `[D]`**, и у этого есть структурная
причина: апстрим OpenStack не имеет примитива подписанных метаданных, а его EC2-совместимый API
прибит к версии 2009-04-04, которая предшествует instance identity document. `[B]`

**TPM: выход закрыт, и теперь это можно сказать точно.** (1) TPM 2.0 Part 1 §9.4.3.4: «**Unless
the EK is certified by a trusted entity, its trust and privacy properties are no different from
any other asymmetric key that can be generated by pure software methods.**» `[A]` (2) TCG
«Keys for Device Identity»: «**The EK and EK certificate identify a TPM, while a DevID
certificate identifies a device**», и тот же документ выводит виртуальные платформы из своей
области. `[A]` (3) Любой может изготовить TPM: swtpm поставляет «tools for… **simulating the
manufacturing of a TPM by creating a TPM's EK and platform certificates**». `[A]` (4) Keylime:
«**There is no certification programme for virtual TPMs (vTPM). Because of this, in a cloud
environment, you typically have no assurance beyond the cloud service provider's word**» и
«**The vTPMs provided by most hypervisors today no longer have a chain of trust rooted in
hardware.**» `[A]` (5) И приговор от вендора с наибольшими возможностями на земле — Microsoft
Autopilot: «**Virtual machines can't attest, including the following, even if they use
vTPMs.**» `[B]` Наш субстрат — виртуальные машины. **Единственное исключение, где удалённый
вендор может проверить аппаратно-укоренённое утверждение без учётных данных клиента, — AMD
SEV-SNP (корень AMD KDS публично доступен, проверено живьём); по SEV-SNP на российских облаках
первоисточника не найдено `[D]`.**

**Отсюда — что делать с личностью, три шага по возрастанию цены.**

1. **Bind-mount якоря личности вместо именованного тома.** Измерено: `down -v` удаляет
   именованные и анонимные тома, но bind-mount не трогает. Это **нулевая криптографическая
   цена** и превращает случайный сброс в намеренный. Против рута не даёт ничего, и подавать это
   надо именно так.
2. **Ключевая пара установки, заведённая при первой аренде и подписывающая каждый последующий
   запрос.** Это уже выбрано для офлайн-SKU (`deployment.key`, `tz-offline-license.md` §6);
   делает скопированный том инертным против НЕ-рута и ложится в существующий цикл лизы.
3. **Подписанный документ облака там, где он есть — для нашего рынка это Yandex Cloud в первую
   очередь — с бухгалтерией TOFU**, и второй инстанс, предъявивший ту же личность, **поднимает
   аномалию, а не убивает контейнер**. Именно так поступает SPIRE со своими облачными
   аттестаторами: «the `aws_iid` node attestor implements **Trust On First Use (or TOFU)
   semantics. For any given node, attestation may occur only once.**» `[A]`

**И попутный сигнал, которого мы не используем.** Хостовый `boot_id` (`/proc/sys/kernel/random/
boot_id`) как ЛИЧНОСТЬ бесполезен — он общий для всех контейнеров на машине, — но именно
поэтому он является **признаком совместного размещения**: сколько наших контейнеров работает на
одной физической/виртуальной машине. Это ровно тот сигнал, которого не хватало при замере E7
(32 контейнера под одним `PSEUDEX_INSTANCE_ID`). И runc отказывается монтировать поверх него
(«cannot be mounted because it is inside /proc»), то есть дешёвая подделка через `-v` не
работает. `[A-obs]`

**Главное про SPIRE, чтобы не строить на нём иллюзий.** Самый продуманный в отрасли ответ на
идентичность рабочих нагрузок ставит рут-хостильного клиента **вне своей модели угроз**: «it is
also assumed that **the hardware on which SPIRE components run, as well as its operators, are
trustworthy**» и «**If an agent is compromised, the attacker will be able to access any identity
that the respective agent is authorized to manage.**» `[A]` Брать SPIRE ради нашей задачи
означало бы взять систему, которая нашего противника не рассматривает.

### 4.7 Конструкция: леджер на СЛОТЕ, эпох на поколении, наследование вместо покупки

Ниже — не седьмая заплатка. Из системы уходит целый слой (детектор жизни), и вместе с ним
уходит вопрос, на который нет ответа.

**Три правила.**

**П1. Слот выдаём мы, а не выводим из того, что сказал клиент.** Тариф даёт `N` слотов с
номерами `1..N` — строки в нашей базе. Клиент не может начеканить слотов, поэтому дыра E7
(«32 контейнера с одним `PSEUDEX_INSTANCE_ID`») закрывается у корня, а не потолком процессов.
Это ровно принцип `tz-offline-license.md` §6 — «потолок, честно посчитанный ПРИ ВЫДАЧЕ».

**П2. Старт контейнера — это ПОКОЛЕНИЕ, и оно предъявляет `(slot, epoch)`.**
`entrypoint.sh` чеканит `start_id` ОДИН РАЗ на все воркеры — ровно так же и в том же файле, как
он уже чеканит `PSEUDEX_ADMIN_TOKEN` и `PSEUDEX_GATEWAY_TOKEN`, и по той же причине (N воркеров,
каждый со своим значением, — это N истин на один порт). `POST /v1/lease` несёт `start_id`; сервер:

* `start_id` уже держит слот → тот же `epoch`, это ещё один воркер того же старта — **даром и
  без предела**, пока воркеров меньше `processes_allowed`;
* иначе выбрать слот: свободный → взять; свободных нет → взять тот, **чей текущий эпох
  разговаривал с нами позже всех** (`MAX(meter.updated_at)`), и увеличить его `epoch`.

Второе — **ранжирование, а не порог**. «Молчит дольше `T_alive`» — утверждение о мире, и оно
бывает ложным (Ford et al.: >90 % молчаний короче 15 минут). «Из занятых этот разговаривал с
нами позже всех» не утверждает ничего и ложным быть не может. Детектор отказов исчезает из
кода не потому, что мы его улучшили, а потому, что решение больше не требует его ответа.

**П3. Фенсинг стоит на `/v1/meter`, и он отказывает в НОВОЙ ёмкости, а не убивает.**
Покупка кванта несёт `(slot, epoch)`; эпох ниже наибольшего записанного для слота получает
терминальный вердикт, минующий grace (как сегодня `instance_limit` в `_ANSWER_CODES`,
`license.py:124`). **Уже выданное не отзывается** — отфенсенное поколение ДОЦЕЖИВАЕТ свой
остаток и честно встаёт. Это и есть секвенсер Chubby, у которого «recipient server» — наш
собственный `/v1/meter`; и это единственное место во всей отрасли плавающих лицензий, где
предусловие Клеппманна выполнимо, потому что ресурс наш.

**И одно изменение, без которого первые три не работают.**

**П4. Леджер ёмкости ключуется СЛОТОМ, а новое поколение НАСЛЕДУЕТ остаток вместо покупки.**
`meter` переключается с `(org_id, pubkey)` на `(org_id, slot)`; `pubkey` остаётся тем, КТО
отчитался, но не тем, ЧЕЙ счёт. И правило §4.3 «первый квант покупается на старте» становится
условным: покупать только если `granted <= consumed`; иначе поколение **принимает остаток слота
как есть** и идёт за следующим квантом, лишь перейдя порог предвыборки.

Вот зачем П4 и почему без него всё остальное — косметика. Возьмём две ситуации, которые шесть
заходов не смогли развести, и посмотрим, что делает наследование:

| | сегодня (леджер на ключе) | с леджером на слоте |
|---|---|---|
| **OOM-перезапуск** | новый ключ → новая строка → покупка на старте → 200 запросов, счёт 0 | то же поколение того же слота: `granted > consumed` → **не покупает вообще**, берёт остаток. Ноль строк, ноль запросов, ноль рублей |
| **оборот кольца** | новый ключ → новая строка → 200 запросов, счёт 0. Повторяемо без предела | тот же слот, тот же остаток. Все обороты **делят один баланс** |

Свободная полоса перестаёт быть «`Q + R` на каждый ключ, который когда-либо существовал» и
становится «`Q + R` на СЛОТ за всю его жизнь». Для клиента с 16 воркерами, перезапускающимися
десять раз в день месяц, это разница между ~4800 строками и одной.

**Что при этом УДАЛЯЕТСЯ из кода** (весь инвентарь шести заходов): `ALIVE_SECONDS`,
`RELEASE_ECHO_SECONDS`, `RELEASE_COOLDOWN_SECONDS`, `turnover_last_hour` / `release_budget`,
`holds_place`, `_speaks_after_release`, `_bought_after_release`, отбор по молчанию
(`released_by='silence'`), `_refuse_turnover`. Остаётся один таймер — TTL аренды плюс grace, и
он теперь отвечает только за БАНДЛ, а не за счёт мест.

**Контракт данных — то, по чему можно писать ТЗ.**

*Что хранит сервер.* Одна новая таблица и одно изменение ключа:

```
slots(org_id, slot_no, epoch, holder_start_id, opened_at, last_meter_at)
      PRIMARY KEY (org_id, slot_no)
      -- slot_no: 1..instances_allowed(plan); строки заводятся при выпуске ключа,
      --          а не при первой аренде: потолок посчитан ПРИ ВЫДАЧЕ (tz-offline-license §6)
      -- epoch:   монотонный, НИКОГДА не переиспользуется; durable (Paxos P1a:
      --          «an acceptor must remember this information even if it fails and then restarts»)

meter(org_id, slot_no, …)   -- было (org_id, pubkey)
      -- granted / acked / prefetch_at / quantum_seq живут на СЛОТЕ и переживают поколения
      -- pubkey переезжает в отдельную колонку «кто отчитался последним»: он нужен для
      --   MAC отчёта и для ack_regressions, но он больше не ключ счёта
```

*Что шлёт клиент.* Два новых поля и ни одного нового запроса:

| запрос | добавляется | кто чеканит |
|---|---|---|
| `POST /v1/lease` | `start_id` | `entrypoint.sh`, один раз на все воркеры |
| ответ на lease | `slot_no`, `epoch` | сервер |
| `POST /v1/meter` | `slot_no`, `epoch` | клиент повторяет выданное |
| `POST /v1/usage` | `slot_no`, `epoch` | то же |

*Эпох ОБЯЗАН ехать внутри MAC-нутого конверта.* Фенсинг-токен вне аутентифицированной нагрузки
— украшение: повтор отчёта со старым эпохом должен валиться и по свежести, и по эпоху
независимо. У нас конверт уже есть (`bundle.mac_report` / `verify_report`).

*Совместимость.* Лиза без `start_id` — это движок до этой версии; для него сервер ведёт себя
как сегодня (`instance_id` как слот, леджер на ключе). Правило то же, что для `heartbeat_seconds`
в прошлом исследовании: **сервер не должен требовать поля никогда**, иначе ошибка = простой у
клиента. Отказ по эпоху доезжает до уже выпущенных движков дословно в `detail` (его печатают
`service.py:253` и `proxy.py:258`); собственный код `fenced` в `_ANSWER_CODES` едет с ближайшим
релизом движка.

**Проверка конструкции по сценариям, которые её и ломали.**

| сценарий | что происходит | цена клиенту |
|---|---|---|
| перезапуск на том же томе (`docker compose up -d`, `pseudexctl upgrade`) | новый `start_id`, слот тот же (его прежний эпох — самый старый среди занятых, потому что он мёртв), `epoch+1`, остаток наследуется | **ноль**, мгновенно |
| **OOM-килл и подъём** | то же самое; ни один порог не опрашивается | **ноль**, мгновенно |
| crash-loop (`restartPolicy: always`) | каждый подъём — новый эпох того же слота; покупки нет, пока не обслужено | **ноль** |
| обрыв сети на 3 суток | без связи новое поколение аренды не получит вовсе (как и сегодня). Старое доживает на остатке слота | без изменений; это НАША доступность |
| кольцо «аренда → релиз → аренда» | каждый оборот наследует один и тот же остаток; отфенсенные доцеживают долю | **обход становится делением, а не умножением** |
| копия тома на второй машине | та же установка → тот же слот → два поколения фенсят друг друга и делят баланс | сегодня копия давала целый новый инстанс |
| контейнеров больше, чем слотов | они фенсят друг друга по кругу; суммарная пропускная способность ≈ один слот; **никого не запирает отказом** | потолок принуждается фенсингом, а не 409 |
| 2 → 20 воркеров | все несут один `start_id` и один леджер слота, просто черпают быстрее | `processes_allowed` становится подсказкой, а не замком. Дефект E8/Б26sexies («10 честных стартов → отказ на 6-м») исчезает как класс |

**Чего конструкция НЕ делает, и это сказано до раздела «предел»:** она не ограничивает
ПАРАЛЛЕЛИЗМ. Двадцать отфенсенных поколений, делящих один баланс, — это двадцать процессов, и
если клиенту нужна не пропускная способность, а отказоустойчивость на двадцати площадках, он
её получит. Ограничен объём, и только он.

**Два свойства, которые надо назвать явно, потому что именно на них сломались прошлые заходы.**

**Конструкция НЕ ТРЕБУЕТ ПРОЩАНИЯ.** Ни одно из четырёх правил не читает `/v1/release`.
Освобождение места происходит в момент, когда НОВОЕ поколение приходит за слотом, — и это
единственный момент, в котором сервер вообще что-то решает. OOM-килл (SIGKILL, обработчик не
исполняется) и перезагрузка узла (`shutdownGracePeriod: 0` по умолчанию) — два самых частых
пути выхода, на которых прощание невозможно (§4.5), — перестают быть особым случаем. Сегодня
они попадают в худшую ветку правила Б26quinquies («молчание место не освобождает»); после
правки их просто нет в коде как отдельного понятия.

**Конструкция ВЫДЕРЖИВАЕТ ШТАТНОЕ ПРЕВЫШЕНИЕ, которое создаёт сама платформа.** Однорепличный
Deployment удваивается при каждом обновлении по умолчанию и обойти это нельзя (§4.5). Фенсинг
на этом сценарии работает правильно и без единой настройки: новый под поднимается, берёт свой
же слот, увеличивает эпох; старый под продолжает обслуживать из уже выданного остатка все свои
30 секунд `terminationGracePeriodSeconds` и уходит. **Отказа не выдаётся никому.** Сравните с
любым правилом, отказывающим на `N`-м контейнере: оно ломает КАЖДУЮ раскатку самой
распространённой формы деплоя нашего продукта.

Одна оговорка, которую надо записать в ТЗ: отфенсенное поколение обслуживает, **пока у слота
есть остаток**. При резерве в 48 часов трафика остаток практически никогда не ноль, но
граничный случай существует — слот, исчерпавший ёмкость ровно в момент раскатки, отдаст
`capacity_exhausted` на 30 секунд. Лечится тем же, чем лечится любой пограничный случай
ёмкости: порог предвыборки стоит ВНУТРИ резерва (`prefetch_at = granted − R − Q/4`), то есть
поколение идёт за ёмкостью, пока страховка цела.

## 5. Критический разбор

### 5.1 Сильнейшая версия возражения: «вы просто меняете одну дыру на другую»

**Steelman.** Сегодня потолок принуждается двумя числами (слоты и места процессов) и кольцо
упирается в 32. В предлагаемой конструкции потолка на ЧИСЛО процессов нет вообще: двадцать
отфенсенных поколений живут одновременно. Значит наблюдаемое «сколько инстансов у клиента»
становится хуже, а не лучше, — а владелец просил именно «100 процентов надёжно понимать
кол-во инстансов».

**Ответ, и он наполовину уступка.** Возражение верно в букве и неверно в валюте.

* Верно: **число одновременно работающих процессов перестаёт принуждаться.** Мы его знаем
  (это наши эпохи и наши покупки), но не отказываем по нему.
* Неверно: «дыра». Двадцать поколений делят ОДИН баланс; сумма того, что они обслужат, равна
  тому, что слот купил. Сегодня двадцать оборотов кольца дают двадцать НЕЗАВИСИМЫХ балансов по
  `Q + R` каждый. Умножение заменяется делением — это не размен дыры на дыру.
* И честная уступка: **«100 процентов надёжно понимать кол-во инстансов» недостижимо, и это
  §4.1, а не недоработка.** Сервер соундно знает ровно две величины: нижнюю границу (кто
  покупал ёмкость в последнее окно — те провабельно работали) и верхнюю (нижняя плюс те, чей
  эпох не превзойдён). Истинное число лежит между и НЕНАБЛЮДАЕМО. Правильный ответ витрине —
  показывать обе границы, а не одно число, и называть молчание «неизвестно». Это уже правило
  проекта в двух местах (`CLAUDE.md` про версии; `storefront/billing/slots.py` про занятость) —
  теория лишь говорит, что оно не осторожность, а единственное, что она лицензирует.

### 5.1bis Конструкция НЕ нова, и это её сильная сторона

Собирая §4.7, я считал сочетание «леджер на слоте + наследование остатка» своим выводом.
Раскопка по старой гвардии показала, что **половина конструкции существует в продакшене с
прошлого века**: RLM `min_checkout` держит место чекнутым столько, сколько стоит минимальная
занятость, **независимо от того, сколько реально прожил процесс**, и вендор называет цель
дословно — «in order to provide a “fairer” measure of concurrent usage». FlexNet `LINGER` и
CodeMeter Linger Time — тот же приём, и FlexNet в том же абзаце называет цену: «other users
have to wait until the first user is completely finished, plus a linger interval». `[A]`

Разница между ними и нами — валюта и знак. У них минимум занятости измеряется В СЕКУНДАХ, и
поэтому он **наказывает честного** (место занято, пока он уже ушёл). У нас он измеряется В
ЗАПРОСАХ и наследуется слотом, поэтому он **не наказывает никого**: перезапустившийся не платит
(он берёт остаток), а кольцу не за что платить (остаток тот же). **Перенос минимальной
занятости из времени в объём — вот вся новизна, и она маленькая.** Это хорошо: у приёма
двадцатилетняя эксплуатация, а мы меняем только ось.

Вторая половина — эпох и фенсинг на ресурсе — не нова вообще (§4.1). Новым остаётся только
место, куда мы его ставим: `/v1/meter`. И оно не «изобретено», а **уже построено** шестым
заходом.

### 5.2 Единственное несущее допущение

**Обслуживать без нашего кванта нельзя.** На нём стоит всё: фенсинг на `/v1/meter` имеет
смысл только пока квант — необходимое условие маскирования. Когда это допущение ложно:

* **патч релизного бинарника**, снимающий проверку ёмкости. Уже записано как принятый остаток
  (`metering-integrity.md` §8, `tz-license-packaging.md` §3.4). Окно такого патча равно TTL
  аренды: без свежей аренды нет бандла, без бандла нет детекции;
* **`granted == 0` означает безлимит** — лазейка, которую уже закрывали дважды
  (`metering-integrity.md` §5.6). Ноль теперь безлимит только для движков старого контракта.
  При переходе на леджер слота это место надо перечитать заново: «слот без покупок» — новое
  состояние, и оно не должно читаться как ноль-безлимит;
* **клонирование процесса вместе с прогретым грантом** (см. §5.4).

### 5.3 Противоречия между источниками — и почему они не усредняются

**Chubby и Consul ставят задержку 60 с и 15 с; у нас место процесса держится до суток.** Это
не «разные масштабы одной настройки». Обоснования РАЗНЫЕ и направлены в разные стороны:
Chubby капирует задержку, «чтобы неисправный клиент не сделал ресурс недоступным на
произвольно долгое время», то есть защищает ДЕРЖАТЕЛЯ от себя же; наш срок защищает НАШ
потолок от держателя. Усреднять эти числа бессмысленно — надо выбрать, чью сторону держит
механизм. Все шесть заходов приземлялись на честного клиента именно потому, что механизм
держал нашу сторону, а платил клиент простоем.

**Kleppmann против Антиреза.** Не «кто прав», а разные объекты спора: Клеппманн требует
МОНОТОННОСТИ, Антирез считает достаточной УНИКАЛЬНОСТЬ плюс check-and-set. Для нас спор решён
контекстом: уникальный токен не даёт упорядочить два поколения ОДНОГО слота, а нам нужно
именно это. Берём монотонность.

**etcd против собственной вывески.** Документация etcd прямо пишет, что её API «называются
lock по историческим причинам» и что аренда мьютекса не даёт. Это не противоречие между
источниками — это единственный вендор, который написал не-гарантию первым лицом, и потому
самый ценный.

### 5.4 Что эта конструкция НЕ закрывает — назван класс, а не отговорка

**(а) Параллелизм.** Ограничен объём, не число процессов. Клиент, покупающий отказоустойчивость
(несколько площадок, низкая латентность), получает её бесплатно. Закрывается только ценой:
если параллелизм продаётся, он должен быть в ЦЕНЕ, а не в отказе.

**(б) Клонирование процесса с прогретым грантом.** `_granted` — это int в памяти воркера.
Root может снять чекпойнт (CRIU) и восстановить N копий, каждая с тем же предоплаченным
резервом. Разовая утечка = `(N − 1) × резерв_на_момент_чекпойнта`. Наблюдаемо: клон, который
доложит свой меньший расход, уронит `consumed` назад → `regressed` → слепой шаг → `granted`
растёт, и `ack_regressions` это считает (строка «два процесса под одним ключом» в
`metering-integrity.md` §5). Клон, который не докладывает НИКОГДА, свой резерв получает даром —
один раз. **Ни счёт инстансов, ни эпохи, ни фенсинг этого не касаются.** Ограничивает это
ровно одна величина — размер резерва, то есть `RESERVE_SECONDS`. Это Barak/RE-TRUST в
конкретной форме.

**(в) Патч, снимающий проверку.** Ограничен TTL аренды и повторяем на каждой версии. Планка —
коммерческий десктопный софт, принята сознательно.

**(г) Перехватчик с первого обращения.** TLS проверяется по хранилищу контейнера. Уже записано.

### 5.5 Теорема о пределе, сформулированная в нашей валюте

Пусть `R` — суммарная ёмкость, которую мы выдали и расход которой ещё не подтверждён. Тогда
число процессов, способных обслуживать БЕЗ дальнейшего нашего разрешения, ограничено сверху
`R / (минимальная ёмкость, нужная процессу)`, и уменьшить `R` быстрее, чем клиент подтверждает
расход, мы не можем: подтверждение — единственная улика, а «не потрачено» от «потрачено и не
доложено» мы не отличаем (это §4.1 в форме бухгалтерии).

**Отсюда прямо:** окно работы без связи с нами и потолок обхода — это одно и то же число,
увиденное дважды. Их нельзя оптимизировать по отдельности, потому что это не два параметра.
Прошлое исследование записало то же самое как `потолок ≈ темп × T_offline`; разница в том, что
`T_offline` теперь измеряется **в запросах**, а не в часах, и называется `RESERVE_SECONDS`.
**Шесть заходов ужимали `темп`; ручка, которая двигает произведение, — вторая.**

### 5.6 Проверка на заинтересованность

* Вендоры плавающих лицензий имеют интерес продавать «надёжный контроль»; поэтому в §4.3
  цитируются админ-руководства и конфигурационные параметры, а не маркетинговые страницы, и
  там, где вендор не документирует поведение при падении клиента, это сказано, а не
  домыслено.
* Академические первоисточники (FLP, CT, CHT, Paxos, Raft, VR) — теоремы; интереса у них нет,
  но у НАС есть соблазн прочитать их как «значит и пытаться незачем». Это неверно, и FLP §5
  говорит это первым лицом.
* Самый опасный источник предвзятости — мой собственный: рекомендуемая конструкция и вывод
  раскопок сошлись, и **сходимость здесь не подтверждение.** Ветвь раскопок и я пришли к
  «эпох + проверка на ресурсе» независимо, но из одной литературы. Поэтому конструкция помечена
  `[D — инженерный вывод]`, а `[A]`/`[B]` стоят только на её деталях.

### 5.7 Заработанный консенсус или повторяемое допущение

Распределение оценок само по себе есть вывод. **Теория — сплошной `[A]`**: FLP, CT (включая
сноску 6), CHT, Paxos, Raft, VR, van Renesse, Ford et al. Здесь консенсус заработан и
доказан. **Практика — `[B]`/`[C]`**: механизмы Chubby, ZooKeeper, etcd, Consul, Kafka
документированы их авторами, но числа (минута, 15 с, 12 с, 45 с) заявлены как обоснование и
нигде не измерены. **«Правильные» сроки для лицензионного сервера — `[D]`**: ни один
первоисточник не выводит их ни из чего; каждый вендор выбрал своё и не объяснил. Отсюда
практическое следствие: **копировать чужие числа не у кого**, а вот копировать чужую
КОНСТРУКЦИЮ есть у кого, и это ровно наоборот тому, как такие решения обычно принимают.

## 6. Что взять готовым, что написать самим и почему

Отрасль делится ровно надвое: **координационные примитивы** (их брать готовыми нельзя, но их
КОНСТРУКЦИЮ можно и нужно) и **лицензионные продукты** (их брать готовыми можно, но они решают
нашу задачу хуже, чем то, что у нас уже построено).

| что | брать готовым? | цена | от чего придётся отказаться |
|---|---|---|---|
| **etcd / ZooKeeper / Consul как хранилище слотов и эпох** | **нет** | новый stateful-компонент в нашем контуре, свой кворум, свои бэкапы, свой отказ | Наш сервер лицензий уже однопроцессный с SQLCipher и реентрантным локом; монотонный счётчик на слот — это `UPDATE … SET epoch=epoch+1 RETURNING` в той же критической секции, что и выдача. Кворум решает задачу, которой у нас нет (у нас ОДНА точка истины по построению). Брать etcd ради `Revision` — это купить консенсус, чтобы получить `AUTOINCREMENT` |
| **их КОНСТРУКЦИЮ (эпох + проверка на ресурсе)** | **да, целиком** | одна колонка, одно поле в двух запросах, один терминальный код | ничего. Это буквально §2.4 Chubby и §5.1 Raft, и обе системы объясняют, почему без этого таймауты не дают безопасности |
| **Keygen.sh / Cryptlex / LicenseSpring** (лицензирование как сервис, с моделью «машины и процессы», heartbeat, cull/resurrection) | **нет** | внешняя зависимость в тракте лицензии; наш сервер лицензий — единственный компонент на нашем железе и в нём же живёт выдача бандла, запечатанного на процессный ключ | Они дают ровно то, что у нас уже есть (heartbeat + culling + окно воскрешения), то есть ДЕТЕКТОР — слой, от которого §4.1 предлагает отказаться. Покупать чужую реализацию нерешаемой задачи незачем. **Но их словарь стоит украсть** (см. §4.3): «resurrection window» — честное имя для того, что мы называли эхом |
| **FlexNet / Sentinel / RLM / CodeMeter** | **нет** | требуют вендор-демона у клиента и своего протокола | Категория построена вокруг TCP-сессии как признака жизни и `lmremove` как ручного рычага. Наш рычаг уже есть (`POST /admin/release`); сессия у нас не держится по построению (сайдкар не держит соединение) |
| **TPM 2.0 / remote attestation как удостоверение установки** | **нет** | требует железа, которого на РФ-рынке on-prem нет; аттестует ПЛАТФОРМУ, а не контейнер поверх неё | Уже отвергнуто в `tz-license-packaging.md` §3.4 по верной причине. §4.4 подтверждает: даже там, где vTPM есть, аттестация не говорит ничего о рабочей нагрузке в контейнере, а верификатор обязан быть удалённым |
| **подписанный identity-документ облака (AWS IMDSv2 / GCP identity token / Azure attested data)** | **точечно, как второй сигнал** | покрывает только клиентов в тех облаках | Российские облака подобного не документируют (см. §4.4). Как ОСНОВА удостоверения не годится — покрытие дырявое; как усиление для тех, у кого оно есть, — почти бесплатно |
| **`deployment.key` в томе как удостоверение** | **да — уже выбрано, для офлайна** | «клон тома = клон лицензии», сказано вслух | Ничего нового: онлайновый `installation_id` уже ровно это, только слабее (клиент может переопределить `PSEUDEX_INSTANCE_ID`). Переход на выдаваемый НАМИ слот делает переопределение бессмысленным |
| **минимальная занятость места** (RLM `min_checkout`, FlexNet `LINGER`, CodeMeter Linger Time) | **идею — да, реализацию — нет** | у них она в СЕКУНДАХ и держит место после ухода, то есть наказывает честного; FlexNet сам называет цену: «other users have to wait until the first user is completely finished, plus a linger interval» | Берём принцип «оборот не даёт ничего», но переносим его из ВРЕМЕНИ в ОБЪЁМ (§5.1bis). Тогда наказания честного не возникает по построению |
| **овердрафт вместо отказа** (FlexNet `OVERDRAFT`, RLM `soft_limit`, Keygen `overageStrategy`, Zentitle2) | **да, как поведение** | ноль кода: в конструкции §4.7 он получается сам — фенсинг не отказывает, он дренирует | Ничего. Отказываемся только от иллюзии, что 409 на `N+1`-м контейнере вообще был нужен |
| **договорный слой (самоотчёт, право проверки, ретроперерасчёт)** | **да — уже есть** | ноль | Оферта, раздел 5bis, по образцам Elastic §5 и Microsoft SPLA. Это то, чем отрасль закрывает остаток §5.4, и наш текст уже написан |

**Что пишем сами и почему именно мы.** Слоты, эпохи и леджер на слоте — потому что у нас есть
то, чего нет ни у одного вендора плавающих лицензий: **точка, в которой право обслуживать
выдаётся непрерывно и нами** (`/v1/meter`, шестой заход). Kleppmann, Burrows и etcd
независимо формулируют одно и то же предусловие фенсинга — «ресурс обязан проверять», — и оно
у нас выполнено. Купить это нельзя, потому что продаётся всё что угодно, кроме доступа к
чужому ресурсу.

## 7. Таблица сравнения механизмов

Оси — из задания владельца. «Перезапуск бесплатен» = честный подъём после падения не стоит ни
простоя, ни единицы бюджета, ни денег. «Кольцо бессмысленно» = `аренда → релиз → аренда` не
даёт ничего сверх одного оборота. Оценки в скобках — по разделу §4.

| механизм | перезапуск бесплатен | кольцо бессмысленно | подделывается рутом | наблюдаемо сервером | работает 72 ч без сети | понятно покупателю |
|---|---|---|---|---|---|---|
| **1. занятость по сроку аренды** (заход 1) | **нет** — место держится 16–24 ч | нет | — | да | да | нет: отказ предлагает остановить то, чего нет |
| **2. занятость по признаку жизни (`T_alive`)** (заходы 2–3) | частично — 10 минут простоя | нет: молчание неотличимо от остановки | нет (отметку ставит сервер) | да | да | средне |
| **3. бюджет перевыдач** (заходы 2–5) | **нет** — редеплой тратил единицу, пятый `up -d` отказывал | ограничивает ТЕМП, не число | нет | да | да | нет: «перевыдача» — не слово клиента |
| **4. остывание слота (`lock-delay`)** (заход 1–5) | нет | нет | нет | да | да | нет |
| **5. правило эха** (заход 3, 5) | не касается | частично — до грации в 30 с | нет | да | да | нет |
| **6. потолок на ЁМКОСТИ** (заход 6, **в дереве сейчас**) | **да** (счёт 0 у умершего воркера) | **почти** — но оборот уносит `Q + R` даром | нет: грант — наша запись | да | да (резерв = 48 ч) | да: «объём» |
| **7. эпох + фенсинг на `/v1/meter` + леджер на СЛОТЕ** (рекомендация) | **да, по построению** — нет строки, нет покупки | **да** — обороты делят один баланс | нет | **да, точнее прежнего**: слот и эпох чеканим мы | да, без изменений | **да**: «N контейнеров, у каждого объём; перезапуск ничего не стоит» |
| — *из отрасли, для сверки* — | | | | | | |
| **8. TCP-сессия как признак жизни** (FlexNet и вся категория) | да, если соединение закрылось | нет | — | да | **нет**: требует постоянного соединения | да |
| **9. heartbeat + cull + resurrection window** (Keygen, Cryptlex) | почти: окно воскрешения 1–15 мин; Keygen Relay — **идемпотентный захват по личности**, худший случай 75 с | нет (ни один современный SaaS-вендор не документирует защиты от карусели) | нет | да | зависит от продукта | да |
| **9bis. минимальная занятость** (RLM `min_checkout`, FlexNet `LINGER`, CodeMeter Linger Time) | **нет** — место держится после ухода | **да** — «fairer measure of concurrent usage» | нет | да | да | средне |
| **9ter. схлопывание личностей** (Sentinel LDK `Count Each: Station` по умолчанию, Cryptlex `Per-Machine`, RLM `share=`) | **да, из коробки** | частично | нет | да | да | **да** |
| **9quater. овердрафт** (FlexNet `OVERDRAFT`, RLM `soft_limit`, Keygen `overageStrategy`, Zentitle2) | **да** — раскатка не отказывает | нет (сам по себе) | нет | да | да | да |
| **10. аппаратная привязка / TPM-аттестация** | ломается при легальной миграции | не касается | **нет** — но аттестует платформу, а не контейнер | да | да | нет |
| **11. не считать вовсе: договор + аудит** | да | **вопрос не стоит** | не применимо | нет | да | да |

Три чтения этой таблицы, которые в ней не написаны прямо:

1. **Строки 1–5 — это шесть заходов, и ни одна не закрывает первые два столбца одновременно.**
   Не потому, что плохо сделаны: первые два столбца — это «не наказывать за неразличимое» и
   «наказывать за неразличимое», то есть одно требование и его отрицание, пока событие
   описывается ВРЕМЕНЕМ.
2. **Строка 6 — уже в дереве, и она первая, где оба столбца почти зелёные.** Это произошло не
   от лучшей эвристики, а от смены валюты: время заменилось объёмом. Строка 7 доводит ту же
   смену до конца, меняя КЛЮЧ леджера.
3. **Строка 11 — не капитуляция, а то, чем отрасль закрывает остаток у всех остальных строк.**
   Она стоит последней не потому, что худшая, а потому, что идёт ПОВЕРХ любой из них.

---

## 8. Реестр доказательности

| утверждение | оценка | первоисточник | честная оговорка |
|---|---|---|---|
| Различить упавший процесс и медленный в асинхронной модели невозможно | **A** | FLP, JACM 32(2) 1985, §1, Theorem 1 | Это про АСИНХРОННУЮ модель; допущение о времени снимает запрет, и аренда — оно и есть |
| Даже слабейший полезный детектор ◇W нереализуем в асинхронной системе | **A** | Chandra–Toueg, JACM 43(2) 1996, §1 сноска 6 | Доказано сведением к FLP, не измерено |
| Слабейший детектор для консенсуса — ◇W₀ / Ω, и он выдаёт лидера, а не свидетельство о смерти | **A** теоремы / **B** формулировка Ω | CHT, JACM 43(4) 1996; Guerraoui–Kuznetsov, arXiv:1310.1761 | До PDF CHT дойти не удалось (ACM DL 403); формулировка Ω взята из двух рецензированных пересказов |
| Аренда переводит проблему живости в проблему времени; небезопасное направление — быстрые часы СЕРВЕРА | **A** | Gray & Cheriton, SOSP 1989, §5 | «Сбои часов реже отказов» в той же §5 — заявлено, не измерено → **C** |
| Фенсинг безопасен, только если проверяет сам ресурс | **B** авторский аргумент / **A** механизм | Kleppmann 2016; Burrows §2.4; etcd docs | Пост Клеппманна — первоисточник его аргумента; механизм — тот же монотонный бюллетень, что доказан в Paxos |
| «В каждый момент операционен не более одного раунда» — общий инвариант Paxos/VR/Zab | **A** | van Renesse, Schiper, Schneider, arXiv:1309.5671 §3.1 | Уточняющие отображения, доказаны |
| Chubby: добровольный релиз освобождает сразу, выведенный — через `lock-delay` ≤ 1 мин | **B** механизм / **C** числа | Burrows, OSDI 2006, §2.4 | 1 мин, 12 с, 45 с заявлены как обоснование, не измерены |
| Аренда etcd НЕ даёт взаимного исключения; её роль — оптимизация | **B** | etcd docs, «Notes on the usage of lock and lease» | Официальная документация, первым лицом |
| Consul: TTL — НИЖНЯЯ граница инвалидации, верхней нет | **B** | developer.hashicorp.com/consul, sessions | Документация, не доказательство |
| >90 % событий недоступности узла короче 15 минут; GFS ждёт 15 минут перед восстановлением | **A** | Ford et al., OSDI 2010, §2 | Измерено за год на десятках кластеров 1000–7000 узлов; Google-специфично |
| Kafka: `InitProducerId` увеличивает эпох и фенсит зомби; таймаут перед перехватом не требуется | **A** | KIP-98; KIP-447 | Нормативный текст KIP |
| Статическое членство существует ради «перезапуск не должен стоить ребаланса» | **A** | KIP-345; `consumer_config` Kafka 4.0 | — |
| Однорепличный k8s-Deployment удваивается при каждой раскатке по умолчанию | **A** | Kubernetes Deployment docs (maxSurge 25 % вверх, maxUnavailable 25 % вниз) | Выведено из документированных правил округления; документация подтверждает превышение `replicas+maxSurge` |
| OOM-килл — SIGKILL, обработчик не исполняется; graceful node shutdown по умолчанию выключен | **A** | k8s node-pressure eviction; k8s graceful-node-shutdown | — |
| Docker сбрасывает бэкофф после 10 с, Kubernetes — после 10 мин; джиттера нет ни у кого | **A** | docs.docker.com + `moby/.../restartmanager.go`; k8s pod-lifecycle + `pkg/kubelet/kubelet.go` | Проверено в документации И в исходниках обоих |
| Из ~21 self-hosted продукта потолок ЧИСЛА принуждают шестеро | **A** | лицензионные соглашения и документация каждого (§4.3) | Выборка — то, что раскопка смогла достать; не перепись |
| NGINX Plus R33+ принуждает ОТЧЁТ, а не счёт; 180 дней без отчёта — остановка трафика | **A** | docs.nginx.com, «About subscription licenses» | — |
| 10Duke: истёкшая аренда освобождается МГНОВЕННО, а добровольный релиз получает cooldown | **A** | docs.enterprise.10duke.com | Один вендор |
| Keygen для раскаток рекомендует `ALLOW_2X_OVERAGE`, «rather than deny» | **B** | keygen.sh/docs/choosing-a-licensing-model/floating-licenses | Один вендор |
| В Docker `/etc/machine-id` в расхожих образах отсутствует или нулевой; DMI недоступен; MAC перегенерируется | **A-obs** | замеры раскопки, Docker 29.4.0, cgroup v2, aarch64 | Отсутствие DMI частично платформенное (ARM без SMBIOS) |
| У Yandex Cloud есть подписанный identity-документ с опубликованными сертификатами, без нонса | **B** докум. / **A-obs** сертификаты | yandex.cloud docs; PEM декодированы раскопкой | Нонса нет → повтор до 2033; IMDS выключается одним флагом |
| TPM-аттестация как лицензионная привязка не существует как продукт; Microsoft не аттестует ВМ | **A** спеки / **B** Microsoft | TCG TPM 2.0 Part 1 §9.4.3.2–9.4.3.4; TCG Keys for Device Identity §3.11, §10; Keylime; Microsoft Autopilot docs | — |
| Виртуальная черновая обфускация невозможна даже в слабых формализациях | **A** | Barak et al., CRYPTO 2001 / JACM 2012, eprint 2001/069 | Не запрещает indistinguishability obfuscation и практическую стойкость |
| Академическое имя задачи — remote entrusting; локальная проверка недостижима | **B** | RE-TRUST (EU FP6 021186); Ceccato/Tonella/Collberg, barrier slicing | До полного текста финального отчёта не дошёл |
| `billable = clamp(acked, granted − Q − R, granted)` делает бесплатными И холодный старт, И оборот кольца | **A** | `licensing/store.py::billable`, `issue_quantum`; `docs/metering-integrity.md` §4.3 | Прочитано в коде; арифметика приведена в §4.2 |
| `RESERVE_SECONDS = 48 ч` — связывающая величина потолка обхода | **A** код / **D** связывание | `licensing/store.py:1095,1582,1117` | Само связывание «резерв = потолок обхода» — мой вывод, не цитата |
| Рекомендуемая конструкция (слот + эпох + наследование) | **D — инженерный вывод** | — | Сборка моя; `A`/`B` стоят только на её компонентах. Аналога, делающего ИМЕННО это, в раскопке не нашлось |

---

## 9. Открытые вопросы и то, чего установить не удалось

**Не закрыто раскопкой.**

* **Две расхожие цифры про старую гвардию оказались ЛОЖНЫМИ, и это стоит записать.**
  (а) Минимум `TIMEOUTALL` у FlexNet — **не платформенная константа**, а переменная,
  вкомпилированная каждым ISV (`ls_minimum_user_timeout`, штатное значение 900 с), и реальные
  ISV её поднимают: IBM Rational требует «greater than 7200 seconds». (б) Таймаут CodeMeter
  при падении клиента — **120 минут, и это цифра для ЛВС**; расхожие «~10 минут для CmWAN» не
  подтверждаются ни одним источником Wibu, а таймаут CmWAN не документирован вообще. Любое
  число из пересказа по этой категории надо перепроверять.
* **`CleanUpTimeOut` у CodeMeter не документирован** — минимума нет ни в одном источнике Wibu.
* **Подписанные identity-документы VK Cloud, Selectel, Timeweb — первоисточника нет `[D]`.**
  Структурная причина названа (апстрим OpenStack не имеет такого примитива), но отрицательный
  результат проверен только косвенно.
* **SEV-SNP / конфиденциальные ВМ на российских облаках — первоисточника нет `[D]`.**
* **VMware `uuid.action` (копирование против перемещения ВМ)** — Broadcom блокирует
  автоматическую загрузку документации.
* **Что делает Grafana, когда суточное обновление токена НЕ проходит, а лицензия ещё не
  истекла** — не документировано. Это ровно наш вопрос про нашу собственную аварию, и у
  ближайшего аналога на него ответа нет.
* **Поведение Portainer при превышении** (`enforced`/`enforcedAt` в BE API) — код закрыт,
  длительность выводить нельзя.

**Что изменило бы вывод, если окажется ложным.**

* **Если обслуживать МОЖНО без кванта ёмкости** — то есть если существует путь, на котором
  `granted == 0` читается как безлимит (это уже чинили дважды, `metering-integrity.md` §5.6), —
  фенсинг на `/v1/meter` теряет смысл целиком, и вся конструкция §4.7 рассыпается. **Это
  единственное несущее допущение, и его надо перепроверить ПЕРВЫМ, до любого кода.**
* **Если число контейнеров — это то, за что клиент платит психологически, а не за объём**, то
  перевод потолка на ёмкость меняет продукт, а не только механизм. Это решение владельца, не
  вывод исследования. Grafana и ISL Online показывают, что режим принуждения можно продавать
  как выбор, — но это два прайса, а не один.
* **Если у нас появятся клиенты в закрытых контурах** (офлайн-SKU), фенсинг на `/v1/meter`
  для них не существует, и потолок там принуждается только числом названных получателей при
  выдаче — то есть ровно так, как `tz-offline-license.md` §6 уже написал. Две конструкции для
  двух SKU — это нормально, но это надо сказать вслух, а не обнаружить потом.

**Что прочитать/замерить следующим, конкретно.**

1. **Перечитать `metering-integrity.md` §5.6 и все места, где `granted == 0`** — на предмет
   того, что означает «слот без покупок» в конструкции §4.7. Это новое состояние.
2. **Замерить на стенде прошлого исследования** (`stand.py` из приложения А) две величины,
   которых никто не мерил: (а) сколько бесплатного объёма даёт один оборот кольца в РАБОЧЕМ
   дереве — я вывел «минимальный квант», но это арифметика, а не замер; (б) сколько обращений к
   `/v1/lease` генерирует крэшлуп под Docker против Kubernetes за час.
3. **Посмотреть `/admin/versions` и `/admin/instances` на проде** — какие формы деплоя реально
   у клиентов (Compose против K8s) и сколько воркеров. От этого зависит, бьёт ли по нам
   `maxSurge` вообще.
4. **Прочитать FlexNet License Administration Guide** — единственная непрочитанная категория, и
   единственное место, где могут найтись ДОКУМЕНТИРОВАННЫЕ минимумы сроков с обоснованием.
5. **Оферта: добавить формулировку в духе Elastic License 2.0 §2** («may not move, change,
   disable, or circumvent the license key functionality»). Наш раздел 5bis закрывает самоотчёт
   и проверку, но не снятие проверки как таковое.

---

## 10. Источники (первоисточники, прочитанные)

**Теория и доказательства**

- [Fischer, Lynch, Paterson, «Impossibility of Distributed Consensus with One Faulty Process», JACM 32(2), 1985, 374–382](https://groups.csail.mit.edu/tds/papers/Lynch/jacm85.pdf) — модель, Theorem 1, и §5 с оговоркой авторов. Прочитан PDF.
- [Chandra & Toueg, «Unreliable Failure Detectors for Reliable Distributed Systems», JACM 43(2), 1996](https://doi.org/10.1145/226643.226647) — свойства полноты/точности, сноска 6, §9.1.
- [Chandra, Hadzilacos, Toueg, «The Weakest Failure Detector for Solving Consensus», JACM 43(4), 1996](https://doi.org/10.1145/234533.234549) — ◇W₀; PDF недоступен, теорема взята из CT96 §6.2.
- [Guerraoui & Kuznetsov, «Simple CHT», arXiv:1310.1761](https://arxiv.org/pdf/1310.1761) — формулировка Ω.
- [Gray & Cheriton, «Leases…», SOSP 1989](https://web.stanford.edu/class/archive/cs/cs240/cs240.1056/readings/89-leases.pdf) — §2 механизм, §5 зависимость от часов.
- [Burrows, «The Chubby lock service…», OSDI 2006](https://research.google.com/archive/chubby-osdi06.pdf) — §2.1, §2.4 (секвенсер, lock-delay), §2.8–2.9 (сессии, jeopardy, эпох мастера). Прочитан PDF.
- [Kleppmann, «How to do distributed locking», 2016](https://martin.kleppmann.com/2016/02/08/how-to-do-distributed-locking.html) и [ответ antirez](http://antirez.com/news/101).
- [Ongaro & Ousterhout, «In Search of an Understandable Consensus Algorithm» (Raft), USENIX ATC 2014](https://raft.github.io/raft.pdf) — §5.1 term как логические часы, §8 отказ от аренды.
- [Liskov & Cowling, «Viewstamped Replication Revisited», MIT-CSAIL-TR-2012-021](https://pmg.csail.mit.edu/papers/vr-revisited.pdf) — §4 номер представления.
- [Lamport, «Paxos Made Simple»](https://lamport.azurewebsites.net/pubs/paxos-simple.pdf) — P1ᵃ и требование durable-памяти у акцептора.
- [van Renesse, Schiper, Schneider, «Vive la Différence: Paxos vs. Viewstamped Replication vs. Zab», arXiv:1309.5671](https://arxiv.org/abs/1309.5671) — §3.1 «at most one round is operational».
- [Ford et al., «Availability in Globally Distributed Storage Systems», OSDI 2010](https://www.usenix.org/legacy/event/osdi10/tech/full_papers/Ford.pdf) — §2, CDF недоступности, 15 минут GFS.
- [Barak, Goldreich, Impagliazzo, Rudich, Sahai, Vadhan, Yang, «On the (Im)possibility of Obfuscating Programs», CRYPTO 2001 / JACM 2012](https://eprint.iacr.org/2001/069).
- [RE-TRUST (EU FP6 021186), «Trustworthy Execution of SW on Remote Untrusted Platforms»](https://cordis.europa.eu/project/id/021186) и [Ceccato, Tonella, Collberg, barrier slicing](https://link.springer.com/chapter/10.1007/978-3-540-77566-9_8).

**Координационные системы (документация и исходники)**

- [ZooKeeper Programmer's Guide](https://zookeeper.apache.org/doc/current/zookeeperProgrammers.html) · [Hunt et al., USENIX ATC 2010](https://www.usenix.org/legacy/event/atc10/tech/full_papers/Hunt.pdf)
- [etcd, «Notes on the usage of lock and lease»](https://etcd.io/docs/v3.6/learning/why/) · [API guarantees](https://etcd.io/docs/v3.5/learning/api_guarantees/) · [`client/v3/concurrency/mutex.go`](https://github.com/etcd-io/etcd/blob/main/client/v3/concurrency/mutex.go)
- [Consul sessions](https://developer.hashicorp.com/consul/docs/automate/session) · [Nomad server config (heartbeat)](https://developer.hashicorp.com/nomad/docs/configuration/server)
- [Kafka KIP-98](https://cwiki.apache.org/confluence/display/KAFKA/KIP-98+-+Exactly+Once+Delivery+and+Transactional+Messaging) · [KIP-447](https://cwiki.apache.org/confluence/display/KAFKA/KIP-447%3A+Producer+scalability+for+exactly+once+semantics) · [KIP-345](https://cwiki.apache.org/confluence/display/KAFKA/KIP-345%3A+Introduce+static+membership+protocol+to+reduce+consumer+rebalances) · [consumer config 4.0](https://kafka.apache.org/40/generated/consumer_config.html)

**Платформы: перезапуск, раскатка, OOM**

- [Docker `run` reference (restart policies)](https://docs.docker.com/reference/cli/docker/container/run/) · [`moby/daemon/internal/restartmanager/restartmanager.go`](https://github.com/moby/moby/blob/master/daemon/internal/restartmanager/restartmanager.go)
- [Kubernetes Pod Lifecycle](https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/) · [Deployment (maxSurge/maxUnavailable)](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/) · [node-pressure eviction](https://kubernetes.io/docs/concepts/scheduling-eviction/node-pressure-eviction/) · [graceful node shutdown](https://kubernetes.io/docs/concepts/architecture/nodes/) · [HPA](https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/) · [KEP-4603](https://github.com/kubernetes/enhancements/tree/master/keps/sig-node/4603-tune-crashloopbackoff)
- [cgroup v2 (kernel)](https://docs.kernel.org/admin-guide/cgroup-v2.html)
- [Reiss et al., SoCC 2012](https://www.cs.virginia.edu/~cr4bd/papers/socc12.pdf) · [Tirmazi et al., «Borg: the Next Generation», EuroSys 2020](https://storage.googleapis.com/gweb-research2023-media/pubtools/5532.pdf) · [Verma et al., Borg, EuroSys 2015](https://storage.googleapis.com/gweb-research2023-media/pubtools/pdf/43438.pdf)
- [Brooker, «Exponential Backoff And Jitter»](https://aws.amazon.com/blogs/architecture/exponential-backoff-and-jitter/) · [AWS Builders' Library, «Timeouts, retries, and backoff with jitter»](https://aws.amazon.com/builders-library/timeouts-retries-and-backoff-with-jitter/) · [Google SRE Book ch. 22](https://sre.google/sre-book/addressing-cascading-failures/)

**Лицензирование: что считают и что принуждают**

- [HashiCorp Vault license](https://developer.hashicorp.com/vault/docs/license) · [client count](https://developer.hashicorp.com/vault/docs/concepts/client-count) · [Consul utilization reporting](https://developer.hashicorp.com/consul/docs/enterprise/license/utilization-reporting) · [BUSL](https://www.hashicorp.com/en/bsl)
- [Elastic License 2.0](https://www.elastic.co/licensing/elastic-license) · [Self-Managed Subscription Agreement (PDF)](https://www.elastic.co/pdf/elastic-self-managed-subscription-agreement-global-v103119-4.pdf) · [managing licenses](https://www.elastic.co/guide/en/kibana/master/managing-licenses.html)
- [Redis Software license keys](https://redis.io/docs/latest/operate/rs/clusters/configure/license-keys/) · [`/v1/license` REST](https://redis.io/docs/latest/operate/rs/references/rest-api/requests/license/)
- [Confluent Platform license](https://docs.confluent.io/platform/current/installation/license.html)
- [Grafana Enterprise licensing](https://grafana.com/docs/grafana/latest/administration/enterprise-licensing/)
- [GitLab quarterly reconciliation / true-up](https://docs.gitlab.com/subscriptions/quarterly_reconciliation/) · [licensed seats](https://docs.gitlab.com/subscriptions/manage_seats/) · [license file 10 % band](https://docs.gitlab.com/administration/license_file/)
- [Camunda 8 license key](https://docs.camunda.io/docs/self-managed/deployment/helm/configure/license-key/)
- [Portainer node licensing](https://www.portainer.io/renew-3-nodes-free-license-key)
- [Sentry self-hosted](https://develop.sentry.dev/self-hosted/) · [open.sentry.io/licensing](https://open.sentry.io/licensing/)
- [JetBrains License Vault floating licenses](https://www.jetbrains.com/help/ide-services/floating-licenses.html)
- [Unity Licensing Server admin](https://docs.unity.com/licensing/en-us/manual/ServerAdmin)
- [Tableau login-based licence management](https://help.tableau.com/current/server/en-us/license_lblm.htm)
- [10Duke Enterprise license models](https://docs.enterprise.10duke.com/admin-tools/configure-products-and-license-models/manage-license-models/define-settings-for-custom-license-models/)
- [F5 NGINX Plus subscription licenses](https://docs.nginx.com/solutions/about-subscription-licenses/getting-started/) · [`ngx_mgmt_module`](https://nginx.org/en/docs/ngx_mgmt_module.html)
- [Veeam: exceeding the license limit](https://helpcenter.veeam.com/docs/backup/vsphere/license_exceeding.html)
- [ISL Online pricing: hard limit vs soft limit](https://www.islonline.com/gb/en/pricing/)
- [CockroachDB licensing FAQ](https://docs.cockroachlabs.com/docs/stable/licensing-faqs)
- [Oracle Processor Core Factor Table](https://www.oracle.com/assets/processor-core-factor-table-070634.pdf) · [Partitioning Policy](https://www.oracle.com/assets/partitioning-070609.pdf)
- [Keygen: floating licenses](https://keygen.sh/docs/choosing-a-licensing-model/floating-licenses/) · [machines API](https://keygen.sh/docs/api/machines/) · [`keygen-sh/machineid`](https://github.com/keygen-sh/machineid)
- [Cryptlex: containers and VMs](https://docs.cryptlex.com/) · [LicenseSpring hardware ID](https://docs.licensespring.com/) · [Thales Sentinel LDK VM fingerprint schemes](https://docs.sentinel.thalesgroup.com/)
- [Distr: usage limits, seat counts and feature gates for self-hosted software](https://distr.sh/blog/license-key/)
- [Reprise RLM License Administration Manual](https://docs.reprisesoftware.com/) · [RLM disconnected operation (бюджет транзакций)](https://docs.reprisesoftware.com/docs/isv/disconnected-operation.html) — `min_checkout`, `hold`, `share=`, `soft_limit`, `min_remove`
- FlexNet Publisher 2022 R3 (11.19.2) License Administration Guide — `TIMEOUT`/`TIMEOUTALL`, `LINGER`, `OVERDRAFT`, `DUP_GROUP`, `lmremove`, ошибка −64; FLEXlm End User Manual §5.2.7, §6.7
- [X-Formation LM-X: `lmx_server_conf.c`](https://docs.x-formation.com/display/LMX/lmx_server_conf.c+file) · [GRACE](https://docs.x-formation.com/display/LMX/GRACE) — `GetClientTimeout` (5 мин, время компиляции), `MIN_USER_REMOVE_TIME`, `SOFTLIMIT`, `SHARE=HOST`
- [Thales Sentinel LDK: Defining License Terms (`Count Each`)](https://docs.sentinel.thalesgroup.com/ldk/LDKdocs/WebHelp/DefLicTerm.htm) · [Sentinel RMS `VLScleanupIssuedKeys`](https://docs.sentinel.thalesgroup.com/softwareandservices/rms/RMSDocumentation/VLSAPI/Content/PR/VLScleanupIssuedKeys.htm)
- Wibu CodeMeter Developer Guide 9.10 §3.1.10 — PIO Linger Time, Firm Security Box
- [Keygen Relay](https://keygen.sh/docs/relay/) · [Keygen policies (`overageStrategy`, `heartbeatCullStrategy`, resurrection)](https://keygen.sh/docs/api/policies/) · [Keygen changelog (гонка выбраковки при частом пульсе)](https://keygen.sh/changelog/)
- [Cryptlex: hosted floating licenses](https://cryptlex.com/docs/licensing-models/floating-licenses/hosted-floating-licenses) · [containers and virtual machines](https://cryptlex.com/docs/licensing-models/containers-and-virtual-machines) · [license templates](https://cryptlex.com/docs/license-management/license-templates)
- [Zentitle2: how activations work (лестница рангов)](https://docs.nalpeiron.com/zentitle2-docs/ui-entitlements/using-entitlements/how-activations-work) · [Overdraft Tracker](https://docs.nalpeiron.com/zentitle2-docs/premium-features/overdraft-tracker-basic)

**Удостоверение установки**

- [`machine-id(5)`](https://www.freedesktop.org/software/systemd/man/latest/machine-id.html) · [`sd_id128_get_machine_app_specific`](https://www.freedesktop.org/software/systemd/man/latest/sd_id128_get_machine.html)
- DMTF DSP0134 (SMBIOS) §7.2.1 · [`drivers/firmware/dmi-id.c`](https://github.com/torvalds/linux/blob/master/drivers/firmware/dmi-id.c)
- [RFC 7844 (Anonymity Profiles for DHCP Clients)](https://www.rfc-editor.org/rfc/rfc7844) · [`moby/.../netutils/utils.go`](https://github.com/moby/moby/blob/master/daemon/libnetwork/netutils/utils.go)
- TCG TPM 2.0 Library Part 1 §9.4.3, §9.5.3 · TCG «TPM 2.0 Keys for Device Identity and Attestation» §3.11, §10
- [Keylime security design](https://keylime.readthedocs.io/) · [SPIRE `aws_iid` node attestor](https://github.com/spiffe/spire/blob/main/doc/plugin_server_nodeattestor_aws_iid.md) · [«Solving the Bottom Turtle» (SPIFFE)](https://spiffe.io/book/)
- [Yandex Cloud: идентификационный документ ВМ](https://yandex.cloud/ru/docs/compute/operations/vm-info/get-identity-document) · [AWS instance identity documents](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/instance-identity-documents.html) · [Azure attested data](https://learn.microsoft.com/azure/virtual-machines/instance-metadata-service) · [GCP instance identity](https://cloud.google.com/compute/docs/instances/verifying-instance-identity)
- [OpenTelemetry `k8s.cluster.uid`](https://opentelemetry.io/docs/specs/semconv/resource/k8s/)
- [Microsoft Autopilot: VMs can't attest](https://learn.microsoft.com/autopilot/)

**Наше дерево (прочитано в коде, а не пересказано)**

- `prototype/licensing/store.py` — `_occupancy`, `_admission`, `capacity_admission`,
  `meter_if_allowed`, `issue_quantum`, `billable`, константы тарифов и резерва
- `prototype/licensing/server.py` — `/v1/meter`, `metered_too_recently`
- `prototype/pseudex/license.py` — `_ANSWER_CODES`, цикл продления, `_meter_once`
- `prototype/pseudex/audit.py::installation_id`
- `docs/metering-integrity.md` §4.3, §4.6, §5, §5.6, §8, §9
- `docs/tz-offline-license.md` §6, §10
- `docs/known-issues.md` Б26 … Б26sexies
- `research/2026-09-22-instance-liveness-and-slots.md` (замеры E1–E10)
- `research/2026-08-31-usage-billing-on-hostile-hardware.md` (кванты, Privacy Pass, аттестация)
