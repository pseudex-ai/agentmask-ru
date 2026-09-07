# Микроскоп — v4-live-small

троек: 261 · разобрано: 207 · исключено: 2

## Причины (по тройкам)

| причина | троек |
|---|---|
| other | 80 |
| derived-only | 59 |
| Б8-echo | 29 |
| leak-only | 12 |
| typo-normalised | 9 |
| partial-call | 4 |
| residual | 4 |
| Б9-span | 3 |
| control_erred | 3 |
| case-only | 2 |
| validate-refuse | 2 |

## Поля (по расходящимся полям)

| подпричина | полей |
|---|---|
| derived | 90 |
| absent:street | 39 |
| absent:phone | 39 |
| absent:gender | 32 |
| absent:building | 31 |
| absent:locality | 31 |
| absent:name | 31 |
| name_partial | 27 |
| extra:gender | 23 |
| extra:phone | 21 |
| name_case | 17 |
| extra:first_name | 15 |
| extra:last_name | 15 |
| absent:last_name | 14 |
| control_erred | 13 |
| absent:first_name | 11 |
| extra:street | 11 |
| absent:number | 10 |
| extra:birth_date | 10 |
| extra:middle_name | 10 |
| absent:city | 8 |
| absent:flat | 8 |
| absent:house | 8 |
| absent:initials | 8 |
| absent:name_latin | 8 |
| name_lemma | 8 |
| extra:age | 8 |
| extra:city | 7 |
| extra:flat | 7 |
| extra:house | 7 |
| extra:initials | 7 |
| extra:name_latin | 7 |
| loc_other | 7 |
| validated_refused | 7 |
| other/misderived | 7 |
| loc_street | 6 |
| absent:middle_name | 5 |
| extra:building | 4 |
| extra:locality | 4 |
| extra:name | 4 |
| absent:snils | 4 |
| absent:birth_date | 3 |
| absent:email | 3 |
| extra:number | 3 |
| loc_fake | 3 |
| absent:sflat | 3 |
| other/inflected | 3 |
| absent:series | 3 |
| extra:email | 2 |
| extra:porch | 2 |
| extra:sflat | 2 |
| absent:porch | 1 |
| extra:query | 1 |
| extra:cardholder | 1 |

## УТЕЧКИ В МОДЕЛЬ — 46 из 723 значений в сообщениях

| тип/регистр | значений |
|---|---|
| LOC/sloppy | 15 |
| PHONE/voice_raw | 12 |
| LOC/chat | 6 |
| LOC/voice_raw | 6 |
| DOB/voice_raw | 3 |
| SNILS/voice_itn | 2 |
| SNILS/sloppy | 1 |
| SNILS/chat | 1 |

| тройка | регистр | тип | значение | реплика |
|---|---|---|---|---|
| chain-003\|0 | voice_raw | PHONE | `восемь девятьсот семьдесят семь восемьсот девяно семь шееся…` | `девушка здравствуйте этоо полякова валентина ивановна хочу поменяять адрес доставки телефон восемь девятьсот …` |
| chain-003\|1 | voice_raw | PHONE | `восемь девятьсот семьдесят семь восемьсот девяно семь шееся…` | `девушка здравствуйте этоо полякова валентина ивановна хочу поменяять адрес доставки телефон восемь девятьсот …` |
| chain-003\|2 | voice_raw | PHONE | `восемь девятьсот семьдесят семь восемьсот девяно семь шееся…` | `девушка здравствуйте этоо полякова валентина ивановна хочу поменяять адрес доставки телефон восемь девятьсот …` |
| chain-038\|0 | chat | LOC | `базисная 152кв7` | `теперь базисная 152кв7` |
| chain-038\|1 | chat | LOC | `базисная 152кв7` | `теперь базисная 152кв7` |
| chain-038\|2 | chat | LOC | `базисная 152кв7` | `теперь базисная 152кв7` |
| compare-011\|0 | voice_raw | PHONE | `восемь девятьсот пятьдесят два двести шеесят пейсят два сем…` | `курьера на химзаводская три в корпус пять это в глазов наа имяя петра телефоон восемь девятьсот пятьдесят два…` |
| compare-011\|1 | voice_raw | PHONE | `восемь девятьсот пятьдесят два двести шеесят пейсят два сем…` | `курьера на химзаводская три в корпус пять это в глазов наа имяя петра телефоон восемь девятьсот пятьдесят два…` |
| compare-011\|2 | voice_raw | PHONE | `восемь девятьсот пятьдесят два двести шеесят пейсят два сем…` | `курьера на химзаводская три в корпус пять это в глазов наа имяя петра телефоон восемь девятьсот пятьдесят два…` |
| compare-014\|0 | sloppy | LOC | `вишёнвая 28` | `курьера на вишёнвая 28 это в крсанодар на имя марину телефон +79601068867` |
| compare-014\|1 | sloppy | LOC | `вишёнвая 28` | `курьера на вишёнвая 28 это в крсанодар на имя марину телефон +79601068867` |
| compare-014\|2 | sloppy | LOC | `вишёнвая 28` | `курьера на вишёнвая 28 это в крсанодар на имя марину телефон +79601068867` |
| compare-021\|0 | sloppy | LOC | `нидняя 59` | `курьера на нидняя 59 это в соравала на имя кирилла тлефон 8-909-528-76-24` |
| compare-021\|1 | sloppy | LOC | `нидняя 59` | `курьера на нидняя 59 это в соравала на имя кирилла тлефон 8-909-528-76-24` |
| compare-021\|2 | sloppy | LOC | `нидняя 59` | `курьера на нидняя 59 это в соравала на имя кирилла тлефон 8-909-528-76-24` |
| compare-034\|0 | voice_raw | LOC | `пушкна шестьдесят пять корпус один` | `курьераа на пушкна шестьдесят пять корпус один этоо в самара на имя петра телефон восемь девятьсот восемьдеся…` |
| compare-034\|1 | voice_raw | LOC | `пушкна шестьдесят пять корпус один` | `курьераа на пушкна шестьдесят пять корпус один этоо в самара на имя петра телефон восемь девятьсот восемьдеся…` |
| compare-034\|2 | voice_raw | LOC | `пушкна шестьдесят пять корпус один` | `курьераа на пушкна шестьдесят пять корпус один этоо в самара на имя петра телефон восемь девятьсот восемьдеся…` |
| correction-013\|0 | sloppy | LOC | `мяаковского 11 квартира 197` | `добрый курьера на мяаковского 11 квартира 197 ой нет правильно маяковского 163 квартира 197 это в сарапул это…` |
| correction-013\|1 | sloppy | LOC | `мяаковского 11 квартира 197` | `добрый курьера на мяаковского 11 квартира 197 ой нет правильно маяковского 163 квартира 197 это в сарапул это…` |
| correction-013\|2 | sloppy | LOC | `мяаковского 11 квартира 197` | `добрый курьера на мяаковского 11 квартира 197 ой нет правильно маяковского 163 квартира 197 это в сарапул это…` |
| correction-016\|0 | chat | LOC | `химзаводская 3кв170` | `курьера на адрес химзаводская 31 кв 170 стоп правильно химзаводская 3кв170 это в колпино это морозов леонид т…` |
| correction-016\|1 | chat | LOC | `химзаводская 3кв170` | `курьера на адрес химзаводская 31 кв 170 стоп правильно химзаводская 3кв170 это в колпино это морозов леонид т…` |
| correction-016\|2 | chat | LOC | `химзаводская 3кв170` | `курьера на адрес химзаводская 31 кв 170 стоп правильно химзаводская 3кв170 это в колпино это морозов леонид т…` |
| correction-018\|0 | voice_raw | PHONE | `восем девятьсот двадцать пяять семест двадцать триста четыр…` | `добрый день курьера на адрес кирочная двадцать пять квартира сто пятьдесят ой нет правильно кирочная сто семь…` |
| correction-018\|1 | voice_raw | PHONE | `восем девятьсот двадцать пяять семест двадцать триста четыр…` | `добрый день курьера на адрес кирочная двадцать пять квартира сто пятьдесят ой нет правильно кирочная сто семь…` |
| correction-018\|2 | voice_raw | PHONE | `восем девятьсот двадцать пяять семест двадцать триста четыр…` | `добрый день курьера на адрес кирочная двадцать пять квартира сто пятьдесят ой нет правильно кирочная сто семь…` |
| correction-030\|0 | voice_raw | LOC | `мончегорская трис три квартира пятьдесят шесть` | `алло курьера наа адрес мончегорская трис три квартира пятьдесят шесть ой нет правильно мончегрская дом сто во…` |
| correction-030\|0 | voice_raw | PHONE | `восемь девятьсот шестьдесят два восемест восемьдесят восемь…` | `алло курьера наа адрес мончегорская трис три квартира пятьдесят шесть ой нет правильно мончегрская дом сто во…` |
| correction-030\|1 | voice_raw | LOC | `мончегорская трис три квартира пятьдесят шесть` | `алло курьера наа адрес мончегорская трис три квартира пятьдесят шесть ой нет правильно мончегрская дом сто во…` |
| correction-030\|1 | voice_raw | PHONE | `восемь девятьсот шестьдесят два восемест восемьдесят восемь…` | `алло курьера наа адрес мончегорская трис три квартира пятьдесят шесть ой нет правильно мончегрская дом сто во…` |
| correction-030\|2 | voice_raw | LOC | `мончегорская трис три квартира пятьдесят шесть` | `алло курьера наа адрес мончегорская трис три квартира пятьдесят шесть ой нет правильно мончегрская дом сто во…` |
| correction-030\|2 | voice_raw | PHONE | `восемь девятьсот шестьдесят два восемест восемьдесят восемь…` | `алло курьера наа адрес мончегорская трис три квартира пятьдесят шесть ой нет правильно мончегрская дом сто во…` |
| correction-031\|0 | sloppy | LOC | `новвя 81 кв 6` | `добрый курьерра на адрес новвя 81 кв 6 нет не так правилньо нвоая 53кв6 это в сарапул это битюков олег телефо…` |
| correction-031\|0 | sloppy | LOC | `нвоая 53кв6` | `добрый курьерра на адрес новвя 81 кв 6 нет не так правилньо нвоая 53кв6 это в сарапул это битюков олег телефо…` |
| correction-031\|1 | sloppy | LOC | `новвя 81 кв 6` | `добрый курьерра на адрес новвя 81 кв 6 нет не так правилньо нвоая 53кв6 это в сарапул это битюков олег телефо…` |
| correction-031\|1 | sloppy | LOC | `нвоая 53кв6` | `добрый курьерра на адрес новвя 81 кв 6 нет не так правилньо нвоая 53кв6 это в сарапул это битюков олег телефо…` |
| correction-031\|2 | sloppy | LOC | `новвя 81 кв 6` | `добрый курьерра на адрес новвя 81 кв 6 нет не так правилньо нвоая 53кв6 это в сарапул это битюков олег телефо…` |
| correction-031\|2 | sloppy | LOC | `нвоая 53кв6` | `добрый курьерра на адрес новвя 81 кв 6 нет не так правилньо нвоая 53кв6 это в сарапул это битюков олег телефо…` |
| derive-020\|0 | voice_raw | DOB | `двадцать первое сентября восьмидесятого года` | `добрыый день запишите к кардиологу миллера валерия леонидовича родилсяя двадцать первое сентября восьмидесято…` |
| derive-020\|1 | voice_raw | DOB | `двадцать первое сентября восьмидесятого года` | `добрыый день запишите к кардиологу миллера валерия леонидовича родилсяя двадцать первое сентября восьмидесято…` |
| derive-020\|2 | voice_raw | DOB | `двадцать первое сентября восьмидесятого года` | `добрыый день запишите к кардиологу миллера валерия леонидовича родилсяя двадцать первое сентября восьмидесято…` |
| validate-017\|0 | sloppy | SNILS | `20304105882` | `здрасте сверьте мои данные силс 20304105882 паспорт 1812759266 соколова анна игоревна` |
| validate-020\|0 | voice_itn | SNILS | `655-971-771 57` | `добрый день сверьте мои данные снилс 655-971-771 57 паспорт 9414 887065 миллер валерий леонидович` |
| validate-032\|0 | voice_itn | SNILS | `578-890-119 63` | `сверьте мои данные снилс 578-890-119 63 паспорт 4114 285851 лебедев максим константинович` |
| validate-035\|0 | chat | SNILS | `688-606-727 65` | `привет сверьте мои данные снилс 688-606-727 65 паспорт 4617 202966 соколова анна игоревна` |

## chain-000|1 · chain · sloppy · L1 = · L3 ≠ · C′≈C нет · причина: **derived-only**
- USER[1]: привет это букин сергей иванович хочу поменять ардес доставки телефон 89164021187
- USER[2]: теперь переулок барышникова 7 кв 111
- USER[3]: и пришлите смс с подтверждением
- seen NAME `букин сергей иванович` → `Тихонов Борис Дмитриевич`
- seen PHONE `89164021187` → `+79442068161`
- seen LOC `переулок барышникова 7 кв 111` → `переулок Тополиный 55, кв. 126`
- C: `crm_find_contact` {'query': {'phone': '+79164021187'}}
- C: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Букин', 'first_name': 'Сергей', 'middle_name': 'Иванович', 'initials': 'С.И.', 'name_latin': 'Bukin Sergey', 'phone': '+79164021187', 'email': 'bukin76@yandex.…
- C: `notify_sms` {'number': '+79164021187', 'text': 'Букин С.И., адрес доставки успешно изменён на: г. Сарапул, пер. Барышникова, д. 7, кв. 111.', 'sign': 'Dostavka'}
- I: `crm_find_contact` written={'query': {'phone': '+79442068161'}} → restored={'query': {'phone': '+79164021187'}}
- I: `crm_upsert_contact` written={'id': 'c-1', 'contact': {'last_name': 'Тихонов', 'first_name': 'Борис', 'middle_name': 'Дмитриевич', 'phone': '+79442068161', 'email': 'jkzvdyxm@example.ru', 'birth_date': '1965-02-03', 'initials': 'Б.Д.', 'name_latin': 'Tikhonov Boris', 'gender': 'M', 'addr… → restored={'id': 'c-1', 'contact': {'last_name': 'букин', 'first_name': 'сергей', 'middle_name': 'иванович', 'phone': '+79164021187', 'email': 'bukin76@yandex.ru', 'birth_date': '1987-03-14', 'initials': 'С.И.', 'name_latin': 'Bukin Sergei', 'gender': 'M', 'address': {…
- I: `notify_sms` written={'number': '+79442068161', 'sign': 'Dostavka', 'text': 'Здравствуйте, Борис Дмитриевич! Ваш адрес доставки успешно изменён на: г. Сарапул, пер. Тополиный, д. 55, кв. 126.'} → restored={'number': '+79164021187', 'sign': 'Dostavka', 'text': 'Здравствуйте, сергей иванович! Ваш адрес доставки успешно изменён на: г. Сарапул, пер. барышникова, д. 7, кв. 111.'}
- C′: `crm_find_contact` {'query': {'phone': '+79164021187'}}
- C′: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Букин', 'first_name': 'Сергей', 'middle_name': 'Иванович', 'initials': 'С.И.', 'name_latin': 'Bukin Sergei', 'phone': '+79164021187', 'email': 'bukin76@yandex.…
- C′: `notify_sms` {'number': '+79164021187', 'sign': 'Dostavka', 'text': 'Здравствуйте, Сергей Иванович! Адрес доставки успешно изменён на: г. Сарапул, пер. Барышникова, д. 7, кв. 111.'}
- FIELD `crm_upsert_contact.contact.gender` [extra → extra:gender] C=`` I=`M`
- FIELD `crm_upsert_contact.contact.name_latin` [derived/unverifiable → derived] C=`Bukin Sergey` I=`Bukin Sergei`
- REPLY I: СМС с подтверждением отправлено на номер 89164021187. Если есть ещё вопросы — обращайтесь! 😊

## chain-003|0 · chain · voice_raw · L1 = · L3 ≠ · C′≈C да · причина: **derived-only**
- USER[1]: девушка здравствуйте этоо полякова валентина ивановна хочу поменяять адрес доставки телефон восемь девятьсот семьдесят семь восемьсот девяно семь шеесят два двадцать шесть
- USER[2]: записывайте маяковского дом двадцать три квартира сто восемь
- USER[3]: ии смс пришлите чтоо адреес поменяли
- seen NAME `полякова валентина ивановна` → `Устинова Надежда Алексеевна`
- **LEAK** PHONE `восемь девятьсот семьдесят семь восемьсот девяно семь шеесят два двадцать шесть` — модель видела настоящее значение
- seen LOC `маяковского дом двадцать три квартира сто восемь` → `улица Черёмуховая 1, кв. 92`
- C: `crm_find_contact` {'query': {'phone': '+79778976226'}}
- C: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Полякова', 'first_name': 'Валентина', 'middle_name': 'Ивановна', 'initials': 'В.И.', 'name_latin': 'Polyakova Valentina', 'phone': '+79778976226', 'email': 'po…
- C: `notify_sms` {'number': '+79778976226', 'text': 'Валентина Ивановна, ваш адрес доставки успешно изменён на: г. Самара, ул. Маяковского, д. 23, кв. 108.', 'sign': 'Dostavka'}
- I: `crm_find_contact` written={'query': {'phone': '+79778976226'}} → restored={'query': {'phone': '+79778976226'}}
- I: `crm_upsert_contact` written={'id': 'c-1', 'contact': {'last_name': 'Устинова', 'first_name': 'Надежда', 'middle_name': 'Алексеевна', 'initials': 'Н.А.', 'name_latin': 'Ustinova Nadezhda', 'phone': '+79929312413', 'email': 'nexjbndr@example.ru', 'birth_date': '2004-08-26', 'gender': 'F',… → restored={'id': 'c-1', 'contact': {'last_name': 'полякова', 'first_name': 'валентина', 'middle_name': 'ивановна', 'initials': 'В.И.', 'name_latin': 'Poliakova Valentina', 'phone': '+79778976226', 'email': 'polyakova72@mail.ru', 'birth_date': '1974-10-08', 'gender': 'F…
- I: `notify_sms` written={'number': '+79929312413', 'text': 'Надежда Алексеевна, адрес доставки в вашей карточке успешно изменён на: г. Самара, ул. Черёмуховая, д. 1, кв. 92.', 'sign': 'Dostavka'} → restored={'number': '+79778976226', 'text': 'валентина ивановна, адрес доставки в вашей карточке успешно изменён на: г. Самара, маяковского, д. 23, кв. 108.', 'sign': 'Dostavka'}
- C′: `crm_find_contact` {'query': {'phone': '+79778976226'}}
- C′: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Полякова', 'first_name': 'Валентина', 'middle_name': 'Ивановна', 'initials': 'В.И.', 'name_latin': 'Polyakova Valentina', 'phone': '+79778976226', 'email': 'po…
- C′: `notify_sms` {'number': '+79778976226', 'text': 'Валентина Ивановна, адрес доставки успешно изменён: г. Самара, ул. Маяковского, д. 23, кв. 108. Если это были не вы, свяжитесь с нами.', 'sign': 'Dostavka'}
- FIELD `crm_upsert_contact.contact.name_latin` [derived/unverifiable → derived] C=`Polyakova Valentina` I=`Poliakova Valentina`
- REPLY I: СМС отправлено! 📱 Проверяйте телефон, валентина ивановна. Если ещё что-то понадобится — обращайтесь, всего доброго!

## chain-003|1 · chain · voice_raw · L1 = · L3 ≠ · C′≈C нет · причина: **derived-only**
- USER[1]: девушка здравствуйте этоо полякова валентина ивановна хочу поменяять адрес доставки телефон восемь девятьсот семьдесят семь восемьсот девяно семь шеесят два двадцать шесть
- USER[2]: записывайте маяковского дом двадцать три квартира сто восемь
- USER[3]: ии смс пришлите чтоо адреес поменяли
- seen NAME `полякова валентина ивановна` → `Панова Нина Валерьевна`
- **LEAK** PHONE `восемь девятьсот семьдесят семь восемьсот девяно семь шеесят два двадцать шесть` — модель видела настоящее значение
- seen LOC `маяковского дом двадцать три квартира сто восемь` → `улица Тополиная 196, кв. 164`
- C: `crm_find_contact` {'query': {'phone': '+79778976226'}}
- C: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Полякова', 'first_name': 'Валентина', 'middle_name': 'Ивановна', 'phone': '+79778976226', 'email': 'polyakova72@mail.ru', 'birth_date': '1974-10-08', 'initials…
- C: `notify_sms` {'number': '+79778976226', 'text': 'Валентина Ивановна, ваш адрес доставки успешно изменён: г. Самара, ул. Маяковского, д. 23, кв. 108. Если это были не вы, позвоните нам.', 'sign': 'Dostavka'}
- I: `crm_find_contact` written={'query': {'phone': '+79778976226'}} → restored={'query': {'phone': '+79778976226'}}
- I: `crm_upsert_contact` written={'id': 'c-1', 'contact': {'last_name': 'Панова', 'first_name': 'Нина', 'middle_name': 'Валерьевна', 'initials': 'Н.В.', 'name_latin': 'Panova Nina', 'phone': '+79778976226', 'email': 'sohvrfxo@example.ru', 'birth_date': '2021-08-27', 'address': {'city': 'Сама… → restored={'id': 'c-1', 'contact': {'last_name': 'полякова', 'first_name': 'валентина', 'middle_name': 'ивановна', 'initials': 'В.И.', 'name_latin': 'Poliakova Valentina', 'phone': '+79778976226', 'email': 'polyakova72@mail.ru', 'birth_date': '1974-10-08', 'address': {…
- I: `notify_sms` written={'number': '+79778976226', 'text': 'Нина Валерьевна, ваш адрес доставки успешно изменён на: г. Самара, ул. Тополиная, д. 196, кв. 164.', 'sign': 'Dostavka'} → restored={'number': '+79778976226', 'text': 'валентина ивановна, ваш адрес доставки успешно изменён на: г. Самара, маяковского, д. 23, кв. 108.', 'sign': 'Dostavka'}
- C′: `crm_find_contact` {'query': {'phone': '+79778976226'}}
- C′: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Полякова', 'first_name': 'Валентина', 'middle_name': 'Ивановна', 'phone': '+79778976226', 'email': 'polyakova72@mail.ru', 'birth_date': '1974-10-08', 'initials…
- C′: `notify_sms` {'number': '+79778976226', 'text': 'Валентина Ивановна, адрес доставки успешно изменён: г. Самара, ул. Маяковского, д. 23, кв. 108.', 'sign': 'Dostavka'}
- FIELD `crm_upsert_contact.contact.name_latin` [derived/unverifiable → derived] C=`Polyakova Valentina` I=`Poliakova Valentina`
- REPLY I: СМС отправлено! 📱 Всё готово, валентина ивановна. Если будут ещё вопросы — обращайтесь, всего доброго!

## chain-003|2 · chain · voice_raw · L1 = · L3 ≠ · C′≈C да · причина: **derived-only**
- USER[1]: девушка здравствуйте этоо полякова валентина ивановна хочу поменяять адрес доставки телефон восемь девятьсот семьдесят семь восемьсот девяно семь шеесят два двадцать шесть
- USER[2]: записывайте маяковского дом двадцать три квартира сто восемь
- USER[3]: ии смс пришлите чтоо адреес поменяли
- seen NAME `полякова валентина ивановна` → `Рыбакова Снежана Сергеевна`
- **LEAK** PHONE `восемь девятьсот семьдесят семь восемьсот девяно семь шеесят два двадцать шесть` — модель видела настоящее значение
- seen LOC `маяковского дом двадцать три квартира сто восемь` → `улица Вишнёвая 103, кв. 32`
- C: `crm_find_contact` {'query': {'phone': '+79778976226'}}
- C: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Полякова', 'first_name': 'Валентина', 'middle_name': 'Ивановна', 'phone': '+79778976226', 'email': 'polyakova72@mail.ru', 'birth_date': '1974-10-08', 'gender':…
- C: `notify_sms` {'number': '+79778976226', 'text': 'Валентина Ивановна, адрес доставки в вашей карточке успешно изменён на: г. Самара, ул. Маяковского, д. 23, кв. 108. Если это сделали не вы — свяжитесь с нами.', 's…
- I: `crm_find_contact` written={'query': {'phone': '+79778976226'}} → restored={'query': {'phone': '+79778976226'}}
- I: `crm_upsert_contact` written={'id': 'c-1', 'contact': {'last_name': 'Рыбакова', 'first_name': 'Снежана', 'middle_name': 'Сергеевна', 'initials': 'С.С.', 'name_latin': 'Rybakova Snezhana', 'phone': '+79778976226', 'address': {'city': 'Самара', 'street': 'Вишнёвая', 'house': '103', 'flat':… → restored={'id': 'c-1', 'contact': {'last_name': 'полякова', 'first_name': 'валентина', 'middle_name': 'ивановна', 'initials': 'В.И.', 'name_latin': 'Poliakova Valentina', 'phone': '+79778976226', 'address': {'city': 'Самара', 'street': 'маяковского', 'house': '23', 'f…
- I: `notify_sms` written={'number': '+79778976226', 'sign': 'Dostavka', 'text': 'Снежана Сергеевна, адрес доставки в вашей карточке успешно изменён на: г. Самара, ул. Вишнёвая, д. 103, кв. 32. Если это были не вы, пожалуйста, свяжитесь с нами.'} → restored={'number': '+79778976226', 'sign': 'Dostavka', 'text': 'валентина ивановна, адрес доставки в вашей карточке успешно изменён на: г. Самара, маяковского, д. 23, кв. 108. Если это были не вы, пожалуйста, свяжитесь с нами.'}
- C′: `crm_find_contact` {'query': {'last_name': 'Полякова'}}
- C′: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Полякова', 'first_name': 'Валентина', 'middle_name': 'Ивановна', 'initials': 'В.И.', 'name_latin': 'Polyakova Valentina', 'phone': '+79778976226', 'email': 'po…
- C′: `notify_sms` {'number': '+79778976226', 'text': 'Здравствуйте, Валентина Ивановна! Адрес доставки в вашей карточке успешно изменён на: г. Самара, ул. Маяковского, д. 23, кв. 108. Если возникнут вопросы — звоните …
- FIELD `crm_upsert_contact.contact.birth_date` [absent → absent:birth_date] C=`1974-10-08` I=``
- FIELD `crm_upsert_contact.contact.email` [absent → absent:email] C=`polyakova72@mail.ru` I=``
- FIELD `crm_upsert_contact.contact.gender` [absent → absent:gender] C=`F` I=``
- FIELD `crm_upsert_contact.contact.name_latin` [derived/unverifiable → derived] C=`Polyakova Valentina` I=`Poliakova Valentina`
- REPLY I: СМС отправлено, валентина ивановна! 📱 Скоро получите сообщение с подтверждением смены адреса. Если ещё что-то понадобится — обращайтесь!

## chain-004|0 · chain · voice_raw · L1 ≠ · L3 ≠ · C′≈C нет · причина: **other**
- USER[1]: добрыый деень этоо захаров владислав юрьевич хочу поменять адресто доставки телефоон восемь девятьсот пятьдесят восемесят ноль восемь восемьдесят восемь один
- USER[2]: теперь бульвар репина сорок квартира двести сорок восемь
- USER[3]: ии смс пришлитее что адрес поменяли
- seen NAME `захаров владислав юрьевич` → `Сазонов Глеб Романович`
- seen PHONE `восемь девятьсот пятьдесят восемесят ноль восемь восемьдесят восемь один` → `+79051341009`
- seen LOC `бульвар репина сорок квартира двести сорок восемь` → `Озёрный бульвар 123, кв. 104`
- C: `crm_find_contact` {'query': {'phone': '+79505800881'}}
- C: `crm_find_contact` {'query': {'last_name': 'Захаров'}}
- C: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Захаров', 'first_name': 'Владислав', 'middle_name': 'Юрьевич', 'initials': 'В.Ю.', 'name_latin': 'Zakharov Vladislav', 'phone': '+79508008881', 'email': 'zahar…
- C: `notify_sms` {'number': '+79508008881', 'text': 'Здравствуйте, Владислав Юрьевич! Ваш адрес доставки успешно изменён: г. Колпино, бульвар Репина, д. 40, кв. 248.', 'sign': 'Dostavka'}
- I: `crm_find_contact` written={'query': {'phone': '+79051341009'}} → restored={'query': {'phone': '+79508008881'}}
- I: `crm_upsert_contact` written={'id': 'c-1', 'contact': {'last_name': 'Сазонов', 'first_name': 'Глеб', 'middle_name': 'Романович', 'initials': 'Г.Р.', 'name_latin': 'Sazonov Gleb', 'phone': '+79051341009', 'email': 'jdzgezib@example.ru', 'birth_date': '1978-06-06', 'address': {'city': 'Кол… → restored={'id': 'c-1', 'contact': {'last_name': 'захаров', 'first_name': 'владислав', 'middle_name': 'юрьевич', 'initials': 'В.Ю.', 'name_latin': 'Zakharov Vladislav', 'phone': '+79508008881', 'email': 'zaharov97@list.ru', 'birth_date': '1997-06-17', 'address': {'city…
- I: `notify_sms` written={'number': '+79051341009', 'text': 'Глеб Романович, адрес доставки успешно изменён на: г. Колпино, бул. Озёрный, д. 123, кв. 104. Если это были не вы, свяжитесь с нами.', 'sign': 'Dostavka'} → restored={'number': '+79508008881', 'text': 'владислав юрьевич, адрес доставки успешно изменён на: г. Колпино, бул. репина, д. 40, кв. 248. Если это были не вы, свяжитесь с нами.', 'sign': 'Dostavka'}
- C′: `crm_find_contact` {'query': {'phone': '+79508008881'}}
- C′: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Захаров', 'first_name': 'Владислав', 'middle_name': 'Юрьевич', 'initials': 'В.Ю.', 'name_latin': 'Zakharov Vladislav', 'phone': '+79508008881', 'email': 'zahar…
- C′: `notify_sms` {'number': '+79508008881', 'text': 'Владислав Юрьевич, адрес доставки в вашей карточке успешно изменён на: г. Колпино, бульвар Репина, д. 40, кв. 248. Если это были не вы — свяжитесь с нами.', 'sign'…
- FIELD `crm_find_contact.query.phone` [control_erred/i4 → control_erred] C=`+79505800881` I=`+79508008881` · контроль ошибся; шлюз восстановил эталон корпуса
- FIELD `crm_find_contact.query.last_name` [absent → absent:last_name] C=`Захаров` I=``
- FIELD `crm_upsert_contact.contact.gender` [absent → absent:gender] C=`M` I=``
- REPLY I: СМС отправлено! 📱 владислав юрьевич получит уведомление об изменении адреса на номер восемь девятьсот пятьдесят восемесят ноль восемь восемьдесят восемь один. Если нужна ещё какая-то помощь — обращайтесь!

## chain-004|1 · chain · voice_raw · L1 = · L3 ≠ · C′≈C нет · причина: **other**
- USER[1]: добрыый деень этоо захаров владислав юрьевич хочу поменять адресто доставки телефоон восемь девятьсот пятьдесят восемесят ноль восемь восемьдесят восемь один
- USER[2]: теперь бульвар репина сорок квартира двести сорок восемь
- USER[3]: ии смс пришлитее что адрес поменяли
- seen NAME `захаров владислав юрьевич` → `Котов Филипп Ярославович`
- seen PHONE `восемь девятьсот пятьдесят восемесят ноль восемь восемьдесят восемь один` → `+79367635627`
- seen LOC `бульвар репина сорок квартира двести сорок восемь` → `Сиреневый бульвар 89, кв. 1`
- C: `crm_find_contact` {'query': {'last_name': 'Захаров'}}
- C: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Захаров', 'first_name': 'Владислав', 'middle_name': 'Юрьевич', 'initials': 'В.Ю.', 'name_latin': 'Zakharov Vladislav', 'phone': '+79508008881', 'email': 'zahar…
- C: `notify_sms` {'number': '+79508008881', 'sign': 'Dostavka', 'text': 'Владислав Юрьевич, адрес доставки в вашей карточке изменён на: г. Колпино, бульвар Репина, д. 40, кв. 248. Если это были не вы, свяжитесь с нам…
- I: `crm_find_contact` written={'query': {'phone': '+79367635627'}} → restored={'query': {'phone': '+79508008881'}}
- I: `crm_upsert_contact` written={'id': 'c-1', 'contact': {'last_name': 'Котов', 'first_name': 'Филипп', 'middle_name': 'Ярославович', 'phone': '+79367635627', 'email': 'kkvpicpy@example.ru', 'birth_date': '2007-12-04', 'initials': 'Ф.Я.', 'name_latin': 'Kotov Filipp', 'gender': 'M', 'addres… → restored={'id': 'c-1', 'contact': {'last_name': 'захаров', 'first_name': 'владислав', 'middle_name': 'юрьевич', 'phone': '+79508008881', 'email': 'zaharov97@list.ru', 'birth_date': '1997-06-17', 'initials': 'В.Ю.', 'name_latin': 'Zakharov Vladislav', 'gender': 'M', 'a…
- I: `notify_sms` written={'number': '+79367635627', 'text': 'Филипп Ярославович, адрес доставки в вашей карточке успешно изменён на: г. Колпино, Сиреневый бульвар, д. 89, кв. 1.', 'sign': 'Dostavka'} → restored={'number': '+79508008881', 'text': 'владислав юрьевич, адрес доставки в вашей карточке успешно изменён на: г. Колпино, репина бульвар, д. 40, кв. 248.', 'sign': 'Dostavka'}
- C′: `crm_find_contact` {'query': {'last_name': 'Захаров'}}
- C′: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Захаров', 'first_name': 'Владислав', 'middle_name': 'Юрьевич', 'initials': 'В.Ю.', 'name_latin': 'Zakharov Vladislav', 'phone': '+79508008881', 'email': 'zahar…
- C′: `notify_sms` {'number': '+79508008881', 'text': 'Владислав Юрьевич, адрес доставки в вашем профиле успешно изменён на: г. Колпино, бульвар Репина, д. 40, кв. 248.', 'sign': 'Dostavka'}
- FIELD `crm_find_contact.query.last_name` [absent → absent:last_name] C=`Захаров` I=``
- FIELD `crm_find_contact.query.phone` [extra → extra:phone] C=`` I=`+79508008881`
- REPLY I: СМС отправлено на номер восемь девятьсот пятьдесят восемесят ноль восемь восемьдесят восемь один! 📱 Если что-то ещё нужно — обращайтесь, всего доброго!

## chain-004|2 · chain · voice_raw · L1 = · L3 ≠ · C′≈C нет · причина: **derived-only**
- USER[1]: добрыый деень этоо захаров владислав юрьевич хочу поменять адресто доставки телефоон восемь девятьсот пятьдесят восемесят ноль восемь восемьдесят восемь один
- USER[2]: теперь бульвар репина сорок квартира двести сорок восемь
- USER[3]: ии смс пришлитее что адрес поменяли
- seen NAME `захаров владислав юрьевич` → `Мещеряков Мирон Романович`
- seen PHONE `восемь девятьсот пятьдесят восемесят ноль восемь восемьдесят восемь один` → `+79111137789`
- seen LOC `бульвар репина сорок квартира двести сорок восемь` → `Мятный бульвар 1, кв. 178`
- C: `crm_find_contact` {'query': {'last_name': 'Захаров'}}
- C: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Захаров', 'first_name': 'Владислав', 'middle_name': 'Юрьевич', 'initials': 'В.Ю.', 'name_latin': 'Zakharov Vladislav', 'phone': '+79508008881', 'email': 'zahar…
- C: `notify_sms` {'number': '+79508008881', 'text': 'Владислав Юрьевич, адрес доставки в вашей карточке успешно изменён на: г. Колпино, бульвар Репина, д. 40, кв. 248.', 'sign': 'Dostavka'}
- I: `crm_find_contact` written={'query': {'phone': '+79111137789'}} → restored={'query': {'phone': '+79508008881'}}
- I: `crm_upsert_contact` written={'id': 'c-1', 'contact': {'last_name': 'Мещеряков', 'first_name': 'Мирон', 'middle_name': 'Романович', 'phone': '+79111137789', 'email': 'binbtqum@example.ru', 'birth_date': '2021-02-24', 'initials': 'М.Р.', 'name_latin': 'Meshcheryakov Miron', 'address': {'c… → restored={'id': 'c-1', 'contact': {'last_name': 'захаров', 'first_name': 'владислав', 'middle_name': 'юрьевич', 'phone': '+79508008881', 'email': 'zaharov97@list.ru', 'birth_date': '1997-06-17', 'initials': 'В.Ю.', 'name_latin': 'Meshcheryakov Vladislav', 'address': {…
- I: `notify_sms` written={'number': '+79111137789', 'text': 'Мирон Романович, адрес доставки в вашей карточке успешно изменён на: г. Колпино, Мятный бульвар, д. 1, кв. 178. Если это были не вы — свяжитесь с нами.', 'sign': 'Dostavka'} → restored={'number': '+79508008881', 'text': 'владислав юрьевич, адрес доставки в вашей карточке успешно изменён на: г. Колпино, репина бульвар, д. 40, кв. 248. Если это были не вы — свяжитесь с нами.', 'sign': 'Dostavka'}
- C′: `crm_find_contact` {'query': {'phone': '+79505800881'}}
- C′: `crm_find_contact` {'query': {'last_name': 'Захаров'}}
- C′: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Захаров', 'first_name': 'Владислав', 'middle_name': 'Юрьевич', 'initials': 'В.Ю.', 'name_latin': 'Zakharov Vladislav', 'phone': '+79508008881', 'email': 'zahar…
- C′: `notify_sms` {'number': '+79508008881', 'text': 'Владислав Юрьевич, ваш адрес доставки успешно изменён на: г. Колпино, бульвар Репина, д. 40, кв. 248. Если это были не вы, пожалуйста, свяжитесь с нами.', 'sign': …
- FIELD `crm_find_contact.query.last_name` [absent → absent:last_name] C=`Захаров` I=``
- FIELD `crm_find_contact.query.phone` [extra → extra:phone] C=`` I=`+79508008881`
- FIELD `crm_upsert_contact.contact.gender` [absent → absent:gender] C=`M` I=``
- FIELD `crm_upsert_contact.contact.name_latin` [derived/unverifiable → derived] C=`Zakharov Vladislav` I=`Meshcheryakov Vladislav`
- REPLY I: СМС отправлено на номер восемь девятьсот пятьдесят восемесят ноль восемь восемьдесят восемь один! 📱 Если нужна ещё какая-то помощь — обращайтесь!

## chain-008|0 · chain · sloppy · L1 = · L3 ≠ · C′≈C нет · причина: **other**
- USER[1]: это громов артём витальевич хчоу поменять адрес доставки телефон 8-925-011-15-03
- USER[2]: записывйате тельмана 94 кв 56
- USER[3]: и отпарвьте мне смс что всё запсиали
- seen NAME `громов артём витальевич` → `Фомин Михаил Алексеевич`
- seen PHONE `8-925-011-15-03` → `+79868198810`
- seen LOC `тельмана 94 кв 56` → `улицы Кедровой 192, кв. 161`
- C: `crm_find_contact` {'query': {'phone': '+79250111503'}}
- C: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Громов', 'first_name': 'Артём', 'middle_name': 'Витальевич', 'initials': 'А.В.', 'name_latin': 'Gromov Artem', 'phone': '+79250111503', 'email': 'gromov94@yand…
- C: `notify_sms` {'number': '+79250111503', 'text': 'Артём Витальевич, ваш адрес доставки успешно обновлён: г. Самара, ул. Тельмана, д. 94, кв. 56. Если что-то не так — свяжитесь с нами.', 'sign': 'Dostavka'}
- I: `crm_find_contact` written={'query': {'phone': '+79868198810'}} → restored={'query': {'phone': '+79250111503'}}
- I: `crm_upsert_contact` written={'id': 'c-1', 'contact': {'last_name': 'громов', 'first_name': 'Михаил', 'middle_name': 'Алексеевич', 'phone': '+79868198810', 'email': 'mvxwhiwl@example.ru', 'birth_date': '2017-03-05', 'initials': 'М.А.', 'name_latin': 'Gromov Mikhail', 'address': {'city': … → restored={'id': 'c-1', 'contact': {'last_name': 'громов', 'first_name': 'артём', 'middle_name': 'витальевич', 'phone': '+79250111503', 'email': 'gromov94@yandex.ru', 'birth_date': '1987-01-14', 'initials': 'А.В.', 'name_latin': 'Gromov Artem', 'address': {'city': 'сам…
- I: `notify_sms` written={'number': '+79868198810', 'text': 'Михаил Алексеевич, ваш адрес доставки успешно обновлён: г. Самара, ул. Кедровая, д. 192, кв. 161.', 'sign': 'Dostavka'} → restored={'number': '+79250111503', 'text': 'артём витальевич, ваш адрес доставки успешно обновлён: г. Самара, тельмана, д. 94, кв. 56.', 'sign': 'Dostavka'}
- C′: `crm_find_contact` {'query': {'phone': '+79250111503'}}
- C′: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Громов', 'first_name': 'Артём', 'middle_name': 'Витальевич', 'initials': 'А.В.', 'name_latin': 'Gromov Artyom', 'phone': '+79250111503', 'email': 'gromov94@yan…
- C′: `notify_sms` {'number': '+79250111503', 'text': 'Артём Витальевич, ваш адрес доставки успешно обновлён: г. Самара, ул. Тельмана, д. 94, кв. 56. Если что-то не так — свяжитесь с нами.', 'sign': 'Dostavka'}
- FIELD `crm_upsert_contact.contact.gender` [absent → absent:gender] C=`M` I=``
- REPLY I: Понял, подтверждаете карточку Громова — обновляю адрес и отправляю СМС одновременно! Всё готово! ✅ - **Адрес в CRM обновлён:** г. Самара, тельмана 94 кв 56 - **СМС отправлено** на номер 8-925-011-15-03

## chain-008|1 · chain · sloppy · L1 ≠ · L3 ≠ · C′≈C нет · причина: **Б8-echo**
- USER[1]: это громов артём витальевич хчоу поменять адрес доставки телефон 8-925-011-15-03
- USER[2]: записывйате тельмана 94 кв 56
- USER[3]: и отпарвьте мне смс что всё запсиали
- seen NAME `громов артём витальевич` → `Лебедев Валерий Сергеевич`
- seen PHONE `8-925-011-15-03` → `+79130826172`
- seen LOC `тельмана 94 кв 56` → `улицы Каштановой 199, кв. 143`
- C: `crm_find_contact` {'query': {'phone': '+79250111503'}}
- C: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Громов', 'first_name': 'Артём', 'middle_name': 'Витальевич', 'initials': 'А.В.', 'name_latin': 'Gromov Artyom', 'phone': '+79250111503', 'email': 'gromov94@yan…
- C: `notify_sms` {'number': '+79250111503', 'text': 'Артём Витальевич, ваш адрес доставки успешно обновлён: г. Самара, ул. Тельмана, д. 94, кв. 56.', 'sign': 'Dostavka'}
- I: `crm_find_contact` written={'query': {'phone': '+79130826172'}} → restored={'query': {'phone': '+79250111503'}}
- C′: `crm_find_contact` {'query': {'phone': '+79250111503'}}
- C′: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Громов', 'first_name': 'Артём', 'middle_name': 'Витальевич', 'initials': 'А.В.', 'name_latin': 'Gromov Artem', 'phone': '+79250111503', 'email': 'gromov94@yand…
- C′: `notify_sms` {'number': '+79250111503', 'text': 'Артём Витальевич, ваш адрес доставки успешно обновлён: г. Самара, ул. Тельмана, д. 94, кв. 56. Если есть вопросы — свяжитесь с нами.', 'sign': 'Dostavka'}
- FIELD `crm_upsert_contact.contact.address.city` [absent → absent:city] C=`Самара` I=``
- FIELD `crm_upsert_contact.contact.address.flat` [absent → absent:flat] C=`56` I=``
- FIELD `crm_upsert_contact.contact.address.house` [absent → absent:house] C=`94` I=``
- FIELD `crm_upsert_contact.contact.address.street` [absent → absent:street] C=`Тельмана` I=``
- FIELD `crm_upsert_contact.contact.birth_date` [absent → absent:birth_date] C=`1987-01-14` I=``
- FIELD `crm_upsert_contact.contact.email` [absent → absent:email] C=`gromov94@yandex.ru` I=``
- FIELD `crm_upsert_contact.contact.first_name` [absent → absent:first_name] C=`Артём` I=``
- FIELD `crm_upsert_contact.contact.initials` [absent → absent:initials] C=`А.В.` I=``
- FIELD `crm_upsert_contact.contact.last_name` [absent → absent:last_name] C=`Громов` I=``
- FIELD `crm_upsert_contact.contact.middle_name` [absent → absent:middle_name] C=`Витальевич` I=``
- FIELD `crm_upsert_contact.contact.name_latin` [absent → absent:name_latin] C=`Gromov Artyom` I=``
- FIELD `crm_upsert_contact.contact.phone` [absent → absent:phone] C=`+79250111503` I=``
- FIELD `notify_sms.number` [absent → absent:number] C=`+79250111503` I=``
- REPLY I: Обязательно отправлю СМС! Но прежде мне нужны ответы на два вопроса, чтобы всё записать корректно: 1. **Город** — оставляем **Самара** или другой? 2. **Фамилия** — в карточке **Громов**, менять на **Громов**?

## chain-008|2 · chain · sloppy · L1 = · L3 ≠ · C′≈C нет · причина: **derived-only**
- USER[1]: это громов артём витальевич хчоу поменять адрес доставки телефон 8-925-011-15-03
- USER[2]: записывйате тельмана 94 кв 56
- USER[3]: и отпарвьте мне смс что всё запсиали
- seen NAME `громов артём витальевич` → `Гущин Дмитрий Андреевич`
- seen PHONE `8-925-011-15-03` → `+79830535245`
- seen LOC `тельмана 94 кв 56` → `улицы Сосновой 179, кв. 148`
- C: `crm_find_contact` {'query': {'phone': '+79250111503'}}
- C: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Громов', 'first_name': 'Артём', 'middle_name': 'Витальевич', 'initials': 'А.В.', 'name_latin': 'Gromov Artem', 'phone': '+79250111503', 'email': 'gromov94@yand…
- C: `notify_sms` {'number': '+79250111503', 'text': 'Артём Витальевич, ваш адрес доставки успешно обновлён: Самара, ул. Тельмана, д. 94, кв. 56. Если возникнут вопросы — обращайтесь!', 'sign': 'Dostavka'}
- I: `crm_find_contact` written={'query': {'phone': '+79830535245'}} → restored={'query': {'phone': '+79250111503'}}
- I: `crm_upsert_contact` written={'id': 'c-1', 'contact': {'last_name': 'громов', 'first_name': 'Дмитрий', 'middle_name': 'Андреевич', 'phone': '+79830535245', 'email': 'txywvjlq@example.ru', 'birth_date': '1984-03-23', 'initials': 'Д.А.', 'name_latin': 'Gromov Dmitry', 'address': {'city': '… → restored={'id': 'c-1', 'contact': {'last_name': 'громов', 'first_name': 'артём', 'middle_name': 'витальевич', 'phone': '+79250111503', 'email': 'gromov94@yandex.ru', 'birth_date': '1987-01-14', 'initials': 'А.В.', 'name_latin': 'Gromov Dmitry', 'address': {'city': 'са…
- I: `notify_sms` written={'number': '+79830535245', 'text': 'Дмитрий Андреевич, ваш адрес доставки успешно обновлён: г. Самара, ул. Сосновая, д. 179, кв. 148.', 'sign': 'Dostavka'} → restored={'number': '+79250111503', 'text': 'артём витальевич, ваш адрес доставки успешно обновлён: г. Самара, тельмана, д. 94, кв. 56.', 'sign': 'Dostavka'}
- C′: `crm_find_contact` {'query': {'phone': '+79250111503'}}
- C′: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Громов', 'first_name': 'Артём', 'middle_name': 'Витальевич', 'phone': '+79250111503', 'email': 'gromov94@yandex.ru', 'birth_date': '1987-01-14', 'initials': 'А…
- C′: `notify_sms` {'number': '+79250111503', 'text': 'Артём Витальевич, ваш адрес доставки успешно обновлён: г. Самара, ул. Тельмана, д. 94, кв. 56. Если возникнут вопросы — свяжитесь с нами.', 'sign': 'Dostavka'}
- FIELD `crm_upsert_contact.contact.name_latin` [derived/unverifiable → derived] C=`Gromov Artem` I=`Gromov Dmitry`
- REPLY I: СМС отправлено на номер **8-925-011-15-03**! Клиент получит подтверждение об обновлении адреса доставки. Если что-то ещё нужно — обращайтесь!

## chain-009|1 · chain · sloppy · L1 = · L3 ≠ · C′≈C нет · причина: **other**
- USER[1]: здрасте это захаров владислав юрьевич хочу поменять адрес доставки телефон 8 960 746 48 97
- USER[2]: заптсывайте вишнёвая 8 кв 176
- USER[3]: и пришлите смс с подтверждением
- seen NAME `захаров владислав юрьевич` → `Чижов Леонид Александрович`
- seen PHONE `8 960 746 48 97` → `+79973885580`
- seen LOC `вишнёвая 8 кв 176` → `улица Луговая 133, кв. 146`
- C: `crm_find_contact` {'query': {'phone': '+79607464897'}}
- C: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Захаров', 'first_name': 'Владислав', 'middle_name': 'Юрьевич', 'initials': 'В.Ю.', 'name_latin': 'Zakharov Vladislav', 'phone': '+79607464897', 'email': 'zahar…
- C: `notify_sms` {'number': '+79607464897', 'text': 'Захаров В.Ю., ваш адрес доставки успешно обновлён: г. Глазов, ул. Вишнёвая, д. 8, кв. 176.', 'sign': 'Dostavka'}
- I: `crm_find_contact` written={'query': {'phone': '+79973885580'}} → restored={'query': {'phone': '+79607464897'}}
- I: `crm_upsert_contact` written={'id': 'c-1', 'contact': {'last_name': 'Чижов', 'first_name': 'Леонид', 'middle_name': 'Александрович', 'initials': 'Л.А.', 'name_latin': 'Chizhov Leonid', 'phone': '+79973885580', 'email': 'zywuarwx@example.ru', 'birth_date': '1972-04-27', 'gender': 'M', 'ad… → restored={'id': 'c-1', 'contact': {'last_name': 'захаров', 'first_name': 'владислав', 'middle_name': 'юрьевич', 'initials': 'В.Ю.', 'name_latin': 'Zakharov Vladislav', 'phone': '+79607464897', 'email': 'zaharov70@list.ru', 'birth_date': '1984-05-22', 'gender': 'M', 'a…
- I: `notify_sms` written={'number': '+79973885580', 'text': 'Уважаемый Леонид Александрович! Адрес доставки в вашей карточке успешно обновлён: г. Глазов, ул. Луговая, д. 133, кв. 146.', 'sign': 'Dostavka'} → restored={'number': '+79607464897', 'text': 'Уважаемый владислав юрьевич! Адрес доставки в вашей карточке успешно обновлён: г. Глазов, вишнёвая, д. 8, кв. 176.', 'sign': 'Dostavka'}
- C′: `crm_find_contact` {'query': {'phone': '+79607464897'}}
- C′: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Захаров', 'first_name': 'Владислав', 'middle_name': 'Юрьевич', 'initials': 'В.Ю.', 'name_latin': 'Zakharov Vladislav', 'phone': '+79607464897', 'email': 'zahar…
- C′: `notify_sms` {'number': '+79607464897', 'text': 'Захаров В.Ю., ваш адрес доставки успешно изменён: г. Глазов, ул. Вишнёвая, д. 8, кв. 176. Если это были не вы, свяжитесь с нами.', 'sign': 'Dostavka'}
- FIELD `crm_upsert_contact.contact.gender` [extra → extra:gender] C=`` I=`M`
- REPLY I: СМС отправлено на номер 8 960 746 48 97. Всего доброго, владислав юрьевич! 👋

## chain-013|0 · chain · chat · L1 = · L3 ≠ · C′≈C нет · причина: **other**
- USER[1]: привет это сергеев кирилл сергеевич хочу поменять адрес доставки телефон +79053336570
- USER[2]: записывайте лермонтова 178 кв 77
- USER[3]: и смс пришлите что адрес поменяли
- seen NAME `сергеев кирилл сергеевич` → `Котов Иван Леонидович`
- seen PHONE `+79053336570` → `+79815832566`
- seen LOC `лермонтова 178 кв 77` → `улицы Сосновой 161, кв. 163`
- C: `crm_find_contact` {'query': {'phone': '+79053336570'}}
- C: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Сергеев', 'first_name': 'Кирилл', 'middle_name': 'Сергеевич', 'initials': 'К.С.', 'name_latin': 'Sergeev Kirill', 'phone': '+79053336570', 'email': 'sergeev83@…
- C: `notify_sms` {'number': '+79053336570', 'text': 'Кирилл Сергеевич, адрес доставки в вашей карточке успешно изменён на: г. Воткинск, ул. Лермонтова, д. 178, кв. 77. Если это были не вы, свяжитесь с нами.', 'sign':…
- I: `crm_find_contact` written={'query': {'phone': '+79815832566'}} → restored={'query': {'phone': '+79053336570'}}
- I: `crm_upsert_contact` written={'id': 'c-1', 'contact': {'last_name': 'Котов', 'first_name': 'Иван', 'middle_name': 'Леонидович', 'initials': 'И.Л.', 'name_latin': 'Kotov Ivan', 'phone': '+79815832566', 'email': 'eyligrih@example.ru', 'birth_date': '1981-11-10', 'address': {'city': 'Воткин… → restored={'id': 'c-1', 'contact': {'last_name': 'сергеев', 'first_name': 'кирилл', 'middle_name': 'сергеевич', 'initials': 'К.С.', 'name_latin': 'Sergeev Kirill', 'phone': '+79053336570', 'email': 'sergeev83@bk.ru', 'birth_date': '1990-11-24', 'address': {'city': 'Вот…
- I: `notify_sms` written={'number': '+79815832566', 'text': 'Иван Леонидович, ваш адрес доставки успешно изменён на: г. Воткинск, ул. Сосновая, д. 161, кв. 163.', 'sign': 'Dostavka'} → restored={'number': '+79053336570', 'text': 'кирилл сергеевич, ваш адрес доставки успешно изменён на: г. Воткинск, лермонтова, д. 178, кв. 77.', 'sign': 'Dostavka'}
- C′: `crm_find_contact` {'query': {'phone': '+79053336570'}}
- C′: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Сергеев', 'first_name': 'Кирилл', 'middle_name': 'Сергеевич', 'initials': 'К.С.', 'name_latin': 'Sergeev Kirill', 'phone': '+79053336570', 'email': 'sergeev83@…
- C′: `notify_sms` {'number': '+79053336570', 'text': 'Уважаемый Кирилл Сергеевич! Адрес доставки в вашем профиле успешно изменён на: г. Воткинск, ул. Лермонтова, д. 178, кв. 77. Если это были не вы, пожалуйста, свяжит…
- FIELD `crm_upsert_contact.contact.gender` [absent → absent:gender] C=`M` I=``
- REPLY I: СМС отправлено на номер +79053336570! Если ещё что-то понадобится — всегда рады помочь. 😊

## chain-013|2 · chain · chat · L1 = · L3 ≠ · C′≈C нет · причина: **other**
- USER[1]: привет это сергеев кирилл сергеевич хочу поменять адрес доставки телефон +79053336570
- USER[2]: записывайте лермонтова 178 кв 77
- USER[3]: и смс пришлите что адрес поменяли
- seen NAME `сергеев кирилл сергеевич` → `Чижов Аркадий Петрович`
- seen PHONE `+79053336570` → `+79825478977`
- seen LOC `лермонтова 178 кв 77` → `улицы Пихтовой 54, кв. 132`
- C: `crm_find_contact` {'query': {'phone': '+79053336570'}}
- C: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Сергеев', 'first_name': 'Кирилл', 'middle_name': 'Сергеевич', 'initials': 'К.С.', 'name_latin': 'Sergeev Kirill', 'phone': '+79053336570', 'email': 'sergeev83@…
- C: `notify_sms` {'number': '+79053336570', 'text': 'Кирилл Сергеевич, ваш адрес доставки успешно изменён на: г. Воткинск, ул. Лермонтова, д. 178, кв. 77.', 'sign': 'Dostavka'}
- I: `crm_find_contact` written={'query': {'phone': '+79825478977'}} → restored={'query': {'phone': '+79053336570'}}
- I: `crm_upsert_contact` written={'id': 'c-1', 'contact': {'last_name': 'Чижов', 'first_name': 'Аркадий', 'middle_name': 'Петрович', 'phone': '+79825478977', 'email': 'cuminsba@example.ru', 'birth_date': '1960-01-09', 'initials': 'А.П.', 'name_latin': 'Chizhov Arkadiy', 'gender': 'M', 'addre… → restored={'id': 'c-1', 'contact': {'last_name': 'сергеев', 'first_name': 'кирилл', 'middle_name': 'сергеевич', 'phone': '+79053336570', 'email': 'sergeev83@bk.ru', 'birth_date': '1990-11-24', 'initials': 'К.С.', 'name_latin': 'Sergeev Kirill', 'gender': 'M', 'address'…
- I: `notify_sms` written={'number': '+79825478977', 'sign': 'Dostavka', 'text': 'Аркадий Петрович, адрес доставки в вашей карточке успешно изменён на: г. Воткинск, ул. Пихтовая, д. 54, кв. 132. Если это были не вы, свяжитесь с нами.'} → restored={'number': '+79053336570', 'sign': 'Dostavka', 'text': 'кирилл сергеевич, адрес доставки в вашей карточке успешно изменён на: г. Воткинск, лермонтова, д. 178, кв. 77. Если это были не вы, свяжитесь с нами.'}
- C′: `crm_find_contact` {'query': {'phone': '+79053336570'}}
- C′: `crm_upsert_contact` {'contact': {'last_name': 'Сергеев', 'first_name': 'Кирилл', 'middle_name': 'Сергеевич', 'initials': 'К.С.', 'name_latin': 'Sergeev Kirill', 'phone': '+79053336570', 'email': 'sergeev83@bk.ru', 'birt…
- C′: `notify_sms` {'number': '+79053336570', 'text': 'Кирилл Сергеевич, адрес доставки успешно изменён на: г. Воткинск, ул. Лермонтова, д. 178, кв. 77.', 'sign': 'Dostavka'}
- FIELD `crm_upsert_contact.contact.gender` [extra → extra:gender] C=`` I=`M`
- REPLY I: СМС отправлено на номер +79053336570! 📱 Если ещё что-то нужно — всегда рады помочь!

## chain-014|0 · chain · voice_raw · L1 ≠ · L3 ≠ · C′≈C нет · причина: **Б8-echo**
- USER[1]: девушка здравствуйте этоо кузнецов дмитрий андреевич хочуу поменять адрес доставки телефон восемсь девятьсот двадцать семь тристо девятьсот четырнадцать ноль
- USER[2]: записывайте проезд репина дом сто девяносто восемь квартира шестьдесят два
- USER[3]: и пришлите смс с подтверждением
- seen NAME `кузнецов дмитрий андреевич` → `Тарасов Прохор Григорьевич`
- seen PHONE `восемсь девятьсот двадцать семь тристо девятьсот четырнадцать ноль` → `+79054289554`
- seen LOC `проезд репина дом сто девяносто восемь квартира шестьдесят два` → `проезд Рябиновый 85, кв. 62`
- C: `crm_find_contact` {'query': {'phone': '+79273009140'}}
- C: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Кузнецов', 'first_name': 'Дмитрий', 'middle_name': 'Андреевич', 'initials': 'Д.А.', 'name_latin': 'Kuznetsov Dmitry', 'phone': '+79273009140', 'email': 'kuznec…
- C: `notify_sms` {'number': '+79273009140', 'sign': 'Dostavka', 'text': 'Дмитрий Андреевич, адрес доставки успешно изменён: г. Абакан, Проезд Репина, д. 198, кв. 62. Если вы не вносили изменения, свяжитесь с нами.'}
- I: `crm_find_contact` written={'query': {'phone': '+79054289554'}} → restored={'query': {'phone': '+79273009140'}}
- C′: `crm_find_contact` {'query': {'phone': '+79273009140'}}
- C′: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Кузнецов', 'first_name': 'Дмитрий', 'middle_name': 'Андреевич', 'initials': 'Д.А.', 'name_latin': 'Kuznetsov Dmitriy', 'phone': '+79273009140', 'email': 'kuzne…
- C′: `notify_sms` {'number': '+79273009140', 'sign': 'Dostavka', 'text': 'Дмитрий Андреевич, адрес доставки успешно изменён: г. Абакан, проезд Репина, д. 198, кв. 62. Если это были не вы, свяжитесь с нами.'}
- FIELD `crm_upsert_contact.contact.address.city` [absent → absent:city] C=`Абакан` I=``
- FIELD `crm_upsert_contact.contact.address.flat` [absent → absent:flat] C=`62` I=``
- FIELD `crm_upsert_contact.contact.address.house` [absent → absent:house] C=`198` I=``
- FIELD `crm_upsert_contact.contact.address.street` [absent → absent:street] C=`Проезд Репина` I=``
- FIELD `crm_upsert_contact.contact.birth_date` [absent → absent:birth_date] C=`2003-05-10` I=``
- FIELD `crm_upsert_contact.contact.email` [absent → absent:email] C=`kuznecov91@gmail.com` I=``
- FIELD `crm_upsert_contact.contact.first_name` [absent → absent:first_name] C=`Дмитрий` I=``
- FIELD `crm_upsert_contact.contact.initials` [absent → absent:initials] C=`Д.А.` I=``
- FIELD `crm_upsert_contact.contact.last_name` [absent → absent:last_name] C=`Кузнецов` I=``
- FIELD `crm_upsert_contact.contact.middle_name` [absent → absent:middle_name] C=`Андреевич` I=``
- FIELD `crm_upsert_contact.contact.name_latin` [absent → absent:name_latin] C=`Kuznetsov Dmitry` I=``
- FIELD `crm_upsert_contact.contact.phone` [absent → absent:phone] C=`+79273009140` I=``
- FIELD `notify_sms.number` [absent → absent:number] C=`+79273009140` I=``
- REPLY I: дмитрий андреевич, я не смогу внести изменения и отправить СМС, не разобравшись с двумя моментами — прошу ответить на оба вопроса: 1. **Город** — остаётся **Абакан**? 2. **Фамилия** — в карточке стоит **Кузнецов**, вы назвались **Кузнецов**. Какая верная? Как только уточните — сразу всё обновлю и в…

## chain-014|1 · chain · voice_raw · L1 = · L3 ≠ · C′≈C нет · причина: **derived-only**
- USER[1]: девушка здравствуйте этоо кузнецов дмитрий андреевич хочуу поменять адрес доставки телефон восемсь девятьсот двадцать семь тристо девятьсот четырнадцать ноль
- USER[2]: записывайте проезд репина дом сто девяносто восемь квартира шестьдесят два
- USER[3]: и пришлите смс с подтверждением
- seen NAME `кузнецов дмитрий андреевич` → `Карпов Святослав Романович`
- seen PHONE `восемсь девятьсот двадцать семь тристо девятьсот четырнадцать ноль` → `+79903301835`
- seen LOC `проезд репина дом сто девяносто восемь квартира шестьдесят два` → `проезд Речной 144, кв. 235`
- C: `crm_find_contact` {'query': {'phone': '+79273009140'}}
- C: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Кузнецов', 'first_name': 'Дмитрий', 'middle_name': 'Андреевич', 'initials': 'Д.А.', 'name_latin': 'Kuznetsov Dmitry', 'phone': '+79273009140', 'email': 'kuznec…
- C: `notify_sms` {'number': '+79273009140', 'sign': 'Dostavka', 'text': 'Дмитрий Андреевич, ваш адрес доставки успешно изменён: г. Абакан, проезд Репина, д. 198, кв. 62.'}
- I: `crm_find_contact` written={'query': {'phone': '+79903301835'}} → restored={'query': {'phone': '+79273009140'}}
- I: `crm_upsert_contact` written={'id': 'c-1', 'contact': {'last_name': 'Кузнецов', 'first_name': 'Святослав', 'middle_name': 'Романович', 'phone': '+79903301835', 'email': 'rsqdgzvv@example.ru', 'birth_date': '2023-01-08', 'initials': 'С.Р.', 'name_latin': 'Kuznetsov Svyatoslav', 'address':… → restored={'id': 'c-1', 'contact': {'last_name': 'Кузнецов', 'first_name': 'дмитрий', 'middle_name': 'андреевич', 'phone': '+79273009140', 'email': 'kuznecov91@gmail.com', 'birth_date': '2003-05-10', 'initials': 'Д.А.', 'name_latin': 'Kuznetsov Dmitrij', 'address': {'c…
- I: `notify_sms` written={'number': '+79903301835', 'text': 'Святослав Романович, ваш адрес доставки успешно обновлён: г. Абакан, проезд Речной, д. 144, кв. 235.', 'sign': 'Dostavka'} → restored={'number': '+79273009140', 'text': 'дмитрий андреевич, ваш адрес доставки успешно обновлён: г. Абакан, проезд репина, д. 198, кв. 62.', 'sign': 'Dostavka'}
- C′: `crm_find_contact` {'query': {'phone': '+79273009140'}}
- C′: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Кузнецов', 'first_name': 'Дмитрий', 'middle_name': 'Андреевич', 'initials': 'Д.А.', 'name_latin': 'Kuznetsov Dmitriy', 'phone': '+79273009140', 'email': 'kuzne…
- C′: `notify_sms` {'number': '+79273009140', 'sign': 'Dostavka', 'text': 'Дмитрий Андреевич, ваш адрес доставки успешно изменён: г. Абакан, проезд Репина, д. 198, кв. 62. Если это были не вы, позвоните нам.'}
- FIELD `crm_upsert_contact.contact.name_latin` [derived/unverifiable → derived] C=`Kuznetsov Dmitry` I=`Kuznetsov Dmitrij`
- REPLY I: СМС отправлено! 📱 Можете ждать сообщение на номер **восемсь девятьсот двадцать семь тристо девятьсот четырнадцать ноль**. Если ещё что-то нужно — обращайтесь!

## chain-014|2 · chain · voice_raw · L1 = · L3 ≠ · C′≈C да · причина: **derived-only**
- USER[1]: девушка здравствуйте этоо кузнецов дмитрий андреевич хочуу поменять адрес доставки телефон восемсь девятьсот двадцать семь тристо девятьсот четырнадцать ноль
- USER[2]: записывайте проезд репина дом сто девяносто восемь квартира шестьдесят два
- USER[3]: и пришлите смс с подтверждением
- seen NAME `кузнецов дмитрий андреевич` → `Рыбаков Харитон Иванович`
- seen PHONE `восемсь девятьсот двадцать семь тристо девятьсот четырнадцать ноль` → `+79185454588`
- seen LOC `проезд репина дом сто девяносто восемь квартира шестьдесят два` → `проезд Буковый 156, кв. 154`
- C: `crm_find_contact` {'query': {'phone': '+79273009140'}}
- C: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Кузнецов', 'first_name': 'Дмитрий', 'middle_name': 'Андреевич', 'initials': 'Д.А.', 'name_latin': 'Kuznetsov Dmitry', 'phone': '+79273009140', 'email': 'kuznec…
- C: `notify_sms` {'number': '+79273009140', 'sign': 'Dostavka', 'text': 'Здравствуйте, Дмитрий Андреевич! Адрес доставки успешно изменён: г. Абакан, пр-д Репина, д. 198, кв. 62.'}
- I: `crm_find_contact` written={'query': {'phone': '+79185454588'}} → restored={'query': {'phone': '+79273009140'}}
- I: `crm_upsert_contact` written={'id': 'c-1', 'contact': {'last_name': 'кузнецов', 'first_name': 'Харитон', 'middle_name': 'Иванович', 'initials': 'Х.И.', 'name_latin': 'Kuznetsov Khariton', 'phone': '+79185454588', 'email': 'yuexawmv@example.ru', 'birth_date': '1970-09-27', 'address': {'ci… → restored={'id': 'c-1', 'contact': {'last_name': 'кузнецов', 'first_name': 'дмитрий', 'middle_name': 'андреевич', 'initials': 'Д.А.', 'name_latin': 'Kuznetsov Dmitrii', 'phone': '+79273009140', 'email': 'kuznecov91@gmail.com', 'birth_date': '2003-05-10', 'address': {'c…
- I: `notify_sms` written={'number': '+79185454588', 'text': 'Харитон Иванович, адрес доставки успешно обновлён: г. Абакан, проезд Буковый, д. 156, кв. 154.', 'sign': 'Dostavka'} → restored={'number': '+79273009140', 'text': 'дмитрий андреевич, адрес доставки успешно обновлён: г. Абакан, проезд репина, д. 198, кв. 62.', 'sign': 'Dostavka'}
- C′: `crm_find_contact` {'query': {'phone': '+79273009140'}}
- C′: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Кузнецов', 'first_name': 'Дмитрий', 'middle_name': 'Андреевич', 'initials': 'Д.А.', 'name_latin': 'Kuznetsov Dmitry', 'phone': '+79273009140', 'email': 'kuznec…
- C′: `notify_sms` {'number': '+79273009140', 'sign': 'Dostavka', 'text': 'Дмитрий Андреевич, адрес доставки успешно изменён: г. Абакан, проезд Репина, д. 198, кв. 62. Если это были не вы, позвоните нам.'}
- FIELD `crm_upsert_contact.contact.gender` [absent → absent:gender] C=`M` I=``
- FIELD `crm_upsert_contact.contact.name_latin` [derived/unverifiable → derived] C=`Kuznetsov Dmitry` I=`Kuznetsov Dmitrii`
- REPLY I: Отправляю SMS! SMS отправлено ✅ дмитрий андреевич, сообщение с подтверждением нового адреса уже на вашем телефоне. И всё же жду ответа — фамилия в карточке верная **Кузнецов** или нужно исправить на **Кузнецов**? 😊

## chain-015|0 · chain · voice_itn · L1 ≠ · L3 ≠ · C′≈C нет · причина: **other**
- USER[1]: здравствуйте это кузнецова ольга дмитриевна хочу поменять адрес доставки телефон 8-912-987-65-43
- USER[2]: записывайте кирочная 29 квартира 31
- USER[3]: и смс пришлите что адрес поменяли
- seen NAME `кузнецова ольга дмитриевна` → `Панова Христина Валентиновна`
- seen PHONE `8-912-987-65-43` → `+79056801520`
- seen LOC `кирочная 29 квартира 31` → `улица Жасминовая 141, кв. 235`
- C: `crm_find_contact` {'query': {'phone': '+79129876543'}}
- I: `crm_find_contact` written={'query': {'phone': '+79056801520'}} → restored={'query': {'phone': '+79129876543'}}
- I: `crm_upsert_contact` written={'id': 'c-1', 'contact': {'last_name': 'Панова', 'first_name': 'Христина', 'middle_name': 'Валентиновна', 'initials': 'Х.В.', 'name_latin': 'Panova Khristina', 'phone': '+79056801520', 'email': 'atadfnjr@example.ru', 'birth_date': '1962-04-23', 'gender': 'F',… → restored={'id': 'c-1', 'contact': {'last_name': 'кузнецова', 'first_name': 'ольга', 'middle_name': 'дмитриевна', 'initials': 'О.Д.', 'name_latin': 'Kuznetsova Olga', 'phone': '+79129876543', 'email': 'kuznecova92@list.ru', 'birth_date': '1969-01-08', 'gender': 'F', 'a…
- I: `notify_sms` written={'number': '+79056801520', 'text': 'Христина Валентиновна, адрес доставки в вашей карточке успешно изменён: г. Сортавала, ул. Жасминовая, д. 141, кв. 235.', 'sign': 'Dostavka'} → restored={'number': '+79129876543', 'text': 'ольга дмитриевна, адрес доставки в вашей карточке успешно изменён: г. Сортавала, ул. кирочная, д. 29, кв. 31.', 'sign': 'Dostavka'}
- C′: `crm_find_contact` {'query': {'phone': '+79129876543'}}
- C′: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Кузнецова', 'first_name': 'Ольга', 'middle_name': 'Дмитриевна', 'initials': 'О.Д.', 'name_latin': 'Kuznetsova Olga', 'phone': '+79129876543', 'email': 'kuzneco…
- C′: `notify_sms` {'number': '+79129876543', 'text': 'Ольга Дмитриевна, адрес доставки в вашей карточке успешно изменён на: г. Сортавала, ул. Кирочная, д. 29, кв. 31. Если это были не вы, позвоните нам.', 'sign': 'Dos…
- FIELD `crm_upsert_contact.contact.address.city` [extra → extra:city] C=`` I=`Сортавала`
- FIELD `crm_upsert_contact.contact.address.flat` [extra → extra:flat] C=`` I=`31`
- FIELD `crm_upsert_contact.contact.address.house` [extra → extra:house] C=`` I=`29`
- FIELD `crm_upsert_contact.contact.address.street` [extra → extra:street] C=`` I=`кирочная`
- FIELD `crm_upsert_contact.contact.birth_date` [extra → extra:birth_date] C=`` I=`1969-01-08`
- FIELD `crm_upsert_contact.contact.email` [extra → extra:email] C=`` I=`kuznecova92@list.ru`
- FIELD `crm_upsert_contact.contact.first_name` [extra → extra:first_name] C=`` I=`ольга`
- FIELD `crm_upsert_contact.contact.gender` [extra → extra:gender] C=`` I=`F`
- FIELD `crm_upsert_contact.contact.initials` [extra → extra:initials] C=`` I=`О.Д.`
- FIELD `crm_upsert_contact.contact.last_name` [extra → extra:last_name] C=`` I=`кузнецова`
- FIELD `crm_upsert_contact.contact.middle_name` [extra → extra:middle_name] C=`` I=`дмитриевна`
- FIELD `crm_upsert_contact.contact.name_latin` [extra → extra:name_latin] C=`` I=`Kuznetsova Olga`
- FIELD `crm_upsert_contact.contact.phone` [extra → extra:phone] C=`` I=`+79129876543`
- FIELD `notify_sms.number` [extra → extra:number] C=`` I=`+79129876543`
- REPLY I: Принято! Обновляю карточку и отправляю СМС одновременно. Всё готово, ольга дмитриевна! ✅ - **Адрес обновлён:** г. Сортавала, ул. кирочная 29 квартира 31 - **СМС отправлено** на номер 8-912-987-65-43 Если понадобится ещё что-то изменить — обращайтесь!

## chain-015|1 · chain · voice_itn · L1 = · L3 ≠ · C′≈C нет · причина: **other**
- USER[1]: здравствуйте это кузнецова ольга дмитриевна хочу поменять адрес доставки телефон 8-912-987-65-43
- USER[2]: записывайте кирочная 29 квартира 31
- USER[3]: и смс пришлите что адрес поменяли
- seen NAME `кузнецова ольга дмитриевна` → `Котова Зинаида Викторовна`
- seen PHONE `8-912-987-65-43` → `+79720689042`
- seen LOC `кирочная 29 квартира 31` → `улица Пихтовая 188, кв. 248`
- C: `crm_find_contact` {'query': {'phone': '+79129876543'}}
- C: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Кузнецова', 'first_name': 'Ольга', 'middle_name': 'Дмитриевна', 'initials': 'О.Д.', 'name_latin': 'Kuznetsova Olga', 'phone': '+79129876543', 'email': 'kuzneco…
- C: `notify_sms` {'number': '+79129876543', 'text': 'Ольга Дмитриевна, ваш адрес доставки успешно изменён на: г. Сортавала, ул. Кирочная, д. 29, кв. 31.', 'sign': 'Dostavka'}
- I: `crm_find_contact` written={'query': {'phone': '+79720689042'}} → restored={'query': {'phone': '+79129876543'}}
- I: `crm_upsert_contact` written={'id': 'c-1', 'contact': {'last_name': 'Котова', 'first_name': 'Зинаида', 'middle_name': 'Викторовна', 'initials': 'З.В.', 'name_latin': 'Kotova Zinaida', 'phone': '+79720689042', 'email': 'aqymplqo@example.ru', 'birth_date': '1975-02-23', 'gender': 'F', 'add… → restored={'id': 'c-1', 'contact': {'last_name': 'кузнецова', 'first_name': 'ольга', 'middle_name': 'дмитриевна', 'initials': 'О.Д.', 'name_latin': 'Kuznetsova Olga', 'phone': '+79129876543', 'email': 'kuznecova92@list.ru', 'birth_date': '1969-01-08', 'gender': 'F', 'a…
- I: `notify_sms` written={'number': '+79720689042', 'text': 'Зинаида Викторовна, ваш адрес доставки успешно изменён на: г. Сортавала, ул. Пихтовая, д. 188, кв. 248. Если это были не вы, свяжитесь с нами.', 'sign': 'Dostavka'} → restored={'number': '+79129876543', 'text': 'ольга дмитриевна, ваш адрес доставки успешно изменён на: г. Сортавала, ул. кирочная, д. 29, кв. 31. Если это были не вы, свяжитесь с нами.', 'sign': 'Dostavka'}
- C′: `crm_find_contact` {'query': {'phone': '+79129876543'}}
- C′: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Кузнецова', 'first_name': 'Ольга', 'middle_name': 'Дмитриевна', 'initials': 'О.Д.', 'name_latin': 'Kuznetsova Olga', 'phone': '+79129876543', 'email': 'kuzneco…
- C′: `notify_sms` {'number': '+79129876543', 'text': 'Ольга Дмитриевна, адрес доставки в вашей карточке успешно изменён на: г. Сортавала, ул. Кирочная, д. 29, кв. 31. Если это были не вы, пожалуйста, свяжитесь с нами.…
- FIELD `crm_upsert_contact.contact.gender` [extra → extra:gender] C=`` I=`F`
- REPLY I: СМС отправлено на номер 8-912-987-65-43. Что-то ещё могу помочь?

## chain-015|2 · chain · voice_itn · L1 = · L3 ≠ · C′≈C да · причина: **other**
- USER[1]: здравствуйте это кузнецова ольга дмитриевна хочу поменять адрес доставки телефон 8-912-987-65-43
- USER[2]: записывайте кирочная 29 квартира 31
- USER[3]: и смс пришлите что адрес поменяли
- seen NAME `кузнецова ольга дмитриевна` → `Ершова Эльвира Владимировна`
- seen PHONE `8-912-987-65-43` → `+79030766607`
- seen LOC `кирочная 29 квартира 31` → `улица Вязовая 144, кв. 235`
- C: `crm_find_contact` {'query': {'phone': '+79129876543'}}
- C: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Кузнецова', 'first_name': 'Ольга', 'middle_name': 'Дмитриевна', 'initials': 'О.Д.', 'name_latin': 'Kuznetsova Olga', 'phone': '+79129876543', 'email': 'kuzneco…
- C: `notify_sms` {'number': '+79129876543', 'text': 'Ольга Дмитриевна, адрес доставки в вашей карточке изменён на: г. Сортавала, ул. Кирочная, д. 29, кв. 31. Если это ошибка, позвоните нам.', 'sign': 'Dostavka'}
- I: `crm_find_contact` written={'query': {'phone': '+79030766607'}} → restored={'query': {'phone': '+79129876543'}}
- I: `crm_upsert_contact` written={'id': 'c-1', 'contact': {'last_name': 'Ершова', 'first_name': 'Эльвира', 'middle_name': 'Владимировна', 'initials': 'Э.В.', 'name_latin': 'Ershova Elvira', 'phone': '+79030766607', 'email': 'ufpmbkqc@example.ru', 'birth_date': '1993-01-11', 'address': {'city… → restored={'id': 'c-1', 'contact': {'last_name': 'кузнецова', 'first_name': 'ольга', 'middle_name': 'дмитриевна', 'initials': 'О.Д.', 'name_latin': 'Kuznetsova Olga', 'phone': '+79129876543', 'email': 'kuznecova92@list.ru', 'birth_date': '1969-01-08', 'address': {'city…
- I: `notify_sms` written={'number': '+79030766607', 'text': 'Эльвира Владимировна, адрес доставки в вашей карточке успешно изменён на: г. Сортавала, ул. Вязовая, д. 144, кв. 235. Если это были не вы, пожалуйста, свяжитесь с нами.', 'sign': 'Dostavka'} → restored={'number': '+79129876543', 'text': 'ольга дмитриевна, адрес доставки в вашей карточке успешно изменён на: г. Сортавала, ул. кирочная, д. 29, кв. 31. Если это были не вы, пожалуйста, свяжитесь с нами.', 'sign': 'Dostavka'}
- C′: `crm_find_contact` {'query': {'phone': '+79129876543'}}
- C′: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Кузнецова', 'first_name': 'Ольга', 'middle_name': 'Дмитриевна', 'initials': 'О.Д.', 'name_latin': 'Kuznetsova Olga', 'phone': '+79129876543', 'email': 'kuzneco…
- C′: `notify_sms` {'number': '+79129876543', 'text': 'Ольга Дмитриевна, адрес доставки в вашей карточке изменён на: г. Сортавала, ул. Кирочная, д. 29, кв. 31. Если это были не вы, свяжитесь с нами.', 'sign': 'Dostavka…
- FIELD `crm_upsert_contact.contact.gender` [absent → absent:gender] C=`F` I=``
- REPLY I: СМС отправлено на номер 8-912-987-65-43! 📱 Если ещё что-то нужно — обращайтесь!

## chain-021|0 · chain · chat · L1 = · L3 ≠ · C′≈C нет · причина: **other**
- USER[1]: добрый день это лебедев максим константинович хочу поменять адрес доставки телефон 89643211075
- USER[2]: записывайте переулок светлый 156 а кв 124
- USER[3]: и пришлите смс с подтверждением
- seen NAME `лебедев максим константинович` → `Юдин Андрей Александрович`
- seen PHONE `89643211075` → `+79414521456`
- seen LOC `переулок светлый 156 а кв 124` → `переулок Сосновый 179, кв. 212`
- C: `crm_find_contact` {'query': {'phone': '+79643211075'}}
- C: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Лебедев', 'first_name': 'Максим', 'middle_name': 'Константинович', 'initials': 'М.К.', 'name_latin': 'Lebedev Maksim', 'phone': '+79643211075', 'email': 'lebed…
- C: `notify_sms` {'number': '+79643211075', 'sign': 'Dostavka', 'text': 'Здравствуйте, Максим Константинович! Ваш адрес доставки успешно изменён: г. Ижевск, пер. Светлый, д. 156а, кв. 124.'}
- I: `crm_find_contact` written={'query': {'phone': '+79414521456'}} → restored={'query': {'phone': '+79643211075'}}
- I: `crm_upsert_contact` written={'id': 'c-1', 'contact': {'last_name': 'Юдин', 'first_name': 'Андрей', 'middle_name': 'Александрович', 'initials': 'А.А.', 'name_latin': 'Yudin Andrey', 'phone': '+79414521456', 'email': 'nffofmxk@example.ru', 'birth_date': '1977-08-25', 'address': {'city': '… → restored={'id': 'c-1', 'contact': {'last_name': 'лебедев', 'first_name': 'максим', 'middle_name': 'константинович', 'initials': 'М.К.', 'name_latin': 'Lebedev Maksim', 'phone': '+79643211075', 'email': 'lebedev83@mail.ru', 'birth_date': '1997-07-24', 'address': {'city…
- I: `notify_sms` written={'number': '+79414521456', 'sign': 'Dostavka', 'text': 'Андрей Александрович, адрес доставки успешно изменён на: г. Ижевск, пер. Сосновый, д. 179, кв. 212.'} → restored={'number': '+79643211075', 'sign': 'Dostavka', 'text': 'максим константинович, адрес доставки успешно изменён на: г. Ижевск, пер. светлый, д. 156 а, кв. 124.'}
- C′: `crm_find_contact` {'query': {'phone': '+79643211075'}}
- C′: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Лебедев', 'first_name': 'Максим', 'middle_name': 'Константинович', 'initials': 'М.К.', 'name_latin': 'Lebedev Maksim', 'phone': '+79643211075', 'email': 'lebed…
- C′: `notify_sms` {'number': '+79643211075', 'text': 'Здравствуйте, Максим Константинович! Адрес доставки в вашей карточке успешно изменён на: г. Ижевск, пер. Светлый, д. 156а, кв. 124.', 'sign': 'Dostavka'}
- FIELD `crm_upsert_contact.contact.gender` [absent → absent:gender] C=`M` I=``
- REPLY I: СМС с подтверждением отправлено на номер 89643211075. Если возникнут ещё вопросы — всегда рады помочь!

## chain-021|1 · chain · chat · L1 = · L3 ≠ · C′≈C да · причина: **other**
- USER[1]: добрый день это лебедев максим константинович хочу поменять адрес доставки телефон 89643211075
- USER[2]: записывайте переулок светлый 156 а кв 124
- USER[3]: и пришлите смс с подтверждением
- seen NAME `лебедев максим константинович` → `Цветков Вячеслав Алексеевич`
- seen PHONE `89643211075` → `+79592495183`
- seen LOC `переулок светлый 156 а кв 124` → `переулок Тополиный 57, кв. 207`
- C: `crm_find_contact` {'query': {'phone': '+79643211075'}}
- C: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Лебедев', 'first_name': 'Максим', 'middle_name': 'Константинович', 'initials': 'М.К.', 'name_latin': 'Lebedev Maksim', 'phone': '+79643211075', 'email': 'lebed…
- C: `notify_sms` {'number': '+79643211075', 'text': 'Уважаемый Максим Константинович! Адрес доставки успешно изменён: г. Ижевск, пер. Светлый, д. 156а, кв. 124. Если это были не вы, свяжитесь с нами.', 'sign': 'Dosta…
- I: `crm_find_contact` written={'query': {'phone': '+79592495183'}} → restored={'query': {'phone': '+79643211075'}}
- I: `crm_upsert_contact` written={'id': 'c-1', 'contact': {'last_name': 'Цветков', 'first_name': 'Вячеслав', 'middle_name': 'Алексеевич', 'initials': 'В.А.', 'name_latin': 'Tsvetkov Vyacheslav', 'phone': '+79592495183', 'email': 'sgwqfrht@example.ru', 'birth_date': '2006-02-16', 'address': {… → restored={'id': 'c-1', 'contact': {'last_name': 'лебедев', 'first_name': 'максим', 'middle_name': 'константинович', 'initials': 'М.К.', 'name_latin': 'Lebedev Maksim', 'phone': '+79643211075', 'email': 'lebedev83@mail.ru', 'birth_date': '1997-07-24', 'address': {'city…
- I: `notify_sms` written={'number': '+79592495183', 'text': 'Вячеслав Алексеевич, ваш адрес доставки успешно изменён на: г. Ижевск, пер. Тополиный, д. 57, кв. 207. Если вы не делали этот запрос, свяжитесь с нами.', 'sign': 'Dostavka'} → restored={'number': '+79643211075', 'text': 'максим константинович, ваш адрес доставки успешно изменён на: г. Ижевск, пер. светлый, д. 156 а, кв. 124. Если вы не делали этот запрос, свяжитесь с нами.', 'sign': 'Dostavka'}
- C′: `crm_find_contact` {'query': {'phone': '+79643211075'}}
- C′: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Лебедев', 'first_name': 'Максим', 'middle_name': 'Константинович', 'initials': 'М.К.', 'name_latin': 'Lebedev Maksim', 'phone': '+79643211075', 'email': 'lebed…
- C′: `notify_sms` {'number': '+79643211075', 'sign': 'Dostavka', 'text': 'Здравствуйте, Максим Константинович! Адрес доставки успешно обновлён: г. Ижевск, переулок Светлый, д. 156а, кв. 124. Если вы не делали этот зап…
- REPLY I: СМС с подтверждением отправлено на номер **89643211075**. Если возникнут ещё вопросы — обращайтесь, максим константинович! Удачного дня! 😊

## chain-021|2 · chain · chat · L1 = · L3 ≠ · C′≈C нет · причина: **other**
- USER[1]: добрый день это лебедев максим константинович хочу поменять адрес доставки телефон 89643211075
- USER[2]: записывайте переулок светлый 156 а кв 124
- USER[3]: и пришлите смс с подтверждением
- seen NAME `лебедев максим константинович` → `Ершов Демьян Максимович`
- seen PHONE `89643211075` → `+79888997824`
- seen LOC `переулок светлый 156 а кв 124` → `переулок Сосновый 173, кв. 111`
- C: `crm_find_contact` {'query': {'phone': '+79643211075'}}
- C: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Лебедев', 'first_name': 'Максим', 'middle_name': 'Константинович', 'initials': 'М.К.', 'name_latin': 'Lebedev Maksim', 'phone': '+79643211075', 'email': 'lebed…
- C: `notify_sms` {'number': '+79643211075', 'text': 'Здравствуйте, Максим Константинович! Ваш адрес доставки успешно изменён: г. Ижевск, пер. Светлый, д. 156а, кв. 124.', 'sign': 'Dostavka'}
- I: `crm_find_contact` written={'query': {'phone': '+79888997824'}} → restored={'query': {'phone': '+79643211075'}}
- I: `crm_upsert_contact` written={'id': 'c-1', 'contact': {'last_name': 'Ершов', 'first_name': 'Демьян', 'middle_name': 'Максимович', 'phone': '+79888997824', 'email': 'nntfpodm@example.ru', 'birth_date': '1989-05-10', 'initials': 'Д.М.', 'name_latin': 'Ershov Demyan', 'gender': 'M', 'addres… → restored={'id': 'c-1', 'contact': {'last_name': 'лебедев', 'first_name': 'максим', 'middle_name': 'константинович', 'phone': '+79643211075', 'email': 'lebedev83@mail.ru', 'birth_date': '1997-07-24', 'initials': 'М.К.', 'name_latin': 'Lebedev Maksim', 'gender': 'M', 'a…
- I: `notify_sms` written={'number': '+79888997824', 'sign': 'Dostavka', 'text': 'Демьян Максимович, адрес доставки успешно изменён: г. Ижевск, пер. Сосновый, д. 173, кв. 111. Если у вас возникнут вопросы, обращайтесь!'} → restored={'number': '+79643211075', 'sign': 'Dostavka', 'text': 'максим константинович, адрес доставки успешно изменён: г. Ижевск, пер. светлый, д. 156 а, кв. 124. Если у вас возникнут вопросы, обращайтесь!'}
- C′: `crm_find_contact` {'query': {'phone': '+79643211075'}}
- C′: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Лебедев', 'first_name': 'Максим', 'middle_name': 'Константинович', 'initials': 'М.К.', 'name_latin': 'Lebedev Maxim', 'phone': '+79643211075', 'email': 'lebede…
- C′: `notify_sms` {'number': '+79643211075', 'sign': 'Dostavka', 'text': 'Здравствуйте, Максим Константинович! Ваш адрес доставки успешно изменён: г. Ижевск, пер. Светлый, д. 156а, кв. 124. Если вы не делали этот запр…
- FIELD `crm_upsert_contact.contact.gender` [extra → extra:gender] C=`` I=`M`
- REPLY I: СМС отправлено на номер **89643211075**. Всего доброго, максим константинович! 😊

## chain-024|1 · chain · voice_itn · L1 = · L3 ≠ · C′≈C нет · причина: **derived-only**
- USER[1]: алло это васильев иван павлович хочу поменять адрес доставки телефон +79636379775
- USER[2]: записывайте рабочая дом 11 квартира 205
- USER[3]: и смс пришлите что адрес поменяли
- seen NAME `васильев иван павлович` → `Устинов Святослав Максимович`
- seen PHONE `+79636379775` → `+79223235699`
- seen LOC `рабочая дом 11 квартира 205` → `улица Жасминовая 7, кв. 24`
- C: `crm_find_contact` {'query': {'phone': '+79636379775'}}
- C: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Васильев', 'first_name': 'Иван', 'middle_name': 'Павлович', 'initials': 'И.П.', 'name_latin': 'Vasiliev Ivan', 'phone': '+79636379775', 'email': 'vasilev90@bk.…
- C: `notify_sms` {'number': '+79636379775', 'text': 'Иван Павлович, адрес доставки успешно изменён: г. Абакан, ул. Рабочая, д. 11, кв. 205. Если это были не вы, свяжитесь с нами.', 'sign': 'Dostavka'}
- I: `crm_find_contact` written={'query': {'phone': '+79223235699'}} → restored={'query': {'phone': '+79636379775'}}
- I: `crm_upsert_contact` written={'id': 'c-1', 'contact': {'last_name': 'Устинов', 'first_name': 'Святослав', 'middle_name': 'Максимович', 'phone': '+79223235699', 'email': 'glturczh@example.ru', 'birth_date': '2024-08-09', 'initials': 'С.М.', 'name_latin': 'Ustinov Svyatoslav', 'address': {… → restored={'id': 'c-1', 'contact': {'last_name': 'васильев', 'first_name': 'иван', 'middle_name': 'павлович', 'phone': '+79636379775', 'email': 'vasilev90@bk.ru', 'birth_date': '1988-07-16', 'initials': 'И.П.', 'name_latin': 'Vasilev Ivan', 'address': {'city': 'Абакан'…
- I: `notify_sms` written={'number': '+79223235699', 'text': 'Святослав Максимович, адрес доставки в вашем профиле успешно изменён на: г. Абакан, ул. Жасминовая, д. 7, кв. 24.', 'sign': 'Dostavka'} → restored={'number': '+79636379775', 'text': 'иван павлович, адрес доставки в вашем профиле успешно изменён на: г. Абакан, рабочая, д. 11, кв. 205.', 'sign': 'Dostavka'}
- C′: `crm_find_contact` {'query': {'phone': '+79636379775'}}
- C′: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Васильев', 'first_name': 'Иван', 'middle_name': 'Павлович', 'initials': 'И.П.', 'name_latin': 'Vasilev Ivan', 'phone': '+79636379775', 'email': 'vasilev90@bk.r…
- C′: `notify_sms` {'number': '+79636379775', 'text': 'Иван Павлович, адрес доставки в вашей карточке успешно изменён: г. Абакан, ул. Рабочая, д. 11, кв. 205.', 'sign': 'Dostavka'}
- FIELD `crm_upsert_contact.contact.gender` [absent → absent:gender] C=`M` I=``
- FIELD `crm_upsert_contact.contact.name_latin` [derived/unverifiable → derived] C=`Vasiliev Ivan` I=`Vasilev Ivan`
- REPLY I: СМС отправлено на номер +79636379775! Что-нибудь ещё могу помочь?

## chain-024|2 · chain · voice_itn · L1 = · L3 ≠ · C′≈C да · причина: **other**
- USER[1]: алло это васильев иван павлович хочу поменять адрес доставки телефон +79636379775
- USER[2]: записывайте рабочая дом 11 квартира 205
- USER[3]: и смс пришлите что адрес поменяли
- seen NAME `васильев иван павлович` → `Бирюков Остап Григорьевич`
- seen PHONE `+79636379775` → `+79166240711`
- seen LOC `рабочая дом 11 квартира 205` → `улица Рябиновая 172, кв. 116`
- C: `crm_find_contact` {'query': {'phone': '+79636379775'}}
- C: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Васильев', 'first_name': 'Иван', 'middle_name': 'Павлович', 'initials': 'И.П.', 'name_latin': 'Vasilev Ivan', 'phone': '+79636379775', 'email': 'vasilev90@bk.r…
- C: `notify_sms` {'number': '+79636379775', 'text': 'Иван Павлович, адрес доставки в вашей карточке успешно изменён: г. Абакан, ул. Рабочая, д. 11, кв. 205.', 'sign': 'Dostavka'}
- I: `crm_find_contact` written={'query': {'phone': '+79166240711'}} → restored={'query': {'phone': '+79636379775'}}
- I: `crm_upsert_contact` written={'id': 'c-1', 'contact': {'last_name': 'Бирюков', 'first_name': 'Остап', 'middle_name': 'Григорьевич', 'initials': 'О.Г.', 'name_latin': 'Biryukov Ostap', 'phone': '+79166240711', 'email': 'frsguzgt@example.ru', 'birth_date': '2004-11-13', 'address': {'city':… → restored={'id': 'c-1', 'contact': {'last_name': 'васильев', 'first_name': 'иван', 'middle_name': 'павлович', 'initials': 'И.П.', 'name_latin': 'Vasilev Ivan', 'phone': '+79636379775', 'email': 'vasilev90@bk.ru', 'birth_date': '1988-07-16', 'address': {'city': 'Абакан'…
- I: `notify_sms` written={'number': '+79166240711', 'text': 'Остап Григорьевич, адрес доставки в вашем профиле успешно изменён на: г. Абакан, ул. Рябиновая, д. 172, кв. 116.', 'sign': 'Dostavka'} → restored={'number': '+79636379775', 'text': 'иван павлович, адрес доставки в вашем профиле успешно изменён на: г. Абакан, рабочая, д. 11, кв. 205.', 'sign': 'Dostavka'}
- C′: `crm_find_contact` {'query': {'phone': '+79636379775'}}
- C′: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Васильев', 'first_name': 'Иван', 'middle_name': 'Павлович', 'initials': 'И.П.', 'name_latin': 'Vasilev Ivan', 'phone': '+79636379775', 'email': 'vasilev90@bk.r…
- C′: `notify_sms` {'number': '+79636379775', 'text': 'Иван Павлович, адрес доставки успешно изменён: г. Абакан, ул. Рабочая, д. 11, кв. 205.', 'sign': 'Dostavka'}
- FIELD `crm_upsert_contact.contact.gender` [absent → absent:gender] C=`M` I=``
- REPLY I: Обновляю адрес и отправляю СМС! Всё готово, иван павлович! ✅ - **Адрес обновлён:** г. Абакан, рабочая дом 11 квартира 205 - **СМС отправлено** на номер +79636379775 Если потребуется ещё что-то изменить — обращайтесь!

## chain-026|0 · chain · chat · L1 = · L3 ≠ · C′≈C да · причина: **other**
- USER[1]: здравствуйте это заболотный руслан фёдорович хочу поменять адрес доставки телефон 8-912-782-75-80
- USER[2]: теперь депутатская 118 кв 75
- USER[3]: и пришлите смс с подтверждением
- seen NAME `заболотный руслан фёдорович` → `Тарасов Остап Игоревич`
- seen PHONE `8-912-782-75-80` → `+79864657624`
- seen LOC `депутатская 118 кв 75` → `улица Мятная 122, кв. 75`
- C: `crm_find_contact` {'query': {'phone': '+79127827580'}}
- C: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Заболотный', 'first_name': 'Руслан', 'middle_name': 'Фёдорович', 'initials': 'Р.Ф.', 'name_latin': 'Zabolotny Ruslan', 'phone': '+79127827580', 'email': 'zabol…
- C: `notify_sms` {'number': '+79127827580', 'sign': 'Dostavka', 'text': 'Здравствуйте, Руслан Фёдорович! Адрес доставки в вашей карточке успешно изменён на: г. Сортавала, ул. Депутатская, д. 118, кв. 75.'}
- I: `crm_find_contact` written={'query': {'phone': '+79864657624'}} → restored={'query': {'phone': '+79127827580'}}
- I: `crm_upsert_contact` written={'id': 'c-1', 'contact': {'last_name': 'Тарасов', 'first_name': 'Остап', 'middle_name': 'Игоревич', 'phone': '+79864657624', 'email': 'jpywwyqx@example.ru', 'birth_date': '1974-02-16', 'initials': 'О.И.', 'name_latin': 'Tarasov Ostap', 'address': {'city': 'Со… → restored={'id': 'c-1', 'contact': {'last_name': 'заболотный', 'first_name': 'руслан', 'middle_name': 'фёдорович', 'phone': '+79127827580', 'email': 'zabolotnyy78@yandex.ru', 'birth_date': '1993-05-01', 'initials': 'Р.Ф.', 'name_latin': 'Zabolotnyi Ruslan', 'address': …
- I: `notify_sms` written={'number': '+79864657624', 'text': 'Остап Игоревич, адрес доставки успешно изменён: г. Сортавала, ул. Мятная, д. 122, кв. 75.', 'sign': 'Dostavka'} → restored={'number': '+79127827580', 'text': 'руслан фёдорович, адрес доставки успешно изменён: г. Сортавала, ул. депутатская, д. 118, кв. 75.', 'sign': 'Dostavka'}
- C′: `crm_find_contact` {'query': {'phone': '+79127827580'}}
- C′: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Заболотный', 'first_name': 'Руслан', 'middle_name': 'Фёдорович', 'initials': 'Р.Ф.', 'name_latin': 'Zabolotny Ruslan', 'phone': '+79127827580', 'email': 'zabol…
- C′: `notify_sms` {'number': '+79127827580', 'sign': 'Dostavka', 'text': 'Здравствуйте, Руслан Фёдорович! Адрес доставки в вашей карточке успешно изменён на: г. Сортавала, ул. Депутатская, д. 118, кв. 75.'}
- FIELD `crm_upsert_contact.contact.address.house` [reformatted → loc_fake] C=`118` I=`122`
- FIELD `crm_upsert_contact.contact.gender` [absent → absent:gender] C=`M` I=``
- FIELD `crm_upsert_contact.contact.name_latin` [derived/unverifiable → derived] C=`Zabolotny Ruslan` I=`Zabolotnyi Ruslan`
- REPLY I: СМС с подтверждением отправлено на номер 8-912-782-75-80. Если будут ещё вопросы — обращайтесь!

## chain-026|1 · chain · chat · L1 = · L3 ≠ · C′≈C да · причина: **derived-only**
- USER[1]: здравствуйте это заболотный руслан фёдорович хочу поменять адрес доставки телефон 8-912-782-75-80
- USER[2]: теперь депутатская 118 кв 75
- USER[3]: и пришлите смс с подтверждением
- seen NAME `заболотный руслан фёдорович` → `Гущин Егор Геннадьевич`
- seen PHONE `8-912-782-75-80` → `+79709778676`
- seen LOC `депутатская 118 кв 75` → `улица Осиновая 138, кв. 65`
- C: `crm_find_contact` {'query': {'phone': '+79127827580'}}
- C: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Заболотный', 'first_name': 'Руслан', 'middle_name': 'Фёдорович', 'initials': 'Р.Ф.', 'name_latin': 'Zabolotny Ruslan', 'phone': '+79127827580', 'email': 'zabol…
- C: `notify_sms` {'number': '+79127827580', 'sign': 'Dostavka', 'text': 'Здравствуйте, Руслан Фёдорович! Адрес доставки в вашей карточке успешно обновлён: г. Сортавала, ул. Депутатская, д. 118, кв. 75.'}
- I: `crm_find_contact` written={'query': {'phone': '+79709778676'}} → restored={'query': {'phone': '+79127827580'}}
- I: `crm_upsert_contact` written={'id': 'c-1', 'contact': {'last_name': 'Гущин', 'first_name': 'Егор', 'middle_name': 'Геннадьевич', 'phone': '+79709778676', 'email': 'yynbykpx@example.ru', 'birth_date': '1990-12-08', 'initials': 'Е.Г.', 'name_latin': 'Gushchin Egor', 'address': {'city': 'Со… → restored={'id': 'c-1', 'contact': {'last_name': 'заболотный', 'first_name': 'руслан', 'middle_name': 'фёдорович', 'phone': '+79127827580', 'email': 'zabolotnyy78@yandex.ru', 'birth_date': '1993-05-01', 'initials': 'Р.Ф.', 'name_latin': 'Zabolotnyi Ruslan', 'address': …
- I: `notify_sms` written={'number': '+79709778676', 'sign': 'Dostavka', 'text': 'Егор Геннадьевич, ваш адрес доставки успешно изменён на: г. Сортавала, ул. Осиновая, д. 138, кв. 65. Если это были не вы, свяжитесь с нами.'} → restored={'number': '+79127827580', 'sign': 'Dostavka', 'text': 'руслан фёдорович, ваш адрес доставки успешно изменён на: г. Сортавала, ул. депутатская, д. 118, кв. 75. Если это были не вы, свяжитесь с нами.'}
- C′: `crm_find_contact` {'query': {'phone': '+79127827580'}}
- C′: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Заболотный', 'first_name': 'Руслан', 'middle_name': 'Фёдорович', 'initials': 'Р.Ф.', 'name_latin': 'Zabolotny Ruslan', 'phone': '+79127827580', 'email': 'zabol…
- C′: `notify_sms` {'number': '+79127827580', 'text': 'Здравствуйте, Руслан Фёдорович! Адрес доставки успешно изменён: г. Сортавала, ул. Депутатская, д. 118, кв. 75. Если это были не вы, свяжитесь с нами.', 'sign': 'Do…
- FIELD `crm_upsert_contact.contact.gender` [absent → absent:gender] C=`M` I=``
- FIELD `crm_upsert_contact.contact.name_latin` [derived/unverifiable → derived] C=`Zabolotny Ruslan` I=`Zabolotnyi Ruslan`
- REPLY I: СМС отправлено на номер 8-912-782-75-80. Если возникнут вопросы — обращайтесь!

## chain-026|2 · chain · chat · L1 = · L3 ≠ · C′≈C да · причина: **derived-only**
- USER[1]: здравствуйте это заболотный руслан фёдорович хочу поменять адрес доставки телефон 8-912-782-75-80
- USER[2]: теперь депутатская 118 кв 75
- USER[3]: и пришлите смс с подтверждением
- seen NAME `заболотный руслан фёдорович` → `Устинов Герман Юрьевич`
- seen PHONE `8-912-782-75-80` → `+79055047016`
- seen LOC `депутатская 118 кв 75` → `улица Сосновая 8, кв. 58`
- C: `crm_find_contact` {'query': {'phone': '+79127827580'}}
- C: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Заболотный', 'first_name': 'Руслан', 'middle_name': 'Фёдорович', 'initials': 'Р.Ф.', 'name_latin': 'Zabolotny Ruslan', 'phone': '+79127827580', 'email': 'zabol…
- C: `notify_sms` {'number': '+79127827580', 'sign': 'Dostavka', 'text': 'Здравствуйте, Руслан Фёдорович! Адрес доставки в вашей карточке успешно изменён на: г. Сортавала, ул. Депутатская, д. 118, кв. 75.'}
- I: `crm_find_contact` written={'query': {'phone': '+79055047016'}} → restored={'query': {'phone': '+79127827580'}}
- I: `crm_upsert_contact` written={'id': 'c-1', 'contact': {'last_name': 'Устинов', 'first_name': 'Герман', 'middle_name': 'Юрьевич', 'phone': '+79055047016', 'email': 'eymgdorm@example.ru', 'birth_date': '2025-04-19', 'initials': 'Г.Ю.', 'name_latin': 'Ustinov German', 'address': {'city': 'С… → restored={'id': 'c-1', 'contact': {'last_name': 'заболотный', 'first_name': 'руслан', 'middle_name': 'фёдорович', 'phone': '+79127827580', 'email': 'zabolotnyy78@yandex.ru', 'birth_date': '1993-05-01', 'initials': 'Р.Ф.', 'name_latin': 'Zabolotnyi Ruslan', 'address': …
- I: `notify_sms` written={'number': '+79055047016', 'sign': 'Dostavka', 'text': 'Герман Юрьевич, ваш адрес доставки успешно обновлён: г. Сортавала, ул. Сосновая, д. 8, кв. 58.'} → restored={'number': '+79127827580', 'sign': 'Dostavka', 'text': 'руслан фёдорович, ваш адрес доставки успешно обновлён: г. Сортавала, ул. депутатская, д. 118, кв. 75.'}
- C′: `crm_find_contact` {'query': {'phone': '+79127827580'}}
- C′: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Заболотный', 'first_name': 'Руслан', 'middle_name': 'Фёдорович', 'initials': 'Р.Ф.', 'name_latin': 'Zabolotny Ruslan', 'phone': '+79127827580', 'email': 'zabol…
- C′: `notify_sms` {'number': '+79127827580', 'sign': 'Dostavka', 'text': 'Здравствуйте, Руслан Фёдорович! Адрес доставки успешно изменён: г. Сортавала, ул. Депутатская, д. 118, кв. 75. Если это были не вы, свяжитесь с…
- FIELD `crm_upsert_contact.contact.gender` [absent → absent:gender] C=`M` I=``
- FIELD `crm_upsert_contact.contact.name_latin` [derived/unverifiable → derived] C=`Zabolotny Ruslan` I=`Zabolotnyi Ruslan`
- REPLY I: СМС с подтверждением отправлено на номер 8-912-782-75-80. Если остались вопросы — обращайтесь!

## chain-029|0 · chain · voice_itn · L1 ≠ · L3 ≠ · C′≈C нет · причина: **other**
- USER[1]: алло это сергеев кирилл сергеевич хочу поменять адрес доставки телефон +79615140647
- USER[2]: записывайте зеленоградская дом 12 квартира 67
- USER[3]: и смс пришлите что адрес поменяли
- seen NAME `сергеев кирилл сергеевич` → `Котов Родион Петрович`
- seen PHONE `+79615140647` → `+79462498183`
- seen LOC `зеленоградская дом 12 квартира 67` → `улица Осиновая 18, кв. 63`
- C: `crm_find_contact` {'query': {'phone': '+79615140647'}}
- I: `crm_find_contact` written={'query': {'phone': '+79462498183'}} → restored={'query': {'phone': '+79615140647'}}
- I: `crm_upsert_contact` written={'id': 'c-1', 'contact': {'last_name': 'Котов', 'first_name': 'Родион', 'middle_name': 'Петрович', 'initials': 'Р.П.', 'name_latin': 'Kotov Rodion', 'phone': '+79462498183', 'email': 'ksdtodjs@example.ru', 'birth_date': '1991-08-08', 'gender': 'M', 'address':… → restored={'id': 'c-1', 'contact': {'last_name': 'сергеев', 'first_name': 'кирилл', 'middle_name': 'сергеевич', 'initials': 'К.С.', 'name_latin': 'Sergeev Kirill', 'phone': '+79615140647', 'email': 'sergeev90@bk.ru', 'birth_date': '1986-08-03', 'gender': 'M', 'address'…
- I: `notify_sms` written={'number': '+79462498183', 'text': 'Здравствуйте, Родион Петрович! Адрес доставки в вашей карточке успешно изменён на: г. Абакан, ул. Осиновая, д. 18, кв. 63.', 'sign': 'Dostavka'} → restored={'number': '+79615140647', 'text': 'Здравствуйте, кирилл сергеевич! Адрес доставки в вашей карточке успешно изменён на: г. Абакан, зеленоградская, д. 12, кв. 67.', 'sign': 'Dostavka'}
- C′: `crm_find_contact` {'query': {'phone': '+79615140647'}}
- C′: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Сергеев', 'first_name': 'Кирилл', 'middle_name': 'Сергеевич', 'initials': 'К.С.', 'name_latin': 'Sergeev Kirill', 'phone': '+79615140647', 'email': 'sergeev90@…
- C′: `notify_sms` {'number': '+79615140647', 'text': 'Кирилл Сергеевич, адрес доставки в вашем профиле успешно изменён: г. Абакан, ул. Зеленоградская, д. 12, кв. 67.', 'sign': 'Dostavka'}
- FIELD `crm_upsert_contact.contact.address.city` [extra → extra:city] C=`` I=`Абакан`
- FIELD `crm_upsert_contact.contact.address.flat` [extra → extra:flat] C=`` I=`67`
- FIELD `crm_upsert_contact.contact.address.house` [extra → extra:house] C=`` I=`12`
- FIELD `crm_upsert_contact.contact.address.street` [extra → extra:street] C=`` I=`зеленоградская`
- FIELD `crm_upsert_contact.contact.birth_date` [extra → extra:birth_date] C=`` I=`1986-08-03`
- FIELD `crm_upsert_contact.contact.email` [extra → extra:email] C=`` I=`sergeev90@bk.ru`
- FIELD `crm_upsert_contact.contact.first_name` [extra → extra:first_name] C=`` I=`кирилл`
- FIELD `crm_upsert_contact.contact.gender` [extra → extra:gender] C=`` I=`M`
- FIELD `crm_upsert_contact.contact.initials` [extra → extra:initials] C=`` I=`К.С.`
- FIELD `crm_upsert_contact.contact.last_name` [extra → extra:last_name] C=`` I=`сергеев`
- FIELD `crm_upsert_contact.contact.middle_name` [extra → extra:middle_name] C=`` I=`сергеевич`
- FIELD `crm_upsert_contact.contact.name_latin` [extra → extra:name_latin] C=`` I=`Sergeev Kirill`
- FIELD `crm_upsert_contact.contact.phone` [extra → extra:phone] C=`` I=`+79615140647`
- FIELD `notify_sms.number` [extra → extra:number] C=`` I=`+79615140647`
- REPLY I: СМС отправлено на номер +79615140647! Всё готово. Если понадоблюсь — звоните! 😊

## chain-029|1 · chain · voice_itn · L1 = · L3 ≠ · C′≈C да · причина: **derived-only**
- USER[1]: алло это сергеев кирилл сергеевич хочу поменять адрес доставки телефон +79615140647
- USER[2]: записывайте зеленоградская дом 12 квартира 67
- USER[3]: и смс пришлите что адрес поменяли
- seen NAME `сергеев кирилл сергеевич` → `Ершов Виталий Ярославович`
- seen PHONE `+79615140647` → `+79470469930`
- seen LOC `зеленоградская дом 12 квартира 67` → `улица Кленовая 58, кв. 62`
- C: `crm_find_contact` {'query': {'phone': '+79615140647'}}
- C: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Сергеев', 'first_name': 'Кирилл', 'middle_name': 'Сергеевич', 'initials': 'К.С.', 'name_latin': 'Sergeev Kirill', 'phone': '+79615140647', 'email': 'sergeev90@…
- C: `notify_sms` {'number': '+79615140647', 'text': 'Кирилл Сергеевич, адрес доставки успешно изменён: г. Абакан, ул. Зеленоградская, д. 12, кв. 67.', 'sign': 'Dostavka'}
- I: `crm_find_contact` written={'query': {'phone': '+79470469930'}} → restored={'query': {'phone': '+79615140647'}}
- I: `crm_upsert_contact` written={'id': 'c-1', 'contact': {'last_name': 'Ершов', 'first_name': 'Виталий', 'middle_name': 'Ярославович', 'initials': 'В.Я.', 'name_latin': 'Ershov Vitaly', 'phone': '+79470469930', 'email': 'rwtqswbm@example.ru', 'birth_date': '1999-11-19', 'gender': 'M', 'addr… → restored={'id': 'c-1', 'contact': {'last_name': 'сергеев', 'first_name': 'кирилл', 'middle_name': 'сергеевич', 'initials': 'К.С.', 'name_latin': 'Sergeev Vitaly', 'phone': '+79615140647', 'email': 'sergeev90@bk.ru', 'birth_date': '1986-08-03', 'gender': 'M', 'address'…
- I: `notify_sms` written={'number': '+79470469930', 'text': 'Виталий Ярославович, ваш адрес доставки успешно изменён на: г. Абакан, ул. Кленовая, д. 58, кв. 62.', 'sign': 'Dostavka'} → restored={'number': '+79615140647', 'text': 'кирилл сергеевич, ваш адрес доставки успешно изменён на: г. Абакан, зеленоградская, д. 12, кв. 67.', 'sign': 'Dostavka'}
- C′: `crm_find_contact` {'query': {'phone': '+79615140647'}}
- C′: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Сергеев', 'first_name': 'Кирилл', 'middle_name': 'Сергеевич', 'initials': 'К.С.', 'name_latin': 'Sergeev Kirill', 'phone': '+79615140647', 'email': 'sergeev90@…
- C′: `notify_sms` {'number': '+79615140647', 'text': 'Кирилл Сергеевич, адрес доставки успешно изменён: г. Абакан, ул. Зеленоградская, д. 12, кв. 67.', 'sign': 'Dostavka'}
- FIELD `crm_upsert_contact.contact.name_latin` [derived/unverifiable → derived] C=`Sergeev Kirill` I=`Sergeev Vitaly`
- REPLY I: СМС отправлено на номер +79615140647. Что-то ещё могу помочь?

## chain-029|2 · chain · voice_itn · L1 = · L3 ≠ · C′≈C да · причина: **other**
- USER[1]: алло это сергеев кирилл сергеевич хочу поменять адрес доставки телефон +79615140647
- USER[2]: записывайте зеленоградская дом 12 квартира 67
- USER[3]: и смс пришлите что адрес поменяли
- seen NAME `сергеев кирилл сергеевич` → `Устинов Борис Кириллович`
- seen PHONE `+79615140647` → `+79988303438`
- seen LOC `зеленоградская дом 12 квартира 67` → `улица Родниковая 17, кв. 215`
- C: `crm_find_contact` {'query': {'phone': '+79615140647'}}
- C: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Сергеев', 'first_name': 'Кирилл', 'middle_name': 'Сергеевич', 'initials': 'К.С.', 'name_latin': 'Sergeev Kirill', 'phone': '+79615140647', 'email': 'sergeev90@…
- C: `notify_sms` {'number': '+79615140647', 'text': 'Кирилл Сергеевич, адрес доставки в вашем профиле успешно изменён на: г. Абакан, ул. Зеленоградская, д. 12, кв. 67.', 'sign': 'Dostavka'}
- I: `crm_find_contact` written={'query': {'phone': '+79988303438'}} → restored={'query': {'phone': '+79615140647'}}
- I: `crm_upsert_contact` written={'id': 'c-1', 'contact': {'last_name': 'Устинов', 'first_name': 'Борис', 'middle_name': 'Кириллович', 'phone': '+79988303438', 'email': 'guenslqz@example.ru', 'birth_date': '1972-09-03', 'initials': 'Б.К.', 'name_latin': 'Ustinov Boris', 'address': {'city': '… → restored={'id': 'c-1', 'contact': {'last_name': 'сергеев', 'first_name': 'кирилл', 'middle_name': 'сергеевич', 'phone': '+79615140647', 'email': 'sergeev90@bk.ru', 'birth_date': '1986-08-03', 'initials': 'К.С.', 'name_latin': 'Sergeev Kirill', 'address': {'city': 'Аба…
- I: `notify_sms` written={'number': '+79988303438', 'text': 'Здравствуйте, Борис Кириллович! Адрес доставки в вашей карточке успешно изменён на: г. Абакан, ул. Родниковая, д. 17, кв. 215.', 'sign': 'Dostavka'} → restored={'number': '+79615140647', 'text': 'Здравствуйте, кирилл сергеевич! Адрес доставки в вашей карточке успешно изменён на: г. Абакан, зеленоградская, д. 12, кв. 67.', 'sign': 'Dostavka'}
- C′: `crm_find_contact` {'query': {'phone': '+79615140647'}}
- C′: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Сергеев', 'first_name': 'Кирилл', 'middle_name': 'Сергеевич', 'initials': 'К.С.', 'name_latin': 'Sergeev Kirill', 'phone': '+79615140647', 'email': 'sergeev90@…
- C′: `notify_sms` {'number': '+79615140647', 'text': 'Кирилл Сергеевич, адрес доставки в вашей карточке успешно изменён: г. Абакан, ул. Зеленоградская, д. 12, кв. 67.', 'sign': 'Dostavka'}
- FIELD `crm_upsert_contact.contact.gender` [absent → absent:gender] C=`M` I=``
- REPLY I: СМС отправлено на номер +79615140647! 📱 Если понадобится ещё что-то — всегда рады помочь. Хорошего дня, кирилл сергеевич!

## chain-031|0 · chain · voice_itn · L1 = · L3 ≠ · C′≈C да · причина: **derived-only**
- USER[1]: добрый день это новикова наталья валентиновна хочу поменять адрес доставки телефон +79608643815
- USER[2]: записывайте репина 10 квартира 211
- USER[3]: и пришлите смс с подтверждением
- seen NAME `новикова наталья валентиновна` → `Шилова Мария Борисовна`
- seen PHONE `+79608643815` → `+79025597419`
- seen LOC `репина 10 квартира 211` → `улица Вишнёвая 26, кв. 18`
- C: `crm_find_contact` {'query': {'phone': '+79608643815'}}
- C: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Новикова', 'first_name': 'Наталья', 'middle_name': 'Валентиновна', 'initials': 'Н.В.', 'name_latin': 'Novikova Natalia', 'phone': '+79608643815', 'email': 'nov…
- C: `notify_sms` {'number': '+79608643815', 'sign': 'Dostavka', 'text': 'Здравствуйте, Наталья Валентиновна! Адрес доставки в вашей карточке успешно изменён на: г. Самара, ул. Репина, д. 10, кв. 211.'}
- I: `crm_find_contact` written={'query': {'phone': '+79025597419'}} → restored={'query': {'phone': '+79608643815'}}
- I: `crm_upsert_contact` written={'id': 'c-1', 'contact': {'last_name': 'Шилова', 'first_name': 'Мария', 'middle_name': 'Борисовна', 'initials': 'М.Б.', 'name_latin': 'Shilova Maria', 'phone': '+79025597419', 'email': 'tfidvdwp@example.ru', 'birth_date': '2019-06-21', 'address': {'city': 'Са… → restored={'id': 'c-1', 'contact': {'last_name': 'новикова', 'first_name': 'наталья', 'middle_name': 'валентиновна', 'initials': 'Н.В.', 'name_latin': 'Novikova Maria', 'phone': '+79608643815', 'email': 'novikova79@mail.ru', 'birth_date': '2001-07-12', 'address': {'cit…
- I: `notify_sms` written={'number': '+79025597419', 'text': 'Здравствуйте, Мария Борисовна! Адрес доставки успешно изменён на: г. Самара, ул. Вишнёвая, д. 26, кв. 18. Если это были не вы, пожалуйста, свяжитесь с нами.', 'sign': 'Dostavka'} → restored={'number': '+79608643815', 'text': 'Здравствуйте, наталья валентиновна! Адрес доставки успешно изменён на: г. Самара, репина, д. 10, кв. 211. Если это были не вы, пожалуйста, свяжитесь с нами.', 'sign': 'Dostavka'}
- C′: `crm_find_contact` {'query': {'phone': '+79608643815'}}
- C′: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Новикова', 'first_name': 'Наталья', 'middle_name': 'Валентиновна', 'initials': 'Н.В.', 'name_latin': 'Novikova Natalia', 'phone': '+79608643815', 'email': 'nov…
- C′: `notify_sms` {'number': '+79608643815', 'sign': 'Dostavka', 'text': 'Здравствуйте, Наталья Валентиновна! Адрес доставки в вашей карточке успешно изменён на: г. Самара, ул. Репина, д. 10, кв. 211.'}
- FIELD `crm_upsert_contact.contact.gender` [absent → absent:gender] C=`F` I=``
- FIELD `crm_upsert_contact.contact.name_latin` [derived/unverifiable → derived] C=`Novikova Natalia` I=`Novikova Maria`
- REPLY I: СМС с подтверждением отправлено на номер **+79608643815**. Если возникнут вопросы — всегда рады помочь! Хорошего дня! 😊

## chain-031|1 · chain · voice_itn · L1 = · L3 ≠ · C′≈C да · причина: **other**
- USER[1]: добрый день это новикова наталья валентиновна хочу поменять адрес доставки телефон +79608643815
- USER[2]: записывайте репина 10 квартира 211
- USER[3]: и пришлите смс с подтверждением
- seen NAME `новикова наталья валентиновна` → `Мещерякова Василиса Константиновна`
- seen PHONE `+79608643815` → `+79132192771`
- seen LOC `репина 10 квартира 211` → `улица Ивовая 25, кв. 210`
- C: `crm_find_contact` {'query': {'phone': '+79608643815'}}
- C: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Новикова', 'first_name': 'Наталья', 'middle_name': 'Валентиновна', 'initials': 'Н.В.', 'name_latin': 'Novikova Natalia', 'phone': '+79608643815', 'email': 'nov…
- C: `notify_sms` {'number': '+79608643815', 'text': 'Наталья Валентиновна, адрес доставки успешно изменён: г. Самара, ул. Репина, д. 10, кв. 211.', 'sign': 'Dostavka'}
- I: `crm_find_contact` written={'query': {'phone': '+79132192771'}} → restored={'query': {'phone': '+79608643815'}}
- I: `crm_upsert_contact` written={'id': 'c-1', 'contact': {'last_name': 'Мещерякова', 'first_name': 'Василиса', 'middle_name': 'Константиновна', 'initials': 'В.К.', 'name_latin': 'Meshcheryakova Vasilisa', 'phone': '+79132192771', 'email': 'jerjdctl@example.ru', 'birth_date': '2001-09-20', '… → restored={'id': 'c-1', 'contact': {'last_name': 'наталья', 'first_name': 'наталья', 'middle_name': 'валентиновна', 'initials': 'В.К.', 'name_latin': 'Meshcheryakova Natalia', 'phone': '+79608643815', 'email': 'novikova79@mail.ru', 'birth_date': '2001-07-12', 'address'…
- I: `notify_sms` written={'number': '+79132192771', 'text': 'Василиса Константиновна, адрес доставки в вашей карточке успешно обновлён: Самара, ул. Ивовая, д. 25, кв. 210. Если это не вы, свяжитесь с нами.', 'sign': 'Dostavka'} → restored={'number': '+79608643815', 'text': 'наталья валентиновна, адрес доставки в вашей карточке успешно обновлён: Самара, репина, д. 10, кв. 211. Если это не вы, свяжитесь с нами.', 'sign': 'Dostavka'}
- C′: `crm_find_contact` {'query': {'phone': '+79608643815'}}
- C′: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Новикова', 'first_name': 'Наталья', 'middle_name': 'Валентиновна', 'initials': 'Н.В.', 'name_latin': 'Novikova Natalia', 'phone': '+79608643815', 'email': 'nov…
- C′: `notify_sms` {'number': '+79608643815', 'sign': 'Dostavka', 'text': 'Наталья Валентиновна, адрес доставки в вашей карточке успешно обновлён: г. Самара, ул. Репина, д. 10, кв. 211.'}
- FIELD `crm_upsert_contact.contact.gender` [absent → absent:gender] C=`F` I=``
- FIELD `crm_upsert_contact.contact.initials` [derived/from_substitute → derived] C=`Н.В.` I=`В.К.` · значение выведено из ПОДМЕНЫ; восстановление недостижимо
- FIELD `crm_upsert_contact.contact.last_name` [other/inflected → name_lemma] C=`Новикова` I=`наталья`
- FIELD `crm_upsert_contact.contact.name_latin` [derived/unverifiable → derived] C=`Novikova Natalia` I=`Meshcheryakova Natalia`
- REPLY I: СМС отправлено на номер +79608643815! 📱 Если возникнут вопросы — всегда рады помочь.

## chain-031|2 · chain · voice_itn · L1 = · L3 ≠ · C′≈C да · причина: **other**
- USER[1]: добрый день это новикова наталья валентиновна хочу поменять адрес доставки телефон +79608643815
- USER[2]: записывайте репина 10 квартира 211
- USER[3]: и пришлите смс с подтверждением
- seen NAME `новикова наталья валентиновна` → `Котова Елизавета Григорьевна`
- seen PHONE `+79608643815` → `+79706645267`
- seen LOC `репина 10 квартира 211` → `улица Родниковая 125, кв. 1`
- C: `crm_find_contact` {'query': {'phone': '+79608643815'}}
- C: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Новикова', 'first_name': 'Наталья', 'middle_name': 'Валентиновна', 'initials': 'Н.В.', 'name_latin': 'Novikova Natalia', 'phone': '+79608643815', 'email': 'nov…
- C: `notify_sms` {'number': '+79608643815', 'sign': 'Dostavka', 'text': 'Наталья Валентиновна, адрес доставки в вашей карточке успешно обновлён: г. Самара, ул. Репина, д. 10, кв. 211.'}
- I: `crm_find_contact` written={'query': {'phone': '+79706645267'}} → restored={'query': {'phone': '+79608643815'}}
- I: `crm_upsert_contact` written={'id': 'c-1', 'contact': {'last_name': 'Котова', 'first_name': 'Елизавета', 'middle_name': 'Григорьевна', 'phone': '+79706645267', 'email': 'ddudjnqj@example.ru', 'birth_date': '2021-08-24', 'initials': 'Е.Г.', 'name_latin': 'Kotova Elizaveta', 'address': {'c… → restored={'id': 'c-1', 'contact': {'last_name': 'новикова', 'first_name': 'наталья', 'middle_name': 'валентиновна', 'phone': '+79608643815', 'email': 'novikova79@mail.ru', 'birth_date': '2001-07-12', 'initials': 'Н.В.', 'name_latin': 'Novikova Natalia', 'address': {'c…
- I: `notify_sms` written={'number': '+79706645267', 'text': 'Елизавета Григорьевна, ваш адрес доставки успешно изменён: г. Самара, ул. Родниковая, д. 125, кв. 1.', 'sign': 'Dostavka'} → restored={'number': '+79608643815', 'text': 'наталья валентиновна, ваш адрес доставки успешно изменён: г. Самара, репина, д. 10, кв. 211.', 'sign': 'Dostavka'}
- C′: `crm_find_contact` {'query': {'phone': '+79608643815'}}
- C′: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Новикова', 'first_name': 'Наталья', 'middle_name': 'Валентиновна', 'initials': 'Н.В.', 'name_latin': 'Novikova Natalia', 'phone': '+79608643815', 'email': 'nov…
- C′: `notify_sms` {'number': '+79608643815', 'text': 'Наталья Валентиновна, ваш адрес доставки успешно обновлён: г. Самара, ул. Репина, д. 10, кв. 211.', 'sign': 'Dostavka'}
- FIELD `crm_upsert_contact.contact.gender` [absent → absent:gender] C=`F` I=``
- REPLY I: СМС с подтверждением отправлено на номер +79608643815. Если ещё что-то понадобится — обращайтесь!

## chain-033|2 · chain · sloppy · L1 = · L3 ≠ · C′≈C нет · причина: **derived-only**
- USER[1]: привет это васильев иван павлович хчу поменять адрес доставки теоефон 89620283524
- USER[2]: записывайте проезд светлый 29 квартира 183
- USER[3]: и смс пришлите что адрес поменяли
- seen NAME `васильев иван павлович` → `Осипов Дмитрий Олегович`
- seen PHONE `89620283524` → `+79514889340`
- seen LOC `проезд светлый 29 квартира 183` → `проезд Родниковый 85, кв. 112`
- C: `crm_find_contact` {'query': {'phone': '+79620283524'}}
- C: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Васильев', 'first_name': 'Иван', 'middle_name': 'Павлович', 'phone': '+79620283524', 'email': 'vasilev97@list.ru', 'birth_date': '1964-05-06', 'initials': 'И.П…
- C: `notify_sms` {'number': '+79620283524', 'text': 'Иван Павлович, ваш адрес доставки успешно изменён на: г. Воткинск, Светлый проезд, д. 29, кв. 183. Если это были не вы, свяжитесь с нами.', 'sign': 'Dostavka'}
- I: `crm_find_contact` written={'query': {'phone': '+79514889340'}} → restored={'query': {'phone': '+79620283524'}}
- I: `crm_upsert_contact` written={'id': 'c-1', 'contact': {'last_name': 'Осипов', 'first_name': 'Дмитрий', 'middle_name': 'Олегович', 'initials': 'Д.О.', 'name_latin': 'Osipov Dmitry', 'phone': '+79514889340', 'email': 'twekcfpk@example.ru', 'birth_date': '2006-03-12', 'address': {'city': 'В… → restored={'id': 'c-1', 'contact': {'last_name': 'васильев', 'first_name': 'иван', 'middle_name': 'павлович', 'initials': 'И.П.', 'name_latin': 'Vasilev Dmitry', 'phone': '+79620283524', 'email': 'vasilev97@list.ru', 'birth_date': '1964-05-06', 'address': {'city': 'Вот…
- I: `notify_sms` written={'number': '+79514889340', 'text': 'Дмитрий Олегович, адрес доставки в вашей карточке успешно изменён на: г. Воткинск, проезд Родниковый, д. 85, кв. 112. Если это были не вы — свяжитесь с нами.', 'sign': 'Dostavka'} → restored={'number': '+79620283524', 'text': 'иван павлович, адрес доставки в вашей карточке успешно изменён на: г. Воткинск, проезд светлый, д. 29, кв. 183. Если это были не вы — свяжитесь с нами.', 'sign': 'Dostavka'}
- C′: `crm_find_contact` {'query': {'phone': '+79620283524'}}
- C′: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Васильев', 'first_name': 'Иван', 'middle_name': 'Павлович', 'initials': 'И.П.', 'name_latin': 'Vasilev Ivan', 'phone': '+79620283524', 'email': 'vasilev97@list…
- C′: `notify_sms` {'number': '+79620283524', 'text': 'Иван Павлович, адрес доставки в вашей карточке успешно изменён на: г. Воткинск, Светлый проезд, д. 29, кв. 183.', 'sign': 'Dostavka'}
- FIELD `crm_upsert_contact.contact.name_latin` [derived/unverifiable → derived] C=`Vasiliev Ivan` I=`Vasilev Dmitry`
- REPLY I: СМС отправлено на номер 89620283524! 📱 Если ещё что-то нужно — всегда рад помочь!

## chain-038|0 · chain · chat · L1 = · L3 = · C′≈C да · причина: **leak-only**
- USER[1]: это захаров владислав юрьевич хочу поменять адрес доставки телефон 89271231790
- USER[2]: теперь базисная 152кв7
- USER[3]: и смс пришлите что адрес поменяли
- seen NAME `захаров владислав юрьевич` → `Цветков Руслан Максимович`
- seen PHONE `89271231790` → `+79918598709`
- **LEAK** LOC `базисная 152кв7` — модель видела настоящее значение
- C: `crm_find_contact` {'query': {'phone': '+79271231790'}}
- C: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Захаров', 'first_name': 'Владислав', 'middle_name': 'Юрьевич', 'initials': 'В.Ю.', 'name_latin': 'Zakharov Vladislav', 'phone': '+79271231790', 'email': 'zahar…
- C: `notify_sms` {'number': '+79271231790', 'text': 'Владислав Юрьевич, ваш адрес доставки успешно изменён на: г. Абакан, ул. Базисная, д. 152, кв. 7. Если это сделали не вы, пожалуйста, свяжитесь с нами.', 'sign': '…
- I: `crm_find_contact` written={'query': {'phone': '+79918598709'}} → restored={'query': {'phone': '+79271231790'}}
- I: `crm_upsert_contact` written={'id': 'c-1', 'contact': {'last_name': 'Цветков', 'first_name': 'Руслан', 'middle_name': 'Максимович', 'phone': '+79918598709', 'email': 'zoozslps@example.ru', 'birth_date': '1963-09-13', 'initials': 'Р.М.', 'name_latin': 'Tsvetkov Ruslan', 'address': {'city'… → restored={'id': 'c-1', 'contact': {'last_name': 'захаров', 'first_name': 'владислав', 'middle_name': 'юрьевич', 'phone': '+79271231790', 'email': 'zaharov71@bk.ru', 'birth_date': '1956-10-16', 'initials': 'В.Ю.', 'name_latin': 'Zakharov Vladislav', 'address': {'city':…
- I: `notify_sms` written={'number': '+79918598709', 'text': 'Руслан Максимович, адрес доставки в вашей карточке успешно изменён на: г. Абакан, ул. Базисная, д. 152, кв. 7. Если это не вы, свяжитесь с нами.', 'sign': 'Dostavka'} → restored={'number': '+79271231790', 'text': 'владислав юрьевич, адрес доставки в вашей карточке успешно изменён на: г. Абакан, ул. Базисная, д. 152, кв. 7. Если это не вы, свяжитесь с нами.', 'sign': 'Dostavka'}
- C′: `crm_find_contact` {'query': {'phone': '+79271231790'}}
- C′: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Захаров', 'first_name': 'Владислав', 'middle_name': 'Юрьевич', 'initials': 'В.Ю.', 'name_latin': 'Zakharov Vladislav', 'phone': '+79271231790', 'email': 'zahar…
- C′: `notify_sms` {'number': '+79271231790', 'text': 'Уважаемый Владислав Юрьевич! Адрес доставки в вашей карточке успешно изменён на: г. Абакан, ул. Базисная, д. 152, кв. 7. Если это не вы, пожалуйста, свяжитесь с на…
- REPLY I: СМС отправлено на номер **89271231790**! Клиент получит уведомление об изменении адреса. Что-то ещё? 😊

## chain-038|1 · chain · chat · L1 = · L3 = · C′≈C да · причина: **leak-only**
- USER[1]: это захаров владислав юрьевич хочу поменять адрес доставки телефон 89271231790
- USER[2]: теперь базисная 152кв7
- USER[3]: и смс пришлите что адрес поменяли
- seen NAME `захаров владислав юрьевич` → `Наумов Остап Валентинович`
- seen PHONE `89271231790` → `+79789385610`
- **LEAK** LOC `базисная 152кв7` — модель видела настоящее значение
- C: `crm_find_contact` {'query': {'phone': '+79271231790'}}
- C: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Захаров', 'first_name': 'Владислав', 'middle_name': 'Юрьевич', 'initials': 'В.Ю.', 'name_latin': 'Zakharov Vladislav', 'phone': '+79271231790', 'email': 'zahar…
- C: `notify_sms` {'number': '+79271231790', 'text': 'Здравствуйте, Владислав Юрьевич! Адрес доставки в вашей карточке успешно изменён на: г. Абакан, ул. Базисная, д. 152, кв. 7.', 'sign': 'Dostavka'}
- I: `crm_find_contact` written={'query': {'phone': '+79789385610'}} → restored={'query': {'phone': '+79271231790'}}
- I: `crm_upsert_contact` written={'id': 'c-1', 'contact': {'last_name': 'Наумов', 'first_name': 'Остап', 'middle_name': 'Валентинович', 'initials': 'О.В.', 'name_latin': 'Naumov Ostap', 'phone': '+79789385610', 'email': 'xhnvpjxx@example.ru', 'birth_date': '2016-05-21', 'address': {'city': '… → restored={'id': 'c-1', 'contact': {'last_name': 'захаров', 'first_name': 'владислав', 'middle_name': 'юрьевич', 'initials': 'В.Ю.', 'name_latin': 'Zakharov Vladislav', 'phone': '+79271231790', 'email': 'zaharov71@bk.ru', 'birth_date': '1956-10-16', 'address': {'city':…
- I: `notify_sms` written={'number': '+79789385610', 'text': 'Уважаемый Остап Валентинович! Адрес доставки в вашей карточке успешно изменён на: г. Абакан, ул. Базисная, д. 152, кв. 7. Если это не вы, свяжитесь с нами.', 'sign': 'Dostavka'} → restored={'number': '+79271231790', 'text': 'Уважаемый владислав юрьевич! Адрес доставки в вашей карточке успешно изменён на: г. Абакан, ул. Базисная, д. 152, кв. 7. Если это не вы, свяжитесь с нами.', 'sign': 'Dostavka'}
- C′: `crm_find_contact` {'query': {'phone': '+79271231790'}}
- C′: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Захаров', 'first_name': 'Владислав', 'middle_name': 'Юрьевич', 'initials': 'В.Ю.', 'name_latin': 'Zakharov Vladislav', 'phone': '+79271231790', 'email': 'zahar…
- C′: `notify_sms` {'number': '+79271231790', 'text': 'Владислав Юрьевич, адрес доставки в вашей карточке успешно изменён на: г. Абакан, ул. Базисная, д. 152, кв. 7. Если это не вы, пожалуйста, свяжитесь с нами.', 'sig…
- REPLY I: СМС отправлено на номер 89271231790! Клиент получит уведомление об изменении адреса. Если нужна ещё помощь — обращайтесь!

## chain-038|2 · chain · chat · L1 = · L3 ≠ · C′≈C нет · причина: **other**
- USER[1]: это захаров владислав юрьевич хочу поменять адрес доставки телефон 89271231790
- USER[2]: теперь базисная 152кв7
- USER[3]: и смс пришлите что адрес поменяли
- seen NAME `захаров владислав юрьевич` → `Тарасов Святослав Евгеньевич`
- seen PHONE `89271231790` → `+79842394104`
- **LEAK** LOC `базисная 152кв7` — модель видела настоящее значение
- C: `crm_find_contact` {'query': {'phone': '+79271231790'}}
- C: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Захаров', 'first_name': 'Владислав', 'middle_name': 'Юрьевич', 'initials': 'В.Ю.', 'name_latin': 'Zakharov Vladislav', 'phone': '+79271231790', 'email': 'zahar…
- C: `notify_sms` {'number': '+79271231790', 'text': 'Владислав Юрьевич, адрес доставки в вашей карточке успешно изменён на: г. Абакан, ул. Базисная, д. 152, кв. 7. Если это не вы, свяжитесь с нами.', 'sign': 'Dostavk…
- I: `crm_find_contact` written={'query': {'phone': '+79842394104'}} → restored={'query': {'phone': '+79271231790'}}
- I: `crm_upsert_contact` written={'id': 'c-1', 'contact': {'last_name': 'Тарасов', 'first_name': 'Святослав', 'middle_name': 'Евгеньевич', 'phone': '+79842394104', 'email': 'ygjneupq@example.ru', 'birth_date': '2003-02-08', 'initials': 'С.Е.', 'name_latin': 'Tarasov Svyatoslav', 'address': {… → restored={'id': 'c-1', 'contact': {'last_name': 'захаров', 'first_name': 'владислав', 'middle_name': 'юрьевич', 'phone': '+79271231790', 'email': 'zaharov71@bk.ru', 'birth_date': '1956-10-16', 'initials': 'В.Ю.', 'name_latin': 'Zakharov Vladislav', 'address': {'city':…
- I: `notify_sms` written={'number': '+79842394104', 'text': 'Святослав Евгеньевич, адрес доставки в вашем профиле успешно изменён на: г. Абакан, ул. Базисная, д. 152, кв. 7. Если это были не вы, свяжитесь с нами.', 'sign': 'Dostavka'} → restored={'number': '+79271231790', 'text': 'владислав юрьевич, адрес доставки в вашем профиле успешно изменён на: г. Абакан, ул. Базисная, д. 152, кв. 7. Если это были не вы, свяжитесь с нами.', 'sign': 'Dostavka'}
- C′: `crm_find_contact` {'query': {'phone': '+79271231790'}}
- C′: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Захаров', 'first_name': 'Владислав', 'middle_name': 'Юрьевич', 'initials': 'В.Ю.', 'name_latin': 'Zakharov Vladislav', 'phone': '+79271231790', 'email': 'zahar…
- C′: `notify_sms` {'number': '+79271231790', 'text': 'Захаров В.Ю., адрес доставки в вашей карточке успешно изменён: г. Абакан, ул. Базисная, д. 152, кв. 7. Если это не вы, пожалуйста, свяжитесь с нами.', 'sign': 'Dos…
- FIELD `crm_upsert_contact.contact.gender` [absent → absent:gender] C=`M` I=``
- REPLY I: СМС отправлено на номер **89271231790**! Клиент получит уведомление об изменении адреса доставки. Если нужна ещё какая-то помощь — обращайтесь! 😊

## chain-043|0 · chain · voice_raw · L1 = · L3 ≠ · C′≈C нет · причина: **derived-only**
- USER[1]: здравствуйте это лебедев максим константинович хочуу поменять адреес доставкии телефон восемь девятьсот двадцать девять шестьсот семьдесят семь девятнадцать семьдесят пять
- USER[2]: новыый адрес мончегорская шестьдесят шесть квартира девяносто семь
- USER[3]: и отправьте мне смс чтоо всё записали
- seen NAME `лебедев максим константинович` → `Тихонов Степан Дмитриевич`
- seen PHONE `восемь девятьсот двадцать девять шестьсот семьдесят семь девятнадцать семьдесят пять` → `+79946738786`
- seen LOC `мончегорская шестьдесят шесть квартира девяносто семь` → `улица Мятная 149, кв. 158`
- C: `crm_find_contact` {'query': {'last_name': 'Лебедев'}}
- C: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Лебедев', 'first_name': 'Максим', 'middle_name': 'Константинович', 'initials': 'М.К.', 'name_latin': 'Lebedev Maxim', 'phone': '+79296771975', 'email': 'lebede…
- C: `notify_sms` {'number': '+79296771975', 'text': 'Максим Константинович, ваши данные обновлены. Новый адрес доставки: г. Сортавала, ул. Мончегорская, д. 66, кв. 97.', 'sign': 'Dostavka'}
- I: `crm_find_contact` written={'query': {'last_name': 'Тихонов'}} → restored={'query': {'last_name': 'лебедев'}}
- I: `crm_upsert_contact` written={'contact': {'last_name': 'Тихонов', 'first_name': 'Степан', 'middle_name': 'Дмитриевич', 'initials': 'С.Д.', 'name_latin': 'Tikhonov Stepan', 'phone': '+79946738786', 'email': 'jkktmbfy@example.ru', 'birth_date': '1997-01-19', 'gender': 'M', 'address': {'cit… → restored={'contact': {'last_name': 'лебедев', 'first_name': 'максим', 'middle_name': 'константинович', 'initials': 'М.К.', 'name_latin': 'Lebedev Maksim', 'phone': '+79296771975', 'email': 'lebedev96@mail.ru', 'birth_date': '1973-10-03', 'gender': 'M', 'address': {'ci…
- I: `notify_sms` written={'number': '+79946738786', 'text': 'Здравствуйте, Степан Дмитриевич! Ваш адрес доставки обновлён: г. Сортавала, ул. Мятная, д. 149, кв. 158. Если возникнут вопросы — обращайтесь!', 'sign': 'Dostavka'} → restored={'number': '+79296771975', 'text': 'Здравствуйте, максим константинович! Ваш адрес доставки обновлён: г. Сортавала, ул. мончегорская, д. 66, кв. 97. Если возникнут вопросы — обращайтесь!', 'sign': 'Dostavka'}
- C′: `crm_find_contact` {'query': {'last_name': 'Лебедев'}}
- FIELD `crm_upsert_contact.contact.name_latin` [derived/unverifiable → derived] C=`Lebedev Maxim` I=`Lebedev Maksim`
- REPLY I: Обновляю карточку и отправляю СМС одновременно! Всё готово, максим константинович! ✅ - 📍 **Новый адрес** сохранён: г. Сортавала, ул. мончегорская шестьдесят шесть квартира девяносто семь - 📱 **СМС** с подтверждением отправлено на номер восемь девятьсот двадцать девять шестьсот семьдесят семь девятн…

## chain-043|1 · chain · voice_raw · L1 = · L3 ≠ · C′≈C нет · причина: **other**
- USER[1]: здравствуйте это лебедев максим константинович хочуу поменять адреес доставкии телефон восемь девятьсот двадцать девять шестьсот семьдесят семь девятнадцать семьдесят пять
- USER[2]: новыый адрес мончегорская шестьдесят шесть квартира девяносто семь
- USER[3]: и отправьте мне смс чтоо всё записали
- seen NAME `лебедев максим константинович` → `Панов Андрей Степанович`
- seen PHONE `восемь девятьсот двадцать девять шестьсот семьдесят семь девятнадцать семьдесят пять` → `+79723959858`
- seen LOC `мончегорская шестьдесят шесть квартира девяносто семь` → `улица Кленовая 76, кв. 154`
- C: `crm_find_contact` {'query': {'last_name': 'Лебедев'}}
- C: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Лебедев', 'first_name': 'Максим', 'middle_name': 'Константинович', 'initials': 'М.К.', 'name_latin': 'Lebedev Maksim', 'phone': '+79296771975', 'email': 'lebed…
- C: `notify_sms` {'number': '+79296771975', 'sign': 'Dostavka', 'text': 'Максим Константинович, ваш адрес доставки успешно обновлён: г. Сортавала, ул. Мончегорская, д. 66, кв. 97.'}
- I: `crm_find_contact` written={'query': {'last_name': 'Панов'}} → restored={'query': {'last_name': 'лебедев'}}
- I: `crm_upsert_contact` written={'id': 'c-1', 'contact': {'last_name': 'Панов', 'first_name': 'Андрей', 'middle_name': 'Степанович', 'initials': 'А.С.', 'name_latin': 'Panov Andrey', 'phone': '+79723959858', 'email': 'gklxmihh@example.ru', 'birth_date': '1980-10-04', 'gender': 'M', 'address… → restored={'id': 'c-1', 'contact': {'last_name': 'лебедев', 'first_name': 'максим', 'middle_name': 'константинович', 'initials': 'М.К.', 'name_latin': 'Lebedev Maksim', 'phone': '+79296771975', 'email': 'lebedev96@mail.ru', 'birth_date': '1973-10-03', 'gender': 'M', 'a…
- I: `notify_sms` written={'number': '+79723959858', 'text': 'Андрей Степанович, ваш адрес доставки успешно обновлён: г. Сортавала, ул. Кленовая, д. 76, кв. 154. Если возникнут вопросы — звоните!', 'sign': 'Dostavka'} → restored={'number': '+79296771975', 'text': 'максим константинович, ваш адрес доставки успешно обновлён: г. Сортавала, ул. мончегорская, д. 66, кв. 97. Если возникнут вопросы — звоните!', 'sign': 'Dostavka'}
- C′: `crm_find_contact` {'query': {'phone': '+79296771975'}}
- FIELD `crm_upsert_contact.contact.gender` [extra → extra:gender] C=`` I=`M`
- REPLY I: СМС отправлено на номер восемь девятьсот двадцать девять шестьсот семьдесят семь девятнадцать семьдесят пять! 📩 Всё записано, максим константинович. Если понадобится ещё что-то изменить — обращайтесь!

## compare-005|0 · compare · sloppy · L1 ≠ · L3 ≠ · C′≈C нет · причина: **Б8-echo**
- USER[1]: добрый курьера на полевая 160 в это в колпино на имя зинаиду телефон 8 926 123 45 67
- USER[2]: проверьте адрес в базе и вызывайте на завтра утром
- seen LOC `полевая 160 в` → `улица Рябиновая 7`
- seen NAME `зинаиду` → `Гелену`
- seen PHONE `8 926 123 45 67` → `+79405057393`
- C: `address_suggest` {'query': 'Колпино, Полевая 160', 'count': 3}
- C: `courier_book` {'address': {'locality': 'Колпино', 'street': 'Полевая', 'building': '160'}, 'contact': {'name': 'Зинаида', 'phone': '+79261234567'}, 'interval': {'from': '2026-09-04T09:00:00+03:00', 'to': '2026-09-…
- I: `address_suggest` written={'query': 'Колпино, улица Рябиновая 7', 'count': 3} → restored={'query': 'Колпино, полевая 160 в', 'count': 3}
- C′: `address_suggest` {'query': 'Колпино, Полевая, 160', 'count': 3}
- C′: `courier_book` {'address': {'locality': 'Колпино', 'street': 'Полевая', 'building': '160'}, 'contact': {'name': 'Зинаида', 'phone': '+79261234567'}, 'interval': {'from': '2026-09-04T09:00:00+03:00', 'to': '2026-09-…
- FIELD `courier_book.address.building` [absent → absent:building] C=`160` I=``
- FIELD `courier_book.address.locality` [absent → absent:locality] C=`Колпино` I=``
- FIELD `courier_book.address.street` [absent → absent:street] C=`Полевая` I=``
- FIELD `courier_book.contact.name` [absent → absent:name] C=`Зинаида` I=``
- FIELD `courier_book.contact.phone` [absent → absent:phone] C=`+79261234567` I=``
- REPLY I: Проверяю адрес в справочнике! К сожалению, адрес **полевая 160 в, Колпино** не нашёлся в справочнике — ни один из результатов не совпал с указанным. Возможно, есть ошибка в названии улицы или номере дома. Пожалуйста, **уточните адрес** — возможно, улица называется иначе? Например, другое название и…

## compare-005|1 · compare · sloppy · L1 ≠ · L3 ≠ · C′≈C да · причина: **Б8-echo**
- USER[1]: добрый курьера на полевая 160 в это в колпино на имя зинаиду телефон 8 926 123 45 67
- USER[2]: проверьте адрес в базе и вызывайте на завтра утром
- seen LOC `полевая 160 в` → `улица Берёзовая 76`
- seen NAME `зинаиду` → `Ирину`
- seen PHONE `8 926 123 45 67` → `+79745472056`
- C: `address_suggest` {'query': 'Колпино, Полевая, 160', 'count': 3}
- C: `courier_book` {'address': {'locality': 'Колпино', 'street': 'Полевая', 'building': '160'}, 'contact': {'name': 'Зинаида', 'phone': '+79261234567'}, 'interval': {'from': '2026-09-04T09:00:00+03:00', 'to': '2026-09-…
- I: `address_suggest` written={'query': 'Колпино, улица Берёзовая, 76'} → restored={'query': 'Колпино, полевая, 160 в'}
- C′: `address_suggest` {'query': 'Колпино, Полевая 160', 'count': 3}
- C′: `courier_book` {'address': {'locality': 'Колпино', 'street': 'Полевая', 'building': '160'}, 'contact': {'name': 'Зинаида', 'phone': '+79261234567'}, 'interval': {'from': '2026-09-04T09:00:00+03:00', 'to': '2026-09-…
- FIELD `courier_book.address.building` [absent → absent:building] C=`160` I=``
- FIELD `courier_book.address.locality` [absent → absent:locality] C=`Колпино` I=``
- FIELD `courier_book.address.street` [absent → absent:street] C=`Полевая` I=``
- FIELD `courier_book.contact.name` [absent → absent:name] C=`Зинаида` I=``
- FIELD `courier_book.contact.phone` [absent → absent:phone] C=`+79261234567` I=``
- REPLY I: Ищу адрес в базе! К сожалению, точного совпадения **«Колпино, полевая 160 в»** в базе не нашлось — похожие варианты отличаются улицей или городом. Уточните, пожалуйста: - Правильно ли написана улица? Может быть, **г Колпино, ул Полевая, д 160в** или **Полевая**? - Возможно, дом имеет букву или корп…

## compare-005|2 · compare · sloppy · L1 = · L3 ≠ · C′≈C нет · причина: **other**
- USER[1]: добрый курьера на полевая 160 в это в колпино на имя зинаиду телефон 8 926 123 45 67
- USER[2]: проверьте адрес в базе и вызывайте на завтра утром
- seen LOC `полевая 160 в` → `улица Озёрная 4`
- seen NAME `зинаиду` → `Викторию`
- seen PHONE `8 926 123 45 67` → `+79181843936`
- C: `address_suggest` {'query': 'Колпино Полевая 160', 'count': 3}
- C: `courier_book` {'address': {'locality': 'Колпино', 'street': 'Полевая', 'building': '160'}, 'contact': {'name': 'Зинаида', 'phone': '+79261234567'}, 'interval': {'from': '2026-09-04T09:00:00+03:00', 'to': '2026-09-…
- I: `address_suggest` written={'query': 'Колпино, улица Озёрная, 4', 'count': 3} → restored={'query': 'Колпино, полевая, 160 в', 'count': 3}
- I: `courier_book` written={'address': {'locality': 'Колпино', 'street': 'Озёрная', 'building': '4'}, 'contact': {'name': 'Виктория', 'phone': '+79181843936'}, 'interval': {'from': '2026-09-04T09:00:00+03:00', 'to': '2026-09-04T12:00:00+03:00'}} → restored={'address': {'locality': 'Колпино', 'street': 'Полевая', 'building': '160'}, 'contact': {'name': 'зинаида', 'phone': '+79261234567'}, 'interval': {'from': '2026-09-04T09:00:00+03:00', 'to': '2026-09-04T12:00:00+03:00'}}
- C′: `address_suggest` {'query': 'Колпино, Полевая 160', 'count': 3}
- C′: `courier_book` {'address': {'locality': 'Колпино', 'street': 'Полевая', 'building': '160'}, 'contact': {'name': 'Зинаида', 'phone': '+79261234567'}, 'interval': {'from': '2026-09-04T09:00:00+03:00', 'to': '2026-09-…
- REPLY I: Проверяю адрес! Нашёл подходящий вариант: **Санкт-Петербург, Колпино, полевая 160 в** (индекс 196499). Вызываю курьера на завтрашнее утро (09:00–12:00)! Готово! ✅ **Курьер вызван**, вот детали: - 📍 **Адрес:** Колпино, полевая 160 в - 👤 **Контакт:** зинаида, 8 926 123 45 67 - 🕘 **Интервал:** 4 сентя…

## compare-009|0 · compare · voice_itn · L1 ≠ · L3 ≠ · C′≈C нет · причина: **Б8-echo**
- USER[1]: курьера на луговая 10 это в самара на имя марину телефон 89163727117
- USER[2]: проверьте адрес в базе и вызывайте на завтра утром
- seen LOC `луговая 10` → `улица Вишнёвая 109`
- seen NAME `марину` → `Прасковье`
- seen PHONE `89163727117` → `+79861650826`
- C: `address_suggest` {'query': 'Самара, Луговая 10', 'count': 3}
- C: `courier_book` {'address': {'locality': 'Самара', 'street': 'Луговая', 'building': '10'}, 'contact': {'name': 'Марина', 'phone': '+79163727117'}, 'interval': {'from': '2026-09-04T09:00:00+04:00', 'to': '2026-09-04T…
- I: `address_suggest` written={'query': 'Самара, улица Вишнёвая, 109', 'count': 3} → restored={'query': 'Самара, луговая, 10', 'count': 3}
- C′: `address_suggest` {'query': 'Самара, Луговая, 10'}
- C′: `courier_book` {'address': {'locality': 'Самара', 'street': 'Луговая', 'building': '10'}, 'contact': {'name': 'Марина', 'phone': '+79163727117'}, 'interval': {'from': '2026-09-04T09:00:00+04:00', 'to': '2026-09-04T…
- FIELD `courier_book.address.building` [absent → absent:building] C=`10` I=``
- FIELD `courier_book.address.locality` [absent → absent:locality] C=`Самара` I=``
- FIELD `courier_book.address.street` [absent → absent:street] C=`Луговая` I=``
- FIELD `courier_book.contact.name` [absent → absent:name] C=`Марина` I=``
- FIELD `courier_book.contact.phone` [absent → absent:phone] C=`+79163727117` I=``
- REPLY I: Проверяю адрес в справочнике! К сожалению, адрес **Самара, луговая 10** не найден в справочнике — ни одно из предложений не совпадает с нужным адресом. Пожалуйста, проверьте: - **Улица** — точно ли «г Абакан, ул Луговая, д 10»? Возможно, другое название? - **Дом** — верно ли 109? - **Город** — это …

## compare-009|1 · compare · voice_itn · L1 ≠ · L3 ≠ · C′≈C да · причина: **Б8-echo**
- USER[1]: курьера на луговая 10 это в самара на имя марину телефон 89163727117
- USER[2]: проверьте адрес в базе и вызывайте на завтра утром
- seen LOC `луговая 10` → `улица Сиреневая 46`
- seen NAME `марину` → `Денису`
- seen PHONE `89163727117` → `+79950352821`
- C: `address_suggest` {'query': 'Самара, Луговая, 10', 'count': 3}
- C: `courier_book` {'address': {'locality': 'Самара', 'street': 'Луговая', 'building': '10'}, 'contact': {'name': 'Марина', 'phone': '+79163727117'}, 'interval': {'from': '2026-09-04T09:00:00+04:00', 'to': '2026-09-04T…
- I: `address_suggest` written={'query': 'Самара, улица Сиреневая, 46', 'count': 1} → restored={'query': 'Самара, луговая, 10', 'count': 1}
- C′: `address_suggest` {'query': 'Самара, Луговая, 10', 'count': 3}
- C′: `courier_book` {'address': {'locality': 'Самара', 'street': 'Луговая', 'building': '10'}, 'contact': {'name': 'Марина', 'phone': '+79163727117'}, 'interval': {'from': '2026-09-04T09:00:00+04:00', 'to': '2026-09-04T…
- FIELD `courier_book.address.building` [absent → absent:building] C=`10` I=``
- FIELD `courier_book.address.locality` [absent → absent:locality] C=`Самара` I=``
- FIELD `courier_book.address.street` [absent → absent:street] C=`Луговая` I=``
- FIELD `courier_book.contact.name` [absent → absent:name] C=`Марина` I=``
- FIELD `courier_book.contact.phone` [absent → absent:phone] C=`+79163727117` I=``
- REPLY I: Сначала проверю адрес в базе! К сожалению, адрес **Самара, луговая 10** не найден в базе — справочник вернул совершенно другой адрес (Самарская область, г Самара, ул Луговая, д 10, Самарская область, г Самара, ул Луговая, д 10), что явно не совпадает. Пожалуйста, уточни: - Точное название улицы (мо…

## compare-009|2 · compare · voice_itn · L1 ≠ · L3 ≠ · C′≈C да · причина: **Б8-echo**
- USER[1]: курьера на луговая 10 это в самара на имя марину телефон 89163727117
- USER[2]: проверьте адрес в базе и вызывайте на завтра утром
- seen LOC `луговая 10` → `улица Буковая 190`
- seen NAME `марину` → `Константину`
- seen PHONE `89163727117` → `+79497233094`
- C: `address_suggest` {'query': 'Самара, Луговая 10', 'count': 3}
- C: `courier_book` {'address': {'locality': 'Самара', 'street': 'Луговая', 'building': '10'}, 'contact': {'name': 'Марина', 'phone': '+79163727117'}, 'interval': {'from': '2026-09-04T09:00:00+04:00', 'to': '2026-09-04T…
- I: `address_suggest` written={'query': 'Самара, улица Буковая, 190', 'count': 3} → restored={'query': 'Самара, луговая, 10', 'count': 3}
- C′: `address_suggest` {'query': 'Самара, Луговая 10', 'count': 3}
- C′: `courier_book` {'address': {'locality': 'Самара', 'street': 'Луговая', 'building': '10'}, 'contact': {'name': 'Марина', 'phone': '+79163727117'}, 'interval': {'from': '2026-09-04T09:00:00+04:00', 'to': '2026-09-04T…
- FIELD `courier_book.address.building` [absent → absent:building] C=`10` I=``
- FIELD `courier_book.address.locality` [absent → absent:locality] C=`Самара` I=``
- FIELD `courier_book.address.street` [absent → absent:street] C=`Луговая` I=``
- FIELD `courier_book.contact.name` [absent → absent:name] C=`Марина` I=``
- FIELD `courier_book.contact.phone` [absent → absent:phone] C=`+79163727117` I=``
- REPLY I: Проверяю адрес в базе! К сожалению, адрес **«Самара, луговая 10»** не нашёлся в базе — ни одно из предложений не совпадает. Похожее название улицы есть только в Республике Хакасия, а не в Самаре. Пожалуйста, уточни: - Возможно, улица называется иначе? Например, **Буковинская**, **Самарская область,…

## compare-011|0 · compare · voice_raw · L1 = · L3 = · C′≈C нет · причина: **leak-only**
- USER[1]: курьера на химзаводская три в корпус пять это в глазов наа имяя петра телефоон восемь девятьсот пятьдесят два двести шеесят пейсят два семьдесят семь
- USER[2]: проверьте адреес в базе и вызывайтее наа завтра утром
- seen LOC `химзаводская три в корпус пять` → `улицу Вишнёвую 99, корп. 8`
- seen NAME `петра` → `Инны`
- **LEAK** PHONE `восемь девятьсот пятьдесят два двести шеесят пейсят два семьдесят семь` — модель видела настоящее значение
- C: `address_suggest` {'query': 'Глазов, Химзаводская, 3 корпус 5', 'count': 3}
- I: `address_suggest` written={'query': 'Глазов Вишнёвая 99 корпус 8', 'count': 3} → restored={'query': 'Глазов химзаводская 3в корпус 5', 'count': 3}
- C′: `address_suggest` {'query': 'Глазов, Химзаводская 3 корпус 5', 'count': 3}
- C′: `courier_book` {'address': {'locality': 'Глазов', 'street': 'Химзаводская', 'building': '3 к5'}, 'contact': {'name': 'Пётр', 'phone': '+79522526277'}, 'interval': {'from': '2026-09-04T09:00:00+04:00', 'to': '2026-0… · refusal=house_format
- C′: `courier_book` {'address': {'locality': 'Глазов', 'street': 'Химзаводская', 'building': '3к5'}, 'contact': {'name': 'Пётр', 'phone': '+79522526277'}, 'interval': {'from': '2026-09-04T09:00:00+04:00', 'to': '2026-09… · refusal=house_format
- C′: `courier_book` {'address': {'locality': 'Глазов', 'street': 'Химзаводская', 'building': '3'}, 'contact': {'name': 'Пётр', 'phone': '+79522526277'}, 'interval': {'from': '2026-09-04T09:00:00+04:00', 'to': '2026-09-0…
- REPLY I: Ищу адрес в базе! К сожалению, адрес **химзаводская три в корпус пять, Глазов** не найден в базе — ни одно из предложений не совпало. База вернула совсем другие улицы. Пожалуйста, уточните: - Правильно ли написана улица? (может быть, **химзаводская три в корпус пять**, **химзаводская три в корпус п…

## compare-011|1 · compare · voice_raw · L1 ≠ · L3 ≠ · C′≈C да · причина: **Б8-echo**
- USER[1]: курьера на химзаводская три в корпус пять это в глазов наа имяя петра телефоон восемь девятьсот пятьдесят два двести шеесят пейсят два семьдесят семь
- USER[2]: проверьте адреес в базе и вызывайтее наа завтра утром
- seen LOC `химзаводская три в корпус пять` → `улицу Кедровую 187, корп. 9`
- seen NAME `петра` → `София`
- **LEAK** PHONE `восемь девятьсот пятьдесят два двести шеесят пейсят два семьдесят семь` — модель видела настоящее значение
- C: `address_suggest` {'query': 'Глазов Химзаводская 3 корпус 5', 'count': 3}
- C: `courier_book` {'address': {'locality': 'Глазов', 'street': 'Химзаводская', 'building': '3к5'}, 'contact': {'name': 'Пётр', 'phone': '+79522605277'}, 'interval': {'from': '2026-09-04T09:00:00+04:00', 'to': '2026-09… · refusal=house_format
- C: `courier_book` {'address': {'locality': 'Глазов', 'street': 'Химзаводская', 'building': '3', 'porch': '5'}, 'contact': {'name': 'Пётр', 'phone': '+79522605277'}, 'interval': {'from': '2026-09-04T09:00:00+04:00', 't…
- I: `address_suggest` written={'query': 'Глазов, улица Кедровая, 187, корпус 9', 'count': 3} → restored={'query': 'Глазов, химзаводская, 3в, корпус 5', 'count': 3}
- C′: `address_suggest` {'query': 'Глазов, Химзаводская, 3 корпус 5', 'count': 3}
- C′: `courier_book` {'address': {'locality': 'Глазов', 'street': 'Химзаводская', 'building': '3к5'}, 'contact': {'name': 'Пётр', 'phone': '+79522605277'}, 'interval': {'from': '2026-09-04T09:00:00+04:00', 'to': '2026-09… · refusal=house_format
- C′: `courier_book` {'address': {'locality': 'Глазов', 'street': 'Химзаводская', 'building': '3', 'porch': '5'}, 'contact': {'name': 'Пётр', 'phone': '+79522605277'}, 'interval': {'from': '2026-09-04T09:00:00+04:00', 't…
- FIELD `courier_book.address.building` [absent → absent:building] C=`3к5` I=``
- FIELD `courier_book.address.locality` [absent → absent:locality] C=`Глазов` I=``
- FIELD `courier_book.address.street` [absent → absent:street] C=`Химзаводская` I=``
- FIELD `courier_book.contact.name` [absent → absent:name] C=`Пётр` I=``
- FIELD `courier_book.contact.phone` [absent → absent:phone] C=`+79522605277` I=``
- FIELD `courier_book.address.building` [absent → absent:building] C=`3` I=``
- FIELD `courier_book.address.locality` [absent → absent:locality] C=`Глазов` I=``
- FIELD `courier_book.address.porch` [absent → absent:porch] C=`5` I=``
- FIELD `courier_book.address.street` [absent → absent:street] C=`Химзаводская` I=``
- FIELD `courier_book.contact.name` [absent → absent:name] C=`Пётр` I=``
- FIELD `courier_book.contact.phone` [absent → absent:phone] C=`+79522605277` I=``
- REPLY I: Ищу адрес в базе — и сразу уточняю: **телефон всё ещё неполный** (8-952-262-77 — 9 цифр вместо 11). Без него не смогу оформить вызов. Пока проверяю адрес: База не нашла точного совпадения для **химзаводская три в корпус пять, Глазов** — адрес не подтверждён. Прежде чем продолжить, мне нужно от вас …

## compare-011|2 · compare · voice_raw · L1 ≠ · L3 ≠ · C′≈C нет · причина: **other**
- USER[1]: курьера на химзаводская три в корпус пять это в глазов наа имяя петра телефоон восемь девятьсот пятьдесят два двести шеесят пейсят два семьдесят семь
- USER[2]: проверьте адреес в базе и вызывайтее наа завтра утром
- seen LOC `химзаводская три в корпус пять` → `улицу Рябиновую 37, корп. 11`
- seen NAME `петра` → `Лады`
- **LEAK** PHONE `восемь девятьсот пятьдесят два двести шеесят пейсят два семьдесят семь` — модель видела настоящее значение
- C: `address_suggest` {'query': 'Глазов, Химзаводская 3 корпус 5', 'count': 3}
- I: `address_suggest` written={'query': 'Глазов, улица Рябиновая, 37 корпус 11', 'count': 3} → restored={'query': 'Глазов, химзаводская, 3в корпус 5', 'count': 3}
- I: `address_suggest` written={'query': 'Глазов Рябиновая 37', 'count': 5} → restored={'query': 'Глазов химзаводская 3в', 'count': 5}
- I: `courier_book` written={'address': {'locality': 'Глазов', 'street': 'Рябиновая', 'building': '37к11'}, 'contact': {'name': 'Лада', 'phone': '+79522605277'}, 'interval': {'from': '2026-09-04T09:00:00+04:00', 'to': '2026-09-04T12:00:00+04:00'}} → restored={'address': {'locality': 'Глазов', 'street': 'химзаводская', 'building': '3в'}, 'contact': {'name': 'петра', 'phone': '+79522605277'}, 'interval': {'from': '2026-09-04T09:00:00+04:00', 'to': '2026-09-04T12:00:00+04:00'}}
- C′: `address_suggest` {'query': 'Глазов, Химзаводская, 3 корпус 5', 'count': 3}
- C′: `courier_book` {'address': {'locality': 'Глазов', 'street': 'Химзаводская', 'building': '3к5'}, 'contact': {'name': 'Пётр', 'phone': '+79522605277'}, 'interval': {'from': '2026-09-04T09:00:00+04:00', 'to': '2026-09… · refusal=house_format
- C′: `courier_book` {'address': {'locality': 'Глазов', 'street': 'Химзаводская', 'building': '3'}, 'contact': {'name': 'Пётр', 'phone': '+79522605277'}, 'interval': {'from': '2026-09-04T09:00:00+04:00', 'to': '2026-09-0…
- FIELD `address_suggest.query` [extra → extra:query] C=`` I=`Глазов химзаводская 3в`
- FIELD `courier_book.address.building` [extra → extra:building] C=`` I=`3в`
- FIELD `courier_book.address.locality` [extra → extra:locality] C=`` I=`Глазов`
- FIELD `courier_book.address.street` [extra → extra:street] C=`` I=`химзаводская`
- FIELD `courier_book.contact.name` [extra → extra:name] C=`` I=`петра`
- FIELD `courier_book.contact.phone` [extra → extra:phone] C=`` I=`+79522605277`
- REPLY I: Ищу адрес в базе, и сразу вызываю курьера на завтрашнее утро (09:00–12:00)! База точного адреса не нашла, но данных достаточно — вызываю курьера напрямую! Готово! Курьер вызван ✅ **Детали заявки:** - 🆔 Номер заявки: **clm-1** - 📍 Адрес: Глазов, химзаводская три в корпус пятьк11 - 👤 Контакт: петра, …

## compare-014|0 · compare · sloppy · L1 = · L3 ≠ · C′≈C да · причина: **typo-normalised**
- USER[1]: курьера на вишёнвая 28 это в крсанодар на имя марину телефон +79601068867
- USER[2]: проверьте адрес в базе и вызывайте на завтра утром
- **LEAK** LOC `вишёнвая 28` — модель видела настоящее значение
- seen NAME `марину` → `Сергею`
- seen PHONE `+79601068867` → `+79914003496`
- C: `address_suggest` {'query': 'Краснодар, Вишнёвая 28', 'count': 3}
- C: `courier_book` {'address': {'locality': 'Краснодар', 'street': 'Вишнёвая', 'building': '28'}, 'contact': {'name': 'Марина', 'phone': '+79601068867'}, 'interval': {'from': '2026-09-04T09:00:00+03:00', 'to': '2026-09…
- I: `address_suggest` written={'query': 'Краснодар, Вишнёвая 28', 'count': 3} → restored={'query': 'Краснодар, Вишнёвая 28', 'count': 3}
- I: `courier_book` written={'address': {'locality': 'Краснодар', 'street': 'Вишнёвая', 'building': '28'}, 'contact': {'name': 'Сергей', 'phone': '+79914003496'}, 'interval': {'from': '2026-09-04T09:00:00+03:00', 'to': '2026-09-04T13:00:00+03:00'}} → restored={'address': {'locality': 'Краснодар', 'street': 'Вишнёвая', 'building': '28'}, 'contact': {'name': 'марин', 'phone': '+79601068867'}, 'interval': {'from': '2026-09-04T09:00:00+03:00', 'to': '2026-09-04T13:00:00+03:00'}}
- C′: `address_suggest` {'query': 'Краснодар, Вишнёвая, 28', 'count': 3}
- C′: `courier_book` {'address': {'locality': 'Краснодар', 'street': 'Вишнёвая', 'building': '28'}, 'contact': {'name': 'Марина', 'phone': '+79601068867'}, 'interval': {'from': '2026-09-04T09:00:00+03:00', 'to': '2026-09…
- FIELD `courier_book.contact.name` [other/inflected → name_case] C=`Марина` I=`марин`
- REPLY I: Адрес в базе есть — **Краснодар, ул. г Абакан, ул Вишнёвая, д 28, 28** ✅ Вызываю курьера на завтра утром (09:00–13:00)! Готово! ✅ Курьер вызван. **Детали заявки:** - 🆔 Номер заявки: `clm-1` - 📍 Адрес: Краснодар, ул. г Абакан, ул Вишнёвая, д 28, 28 - 👤 Контакт: марин, +79601068867 - 🗓 Дата и время: …

## compare-014|1 · compare · sloppy · L1 = · L3 ≠ · C′≈C да · причина: **typo-normalised**
- USER[1]: курьера на вишёнвая 28 это в крсанодар на имя марину телефон +79601068867
- USER[2]: проверьте адрес в базе и вызывайте на завтра утром
- **LEAK** LOC `вишёнвая 28` — модель видела настоящее значение
- seen NAME `марину` → `Прохору`
- seen PHONE `+79601068867` → `+79587943966`
- C: `address_suggest` {'query': 'Краснодар, Вишнёвая, 28', 'count': 3}
- C: `courier_book` {'address': {'locality': 'Краснодар', 'street': 'Вишнёвая', 'building': '28'}, 'contact': {'name': 'Марина', 'phone': '+79601068867'}, 'interval': {'from': '2026-09-04T09:00:00+03:00', 'to': '2026-09…
- I: `address_suggest` written={'query': 'Краснодар, Вишнёвая 28', 'count': 3} → restored={'query': 'Краснодар, Вишнёвая 28', 'count': 3}
- I: `courier_book` written={'address': {'locality': 'Краснодар', 'street': 'Вишнёвая', 'building': '28'}, 'contact': {'name': 'Прохор', 'phone': '+79587943966'}, 'interval': {'from': '2026-09-04T09:00:00+03:00', 'to': '2026-09-04T12:00:00+03:00'}} → restored={'address': {'locality': 'Краснодар', 'street': 'Вишнёвая', 'building': '28'}, 'contact': {'name': 'марин', 'phone': '+79601068867'}, 'interval': {'from': '2026-09-04T09:00:00+03:00', 'to': '2026-09-04T12:00:00+03:00'}}
- C′: `address_suggest` {'query': 'Краснодар Вишнёвая 28', 'count': 3}
- C′: `courier_book` {'address': {'locality': 'Краснодар', 'street': 'Вишнёвая', 'building': '28'}, 'contact': {'name': 'Марина', 'phone': '+79601068867'}, 'interval': {'from': '2026-09-04T09:00:00+03:00', 'to': '2026-09…
- FIELD `courier_book.contact.name` [other/inflected → name_case] C=`Марина` I=`марин`
- REPLY I: Адрес в базе подтверждён — вызываю курьера! 🚚 Курьер вызван! ✅ **Детали вызова:** - 📍 Адрес: Краснодар, ул. Вишнёвая, 28 - 👤 Контакт: марин, +79601068867 - 🗓 Дата: 4 сентября 2026 г., с 09:00 до 12:00 - 🆔 Номер заявки: **clm-1** (статус: обрабатывается) Если понадобится что-то изменить — обращайтес…

## compare-014|2 · compare · sloppy · L1 = · L3 ≠ · C′≈C да · причина: **typo-normalised**
- USER[1]: курьера на вишёнвая 28 это в крсанодар на имя марину телефон +79601068867
- USER[2]: проверьте адрес в базе и вызывайте на завтра утром
- **LEAK** LOC `вишёнвая 28` — модель видела настоящее значение
- seen NAME `марину` → `Елизавете`
- seen PHONE `+79601068867` → `+79360910961`
- C: `address_suggest` {'query': 'Краснодар Вишнёвая 28', 'count': 3}
- C: `courier_book` {'address': {'locality': 'Краснодар', 'street': 'Вишнёвая', 'building': '28'}, 'contact': {'name': 'Марина', 'phone': '+79601068867'}, 'interval': {'from': '2026-09-04T09:00:00+03:00', 'to': '2026-09…
- I: `address_suggest` written={'query': 'Краснодар, Вишнёвая, 28', 'count': 3} → restored={'query': 'Краснодар, Вишнёвая, 28', 'count': 3}
- I: `courier_book` written={'address': {'locality': 'Краснодар', 'street': 'Вишнёвая', 'building': '28'}, 'contact': {'name': 'Елизавета', 'phone': '+79360910961'}, 'interval': {'from': '2026-09-04T09:00:00+03:00', 'to': '2026-09-04T12:00:00+03:00'}} → restored={'address': {'locality': 'Краснодар', 'street': 'Краснодарский край, г Краснодар, Вишнёвая', 'building': '28'}, 'contact': {'name': 'марин', 'phone': '+79601068867'}, 'interval': {'from': '2026-09-04T09:00:00+03:00', 'to': '2026-09-04T12:00:00+03:00'}}
- C′: `address_suggest` {'query': 'Краснодар, Вишнёвая 28', 'count': 3}
- C′: `courier_book` {'address': {'locality': 'Краснодар', 'street': 'Вишнёвая', 'building': '28'}, 'contact': {'name': 'Марина', 'phone': '+79601068867'}, 'interval': {'from': '2026-09-04T09:00:00+03:00', 'to': '2026-09…
- FIELD `courier_book.address.street` [composed → loc_street] C=`Вишнёвая` I=`Краснодарский край, г Краснодар, Вишнёвая`
- FIELD `courier_book.contact.name` [other/inflected → name_case] C=`Марина` I=`марин`
- REPLY I: Адрес в базе есть — вызываю курьера на **завтра, 4 сентября, с 09:00 до 12:00**! Готово! Курьер вызван ✅ **Детали вызова:** - 📍 Краснодар, ул. Краснодарский край, г Краснодар, ул Вишнёвая, д 28, 28 - 👤 марин, +79601068867 - 🕘 4 сентября 2026, с 09:00 до 12:00 - 🔖 Номер заявки: **clm-1** Если понадо…

## compare-017|0 · compare · chat · L1 ≠ · L3 ≠ · C′≈C да · причина: **Б8-echo**
- USER[1]: привет курьера на некрасова 33 это в колпино на имя олега телефон +79268761489
- USER[2]: сверьте по справочнику и оформляйте на завтра с десяти до четырёх
- seen LOC `некрасова 33` → `улицы Барбарисовой 184`
- seen NAME `олега` → `Платона`
- seen PHONE `+79268761489` → `+79894355451`
- C: `address_suggest` {'query': 'Колпино, Некрасова 33', 'count': 3}
- C: `courier_book` {'address': {'locality': 'Колпино', 'street': 'Некрасова', 'building': '33'}, 'contact': {'name': 'Олег', 'phone': '+79268761489'}, 'interval': {'from': '2026-09-04T10:00:00+03:00', 'to': '2026-09-04…
- I: `address_suggest` written={'query': 'Колпино, Барбарисовая, 184'} → restored={'query': 'Колпино, некрасова, 33'}
- C′: `address_suggest` {'query': 'Колпино, улица Некрасова, 33', 'count': 3}
- C′: `courier_book` {'address': {'locality': 'Колпино', 'street': 'Некрасова', 'building': '33'}, 'contact': {'name': 'Олег', 'phone': '+79268761489'}, 'interval': {'from': '2026-09-04T10:00:00+03:00', 'to': '2026-09-04…
- FIELD `courier_book.address.building` [absent → absent:building] C=`33` I=``
- FIELD `courier_book.address.locality` [absent → absent:locality] C=`Колпино` I=``
- FIELD `courier_book.address.street` [absent → absent:street] C=`Некрасова` I=``
- FIELD `courier_book.contact.name` [absent → absent:name] C=`Олег` I=``
- FIELD `courier_book.contact.phone` [absent → absent:phone] C=`+79268761489` I=``
- REPLY I: Сверяю адрес по справочнику! К сожалению, адрес **некрасова 33, Колпино** не нашёлся в справочнике — ни один из вариантов ему не соответствует. Пожалуйста, проверьте: - Правильно ли указана **улица** (может, другое название?) - Правильно ли указан **номер дома** (184 — это не опечатка?) Уточните де…

## compare-017|1 · compare · chat · L1 ≠ · L3 ≠ · C′≈C да · причина: **Б8-echo**
- USER[1]: привет курьера на некрасова 33 это в колпино на имя олега телефон +79268761489
- USER[2]: сверьте по справочнику и оформляйте на завтра с десяти до четырёх
- seen LOC `некрасова 33` → `улицы Полевой 186`
- seen NAME `олега` → `Александра`
- seen PHONE `+79268761489` → `+79157040895`
- C: `address_suggest` {'query': 'Колпино, Некрасова 33', 'count': 3}
- C: `courier_book` {'address': {'locality': 'Колпино', 'street': 'Некрасова', 'building': '33'}, 'contact': {'name': 'Олег', 'phone': '+79268761489'}, 'interval': {'from': '2026-09-04T10:00:00+03:00', 'to': '2026-09-04…
- I: `address_suggest` written={'query': 'Колпино, улица Полевая, 186', 'count': 3} → restored={'query': 'Колпино, некрасова, 33', 'count': 3}
- C′: `address_suggest` {'query': 'Колпино, Некрасова 33', 'count': 3}
- C′: `courier_book` {'address': {'locality': 'Колпино', 'street': 'Некрасова', 'building': '33'}, 'contact': {'name': 'Олег', 'phone': '+79268761489'}, 'interval': {'from': '2026-09-04T10:00:00+03:00', 'to': '2026-09-04…
- FIELD `courier_book.address.building` [absent → absent:building] C=`33` I=``
- FIELD `courier_book.address.locality` [absent → absent:locality] C=`Колпино` I=``
- FIELD `courier_book.address.street` [absent → absent:street] C=`Некрасова` I=``
- FIELD `courier_book.contact.name` [absent → absent:name] C=`Олег` I=``
- FIELD `courier_book.contact.phone` [absent → absent:phone] C=`+79268761489` I=``
- REPLY I: Сначала сверю адрес по справочнику! К сожалению, справочник не нашёл точного совпадения для **Колпино, некрасова 33** — все три варианта совсем другие (другие улицы и города). Пожалуйста, уточните адрес: возможно, улица называется иначе или номер дома другой? Как только подтвердите — сразу оформлю …

## compare-017|2 · compare · chat · L1 ≠ · L3 ≠ · C′≈C да · причина: **Б8-echo**
- USER[1]: привет курьера на некрасова 33 это в колпино на имя олега телефон +79268761489
- USER[2]: сверьте по справочнику и оформляйте на завтра с десяти до четырёх
- seen LOC `некрасова 33` → `улицы Жасминовой 31`
- seen NAME `олега` → `Ильи`
- seen PHONE `+79268761489` → `+79701167412`
- C: `address_suggest` {'query': 'Колпино, улица Некрасова 33', 'count': 3}
- C: `courier_book` {'address': {'locality': 'Колпино', 'street': 'Некрасова', 'building': '33'}, 'contact': {'name': 'Олег', 'phone': '+79268761489'}, 'interval': {'from': '2026-09-04T10:00:00+03:00', 'to': '2026-09-04…
- I: `address_suggest` written={'query': 'Колпино, улица Жасминовая 31', 'count': 3} → restored={'query': 'Колпино, некрасова 33', 'count': 3}
- C′: `address_suggest` {'query': 'Колпино, улица Некрасова, 33', 'count': 3}
- C′: `courier_book` {'address': {'locality': 'Колпино', 'street': 'Некрасова', 'building': '33'}, 'contact': {'name': 'Олег', 'phone': '+79268761489'}, 'interval': {'from': '2026-09-04T10:00:00+03:00', 'to': '2026-09-04…
- FIELD `courier_book.address.building` [absent → absent:building] C=`33` I=``
- FIELD `courier_book.address.locality` [absent → absent:locality] C=`Колпино` I=``
- FIELD `courier_book.address.street` [absent → absent:street] C=`Некрасова` I=``
- FIELD `courier_book.contact.name` [absent → absent:name] C=`Олег` I=``
- FIELD `courier_book.contact.phone` [absent → absent:phone] C=`+79268761489` I=``
- REPLY I: Сверяю адрес по справочнику! По справочнику адрес **некрасова 33, Колпино** не нашёлся — результаты вернули совсем другие улицы и города, ни один вариант не подходит. Уточните, пожалуйста: - Правильно ли написана улица? (возможно, другое название) - Это точно **Колпино** (Санкт-Петербург)? Как толь…

## compare-021|0 · compare · sloppy · L1 = · L3 = · C′≈C да · причина: **leak-only**
- USER[1]: курьера на нидняя 59 это в соравала на имя кирилла тлефон 8-909-528-76-24
- USER[2]: провертте адрес в базе и вызывайте на завтра утром
- **LEAK** LOC `нидняя 59` — модель видела настоящее значение
- seen NAME `кирилла` → `Олега`
- seen PHONE `8-909-528-76-24` → `+79839905656`
- C: `address_suggest` {'query': 'Сортавала, Нижняя, 59'}
- C: `courier_book` {'address': {'locality': 'Сортавала', 'street': 'Нижняя', 'building': '59'}, 'contact': {'name': 'Кирилл', 'phone': '+79095287624'}, 'interval': {'from': '2026-09-04T09:00:00+03:00', 'to': '2026-09-0…
- I: `address_suggest` written={'query': 'Сортавала Нижняя 59', 'count': 3} → restored={'query': 'Сортавала Нижняя 59', 'count': 3}
- I: `courier_book` written={'address': {'locality': 'Сортавала', 'street': 'Нижняя', 'building': '59'}, 'contact': {'name': 'Олег', 'phone': '+79839905656'}, 'interval': {'from': '2026-09-04T09:00:00+03:00', 'to': '2026-09-04T12:00:00+03:00'}} → restored={'address': {'locality': 'Сортавала', 'street': 'Нижняя', 'building': '59'}, 'contact': {'name': 'кирилл', 'phone': '+79095287624'}, 'interval': {'from': '2026-09-04T09:00:00+03:00', 'to': '2026-09-04T12:00:00+03:00'}}
- C′: `address_suggest` {'query': 'Сортавала Нижняя 59', 'count': 3}
- C′: `courier_book` {'address': {'locality': 'Сортавала', 'street': 'Нижняя', 'building': '59'}, 'contact': {'name': 'Кирилл', 'phone': '+79095287624'}, 'interval': {'from': '2026-09-04T09:00:00+03:00', 'to': '2026-09-0…
- REPLY I: Вызываю курьера на **4 сентября, утро (09:00–12:00)**! Готово! Курьер вызван ✅ **Детали вызова:** - 📍 Адрес: Сортавала, ул. Нижняя, 59 - 👤 Контакт: кирилл, 8-909-528-76-24 - 📅 Дата и время: 4 сентября, с 09:00 до 12:00 - 🆔 Номер заявки: **clm-1** Если потребуется что-то изменить — обращайтесь!

## compare-021|1 · compare · sloppy · L1 = · L3 = · C′≈C да · причина: **leak-only**
- USER[1]: курьера на нидняя 59 это в соравала на имя кирилла тлефон 8-909-528-76-24
- USER[2]: провертте адрес в базе и вызывайте на завтра утром
- **LEAK** LOC `нидняя 59` — модель видела настоящее значение
- seen NAME `кирилла` → `Германа`
- seen PHONE `8-909-528-76-24` → `+79981151339`
- C: `address_suggest` {'query': 'Сортавала, улица Нижняя, 59', 'count': 3}
- C: `courier_book` {'address': {'locality': 'Сортавала', 'street': 'Нижняя', 'building': '59'}, 'contact': {'name': 'Кирилл', 'phone': '+79095287624'}, 'interval': {'from': '2026-09-04T09:00:00+03:00', 'to': '2026-09-0…
- I: `address_suggest` written={'query': 'Сортавала Нижняя 59'} → restored={'query': 'Сортавала Нижняя 59'}
- I: `courier_book` written={'address': {'locality': 'Сортавала', 'street': 'Нижняя', 'building': '59'}, 'contact': {'name': 'Герман', 'phone': '+79981151339'}, 'interval': {'from': '2026-09-04T09:00:00+03:00', 'to': '2026-09-04T12:00:00+03:00'}} → restored={'address': {'locality': 'Сортавала', 'street': 'Нижняя', 'building': '59'}, 'contact': {'name': 'кирилл', 'phone': '+79095287624'}, 'interval': {'from': '2026-09-04T09:00:00+03:00', 'to': '2026-09-04T12:00:00+03:00'}}
- C′: `address_suggest` {'query': 'Сортавала Нижняя 59', 'count': 3}
- C′: `courier_book` {'address': {'locality': 'Сортавала', 'street': 'Нижняя', 'building': '59'}, 'contact': {'name': 'Кирилл', 'phone': '+79095287624'}, 'interval': {'from': '2026-09-04T09:00:00+03:00', 'to': '2026-09-0…
- REPLY I: Адрес в базе подтверждён ✅ Вызываю курьера на завтра утром (09:00–12:00)! Готово! 🎉 Курьер вызван. **Детали вызова:** - 📍 Адрес: Сортавала, ул. Нижняя, 59 - 👤 Контакт: кирилл, 8-909-528-76-24 - 🗓 Дата: 4 сентября 2026 г. - ⏰ Интервал: 09:00 – 12:00 (МСК) - 🔖 Номер заявки: **clm-1** Если что-то нужн…

## compare-021|2 · compare · sloppy · L1 = · L3 = · C′≈C да · причина: **leak-only**
- USER[1]: курьера на нидняя 59 это в соравала на имя кирилла тлефон 8-909-528-76-24
- USER[2]: провертте адрес в базе и вызывайте на завтра утром
- **LEAK** LOC `нидняя 59` — модель видела настоящее значение
- seen NAME `кирилла` → `Богдана`
- seen PHONE `8-909-528-76-24` → `+79896090478`
- C: `address_suggest` {'query': 'Сортавала, улица Нижняя, 59', 'count': 3}
- C: `courier_book` {'address': {'locality': 'Сортавала', 'street': 'Нижняя', 'building': '59'}, 'contact': {'name': 'Кирилл', 'phone': '+79095287624'}, 'interval': {'from': '2026-09-04T09:00:00+03:00', 'to': '2026-09-0…
- I: `address_suggest` written={'query': 'Сортавала Нижняя 59', 'count': 3} → restored={'query': 'Сортавала Нижняя 59', 'count': 3}
- I: `courier_book` written={'address': {'locality': 'Сортавала', 'street': 'Нижняя', 'building': '59'}, 'contact': {'name': 'Богдан', 'phone': '+79896090478'}, 'interval': {'from': '2026-09-04T09:00:00+03:00', 'to': '2026-09-04T12:00:00+03:00'}} → restored={'address': {'locality': 'Сортавала', 'street': 'Нижняя', 'building': '59'}, 'contact': {'name': 'кирилл', 'phone': '+79095287624'}, 'interval': {'from': '2026-09-04T09:00:00+03:00', 'to': '2026-09-04T12:00:00+03:00'}}
- C′: `address_suggest` {'query': 'Сортавала, Нижняя 59'}
- C′: `courier_book` {'address': {'locality': 'Сортавала', 'street': 'Нижняя', 'building': '59'}, 'contact': {'name': 'Кирилл', 'phone': '+79095287624'}, 'interval': {'from': '2026-09-04T09:00:00+03:00', 'to': '2026-09-0…
- REPLY I: Вызываю курьера на завтра утром (09:00–12:00)! Готово! ✅ Курьер вызван. **Детали вызова:** - 📍 Адрес: Сортавала, ул. Нижняя, 59 - 👤 Контакт: кирилл, 8-909-528-76-24 - 🕘 Интервал: 4 сентября 2026, с 09:00 до 12:00 - 🔖 Номер заявки: **clm-1** Если нужно что-то изменить или оформить доставку — обращай…

## compare-028|0 · compare · voice_itn · L1 ≠ · L3 ≠ · C′≈C нет · причина: **Б8-echo**
- USER[1]: здравствуйте курьера на садовая 155 это в абакан на имя евгения телефон 89854133360
- USER[2]: проверьте адрес в базе и вызывайте на завтра утром
- seen LOC `садовая 155` → `улица Барбарисовая 45`
- seen NAME `евгения` → `Лады`
- seen PHONE `89854133360` → `+79088771652`
- C: `address_suggest` {'query': 'Абакан, Садовая, 155', 'count': 3}
- C: `courier_book` {'address': {'locality': 'Абакан', 'street': 'Садовая', 'building': '155'}, 'contact': {'name': 'Евгений', 'phone': '+79854133360'}, 'interval': {'from': '2026-09-04T09:00:00+07:00', 'to': '2026-09-0…
- I: `address_suggest` written={'query': 'Абакан, улица Барбарисовая 45', 'count': 3} → restored={'query': 'Абакан, садовая 155', 'count': 3}
- C′: `address_suggest` {'query': 'Абакан, Садовая, 155', 'count': 3}
- C′: `courier_book` {'address': {'locality': 'Абакан', 'street': 'Садовая', 'building': '155'}, 'contact': {'name': 'Евгения', 'phone': '+79854133360'}, 'interval': {'from': '2026-09-04T09:00:00+07:00', 'to': '2026-09-0…
- FIELD `courier_book.address.building` [absent → absent:building] C=`155` I=``
- FIELD `courier_book.address.locality` [absent → absent:locality] C=`Абакан` I=``
- FIELD `courier_book.address.street` [absent → absent:street] C=`Садовая` I=``
- FIELD `courier_book.contact.name` [absent → absent:name] C=`Евгений` I=``
- FIELD `courier_book.contact.phone` [absent → absent:phone] C=`+79854133360` I=``
- REPLY I: Сейчас проверю адрес в справочнике! К сожалению, адрес **садовая 155, Абакан** не нашёлся в справочнике — точного совпадения нет. Возможно, улица называется иначе или номер дома другой. Пожалуйста, уточните: - Полное название улицы (может быть, **переулок**, **проезд** или другое написание?) - Номе…

## compare-028|1 · compare · voice_itn · L1 ≠ · L3 ≠ · C′≈C да · причина: **Б8-echo**
- USER[1]: здравствуйте курьера на садовая 155 это в абакан на имя евгения телефон 89854133360
- USER[2]: проверьте адрес в базе и вызывайте на завтра утром
- seen LOC `садовая 155` → `улица Речная 117`
- seen NAME `евгения` → `Ольги`
- seen PHONE `89854133360` → `+79712126359`
- C: `address_suggest` {'query': 'Абакан, Садовая, 155'}
- C: `courier_book` {'address': {'locality': 'Абакан', 'street': 'Садовая', 'building': '155'}, 'contact': {'name': 'Евгения', 'phone': '+79854133360'}, 'interval': {'from': '2026-09-04T09:00:00+07:00', 'to': '2026-09-0…
- I: `address_suggest` written={'query': 'Абакан, улица Речная 117', 'count': 3} → restored={'query': 'Абакан, садовая 155', 'count': 3}
- C′: `address_suggest` {'query': 'Абакан, Садовая 155', 'count': 3}
- C′: `courier_book` {'address': {'locality': 'Абакан', 'street': 'Садовая', 'building': '155'}, 'contact': {'name': 'Евгения', 'phone': '+79854133360'}, 'interval': {'from': '2026-09-04T09:00:00+07:00', 'to': '2026-09-0…
- FIELD `courier_book.address.building` [absent → absent:building] C=`155` I=``
- FIELD `courier_book.address.locality` [absent → absent:locality] C=`Абакан` I=``
- FIELD `courier_book.address.street` [absent → absent:street] C=`Садовая` I=``
- FIELD `courier_book.contact.name` [absent → absent:name] C=`Евгения` I=``
- FIELD `courier_book.contact.phone` [absent → absent:phone] C=`+79854133360` I=``
- REPLY I: Проверяю адрес в справочнике! К сожалению, точного совпадения по адресу **садовая 155, Абакан** в справочнике не нашлось — результаты поиска показали другие улицы и города. Пожалуйста, уточните: - Правильно ли написана улица? (возможно, другое название) - Есть ли номер квартиры или подъезда? Если в…

## compare-028|2 · compare · voice_itn · L1 ≠ · L3 ≠ · C′≈C нет · причина: **Б8-echo**
- USER[1]: здравствуйте курьера на садовая 155 это в абакан на имя евгения телефон 89854133360
- USER[2]: проверьте адрес в базе и вызывайте на завтра утром
- seen LOC `садовая 155` → `улица Озёрная 60`
- seen NAME `евгения` → `Иванны`
- seen PHONE `89854133360` → `+79329904115`
- C: `address_suggest` {'query': 'Абакан, Садовая, 155', 'count': 3}
- C: `courier_book` {'address': {'locality': 'Абакан', 'street': 'Садовая', 'building': '155'}, 'contact': {'name': 'Евгений', 'phone': '+79854133360'}, 'interval': {'from': '2026-09-04T09:00:00+07:00', 'to': '2026-09-0…
- I: `address_suggest` written={'query': 'Абакан, улица Озёрная 60', 'count': 3} → restored={'query': 'Абакан, садовая 155', 'count': 3}
- C′: `address_suggest` {'query': 'Абакан, Садовая 155', 'count': 3}
- C′: `courier_book` {'address': {'locality': 'Абакан', 'street': 'Садовая', 'building': '155'}, 'contact': {'name': 'Евгений', 'phone': '+79854133360'}, 'interval': {'from': '2026-09-04T09:00:00+07:00', 'to': '2026-09-0…
- FIELD `courier_book.address.building` [absent → absent:building] C=`155` I=``
- FIELD `courier_book.address.locality` [absent → absent:locality] C=`Абакан` I=``
- FIELD `courier_book.address.street` [absent → absent:street] C=`Садовая` I=``
- FIELD `courier_book.contact.name` [absent → absent:name] C=`Евгений` I=``
- FIELD `courier_book.contact.phone` [absent → absent:phone] C=`+79854133360` I=``
- REPLY I: Проверяю адрес! К сожалению, адрес **садовая 155 в Абакане** не найден в нашей базе — справочник не вернул подходящего совпадения. Пожалуйста, уточните: - Возможно, улица называется иначе? (например, другое написание) - Или укажите **почтовый индекс** — тогда оформлю вызов вручную.

## compare-029|0 · compare · voice_raw · L1 ≠ · L3 ≠ · C′≈C да · причина: **Б8-echo**
- USER[1]: здравствуйте курьера на центральная сто это в краснодар на имя владислава телефонто восемь девятьсот восемесят восемь пятьсот восемьдесят девять тринадцать ноль один
- USER[2]: сверьте по справочнику и оформляйте на завтра с десяти до четырёх
- seen LOC `центральная сто` → `улица Пихтовая 18`
- seen NAME `владислава` → `Беллы`
- seen PHONE `восемь девятьсот восемесят восемь пятьсот восемьдесят девять тринадцать ноль один` → `+79665384960`
- C: `address_suggest` {'query': 'Краснодар, улица Центральная, 100', 'count': 3}
- C: `courier_book` {'address': {'locality': 'Краснодар', 'street': 'Центральная', 'building': '100'}, 'contact': {'name': 'Владислав', 'phone': '+79885891301'}, 'interval': {'from': '2026-09-04T10:00:00+03:00', 'to': '…
- I: `address_suggest` written={'query': 'Краснодар, улица Пихтовая, 18', 'count': 3} → restored={'query': 'Краснодар, центральная, 100', 'count': 3}
- C′: `address_suggest` {'query': 'Краснодар, Центральная, 100', 'count': 3}
- C′: `courier_book` {'address': {'locality': 'Краснодар', 'street': 'Центральная', 'building': '100'}, 'contact': {'name': 'Владислав', 'phone': '+79885891301'}, 'interval': {'from': '2026-09-04T10:00:00+03:00', 'to': '…
- FIELD `courier_book.address.building` [absent → absent:building] C=`100` I=``
- FIELD `courier_book.address.locality` [absent → absent:locality] C=`Краснодар` I=``
- FIELD `courier_book.address.street` [absent → absent:street] C=`Центральная` I=``
- FIELD `courier_book.contact.name` [absent → absent:name] C=`Владислав` I=``
- FIELD `courier_book.contact.phone` [absent → absent:phone] C=`+79885891301` I=``
- REPLY I: Сверяю адрес по справочнику! К сожалению, адрес **центральная сто, Краснодар** не найден в справочнике — подходящих совпадений нет. Пожалуйста, уточните адрес: - Возможно, улица называется иначе? (или это другой населённый пункт?) - Есть ли номер подъезда или квартиры? Как только подтвердим адрес —…

## compare-029|1 · compare · voice_raw · L1 ≠ · L3 ≠ · C′≈C да · причина: **Б8-echo**
- USER[1]: здравствуйте курьера на центральная сто это в краснодар на имя владислава телефонто восемь девятьсот восемесят восемь пятьсот восемьдесят девять тринадцать ноль один
- USER[2]: сверьте по справочнику и оформляйте на завтра с десяти до четырёх
- seen LOC `центральная сто` → `улица Ивовая 99`
- seen NAME `владислава` → `Галины`
- seen PHONE `восемь девятьсот восемесят восемь пятьсот восемьдесят девять тринадцать ноль один` → `+79755850470`
- C: `address_suggest` {'query': 'Краснодар, улица Центральная, 100', 'count': 3}
- C: `courier_book` {'address': {'locality': 'Краснодар', 'street': 'Центральная', 'building': '100'}, 'contact': {'name': 'Владислав', 'phone': '+79885891301'}, 'interval': {'from': '2026-09-04T10:00:00+03:00', 'to': '…
- I: `address_suggest` written={'query': 'Краснодар, улица Ивовая, 99', 'count': 3} → restored={'query': 'Краснодар, центральная, 100', 'count': 3}
- C′: `address_suggest` {'query': 'Краснодар, Центральная, 100', 'count': 3}
- C′: `courier_book` {'address': {'locality': 'Краснодар', 'street': 'Центральная', 'building': '100'}, 'contact': {'name': 'Владислав', 'phone': '+79885891301'}, 'interval': {'from': '2026-09-04T10:00:00+03:00', 'to': '…
- FIELD `courier_book.address.building` [absent → absent:building] C=`100` I=``
- FIELD `courier_book.address.locality` [absent → absent:locality] C=`Краснодар` I=``
- FIELD `courier_book.address.street` [absent → absent:street] C=`Центральная` I=``
- FIELD `courier_book.contact.name` [absent → absent:name] C=`Владислав` I=``
- FIELD `courier_book.contact.phone` [absent → absent:phone] C=`+79885891301` I=``
- REPLY I: Сначала проверю адрес по справочнику! К сожалению, адрес **центральная сто, Краснодар** по справочнику не найден — ни улица, ни дом не подтвердились. Пожалуйста, проверьте: - **Название улицы** — возможно, она называется иначе (например, центральная сто, центральная сто и т.п.)? - **Номер дома** — …

## compare-029|2 · compare · voice_raw · L1 ≠ · L3 ≠ · C′≈C да · причина: **Б8-echo**
- USER[1]: здравствуйте курьера на центральная сто это в краснодар на имя владислава телефонто восемь девятьсот восемесят восемь пятьсот восемьдесят девять тринадцать ноль один
- USER[2]: сверьте по справочнику и оформляйте на завтра с десяти до четырёх
- seen LOC `центральная сто` → `улица Кленовая 65`
- seen NAME `владислава` → `Людмилы`
- seen PHONE `восемь девятьсот восемесят восемь пятьсот восемьдесят девять тринадцать ноль один` → `+79842234343`
- C: `address_suggest` {'query': 'Краснодар, Центральная, 100', 'count': 3}
- C: `courier_book` {'address': {'locality': 'Краснодар', 'street': 'Центральная', 'building': '100'}, 'contact': {'name': 'Владислав', 'phone': '+79885891301'}, 'interval': {'from': '2026-09-04T10:00:00+03:00', 'to': '…
- I: `address_suggest` written={'query': 'Краснодар, улица Кленовая, 65', 'count': 3} → restored={'query': 'Краснодар, центральная, 100', 'count': 3}
- C′: `address_suggest` {'query': 'Краснодар, Центральная, 100', 'count': 3}
- C′: `courier_book` {'address': {'locality': 'Краснодар', 'street': 'Центральная', 'building': '100'}, 'contact': {'name': 'Владислав', 'phone': '+79885891301'}, 'interval': {'from': '2026-09-04T10:00:00+03:00', 'to': '…
- FIELD `courier_book.address.building` [absent → absent:building] C=`100` I=``
- FIELD `courier_book.address.locality` [absent → absent:locality] C=`Краснодар` I=``
- FIELD `courier_book.address.street` [absent → absent:street] C=`Центральная` I=``
- FIELD `courier_book.contact.name` [absent → absent:name] C=`Владислав` I=``
- FIELD `courier_book.contact.phone` [absent → absent:phone] C=`+79885891301` I=``
- REPLY I: Сейчас сверю адрес по справочнику! Адрес **центральная сто, Краснодар** в справочнике не найден — подходящих совпадений нет. Пожалуйста, уточните: - Правильно ли написана улица? Может быть, **Клёновая**, **Кленовский переулок** или другое название? - Верен ли номер дома? Как только уточните — сразу…

## compare-034|0 · compare · voice_raw · L1 = · L3 ≠ · C′≈C нет · причина: **other**
- USER[1]: курьераа на пушкна шестьдесят пять корпус один этоо в самара на имя петра телефон восемь девятьсот восемьдесят семь четыреста девяносто четыре пятьсот тридцать три пять
- USER[2]: проверьте адрес в базее ии вызывайтее на завтра утром
- **LEAK** LOC `пушкна шестьдесят пять корпус один` — модель видела настоящее значение
- seen NAME `петра` → `Натальи`
- seen PHONE `восемь девятьсот восемьдесят семь четыреста девяносто четыре пятьсот тридцать три пять` → `+79055509896`
- C: `address_suggest` {'query': 'Самара, улица Пушкина, 65 корпус 1', 'count': 3}
- C: `courier_book` {'address': {'locality': 'Самара', 'street': 'Пушкина', 'building': '65 корпус 1'}, 'contact': {'name': 'Пётр', 'phone': '+79874945335'}, 'interval': {'from': '2026-09-04T09:00:00+04:00', 'to': '2026… · refusal=house_format
- C: `courier_book` {'address': {'locality': 'Самара', 'street': 'Пушкина', 'building': '65к1'}, 'contact': {'name': 'Пётр', 'phone': '+79874945335'}, 'interval': {'from': '2026-09-04T09:00:00+04:00', 'to': '2026-09-04T… · refusal=house_format
- C: `courier_book` {'address': {'locality': 'Самара', 'street': 'Пушкина', 'building': '65'}, 'contact': {'name': 'Пётр', 'phone': '+79874945335'}, 'interval': {'from': '2026-09-04T09:00:00+04:00', 'to': '2026-09-04T12…
- I: `address_suggest` written={'query': 'Самара, улица Пушкина, 65 корпус 1', 'count': 3} → restored={'query': 'Самара, улица Пушкина, 65 корпус 1', 'count': 3}
- I: `courier_book` written={'address': {'locality': 'Самара', 'street': 'Пушкина', 'building': '65 корп. 1'}, 'contact': {'name': 'Наталья', 'phone': '+79055509896'}, 'interval': {'from': '2026-09-04T09:00:00+04:00', 'to': '2026-09-04T12:00:00+04:00'}} → restored={'address': {'locality': 'Самара', 'street': 'Пушкина', 'building': '65 корп. 1'}, 'contact': {'name': 'петра', 'phone': '+79874945335'}, 'interval': {'from': '2026-09-04T09:00:00+04:00', 'to': '2026-09-04T12:00:00+04:00'}} · refusal=house_format
- I: `courier_book` written={'address': {'locality': 'Самара', 'street': 'Пушкина', 'building': '65к1'}, 'contact': {'name': 'Наталья', 'phone': '+79055509896'}, 'interval': {'from': '2026-09-04T09:00:00+04:00', 'to': '2026-09-04T12:00:00+04:00'}} → restored={'address': {'locality': 'Самара', 'street': 'Пушкина', 'building': '65к1'}, 'contact': {'name': 'петра', 'phone': '+79874945335'}, 'interval': {'from': '2026-09-04T09:00:00+04:00', 'to': '2026-09-04T12:00:00+04:00'}} · refusal=house_format
- I: `courier_book` written={'address': {'locality': 'Самара', 'street': 'Пушкина', 'building': '65'}, 'contact': {'name': 'Наталья', 'phone': '+79055509896'}, 'interval': {'from': '2026-09-04T09:00:00+04:00', 'to': '2026-09-04T12:00:00+04:00'}} → restored={'address': {'locality': 'Самара', 'street': 'Пушкина', 'building': '65'}, 'contact': {'name': 'петра', 'phone': '+79874945335'}, 'interval': {'from': '2026-09-04T09:00:00+04:00', 'to': '2026-09-04T12:00:00+04:00'}}
- C′: `address_suggest` {'query': 'Самара, улица Пушкина, 65 корпус 1', 'count': 3}
- C′: `courier_book` {'address': {'locality': 'Самара', 'street': 'Пушкина', 'building': '65к1'}, 'contact': {'name': 'Пётр', 'phone': '+79874945335'}, 'interval': {'from': '2026-09-04T09:00:00+04:00', 'to': '2026-09-04T… · refusal=house_format
- C′: `courier_book` {'address': {'locality': 'Самара', 'street': 'Пушкина', 'building': '65/1'}, 'contact': {'name': 'Пётр', 'phone': '+79874945335'}, 'interval': {'from': '2026-09-04T09:00:00+04:00', 'to': '2026-09-04T…
- FIELD `courier_book.address.building` [reformatted → loc_other] C=`65 корпус 1` I=`65 корп. 1`
- FIELD `courier_book.contact.name` [other/inflected → name_case] C=`Пётр` I=`петра`
- FIELD `courier_book.contact.name` [other/inflected → name_case] C=`Пётр` I=`петра`
- FIELD `courier_book.contact.name` [other/inflected → name_case] C=`Пётр` I=`петра`
- REPLY I: Адрес уже проверил по базе — всё есть ✅ Вызываю курьера на завтра утром (09:00–12:00 по-самарски)! Курьер вызван! ✅ **Детали заказа:** - 🆔 Номер заявки: `clm-1` - 📍 Адрес: Самара, ул. Пушкина, 65, корп. 1 - 👤 Контакт: петра, восемь девятьсот восемьдесят семь четыреста девяносто четыре пятьсот тридц…

## compare-034|1 · compare · voice_raw · L1 = · L3 ≠ · C′≈C нет · причина: **other**
- USER[1]: курьераа на пушкна шестьдесят пять корпус один этоо в самара на имя петра телефон восемь девятьсот восемьдесят семь четыреста девяносто четыре пятьсот тридцать три пять
- USER[2]: проверьте адрес в базее ии вызывайтее на завтра утром
- **LEAK** LOC `пушкна шестьдесят пять корпус один` — модель видела настоящее значение
- seen NAME `петра` → `Стеллы`
- seen PHONE `восемь девятьсот восемьдесят семь четыреста девяносто четыре пятьсот тридцать три пять` → `+79084652104`
- C: `address_suggest` {'query': 'Самара, улица Пушкина, 65 корпус 1', 'count': 3}
- C: `courier_book` {'address': {'locality': 'Самара', 'street': 'Пушкина', 'building': '65к1'}, 'contact': {'name': 'Пётр', 'phone': '+79874945335'}, 'interval': {'from': '2026-09-04T09:00:00+04:00', 'to': '2026-09-04T… · refusal=house_format
- C: `courier_book` {'address': {'locality': 'Самара', 'street': 'Пушкина', 'building': '65 к1'}, 'contact': {'name': 'Пётр', 'phone': '+79874945335'}, 'interval': {'from': '2026-09-04T09:00:00+04:00', 'to': '2026-09-04… · refusal=house_format
- C: `courier_book` {'address': {'locality': 'Самара', 'street': 'Пушкина', 'building': '65/1'}, 'contact': {'name': 'Пётр', 'phone': '+79874945335'}, 'interval': {'from': '2026-09-04T09:00:00+04:00', 'to': '2026-09-04T…
- I: `address_suggest` written={'query': 'Самара, улица Пушкина, 65 корпус 1', 'count': 3} → restored={'query': 'Самара, улица Пушкина, 65 корпус 1', 'count': 3}
- I: `courier_book` written={'address': {'locality': 'Самара', 'street': 'Пушкина', 'building': '65 к1'}, 'contact': {'name': 'Стелла', 'phone': '+79084652104'}, 'interval': {'from': '2026-09-04T09:00:00+04:00', 'to': '2026-09-04T12:00:00+04:00'}} → restored={'address': {'locality': 'Самара', 'street': 'Пушкина', 'building': '65 к1'}, 'contact': {'name': 'петра', 'phone': '+79874945335'}, 'interval': {'from': '2026-09-04T09:00:00+04:00', 'to': '2026-09-04T12:00:00+04:00'}} · refusal=house_format
- I: `courier_book` written={'address': {'locality': 'Самара', 'street': 'Пушкина', 'building': '65к1'}, 'contact': {'name': 'Стелла', 'phone': '+79084652104'}, 'interval': {'from': '2026-09-04T09:00:00+04:00', 'to': '2026-09-04T12:00:00+04:00'}} → restored={'address': {'locality': 'Самара', 'street': 'Пушкина', 'building': '65к1'}, 'contact': {'name': 'петра', 'phone': '+79874945335'}, 'interval': {'from': '2026-09-04T09:00:00+04:00', 'to': '2026-09-04T12:00:00+04:00'}} · refusal=house_format
- I: `courier_book` written={'address': {'locality': 'Самара', 'street': 'Пушкина', 'building': '65'}, 'contact': {'name': 'Стелла', 'phone': '+79084652104'}, 'interval': {'from': '2026-09-04T09:00:00+04:00', 'to': '2026-09-04T12:00:00+04:00'}} → restored={'address': {'locality': 'Самара', 'street': 'Пушкина', 'building': '65'}, 'contact': {'name': 'петра', 'phone': '+79874945335'}, 'interval': {'from': '2026-09-04T09:00:00+04:00', 'to': '2026-09-04T12:00:00+04:00'}}
- C′: `address_suggest` {'query': 'Самара, улица Пушкина, 65 корпус 1', 'count': 3}
- C′: `courier_book` {'address': {'locality': 'Самара', 'street': 'Пушкина', 'building': '65к1'}, 'contact': {'name': 'Пётр', 'phone': '+79874945335'}, 'interval': {'from': '2026-09-04T09:00:00+04:00', 'to': '2026-09-04T… · refusal=house_format
- C′: `courier_book` {'address': {'locality': 'Самара', 'street': 'Пушкина', 'building': '65к1'}, 'contact': {'name': 'Пётр', 'phone': '+79874945335'}, 'interval': {'from': '2026-09-04T09:00:00+04:00', 'to': '2026-09-04T… · refusal=house_format
- C′: `courier_book` {'address': {'locality': 'Самара', 'street': 'Пушкина', 'building': '65'}, 'contact': {'name': 'Пётр', 'phone': '+79874945335'}, 'interval': {'from': '2026-09-04T09:00:00+04:00', 'to': '2026-09-04T12…
- FIELD `courier_book.contact.name` [other/inflected → name_case] C=`Пётр` I=`петра`
- FIELD `courier_book.contact.name` [other/inflected → name_case] C=`Пётр` I=`петра`
- FIELD `courier_book.address.building` [control_erred/i1 → control_erred] C=`65/1` I=`65` · контроль ошибся; шлюз восстановил эталон корпуса
- FIELD `courier_book.contact.name` [other/inflected → name_case] C=`Пётр` I=`петра`
- REPLY I: Адрес в базе есть ✅ — **Самара, ул. Пушкина, 65, корп. 1**. Вызываю курьера на завтрашнее утро (09:00–12:00)! Готово! ✅ Курьер вызван, заявка принята. **Детали вызова:** - 📍 Самара, ул. Пушкина, 65, корп. 1 - 👤 петра, восемь девятьсот восемьдесят семь четыреста девяносто четыре пятьсот тридцать три…

## compare-034|2 · compare · voice_raw · L1 ≠ · L3 ≠ · C′≈C да · причина: **typo-normalised**
- USER[1]: курьераа на пушкна шестьдесят пять корпус один этоо в самара на имя петра телефон восемь девятьсот восемьдесят семь четыреста девяносто четыре пятьсот тридцать три пять
- USER[2]: проверьте адрес в базее ии вызывайтее на завтра утром
- **LEAK** LOC `пушкна шестьдесят пять корпус один` — модель видела настоящее значение
- seen NAME `петра` → `Майи`
- seen PHONE `восемь девятьсот восемьдесят семь четыреста девяносто четыре пятьсот тридцать три пять` → `+79645477981`
- C: `address_suggest` {'query': 'Самара, улица Пушкина, 65 корпус 1', 'count': 3}
- C: `courier_book` {'address': {'locality': 'Самара', 'street': 'Пушкина', 'building': '65 к1'}, 'contact': {'name': 'Петр', 'phone': '+79874945335'}, 'interval': {'from': '2026-09-04T09:00:00+04:00', 'to': '2026-09-04… · refusal=house_format
- C: `courier_book` {'address': {'locality': 'Самара', 'street': 'Пушкина', 'building': '65'}, 'contact': {'name': 'Петр', 'phone': '+79874945335'}, 'interval': {'from': '2026-09-04T09:00:00+04:00', 'to': '2026-09-04T12…
- I: `address_suggest` written={'query': 'Самара, улица Пушкина, 65 корпус 1', 'count': 3} → restored={'query': 'Самара, улица Пушкина, 65 корпус 1', 'count': 3}
- I: `courier_book` written={'address': {'locality': 'Самара', 'street': 'Пушкина', 'building': '65 к1'}, 'contact': {'name': 'Майя', 'phone': '+79645477981'}, 'interval': {'from': '2026-09-04T09:00:00+04:00', 'to': '2026-09-04T12:00:00+04:00'}} → restored={'address': {'locality': 'Самара', 'street': 'Пушкина', 'building': '65 к1'}, 'contact': {'name': 'петра', 'phone': '+79874945335'}, 'interval': {'from': '2026-09-04T09:00:00+04:00', 'to': '2026-09-04T12:00:00+04:00'}} · refusal=house_format
- I: `courier_book` written={'address': {'locality': 'Самара', 'street': 'Пушкина', 'building': '65к1'}, 'contact': {'name': 'Майя', 'phone': '+79645477981'}, 'interval': {'from': '2026-09-04T09:00:00+04:00', 'to': '2026-09-04T12:00:00+04:00'}} → restored={'address': {'locality': 'Самара', 'street': 'Пушкина', 'building': '65к1'}, 'contact': {'name': 'петра', 'phone': '+79874945335'}, 'interval': {'from': '2026-09-04T09:00:00+04:00', 'to': '2026-09-04T12:00:00+04:00'}} · refusal=house_format
- I: `courier_book` written={'address': {'locality': 'Самара', 'street': 'Пушкина', 'building': '65', 'porch': '1'}, 'contact': {'name': 'Майя', 'phone': '+79645477981'}, 'interval': {'from': '2026-09-04T09:00:00+04:00', 'to': '2026-09-04T12:00:00+04:00'}} → restored={'address': {'locality': 'Самара', 'street': 'Пушкина', 'building': '65', 'porch': '1'}, 'contact': {'name': 'петра', 'phone': '+79874945335'}, 'interval': {'from': '2026-09-04T09:00:00+04:00', 'to': '2026-09-04T12:00:00+04:00'}}
- C′: `address_suggest` {'query': 'Самара, улица Пушкина, 65 корпус 1', 'count': 3}
- C′: `courier_book` {'address': {'locality': 'Самара', 'street': 'Пушкина', 'building': '65к1'}, 'contact': {'name': 'Петр', 'phone': '+79874945335'}, 'interval': {'from': '2026-09-04T09:00:00+04:00', 'to': '2026-09-04T… · refusal=house_format
- C′: `courier_book` {'address': {'locality': 'Самара', 'street': 'Пушкина', 'building': '65'}, 'contact': {'name': 'Петр', 'phone': '+79874945335'}, 'interval': {'from': '2026-09-04T09:00:00+04:00', 'to': '2026-09-04T12…
- FIELD `courier_book.contact.name` [other/inflected → name_case] C=`Петр` I=`петра`
- FIELD `courier_book.address.building` [validated_refused/house_format → validated_refused] C=`65` I=`65к1`
- FIELD `courier_book.contact.name` [other/inflected → name_case] C=`Петр` I=`петра`
- FIELD `courier_book.address.building` [extra → extra:building] C=`` I=`65`
- FIELD `courier_book.address.locality` [extra → extra:locality] C=`` I=`Самара`
- FIELD `courier_book.address.porch` [extra → extra:porch] C=`` I=`1`
- FIELD `courier_book.address.street` [extra → extra:street] C=`` I=`Пушкина`
- FIELD `courier_book.contact.name` [extra → extra:name] C=`` I=`петра`
- FIELD `courier_book.contact.phone` [extra → extra:phone] C=`` I=`+79874945335`
- REPLY I: Адрес подтверждён в базе: **Самара, ул. Пушкина, 65, корпус 1**. Вызываю курьера на завтра утром (09:00–12:00)! Курьер успешно вызван! 🎉 **Детали вызова:** - 📍 **Адрес:** Самара, ул. Пушкина, 65, корпус 1 - 👤 **Контакт:** петра, восемь девятьсот восемьдесят семь четыреста девяносто четыре пятьсот т…

## compare-035|0 · compare · voice_itn · L1 ≠ · L3 ≠ · C′≈C да · причина: **Б8-echo**
- USER[1]: алло курьера на кирова 79 это в глазов на имя анну телефон 8 977 777 88 99
- USER[2]: сверьте по справочнику и оформляйте на завтра с десяти до четырёх
- seen LOC `кирова 79` → `улицы Осиновой 103`
- seen NAME `анну` → `Ладу`
- seen PHONE `8 977 777 88 99` → `+79955768579`
- C: `address_suggest` {'query': 'Глазов, улица Кирова 79', 'count': 1}
- C: `courier_book` {'address': {'locality': 'Глазов', 'street': 'Кирова', 'building': '79'}, 'contact': {'name': 'Анна', 'phone': '+79777778899'}, 'interval': {'from': '2026-09-04T10:00:00+04:00', 'to': '2026-09-04T16:…
- I: `address_suggest` written={'query': 'Глазов, улица Осиновая, 103', 'count': 3} → restored={'query': 'Глазов, кирова, 79', 'count': 3}
- C′: `address_suggest` {'query': 'Глазов, улица Кирова, 79', 'count': 3}
- C′: `courier_book` {'address': {'locality': 'Глазов', 'street': 'Кирова', 'building': '79'}, 'contact': {'name': 'Анна', 'phone': '+79777778899'}, 'interval': {'from': '2026-09-04T10:00:00+04:00', 'to': '2026-09-04T16:…
- FIELD `courier_book.address.building` [absent → absent:building] C=`79` I=``
- FIELD `courier_book.address.locality` [absent → absent:locality] C=`Глазов` I=``
- FIELD `courier_book.address.street` [absent → absent:street] C=`Кирова` I=``
- FIELD `courier_book.contact.name` [absent → absent:name] C=`Анна` I=``
- FIELD `courier_book.contact.phone` [absent → absent:phone] C=`+79777778899` I=``
- REPLY I: Сначала проверю адрес по справочнику! Справочник не нашёл кирова 79 в Глазове — результаты совсем не совпадают с запросом. Возможно, улица называется немного иначе. Уточните, пожалуйста: - Точное название улицы (может быть **Осиновская**, **кирова 79 роща** и т.п.)? - Или, возможно, это другой насе…

## compare-035|2 · compare · voice_itn · L1 ≠ · L3 ≠ · C′≈C да · причина: **Б8-echo**
- USER[1]: алло курьера на кирова 79 это в глазов на имя анну телефон 8 977 777 88 99
- USER[2]: сверьте по справочнику и оформляйте на завтра с десяти до четырёх
- seen LOC `кирова 79` → `улицы Тополиной 112`
- seen NAME `анну` → `Ольгу`
- seen PHONE `8 977 777 88 99` → `+79948937987`
- C: `address_suggest` {'query': 'Глазов, улица Кирова, 79', 'count': 3}
- C: `courier_book` {'address': {'locality': 'Глазов', 'street': 'Кирова', 'building': '79'}, 'contact': {'name': 'Анна', 'phone': '+79777778899'}, 'interval': {'from': '2026-09-04T10:00:00+04:00', 'to': '2026-09-04T16:…
- I: `address_suggest` written={'query': 'Глазов, улица Тополиная, 112', 'count': 3} → restored={'query': 'Глазов, кирова, 79', 'count': 3}
- C′: `address_suggest` {'query': 'Глазов, Кирова 79', 'count': 3}
- C′: `courier_book` {'address': {'locality': 'Глазов', 'street': 'Кирова', 'building': '79'}, 'contact': {'name': 'Анна', 'phone': '+79777778899'}, 'interval': {'from': '2026-09-04T10:00:00+04:00', 'to': '2026-09-04T16:…
- FIELD `courier_book.address.building` [absent → absent:building] C=`79` I=``
- FIELD `courier_book.address.locality` [absent → absent:locality] C=`Глазов` I=``
- FIELD `courier_book.address.street` [absent → absent:street] C=`Кирова` I=``
- FIELD `courier_book.contact.name` [absent → absent:name] C=`Анна` I=``
- FIELD `courier_book.contact.phone` [absent → absent:phone] C=`+79777778899` I=``
- REPLY I: Сейчас проверю адрес по справочнику! Справочник не нашёл улицу **кирова 79** в Глазове — ни одно из предложений не совпадает с указанным адресом. Пожалуйста, уточните: - Точное название улицы (возможно, другое написание?) - Или подтвердите адрес, и я оформлю как есть, на ваш страх и риск

## compare-036|0 · compare · chat · L1 ≠ · L3 ≠ · C′≈C да · причина: **Б8-echo**
- USER[1]: здравствуйте курьера на маяковского 82 это в можга на имя валерию телефон 8-952-114-78-01
- USER[2]: проверьте адрес в базе и вызывайте на завтра утром
- seen LOC `маяковского 82` → `улицы Каштановой 22`
- seen NAME `валерию` → `Николаю`
- seen PHONE `8-952-114-78-01` → `+79749971888`
- C: `address_suggest` {'query': 'Можга, улица Маяковского, 82', 'count': 3}
- C: `courier_book` {'address': {'locality': 'Можга', 'street': 'Маяковского', 'building': '82'}, 'contact': {'name': 'Валерия', 'phone': '+79521147801'}, 'interval': {'from': '2026-09-04T09:00:00+04:00', 'to': '2026-09…
- I: `address_suggest` written={'query': 'Можга, улица Каштановая, 22', 'count': 3} → restored={'query': 'Можга, маяковского, 82', 'count': 3}
- C′: `address_suggest` {'query': 'Можга, Маяковского 82', 'count': 3}
- C′: `courier_book` {'address': {'locality': 'Можга', 'street': 'Маяковского', 'building': '82'}, 'contact': {'name': 'Валерия', 'phone': '+79521147801'}, 'interval': {'from': '2026-09-04T09:00:00+04:00', 'to': '2026-09…
- FIELD `courier_book.address.building` [absent → absent:building] C=`82` I=``
- FIELD `courier_book.address.locality` [absent → absent:locality] C=`Можга` I=``
- FIELD `courier_book.address.street` [absent → absent:street] C=`Маяковского` I=``
- FIELD `courier_book.contact.name` [absent → absent:name] C=`Валерия` I=``
- FIELD `courier_book.contact.phone` [absent → absent:phone] C=`+79521147801` I=``
- REPLY I: Проверяю адрес в базе! К сожалению, адрес **Можга, маяковского 82** в базе не найден — подходящих совпадений нет. Возможно, улица называется иначе или в адресе есть опечатка. Пожалуйста, уточните адрес — возможно, вы имели в виду другую улицу или другой город? Тогда сразу оформим вызов курьера.

## compare-036|1 · compare · chat · L1 ≠ · L3 ≠ · C′≈C да · причина: **Б8-echo**
- USER[1]: здравствуйте курьера на маяковского 82 это в можга на имя валерию телефон 8-952-114-78-01
- USER[2]: проверьте адрес в базе и вызывайте на завтра утром
- seen LOC `маяковского 82` → `улицы Жасминовой 193`
- seen NAME `валерию` → `Тарасу`
- seen PHONE `8-952-114-78-01` → `+79038367400`
- C: `address_suggest` {'query': 'Можга, улица Маяковского, 82', 'count': 3}
- C: `courier_book` {'address': {'locality': 'Можга', 'street': 'Маяковского', 'building': '82'}, 'contact': {'name': 'Валерия', 'phone': '+79521147801'}, 'interval': {'from': '2026-09-04T09:00:00+04:00', 'to': '2026-09…
- I: `address_suggest` written={'query': 'Можга, улица Жасминовая, 193'} → restored={'query': 'Можга, маяковского, 82'}
- C′: `address_suggest` {'query': 'Можга, улица Маяковского, 82', 'count': 3}
- C′: `courier_book` {'address': {'locality': 'Можга', 'street': 'Маяковского', 'building': '82'}, 'contact': {'name': 'Валерия', 'phone': '+79521147801'}, 'interval': {'from': '2026-09-04T09:00:00+04:00', 'to': '2026-09…
- FIELD `courier_book.address.building` [absent → absent:building] C=`82` I=``
- FIELD `courier_book.address.locality` [absent → absent:locality] C=`Можга` I=``
- FIELD `courier_book.address.street` [absent → absent:street] C=`Маяковского` I=``
- FIELD `courier_book.contact.name` [absent → absent:name] C=`Валерия` I=``
- FIELD `courier_book.contact.phone` [absent → absent:phone] C=`+79521147801` I=``
- REPLY I: Проверяю адрес в базе! К сожалению, адрес **маяковского 82, Можга** не найден в базе — ни одно из предложений не совпадает с вашим запросом. Пожалуйста, уточните адрес: - Возможно, улица называется иначе? (например, **Жасминная**, **Жасмин** и т.д.) - Или номер дома другой? Как только подтвердим ад…

## compare-036|2 · compare · chat · L1 ≠ · L3 ≠ · C′≈C да · причина: **Б8-echo**
- USER[1]: здравствуйте курьера на маяковского 82 это в можга на имя валерию телефон 8-952-114-78-01
- USER[2]: проверьте адрес в базе и вызывайте на завтра утром
- seen LOC `маяковского 82` → `улицы Абрикосовой 79`
- seen NAME `валерию` → `Платону`
- seen PHONE `8-952-114-78-01` → `+79076128900`
- C: `address_suggest` {'query': 'Можга, улица Маяковского, 82', 'count': 3}
- C: `courier_book` {'address': {'locality': 'Можга', 'street': 'Маяковского', 'building': '82'}, 'contact': {'name': 'Валерия', 'phone': '+79521147801'}, 'interval': {'from': '2026-09-04T09:00:00+04:00', 'to': '2026-09…
- I: `address_suggest` written={'query': 'Можга, улица Абрикосовая, 79', 'count': 3} → restored={'query': 'Можга, маяковского, 82', 'count': 3}
- C′: `address_suggest` {'query': 'Можга, Маяковского 82'}
- C′: `courier_book` {'address': {'locality': 'Можга', 'street': 'Маяковского', 'building': '82'}, 'contact': {'name': 'Валерия', 'phone': '+79521147801'}, 'interval': {'from': '2026-09-04T09:00:00+04:00', 'to': '2026-09…
- FIELD `courier_book.address.building` [absent → absent:building] C=`82` I=``
- FIELD `courier_book.address.locality` [absent → absent:locality] C=`Можга` I=``
- FIELD `courier_book.address.street` [absent → absent:street] C=`Маяковского` I=``
- FIELD `courier_book.contact.name` [absent → absent:name] C=`Валерия` I=``
- FIELD `courier_book.contact.phone` [absent → absent:phone] C=`+79521147801` I=``
- REPLY I: Сейчас проверю адрес в базе! К сожалению, адрес **маяковского 82, Можга** не найден в базе — похожих совпадений нет. Пожалуйста, уточните: - Правильно ли написана улица? Может быть, другое название (например, маяковского 82, переулок и т.д.)? - Верный ли номер дома — **82**? Как только подтвердите …

## compare-039|0 · compare · chat · L1 ≠ · L3 ≠ · C′≈C да · причина: **Б8-echo**
- USER[1]: курьера на нижняя 121 это в колпино на имя артёма телефон 89653645241
- USER[2]: сверьте по справочнику и оформляйте на завтра с десяти до четырёх
- seen LOC `нижняя 121` → `улица Черёмуховая 129`
- seen NAME `артёма` → `Никиты`
- seen PHONE `89653645241` → `+79785010986`
- C: `address_suggest` {'query': 'Колпино, Нижняя, 121', 'count': 3}
- C: `courier_book` {'address': {'locality': 'Колпино', 'street': 'Нижняя', 'building': '121'}, 'contact': {'name': 'Артём', 'phone': '+79653645241'}, 'interval': {'from': '2026-09-04T10:00:00+03:00', 'to': '2026-09-04T…
- I: `address_suggest` written={'query': 'Колпино, улица Черёмуховая, 129', 'count': 3} → restored={'query': 'Колпино, нижняя, 121', 'count': 3}
- C′: `address_suggest` {'query': 'Колпино Нижняя 121', 'count': 3}
- C′: `courier_book` {'address': {'locality': 'Колпино', 'street': 'Нижняя', 'building': '121'}, 'contact': {'name': 'Артём', 'phone': '+79653645241'}, 'interval': {'from': '2026-09-04T10:00:00+03:00', 'to': '2026-09-04T…
- FIELD `courier_book.address.building` [absent → absent:building] C=`121` I=``
- FIELD `courier_book.address.locality` [absent → absent:locality] C=`Колпино` I=``
- FIELD `courier_book.address.street` [absent → absent:street] C=`Нижняя` I=``
- FIELD `courier_book.contact.name` [absent → absent:name] C=`Артём` I=``
- FIELD `courier_book.contact.phone` [absent → absent:phone] C=`+79653645241` I=``
- REPLY I: Сверяю адрес по справочнику! Справочник не нашёл точного совпадения для **нижняя 121, Колпино** — предложенные варианты не совпадают с вашим адресом. Уточните, пожалуйста: - Точное написание улицы (может быть, **нижняя 121** пишется иначе в справочнике)? - Есть ли квартира/подъезд? Как только подтв…

## compare-040|0 · compare · voice_raw · L1 ≠ · L3 ≠ · C′≈C да · причина: **Б8-echo**
- USER[1]: аллоо курьера наа шумайлова двадцать шесть этоо в сортавала на имя сергея телефон восем девятьсот шестнадцать четыреста два сто восемнадцать семь
- USER[2]: сверьтее по справочникуу ии оформляйтее на завтра с десяти доо четырёх
- seen LOC `шумайлова двадцать шесть` → `улицу Речную 3`
- seen NAME `сергея` → `Максима`
- seen PHONE `восем девятьсот шестнадцать четыреста два сто восемнадцать семь` → `+79197250865`
- C: `address_suggest` {'query': 'Сортавала, Шумайлова, 26', 'count': 3}
- C: `courier_book` {'address': {'locality': 'Сортавала', 'street': 'Шумайлова', 'building': '26'}, 'contact': {'name': 'Сергей', 'phone': '+79164021187'}, 'interval': {'from': '2026-09-04T10:00:00+03:00', 'to': '2026-0…
- I: `address_suggest` written={'query': 'Сортавала, улица Речная, 3', 'count': 3} → restored={'query': 'Сортавала, улица шумайлова, 26', 'count': 3}
- C′: `address_suggest` {'query': 'Сортавала, Шумайлова 26', 'count': 3}
- C′: `courier_book` {'address': {'locality': 'Сортавала', 'street': 'Шумайлова', 'building': '26'}, 'contact': {'name': 'Сергей', 'phone': '+79164021187'}, 'interval': {'from': '2026-09-04T10:00:00+03:00', 'to': '2026-0…
- FIELD `courier_book.address.building` [absent → absent:building] C=`26` I=``
- FIELD `courier_book.address.locality` [absent → absent:locality] C=`Сортавала` I=``
- FIELD `courier_book.address.street` [absent → absent:street] C=`Шумайлова` I=``
- FIELD `courier_book.contact.name` [absent → absent:name] C=`Сергей` I=``
- FIELD `courier_book.contact.phone` [absent → absent:phone] C=`+79164021187` I=``
- REPLY I: Сначала проверю адрес по справочнику! Справочник не нашёл точного совпадения для адреса **Сортавала, ул. шумайлова двадцать шесть** — ни один из вариантов не подходит. Уточните, пожалуйста: - Правильно ли написана **улица** (может, г Сортавала, ул Шумайлова, д 26 — точное название)? - Есть ли **ном…

## compare-040|1 · compare · voice_raw · L1 ≠ · L3 ≠ · C′≈C да · причина: **Б8-echo**
- USER[1]: аллоо курьера наа шумайлова двадцать шесть этоо в сортавала на имя сергея телефон восем девятьсот шестнадцать четыреста два сто восемнадцать семь
- USER[2]: сверьтее по справочникуу ии оформляйтее на завтра с десяти доо четырёх
- seen LOC `шумайлова двадцать шесть` → `улицу Родниковую 33`
- seen NAME `сергея` → `Ратмира`
- seen PHONE `восем девятьсот шестнадцать четыреста два сто восемнадцать семь` → `+79334601868`
- C: `address_suggest` {'query': 'Сортавала, Шумайлова, 26', 'count': 3}
- C: `courier_book` {'address': {'locality': 'Сортавала', 'street': 'Шумайлова', 'building': '26'}, 'contact': {'name': 'Сергей', 'phone': '+79164021187'}, 'interval': {'from': '2026-09-04T10:00:00+03:00', 'to': '2026-0…
- I: `address_suggest` written={'query': 'Сортавала, улица Родниковая, 33', 'count': 3} → restored={'query': 'Сортавала, улица шумайлова, 26', 'count': 3}
- C′: `address_suggest` {'query': 'Сортавала, Шумайлова, 26', 'count': 3}
- C′: `courier_book` {'address': {'locality': 'Сортавала', 'street': 'Шумайлова', 'building': '26'}, 'contact': {'name': 'Сергей', 'phone': '+79164021187'}, 'interval': {'from': '2026-09-04T10:00:00+03:00', 'to': '2026-0…
- FIELD `courier_book.address.building` [absent → absent:building] C=`26` I=``
- FIELD `courier_book.address.locality` [absent → absent:locality] C=`Сортавала` I=``
- FIELD `courier_book.address.street` [absent → absent:street] C=`Шумайлова` I=``
- FIELD `courier_book.contact.name` [absent → absent:name] C=`Сергей` I=``
- FIELD `courier_book.contact.phone` [absent → absent:phone] C=`+79164021187` I=``
- REPLY I: Сейчас сверю адрес по справочнику! Справочник не подтвердил адрес **шумайлова двадцать шесть, Сортавала** — ни одно из предложенных совпадений не соответствует. Возможно, улица называется иначе или адрес введён с ошибкой. Уточните, пожалуйста: - Верно ли написание улицы? (Может быть **г Сортавала, …

## compare-040|2 · compare · voice_raw · L1 ≠ · L3 ≠ · C′≈C да · причина: **Б8-echo**
- USER[1]: аллоо курьера наа шумайлова двадцать шесть этоо в сортавала на имя сергея телефон восем девятьсот шестнадцать четыреста два сто восемнадцать семь
- USER[2]: сверьтее по справочникуу ии оформляйтее на завтра с десяти доо четырёх
- seen LOC `шумайлова двадцать шесть` → `улицу Вязовую 87`
- seen NAME `сергея` → `Артура`
- seen PHONE `восем девятьсот шестнадцать четыреста два сто восемнадцать семь` → `+79484397832`
- C: `address_suggest` {'query': 'Сортавала, улица Шумайлова, 26', 'count': 3}
- C: `courier_book` {'address': {'locality': 'Сортавала', 'street': 'Шумайлова', 'building': '26'}, 'contact': {'name': 'Сергей', 'phone': '+79164021187'}, 'interval': {'from': '2026-09-04T10:00:00+03:00', 'to': '2026-0…
- I: `address_suggest` written={'query': 'Сортавала, улица Вязовая, 87', 'count': 3} → restored={'query': 'Сортавала, улица шумайлова, 26', 'count': 3}
- C′: `address_suggest` {'query': 'Сортавала, Шумайлова, 26', 'count': 3}
- C′: `courier_book` {'address': {'locality': 'Сортавала', 'street': 'Шумайлова', 'building': '26'}, 'contact': {'name': 'Сергей', 'phone': '+79164021187'}, 'interval': {'from': '2026-09-04T10:00:00+03:00', 'to': '2026-0…
- FIELD `courier_book.address.building` [absent → absent:building] C=`26` I=``
- FIELD `courier_book.address.locality` [absent → absent:locality] C=`Сортавала` I=``
- FIELD `courier_book.address.street` [absent → absent:street] C=`Шумайлова` I=``
- FIELD `courier_book.contact.name` [absent → absent:name] C=`Сергей` I=``
- FIELD `courier_book.contact.phone` [absent → absent:phone] C=`+79164021187` I=``
- REPLY I: Сверяю адрес по справочнику! Справочник не подтвердил адрес — ни один из вариантов не соответствует **шумайлова двадцать шесть, Сортавала**. Результаты вернули совсем другие улицы и города. Пожалуйста, проверьте адрес: - Верно ли написание улицы? (Может, **Вязовская**, **Берёзовая** и т.п.?) - Верн…

## compare-041|0 · compare · voice_itn · L1 ≠ · L3 ≠ · C′≈C да · причина: **Б8-echo**
- USER[1]: курьера на вишнёвая 148 это в сортавала на имя елену телефон 8-951-001-20-50
- USER[2]: сверьте по справочнику и оформляйте на завтра с десяти до четырёх
- seen LOC `вишнёвая 148` → `улица Тополиная 90`
- seen NAME `елену` → `Аглаю`
- seen PHONE `8-951-001-20-50` → `+79982597194`
- C: `address_suggest` {'query': 'Сортавала, Вишнёвая, 148', 'count': 3}
- C: `courier_book` {'address': {'locality': 'Сортавала', 'street': 'Вишнёвая', 'building': '148'}, 'contact': {'name': 'Елена', 'phone': '+79510012050'}, 'interval': {'from': '2026-09-04T10:00:00+03:00', 'to': '2026-09…
- I: `address_suggest` written={'query': 'Сортавала, улица Тополиная, 90', 'count': 3} → restored={'query': 'Сортавала, улица вишнёвая, 148', 'count': 3}
- C′: `address_suggest` {'query': 'Сортавала, Вишнёвая, 148', 'count': 3}
- C′: `courier_book` {'address': {'locality': 'Сортавала', 'street': 'Вишнёвая', 'building': '148'}, 'contact': {'name': 'Елена', 'phone': '+79510012050'}, 'interval': {'from': '2026-09-04T10:00:00+03:00', 'to': '2026-09…
- FIELD `courier_book.address.building` [absent → absent:building] C=`148` I=``
- FIELD `courier_book.address.locality` [absent → absent:locality] C=`Сортавала` I=``
- FIELD `courier_book.address.street` [absent → absent:street] C=`Вишнёвая` I=``
- FIELD `courier_book.contact.name` [absent → absent:name] C=`Елена` I=``
- FIELD `courier_book.contact.phone` [absent → absent:phone] C=`+79510012050` I=``
- REPLY I: Сверяю адрес по справочнику! По справочнику точного совпадения для **вишнёвая 148, Сортавала** не нашлось — результаты вернулись с другими улицами и номерами домов, подтвердить адрес не удалось. Пожалуйста, перепроверьте адрес: - Возможно, улица называется иначе? - Верен ли номер дома — **148**? Ка…

## compare-041|1 · compare · voice_itn · L1 ≠ · L3 ≠ · C′≈C да · причина: **Б8-echo**
- USER[1]: курьера на вишнёвая 148 это в сортавала на имя елену телефон 8-951-001-20-50
- USER[2]: сверьте по справочнику и оформляйте на завтра с десяти до четырёх
- seen LOC `вишнёвая 148` → `улица Каштановая 117`
- seen NAME `елену` → `Нину`
- seen PHONE `8-951-001-20-50` → `+79479882151`
- C: `address_suggest` {'query': 'Сортавала, Вишнёвая, 148', 'count': 3}
- C: `courier_book` {'address': {'locality': 'Сортавала', 'street': 'Вишнёвая', 'building': '148'}, 'contact': {'name': 'Елена', 'phone': '+79510012050'}, 'interval': {'from': '2026-09-04T10:00:00+03:00', 'to': '2026-09…
- I: `address_suggest` written={'query': 'Сортавала, улица Каштановая, 117', 'count': 3} → restored={'query': 'Сортавала, улица вишнёвая, 148', 'count': 3}
- C′: `address_suggest` {'query': 'Сортавала Вишнёвая 148', 'count': 3}
- C′: `courier_book` {'address': {'locality': 'Сортавала', 'street': 'Вишнёвая', 'building': '148'}, 'contact': {'name': 'Елена', 'phone': '+79510012050'}, 'interval': {'from': '2026-09-04T10:00:00+03:00', 'to': '2026-09…
- FIELD `courier_book.address.building` [absent → absent:building] C=`148` I=``
- FIELD `courier_book.address.locality` [absent → absent:locality] C=`Сортавала` I=``
- FIELD `courier_book.address.street` [absent → absent:street] C=`Вишнёвая` I=``
- FIELD `courier_book.contact.name` [absent → absent:name] C=`Елена` I=``
- FIELD `courier_book.contact.phone` [absent → absent:phone] C=`+79510012050` I=``
- REPLY I: Сейчас проверю адрес по справочнику! Справочник не нашёл точного совпадения для **вишнёвая 148 в Сортавале** — похожих адресов нет. Возможно, улица новая или в базе есть расхождение. Хотите всё равно оформить вызов курьера с адресом как вы указали? Или уточните адрес — возможно, улица называется ин…

## compare-041|2 · compare · voice_itn · L1 ≠ · L3 ≠ · C′≈C да · причина: **Б8-echo**
- USER[1]: курьера на вишнёвая 148 это в сортавала на имя елену телефон 8-951-001-20-50
- USER[2]: сверьте по справочнику и оформляйте на завтра с десяти до четырёх
- seen LOC `вишнёвая 148` → `улица Ивовая 27`
- seen NAME `елену` → `Валентину`
- seen PHONE `8-951-001-20-50` → `+79721580726`
- C: `address_suggest` {'query': 'Сортавала, Вишнёвая, 148', 'count': 3}
- C: `courier_book` {'address': {'locality': 'Сортавала', 'street': 'Вишнёвая', 'building': '148'}, 'contact': {'name': 'Елена', 'phone': '+79510012050'}, 'interval': {'from': '2026-09-04T10:00:00+03:00', 'to': '2026-09…
- I: `address_suggest` written={'query': 'Сортавала, улица Ивовая 27', 'count': 3} → restored={'query': 'Сортавала, улица вишнёвая 148', 'count': 3}
- C′: `address_suggest` {'query': 'Сортавала Вишнёвая 148', 'count': 3}
- C′: `courier_book` {'address': {'locality': 'Сортавала', 'street': 'Вишнёвая', 'building': '148'}, 'contact': {'name': 'Елена', 'phone': '+79510012050'}, 'interval': {'from': '2026-09-04T10:00:00+03:00', 'to': '2026-09…
- FIELD `courier_book.address.building` [absent → absent:building] C=`148` I=``
- FIELD `courier_book.address.locality` [absent → absent:locality] C=`Сортавала` I=``
- FIELD `courier_book.address.street` [absent → absent:street] C=`Вишнёвая` I=``
- FIELD `courier_book.contact.name` [absent → absent:name] C=`Елена` I=``
- FIELD `courier_book.contact.phone` [absent → absent:phone] C=`+79510012050` I=``
- REPLY I: Сверяю адрес по справочнику! Справочник не нашёл точного совпадения для **вишнёвая 148, Сортавала, улица Ивовая 27** — похожих адресов нет, выдались нерелевантные варианты. Пожалуйста, проверьте адрес: возможно, улица называется иначе (например, Вишнёвая, Краснодарский край, г Краснодар, ул Вишнёва…

## correction-010|0 · correction · chat · L1 ≠ · L3 ≠ · C′≈C да · причина: **other**
- USER[1]: курьера на полевая 30 кв 150 нет не так правильно полевая 2 квартира 150 это в ижевск это ерохин пётр телефон 8-903-765-43-21
- USER[2]: завтра с десяти до двух
- seen LOC `полевая 30 кв 150` → `улица Лавандовая 69, кв. 52`
- seen LOC `полевая 2 квартира 150` → `улица Родниковая 145, кв. 24`
- seen NAME `ерохин пётр` → `Панов Александр`
- seen PHONE `8-903-765-43-21` → `+79626684321`
- C: `courier_book` {'address': {'locality': 'Ижевск', 'street': 'Полевая', 'building': '2', 'sflat': '150'}, 'contact': {'name': 'Ерохин Пётр', 'phone': '+79037654321'}, 'interval': {'from': '2026-09-04T10:00:00+04:00'…
- I: `courier_book` written={'address': {'locality': 'Ижевск', 'street': 'Родниковая', 'building': '145', 'sflat': '24'}, 'contact': {'name': 'Панов Александр', 'phone': '+79626684321'}, 'interval': {'from': '2026-09-04T10:00:00+04:00', 'to': '2026-09-04T14:00:00+04:00'}} → restored={'address': {'locality': 'Ижевск', 'street': 'полевая', 'building': '2', 'sflat': '150'}, 'contact': {'name': 'ерохин пётр', 'phone': '+79037654321'}, 'interval': {'from': '2026-09-04T10:00:00+04:00', 'to': '2026-09-04T14:00:00+04:00'}}
- I: `crm_upsert_contact` written={'contact': {'last_name': 'Панов', 'first_name': 'Александр', 'initials': 'А.', 'name_latin': 'Panov Alexander', 'phone': '+79626684321', 'gender': 'M', 'address': {'city': 'Ижевск', 'street': 'Родниковая', 'house': '145', 'flat': '24'}}} → restored={'contact': {'last_name': 'ерохин', 'first_name': 'пётр', 'initials': 'А.', 'name_latin': 'Erokhin Alexander', 'phone': '+79037654321', 'gender': 'M', 'address': {'city': 'Ижевск', 'street': 'полевая', 'house': '2', 'flat': '150'}}}
- C′: `courier_book` {'address': {'locality': 'Ижевск', 'street': 'Полевая', 'building': '2', 'sflat': '150'}, 'contact': {'name': 'Ерохин Пётр', 'phone': '+79037654321'}, 'interval': {'from': '2026-09-04T10:00:00+04:00'…
- FIELD `crm_upsert_contact.contact.address.city` [extra → extra:city] C=`` I=`Ижевск`
- FIELD `crm_upsert_contact.contact.address.flat` [extra → extra:flat] C=`` I=`150`
- FIELD `crm_upsert_contact.contact.address.house` [extra → extra:house] C=`` I=`2`
- FIELD `crm_upsert_contact.contact.address.street` [extra → extra:street] C=`` I=`полевая`
- FIELD `crm_upsert_contact.contact.first_name` [extra → extra:first_name] C=`` I=`пётр`
- FIELD `crm_upsert_contact.contact.gender` [extra → extra:gender] C=`` I=`M`
- FIELD `crm_upsert_contact.contact.initials` [extra → extra:initials] C=`` I=`А.`
- FIELD `crm_upsert_contact.contact.last_name` [extra → extra:last_name] C=`` I=`ерохин`
- FIELD `crm_upsert_contact.contact.name_latin` [extra → extra:name_latin] C=`` I=`Erokhin Alexander`
- FIELD `crm_upsert_contact.contact.phone` [extra → extra:phone] C=`` I=`+79037654321`
- REPLY I: Оформляю! Запускаю сразу два действия параллельно — вызов курьера и карточку клиента. Всё готово! Вот итог: **🚚 Курьер вызван** (№ clm-1) - **Адрес:** г. Ижевск, полевая 2 квартира 150 - **Получатель:** ерохин пётр, 8-903-765-43-21 - **Дата и время:** 4 сентября 2026, с 10:00 до 14:00 **👤 Карточка …

## correction-010|1 · correction · chat · L1 ≠ · L3 ≠ · C′≈C да · причина: **other**
- USER[1]: курьера на полевая 30 кв 150 нет не так правильно полевая 2 квартира 150 это в ижевск это ерохин пётр телефон 8-903-765-43-21
- USER[2]: завтра с десяти до двух
- seen LOC `полевая 30 кв 150` → `улица Каштановая 69, кв. 3`
- seen LOC `полевая 2 квартира 150` → `улица Лавандовая 154, кв. 70`
- seen NAME `ерохин пётр` → `Устинов Владислав`
- seen PHONE `8-903-765-43-21` → `+79938943179`
- C: `courier_book` {'address': {'locality': 'Ижевск', 'street': 'Полевая', 'building': '2', 'sflat': '150'}, 'contact': {'name': 'Ерохин Пётр', 'phone': '+79037654321'}, 'interval': {'from': '2026-09-04T10:00:00+04:00'…
- I: `courier_book` written={'address': {'locality': 'Ижевск', 'street': 'Лавандовая', 'building': '154', 'sflat': '70'}, 'contact': {'name': 'Устинов Владислав', 'phone': '+79938943179'}, 'interval': {'from': '2026-09-04T10:00:00+04:00', 'to': '2026-09-04T14:00:00+04:00'}} → restored={'address': {'locality': 'Ижевск', 'street': 'полевая', 'building': '2', 'sflat': '150'}, 'contact': {'name': 'ерохин пётр', 'phone': '+79037654321'}, 'interval': {'from': '2026-09-04T10:00:00+04:00', 'to': '2026-09-04T14:00:00+04:00'}}
- I: `crm_upsert_contact` written={'contact': {'last_name': 'Устинов', 'first_name': 'Владислав', 'initials': 'В.', 'name_latin': 'Ustinov Vladislav', 'phone': '+79938943179', 'address': {'city': 'Ижевск', 'street': 'Лавандовая', 'house': '154', 'flat': '70'}}} → restored={'contact': {'last_name': 'ерохин', 'first_name': 'пётр', 'initials': 'В.', 'name_latin': 'Erokhin Petr', 'phone': '+79037654321', 'address': {'city': 'Ижевск', 'street': 'полевая', 'house': '2', 'flat': '150'}}}
- C′: `courier_book` {'address': {'locality': 'Ижевск', 'street': 'Полевая', 'building': '2', 'sflat': '150'}, 'contact': {'name': 'Ерохин Пётр', 'phone': '+79037654321'}, 'interval': {'from': '2026-09-04T10:00:00+04:00'…
- FIELD `crm_upsert_contact.contact.address.city` [extra → extra:city] C=`` I=`Ижевск`
- FIELD `crm_upsert_contact.contact.address.flat` [extra → extra:flat] C=`` I=`150`
- FIELD `crm_upsert_contact.contact.address.house` [extra → extra:house] C=`` I=`2`
- FIELD `crm_upsert_contact.contact.address.street` [extra → extra:street] C=`` I=`полевая`
- FIELD `crm_upsert_contact.contact.first_name` [extra → extra:first_name] C=`` I=`пётр`
- FIELD `crm_upsert_contact.contact.initials` [extra → extra:initials] C=`` I=`В.`
- FIELD `crm_upsert_contact.contact.last_name` [extra → extra:last_name] C=`` I=`ерохин`
- FIELD `crm_upsert_contact.contact.name_latin` [extra → extra:name_latin] C=`` I=`Erokhin Petr`
- FIELD `crm_upsert_contact.contact.phone` [extra → extra:phone] C=`` I=`+79037654321`
- REPLY I: Отлично, оформляю! Запускаю вызов курьера и создаю карточку клиента одновременно. Всё готово! ✅ **Курьер вызван** (заявка `clm-1`) - 📍 Ижевск, полевая 2 квартира 150 - 👤 ерохин пётр, 8-903-765-43-21 - 🕙 Завтра, 4 сентября, с 10:00 до 14:00 **Карточка клиента** создана/обновлена в CRM (`c-1`). Если …

## correction-010|2 · correction · chat · L1 = · L3 ≠ · C′≈C нет · причина: **other**
- USER[1]: курьера на полевая 30 кв 150 нет не так правильно полевая 2 квартира 150 это в ижевск это ерохин пётр телефон 8-903-765-43-21
- USER[2]: завтра с десяти до двух
- seen LOC `полевая 30 кв 150` → `улица Мятная 146, кв. 221`
- seen LOC `полевая 2 квартира 150` → `улица Тополиная 100, кв. 150`
- seen NAME `ерохин пётр` → `Щукин Радислав`
- seen PHONE `8-903-765-43-21` → `+79837849986`
- C: `courier_book` {'address': {'locality': 'Ижевск', 'street': 'Полевая', 'building': '2', 'sflat': '150'}, 'contact': {'name': 'Ерохин Пётр', 'phone': '+79037654321'}, 'interval': {'from': '2026-09-04T10:00:00+04:00'…
- C: `crm_upsert_contact` {'contact': {'last_name': 'Ерохин', 'first_name': 'Пётр', 'initials': 'П.', 'name_latin': 'Erokhin Pyotr', 'gender': 'M', 'phone': '+79037654321', 'address': {'city': 'Ижевск', 'street': 'Полевая', '…
- I: `courier_book` written={'address': {'locality': 'Ижевск', 'street': 'Тополиная', 'building': '100', 'sflat': '150'}, 'contact': {'name': 'Щукин Радислав', 'phone': '+79837849986'}, 'interval': {'from': '2026-09-04T10:00:00+04:00', 'to': '2026-09-04T14:00:00+04:00'}} → restored={'address': {'locality': 'Ижевск', 'street': 'полевая', 'building': '2', 'sflat': '150'}, 'contact': {'name': 'ерохин пётр', 'phone': '+79037654321'}, 'interval': {'from': '2026-09-04T10:00:00+04:00', 'to': '2026-09-04T14:00:00+04:00'}}
- I: `crm_upsert_contact` written={'contact': {'last_name': 'Щукин', 'first_name': 'Радислав', 'initials': 'Р.', 'name_latin': 'Shchukin Radislav', 'phone': '+79837849986', 'gender': 'M', 'address': {'city': 'Ижевск', 'street': 'Тополиная', 'house': '100', 'flat': '150'}}} → restored={'contact': {'last_name': 'ерохин', 'first_name': 'пётр', 'initials': 'Р.', 'name_latin': 'Erokhin Petr', 'phone': '+79037654321', 'gender': 'M', 'address': {'city': 'Ижевск', 'street': 'полевая', 'house': '2', 'flat': '150'}}}
- C′: `courier_book` {'address': {'locality': 'Ижевск', 'street': 'Полевая', 'building': '2', 'sflat': '150'}, 'contact': {'name': 'Ерохин Пётр', 'phone': '+79037654321'}, 'interval': {'from': '2026-09-04T10:00:00+04:00'…
- C′: `crm_upsert_contact` {'contact': {'last_name': 'Ерохин', 'first_name': 'Пётр', 'initials': 'П.', 'name_latin': 'Erokhin Petr', 'phone': '+79037654321', 'address': {'city': 'Ижевск', 'street': 'Полевая', 'house': '2', 'fl…
- FIELD `crm_upsert_contact.contact.initials` [derived/from_substitute → derived] C=`П.` I=`Р.` · значение выведено из ПОДМЕНЫ; восстановление недостижимо
- FIELD `crm_upsert_contact.contact.name_latin` [other/misderived → name_partial] C=`Erokhin Pyotr` I=`Erokhin Petr`
- REPLY I: Оформляю всё сразу! Всё оформлено! ✅ **Вызов курьера** (№ clm-1) - 📍 Ижевск, полевая 2 квартира 150 - 👤 ерохин пётр, 8-903-765-43-21 - 🕙 4 сентября 2026, с 10:00 до 14:00 Карточка клиента в CRM также создана/обновлена. Если нужно что-то ещё — готов помочь!

## correction-012|0 · correction · chat · L1 ≠ · L3 ≠ · C′≈C нет · причина: **partial-call**
- USER[1]: добрый день курьера на адрес добролюбова 50 квартира 193 стоп правильно добролюбова 22 квартира 193 это в можга это кузнецова ольга телефон 8-961-473-24-80
- USER[2]: в любой день с девяти до шести
- seen LOC `добролюбова 50 квартира 193` → `улица Берёзовая 51, кв. 25`
- seen LOC `добролюбова 22 квартира 193` → `улица Абрикосовая 71, кв. 178`
- seen NAME `кузнецова ольга` → `Панова Василиса`
- seen PHONE `8-961-473-24-80` → `+79364708792`
- C: `courier_book` {'address': {'locality': 'Можга', 'street': 'Добролюбова', 'building': '22', 'sflat': '193'}, 'contact': {'name': 'Кузнецова Ольга', 'phone': '+79614732480'}, 'interval': {'from': '2026-09-03T09:00:0…
- C: `crm_upsert_contact` {'contact': {'last_name': 'Кузнецова', 'first_name': 'Ольга', 'initials': 'О.', 'name_latin': 'Kuznetsova Olga', 'gender': 'F', 'phone': '+79614732480', 'address': {'city': 'Можга', 'street': 'Доброл…
- I: `courier_book` written={'address': {'locality': 'Можга', 'street': 'Абрикосовая', 'building': '71', 'sflat': '178'}, 'contact': {'name': 'Панова Василиса', 'phone': '+79364708792'}, 'interval': {'from': '2026-09-03T09:00:00+04:00', 'to': '2026-09-03T18:00:00+04:00'}} → restored={'address': {'locality': 'Можга', 'street': 'добролюбова', 'building': '22', 'sflat': '193'}, 'contact': {'name': 'кузнецова ольга', 'phone': '+79614732480'}, 'interval': {'from': '2026-09-03T09:00:00+04:00', 'to': '2026-09-03T18:00:00+04:00'}}
- C′: `courier_book` {'address': {'locality': 'Можга', 'street': 'Добролюбова', 'building': '22', 'sflat': '193'}, 'contact': {'name': 'Кузнецова Ольга', 'phone': '+79614732480'}, 'interval': {'from': '2026-09-03T09:00:0…
- FIELD `crm_upsert_contact.contact.address.city` [absent → absent:city] C=`Можга` I=``
- FIELD `crm_upsert_contact.contact.address.flat` [absent → absent:flat] C=`193` I=``
- FIELD `crm_upsert_contact.contact.address.house` [absent → absent:house] C=`22` I=``
- FIELD `crm_upsert_contact.contact.address.street` [absent → absent:street] C=`Добролюбова` I=``
- FIELD `crm_upsert_contact.contact.first_name` [absent → absent:first_name] C=`Ольга` I=``
- FIELD `crm_upsert_contact.contact.gender` [absent → absent:gender] C=`F` I=``
- FIELD `crm_upsert_contact.contact.initials` [absent → absent:initials] C=`О.` I=``
- FIELD `crm_upsert_contact.contact.last_name` [absent → absent:last_name] C=`Кузнецова` I=``
- FIELD `crm_upsert_contact.contact.name_latin` [absent → absent:name_latin] C=`Kuznetsova Olga` I=``
- FIELD `crm_upsert_contact.contact.phone` [absent → absent:phone] C=`+79614732480` I=``
- REPLY I: Оформляю на сегодня, 3 сентября, с 09:00 до 18:00! Готово! Курьер вызван. 🎉 **Детали заявки:** - 🆔 Номер заявки: **clm-1** - 📍 Адрес: г. Можга, добролюбова 22 квартира 193 - 👤 Получатель: кузнецова ольга, 8-961-473-24-80 - 🕘 Интервал: 3 сентября 2026, с 09:00 до 18:00 Если нужно что-то ещё — обраща…

## correction-012|1 · correction · chat · L1 = · L3 ≠ · C′≈C да · причина: **derived-only**
- USER[1]: добрый день курьера на адрес добролюбова 50 квартира 193 стоп правильно добролюбова 22 квартира 193 это в можга это кузнецова ольга телефон 8-961-473-24-80
- USER[2]: в любой день с девяти до шести
- seen LOC `добролюбова 50 квартира 193` → `улица Ольховая 17, кв. 156`
- seen LOC `добролюбова 22 квартира 193` → `улица Черёмуховая 26, кв. 121`
- seen NAME `кузнецова ольга` → `Устинова Ирина`
- seen PHONE `8-961-473-24-80` → `+79378491882`
- C: `courier_book` {'address': {'locality': 'Можга', 'street': 'Добролюбова', 'building': '22', 'sflat': '193'}, 'contact': {'name': 'Кузнецова Ольга', 'phone': '+79614732480'}, 'interval': {'from': '2026-09-03T09:00:0…
- C: `crm_upsert_contact` {'contact': {'last_name': 'Кузнецова', 'first_name': 'Ольга', 'initials': 'О.', 'name_latin': 'Kuznetsova Olga', 'phone': '+79614732480', 'gender': 'F', 'address': {'city': 'Можга', 'street': 'Доброл…
- I: `courier_book` written={'address': {'locality': 'Можга', 'street': 'Черёмуховая', 'building': '26', 'sflat': '121'}, 'contact': {'name': 'Устинова Ирина', 'phone': '+79378491882'}, 'interval': {'from': '2026-09-03T09:00:00+04:00', 'to': '2026-09-03T18:00:00+04:00'}} → restored={'address': {'locality': 'Можга', 'street': 'добролюбова', 'building': '22', 'sflat': '193'}, 'contact': {'name': 'кузнецова ольга', 'phone': '+79614732480'}, 'interval': {'from': '2026-09-03T09:00:00+04:00', 'to': '2026-09-03T18:00:00+04:00'}}
- I: `crm_upsert_contact` written={'contact': {'last_name': 'Устинова', 'first_name': 'Ирина', 'initials': 'И.', 'name_latin': 'Ustinova Irina', 'gender': 'F', 'phone': '+79378491882', 'address': {'city': 'Можга', 'street': 'Черёмуховая', 'house': '26', 'flat': '121'}}} → restored={'contact': {'last_name': 'кузнецова', 'first_name': 'ольга', 'initials': 'И.', 'name_latin': 'Kuznetsova Olga', 'gender': 'F', 'phone': '+79614732480', 'address': {'city': 'Можга', 'street': 'добролюбова', 'house': '22', 'flat': '193'}}}
- C′: `courier_book` {'address': {'locality': 'Можга', 'street': 'Добролюбова', 'building': '22', 'sflat': '193'}, 'contact': {'name': 'Кузнецова Ольга', 'phone': '+79614732480'}, 'interval': {'from': '2026-09-03T09:00:0…
- C′: `crm_upsert_contact` {'contact': {'last_name': 'Кузнецова', 'first_name': 'Ольга', 'initials': 'О.', 'name_latin': 'Kuznetsova Olga', 'phone': '+79614732480', 'gender': 'F', 'address': {'city': 'Можга', 'street': 'Доброл…
- FIELD `crm_upsert_contact.contact.initials` [derived/from_substitute → derived] C=`О.` I=`И.` · значение выведено из ПОДМЕНЫ; восстановление недостижимо
- REPLY I: Отлично, оформляю на сегодня, 3 сентября, с 09:00 до 18:00! Всё готово! ✅ **Курьер вызван** (заявка `clm-1`): - 📍 Можга, добролюбова 22 квартира 193 - 👤 кузнецова ольга, 8-961-473-24-80 - 🕘 Сегодня, 3 сентября, с 09:00 до 18:00 Карточка клиента в CRM также создана/обновлена. Если нужно что-то ещё —…

## correction-012|2 · correction · chat · L1 = · L3 ≠ · C′≈C да · причина: **derived-only**
- USER[1]: добрый день курьера на адрес добролюбова 50 квартира 193 стоп правильно добролюбова 22 квартира 193 это в можга это кузнецова ольга телефон 8-961-473-24-80
- USER[2]: в любой день с девяти до шести
- seen LOC `добролюбова 50 квартира 193` → `улица Берёзовая 90, кв. 171`
- seen LOC `добролюбова 22 квартира 193` → `улица Озёрная 16, кв. 239`
- seen NAME `кузнецова ольга` → `Гущина Тамара`
- seen PHONE `8-961-473-24-80` → `+79045245808`
- C: `courier_book` {'address': {'locality': 'Можга', 'street': 'Добролюбова', 'building': '22', 'sflat': '193'}, 'contact': {'name': 'Кузнецова Ольга', 'phone': '+79614732480'}, 'interval': {'from': '2026-09-03T09:00:0…
- C: `crm_upsert_contact` {'contact': {'last_name': 'Кузнецова', 'first_name': 'Ольга', 'gender': 'F', 'phone': '+79614732480', 'initials': 'О.', 'name_latin': 'Kuznetsova Olga', 'address': {'city': 'Можга', 'street': 'Доброл…
- I: `courier_book` written={'address': {'locality': 'Можга', 'street': 'Озёрная', 'building': '16', 'sflat': '239'}, 'contact': {'name': 'Гущина Тамара', 'phone': '+79045245808'}, 'interval': {'from': '2026-09-03T09:00:00+04:00', 'to': '2026-09-03T18:00:00+04:00'}} → restored={'address': {'locality': 'Можга', 'street': 'добролюбова', 'building': '22', 'sflat': '193'}, 'contact': {'name': 'кузнецова ольга', 'phone': '+79614732480'}, 'interval': {'from': '2026-09-03T09:00:00+04:00', 'to': '2026-09-03T18:00:00+04:00'}}
- I: `crm_upsert_contact` written={'contact': {'first_name': 'Тамара', 'last_name': 'Гущина', 'phone': '+79045245808', 'gender': 'F', 'initials': 'Т.', 'name_latin': 'Gushchina Tamara', 'address': {'city': 'Можга', 'street': 'Озёрная', 'house': '16', 'flat': '239'}}} → restored={'contact': {'first_name': 'ольга', 'last_name': 'кузнецова', 'phone': '+79614732480', 'gender': 'F', 'initials': 'Т.', 'name_latin': 'Kuznetsova Olga', 'address': {'city': 'Можга', 'street': 'добролюбова', 'house': '22', 'flat': '193'}}}
- C′: `courier_book` {'address': {'locality': 'Можга', 'street': 'Добролюбова', 'building': '22', 'sflat': '193'}, 'contact': {'name': 'Кузнецова Ольга', 'phone': '+79614732480'}, 'interval': {'from': '2026-09-03T09:00:0…
- C′: `crm_upsert_contact` {'contact': {'last_name': 'Кузнецова', 'first_name': 'Ольга', 'initials': 'О.', 'name_latin': 'Kuznetsova Olga', 'gender': 'F', 'phone': '+79614732480', 'address': {'city': 'Можга', 'street': 'Доброл…
- FIELD `crm_upsert_contact.contact.initials` [derived/from_substitute → derived] C=`О.` I=`Т.` · значение выведено из ПОДМЕНЫ; восстановление недостижимо
- REPLY I: Принято! Оформляю вызов курьера и карточку клиента. Всё оформлено! ✅ **Вызов курьера** (№ clm-1): - 📍 г. Можга, добролюбова 22 квартира 193 - 👤 кузнецова ольга, 8-961-473-24-80 - 🕘 Сегодня, 03.09.2026, с 09:00 до 18:00 **Карточка клиента** в CRM также создана/обновлена. Если что-то нужно изменить —…

## correction-013|0 · correction · sloppy · L1 ≠ · L3 ≠ · C′≈C нет · причина: **other**
- USER[1]: добрый курьера на мяаковского 11 квартира 197 ой нет правильно маяковского 163 квартира 197 это в сарапул это миллер валерия телефлн 89502880554
- USER[2]: в любой день с девяти до шетси
- **LEAK** LOC `мяаковского 11 квартира 197` — модель видела настоящее значение
- seen LOC `маяковского 163 квартира 197` → `улица Речная 43, кв. 181`
- seen NAME `миллер валерия` → `Котов Николай`
- seen PHONE `89502880554` → `+79760226472`
- C: `courier_book` {'address': {'locality': 'Сарапул', 'street': 'Маяковского', 'building': '163', 'sflat': '197'}, 'contact': {'name': 'Валерия Миллер', 'phone': '+79502880554'}, 'interval': {'from': '2026-09-03T09:00…
- C: `crm_upsert_contact` {'contact': {'last_name': 'Миллер', 'first_name': 'Валерия', 'initials': 'В.', 'name_latin': 'Miller Valeria', 'gender': 'F', 'phone': '+79502880554', 'address': {'city': 'Сарапул', 'street': 'Маяков…
- I: `crm_upsert_contact` written={'contact': {'last_name': 'Котов', 'first_name': 'Николай', 'initials': 'Н.', 'name_latin': 'Kotov Nikolay', 'gender': 'M', 'phone': '+79760226472', 'address': {'city': 'Сарапул', 'street': 'Речная', 'house': '43', 'flat': '181'}}} → restored={'contact': {'last_name': 'миллер', 'first_name': 'валерия', 'initials': 'Н.', 'name_latin': 'Miller Valeriya', 'gender': 'M', 'phone': '+79502880554', 'address': {'city': 'Сарапул', 'street': 'маяковского', 'house': '163', 'flat': '197'}}}
- I: `courier_book` written={'address': {'locality': 'Сарапул', 'street': 'Речная', 'building': '43', 'sflat': '181'}, 'contact': {'name': 'Котов Николай', 'phone': '+79760226472'}, 'interval': {'from': '2026-09-03T09:00:00+04:00', 'to': '2026-09-03T18:00:00+04:00'}} → restored={'address': {'locality': 'Сарапул', 'street': 'маяковского', 'building': '163', 'sflat': '197'}, 'contact': {'name': 'миллер валерия', 'phone': '+79502880554'}, 'interval': {'from': '2026-09-03T09:00:00+04:00', 'to': '2026-09-03T18:00:00+04:00'}}
- C′: `crm_upsert_contact` {'contact': {'last_name': 'Миллер', 'first_name': 'Валерия', 'initials': 'В.', 'name_latin': 'Miller Valeria', 'gender': 'F', 'phone': '+79502880554', 'address': {'city': 'Сарапул', 'street': 'Маяков…
- C′: `courier_book` {'address': {'locality': 'Сарапул', 'street': 'Маяковского', 'building': '163', 'sflat': '197'}, 'contact': {'name': 'Миллер Валерия', 'phone': '+79502880554'}, 'interval': {'from': '2026-09-03T09:00…
- FIELD `courier_book.contact.name` [control_erred/i3 → control_erred] C=`Валерия Миллер` I=`миллер валерия` · контроль ошибся; шлюз восстановил эталон корпуса
- FIELD `crm_upsert_contact.contact.gender` [derived/from_substitute → derived] C=`F` I=`M` · значение выведено из ПОДМЕНЫ; восстановление недостижимо
- FIELD `crm_upsert_contact.contact.initials` [derived/from_substitute → derived] C=`В.` I=`Н.` · значение выведено из ПОДМЕНЫ; восстановление недостижимо
- FIELD `crm_upsert_contact.contact.name_latin` [other/misderived → name_partial] C=`Miller Valeria` I=`Miller Valeriya`
- REPLY I: Оформляю всё сразу! Всё готово! ✅ **Вызов курьера оформлен:** - 📍 Сарапул, маяковского 163 квартира 197 - 👤 миллер валерия, 89502880554 - 🕐 Сегодня, 03.09.2026, с 09:00 до 18:00 - 🔖 Номер заявки: **clm-1** Карточка клиента в CRM также создана/обновлена. Если нужно что-то ещё — обращайтесь!

## correction-013|1 · correction · sloppy · L1 ≠ · L3 ≠ · C′≈C нет · причина: **other**
- USER[1]: добрый курьера на мяаковского 11 квартира 197 ой нет правильно маяковского 163 квартира 197 это в сарапул это миллер валерия телефлн 89502880554
- USER[2]: в любой день с девяти до шетси
- **LEAK** LOC `мяаковского 11 квартира 197` — модель видела настоящее значение
- seen LOC `маяковского 163 квартира 197` → `улица Ивовая 106, кв. 52`
- seen NAME `миллер валерия` → `Фомин Борис`
- seen PHONE `89502880554` → `+79111485230`
- C: `crm_upsert_contact` {'contact': {'last_name': 'Миллер', 'first_name': 'Валерия', 'initials': 'В.', 'name_latin': 'Miller Valeria', 'gender': 'F', 'phone': '+79502880554', 'address': {'city': 'Сарапул', 'street': 'Маяков…
- C: `courier_book` {'address': {'locality': 'Сарапул', 'street': 'Маяковского', 'building': '163', 'sflat': '197'}, 'contact': {'name': 'Миллер Валерия', 'phone': '+79502880554'}, 'interval': {'from': '2026-09-03T09:00…
- I: `courier_book` written={'address': {'locality': 'Сарапул', 'street': 'Ивовая', 'building': '106', 'sflat': '52'}, 'contact': {'name': 'Фомин Борис', 'phone': '+79111485230'}, 'interval': {'from': '2026-09-03T09:00:00+04:00', 'to': '2026-09-03T18:00:00+04:00'}} → restored={'address': {'locality': 'Сарапул', 'street': 'маяковского', 'building': '163', 'sflat': '197'}, 'contact': {'name': 'миллер валерия', 'phone': '+79502880554'}, 'interval': {'from': '2026-09-03T09:00:00+04:00', 'to': '2026-09-03T18:00:00+04:00'}}
- I: `crm_upsert_contact` written={'contact': {'first_name': 'Борис', 'last_name': 'Фомин', 'phone': '+79111485230', 'initials': 'Б.', 'name_latin': 'Fomin Boris', 'address': {'city': 'Сарапул', 'street': 'Ивовая', 'house': '106', 'flat': '52'}}} → restored={'contact': {'first_name': 'валерия', 'last_name': 'миллер', 'phone': '+79502880554', 'initials': 'Б.', 'name_latin': 'Miller Valeriia', 'address': {'city': 'Сарапул', 'street': 'маяковского', 'house': '163', 'flat': '197'}}}
- C′: `courier_book` {'address': {'locality': 'Сарапул', 'street': 'Маяковского', 'building': '163', 'sflat': '197'}, 'contact': {'name': 'Миллер Валерия', 'phone': '+79502880554'}, 'interval': {'from': '2026-09-03T09:00…
- C′: `crm_upsert_contact` {'contact': {'first_name': 'Валерия', 'last_name': 'Миллер', 'phone': '+79502880554', 'initials': 'В.', 'name_latin': 'Miller Valeria', 'address': {'city': 'Сарапул', 'street': 'Маяковского', 'house'…
- FIELD `crm_upsert_contact.contact.gender` [absent → absent:gender] C=`F` I=``
- FIELD `crm_upsert_contact.contact.initials` [derived/from_substitute → derived] C=`В.` I=`Б.` · значение выведено из ПОДМЕНЫ; восстановление недостижимо
- FIELD `crm_upsert_contact.contact.name_latin` [other/misderived → name_partial] C=`Miller Valeria` I=`Miller Valeriia`
- REPLY I: Оформляю курьера и карточку клиента одновременно! Всё готово! Вот что сделано: **🚚 Курьер вызван** (заявка `clm-1`) - Адрес: г. Сарапул, маяковского 163 квартира 197 - Получатель: миллер валерия, 89502880554 - Интервал: сегодня, 03.09.2026, с 09:00 до 18:00 **👤 Карточка клиента** создана/обновлена …

## correction-013|2 · correction · sloppy · L1 ≠ · L3 ≠ · C′≈C нет · причина: **other**
- USER[1]: добрый курьера на мяаковского 11 квартира 197 ой нет правильно маяковского 163 квартира 197 это в сарапул это миллер валерия телефлн 89502880554
- USER[2]: в любой день с девяти до шетси
- **LEAK** LOC `мяаковского 11 квартира 197` — модель видела настоящее значение
- seen LOC `маяковского 163 квартира 197` → `улица Осиновая 195, кв. 163`
- seen NAME `миллер валерия` → `Рыбаков Эдуард`
- seen PHONE `89502880554` → `+79360214218`
- C: `crm_upsert_contact` {'contact': {'last_name': 'Миллер', 'first_name': 'Валерия', 'initials': 'В.', 'name_latin': 'Miller Valeria', 'gender': 'F', 'phone': '+79502880554', 'address': {'city': 'Сарапул', 'street': 'Маяков…
- C: `courier_book` {'address': {'locality': 'Сарапул', 'street': 'Маяковского', 'building': '163', 'sflat': '197'}, 'contact': {'name': 'Миллер Валерия', 'phone': '+79502880554'}, 'interval': {'from': '2026-09-03T09:00…
- I: `courier_book` written={'address': {'locality': 'Сарапул', 'street': 'Осиновая', 'building': '195', 'sflat': '163'}, 'contact': {'name': 'Рыбаков Эдуард', 'phone': '+79360214218'}, 'interval': {'from': '2026-09-03T09:00:00+04:00', 'to': '2026-09-03T18:00:00+04:00'}} → restored={'address': {'locality': 'Сарапул', 'street': 'маяковского', 'building': '163', 'sflat': '197'}, 'contact': {'name': 'миллер валерия', 'phone': '+79502880554'}, 'interval': {'from': '2026-09-03T09:00:00+04:00', 'to': '2026-09-03T18:00:00+04:00'}}
- I: `crm_upsert_contact` written={'contact': {'last_name': 'Рыбаков', 'first_name': 'Эдуард', 'initials': 'Э.', 'name_latin': 'Rybakov Eduard', 'gender': 'M', 'phone': '+79360214218', 'address': {'city': 'Сарапул', 'street': 'Осиновая', 'house': '195', 'flat': '163'}}} → restored={'contact': {'last_name': 'миллер', 'first_name': 'валерия', 'initials': 'Э.', 'name_latin': 'Miller Valeriia', 'gender': 'M', 'phone': '+79502880554', 'address': {'city': 'Сарапул', 'street': 'маяковского', 'house': '163', 'flat': '197'}}}
- C′: `courier_book` {'address': {'locality': 'Сарапул', 'street': 'Маяковского', 'building': '163', 'sflat': '197'}, 'contact': {'name': 'Миллер Валерия', 'phone': '+79502880554'}, 'interval': {'from': '2026-09-03T09:00…
- C′: `crm_upsert_contact` {'contact': {'last_name': 'Миллер', 'first_name': 'Валерия', 'initials': 'В.', 'name_latin': 'Miller Valeria', 'gender': 'F', 'phone': '+79502880554', 'address': {'city': 'Сарапул', 'street': 'Маяков…
- FIELD `crm_upsert_contact.contact.gender` [derived/from_substitute → derived] C=`F` I=`M` · значение выведено из ПОДМЕНЫ; восстановление недостижимо
- FIELD `crm_upsert_contact.contact.initials` [derived/from_substitute → derived] C=`В.` I=`Э.` · значение выведено из ПОДМЕНЫ; восстановление недостижимо
- FIELD `crm_upsert_contact.contact.name_latin` [other/misderived → name_partial] C=`Miller Valeria` I=`Miller Valeriia`
- REPLY I: Принято! Оформляю курьера и карточку клиента одновременно. Всё готово! ✅ **Курьер вызван** (заявка `clm-1`) - 📍 Сарапул, маяковского 163 квартира 197 - 👤 миллер валерия, 89502880554 - 🕘 Сегодня, 03.09.2026, с 09:00 до 18:00 **Карточка клиента** в CRM также создана/обновлена. Если что-то нужно измен…

## correction-016|0 · correction · chat · L1 = · L3 ≠ · C′≈C нет · причина: **other**
- USER[1]: курьера на адрес химзаводская 31 кв 170 стоп правильно химзаводская 3кв170 это в колпино это морозов леонид телефон 89827992458
- USER[2]: в четверг после обеда
- seen LOC `химзаводская 31 кв 170` → `улица Полевая 144, кв. 35`
- **LEAK** LOC `химзаводская 3кв170` — модель видела настоящее значение
- seen NAME `морозов леонид` → `Цветков Никита`
- seen PHONE `89827992458` → `+79226471222`
- C: `courier_book` {'address': {'locality': 'Колпино', 'street': 'Химзаводская', 'building': '3', 'sflat': '170'}, 'contact': {'name': 'Морозов Леонид', 'phone': '+79827992458'}, 'interval': {'from': '2026-09-03T13:00:…
- I: `courier_book` written={'address': {'locality': 'Колпино', 'street': 'Химзаводская', 'building': '3', 'sflat': '170'}, 'contact': {'name': 'Цветков Никита', 'phone': '+79226471222'}, 'interval': {'from': '2026-09-03T14:00:00+03:00', 'to': '2026-09-03T18:00:00+03:00'}} → restored={'address': {'locality': 'Колпино', 'street': 'Химзаводская', 'building': '3', 'sflat': '170'}, 'contact': {'name': 'морозов леонид', 'phone': '+79827992458'}, 'interval': {'from': '2026-09-03T14:00:00+03:00', 'to': '2026-09-03T18:00:00+03:00'}}
- C′: `courier_book` {'address': {'locality': 'Колпино', 'street': 'Химзаводская', 'building': '3', 'sflat': '170'}, 'contact': {'name': 'Морозов Леонид', 'phone': '+79827992458'}, 'interval': {'from': '2026-09-03T13:00:…
- C′: `crm_upsert_contact` {'contact': {'last_name': 'Морозов', 'first_name': 'Леонид', 'initials': 'Л.', 'name_latin': 'Morozov Leonid', 'phone': '+79827992458', 'gender': 'M', 'address': {'city': 'Колпино', 'street': 'Химзав…
- REPLY I: Сегодня четверг, 3 сентября — оформляю на сегодня после обеда (14:00–18:00). Вызываю курьера! Готово! Курьер вызван. 🎉 **Детали заявки:** - 📍 Колпино, ул. Химзаводская, д. 3, кв. 170 - 👤 морозов леонид, 89827992458 - 🕒 Сегодня, 3 сентября, с **14:00 до 18:00** - 🆔 Номер заявки: **clm-1** Если нужно…

## correction-016|1 · correction · chat · L1 ≠ · L3 ≠ · C′≈C нет · причина: **partial-call**
- USER[1]: курьера на адрес химзаводская 31 кв 170 стоп правильно химзаводская 3кв170 это в колпино это морозов леонид телефон 89827992458
- USER[2]: в четверг после обеда
- seen LOC `химзаводская 31 кв 170` → `улица Сосновая 98, кв. 148`
- **LEAK** LOC `химзаводская 3кв170` — модель видела настоящее значение
- seen NAME `морозов леонид` → `Чижов Радислав`
- seen PHONE `89827992458` → `+79492216935`
- C: `courier_book` {'address': {'locality': 'Колпино', 'street': 'Химзаводская', 'building': '3', 'sflat': '170'}, 'contact': {'name': 'Морозов Леонид', 'phone': '+79827992458'}, 'interval': {'from': '2026-09-03T13:00:…
- C: `crm_upsert_contact` {'contact': {'last_name': 'Морозов', 'first_name': 'Леонид', 'initials': 'Л.', 'name_latin': 'Morozov Leonid', 'gender': 'M', 'phone': '+79827992458', 'address': {'city': 'Колпино', 'street': 'Химзав…
- I: `courier_book` written={'address': {'locality': 'Колпино', 'street': 'Химзаводская', 'building': '3', 'sflat': '170'}, 'contact': {'name': 'Чижов Радислав', 'phone': '+79492216935'}, 'interval': {'from': '2026-09-03T14:00:00+03:00', 'to': '2026-09-03T18:00:00+03:00'}} → restored={'address': {'locality': 'Колпино', 'street': 'Химзаводская', 'building': '3', 'sflat': '170'}, 'contact': {'name': 'морозов леонид', 'phone': '+79827992458'}, 'interval': {'from': '2026-09-03T14:00:00+03:00', 'to': '2026-09-03T18:00:00+03:00'}}
- C′: `courier_book` {'address': {'locality': 'Колпино', 'street': 'Химзаводская', 'building': '3', 'sflat': '170'}, 'contact': {'name': 'Морозов Леонид', 'phone': '+79827992458'}, 'interval': {'from': '2026-09-03T13:00:…
- C′: `crm_upsert_contact` {'contact': {'last_name': 'Морозов', 'first_name': 'Леонид', 'initials': 'Л.', 'name_latin': 'Morozov Leonid', 'phone': '+79827992458', 'gender': 'M', 'address': {'city': 'Колпино', 'street': 'Химзав…
- C′: `notify_sms` {'number': '+79827992458', 'sign': 'Dostavka', 'text': 'Здравствуйте, Леонид! Курьер приедет сегодня, 3 сентября, с 13:00 до 18:00 по адресу: г. Колпино, ул. Химзаводская, д. 3, кв. 170. По вопросам …
- FIELD `crm_upsert_contact.contact.address.city` [absent → absent:city] C=`Колпино` I=``
- FIELD `crm_upsert_contact.contact.address.flat` [absent → absent:flat] C=`170` I=``
- FIELD `crm_upsert_contact.contact.address.house` [absent → absent:house] C=`3` I=``
- FIELD `crm_upsert_contact.contact.address.street` [absent → absent:street] C=`Химзаводская` I=``
- FIELD `crm_upsert_contact.contact.first_name` [absent → absent:first_name] C=`Леонид` I=``
- FIELD `crm_upsert_contact.contact.gender` [absent → absent:gender] C=`M` I=``
- FIELD `crm_upsert_contact.contact.initials` [absent → absent:initials] C=`Л.` I=``
- FIELD `crm_upsert_contact.contact.last_name` [absent → absent:last_name] C=`Морозов` I=``
- FIELD `crm_upsert_contact.contact.name_latin` [absent → absent:name_latin] C=`Morozov Leonid` I=``
- FIELD `crm_upsert_contact.contact.phone` [absent → absent:phone] C=`+79827992458` I=``
- REPLY I: Сегодня четверг, значит оформляю **сегодня, 3 сентября, с 14:00 до 18:00**. Вызываю! Готово! Курьер оформлен ✅ **Детали вызова:** - 📍 Колпино, Химзаводская, 3, кв. 170 - 👤 морозов леонид, 89827992458 - 🕑 Сегодня, 3 сентября, с 14:00 до 18:00 - 🆔 Заявка: **clm-1** Если нужно что-то изменить или доба…

## correction-016|2 · correction · chat · L1 ≠ · L3 ≠ · C′≈C нет · причина: **partial-call**
- USER[1]: курьера на адрес химзаводская 31 кв 170 стоп правильно химзаводская 3кв170 это в колпино это морозов леонид телефон 89827992458
- USER[2]: в четверг после обеда
- seen LOC `химзаводская 31 кв 170` → `улица Мятная 152, кв. 8`
- **LEAK** LOC `химзаводская 3кв170` — модель видела настоящее значение
- seen NAME `морозов леонид` → `Сорокин Алексей`
- seen PHONE `89827992458` → `+79387095452`
- C: `crm_upsert_contact` {'contact': {'last_name': 'Морозов', 'first_name': 'Леонид', 'initials': 'Л.', 'name_latin': 'Morozov Leonid', 'phone': '+79827992458', 'address': {'city': 'Колпино', 'street': 'Химзаводская', 'house…
- C: `courier_book` {'address': {'locality': 'Колпино', 'street': 'Химзаводская', 'building': '3', 'sflat': '170'}, 'contact': {'name': 'Морозов Леонид', 'phone': '+79827992458'}, 'interval': {'from': '2026-09-03T14:00:…
- I: `courier_book` written={'address': {'locality': 'Колпино', 'street': 'Химзаводская', 'building': '3', 'sflat': '170'}, 'contact': {'name': 'Сорокин Алексей', 'phone': '+79387095452'}, 'interval': {'from': '2026-09-10T14:00:00+03:00', 'to': '2026-09-10T18:00:00+03:00'}} → restored={'address': {'locality': 'Колпино', 'street': 'Химзаводская', 'building': '3', 'sflat': '170'}, 'contact': {'name': 'морозов леонид', 'phone': '+79827992458'}, 'interval': {'from': '2026-09-10T14:00:00+03:00', 'to': '2026-09-10T18:00:00+03:00'}}
- C′: `courier_book` {'address': {'locality': 'Колпино', 'street': 'Химзаводская', 'building': '3', 'sflat': '170'}, 'contact': {'name': 'Морозов Леонид', 'phone': '+79827992458'}, 'interval': {'from': '2026-09-03T13:00:…
- C′: `crm_upsert_contact` {'contact': {'last_name': 'Морозов', 'first_name': 'Леонид', 'initials': 'Л.', 'name_latin': 'Morozov Leonid', 'phone': '+79827992458', 'address': {'city': 'Колпино', 'street': 'Химзаводская', 'house…
- FIELD `crm_upsert_contact.contact.address.city` [absent → absent:city] C=`Колпино` I=``
- FIELD `crm_upsert_contact.contact.address.flat` [absent → absent:flat] C=`170` I=``
- FIELD `crm_upsert_contact.contact.address.house` [absent → absent:house] C=`3` I=``
- FIELD `crm_upsert_contact.contact.address.street` [absent → absent:street] C=`Химзаводская` I=``
- FIELD `crm_upsert_contact.contact.first_name` [absent → absent:first_name] C=`Леонид` I=``
- FIELD `crm_upsert_contact.contact.initials` [absent → absent:initials] C=`Л.` I=``
- FIELD `crm_upsert_contact.contact.last_name` [absent → absent:last_name] C=`Морозов` I=``
- FIELD `crm_upsert_contact.contact.name_latin` [absent → absent:name_latin] C=`Morozov Leonid` I=``
- FIELD `crm_upsert_contact.contact.phone` [absent → absent:phone] C=`+79827992458` I=``
- REPLY I: Оформляю на **четверг, 10 сентября, с 14:00 до 18:00**! Готово! ✅ **Курьер оформлен:** - 📍 Колпино, ул. Химзаводская, д. 3, кв. 170 - 👤 морозов леонид, 89827992458 - 🗓 Четверг, 10 сентября — с 14:00 до 18:00 - 🔖 Номер заявки: **clm-1** Если нужно что-то изменить — скажите!

## correction-017|0 · correction · voice_itn · L1 = · L3 ≠ · C′≈C нет · причина: **other**
- USER[1]: добрый день курьера на барышникова 34 квартира 164 нет не так правильно барышникова 6 квартира 164 это в глазов это фёдорова юлия телефон 8-960-708-39-07
- USER[2]: завтра с десяти до двух
- seen LOC `барышникова 34 квартира 164` → `улица Ивовая 198, кв. 72`
- seen LOC `барышникова 6 квартира 164` → `улица Черёмуховая 27, кв. 175`
- seen NAME `фёдорова юлия` → `Цветкова Виктория`
- seen PHONE `8-960-708-39-07` → `+79868272472`
- C: `courier_book` {'address': {'locality': 'Глазов', 'street': 'Барышникова', 'building': '6', 'sflat': '164'}, 'contact': {'name': 'Фёдорова Юлия', 'phone': '+79607083907'}, 'interval': {'from': '2026-09-04T10:00:00+…
- C: `crm_upsert_contact` {'contact': {'last_name': 'Фёдорова', 'first_name': 'Юлия', 'initials': 'Ю.', 'name_latin': 'Fedorova Yulia', 'phone': '+79607083907', 'gender': 'F', 'address': {'city': 'Глазов', 'street': 'Барышник…
- I: `courier_book` written={'address': {'locality': 'Глазов', 'street': 'Черёмуховая', 'building': '27', 'sflat': '175'}, 'contact': {'name': 'Цветкова Виктория', 'phone': '+79868272472'}, 'interval': {'from': '2026-09-04T10:00:00+04:00', 'to': '2026-09-04T14:00:00+04:00'}} → restored={'address': {'locality': 'Глазов', 'street': 'барышникова', 'building': '6', 'sflat': '164'}, 'contact': {'name': 'фёдорова юлия', 'phone': '+79607083907'}, 'interval': {'from': '2026-09-04T10:00:00+04:00', 'to': '2026-09-04T14:00:00+04:00'}}
- I: `crm_upsert_contact` written={'contact': {'last_name': 'Цветкова', 'first_name': 'Виктория', 'gender': 'F', 'phone': '+79868272472', 'initials': 'В.', 'name_latin': 'Tsvetkova Viktoria', 'address': {'city': 'Глазов', 'street': 'Черёмуховая', 'house': '27', 'flat': '175'}}} → restored={'contact': {'last_name': 'фёдорова', 'first_name': 'юлия', 'gender': 'F', 'phone': '+79607083907', 'initials': 'В.', 'name_latin': 'Fedorova Viktoria', 'address': {'city': 'Глазов', 'street': 'барышникова', 'house': '6', 'flat': '164'}}}
- C′: `courier_book` {'address': {'locality': 'Глазов', 'street': 'Барышникова', 'building': '6', 'sflat': '164'}, 'contact': {'name': 'Фёдорова Юлия', 'phone': '+79607083907'}, 'interval': {'from': '2026-09-04T10:00:00+…
- FIELD `crm_upsert_contact.contact.initials` [derived/from_substitute → derived] C=`Ю.` I=`В.` · значение выведено из ПОДМЕНЫ; восстановление недостижимо
- FIELD `crm_upsert_contact.contact.name_latin` [other/misderived → name_partial] C=`Fedorova Yulia` I=`Fedorova Viktoria`
- REPLY I: Оформляю всё сразу! Всё готово! Вот итог: **🚚 Курьер вызван** (заявка `clm-1`) - **Адрес:** г. Глазов, барышникова 6 квартира 164 - **Получатель:** фёдорова юлия, 8-960-708-39-07 - **Дата и время:** 4 сентября 2026, с 10:00 до 14:00 **👤 Карточка клиента** в CRM создана/обновлена. Если нужно что-то …

## correction-017|1 · correction · voice_itn · L1 = · L3 ≠ · C′≈C нет · причина: **other**
- USER[1]: добрый день курьера на барышникова 34 квартира 164 нет не так правильно барышникова 6 квартира 164 это в глазов это фёдорова юлия телефон 8-960-708-39-07
- USER[2]: завтра с десяти до двух
- seen LOC `барышникова 34 квартира 164` → `улица Мятная 61, кв. 68`
- seen LOC `барышникова 6 квартира 164` → `улица Барбарисовая 71, кв. 127`
- seen NAME `фёдорова юлия` → `Панова Злата`
- seen PHONE `8-960-708-39-07` → `+79953038716`
- C: `courier_book` {'address': {'locality': 'Глазов', 'street': 'Барышникова', 'building': '6', 'sflat': '164'}, 'contact': {'name': 'Юлия Фёдорова', 'phone': '+79607083907'}, 'interval': {'from': '2026-09-04T10:00:00+…
- C: `crm_upsert_contact` {'contact': {'last_name': 'Фёдорова', 'first_name': 'Юлия', 'gender': 'F', 'phone': '+79607083907', 'initials': 'Ю.', 'name_latin': 'Fedorova Yulia', 'address': {'city': 'Глазов', 'street': 'Барышник…
- I: `courier_book` written={'address': {'locality': 'Глазов', 'street': 'Барбарисовая', 'building': '71', 'sflat': '127'}, 'contact': {'name': 'Панова Злата', 'phone': '+79953038716'}, 'interval': {'from': '2026-09-04T10:00:00+04:00', 'to': '2026-09-04T14:00:00+04:00'}} → restored={'address': {'locality': 'Глазов', 'street': 'барышникова', 'building': '6', 'sflat': '164'}, 'contact': {'name': 'фёдорова юлия', 'phone': '+79607083907'}, 'interval': {'from': '2026-09-04T10:00:00+04:00', 'to': '2026-09-04T14:00:00+04:00'}}
- I: `crm_upsert_contact` written={'contact': {'last_name': 'Панова', 'first_name': 'Злата', 'initials': 'З.', 'name_latin': 'Panova Zlata', 'phone': '+79953038716', 'address': {'city': 'Глазов', 'street': 'Барбарисовая', 'house': '71', 'flat': '127'}}} → restored={'contact': {'last_name': 'фёдорова', 'first_name': 'юлия', 'initials': 'З.', 'name_latin': 'Fedorova Iuliia', 'phone': '+79607083907', 'address': {'city': 'Глазов', 'street': 'барышникова', 'house': '6', 'flat': '164'}}}
- C′: `courier_book` {'address': {'locality': 'Глазов', 'street': 'Барышникова', 'building': '6', 'sflat': '164'}, 'contact': {'name': 'Фёдорова Юлия', 'phone': '+79607083907'}, 'interval': {'from': '2026-09-04T10:00:00+…
- C′: `crm_upsert_contact` {'contact': {'last_name': 'Фёдорова', 'first_name': 'Юлия', 'phone': '+79607083907', 'gender': 'F', 'initials': 'Ю.', 'name_latin': 'Fedorova Yulia', 'address': {'city': 'Глазов', 'street': 'Барышник…
- FIELD `courier_book.contact.name` [control_erred/i3 → control_erred] C=`Юлия Фёдорова` I=`фёдорова юлия` · контроль ошибся; шлюз восстановил эталон корпуса
- FIELD `crm_upsert_contact.contact.gender` [absent → absent:gender] C=`F` I=``
- FIELD `crm_upsert_contact.contact.initials` [derived/from_substitute → derived] C=`Ю.` I=`З.` · значение выведено из ПОДМЕНЫ; восстановление недостижимо
- FIELD `crm_upsert_contact.contact.name_latin` [other/misderived → name_partial] C=`Fedorova Yulia` I=`Fedorova Iuliia`
- REPLY I: Оформляю всё сразу! Всё готово! ✅ **Курьер вызван** (№ clm-1) - 📍 Глазов, барышникова 6 квартира 164 - 👤 фёдорова юлия, 8-960-708-39-07 - 🕐 4 сентября 2026, с 10:00 до 14:00 Карточка клиента в CRM также создана/обновлена. Если нужно что-то ещё — обращайтесь!

## correction-017|2 · correction · voice_itn · L1 ≠ · L3 ≠ · C′≈C да · причина: **other**
- USER[1]: добрый день курьера на барышникова 34 квартира 164 нет не так правильно барышникова 6 квартира 164 это в глазов это фёдорова юлия телефон 8-960-708-39-07
- USER[2]: завтра с десяти до двух
- seen LOC `барышникова 34 квартира 164` → `улица Каштановая 177, кв. 208`
- seen LOC `барышникова 6 квартира 164` → `улица Полевая 100, кв. 149`
- seen NAME `фёдорова юлия` → `Бирюкова Прасковья`
- seen PHONE `8-960-708-39-07` → `+79944609875`
- C: `courier_book` {'address': {'locality': 'Глазов', 'street': 'Барышникова', 'building': '6', 'sflat': '164'}, 'contact': {'name': 'Фёдорова Юлия', 'phone': '+79607083907'}, 'interval': {'from': '2026-09-04T10:00:00+…
- C: `crm_upsert_contact` {'contact': {'last_name': 'Фёдорова', 'first_name': 'Юлия', 'initials': 'Ю.', 'name_latin': 'Fedorova Yulia', 'gender': 'F', 'phone': '+79607083907', 'address': {'city': 'Глазов', 'street': 'Барышник…
- I: `crm_upsert_contact` written={'contact': {'last_name': 'Бирюкова', 'first_name': 'Прасковья', 'initials': 'П.', 'name_latin': 'Biryukova Praskovya', 'gender': 'F', 'phone': '+79944609875', 'address': {'city': 'Глазов', 'street': 'Полевая', 'house': '100', 'flat': '149'}}} → restored={'contact': {'last_name': 'фёдорова', 'first_name': 'юлия', 'initials': 'П.', 'name_latin': 'Fyodorova Yuliya', 'gender': 'F', 'phone': '+79607083907', 'address': {'city': 'Глазов', 'street': 'барышникова', 'house': '6', 'flat': '164'}}}
- I: `courier_book` written={'address': {'locality': 'Глазов', 'street': 'Полевая', 'building': '100', 'sflat': '149'}, 'contact': {'name': 'Бирюкова Прасковья', 'phone': '+79944609875'}, 'interval': {'from': '2026-09-04T10:00:00+04:00', 'to': '2026-09-04T14:00:00+04:00'}} → restored={'address': {'locality': 'Глазов', 'street': 'барышникова', 'building': '6', 'sflat': '164'}, 'contact': {'name': 'фёдорова юлия', 'phone': '+79607083907'}, 'interval': {'from': '2026-09-04T10:00:00+04:00', 'to': '2026-09-04T14:00:00+04:00'}}
- C′: `courier_book` {'address': {'locality': 'Глазов', 'street': 'Барышникова', 'building': '6', 'sflat': '164'}, 'contact': {'name': 'Фёдорова Юлия', 'phone': '+79607083907'}, 'interval': {'from': '2026-09-04T10:00:00+…
- C′: `crm_upsert_contact` {'contact': {'first_name': 'Юлия', 'last_name': 'Фёдорова', 'phone': '+79607083907', 'gender': 'F', 'initials': 'Ю.', 'name_latin': 'Fedorova Yulia', 'address': {'city': 'Глазов', 'street': 'Барышник…
- FIELD `crm_upsert_contact.contact.initials` [derived/from_substitute → derived] C=`Ю.` I=`П.` · значение выведено из ПОДМЕНЫ; восстановление недостижимо
- FIELD `crm_upsert_contact.contact.name_latin` [other/misderived → name_lemma] C=`Fedorova Yulia` I=`Fyodorova Yuliya`
- REPLY I: Отлично, оформляю всё одновременно — карточку клиента и вызов курьера! Всё готово! Вот итог: - **Карточка клиента** — создана (фёдорова юлия, 8-960-708-39-07) - **Курьер вызван** — завтра, **4 сентября с 10:00 до 14:00** - 📍 Глазов, барышникова 6 квартира 164 - Номер заявки: **clm-1** Если нужно чт…

## correction-018|0 · correction · voice_raw · L1 ≠ · L3 ≠ · C′≈C нет · причина: **Б9-span**
- USER[1]: добрый день курьера на адрес кирочная двадцать пять квартира сто пятьдесят ой нет правильно кирочная сто семьдесят семь квартира сто пятьдесят это в воткинск это захаров владислав телефон восем девятьсот двадцать пяять семест двадцать триста четырнадцать пяять
- USER[2]: в любой день с девяти до шести
- seen LOC `кирочная двадцать пять квартира сто пятьдесят` → `улица Кедровая 27, кв. 27`
- seen LOC `кирочная сто семьдесят семь квартира сто пятьдесят` → `улица Каштановая 192, кв. 165`
- seen NAME `захаров владислав` → `Беляев Матвей`
- **LEAK** PHONE `восем девятьсот двадцать пяять семест двадцать триста четырнадцать пяять` — модель видела настоящее значение
- C: `courier_book` {'address': {'locality': 'Воткинск', 'street': 'Кирочная', 'building': '177', 'sflat': '150'}, 'contact': {'name': 'Захаров Владислав', 'phone': '+79257203145'}, 'interval': {'from': '2026-09-03T09:0…
- C: `crm_upsert_contact` {'contact': {'last_name': 'Захаров', 'first_name': 'Владислав', 'initials': 'В.', 'name_latin': 'Zakharov Vladislav', 'gender': 'M', 'phone': '+79257203145', 'address': {'city': 'Воткинск', 'street':…
- I: — (без вызовов)
- C′: — (без вызовов)
- FIELD `courier_book.address.building` [absent → absent:building] C=`177` I=``
- FIELD `courier_book.address.locality` [absent → absent:locality] C=`Воткинск` I=``
- FIELD `courier_book.address.sflat` [absent → absent:sflat] C=`150` I=``
- FIELD `courier_book.address.street` [absent → absent:street] C=`Кирочная` I=``
- FIELD `courier_book.contact.name` [absent → absent:name] C=`Захаров Владислав` I=``
- FIELD `courier_book.contact.phone` [absent → absent:phone] C=`+79257203145` I=``
- FIELD `crm_upsert_contact.contact.address.city` [absent → absent:city] C=`Воткинск` I=``
- FIELD `crm_upsert_contact.contact.address.flat` [absent → absent:flat] C=`150` I=``
- FIELD `crm_upsert_contact.contact.address.house` [absent → absent:house] C=`177` I=``
- FIELD `crm_upsert_contact.contact.address.street` [absent → absent:street] C=`Кирочная` I=``
- FIELD `crm_upsert_contact.contact.first_name` [absent → absent:first_name] C=`Владислав` I=``
- FIELD `crm_upsert_contact.contact.gender` [absent → absent:gender] C=`M` I=``
- FIELD `crm_upsert_contact.contact.initials` [absent → absent:initials] C=`В.` I=``
- FIELD `crm_upsert_contact.contact.last_name` [absent → absent:last_name] C=`Захаров` I=``
- FIELD `crm_upsert_contact.contact.name_latin` [absent → absent:name_latin] C=`Zakharov Vladislav` I=``
- FIELD `crm_upsert_contact.contact.phone` [absent → absent:phone] C=`+79257203145` I=``
- REPLY I: Вы не ответили по телефону — верно ли **+7 925 720-31-45**? Пожалуйста, подтвердите или продиктуйте заново, и сразу оформлю!

## correction-018|1 · correction · voice_raw · L1 ≠ · L3 ≠ · C′≈C нет · причина: **Б9-span**
- USER[1]: добрый день курьера на адрес кирочная двадцать пять квартира сто пятьдесят ой нет правильно кирочная сто семьдесят семь квартира сто пятьдесят это в воткинск это захаров владислав телефон восем девятьсот двадцать пяять семест двадцать триста четырнадцать пяять
- USER[2]: в любой день с девяти до шести
- seen LOC `кирочная двадцать пять квартира сто пятьдесят` → `улица Луговая 73, кв. 93`
- seen LOC `кирочная сто семьдесят семь квартира сто пятьдесят` → `улица Абрикосовая 29, кв. 112`
- seen NAME `захаров владислав` → `Бирюков Матвей`
- **LEAK** PHONE `восем девятьсот двадцать пяять семест двадцать триста четырнадцать пяять` — модель видела настоящее значение
- C: `courier_book` {'address': {'locality': 'Воткинск', 'street': 'Кирочная', 'building': '177', 'sflat': '150'}, 'contact': {'name': 'Захаров Владислав', 'phone': '+79257203145'}, 'interval': {'from': '2026-09-03T09:0…
- C: `crm_upsert_contact` {'contact': {'last_name': 'Захаров', 'first_name': 'Владислав', 'initials': 'В.', 'name_latin': 'Zakharov Vladislav', 'gender': 'M', 'phone': '+79257203145', 'address': {'city': 'Воткинск', 'street':…
- I: — (без вызовов)
- C′: — (без вызовов)
- FIELD `courier_book.address.building` [absent → absent:building] C=`177` I=``
- FIELD `courier_book.address.locality` [absent → absent:locality] C=`Воткинск` I=``
- FIELD `courier_book.address.sflat` [absent → absent:sflat] C=`150` I=``
- FIELD `courier_book.address.street` [absent → absent:street] C=`Кирочная` I=``
- FIELD `courier_book.contact.name` [absent → absent:name] C=`Захаров Владислав` I=``
- FIELD `courier_book.contact.phone` [absent → absent:phone] C=`+79257203145` I=``
- FIELD `crm_upsert_contact.contact.address.city` [absent → absent:city] C=`Воткинск` I=``
- FIELD `crm_upsert_contact.contact.address.flat` [absent → absent:flat] C=`150` I=``
- FIELD `crm_upsert_contact.contact.address.house` [absent → absent:house] C=`177` I=``
- FIELD `crm_upsert_contact.contact.address.street` [absent → absent:street] C=`Кирочная` I=``
- FIELD `crm_upsert_contact.contact.first_name` [absent → absent:first_name] C=`Владислав` I=``
- FIELD `crm_upsert_contact.contact.gender` [absent → absent:gender] C=`M` I=``
- FIELD `crm_upsert_contact.contact.initials` [absent → absent:initials] C=`В.` I=``
- FIELD `crm_upsert_contact.contact.last_name` [absent → absent:last_name] C=`Захаров` I=``
- FIELD `crm_upsert_contact.contact.name_latin` [absent → absent:name_latin] C=`Zakharov Vladislav` I=``
- FIELD `crm_upsert_contact.contact.phone` [absent → absent:phone] C=`+79257203145` I=``
- REPLY I: Понял, возьму сегодня, 3 сентября, с 09:00 до 18:00. Но телефон владислава всё ещё нужен — без него не смогу оформить вызов. Пожалуйста, продиктуйте номер ещё раз! 📞

## correction-018|2 · correction · voice_raw · L1 = · L3 = · C′≈C да · причина: **leak-only**
- USER[1]: добрый день курьера на адрес кирочная двадцать пять квартира сто пятьдесят ой нет правильно кирочная сто семьдесят семь квартира сто пятьдесят это в воткинск это захаров владислав телефон восем девятьсот двадцать пяять семест двадцать триста четырнадцать пяять
- USER[2]: в любой день с девяти до шести
- seen LOC `кирочная двадцать пять квартира сто пятьдесят` → `улица Липовая 65, кв. 95`
- seen LOC `кирочная сто семьдесят семь квартира сто пятьдесят` → `улица Еловая 116, кв. 189`
- seen NAME `захаров владислав` → `Фомин Эдуард`
- **LEAK** PHONE `восем девятьсот двадцать пяять семест двадцать триста четырнадцать пяять` — модель видела настоящее значение
- C: — (без вызовов)
- I: — (без вызовов)
- C′: — (без вызовов)
- REPLY I: Понял, время — с 09:00 до 18:00, оформлю на сегодня, 3 сентября. Но номер телефона так и не получил — без него курьера не вызвать. Продиктуйте, пожалуйста, ещё раз! 📞

## correction-021|0 · correction · sloppy · L1 = · L3 ≠ · C′≈C нет · причина: **other**
- USER[1]: привет курьера на добролюбова 29кв73 простите ошиблась правильно добролюбова 1кв73 это в можга это новиков игорь телефон 8-999-106-11-83
- USER[2]: в любой день с девяти до шести
- seen LOC `добролюбова 29кв73` → `Бабаян 29кв73`
- seen LOC `добролюбова 1кв73` → `Бабаян 1кв73`
- seen NAME `новиков игорь` → `Цветков Виталий`
- seen PHONE `8-999-106-11-83` → `+79867644626`
- C: `courier_book` {'address': {'locality': 'Можга', 'street': 'Добролюбова', 'building': '1', 'sflat': '73'}, 'contact': {'name': 'Новиков Игорь', 'phone': '+79991061183'}, 'interval': {'from': '2026-09-03T09:00:00+04…
- C: `crm_upsert_contact` {'contact': {'last_name': 'Новиков', 'first_name': 'Игорь', 'initials': 'И.', 'name_latin': 'Novikov Igor', 'phone': '+79991061183', 'address': {'city': 'Можга', 'street': 'Добролюбова', 'house': '1'…
- I: `courier_book` written={'address': {'locality': 'Можга', 'street': 'Бабаян', 'building': '1', 'sflat': '73'}, 'contact': {'name': 'Цветков Виталий', 'phone': '+79867644626'}, 'interval': {'from': '2026-09-03T09:00:00+04:00', 'to': '2026-09-03T18:00:00+04:00'}} → restored={'address': {'locality': 'Можга', 'street': 'добролюбова', 'building': '1', 'sflat': '73'}, 'contact': {'name': 'новиков игорь', 'phone': '+79991061183'}, 'interval': {'from': '2026-09-03T09:00:00+04:00', 'to': '2026-09-03T18:00:00+04:00'}}
- I: `crm_upsert_contact` written={'contact': {'last_name': 'Цветков', 'first_name': 'Виталий', 'initials': 'В.', 'name_latin': 'Tsvetkov Vitaly', 'gender': 'M', 'phone': '+79867644626', 'address': {'city': 'Можга', 'street': 'Бабаян', 'house': '1', 'flat': '73'}}} → restored={'contact': {'last_name': 'новиков', 'first_name': 'игорь', 'initials': 'В.', 'name_latin': 'Novikov Vitaly', 'gender': 'M', 'phone': '+79991061183', 'address': {'city': 'Можга', 'street': 'добролюбова', 'house': '1', 'flat': '73'}}}
- C′: `courier_book` {'address': {'locality': 'Можга', 'street': 'Добролюбова', 'building': '1', 'sflat': '73'}, 'contact': {'name': 'Новиков Игорь', 'phone': '+79991061183'}, 'interval': {'from': '2026-09-03T09:00:00+04…
- C′: `crm_upsert_contact` {'contact': {'last_name': 'Новиков', 'first_name': 'Игорь', 'initials': 'И.', 'name_latin': 'Novikov Igor', 'gender': 'M', 'phone': '+79991061183', 'address': {'city': 'Можга', 'street': 'Добролюбова…
- FIELD `crm_upsert_contact.contact.gender` [extra → extra:gender] C=`` I=`M`
- FIELD `crm_upsert_contact.contact.initials` [derived/from_substitute → derived] C=`И.` I=`В.` · значение выведено из ПОДМЕНЫ; восстановление недостижимо
- FIELD `crm_upsert_contact.contact.name_latin` [other/misderived → name_partial] C=`Novikov Igor` I=`Novikov Vitaly`
- REPLY I: Оформляю сразу всё — вызов курьера и карточку клиента! Всё готово! ✅ **Курьер вызван** (заявка `clm-1`) - 📍 Можга, ул. добролюбова, д. 1, кв. 73 - 👤 новиков игорь, 8-999-106-11-83 - 🕘 Сегодня, 03.09.2026, с 09:00 до 18:00 **Карточка клиента** создана/обновлена в CRM (`c-1`). Если что-то нужно измен…

## correction-021|1 · correction · sloppy · L1 = · L3 ≠ · C′≈C да · причина: **derived-only**
- USER[1]: привет курьера на добролюбова 29кв73 простите ошиблась правильно добролюбова 1кв73 это в можга это новиков игорь телефон 8-999-106-11-83
- USER[2]: в любой день с девяти до шести
- seen LOC `добролюбова 29кв73` → `Марчук 29кв73`
- seen LOC `добролюбова 1кв73` → `Марчук 1кв73`
- seen NAME `новиков игорь` → `Лебедев Кузьма`
- seen PHONE `8-999-106-11-83` → `+79856602796`
- C: `courier_book` {'address': {'locality': 'Можга', 'street': 'Добролюбова', 'building': '1', 'sflat': '73'}, 'contact': {'name': 'Новиков Игорь', 'phone': '+79991061183'}, 'interval': {'from': '2026-09-03T09:00:00+04…
- C: `crm_upsert_contact` {'contact': {'first_name': 'Игорь', 'last_name': 'Новиков', 'phone': '+79991061183', 'initials': 'И.', 'name_latin': 'Novikov Igor', 'address': {'city': 'Можга', 'street': 'Добролюбова', 'house': '1'…
- I: `courier_book` written={'address': {'locality': 'Можга', 'street': 'Марчук', 'building': '1', 'sflat': '73'}, 'contact': {'name': 'Лебедев Кузьма', 'phone': '+79856602796'}, 'interval': {'from': '2026-09-03T09:00:00+04:00', 'to': '2026-09-03T18:00:00+04:00'}} → restored={'address': {'locality': 'Можга', 'street': 'добролюбова', 'building': '1', 'sflat': '73'}, 'contact': {'name': 'новиков игорь', 'phone': '+79991061183'}, 'interval': {'from': '2026-09-03T09:00:00+04:00', 'to': '2026-09-03T18:00:00+04:00'}}
- I: `crm_upsert_contact` written={'contact': {'last_name': 'Лебедев', 'first_name': 'Кузьма', 'phone': '+79856602796', 'gender': 'M', 'initials': 'К.', 'name_latin': 'Lebedev Kuzma', 'address': {'city': 'Можга', 'street': 'Марчук', 'house': '1', 'flat': '73'}}} → restored={'contact': {'last_name': 'новиков', 'first_name': 'игорь', 'phone': '+79991061183', 'gender': 'M', 'initials': 'К.', 'name_latin': 'Novikov Igor', 'address': {'city': 'Можга', 'street': 'добролюбова', 'house': '1', 'flat': '73'}}}
- C′: `courier_book` {'address': {'locality': 'Можга', 'street': 'Добролюбова', 'building': '1', 'sflat': '73'}, 'contact': {'name': 'Новиков Игорь', 'phone': '+79991061183'}, 'interval': {'from': '2026-09-03T09:00:00+04…
- C′: `crm_upsert_contact` {'contact': {'first_name': 'Игорь', 'last_name': 'Новиков', 'initials': 'И.', 'name_latin': 'Novikov Igor', 'phone': '+79991061183', 'address': {'city': 'Можга', 'street': 'Добролюбова', 'house': '1'…
- FIELD `crm_upsert_contact.contact.gender` [extra → extra:gender] C=`` I=`M`
- FIELD `crm_upsert_contact.contact.initials` [derived/from_substitute → derived] C=`И.` I=`К.` · значение выведено из ПОДМЕНЫ; восстановление недостижимо
- REPLY I: Оформляю сразу всё параллельно! 🚀 Всё готово! ✅ **Курьер вызван** (заявка `clm-1`): - 📍 Можга, ул. добролюбова, д. 1, кв. 73 - 👤 новиков игорь, 8-999-106-11-83 - 🕘 Сегодня, 03.09.2026, с 09:00 до 18:00 **Карточка клиента** в CRM также создана/обновлена. Если что-то нужно изменить — скажите!

## correction-021|2 · correction · sloppy · L1 ≠ · L3 ≠ · C′≈C нет · причина: **other**
- USER[1]: привет курьера на добролюбова 29кв73 простите ошиблась правильно добролюбова 1кв73 это в можга это новиков игорь телефон 8-999-106-11-83
- USER[2]: в любой день с девяти до шести
- seen LOC `добролюбова 29кв73` → `Коваленко 29кв73`
- seen LOC `добролюбова 1кв73` → `Коваленко 1кв73`
- seen NAME `новиков игорь` → `Беляев Роман`
- seen PHONE `8-999-106-11-83` → `+79877853387`
- C: `courier_book` {'address': {'locality': 'Можга', 'street': 'Добролюбова', 'building': '1', 'sflat': '73'}, 'contact': {'name': 'Новиков Игорь', 'phone': '+79991061183'}, 'interval': {'from': '2026-09-03T09:00:00+04…
- I: `crm_upsert_contact` written={'contact': {'first_name': 'Роман', 'last_name': 'Беляев', 'phone': '+79877853387', 'initials': 'Р.', 'name_latin': 'Belyaev Roman', 'address': {'city': 'Можга', 'street': 'Коваленко', 'house': '1', 'flat': '73'}}} → restored={'contact': {'first_name': 'игорь', 'last_name': 'новиков', 'phone': '+79991061183', 'initials': 'Р.', 'name_latin': 'Novikov Igor', 'address': {'city': 'Можга', 'street': 'добролюбова', 'house': '1', 'flat': '73'}}}
- I: `courier_book` written={'address': {'locality': 'Можга', 'street': 'Коваленко', 'building': '1', 'sflat': '73'}, 'contact': {'name': 'Беляев Роман', 'phone': '+79877853387'}, 'interval': {'from': '2026-09-03T09:00:00+04:00', 'to': '2026-09-03T18:00:00+04:00'}} → restored={'address': {'locality': 'Можга', 'street': 'добролюбова', 'building': '1', 'sflat': '73'}, 'contact': {'name': 'новиков игорь', 'phone': '+79991061183'}, 'interval': {'from': '2026-09-03T09:00:00+04:00', 'to': '2026-09-03T18:00:00+04:00'}}
- C′: `courier_book` {'address': {'locality': 'Можга', 'street': 'Добролюбова', 'building': '1', 'sflat': '73'}, 'contact': {'name': 'Новиков Игорь', 'phone': '+79991061183'}, 'interval': {'from': '2026-09-03T09:00:00+04…
- C′: `crm_upsert_contact` {'contact': {'last_name': 'Новиков', 'first_name': 'Игорь', 'initials': 'И.', 'name_latin': 'Novikov Igor', 'phone': '+79991061183', 'address': {'city': 'Можга', 'street': 'Добролюбова', 'house': '1'…
- FIELD `crm_upsert_contact.contact.address.city` [extra → extra:city] C=`` I=`Можга`
- FIELD `crm_upsert_contact.contact.address.flat` [extra → extra:flat] C=`` I=`73`
- FIELD `crm_upsert_contact.contact.address.house` [extra → extra:house] C=`` I=`1`
- FIELD `crm_upsert_contact.contact.address.street` [extra → extra:street] C=`` I=`добролюбова`
- FIELD `crm_upsert_contact.contact.first_name` [extra → extra:first_name] C=`` I=`игорь`
- FIELD `crm_upsert_contact.contact.initials` [extra → extra:initials] C=`` I=`Р.`
- FIELD `crm_upsert_contact.contact.last_name` [extra → extra:last_name] C=`` I=`новиков`
- FIELD `crm_upsert_contact.contact.name_latin` [extra → extra:name_latin] C=`` I=`Novikov Igor`
- FIELD `crm_upsert_contact.contact.phone` [extra → extra:phone] C=`` I=`+79991061183`
- REPLY I: Оформляю заказ и вызываю курьера на сегодня, 3 сентября, с 09:00 до 18:00! Всё оформлено! ✅ **Курьер вызван** (№ clm-1): - 📍 Можга, ул. добролюбова, д. 1, кв. 73 - 👤 новиков игорь, 8-999-106-11-83 - 🕘 Сегодня, 3 сентября, с 09:00 до 18:00 Карточка клиента в CRM также создана. Если что-то нужно изме…

## correction-024|0 · correction · voice_raw · L1 ≠ · L3 ≠ · C′≈C нет · причина: **other**
- USER[1]: здравствуйтее курьера на базисная три квартира сто семьдесят один нет не таак правильно базисная сто пятьдесят пять квартира сто семьдесят один этоо в сортавала этоо морозов леонид телефонто восемь девятьсот шестьдесят девятьсот семь восемьдесят пять девяносто два
- USER[2]: завтра с десяти до двух
- seen LOC `базисная три квартира сто семьдесят один` → `улица Сиреневая 81, кв. 66`
- seen LOC `базисная сто пятьдесят пять квартира сто семьдесят один` → `улица Луговая 67, кв. 12`
- seen NAME `морозов леонид` → `Щукин Георгий`
- seen PHONE `восемь девятьсот шестьдесят девятьсот семь восемьдесят пять девяносто два` → `+79117073169`
- C: — (без вызовов)
- I: `courier_book` written={'address': {'locality': 'Сортавала', 'street': 'Луговая', 'building': '67', 'sflat': '12'}, 'contact': {'name': 'Щукин Георгий', 'phone': '+79117073169'}, 'interval': {'from': '2026-09-04T10:00:00+03:00', 'to': '2026-09-04T14:00:00+03:00'}} → restored={'address': {'locality': 'Сортавала', 'street': 'базисная', 'building': '155', 'sflat': '171'}, 'contact': {'name': 'морозов леонид', 'phone': '+79609078592'}, 'interval': {'from': '2026-09-04T10:00:00+03:00', 'to': '2026-09-04T14:00:00+03:00'}}
- I: `crm_upsert_contact` written={'contact': {'last_name': 'Щукин', 'first_name': 'Георгий', 'initials': 'Г.', 'name_latin': 'Shchukin Georgiy', 'phone': '+79117073169', 'gender': 'M', 'address': {'city': 'Сортавала', 'street': 'Луговая', 'house': '67', 'flat': '12'}}} → restored={'contact': {'last_name': 'морозов', 'first_name': 'леонид', 'initials': 'Г.', 'name_latin': 'Morozov Leonid', 'phone': '+79609078592', 'gender': 'M', 'address': {'city': 'Сортавала', 'street': 'базисная', 'house': '155', 'flat': '171'}}}
- C′: `courier_book` {'address': {'locality': 'Сортавала', 'street': 'Базисная', 'building': '155', 'sflat': '171'}, 'contact': {'name': 'Морозов Леонид', 'phone': '+79609078592'}, 'interval': {'from': '2026-09-04T10:00:…
- C′: `crm_upsert_contact` {'contact': {'last_name': 'Морозов', 'first_name': 'Леонид', 'initials': 'Л.', 'name_latin': 'Morozov Leonid', 'phone': '+79609078592', 'address': {'city': 'Сортавала', 'street': 'Базисная', 'house':…
- FIELD `courier_book.address.building` [extra → extra:building] C=`` I=`155`
- FIELD `courier_book.address.locality` [extra → extra:locality] C=`` I=`Сортавала`
- FIELD `courier_book.address.sflat` [extra → extra:sflat] C=`` I=`171`
- FIELD `courier_book.address.street` [extra → extra:street] C=`` I=`базисная`
- FIELD `courier_book.contact.name` [extra → extra:name] C=`` I=`морозов леонид`
- FIELD `courier_book.contact.phone` [extra → extra:phone] C=`` I=`+79609078592`
- FIELD `crm_upsert_contact.contact.address.city` [extra → extra:city] C=`` I=`Сортавала`
- FIELD `crm_upsert_contact.contact.address.flat` [extra → extra:flat] C=`` I=`171`
- FIELD `crm_upsert_contact.contact.address.house` [extra → extra:house] C=`` I=`155`
- FIELD `crm_upsert_contact.contact.address.street` [extra → extra:street] C=`` I=`базисная`
- FIELD `crm_upsert_contact.contact.first_name` [extra → extra:first_name] C=`` I=`леонид`
- FIELD `crm_upsert_contact.contact.gender` [extra → extra:gender] C=`` I=`M`
- FIELD `crm_upsert_contact.contact.initials` [extra → extra:initials] C=`` I=`Г.`
- FIELD `crm_upsert_contact.contact.last_name` [extra → extra:last_name] C=`` I=`морозов`
- FIELD `crm_upsert_contact.contact.name_latin` [extra → extra:name_latin] C=`` I=`Morozov Leonid`
- FIELD `crm_upsert_contact.contact.phone` [extra → extra:phone] C=`` I=`+79609078592`
- REPLY I: Отлично, оформляю всё одновременно! Всё готово! ✅ **Курьер вызван** (№ clm-1): - 📍 Сортавала, ул. базисная сто пятьдесят пять квартира сто семьдесят один - 👤 морозов леонид, восемь девятьсот шестьдесят девятьсот семь восемьдесят пять девяносто два - 🗓 4 сентября 2026, с 10:00 до 14:00 **Карточка кл…

## correction-024|1 · correction · voice_raw · L1 = · L3 ≠ · C′≈C да · причина: **other**
- USER[1]: здравствуйтее курьера на базисная три квартира сто семьдесят один нет не таак правильно базисная сто пятьдесят пять квартира сто семьдесят один этоо в сортавала этоо морозов леонид телефонто восемь девятьсот шестьдесят девятьсот семь восемьдесят пять девяносто два
- USER[2]: завтра с десяти до двух
- seen LOC `базисная три квартира сто семьдесят один` → `улица Буковая 106, кв. 165`
- seen LOC `базисная сто пятьдесят пять квартира сто семьдесят один` → `улица Родниковая 101, кв. 181`
- seen NAME `морозов леонид` → `Мещеряков Лев`
- seen PHONE `восемь девятьсот шестьдесят девятьсот семь восемьдесят пять девяносто два` → `+79766540151`
- C: `courier_book` {'address': {'locality': 'Сортавала', 'street': 'Базисная', 'building': '155', 'sflat': '171'}, 'contact': {'name': 'Морозов Леонид', 'phone': '+79609078592'}, 'interval': {'from': '2026-09-04T10:00:…
- C: `crm_upsert_contact` {'contact': {'last_name': 'Морозов', 'first_name': 'Леонид', 'initials': 'Л.', 'name_latin': 'Morozov Leonid', 'phone': '+79609078592', 'gender': 'M', 'address': {'city': 'Сортавала', 'street': 'Бази…
- I: `courier_book` written={'address': {'locality': 'Сортавала', 'street': 'Родниковая', 'building': '101', 'sflat': '181'}, 'contact': {'name': 'Мещеряков Лев', 'phone': '+79766540151'}, 'interval': {'from': '2026-09-04T10:00:00+03:00', 'to': '2026-09-04T14:00:00+03:00'}} → restored={'address': {'locality': 'Сортавала', 'street': 'базисная', 'building': '155', 'sflat': '171'}, 'contact': {'name': 'морозов леонид', 'phone': '+79609078592'}, 'interval': {'from': '2026-09-04T10:00:00+03:00', 'to': '2026-09-04T14:00:00+03:00'}}
- I: `crm_upsert_contact` written={'contact': {'last_name': 'Мещеряков', 'first_name': 'Лев', 'initials': 'Л.', 'name_latin': 'Meshcheryakov Lev', 'phone': '+79766540151', 'address': {'city': 'Сортавала', 'street': 'Родниковая', 'house': '101', 'flat': '181'}}} → restored={'contact': {'last_name': 'морозов', 'first_name': 'леонид', 'initials': 'Л.', 'name_latin': 'Meshcheryakov Leonid', 'phone': '+79609078592', 'address': {'city': 'Сортавала', 'street': 'базисная', 'house': '155', 'flat': '171'}}}
- C′: `courier_book` {'address': {'locality': 'Сортавала', 'street': 'Базисная', 'building': '155', 'sflat': '171'}, 'contact': {'name': 'Морозов Леонид', 'phone': '+79609078592'}, 'interval': {'from': '2026-09-04T10:00:…
- C′: `crm_upsert_contact` {'contact': {'first_name': 'Леонид', 'last_name': 'Морозов', 'phone': '+79609078592', 'gender': 'M', 'initials': 'Л.', 'name_latin': 'Morozov Leonid', 'address': {'city': 'Сортавала', 'street': 'Бази…
- FIELD `crm_upsert_contact.contact.gender` [absent → absent:gender] C=`M` I=``
- FIELD `crm_upsert_contact.contact.name_latin` [other/misderived → name_partial] C=`Morozov Leonid` I=`Meshcheryakov Leonid`
- REPLY I: Отлично, оформляю всё одновременно! Всё готово! Вот что оформлено: 🚚 **Курьер вызван** - **Адрес:** г. Сортавала, ул. базисная сто пятьдесят пять квартира сто семьдесят один - **Получатель:** морозов леонид, восемь девятьсот шестьдесят девятьсот семь восемьдесят пять девяносто два - **Дата и время:…

## correction-024|2 · correction · voice_raw · L1 = · L3 ≠ · C′≈C нет · причина: **other**
- USER[1]: здравствуйтее курьера на базисная три квартира сто семьдесят один нет не таак правильно базисная сто пятьдесят пять квартира сто семьдесят один этоо в сортавала этоо морозов леонид телефонто восемь девятьсот шестьдесят девятьсот семь восемьдесят пять девяносто два
- USER[2]: завтра с десяти до двух
- seen LOC `базисная три квартира сто семьдесят один` → `улица Речная 145, кв. 210`
- seen LOC `базисная сто пятьдесят пять квартира сто семьдесят один` → `улица Ивовая 106, кв. 187`
- seen NAME `морозов леонид` → `Юдин Тимофей`
- seen PHONE `восемь девятьсот шестьдесят девятьсот семь восемьдесят пять девяносто два` → `+79174041695`
- C: `crm_upsert_contact` {'contact': {'first_name': 'Леонид', 'last_name': 'Морозов', 'initials': 'Л.', 'name_latin': 'Morozov Leonid', 'phone': '+79699078592', 'gender': 'M', 'address': {'city': 'Сортавала', 'street': 'Бази…
- C: `courier_book` {'address': {'locality': 'Сортавала', 'street': 'Базисная', 'building': '155', 'sflat': '171'}, 'contact': {'name': 'Морозов Леонид', 'phone': '+79699078592'}, 'interval': {'from': '2026-09-04T10:00:…
- I: `crm_upsert_contact` written={'contact': {'last_name': 'Юдин', 'first_name': 'Тимофей', 'initials': 'Т.', 'name_latin': 'Yudin Timofey', 'gender': 'M', 'phone': '+79174041695', 'address': {'city': 'Сортавала', 'street': 'Ивовая', 'house': '106', 'flat': '187'}}} → restored={'contact': {'last_name': 'морозов', 'first_name': 'леонид', 'initials': 'Т.', 'name_latin': 'Morozov Leonid', 'gender': 'M', 'phone': '+79609078592', 'address': {'city': 'Сортавала', 'street': 'базисная', 'house': '155', 'flat': '171'}}}
- I: `courier_book` written={'address': {'locality': 'Сортавала', 'street': 'Ивовая', 'building': '106', 'sflat': '187'}, 'contact': {'name': 'Юдин Тимофей', 'phone': '+79174041695'}, 'interval': {'from': '2026-09-04T10:00:00+03:00', 'to': '2026-09-04T14:00:00+03:00'}} → restored={'address': {'locality': 'Сортавала', 'street': 'базисная', 'building': '155', 'sflat': '171'}, 'contact': {'name': 'морозов леонид', 'phone': '+79609078592'}, 'interval': {'from': '2026-09-04T10:00:00+03:00', 'to': '2026-09-04T14:00:00+03:00'}}
- C′: `courier_book` {'address': {'locality': 'Сортавала', 'street': 'Базисная', 'building': '155', 'sflat': '171'}, 'contact': {'name': 'Морозов Леонид', 'phone': '+79609078592'}, 'interval': {'from': '2026-09-04T10:00:…
- C′: `crm_upsert_contact` {'contact': {'last_name': 'Морозов', 'first_name': 'Леонид', 'initials': 'Л.', 'name_latin': 'Morozov Leonid', 'gender': 'M', 'phone': '+79609078592', 'address': {'city': 'Сортавала', 'street': 'Бази…
- FIELD `crm_upsert_contact.contact.initials` [derived/from_substitute → derived] C=`Л.` I=`Т.` · значение выведено из ПОДМЕНЫ; восстановление недостижимо
- FIELD `crm_upsert_contact.contact.phone` [control_erred/i4 → control_erred] C=`+79699078592` I=`+79609078592` · контроль ошибся; шлюз восстановил эталон корпуса
- FIELD `courier_book.contact.phone` [control_erred/i4 → control_erred] C=`+79699078592` I=`+79609078592` · контроль ошибся; шлюз восстановил эталон корпуса
- REPLY I: Отлично, оформляю! Запускаю одновременно карточку клиента и вызов курьера. Всё готово! Вот итог: - 📋 **Карточка клиента** — создана (морозов леонид, восемь девятьсот шестьдесят девятьсот семь восемьдесят пять девяносто два) - 🚚 **Курьер вызван** — **4 сентября, с 10:00 до 14:00** - Адрес: базисная …

## correction-025|0 · correction · voice_itn · L1 = · L3 ≠ · C′≈C да · причина: **other**
- USER[1]: здравствуйте курьера на калашникова дом 65 квартира 143 стоп правильно калашникова 37 квартира 143 это в краснодар это громова марина телефон 89505556677
- USER[2]: в любой день с девяти до шести
- seen LOC `калашникова дом 65 квартира 143` → `улица Речная 131, кв. 187`
- seen LOC `калашникова 37 квартира 143` → `улица Кедровая 125, кв. 97`
- seen NAME `громова марина` → `Панова Амелия`
- seen PHONE `89505556677` → `+79821682814`
- C: `courier_book` {'address': {'locality': 'Краснодар', 'street': 'Калашникова', 'building': '37', 'sflat': '143'}, 'contact': {'name': 'Громова Марина', 'phone': '+79505556677'}, 'interval': {'from': '2026-09-03T09:0…
- C: `crm_upsert_contact` {'contact': {'last_name': 'Громова', 'first_name': 'Марина', 'initials': 'М.', 'name_latin': 'Gromova Marina', 'gender': 'F', 'phone': '+79505556677', 'address': {'city': 'Краснодар', 'street': 'Кала…
- I: `courier_book` written={'address': {'locality': 'Краснодар', 'street': 'Кедровая', 'building': '125', 'sflat': '97'}, 'contact': {'name': 'Панова Амелия', 'phone': '+79821682814'}, 'interval': {'from': '2026-09-03T09:00:00+03:00', 'to': '2026-09-03T18:00:00+03:00'}} → restored={'address': {'locality': 'Краснодар', 'street': 'калашникова', 'building': '125', 'sflat': '143'}, 'contact': {'name': 'громова марина', 'phone': '+79505556677'}, 'interval': {'from': '2026-09-03T09:00:00+03:00', 'to': '2026-09-03T18:00:00+03:00'}}
- I: `crm_upsert_contact` written={'contact': {'last_name': 'Панова', 'first_name': 'Амелия', 'initials': 'А.', 'name_latin': 'Panova Amelia', 'gender': 'F', 'phone': '+79821682814', 'address': {'city': 'Краснодар', 'street': 'Кедровая', 'house': '125', 'flat': '97'}}} → restored={'contact': {'last_name': 'громова', 'first_name': 'марина', 'initials': 'А.', 'name_latin': 'Gromova Amelia', 'gender': 'F', 'phone': '+79505556677', 'address': {'city': 'Краснодар', 'street': 'калашникова', 'house': '37', 'flat': '143'}}}
- C′: `courier_book` {'address': {'locality': 'Краснодар', 'street': 'Калашникова', 'building': '37', 'sflat': '143'}, 'contact': {'name': 'Громова Марина', 'phone': '+79505556677'}, 'interval': {'from': '2026-09-03T09:0…
- C′: `crm_upsert_contact` {'contact': {'last_name': 'Громова', 'first_name': 'Марина', 'initials': 'М.', 'name_latin': 'Gromova Marina', 'gender': 'F', 'phone': '+79505556677', 'address': {'city': 'Краснодар', 'street': 'Кала…
- FIELD `courier_book.address.building` [reformatted → loc_fake] C=`37` I=`125`
- FIELD `crm_upsert_contact.contact.initials` [derived/from_substitute → derived] C=`М.` I=`А.` · значение выведено из ПОДМЕНЫ; восстановление недостижимо
- FIELD `crm_upsert_contact.contact.name_latin` [other/misderived → name_partial] C=`Gromova Marina` I=`Gromova Amelia`
- REPLY I: Оформляю курьера на сегодня и создаю карточку клиента! Всё готово! Вот итоги: ✅ **Курьер вызван** (заявка `clm-1`) - 📍 Краснодар, калашникова 37 квартира 143 - 👤 громовой марины, 89505556677 - 🕘 Сегодня, 03.09.2026, с 09:00 до 18:00 ✅ **Карточка клиента** создана/обновлена в CRM. Если понадобится ч…

## correction-025|1 · correction · voice_itn · L1 = · L3 ≠ · C′≈C нет · причина: **other**
- USER[1]: здравствуйте курьера на калашникова дом 65 квартира 143 стоп правильно калашникова 37 квартира 143 это в краснодар это громова марина телефон 89505556677
- USER[2]: в любой день с девяти до шести
- seen LOC `калашникова дом 65 квартира 143` → `улица Вязовая 44, кв. 165`
- seen LOC `калашникова 37 квартира 143` → `улица Вишнёвая 196, кв. 117`
- seen NAME `громова марина` → `Рыбакова Людмила`
- seen PHONE `89505556677` → `+79274653177`
- C: `courier_book` {'address': {'locality': 'Краснодар', 'street': 'Калашникова', 'building': '37', 'sflat': '143'}, 'contact': {'name': 'Громова Марина', 'phone': '+79505556677'}, 'interval': {'from': '2026-09-03T09:0…
- C: `crm_upsert_contact` {'contact': {'first_name': 'Марина', 'last_name': 'Громова', 'phone': '+79505556677', 'gender': 'F', 'initials': 'М.', 'name_latin': 'Gromova Marina', 'address': {'city': 'Краснодар', 'street': 'Кала…
- I: `courier_book` written={'address': {'locality': 'Краснодар', 'street': 'Вишнёвая', 'building': '196', 'sflat': '117'}, 'contact': {'name': 'Рыбакова Людмила', 'phone': '+79274653177'}, 'interval': {'from': '2026-09-03T09:00:00+03:00', 'to': '2026-09-03T18:00:00+03:00'}} → restored={'address': {'locality': 'Краснодар', 'street': 'калашникова', 'building': '37', 'sflat': '143'}, 'contact': {'name': 'громова марина', 'phone': '+79505556677'}, 'interval': {'from': '2026-09-03T09:00:00+03:00', 'to': '2026-09-03T18:00:00+03:00'}}
- I: `crm_upsert_contact` written={'contact': {'last_name': 'Рыбакова', 'first_name': 'Людмила', 'gender': 'F', 'phone': '+79274653177', 'initials': 'Л.', 'name_latin': 'Rybakova Ludmila', 'address': {'city': 'Краснодар', 'street': 'Вишнёвая', 'house': '196', 'flat': '117'}}} → restored={'contact': {'last_name': 'громова', 'first_name': 'марина', 'gender': 'F', 'phone': '+79505556677', 'initials': 'Л.', 'name_latin': 'Gromova Ludmila', 'address': {'city': 'Краснодар', 'street': 'калашникова', 'house': '37', 'flat': '143'}}}
- C′: `courier_book` {'address': {'locality': 'Краснодар', 'street': 'Калашникова', 'building': '37', 'sflat': '143'}, 'contact': {'name': 'Громова Марина', 'phone': '+79505556677'}, 'interval': {'from': '2026-09-03T09:0…
- C′: `crm_upsert_contact` {'contact': {'last_name': 'Громова', 'first_name': 'Марина', 'initials': 'М.', 'name_latin': 'Gromova Marina', 'phone': '+79505556677', 'address': {'city': 'Краснодар', 'street': 'Калашникова', 'hous…
- FIELD `crm_upsert_contact.contact.initials` [derived/from_substitute → derived] C=`М.` I=`Л.` · значение выведено из ПОДМЕНЫ; восстановление недостижимо
- FIELD `crm_upsert_contact.contact.name_latin` [other/misderived → name_partial] C=`Gromova Marina` I=`Gromova Ludmila`
- REPLY I: Принято, оформляю сегодня с 09:00 до 18:00! Запускаю одновременно вызов курьера и карточку клиента. Всё оформлено! ✅ **Вызов курьера** (№ clm-1): - 📍 Краснодар, калашникова 37 квартира 143 - 👤 громова марина, 89505556677 - 🕘 Сегодня, 03.09.2026, с 09:00 до 18:00 **Карточка клиента** в CRM создана/о…

## correction-025|2 · correction · voice_itn · L1 ≠ · L3 ≠ · C′≈C нет · причина: **derived-only**
- USER[1]: здравствуйте курьера на калашникова дом 65 квартира 143 стоп правильно калашникова 37 квартира 143 это в краснодар это громова марина телефон 89505556677
- USER[2]: в любой день с девяти до шести
- seen LOC `калашникова дом 65 квартира 143` → `улица Ивовая 43, кв. 75`
- seen LOC `калашникова 37 квартира 143` → `улица Родниковая 40, кв. 155`
- seen NAME `громова марина` → `Лебедева Власта`
- seen PHONE `89505556677` → `+79470484599`
- C: `crm_upsert_contact` {'contact': {'last_name': 'Громова', 'first_name': 'Марина', 'gender': 'F', 'initials': 'М.', 'name_latin': 'Gromova Marina', 'phone': '+79505556677', 'address': {'city': 'Краснодар', 'street': 'Кала…
- C: `courier_book` {'address': {'locality': 'Краснодар', 'street': 'Калашникова', 'building': '37', 'sflat': '143'}, 'contact': {'name': 'Громова Марина', 'phone': '+79505556677'}, 'interval': {'from': '2026-09-03T09:0…
- I: `courier_book` written={'address': {'locality': 'Краснодар', 'street': 'Родниковая', 'building': '40', 'sflat': '155'}, 'contact': {'name': 'Лебедева Власта', 'phone': '+79470484599'}, 'interval': {'from': '2026-09-03T09:00:00+03:00', 'to': '2026-09-03T18:00:00+03:00'}} → restored={'address': {'locality': 'Краснодар', 'street': 'калашникова', 'building': '37', 'sflat': '143'}, 'contact': {'name': 'громова марина', 'phone': '+79505556677'}, 'interval': {'from': '2026-09-03T09:00:00+03:00', 'to': '2026-09-03T18:00:00+03:00'}}
- I: `crm_upsert_contact` written={'contact': {'last_name': 'Лебедева', 'first_name': 'Власта', 'initials': 'В.', 'name_latin': 'Lebedeva Vlasta', 'gender': 'F', 'phone': '+79470484599', 'address': {'city': 'Краснодар', 'street': 'Родниковая', 'house': '40', 'flat': '155'}}} → restored={'contact': {'last_name': 'громова', 'first_name': 'марина', 'initials': 'В.', 'name_latin': 'Gromova Marina', 'gender': 'F', 'phone': '+79505556677', 'address': {'city': 'Краснодар', 'street': 'калашникова', 'house': '37', 'flat': '143'}}}
- C′: `courier_book` {'address': {'locality': 'Краснодар', 'street': 'Калашникова', 'building': '37', 'sflat': '143'}, 'contact': {'name': 'Громова Марина', 'phone': '+79505556677'}, 'interval': {'from': '2026-09-03T09:0…
- C′: `crm_upsert_contact` {'contact': {'last_name': 'Громова', 'first_name': 'Марина', 'initials': 'М.', 'name_latin': 'Gromova Marina', 'gender': 'F', 'phone': '+79505556677', 'address': {'city': 'Краснодар', 'street': 'Кала…
- FIELD `crm_upsert_contact.contact.initials` [derived/from_substitute → derived] C=`М.` I=`В.` · значение выведено из ПОДМЕНЫ; восстановление недостижимо
- REPLY I: Принято! Оформляю на сегодня, 3 сентября, с 09:00 до 18:00. Запускаю оба действия сразу. Всё готово! Вот итог: - ✅ **Курьер вызван** на сегодня, **3 сентября, с 09:00 до 18:00** 📍 Краснодар, калашникова 37 квартира 143 👤 громова марина, 89505556677 🔖 Заявка №: `clm-1` - ✅ **Карточка клиента** созда…

## correction-030|0 · correction · voice_raw · L1 ≠ · L3 ≠ · C′≈C нет · причина: **typo-normalised**
- USER[1]: алло курьера наа адрес мончегорская трис три квартира пятьдесят шесть ой нет правильно мончегрская дом сто восемьдесят пять квартира пятьдесят шесть это в сарапул это кузнецов дмитрий телефон восемь девятьсот шестьдесят два восемест восемьдесят восемь девяно девять ноль ноль
- USER[2]: завтра с десятии до двух
- **LEAK** LOC `мончегорская трис три квартира пятьдесят шесть` — модель видела настоящее значение
- seen LOC `мончегрская дом сто восемьдесят пять квартира пятьдесят шесть` → `мончегрская улица Кленовая 79, кв. 81`
- seen NAME `кузнецов дмитрий` → `Цветков Борис`
- **LEAK** PHONE `восемь девятьсот шестьдесят два восемест восемьдесят восемь девяно девять ноль ноль` — модель видела настоящее значение
- C: `courier_book` {'address': {'locality': 'Сарапул', 'street': 'Мончегорская', 'building': '185', 'sflat': '56'}, 'contact': {'name': 'Кузнецов Дмитрий', 'phone': '+79628889900'}, 'interval': {'from': '2026-09-04T10:…
- I: `courier_book` written={'address': {'locality': 'Сарапул', 'street': 'Кленовая', 'building': '79', 'sflat': '81'}, 'contact': {'name': 'Цветков Борис', 'phone': '+79622889900'}, 'interval': {'from': '2026-09-04T10:00:00+04:00', 'to': '2026-09-04T14:00:00+04:00'}} → restored={'address': {'locality': 'Сарапул', 'street': 'дом сто восемьдесят пять квартира пятьдесят шесть', 'building': '185', 'sflat': '56'}, 'contact': {'name': 'кузнецов дмитрий', 'phone': '+79622889900'}, 'interval': {'from': '2026-09-04T10:00:00+04:00', 'to': '20…
- I: `crm_upsert_contact` written={'contact': {'last_name': 'Цветков', 'first_name': 'Борис', 'initials': 'Б.', 'name_latin': 'Tsvetkov Boris', 'phone': '+79622889900', 'address': {'city': 'Сарапул', 'street': 'Кленовая', 'house': '79', 'flat': '81'}}} → restored={'contact': {'last_name': 'кузнецов', 'first_name': 'дмитрий', 'initials': 'Б.', 'name_latin': 'Kuznetsov Dmitrii', 'phone': '+79622889900', 'address': {'city': 'Сарапул', 'street': 'дом сто восемьдесят пять квартира пятьдесят шесть', 'house': '185', 'flat': …
- C′: `crm_upsert_contact` {'contact': {'last_name': 'Кузнецов', 'first_name': 'Дмитрий', 'initials': 'Д.', 'name_latin': 'Kuznetsov Dmitry', 'gender': 'M', 'phone': '+79628889900', 'address': {'city': 'Сарапул', 'street': 'Мо…
- C′: `courier_book` {'address': {'locality': 'Сарапул', 'street': 'Мончегорская', 'building': '185', 'sflat': '56'}, 'contact': {'name': 'Кузнецов Дмитрий', 'phone': '+79628889900'}, 'interval': {'from': '2026-09-04T10:…
- FIELD `courier_book.address.street` [other/unbound → loc_other] C=`Мончегорская` I=`дом сто восемьдесят пять квартира пятьдесят шесть`
- FIELD `courier_book.contact.phone` [other/inflected → other/inflected] C=`+79628889900` I=`+79622889900`
- FIELD `crm_upsert_contact.contact.address.city` [extra → extra:city] C=`` I=`Сарапул`
- FIELD `crm_upsert_contact.contact.address.flat` [extra → extra:flat] C=`` I=`56`
- FIELD `crm_upsert_contact.contact.address.house` [extra → extra:house] C=`` I=`185`
- FIELD `crm_upsert_contact.contact.address.street` [extra → extra:street] C=`` I=`дом сто восемьдесят пять квартира пятьдесят шесть`
- FIELD `crm_upsert_contact.contact.first_name` [extra → extra:first_name] C=`` I=`дмитрий`
- FIELD `crm_upsert_contact.contact.initials` [extra → extra:initials] C=`` I=`Б.`
- FIELD `crm_upsert_contact.contact.last_name` [extra → extra:last_name] C=`` I=`кузнецов`
- FIELD `crm_upsert_contact.contact.name_latin` [extra → extra:name_latin] C=`` I=`Kuznetsov Dmitrii`
- FIELD `crm_upsert_contact.contact.phone` [extra → extra:phone] C=`` I=`+79622889900`
- REPLY I: Отлично, оформляю! Всё оформлено! ✅ **Курьер вызван** (заявка `clm-1`): - 📍 Сарапул, дом сто восемьдесят пять квартира пятьдесят шесть - 👤 кузнецов дмитрий, +7 962 288-99-00 - 🕙 4 сентября, с 10:00 до 14:00 Карточка клиента в CRM также создана. Если что-то нужно изменить — скажите!

## correction-030|1 · correction · voice_raw · L1 = · L3 ≠ · C′≈C нет · причина: **typo-normalised**
- USER[1]: алло курьера наа адрес мончегорская трис три квартира пятьдесят шесть ой нет правильно мончегрская дом сто восемьдесят пять квартира пятьдесят шесть это в сарапул это кузнецов дмитрий телефон восемь девятьсот шестьдесят два восемест восемьдесят восемь девяно девять ноль ноль
- USER[2]: завтра с десятии до двух
- **LEAK** LOC `мончегорская трис три квартира пятьдесят шесть` — модель видела настоящее значение
- seen LOC `мончегрская дом сто восемьдесят пять квартира пятьдесят шесть` → `мончегрская улица Абрикосовая 111, кв. 159`
- seen NAME `кузнецов дмитрий` → `Наумов Назар`
- **LEAK** PHONE `восемь девятьсот шестьдесят два восемест восемьдесят восемь девяно девять ноль ноль` — модель видела настоящее значение
- C: `courier_book` {'address': {'locality': 'Сарапул', 'street': 'Мончегорская', 'building': '185', 'sflat': '56'}, 'contact': {'name': 'Кузнецов Дмитрий', 'phone': '+79628889900'}, 'interval': {'from': '2026-09-04T10:…
- C: `crm_upsert_contact` {'contact': {'last_name': 'Кузнецов', 'first_name': 'Дмитрий', 'initials': 'Д.', 'name_latin': 'Kuznetsov Dmitriy', 'phone': '+79628889900', 'address': {'city': 'Сарапул', 'street': 'Мончегорская', '…
- I: `courier_book` written={'address': {'locality': 'Сарапул', 'street': 'Абрикосовая', 'building': '111', 'sflat': '159'}, 'contact': {'name': 'Наумов Назар', 'phone': '+79622889900'}, 'interval': {'from': '2026-09-04T10:00:00+04:00', 'to': '2026-09-04T14:00:00+04:00'}} → restored={'address': {'locality': 'Сарапул', 'street': 'дом сто восемьдесят пять квартира пятьдесят шесть', 'building': '185', 'sflat': '56'}, 'contact': {'name': 'кузнецов дмитрий', 'phone': '+79622889900'}, 'interval': {'from': '2026-09-04T10:00:00+04:00', 'to': '20…
- I: `crm_upsert_contact` written={'contact': {'last_name': 'Наумов', 'first_name': 'Назар', 'initials': 'Н.', 'name_latin': 'Naumov Nazar', 'gender': 'M', 'phone': '+79622889900', 'address': {'city': 'Сарапул', 'street': 'Абрикосовая', 'house': '111', 'flat': '159'}}} → restored={'contact': {'last_name': 'кузнецов', 'first_name': 'дмитрий', 'initials': 'Н.', 'name_latin': 'Kuznetsov Dmitrii', 'gender': 'M', 'phone': '+79622889900', 'address': {'city': 'Сарапул', 'street': 'дом сто восемьдесят пять квартира пятьдесят шесть', 'house': …
- C′: `courier_book` {'address': {'locality': 'Сарапул', 'street': 'Мончегорская', 'building': '185', 'sflat': '56'}, 'contact': {'name': 'Кузнецов Дмитрий', 'phone': '+79628889900'}, 'interval': {'from': '2026-09-04T10:…
- C′: `crm_upsert_contact` {'contact': {'last_name': 'Кузнецов', 'first_name': 'Дмитрий', 'initials': 'Д.', 'name_latin': 'Kuznetsov Dmitriy', 'gender': 'M', 'phone': '+79628889900', 'address': {'city': 'Сарапул', 'street': 'М…
- FIELD `courier_book.address.street` [other/unbound → loc_other] C=`Мончегорская` I=`дом сто восемьдесят пять квартира пятьдесят шесть`
- FIELD `courier_book.contact.phone` [other/inflected → other/inflected] C=`+79628889900` I=`+79622889900`
- FIELD `crm_upsert_contact.contact.address.street` [other/unbound → loc_other] C=`Мончегорская` I=`дом сто восемьдесят пять квартира пятьдесят шесть`
- FIELD `crm_upsert_contact.contact.gender` [extra → extra:gender] C=`` I=`M`
- FIELD `crm_upsert_contact.contact.initials` [derived/from_substitute → derived] C=`Д.` I=`Н.` · значение выведено из ПОДМЕНЫ; восстановление недостижимо
- FIELD `crm_upsert_contact.contact.name_latin` [other/misderived → name_partial] C=`Kuznetsov Dmitriy` I=`Kuznetsov Dmitrii`
- FIELD `crm_upsert_contact.contact.phone` [other/inflected → other/inflected] C=`+79628889900` I=`+79622889900`
- REPLY I: Отлично, оформляю всё сразу! Всё готово! Вот итог: 🚚 **Курьер вызван** (заявка `clm-1`) - **Адрес:** Сарапул, дом сто восемьдесят пять квартира пятьдесят шесть - **Получатель:** кузнецов дмитрий, +7 962 288 99 00 - **Интервал:** 4 сентября 2026, с 10:00 до 14:00 📋 **Карточка клиента** в CRM создана…

## correction-030|2 · correction · voice_raw · L1 ≠ · L3 ≠ · C′≈C нет · причина: **Б9-span**
- USER[1]: алло курьера наа адрес мончегорская трис три квартира пятьдесят шесть ой нет правильно мончегрская дом сто восемьдесят пять квартира пятьдесят шесть это в сарапул это кузнецов дмитрий телефон восемь девятьсот шестьдесят два восемест восемьдесят восемь девяно девять ноль ноль
- USER[2]: завтра с десятии до двух
- **LEAK** LOC `мончегорская трис три квартира пятьдесят шесть` — модель видела настоящее значение
- seen LOC `мончегрская дом сто восемьдесят пять квартира пятьдесят шесть` → `мончегрская улица Сиреневая 29, кв. 139`
- seen NAME `кузнецов дмитрий` → `Котов Артур`
- **LEAK** PHONE `восемь девятьсот шестьдесят два восемест восемьдесят восемь девяно девять ноль ноль` — модель видела настоящее значение
- C: `crm_upsert_contact` {'contact': {'last_name': 'Кузнецов', 'first_name': 'Дмитрий', 'initials': 'Д.', 'name_latin': 'Kuznetsov Dmitry', 'gender': 'M', 'phone': '+79628889900', 'address': {'city': 'Сарапул', 'street': 'Мо…
- C: `courier_book` {'address': {'locality': 'Сарапул', 'street': 'Мончегорская', 'building': '185', 'sflat': '56'}, 'contact': {'name': 'Кузнецов Дмитрий', 'phone': '+79628889900'}, 'interval': {'from': '2026-09-04T10:…
- I: — (без вызовов)
- C′: `courier_book` {'address': {'locality': 'Сарапул', 'street': 'Мончегорская', 'building': '185', 'sflat': '56'}, 'contact': {'name': 'Кузнецов Дмитрий', 'phone': '+79628889900'}, 'interval': {'from': '2026-09-04T10:…
- C′: `crm_upsert_contact` {'contact': {'last_name': 'Кузнецов', 'first_name': 'Дмитрий', 'initials': 'Д.', 'name_latin': 'Kuznetsov Dmitry', 'gender': 'M', 'phone': '+79628889900', 'address': {'city': 'Сарапул', 'street': 'Мо…
- FIELD `crm_upsert_contact.contact.address.city` [absent → absent:city] C=`Сарапул` I=``
- FIELD `crm_upsert_contact.contact.address.flat` [absent → absent:flat] C=`56` I=``
- FIELD `crm_upsert_contact.contact.address.house` [absent → absent:house] C=`185` I=``
- FIELD `crm_upsert_contact.contact.address.street` [absent → absent:street] C=`Мончегорская` I=``
- FIELD `crm_upsert_contact.contact.first_name` [absent → absent:first_name] C=`Дмитрий` I=``
- FIELD `crm_upsert_contact.contact.gender` [absent → absent:gender] C=`M` I=``
- FIELD `crm_upsert_contact.contact.initials` [absent → absent:initials] C=`Д.` I=``
- FIELD `crm_upsert_contact.contact.last_name` [absent → absent:last_name] C=`Кузнецов` I=``
- FIELD `crm_upsert_contact.contact.name_latin` [absent → absent:name_latin] C=`Kuznetsov Dmitry` I=``
- FIELD `crm_upsert_contact.contact.phone` [absent → absent:phone] C=`+79628889900` I=``
- FIELD `courier_book.address.building` [absent → absent:building] C=`185` I=``
- FIELD `courier_book.address.locality` [absent → absent:locality] C=`Сарапул` I=``
- FIELD `courier_book.address.sflat` [absent → absent:sflat] C=`56` I=``
- FIELD `courier_book.address.street` [absent → absent:street] C=`Мончегорская` I=``
- FIELD `courier_book.contact.name` [absent → absent:name] C=`Кузнецов Дмитрий` I=``
- FIELD `courier_book.contact.phone` [absent → absent:phone] C=`+79628889900` I=``
- REPLY I: Отлично, завтра 4 сентября с 10:00 до 14:00 — записал! Но вы не уточнили номер телефона 😊 Какой правильный — **8-962-288-99-00** или **8-962-888-99-00**?

## correction-031|0 · correction · sloppy · L1 = · L3 ≠ · C′≈C нет · причина: **other**
- USER[1]: добрый курьерра на адрес новвя 81 кв 6 нет не так правилньо нвоая 53кв6 это в сарапул это битюков олег телефон 89896866953
- USER[2]: в четверг после обеда
- **LEAK** LOC `новвя 81 кв 6` — модель видела настоящее значение
- **LEAK** LOC `нвоая 53кв6` — модель видела настоящее значение
- seen NAME `битюков олег` → `Карпов Савва`
- seen PHONE `89896866953` → `+79507373198`
- C: `courier_book` {'address': {'locality': 'Сарапул', 'street': 'Новая', 'building': '53', 'sflat': '6'}, 'contact': {'name': 'Битюков Олег', 'phone': '+79896866953'}, 'interval': {'from': '2026-09-03T13:00:00+04:00',…
- C: `crm_upsert_contact` {'contact': {'last_name': 'Битюков', 'first_name': 'Олег', 'initials': 'О.', 'name_latin': 'Bityukov Oleg', 'phone': '+79896866953', 'address': {'city': 'Сарапул', 'street': 'Новая', 'house': '53', '…
- I: `courier_book` written={'address': {'locality': 'Сарапул', 'street': 'Новая', 'building': '53', 'sflat': '6'}, 'contact': {'name': 'Карпов Савва', 'phone': '+79507373198'}, 'interval': {'from': '2026-09-03T14:00:00+04:00', 'to': '2026-09-03T18:00:00+04:00'}} → restored={'address': {'locality': 'Сарапул', 'street': 'Новая', 'building': '53', 'sflat': '6'}, 'contact': {'name': 'битюков олег', 'phone': '+79896866953'}, 'interval': {'from': '2026-09-03T14:00:00+04:00', 'to': '2026-09-03T18:00:00+04:00'}}
- I: `crm_upsert_contact` written={'contact': {'last_name': 'Карпов', 'first_name': 'Савва', 'initials': 'С.', 'name_latin': 'Karpov Savva', 'phone': '+79507373198', 'address': {'city': 'Сарапул', 'street': 'Новая', 'house': '53', 'flat': '6'}}} → restored={'contact': {'last_name': 'битюков', 'first_name': 'олег', 'initials': 'С.', 'name_latin': 'Bitiukov Oleg', 'phone': '+79896866953', 'address': {'city': 'Сарапул', 'street': 'Новая', 'house': '53', 'flat': '6'}}}
- C′: `crm_upsert_contact` {'contact': {'first_name': 'Олег', 'last_name': 'Битюков', 'initials': 'О.', 'name_latin': 'Bityukov Oleg', 'phone': '+79896866953', 'address': {'city': 'Сарапул', 'street': 'Новая', 'house': '53', '…
- C′: `courier_book` {'address': {'locality': 'Сарапул', 'street': 'Новая', 'building': '53', 'sflat': '6'}, 'contact': {'name': 'Битюков Олег', 'phone': '+79896866953'}, 'interval': {'from': '2026-09-03T13:00:00+04:00',…
- FIELD `crm_upsert_contact.contact.initials` [derived/from_substitute → derived] C=`О.` I=`С.` · значение выведено из ПОДМЕНЫ; восстановление недостижимо
- FIELD `crm_upsert_contact.contact.name_latin` [other/misderived → name_partial] C=`Bityukov Oleg` I=`Bitiukov Oleg`
- REPLY I: Сегодня четверг, 3 сентября. Назначу курьера на **послеобеденное время — с 14:00 до 18:00**. Оформляю заказ и карточку клиента! Всё готово! ✅ **Курьер вызван** (заявка `clm-1`): - 📍 Сарапул, ул. Новая, д. 53, кв. 6 - 👤 битюков олег, 89896866953 - 🕒 Сегодня, 3 сентября, с 14:00 до 18:00 Карточка кли…

## correction-031|1 · correction · sloppy · L1 ≠ · L3 ≠ · C′≈C нет · причина: **other**
- USER[1]: добрый курьерра на адрес новвя 81 кв 6 нет не так правилньо нвоая 53кв6 это в сарапул это битюков олег телефон 89896866953
- USER[2]: в четверг после обеда
- **LEAK** LOC `новвя 81 кв 6` — модель видела настоящее значение
- **LEAK** LOC `нвоая 53кв6` — модель видела настоящее значение
- seen NAME `битюков олег` → `Сазонов Демьян`
- seen PHONE `89896866953` → `+79078304393`
- C: `crm_upsert_contact` {'contact': {'last_name': 'Битюков', 'first_name': 'Олег', 'initials': 'О.', 'name_latin': 'Bityukov Oleg', 'gender': 'M', 'phone': '+79896866953', 'address': {'city': 'Сарапул', 'street': 'Новая', '…
- C: `courier_book` {'address': {'locality': 'Сарапул', 'street': 'Новая', 'building': '53', 'sflat': '6'}, 'contact': {'name': 'Битюков Олег', 'phone': '+79896866953'}, 'interval': {'from': '2026-09-03T13:00:00+04:00',…
- I: `courier_book` written={'address': {'locality': 'Сарапул', 'street': 'Новая', 'building': '53', 'sflat': '6'}, 'contact': {'name': 'Сазонов Демьян', 'phone': '+79078304393'}, 'interval': {'from': '2026-09-03T13:00:00+04:00', 'to': '2026-09-03T18:00:00+04:00'}} → restored={'address': {'locality': 'Сарапул', 'street': 'Новая', 'building': '53', 'sflat': '6'}, 'contact': {'name': 'битюков олег', 'phone': '+79896866953'}, 'interval': {'from': '2026-09-03T13:00:00+04:00', 'to': '2026-09-03T18:00:00+04:00'}}
- I: `crm_upsert_contact` written={'contact': {'last_name': 'Сазонов', 'first_name': 'Демьян', 'initials': 'Д.', 'name_latin': 'Sazonov Demyan', 'phone': '+79078304393', 'address': {'city': 'Сарапул', 'street': 'Новая', 'house': '53', 'flat': '6'}}} → restored={'contact': {'last_name': 'битюков', 'first_name': 'олег', 'initials': 'Д.', 'name_latin': 'Bitiukov Oleg', 'phone': '+79896866953', 'address': {'city': 'Сарапул', 'street': 'Новая', 'house': '53', 'flat': '6'}}}
- C′: `courier_book` {'address': {'locality': 'Сарапул', 'street': 'Новая', 'building': '53', 'sflat': '6'}, 'contact': {'name': 'Битюков Олег', 'phone': '+79896866953'}, 'interval': {'from': '2026-09-03T13:00:00+04:00',…
- C′: `crm_upsert_contact` {'contact': {'last_name': 'Битюков', 'first_name': 'Олег', 'initials': 'О.', 'name_latin': 'Bityukov Oleg', 'phone': '+79896866953', 'address': {'city': 'Сарапул', 'street': 'Новая', 'house': '53', '…
- FIELD `crm_upsert_contact.contact.gender` [absent → absent:gender] C=`M` I=``
- FIELD `crm_upsert_contact.contact.initials` [derived/from_substitute → derived] C=`О.` I=`Д.` · значение выведено из ПОДМЕНЫ; восстановление недостижимо
- FIELD `crm_upsert_contact.contact.name_latin` [other/misderived → name_partial] C=`Bityukov Oleg` I=`Bitiukov Oleg`
- REPLY I: Четверг — это сегодня, 3 сентября. Принимаю интервал **13:00–18:00**. Оформляю всё одновременно! Всё оформлено! ✅ **Вызов курьера** (заявка `clm-1`): - 📍 Сарапул, ул. Новая, д. 53, кв. 6 - 👤 битюков олег, 89896866953 - 🕐 Сегодня, 3 сентября, с 13:00 до 18:00 **Карточка клиента** в CRM также создана…

## correction-031|2 · correction · sloppy · L1 = · L3 ≠ · C′≈C нет · причина: **other**
- USER[1]: добрый курьерра на адрес новвя 81 кв 6 нет не так правилньо нвоая 53кв6 это в сарапул это битюков олег телефон 89896866953
- USER[2]: в четверг после обеда
- **LEAK** LOC `новвя 81 кв 6` — модель видела настоящее значение
- **LEAK** LOC `нвоая 53кв6` — модель видела настоящее значение
- seen NAME `битюков олег` → `Сорокин Алексей`
- seen PHONE `89896866953` → `+79612767871`
- C: `courier_book` {'address': {'locality': 'Сарапул', 'street': 'Новая', 'building': '53', 'sflat': '6'}, 'contact': {'name': 'Битюков Олег', 'phone': '+79896866953'}, 'interval': {'from': '2026-09-03T14:00:00+04:00',…
- C: `crm_upsert_contact` {'contact': {'last_name': 'Битюков', 'first_name': 'Олег', 'initials': 'О.', 'name_latin': 'Bityukov Oleg', 'phone': '+79896866953', 'gender': 'M', 'address': {'city': 'Сарапул', 'street': 'Новая', '…
- I: `courier_book` written={'address': {'locality': 'Сарапул', 'street': 'Новая', 'building': '53', 'sflat': '6'}, 'contact': {'name': 'Сорокин Алексей', 'phone': '+79612767871'}, 'interval': {'from': '2026-09-03T13:00:00+04:00', 'to': '2026-09-03T18:00:00+04:00'}} → restored={'address': {'locality': 'Сарапул', 'street': 'Новая', 'building': '53', 'sflat': '6'}, 'contact': {'name': 'битюков олег', 'phone': '+79896866953'}, 'interval': {'from': '2026-09-03T13:00:00+04:00', 'to': '2026-09-03T18:00:00+04:00'}}
- I: `crm_upsert_contact` written={'contact': {'first_name': 'Алексей', 'last_name': 'Сорокин', 'phone': '+79612767871', 'initials': 'А.', 'name_latin': 'Sorokin Aleksei', 'address': {'city': 'Сарапул', 'street': 'Новая', 'house': '53', 'flat': '6'}}} → restored={'contact': {'first_name': 'олег', 'last_name': 'битюков', 'phone': '+79896866953', 'initials': 'А.', 'name_latin': 'Bitiukov Oleg', 'address': {'city': 'Сарапул', 'street': 'Новая', 'house': '53', 'flat': '6'}}}
- C′: `courier_book` {'address': {'locality': 'Сарапул', 'street': 'Новая', 'building': '53', 'sflat': '6'}, 'contact': {'name': 'Битюков Олег', 'phone': '+79896866953'}, 'interval': {'from': '2026-09-03T13:00:00+04:00',…
- C′: `crm_upsert_contact` {'contact': {'last_name': 'Битюков', 'first_name': 'Олег', 'initials': 'О.', 'name_latin': 'Bityukov Oleg', 'phone': '+79896866953', 'address': {'city': 'Сарапул', 'street': 'Новая', 'house': '53', '…
- FIELD `crm_upsert_contact.contact.gender` [absent → absent:gender] C=`M` I=``
- FIELD `crm_upsert_contact.contact.initials` [derived/from_substitute → derived] C=`О.` I=`А.` · значение выведено из ПОДМЕНЫ; восстановление недостижимо
- FIELD `crm_upsert_contact.contact.name_latin` [other/misderived → name_partial] C=`Bityukov Oleg` I=`Bitiukov Oleg`
- REPLY I: Принято! Четверг — это сегодня, 3 сентября, интервал возьму **с 13:00 до 18:00**. Оформляю всё сразу! Всё оформлено! ✅ **Курьер вызван** (заявка `clm-1`): - 📍 Сарапул, ул. Новая, д. 53, кв. 6 - 👤 битюков олег, 89896866953 - 🕐 Сегодня, 3 сентября, с 13:00 до 18:00 Карточка клиента в CRM также обновл…

## correction-032|0 · correction · voice_itn · L1 = · L3 ≠ · C′≈C нет · причина: **residual**
- USER[1]: добрый день курьера на кирочная 129 квартира 59 нет не так правильно кирочная дом 101 квартира 59 это в ижевск это букин сергей телефон 8-982-513-94-60
- USER[2]: завтра с десяти до двух
- seen LOC `кирочная 129 квартира 59` → `улица Жасминовая 69, кв. 167`
- seen LOC `кирочная дом 101 квартира 59` → `улица Жасминовая 88, кв. 87`
- seen NAME `букин сергей` → `Сорокин Тимур`
- seen PHONE `8-982-513-94-60` → `+79621208582`
- C: `courier_book` {'address': {'locality': 'Ижевск', 'street': 'Кирочная', 'building': '101', 'sflat': '59'}, 'contact': {'name': 'Букин Сергей', 'phone': '+79825139460'}, 'interval': {'from': '2026-09-04T10:00:00+04:…
- C: `crm_upsert_contact` {'contact': {'last_name': 'Букин', 'first_name': 'Сергей', 'initials': 'С.', 'name_latin': 'Bukin Sergei', 'gender': 'M', 'phone': '+79825139460', 'address': {'city': 'Ижевск', 'street': 'Кирочная', …
- I: `courier_book` written={'address': {'locality': 'Ижевск', 'street': 'Жасминовая', 'building': '88', 'sflat': '87'}, 'contact': {'name': 'Сорокин Тимур', 'phone': '+79621208582'}, 'interval': {'from': '2026-09-04T10:00:00+04:00', 'to': '2026-09-04T14:00:00+04:00'}} → restored={'address': {'locality': 'Ижевск', 'street': 'Жасминовая', 'building': '101', 'sflat': '59'}, 'contact': {'name': 'букин сергей', 'phone': '+79825139460'}, 'interval': {'from': '2026-09-04T10:00:00+04:00', 'to': '2026-09-04T14:00:00+04:00'}} · residual={'address.street': ('жасминовая',)}
- I: `crm_upsert_contact` written={'contact': {'last_name': 'Сорокин', 'first_name': 'Тимур', 'initials': 'Т.', 'name_latin': 'Sorokin Timur', 'phone': '+79621208582', 'address': {'city': 'Ижевск', 'street': 'Жасминовая', 'house': '88', 'flat': '87'}}} → restored={'contact': {'last_name': 'букин', 'first_name': 'сергей', 'initials': 'Т.', 'name_latin': 'Bukin Sergei', 'phone': '+79825139460', 'address': {'city': 'Ижевск', 'street': 'кирочная', 'house': '101', 'flat': '59'}}}
- C′: `courier_book` {'address': {'locality': 'Ижевск', 'street': 'Кирочная', 'building': '101', 'sflat': '59'}, 'contact': {'name': 'Букин Сергей', 'phone': '+79825139460'}, 'interval': {'from': '2026-09-04T10:00:00+04:…
- FIELD `courier_book.address.street` [residual → loc_fake] C=`Кирочная` I=`Жасминовая` · подмена дошла до инструмента: жасминовая
- FIELD `crm_upsert_contact.contact.gender` [absent → absent:gender] C=`M` I=``
- FIELD `crm_upsert_contact.contact.initials` [derived/from_substitute → derived] C=`С.` I=`Т.` · значение выведено из ПОДМЕНЫ; восстановление недостижимо
- REPLY I: Оформляю всё одновременно! Всё готово! Вот итог: - 🚚 **Курьер вызван** — 4 сентября с 10:00 до 14:00 - 📍 **Адрес:** Ижевск, кирочная дом 101 квартира 59 - 👤 **Клиент:** букин сергей, 8-982-513-94-60 - 📋 **Карточка в CRM** обновлена - 🔖 **Номер заявки:** clm-1 Если понадобится что-то изменить — обра…

## correction-032|1 · correction · voice_itn · L1 = · L3 ≠ · C′≈C нет · причина: **other**
- USER[1]: добрый день курьера на кирочная 129 квартира 59 нет не так правильно кирочная дом 101 квартира 59 это в ижевск это букин сергей телефон 8-982-513-94-60
- USER[2]: завтра с десяти до двух
- seen LOC `кирочная 129 квартира 59` → `улица Ивовая 46, кв. 236`
- seen LOC `кирочная дом 101 квартира 59` → `улица Кедровая 91, кв. 124`
- seen NAME `букин сергей` → `Сазонов Савелий`
- seen PHONE `8-982-513-94-60` → `+79597777291`
- C: `courier_book` {'address': {'locality': 'Ижевск', 'street': 'Кирочная', 'building': '101', 'sflat': '59'}, 'contact': {'name': 'Букин Сергей', 'phone': '+79825139460'}, 'interval': {'from': '2026-09-04T10:00:00+04:…
- C: `crm_upsert_contact` {'contact': {'last_name': 'Букин', 'first_name': 'Сергей', 'initials': 'С.', 'name_latin': 'Bukin Sergei', 'phone': '+79825139460', 'address': {'city': 'Ижевск', 'street': 'Кирочная', 'house': '101',…
- I: `courier_book` written={'address': {'locality': 'Ижевск', 'street': 'Кедровая', 'building': '91', 'sflat': '124'}, 'contact': {'name': 'Сазонов Савелий', 'phone': '+79597777291'}, 'interval': {'from': '2026-09-04T10:00:00+04:00', 'to': '2026-09-04T14:00:00+04:00'}} → restored={'address': {'locality': 'Ижевск', 'street': 'кирочная', 'building': '101', 'sflat': '59'}, 'contact': {'name': 'букин сергей', 'phone': '+79825139460'}, 'interval': {'from': '2026-09-04T10:00:00+04:00', 'to': '2026-09-04T14:00:00+04:00'}}
- I: `crm_upsert_contact` written={'contact': {'last_name': 'Сазонов', 'first_name': 'Савелий', 'initials': 'С.', 'name_latin': 'Sazonov Saveliy', 'gender': 'M', 'phone': '+79597777291', 'address': {'city': 'Ижевск', 'street': 'Кедровая', 'house': '91', 'flat': '124'}}} → restored={'contact': {'last_name': 'букин', 'first_name': 'сергей', 'initials': 'С.', 'name_latin': 'Bukin Sergey', 'gender': 'M', 'phone': '+79825139460', 'address': {'city': 'Ижевск', 'street': 'кирочная', 'house': '101', 'flat': '59'}}}
- C′: `courier_book` {'address': {'locality': 'Ижевск', 'street': 'Кирочная', 'building': '101', 'sflat': '59'}, 'contact': {'name': 'Букин Сергей', 'phone': '+79825139460'}, 'interval': {'from': '2026-09-04T10:00:00+04:…
- C′: `crm_upsert_contact` {'contact': {'last_name': 'Букин', 'first_name': 'Сергей', 'initials': 'С.', 'name_latin': 'Bukin Sergei', 'phone': '+79825139460', 'gender': 'M', 'address': {'city': 'Ижевск', 'street': 'Кирочная', …
- FIELD `crm_upsert_contact.contact.gender` [extra → extra:gender] C=`` I=`M`
- FIELD `crm_upsert_contact.contact.name_latin` [other/misderived → name_partial] C=`Bukin Sergei` I=`Bukin Sergey`
- REPLY I: Принято! Оформляю всё одновременно — вызываю курьера и создаю карточку клиента. Всё оформлено! ✅ **Вызов курьера** (№ clm-1) - 📍 Ижевск, кирочная дом 101 квартира 59 - 👤 букин сергей, 8-982-513-94-60 - 🕙 4 сентября, с 10:00 до 14:00 **Карточка клиента** в CRM создана (№ c-1). Если нужно что-то изме…

## decompose-007|0 · decompose · sloppy · L1 = · L3 ≠ · C′≈C да · причина: **typo-normalised**
- USER[1]: дообрый курьера на глазов проезд неркасова 170 подъезд 6 квартира 119 это в глазов полуачтель лебедева ирина телефон +79875487262 завтра с десяти до двух
- seen LOC `глазов проезд неркасова 170 подъезд 6 квартира 119` → `глазов проезд Речной 143, подъезд 22, кв. 4`
- seen NAME `лебедева ирина` → `Устинова Шилова Инна`
- seen PHONE `+79875487262` → `+79528909552`
- C: `courier_book` {'address': {'locality': 'Глазов', 'street': 'проезд Некрасова', 'building': '170', 'porch': '6', 'sflat': '119'}, 'contact': {'name': 'Лебедева Ирина', 'phone': '+79875487262'}, 'interval': {'from':…
- I: `courier_book` written={'address': {'locality': 'Глазов', 'street': 'проезд Речной', 'building': '143', 'porch': '22', 'sflat': '4'}, 'contact': {'name': 'Шилова Инна', 'phone': '+79528909552'}, 'interval': {'from': '2026-09-04T10:00:00+03:00', 'to': '2026-09-04T14:00:00+03:00'}} → restored={'address': {'locality': 'Глазов', 'street': 'проезд неркасова', 'building': '170', 'porch': '6', 'sflat': '119'}, 'contact': {'name': 'лебедева ирина', 'phone': '+79875487262'}, 'interval': {'from': '2026-09-04T10:00:00+03:00', 'to': '2026-09-04T14:00:00+03:…
- C′: `courier_book` {'address': {'locality': 'Глазов', 'street': 'Некрасова', 'building': '170', 'porch': '6', 'sflat': '119'}, 'contact': {'name': 'Лебедева Ирина', 'phone': '+79875487262'}, 'interval': {'from': '2026-…
- FIELD `courier_book.address.street` [other/unbound → loc_street] C=`проезд Некрасова` I=`проезд неркасова`
- REPLY I: Оформляю вызов курьера — все данные есть, запускаю! Готово! Курьер вызван ✅ **Детали заказа (clm-1):** - 📍 Глазов, проезд неркасова 170 подъезд 6 квартира 119 - 👤 лебедева ирина, +79875487262 - 🗓 4 сентября 2026, с 10:00 до 14:00 Заявка принята, статус: *оценивается*. Как только курьер будет назнач…

## decompose-007|1 · decompose · sloppy · L1 = · L3 ≠ · C′≈C нет · причина: **residual**
- USER[1]: дообрый курьера на глазов проезд неркасова 170 подъезд 6 квартира 119 это в глазов полуачтель лебедева ирина телефон +79875487262 завтра с десяти до двух
- seen LOC `глазов проезд неркасова 170 подъезд 6 квартира 119` → `глазов проезд Кленовый 69, подъезд 9, кв. 230`
- seen NAME `лебедева ирина` → `Тарасова Цветкова Людмила`
- seen PHONE `+79875487262` → `+79113634572`
- C: `courier_book` {'address': {'locality': 'Глазов', 'street': 'проезд Некрасова', 'building': '170', 'porch': '6', 'sflat': '119'}, 'contact': {'name': 'Лебедева Ирина', 'phone': '+79875487262'}, 'interval': {'from':…
- I: `courier_book` written={'address': {'locality': 'Глазов', 'street': 'Кленовый проезд', 'building': '69', 'porch': '9', 'sflat': '230'}, 'contact': {'name': 'Тарасова-Цветкова Людмила', 'phone': '+79113634572'}, 'interval': {'from': '2026-09-04T10:00:00+04:00', 'to': '2026-09-04T14:… → restored={'address': {'locality': 'Глазов', 'street': 'неркасова проезд', 'building': '170', 'porch': '6', 'sflat': '119'}, 'contact': {'name': 'Тарасова-Цветкова ирина', 'phone': '+79875487262'}, 'interval': {'from': '2026-09-04T10:00:00+04:00', 'to': '2026-09-04T14:… · residual={'contact.name': ('тарасова', 'цветкова')}
- C′: `courier_book` {'address': {'locality': 'Глазов', 'street': 'проезд Некрасова', 'building': '170', 'porch': '6', 'sflat': '119'}, 'contact': {'name': 'Лебедева Ирина', 'phone': '+79875487262'}, 'interval': {'from':…
- FIELD `courier_book.address.street` [other/unbound → loc_street] C=`проезд Некрасова` I=`неркасова проезд`
- FIELD `courier_book.contact.name` [residual → name_partial] C=`Лебедева Ирина` I=`Тарасова-Цветкова ирина` · подмена дошла до инструмента: тарасова
- REPLY I: Оформляю вызов курьера — всё есть, уточнять нечего! Готово! Курьер заказан ✅ **Детали вызова:** - 📍 Глазов, проезд неркасова 170 подъезд 6 квартира 119 - 👤 Тарасова-Цветкова ирина, +79875487262 - 🗓 4 сентября 2026, с 10:00 до 14:00 - 🆔 Заявка: **clm-1** Курьер прибудет в указанный интервал. Если ну…

## decompose-007|2 · decompose · sloppy · L1 = · L3 ≠ · C′≈C да · причина: **typo-normalised**
- USER[1]: дообрый курьера на глазов проезд неркасова 170 подъезд 6 квартира 119 это в глазов полуачтель лебедева ирина телефон +79875487262 завтра с десяти до двух
- seen LOC `глазов проезд неркасова 170 подъезд 6 квартира 119` → `глазов проезд Берёзовый 47, подъезд 18, кв. 40`
- seen NAME `лебедева ирина` → `Гущина Беляева Лилия`
- seen PHONE `+79875487262` → `+79551441207`
- C: `courier_book` {'address': {'locality': 'Глазов', 'street': 'проезд Некрасова', 'building': '170', 'porch': '6', 'sflat': '119'}, 'contact': {'name': 'Лебедева Ирина', 'phone': '+79875487262'}, 'interval': {'from':…
- I: `courier_book` written={'address': {'locality': 'Глазов', 'street': 'проезд Берёзовый', 'building': '47', 'porch': '18', 'sflat': '40'}, 'contact': {'name': 'Гущина Лилия', 'phone': '+79551441207'}, 'interval': {'from': '2026-09-04T10:00:00+04:00', 'to': '2026-09-04T14:00:00+04:00'… → restored={'address': {'locality': 'Глазов', 'street': 'проезд неркасова', 'building': '170', 'porch': '6', 'sflat': '119'}, 'contact': {'name': 'полуачтель ирина', 'phone': '+79875487262'}, 'interval': {'from': '2026-09-04T10:00:00+04:00', 'to': '2026-09-04T14:00:00+0…
- C′: `courier_book` {'address': {'locality': 'Глазов', 'street': 'проезд Некрасова', 'building': '170', 'porch': '6', 'sflat': '119'}, 'contact': {'name': 'Лебедева Ирина', 'phone': '+79875487262'}, 'interval': {'from':…
- FIELD `courier_book.address.street` [other/unbound → loc_street] C=`проезд Некрасова` I=`проезд неркасова`
- FIELD `courier_book.contact.name` [other/inflected → name_partial] C=`Лебедева Ирина` I=`полуачтель ирина`
- REPLY I: Оформляю вызов курьера, одну секунду! Готово! Курьер вызван ✅ **Детали заказа:** - 📍 **Адрес:** г. Глазов, проезд неркасова 170 подъезд 6 квартира 119 - 👤 **Получатель:** полуачтель ирина, +79875487262 - 🗓 **Дата:** 4 сентября 2026 г. - ⏰ **Интервал:** с 10:00 до 14:00 - 🔖 **Номер заявки:** clm-1 Е…

## decompose-008|1 · decompose · sloppy · L1 = · L3 ≠ · C′≈C да · причина: **other**
- USER[1]: привет проведите оплату 620 рублей карта 4276945545660784 срок 09/27 дерржатель пётр ерохин
- seen CARD `4276945545660784` → `0761 8452 6116 2702`
- seen NAME `пётр ерохин` → `Артём Юдин`
- C: `payment_create` {'amount': {'value': '620.00', 'currency': 'RUB'}, 'payment_method_data': {'type': 'bank_card', 'card': {'number': '4276945545660784', 'expiry_month': '09', 'expiry_year': '2027', 'cardholder': 'PETR…
- I: `payment_create` written={'amount': {'value': '620.00', 'currency': 'RUB'}, 'payment_method_data': {'type': 'bank_card', 'card': {'number': '0761845261162702', 'expiry_month': '09', 'expiry_year': '2027', 'cardholder': 'ARTEM YUDIN'}}} → restored={'amount': {'value': '620.00', 'currency': 'RUB'}, 'payment_method_data': {'type': 'bank_card', 'card': {'number': '4276945545660784', 'expiry_month': '09', 'expiry_year': '2027', 'cardholder': 'PETR EROXIN'}}}
- C′: `payment_create` {'amount': {'value': '620.00', 'currency': 'RUB'}, 'payment_method_data': {'type': 'bank_card', 'card': {'number': '4276945545660784', 'expiry_month': '09', 'expiry_year': '2027', 'cardholder': 'PETR…
- FIELD `payment_create.payment_method_data.card.cardholder` [other/misderived → name_partial] C=`PETR EROKHIN` I=`PETR EROXIN`
- REPLY I: Провожу платёж! Держатель карты транслитерирован латиницей заглавными: **PETR EROXIN**. Платёж создан! Вот детали: - **ID платежа:** pay-1 - **Статус:** ожидает подтверждения (pending) - **Сумма:** 620,00 ₽ - **Карта:** **** **** **** 0784, срок 09/2027 - **Держатель:** PETR EROXIN Если потребуется…

## decompose-016|0 · decompose · clean · L1 = · L3 ≠ · C′≈C да · причина: **other**
- USER[1]: Здравствуйте. курьера на Ижевск, Маяковского, 141 подъезд 5 кв. 175 это в ижевск получатель Вольнов Евгений телефон +7 916 077-55-29 завтра с десяти до двух.
- seen LOC `Ижевск, Маяковского, 141 подъезд 5 кв. 175` → `Ижевск, Игната Беляева, улицу Озёрную 44, подъезд 15, кв. 12`
- seen NAME `Вольнов Евгений` → `Цветков Всеволод`
- seen PHONE `+7 916 077-55-29` → `+79208542781`
- C: `courier_book` {'address': {'locality': 'Ижевск', 'street': 'Маяковского', 'building': '141', 'porch': '5', 'sflat': '175'}, 'contact': {'name': 'Вольнов Евгений', 'phone': '+79160775529'}, 'interval': {'from': '20…
- I: `courier_book` written={'address': {'locality': 'Ижевск', 'street': 'Озёрная', 'building': '44', 'porch': '15', 'sflat': '12'}, 'contact': {'name': 'Цветков Всеволод', 'phone': '+79208542781'}, 'interval': {'from': '2026-09-04T10:00:00+04:00', 'to': '2026-09-04T14:00:00+04:00'}} → restored={'address': {'locality': 'Ижевск', 'street': '141 подъезд 5 кв. 175', 'building': '141', 'porch': '5', 'sflat': '175'}, 'contact': {'name': 'Вольнов Евгений', 'phone': '+79160775529'}, 'interval': {'from': '2026-09-04T10:00:00+04:00', 'to': '2026-09-04T14:00:…
- C′: `courier_book` {'address': {'locality': 'Ижевск', 'street': 'Маяковского', 'building': '141', 'porch': '5', 'sflat': '175'}, 'contact': {'name': 'Вольнов Евгений', 'phone': '+79160775529'}, 'interval': {'from': '20…
- FIELD `courier_book.address.street` [composed → loc_other] C=`Маяковского` I=`141 подъезд 5 кв. 175`
- REPLY I: Оформляю вызов курьера, всё необходимое есть! Готово! Курьер вызван. Детали заявки: - **Номер заявки:** clm-1 - **Статус:** оценивается - **Адрес:** Ижевск, 141 подъезд 5 кв. 175 - **Получатель:** Вольнов Евгений, +7 916 077-55-29 - **Интервал:** 4 сентября 2026, с 10:00 до 14:00 (МСК+1, Ижевск) Ес…

## decompose-016|1 · decompose · clean · L1 = · L3 ≠ · C′≈C да · причина: **other**
- USER[1]: Здравствуйте. курьера на Ижевск, Маяковского, 141 подъезд 5 кв. 175 это в ижевск получатель Вольнов Евгений телефон +7 916 077-55-29 завтра с десяти до двух.
- seen LOC `Ижевск, Маяковского, 141 подъезд 5 кв. 175` → `Ижевск, Романа Беляева, улицу Еловую 119, подъезд 10, кв. 116`
- seen NAME `Вольнов Евгений` → `Тихонов Захар`
- seen PHONE `+7 916 077-55-29` → `+79389535033`
- C: `courier_book` {'address': {'locality': 'Ижевск', 'street': 'Маяковского', 'building': '141', 'porch': '5', 'sflat': '175'}, 'contact': {'name': 'Вольнов Евгений', 'phone': '+79160775529'}, 'interval': {'from': '20…
- I: `courier_book` written={'address': {'locality': 'Ижевск', 'street': 'Еловая', 'building': '119', 'porch': '10', 'sflat': '116'}, 'contact': {'name': 'Тихонов Захар', 'phone': '+79389535033'}, 'interval': {'from': '2026-09-04T10:00:00+04:00', 'to': '2026-09-04T14:00:00+04:00'}} → restored={'address': {'locality': 'Ижевск', 'street': '141 подъезд 5 кв. 175', 'building': '141', 'porch': '5', 'sflat': '175'}, 'contact': {'name': 'Вольнов Евгений', 'phone': '+79160775529'}, 'interval': {'from': '2026-09-04T10:00:00+04:00', 'to': '2026-09-04T14:00:…
- C′: `courier_book` {'address': {'locality': 'Ижевск', 'street': 'Маяковского', 'building': '141', 'porch': '5', 'sflat': '175'}, 'contact': {'name': 'Вольнов Евгений', 'phone': '+79160775529'}, 'interval': {'from': '20…
- FIELD `courier_book.address.street` [composed → loc_other] C=`Маяковского` I=`141 подъезд 5 кв. 175`
- REPLY I: Здравствуйте! Оформляю вызов курьера — всё необходимое есть, вызываю! Готово! Курьер вызван. Вот детали заявки: - **Номер заявки:** clm-1 - **Статус:** оценивается - **Адрес:** Ижевск, 141 подъезд 5 кв. 175 - **Получатель:** Вольнов Евгений, +7 916 077-55-29 - **Дата и время:** 4 сентября 2026 г., …

## decompose-016|2 · decompose · clean · L1 = · L3 ≠ · C′≈C да · причина: **other**
- USER[1]: Здравствуйте. курьера на Ижевск, Маяковского, 141 подъезд 5 кв. 175 это в ижевск получатель Вольнов Евгений телефон +7 916 077-55-29 завтра с десяти до двух.
- seen LOC `Ижевск, Маяковского, 141 подъезд 5 кв. 175` → `Ижевск, Даниила Беляева, улицу Грушевую 56, подъезд 18, кв. 70`
- seen NAME `Вольнов Евгений` → `Бирюков Николай`
- seen PHONE `+7 916 077-55-29` → `+79129515412`
- C: `courier_book` {'address': {'locality': 'Ижевск', 'street': 'Маяковского', 'building': '141', 'porch': '5', 'sflat': '175'}, 'contact': {'name': 'Вольнов Евгений', 'phone': '+79160775529'}, 'interval': {'from': '20…
- I: `courier_book` written={'address': {'locality': 'Ижевск', 'street': 'Грушевая', 'building': '56', 'porch': '18', 'sflat': '70'}, 'contact': {'name': 'Бирюков Николай', 'phone': '+79129515412'}, 'interval': {'from': '2026-09-04T10:00:00+04:00', 'to': '2026-09-04T14:00:00+04:00'}} → restored={'address': {'locality': 'Ижевск', 'street': '141 подъезд 5 кв. 175', 'building': '141', 'porch': '5', 'sflat': '175'}, 'contact': {'name': 'Вольнов Евгений', 'phone': '+79160775529'}, 'interval': {'from': '2026-09-04T10:00:00+04:00', 'to': '2026-09-04T14:00:…
- C′: `courier_book` {'address': {'locality': 'Ижевск', 'street': 'Маяковского', 'building': '141', 'porch': '5', 'sflat': '175'}, 'contact': {'name': 'Вольнов Евгений', 'phone': '+79160775529'}, 'interval': {'from': '20…
- FIELD `courier_book.address.street` [composed → loc_other] C=`Маяковского` I=`141 подъезд 5 кв. 175`
- REPLY I: Здравствуйте! Принимаю заказ — вызываю курьера на завтра, 4 сентября, с 10:00 до 14:00 (Ижевск, UTC+4). Готово! Курьер оформлен. 🎉 **Детали вызова:** - 📍 Ижевск, 141 подъезд 5 кв. 175 - 👤 Получатель: Вольнов Евгений, +7 916 077-55-29 - 📅 4 сентября 2026 г., с **10:00 до 14:00** - 🆔 Номер заявки: **…

## decompose-019|0 · decompose · sloppy · L1 = · L3 ≠ · C′≈C да · причина: **control_erred**
- USER[1]: добрый курьера на абакан луогвая 5 подъезд 7 кв 30 это в абпкан получатель миллер валерий телефон 8 952 279 93 12 завтра с десяти до двкх
- seen LOC `абакан луогвая 5 подъезд 7 кв 30` → `абакан Углича, улицы Вишнёвой 51, подъезд 2, кв. 202`
- seen NAME `миллер валерий` → `Наумов Антон`
- seen PHONE `8 952 279 93 12` → `+79112068883`
- C: `courier_book` {'address': {'locality': 'Абакан', 'street': 'Луговая', 'building': '5', 'porch': '7', 'sflat': '30'}, 'contact': {'name': 'Миллер Валерий', 'phone': '+79522799312'}, 'interval': {'from': '2026-09-04…
- I: `courier_book` written={'address': {'locality': 'Абакан', 'street': 'Вишнёвая', 'building': '51', 'porch': '2', 'sflat': '202'}, 'contact': {'name': 'Наумов Антон', 'phone': '+79112068883'}, 'interval': {'from': '2026-09-04T10:00:00+07:00', 'to': '2026-09-04T14:00:00+07:00'}} → restored={'address': {'locality': 'Абакан', 'street': 'луогвая', 'building': '5', 'porch': '7', 'sflat': '30'}, 'contact': {'name': 'миллер валерий', 'phone': '+79522799312'}, 'interval': {'from': '2026-09-04T10:00:00+07:00', 'to': '2026-09-04T14:00:00+07:00'}}
- C′: `courier_book` {'address': {'locality': 'Абакан', 'street': 'Луговая', 'building': '5', 'porch': '7', 'sflat': '30'}, 'contact': {'name': 'Миллер Валерий', 'phone': '+79522799312'}, 'interval': {'from': '2026-09-04…
- FIELD `courier_book.address.street` [control_erred/i1 → control_erred] C=`Луговая` I=`луогвая` · контроль ошибся; шлюз восстановил эталон корпуса
- REPLY I: Вызываю курьера, всё понял! Готово! Курьер оформлен ✅ **Детали заявки:** - 📍 Абакан, луогвая 5 подъезд 7 кв 30 - 👤 миллер валерий, 8 952 279 93 12 - 🗓 4 сентября 2026 г., с 10:00 до 14:00 (по Красноярскому времени) - 🆔 Номер заявки: **clm-1** Если нужно что-то изменить — скажите!

## decompose-019|1 · decompose · sloppy · L1 = · L3 ≠ · C′≈C да · причина: **control_erred**
- USER[1]: добрый курьера на абакан луогвая 5 подъезд 7 кв 30 это в абпкан получатель миллер валерий телефон 8 952 279 93 12 завтра с десяти до двкх
- seen LOC `абакан луогвая 5 подъезд 7 кв 30` → `абакан Торжка, улицы Абрикосовой 94, подъезд 12, кв. 18`
- seen NAME `миллер валерий` → `Юдин Савелий`
- seen PHONE `8 952 279 93 12` → `+79225687565`
- C: `courier_book` {'address': {'locality': 'Абакан', 'street': 'Луговая', 'building': '5', 'porch': '7', 'sflat': '30'}, 'contact': {'name': 'Миллер Валерий', 'phone': '+79522799312'}, 'interval': {'from': '2026-09-04…
- I: `courier_book` written={'address': {'locality': 'Абакан', 'street': 'Абрикосовая', 'building': '94', 'porch': '12', 'sflat': '18'}, 'contact': {'name': 'Юдин Савелий', 'phone': '+79225687565'}, 'interval': {'from': '2026-09-04T10:00:00+07:00', 'to': '2026-09-04T14:00:00+07:00'}} → restored={'address': {'locality': 'Абакан', 'street': 'луогвая', 'building': '5', 'porch': '7', 'sflat': '30'}, 'contact': {'name': 'миллер валерий', 'phone': '+79522799312'}, 'interval': {'from': '2026-09-04T10:00:00+07:00', 'to': '2026-09-04T14:00:00+07:00'}}
- C′: `courier_book` {'address': {'locality': 'Абакан', 'street': 'Луговая', 'building': '5', 'porch': '7', 'sflat': '30'}, 'contact': {'name': 'Миллер Валерий', 'phone': '+79522799312'}, 'interval': {'from': '2026-09-04…
- FIELD `courier_book.address.street` [control_erred/i1 → control_erred] C=`Луговая` I=`луогвая` · контроль ошибся; шлюз восстановил эталон корпуса
- REPLY I: Всё понял, оформляю вызов курьера в Абакан! Курьер вызван! 🎉 **Детали заказа (clm-1):** - 📍 **Адрес:** Абакан, луогвая 5 подъезд 7 кв 30 - 👤 **Получатель:** миллер валерий, 8 952 279 93 12 - 🕙 **Время:** завтра, 4 сентября, с 10:00 до 14:00 (по местному времени) - 📋 **Статус:** оформляется Если пот…

## decompose-025|0 · decompose · voice_raw · L1 ≠ · L3 ≠ · C′≈C нет · причина: **other**
- USER[1]: алло курьераа на глазов проезд октябрьский семнадцать шестой подъезд квартира восемь это в глазов получатель громова марина телефон восемь девятьсот пятьдесят пятьдесят пяять пятьдесят шесть шестьдесят семь семь в четверг с двуух до шести
- seen LOC `глазов проезд октябрьский семнадцать шестой подъезд квартира восемь` → `глазов проезд Мятный 77, подъезд 12, кв. 19`
- seen NAME `громова марина` → `Осипова Маргарита`
- seen PHONE `восемь девятьсот пятьдесят пятьдесят пяять пятьдесят шесть шестьдесят семь семь` → `+79227831597`
- C: — (без вызовов)
- I: `courier_book` written={'address': {'locality': 'Глазов', 'street': 'Мятный проезд', 'building': '77', 'porch': '12', 'sflat': '19'}, 'contact': {'name': 'Осипова Маргарита', 'phone': '+79227831597'}, 'interval': {'from': '2026-09-03T14:00:00+04:00', 'to': '2026-09-03T18:00:00+04:0… → restored={'address': {'locality': 'Глазов', 'street': 'октябрьский проезд', 'building': '17', 'porch': '6', 'sflat': '8'}, 'contact': {'name': 'громова марина', 'phone': '+79505556677'}, 'interval': {'from': '2026-09-03T14:00:00+04:00', 'to': '2026-09-03T18:00:00+04:0…
- C′: `courier_book` {'address': {'locality': 'Глазов', 'street': 'Октябрьский проезд', 'building': '17', 'porch': '6', 'sflat': '8'}, 'contact': {'name': 'Громова Марина', 'phone': '+79005556677'}, 'interval': {'from': …
- FIELD `courier_book.address.building` [extra → extra:building] C=`` I=`17`
- FIELD `courier_book.address.locality` [extra → extra:locality] C=`` I=`Глазов`
- FIELD `courier_book.address.porch` [extra → extra:porch] C=`` I=`6`
- FIELD `courier_book.address.sflat` [extra → extra:sflat] C=`` I=`8`
- FIELD `courier_book.address.street` [extra → extra:street] C=`` I=`октябрьский проезд`
- FIELD `courier_book.contact.name` [extra → extra:name] C=`` I=`громова марина`
- FIELD `courier_book.contact.phone` [extra → extra:phone] C=`` I=`+79505556677`
- REPLY I: Принял! Оформляю вызов курьера — все данные есть, вызываю! Готово! Курьер вызван ✅ **Детали заказа (clm-1):** - 📍 Глазов, проезд октябрьский семнадцать шестой подъезд квартира восемь - 👤 громова марина, восемь девятьсот пятьдесят пятьдесят пяять пятьдесят шесть шестьдесят семь семь - 🕑 Сегодня, чет…

## decompose-025|2 · decompose · voice_raw · L1 = · L3 ≠ · C′≈C нет · причина: **control_erred**
- USER[1]: алло курьераа на глазов проезд октябрьский семнадцать шестой подъезд квартира восемь это в глазов получатель громова марина телефон восемь девятьсот пятьдесят пятьдесят пяять пятьдесят шесть шестьдесят семь семь в четверг с двуух до шести
- seen LOC `глазов проезд октябрьский семнадцать шестой подъезд квартира восемь` → `глазов проезд Лавандовый 189, подъезд 12, кв. 23`
- seen NAME `громова марина` → `Панова Жанна`
- seen PHONE `восемь девятьсот пятьдесят пятьдесят пяять пятьдесят шесть шестьдесят семь семь` → `+79639580280`
- C: `courier_book` {'address': {'locality': 'Глазов', 'street': 'Октябрьский проезд', 'building': '17', 'porch': '6', 'sflat': '8'}, 'contact': {'name': 'Громова Марина', 'phone': '+79005556677'}, 'interval': {'from': …
- I: `courier_book` written={'address': {'locality': 'Глазов', 'street': 'Лавандовый проезд', 'building': '189', 'porch': '12', 'sflat': '23'}, 'contact': {'name': 'Панова Жанна', 'phone': '+79639580280'}, 'interval': {'from': '2026-09-03T14:00:00+04:00', 'to': '2026-09-03T18:00:00+04:0… → restored={'address': {'locality': 'Глазов', 'street': 'октябрьский проезд', 'building': '17', 'porch': '6', 'sflat': '8'}, 'contact': {'name': 'громова марина', 'phone': '+79505556677'}, 'interval': {'from': '2026-09-03T14:00:00+04:00', 'to': '2026-09-03T18:00:00+04:0…
- C′: `courier_book` {'address': {'locality': 'Глазов', 'street': 'Октябрьский проезд', 'building': '17', 'porch': '6', 'sflat': '8'}, 'contact': {'name': 'Громова Марина', 'phone': '+79005556677'}, 'interval': {'from': …
- FIELD `courier_book.contact.phone` [control_erred/i3 → control_erred] C=`+79005556677` I=`+79505556677` · контроль ошибся; шлюз восстановил эталон корпуса
- REPLY I: Вызываю курьера, минуту! Готово! Курьер оформлен ✅ **Детали вызова:** - 📍 Глазов, пр. проезд октябрьский семнадцать шестой, д. 17, подъезд 6, кв. 8 - 👤 громова марина, восемь девятьсот пятьдесят пятьдесят пяять пятьдесят шесть шестьдесят семь семь - 🗓 Сегодня, четверг 3 сентября, с **14:00 до 18:00…

## decompose-029|1 · decompose · clean · L1 = · L3 ≠ · C′≈C да · причина: **other**
- USER[1]: Добрый день! проведите оплату 450 рублей карта 5469 5614 0463 3756 срок 07/30 держатель Валерий Миллер.
- seen CARD `5469 5614 0463 3756` → `0886 1410 4508 4861`
- seen NAME `Валерий Миллер` → `Никита Панов`
- C: `payment_create` {'amount': {'value': '450.00', 'currency': 'RUB'}, 'payment_method_data': {'type': 'bank_card', 'card': {'number': '5469561404633756', 'expiry_month': '07', 'expiry_year': '2030', 'cardholder': 'VALE…
- I: `payment_create` written={'amount': {'value': '450.00', 'currency': 'RUB'}, 'payment_method_data': {'type': 'bank_card', 'card': {'number': '0886141045084861', 'expiry_month': '07', 'expiry_year': '2030', 'cardholder': 'NIKITA PANOV'}}} → restored={'amount': {'value': '450.00', 'currency': 'RUB'}, 'payment_method_data': {'type': 'bank_card', 'card': {'number': '5469561404633756', 'expiry_month': '07', 'expiry_year': '2030', 'cardholder': 'VALERII MILLER'}}}
- C′: `payment_create` {'amount': {'value': '450.00', 'currency': 'RUB'}, 'payment_method_data': {'type': 'bank_card', 'card': {'number': '5469561404633756', 'expiry_month': '07', 'expiry_year': '2030', 'cardholder': 'VALE…
- FIELD `payment_create.payment_method_data.card.cardholder` [other/misderived → name_partial] C=`VALERIY MILLER` I=`VALERII MILLER`
- REPLY I: Добрый день! Провожу платёж прямо сейчас. Платёж создан! Вот детали: | Параметр | Значение | |---|---| | **ID платежа** | pay-1 | | **Статус** | 🕐 В обработке (pending) | | **Сумма** | 450.00 RUB | | **Карта** | **** **** **** 3756 | | **Держатель** | VALERII MILLER | | **Срок действия** | 07/2030 …

## decompose-029|2 · decompose · clean · L1 ≠ · L3 ≠ · C′≈C нет · причина: **other**
- USER[1]: Добрый день! проведите оплату 450 рублей карта 5469 5614 0463 3756 срок 07/30 держатель Валерий Миллер.
- seen CARD `5469 5614 0463 3756` → `0119 7314 0369 2658`
- seen NAME `Валерий Миллер` → `Назар Осипов`
- C: — (без вызовов)
- I: `payment_create` written={'amount': {'value': '450.00', 'currency': 'RUB'}, 'payment_method_data': {'type': 'bank_card', 'card': {'number': '0119731403692658', 'expiry_month': '07', 'expiry_year': '2030', 'cardholder': 'NAZAR OSIPOV'}}} → restored={'amount': {'value': '450.00', 'currency': 'RUB'}, 'payment_method_data': {'type': 'bank_card', 'card': {'number': '5469561404633756', 'expiry_month': '07', 'expiry_year': '2030', 'cardholder': 'VALERII MILLER'}}}
- C′: `payment_create` {'amount': {'value': '450.00', 'currency': 'RUB'}, 'payment_method_data': {'type': 'bank_card', 'card': {'number': '5469561404633756', 'expiry_month': '07', 'expiry_year': '2030', 'cardholder': 'VALE…
- FIELD `payment_create.payment_method_data.card.cardholder` [extra → extra:cardholder] C=`` I=`VALERII MILLER`
- FIELD `payment_create.payment_method_data.card.number` [extra → extra:number] C=`` I=`5469561404633756`
- REPLY I: Добрый день! Провожу платёж, одну секунду. Платёж создан! Вот детали: | Параметр | Значение | |---|---| | **ID платежа** | pay-1 | | **Статус** | ⏳ Pending (в обработке) | | **Сумма** | 450,00 ₽ | | **Карта** | **** **** **** 3756 | | **Держатель** | VALERII MILLER | | **Срок действия** | 07/2030 |…

## decompose-033|0 · decompose · voice_raw · L1 = · L3 ≠ · C′≈C да · причина: **residual**
- USER[1]: алло сверьте паспорт сорок девятнадцать трииста тринадцать пятьсот пятьдесят девять выдан гу мвд россии по краснодарскому краю код подразделенияя сто сорок семь шестьсот пятьдесят семь сниилс ноль семьдесят три двести пейсят три ноль восемьдесят семь сорок восемсь кукушкин валерий михайлович
- seen PASSPORT `сорок девятнадцать трииста тринадцать пятьсот пятьдесят девять` → `00 22 350546`
- seen SNILS `ноль семьдесят три двести пейсят три ноль восемьдесят семь сорок восемсь` → `ноль семьдесят три двести пейсят три ноль восемьдесят семь сорок Гущин Карпов Олег Степанович`
- seen NAME `кукушкин валерий михайлович` → `Гущин Карпов Олег Степанович`
- C: `passport_verify` {'passport': {'series': '4919', 'number': '313559', 'issued_by': 'ГУ МВД России по Краснодарскому краю', 'department_code': '147-657'}, 'person': {'last_name': 'Кукушкин', 'first_name': 'Валерий', 'm…
- I: `passport_verify` written={'passport': {'series': '0022', 'number': '350546', 'issued_by': 'ГУ МВД России по Краснодарскому краю', 'department_code': '147-657'}, 'person': {'last_name': 'Гущин-Карпов', 'first_name': 'Олег', 'middle_name': 'Степанович'}, 'snils': '073-253-087 40'} → restored={'passport': {'series': '4019', 'number': '313559', 'issued_by': 'ГУ МВД России по Краснодарскому краю', 'department_code': '147-657'}, 'person': {'last_name': 'Гущин-Карпов', 'first_name': 'валерий', 'middle_name': 'михайлович'}, 'snils': '073-253-087 40'} · residual={'person.last_name': ('гущин', 'карпов')} · refusal=snils_checksum
- C′: `passport_verify` {'passport': {'series': '4919', 'number': '313559', 'issued_by': 'ГУ МВД России по Краснодарскому краю', 'department_code': '147-657'}, 'person': {'last_name': 'Кукушкин', 'first_name': 'Валерий', 'm…
- FIELD `passport_verify.passport.series` [control_erred/i1 → control_erred] C=`4919` I=`4019` · контроль ошибся; шлюз восстановил эталон корпуса
- FIELD `passport_verify.person.last_name` [residual → name_lemma] C=`Кукушкин` I=`Гущин-Карпов` · подмена дошла до инструмента: гущин
- FIELD `passport_verify.snils` [validated_refused/snils_checksum → validated_refused] C=`073-253-087 48` I=`073-253-087 40`
- REPLY I: Понял, сверяю! Разобрал данные: - **Серия:** 0022, **Номер:** 350546 - **Выдан:** ГУ МВД России по Краснодарскому краю - **Код подразделения:** 147-657 - **СНИЛС:** 073-253-087 40 - **ФИО:** Гущин-Карпов валерий михайлович По паспорту и ФИО ошибок нет, однако **СНИЛС не прошёл проверку контрольной …

## decompose-033|1 · decompose · voice_raw · L1 = · L3 ≠ · C′≈C да · причина: **residual**
- USER[1]: алло сверьте паспорт сорок девятнадцать трииста тринадцать пятьсот пятьдесят девять выдан гу мвд россии по краснодарскому краю код подразделенияя сто сорок семь шестьсот пятьдесят семь сниилс ноль семьдесят три двести пейсят три ноль восемьдесят семь сорок восемсь кукушкин валерий михайлович
- seen PASSPORT `сорок девятнадцать трииста тринадцать пятьсот пятьдесят девять` → `00 03 037093`
- seen SNILS `ноль семьдесят три двести пейсят три ноль восемьдесят семь сорок восемсь` → `ноль семьдесят три двести пейсят три ноль восемьдесят семь сорок Осипов Котов Николай Максимович`
- seen NAME `кукушкин валерий михайлович` → `Осипов Котов Николай Максимович`
- C: `passport_verify` {'passport': {'series': '4919', 'number': '313559', 'issued_by': 'ГУ МВД России по Краснодарскому краю', 'department_code': '147-657'}, 'person': {'last_name': 'Кукушкин', 'first_name': 'Валерий', 'm…
- I: `passport_verify` written={'passport': {'series': '0003', 'number': '037093', 'issued_by': 'ГУ МВД России по Краснодарскому краю', 'department_code': '147-657'}, 'person': {'last_name': 'Осипов-Котов', 'first_name': 'Николай', 'middle_name': 'Максимович'}, 'snils': '073-253-087 40'} → restored={'passport': {'series': '4019', 'number': '313559', 'issued_by': 'ГУ МВД России по Краснодарскому краю', 'department_code': '147-657'}, 'person': {'last_name': 'Осипов-Котов', 'first_name': 'валерий', 'middle_name': 'михайлович'}, 'snils': '073-253-087 40'} · residual={'person.last_name': ('котов', 'осипов')} · refusal=snils_checksum
- C′: `passport_verify` {'passport': {'series': '4919', 'number': '313559', 'issued_by': 'ГУ МВД России по Краснодарскому краю', 'department_code': '147-657'}, 'person': {'last_name': 'Кукушкин', 'first_name': 'Валерий', 'm…
- FIELD `passport_verify.passport.series` [control_erred/i1 → control_erred] C=`4919` I=`4019` · контроль ошибся; шлюз восстановил эталон корпуса
- FIELD `passport_verify.person.last_name` [residual → name_lemma] C=`Кукушкин` I=`Осипов-Котов` · подмена дошла до инструмента: котов
- FIELD `passport_verify.snils` [validated_refused/snils_checksum → validated_refused] C=`073-253-087 48` I=`073-253-087 40`
- REPLY I: Принято, сейчас проверю! Уточню только по фамилии — вы сказали «восемсь кукушкин», это двойная фамилия **Осипов-Котов**? Запускаю проверку с этим вариантом. СНИЛС не прошёл проверку контрольной суммы — скорее всего, одна из цифр была названа неверно. Продиктуйте, пожалуйста, СНИЛС ещё раз медленно …

## decompose-033|2 · decompose · voice_raw · L1 = · L3 ≠ · C′≈C да · причина: **other**
- USER[1]: алло сверьте паспорт сорок девятнадцать трииста тринадцать пятьсот пятьдесят девять выдан гу мвд россии по краснодарскому краю код подразделенияя сто сорок семь шестьсот пятьдесят семь сниилс ноль семьдесят три двести пейсят три ноль восемьдесят семь сорок восемсь кукушкин валерий михайлович
- seen PASSPORT `сорок девятнадцать трииста тринадцать пятьсот пятьдесят девять` → `00 18 801664`
- seen SNILS `ноль семьдесят три двести пейсят три ноль восемьдесят семь сорок восемсь` → `ноль семьдесят три двести пейсят три ноль восемьдесят семь сорок Бирюков Бирюков Григорий Ярославович`
- seen NAME `кукушкин валерий михайлович` → `Бирюков Бирюков Григорий Ярославович`
- C: `passport_verify` {'passport': {'series': '4919', 'number': '313559', 'issued_by': 'ГУ МВД России по Краснодарскому краю', 'department_code': '147-657'}, 'person': {'last_name': 'Кукушкин', 'first_name': 'Валерий', 'm…
- I: `passport_verify` written={'passport': {'series': '0018', 'number': '801664', 'issued_by': 'ГУ МВД России по Краснодарскому краю', 'department_code': '147-657'}, 'person': {'last_name': 'Бирюков', 'first_name': 'Григорий', 'middle_name': 'Ярославович'}, 'snils': '073-253-087 40'} → restored={'passport': {'series': '4019', 'number': '313559', 'issued_by': 'ГУ МВД России по Краснодарскому краю', 'department_code': '147-657'}, 'person': {'last_name': 'восемсь кукушкин валерий михайлович', 'first_name': 'валерий', 'middle_name': 'михайлович'}, 'snil… · refusal=snils_checksum
- C′: `passport_verify` {'passport': {'series': '4919', 'number': '313559', 'issued_by': 'ГУ МВД России по Краснодарскому краю', 'department_code': '147-657'}, 'person': {'last_name': 'Кукушкин', 'first_name': 'Валерий', 'm…
- FIELD `passport_verify.passport.series` [control_erred/i1 → control_erred] C=`4919` I=`4019` · контроль ошибся; шлюз восстановил эталон корпуса
- FIELD `passport_verify.person.last_name` [composed → name_partial] C=`Кукушкин` I=`восемсь кукушкин валерий михайлович`
- FIELD `passport_verify.snils` [validated_refused/snils_checksum → validated_refused] C=`073-253-087 48` I=`073-253-087 40`
- REPLY I: Понял, сейчас проверю. Одну секунду! Паспортные данные я принял, однако система выдала ошибку контрольной суммы СНИЛС — **073-253-087 40** не проходит проверку. Уточните, пожалуйста, СНИЛС ещё раз — возможно, я неверно расслышал цифры, особенно двузначный контрольный номер в конце (у вас было «соро…

## decompose-041|1 · decompose · voice_raw · L1 = · L3 ≠ · C′≈C да · причина: **other**
- USER[1]: ааа здравствуйте проведите оплатуу шестьсот двадцать рублей карта двадцать два ноль ноль девяносто два двадцать шесть шестьдесят один шестьдесят пять одиннадцать тридцать два сроок один двадцать девятого держатель владислав захаров
- seen CARD `двадцать два ноль ноль девяносто два двадцать шесть шестьдесят один шестьдесят пять одиннадцать тридцать два` → `0217 8796 0145 8710`
- seen NAME `владислав захаров` → `Роман Мещеряков`
- C: `payment_create` {'amount': {'value': '620.00', 'currency': 'RUB'}, 'payment_method_data': {'type': 'bank_card', 'card': {'number': '2200922661651132', 'expiry_month': '01', 'expiry_year': '2029', 'cardholder': 'VLAD…
- I: `payment_create` written={'amount': {'value': '620.00', 'currency': 'RUB'}, 'payment_method_data': {'type': 'bank_card', 'card': {'number': '0217879601458710', 'expiry_month': '01', 'expiry_year': '2029', 'cardholder': 'ROMAN MESHCHERYAKOV'}}} → restored={'amount': {'value': '620.00', 'currency': 'RUB'}, 'payment_method_data': {'type': 'bank_card', 'card': {'number': '2200922661651132', 'expiry_month': '01', 'expiry_year': '2029', 'cardholder': 'VLADISLAV MESHCHERYAKOV'}}}
- C′: `payment_create` {'amount': {'value': '620.00', 'currency': 'RUB'}, 'payment_method_data': {'type': 'bank_card', 'card': {'number': '2200922661651132', 'expiry_month': '01', 'expiry_year': '2029', 'cardholder': 'VLAD…
- FIELD `payment_create.payment_method_data.card.cardholder` [other/misderived → name_partial] C=`VLADISLAV ZAKHAROV` I=`VLADISLAV MESHCHERYAKOV`
- REPLY I: Здравствуйте! Провожу оплату, одну секунду! Платёж создан! Вот детали: - **Сумма:** 620.00 ₽ - **Карта:** **** **** **** 1132 - **Держатель:** VLADISLAV MESHCHERYAKOV - **Статус:** ⏳ В обработке (pending) Если возникнут вопросы — обращайтесь! 😊

## derive-002|0 · derive · chat · L1 = · L3 ≠ · C′≈C да · причина: **other**
- USER[1]: оформите доставку на фёдорову юлию телефон 8 903 008 68 30 адрес ижевск улица репина 2 кв 38 посылка два килограмма индекс подберите сами
- seen NAME `фёдорову юлию` → `Сорокину Маргарите`
- seen PHONE `8 903 008 68 30` → `+79508549055`
- seen LOC `ижевск улица репина 2 кв 38` → `Тихвин, улица Абрикосовая 189, кв. 14`
- C: `delivery_create_order` {'recipient': {'name': 'Фёдорова Юлия', 'phones': [{'number': '+79030086830'}]}, 'to_location': {'postal_code': '426008', 'city': 'Ижевск', 'address': 'ул. Репина, 2, кв. 38'}, 'packages': [{'weight'…
- I: `delivery_create_order` written={'recipient': {'name': 'Сорокина Маргарита', 'phones': [{'number': '+79508549055'}]}, 'to_location': {'postal_code': '187550', 'city': 'Тихвин', 'address': 'ул. Абрикосовая, д. 189, кв. 14'}, 'packages': [{'weight': 2000}]} → restored={'recipient': {'name': 'фёдоров юлий', 'phones': [{'number': '+79030086830'}]}, 'to_location': {'postal_code': '187550', 'city': 'ижевск', 'address': 'ул. репина, д. 2, кв. 38'}, 'packages': [{'weight': 2000}]}
- C′: `delivery_create_order` {'recipient': {'name': 'Фёдорова Юлия', 'phones': [{'number': '+79030086830'}]}, 'to_location': {'postal_code': '426076', 'city': 'Ижевск', 'address': 'ул. Репина, д. 2, кв. 38'}, 'packages': [{'weig…
- FIELD `delivery_create_order.recipient.name` [other/inflected → name_case] C=`Фёдорова Юлия` I=`фёдоров юлий`
- FIELD `delivery_create_order.to_location.postal_code` [derived/unverifiable → derived] C=`426008` I=`187550`
- REPLY I: Оформляю заказ! Почтовый индекс ижевска улицы репина 2 — **187550**. Заказ успешно оформлен! 🎉 **Детали доставки:** - 📦 **Номер заказа:** ord-1 - 👤 **Получатель:** фёдоров юлий - 📞 **Телефон:** 8 903 008 68 30 - 📍 **Адрес:** ижевск улица репина 2 кв 38 (индекс 187550) - ⚖️ **Вес посылки:** 2 кг - ✅…

## derive-002|1 · derive · chat · L1 = · L3 ≠ · C′≈C да · причина: **other**
- USER[1]: оформите доставку на фёдорову юлию телефон 8 903 008 68 30 адрес ижевск улица репина 2 кв 38 посылка два килограмма индекс подберите сами
- seen NAME `фёдорову юлию` → `Котову Денису`
- seen PHONE `8 903 008 68 30` → `+79342537610`
- seen LOC `ижевск улица репина 2 кв 38` → `Приозерск, улица Осиновая 43, кв. 76`
- C: `delivery_create_order` {'recipient': {'name': 'Фёдорова Юлия', 'phones': [{'number': '+79030086830'}]}, 'to_location': {'postal_code': '426000', 'city': 'Ижевск', 'address': 'ул. Репина, д. 2, кв. 38'}, 'packages': [{'weig…
- I: `delivery_create_order` written={'recipient': {'name': 'Котов Денис', 'phones': [{'number': '+79342537610'}]}, 'to_location': {'postal_code': '188760', 'city': 'Приозерск', 'address': 'ул. Осиновая, 43, кв. 76'}, 'packages': [{'weight': 2000}]} → restored={'recipient': {'name': 'фёдоров юлий', 'phones': [{'number': '+79030086830'}]}, 'to_location': {'postal_code': '188760', 'city': 'ижевск', 'address': 'ул. репина, 2, кв. 38'}, 'packages': [{'weight': 2000}]}
- C′: `delivery_create_order` {'recipient': {'name': 'Фёдорова Юлия', 'phones': [{'number': '+79030086830'}]}, 'to_location': {'postal_code': '426000', 'city': 'Ижевск', 'address': 'улица Репина, 2, кв. 38'}, 'packages': [{'weigh…
- FIELD `delivery_create_order.recipient.name` [other/inflected → name_case] C=`Фёдорова Юлия` I=`фёдоров юлий`
- FIELD `delivery_create_order.to_location.postal_code` [derived/unverifiable → derived] C=`426000` I=`188760`
- REPLY I: Оформляю заказ! ижевск улица репина 2 — Ленинградская область, почтовый индекс **188760**. Заказ успешно оформлен! Вот детали: - **Номер заказа:** ord-1 - **Статус:** принят ✅ - **Получатель:** фёдоров юлий, 8 903 008 68 30 - **Адрес:** ижевск улица репина 2 кв 38 (индекс 188760) - **Вес посылки:**…

## derive-002|2 · derive · chat · L1 = · L3 ≠ · C′≈C да · причина: **other**
- USER[1]: оформите доставку на фёдорову юлию телефон 8 903 008 68 30 адрес ижевск улица репина 2 кв 38 посылка два килограмма индекс подберите сами
- seen NAME `фёдорову юлию` → `Тарасову Юрию`
- seen PHONE `8 903 008 68 30` → `+79104571630`
- seen LOC `ижевск улица репина 2 кв 38` → `Белёв, улица Сиреневая 74, кв. 188`
- C: `delivery_create_order` {'recipient': {'name': 'Фёдорова Юлия', 'phones': [{'number': '+79030086830'}]}, 'to_location': {'postal_code': '426008', 'city': 'Ижевск', 'address': 'ул. Репина, 2, кв. 38'}, 'packages': [{'weight'…
- I: `delivery_create_order` written={'recipient': {'name': 'Тарасов Юрий', 'phones': [{'number': '+79104571630'}]}, 'to_location': {'postal_code': '301530', 'city': 'Белёв', 'address': 'улица Сиреневая, д. 74, кв. 188'}, 'packages': [{'weight': 2000}]} → restored={'recipient': {'name': 'фёдоров юлий', 'phones': [{'number': '+79030086830'}]}, 'to_location': {'postal_code': '301530', 'city': 'ижевск', 'address': 'улица репина, д. 2, кв. 38'}, 'packages': [{'weight': 2000}]}
- C′: `delivery_create_order` {'recipient': {'name': 'Фёдорова Юлия', 'phones': [{'number': '+79030086830'}]}, 'to_location': {'postal_code': '426006', 'city': 'Ижевск', 'address': 'ул. Репина, 2, кв. 38'}, 'packages': [{'weight'…
- FIELD `delivery_create_order.recipient.name` [other/inflected → name_case] C=`Фёдорова Юлия` I=`фёдоров юлий`
- FIELD `delivery_create_order.to_location.postal_code` [derived/unverifiable → derived] C=`426008` I=`301530`
- REPLY I: Оформляю заказ! ижевска улицы репина 2 — город в Тульской области, почтовый индекс **301530**. Заказ успешно оформлен! Вот детали: - **Номер заказа:** ord-1 - **Статус:** принят ✅ - **Получатель:** фёдоров юлий, 8 903 008 68 30 - **Адрес:** ижевск улица репина 2 кв 38 (индекс 301530) - **Вес посылк…

## derive-007|0 · derive · voice_itn · L1 = · L3 ≠ · C′≈C да · причина: **derived-only**
- USER[1]: здравствуйте перезвоните мне завтра к 17 00 по моему времени я в самара проспект северный 27 а телефон 89274481140
- seen LOC `самара проспект северный 27 а` → `Сортавала, Речной проспект 136`
- seen PHONE `89274481140` → `+79919536337`
- C: `callback_schedule` {'phone': '+79274481140', 'at': '2026-09-04T17:00:00+04:00', 'timezone': 'Europe/Samara'}
- I: `callback_schedule` written={'phone': '+79919536337', 'at': '2026-09-04T17:00:00+03:00', 'timezone': 'Europe/Moscow'} → restored={'phone': '+79274481140', 'at': '2026-09-04T17:00:00+03:00', 'timezone': 'Europe/Moscow'}
- C′: `callback_schedule` {'phone': '+79274481140', 'at': '2026-09-04T17:00:00+04:00', 'timezone': 'Europe/Samara'}
- FIELD `callback_schedule.timezone` [derived/from_substitute → derived] C=`Europe/Samara` I=`Europe/Moscow` · значение выведено из ПОДМЕНЫ; восстановление недостижимо
- REPLY I: Здравствуйте! Планирую обратный звонок на завтра, 4 сентября 2026 года, в 17:00 по вашему времени (самара проспект северный 27 а, UTC+3). Готово! Обратный звонок запланирован на **завтра, 4 сентября 2026 года в 17:00** по вашему времени на номер **89274481140**. Будьте на связи! 😊

## derive-007|1 · derive · voice_itn · L1 = · L3 ≠ · C′≈C да · причина: **derived-only**
- USER[1]: здравствуйте перезвоните мне завтра к 17 00 по моему времени я в самара проспект северный 27 а телефон 89274481140
- seen LOC `самара проспект северный 27 а` → `Луга, Липовый проспект 9`
- seen PHONE `89274481140` → `+79850527672`
- C: `callback_schedule` {'phone': '+79274481140', 'at': '2026-09-04T17:00:00+04:00', 'timezone': 'Europe/Samara'}
- I: `callback_schedule` written={'phone': '+79850527672', 'at': '2026-09-04T17:00:00+03:00', 'timezone': 'Europe/Moscow'} → restored={'phone': '+79274481140', 'at': '2026-09-04T17:00:00+03:00', 'timezone': 'Europe/Moscow'}
- C′: `callback_schedule` {'phone': '+79274481140', 'at': '2026-09-04T17:00:00+04:00', 'timezone': 'Europe/Samara'}
- FIELD `callback_schedule.timezone` [derived/unverifiable → derived] C=`Europe/Samara` I=`Europe/Moscow`
- REPLY I: Здравствуйте! Планирую обратный звонок прямо сейчас. самара проспект северный 27 а — это Ленинградская область, часовой пояс московский (UTC+3). Завтра — 4 сентября 2026 года. Готово! Обратный звонок запланирован на **завтра, 4 сентября 2026 года в 17:00** по вашему времени на номер **89274481140**…

## derive-007|2 · derive · voice_itn · L1 = · L3 ≠ · C′≈C да · причина: **derived-only**
- USER[1]: здравствуйте перезвоните мне завтра к 17 00 по моему времени я в самара проспект северный 27 а телефон 89274481140
- seen LOC `самара проспект северный 27 а` → `Крапивна, Луговой проспект 28`
- seen PHONE `89274481140` → `+79287643911`
- C: `callback_schedule` {'phone': '+79274481140', 'at': '2026-09-04T17:00:00+04:00', 'timezone': 'Europe/Samara'}
- I: `callback_schedule` written={'phone': '+79287643911', 'at': '2026-09-04T17:00:00+03:00', 'timezone': 'Europe/Moscow'} → restored={'phone': '+79274481140', 'at': '2026-09-04T17:00:00+03:00', 'timezone': 'Europe/Moscow'}
- C′: `callback_schedule` {'phone': '+79274481140', 'at': '2026-09-04T17:00:00+04:00', 'timezone': 'Europe/Samara'}
- FIELD `callback_schedule.timezone` [derived/unverifiable → derived] C=`Europe/Samara` I=`Europe/Moscow`
- REPLY I: Здравствуйте! Планирую обратный звонок на завтра, 4 сентября, в 17:00 по московскому времени (самара проспект северный 27 а, Тульская область — UTC+3). Готово! Обратный звонок запланирован на **4 сентября 2026 года в 17:00** по вашему времени на номер **89274481140**. Ждите нашего звонка! Если что-…

## derive-008|0 · derive · sloppy · L1 = · L3 ≠ · C′≈C да · причина: **derived-only**
- USER[1]: добырй заипшите к офтальмологу соколову анну игоревну дата рождения 08.10.1997 телефон +79166983686 на завира на дсять утра
- seen NAME `соколову анну игоревну` → `Сазонову Регину Романовну`
- seen DOB `08.10.1997` → `16.07.1990`
- seen PHONE `+79166983686` → `+79404430372`
- C: `clinic_book` {'patient': {'last_name': 'Соколова', 'first_name': 'Анна', 'middle_name': 'Игоревна', 'birth_date': '1997-10-08', 'age': 28, 'gender': 'F'}, 'phone': '+79166983686', 'speciality': 'офтальмолог', 'sl…
- I: `clinic_book` written={'patient': {'last_name': 'Сазонова', 'first_name': 'Регина', 'middle_name': 'Романовна', 'birth_date': '1990-07-16', 'age': 36, 'gender': 'F'}, 'phone': '+79404430372', 'speciality': 'офтальмолог', 'slot': '2026-09-04T10:00:00+03:00'} → restored={'patient': {'last_name': 'соколова', 'first_name': 'анна', 'middle_name': 'игоревна', 'birth_date': '1997-10-08', 'age': 36, 'gender': 'F'}, 'phone': '+79166983686', 'speciality': 'офтальмолог', 'slot': '2026-09-04T10:00:00+03:00'}
- C′: `clinic_book` {'patient': {'last_name': 'Соколова', 'first_name': 'Анна', 'middle_name': 'Игоревна', 'birth_date': '1997-10-08', 'age': 28, 'gender': 'F'}, 'phone': '+79166983686', 'speciality': 'офтальмолог', 'sl…
- FIELD `clinic_book.patient.age` [derived/from_substitute → derived] C=`28` I=`36` · значение выведено из ПОДМЕНЫ; восстановление недостижимо
- REPLY I: Записываю! Вычисляю данные пациента: - **Пол:** женский (анны — женское имя) - **Возраст:** 36 лет (род. 08.10.1997, сегодня 03.09.2026) - **Дата приёма:** завтра, 04.09.2026 в 10:00 Готово! Пациентка успешно записана. Вот детали: - 👤 **Пациент:** соколова анна игоревна - 🏥 **Специалист:** Офтальмо…

## derive-008|1 · derive · sloppy · L1 = · L3 ≠ · C′≈C да · причина: **other**
- USER[1]: добырй заипшите к офтальмологу соколову анну игоревну дата рождения 08.10.1997 телефон +79166983686 на завира на дсять утра
- seen NAME `соколову анну игоревну` → `Карпову Веронику Степановну`
- seen DOB `08.10.1997` → `22.01.2005`
- seen PHONE `+79166983686` → `+79261543776`
- C: `clinic_book` {'patient': {'last_name': 'Соколова', 'first_name': 'Анна', 'middle_name': 'Игоревна', 'birth_date': '1997-10-08', 'age': 28, 'gender': 'F'}, 'phone': '+79166983686', 'speciality': 'офтальмолог', 'sl…
- I: `clinic_book` written={'patient': {'last_name': 'Карпова', 'first_name': 'Вероника', 'middle_name': 'Степановна', 'birth_date': '2005-01-22', 'age': 9, 'gender': 'F'}, 'phone': '+79261543776', 'speciality': 'офтальмолог', 'slot': '2014-12-25T10:00:00+03:00'} → restored={'patient': {'last_name': 'соколова', 'first_name': 'анна', 'middle_name': 'игоревна', 'birth_date': '1997-10-08', 'age': 9, 'gender': 'F'}, 'phone': '+79166983686', 'speciality': 'офтальмолог', 'slot': '2014-12-25T10:00:00+03:00'}
- C′: `clinic_book` {'patient': {'last_name': 'Соколова', 'first_name': 'Анна', 'middle_name': 'Игоревна', 'birth_date': '1997-10-08', 'age': 28, 'gender': 'F'}, 'phone': '+79166983686', 'speciality': 'офтальмолог', 'sl…
- FIELD `clinic_book.patient.age` [other/misderived → other/misderived] C=`28` I=`9`
- REPLY I: Записываю! анна игоревна — женский пол, возраст на 2026-09-02: **9 лет** (день рождения 08.10.1997, в этом году уже был). Завтра — 25.12.2014, 10:00. Готово! ✅ Запись оформлена: - **Пациент:** соколова анна игоревна - **Специалист:** Офтальмолог - **Дата и время:** 25 декабря 2014 г., 10:00 - **Тел…

## derive-008|2 · derive · sloppy · L1 = · L3 ≠ · C′≈C нет · причина: **derived-only**
- USER[1]: добырй заипшите к офтальмологу соколову анну игоревну дата рождения 08.10.1997 телефон +79166983686 на завира на дсять утра
- seen NAME `соколову анну игоревну` → `Юдину Ксению Валентиновну`
- seen DOB `08.10.1997` → `17.02.1982`
- seen PHONE `+79166983686` → `+79276781879`
- C: `clinic_book` {'patient': {'last_name': 'Соколова', 'first_name': 'Анна', 'middle_name': 'Игоревна', 'birth_date': '1997-10-08', 'age': 28, 'gender': 'F'}, 'phone': '+79166983686', 'speciality': 'офтальмолог', 'sl…
- I: `clinic_book` written={'patient': {'last_name': 'Юдина', 'first_name': 'Ксения', 'middle_name': 'Валентиновна', 'birth_date': '1982-02-17', 'age': 44, 'gender': 'F'}, 'phone': '+79276781879', 'speciality': 'офтальмолог', 'slot': '2026-09-04T10:00:00+03:00'} → restored={'patient': {'last_name': 'соколова', 'first_name': 'анна', 'middle_name': 'игоревна', 'birth_date': '1997-10-08', 'age': 44, 'gender': 'F'}, 'phone': '+79166983686', 'speciality': 'офтальмолог', 'slot': '2026-09-04T10:00:00+03:00'}
- C′: `clinic_book` {'patient': {'last_name': 'Соколова', 'first_name': 'Анна', 'middle_name': 'Игоревна', 'birth_date': '1997-10-08', 'age': 28, 'gender': 'F'}, 'phone': '+79166983686', 'speciality': 'офтальмолог', 'sl…
- FIELD `clinic_book.patient.age` [derived/from_substitute → derived] C=`28` I=`44` · значение выведено из ПОДМЕНЫ; восстановление недостижимо
- REPLY I: Записываю! Вычисляю данные пациентки: - **Возраст:** 44 года (род. 08.10.1997, сегодня 03.09.2026) - **Пол:** Женский (анна) - **Приём:** завтра, 04.09.2026 в 10:00 Готово! Пациентка записана. Вот детали записи: - 👤 **Пациент:** соколова анна игоревна - 🏥 **Специалист:** Офтальмолог - 📅 **Дата и вр…

## derive-013|0 · derive · voice_raw · L1 = · L3 ≠ · C′≈C нет · причина: **other**
- USER[1]: заведитее карточкуу букин сергей иванович телефон восемь девятьсот двенадцать пятьсот сорок шесть пятьдесят девять пятьдесят инициалыы и латиницей заполните самии
- seen NAME `букин сергей иванович` → `Панов Назар Фёдорович`
- seen PHONE `восемь девятьсот двенадцать пятьсот сорок шесть пятьдесят девять пятьдесят` → `+79772647564`
- C: `crm_upsert_contact` {'contact': {'last_name': 'Букин', 'first_name': 'Сергей', 'middle_name': 'Иванович', 'phone': '+79125465950', 'gender': 'M', 'initials': 'С.И.', 'name_latin': 'Bukin Sergey'}}
- I: `crm_upsert_contact` written={'contact': {'last_name': 'Панов', 'first_name': 'Назар', 'middle_name': 'Фёдорович', 'phone': '+79772647564', 'gender': 'M', 'initials': 'Н.Ф.', 'name_latin': 'Panov Nazar'}} → restored={'contact': {'last_name': 'букин', 'first_name': 'сергей', 'middle_name': 'иванович', 'phone': '+79125465950', 'gender': 'M', 'initials': 'С.И.', 'name_latin': 'Bukin Sergei'}}
- C′: `crm_upsert_contact` {'contact': {'last_name': 'Букин', 'first_name': 'Сергей', 'middle_name': 'Иванович', 'initials': 'С.И.', 'name_latin': 'Bukin Sergey', 'phone': '+79125465950'}}
- FIELD `crm_upsert_contact.contact.name_latin` [other/misderived → name_partial] C=`Bukin Sergey` I=`Bukin Sergei`
- REPLY I: Создаю карточку — инициалы и латиницу заполню сам по ФИО! Карточка создана! Вот что записал: | Поле | Значение | |---|---| | **ФИО** | букин сергей иванович | | **Телефон** | восемь девятьсот двенадцать пятьсот сорок шесть пятьдесят девять пятьдесят | | **Пол** | М | | **Инициалы** | С.И. | | **Лат…

## derive-013|1 · derive · voice_raw · L1 = · L3 ≠ · C′≈C нет · причина: **other**
- USER[1]: заведитее карточкуу букин сергей иванович телефон восемь девятьсот двенадцать пятьсот сорок шесть пятьдесят девять пятьдесят инициалыы и латиницей заполните самии
- seen NAME `букин сергей иванович` → `Рыбаков Денис Павлович`
- seen PHONE `восемь девятьсот двенадцать пятьсот сорок шесть пятьдесят девять пятьдесят` → `+79112115253`
- C: `crm_upsert_contact` {'contact': {'last_name': 'Букин', 'first_name': 'Сергей', 'middle_name': 'Иванович', 'initials': 'С.И.', 'name_latin': 'Bukin Sergey', 'phone': '+79125465950'}}
- I: `crm_upsert_contact` written={'contact': {'last_name': 'Рыбаков', 'first_name': 'Денис', 'middle_name': 'Павлович', 'phone': '+79112115253', 'gender': 'M', 'initials': 'Д.П.', 'name_latin': 'Rybakov Denis'}} → restored={'contact': {'last_name': 'букин', 'first_name': 'сергей', 'middle_name': 'иванович', 'phone': '+79125465950', 'gender': 'M', 'initials': 'С.И.', 'name_latin': 'Bukin Sergei'}}
- C′: `crm_upsert_contact` {'contact': {'last_name': 'Букин', 'first_name': 'Сергей', 'middle_name': 'Иванович', 'phone': '+79125465950', 'gender': 'M', 'initials': 'С.И.', 'name_latin': 'Bukin Sergei'}}
- FIELD `crm_upsert_contact.contact.gender` [extra → extra:gender] C=`` I=`M`
- FIELD `crm_upsert_contact.contact.name_latin` [other/misderived → name_partial] C=`Bukin Sergey` I=`Bukin Sergei`
- REPLY I: Создаю карточку для **букина сергея ивановича**. Инициалы и латиницу заполняю самостоятельно по ФИО. Карточка создана! ✅ **букин сергей иванович** (ID: c-1) - 📞 Телефон: восемь девятьсот двенадцать пятьсот сорок шесть пятьдесят девять пятьдесят - Инициалы: **С.И.** - Латиница: **Bukin Sergei** - По…

## derive-013|2 · derive · voice_raw · L1 = · L3 ≠ · C′≈C нет · причина: **other**
- USER[1]: заведитее карточкуу букин сергей иванович телефон восемь девятьсот двенадцать пятьсот сорок шесть пятьдесят девять пятьдесят инициалыы и латиницей заполните самии
- seen NAME `букин сергей иванович` → `Тихонов Константин Юрьевич`
- seen PHONE `восемь девятьсот двенадцать пятьсот сорок шесть пятьдесят девять пятьдесят` → `+79400968651`
- C: `crm_upsert_contact` {'contact': {'last_name': 'Букин', 'first_name': 'Сергей', 'middle_name': 'Иванович', 'phone': '+79125465950', 'gender': 'M', 'initials': 'С.И.', 'name_latin': 'Bukin Sergey'}}
- I: `crm_upsert_contact` written={'contact': {'last_name': 'Тихонов', 'first_name': 'Константин', 'middle_name': 'Юрьевич', 'phone': '+79400968651', 'gender': 'M', 'initials': 'К.Ю.', 'name_latin': 'Tikhonov Konstantin'}} → restored={'contact': {'last_name': 'букин', 'first_name': 'сергей', 'middle_name': 'иванович', 'phone': '+79125465950', 'gender': 'M', 'initials': 'С.И.', 'name_latin': 'Bukin Sergei'}}
- C′: `crm_upsert_contact` {'contact': {'last_name': 'Букин', 'first_name': 'Сергей', 'middle_name': 'Иванович', 'initials': 'С.И.', 'name_latin': 'Bukin Sergey', 'phone': '+79125465950'}}
- FIELD `crm_upsert_contact.contact.name_latin` [other/misderived → name_partial] C=`Bukin Sergey` I=`Bukin Sergei`
- REPLY I: Создаю карточку — инициалы и латиницу заполняю сам по ФИО: Готово! Карточка создана (ID: **c-1**) со следующими данными: | Поле | Значение | |---|---| | ФИО | букин сергей иванович | | Телефон | восемь девятьсот двенадцать пятьсот сорок шесть пятьдесят девять пятьдесят | | Инициалы | С.И. | | Латин…

## derive-014|0 · derive · chat · L1 = · L3 ≠ · C′≈C да · причина: **derived-only**
- USER[1]: здравствуйте оформите доставку на букина сергея телефон 89659854545 адрес самара переулок маяковского 144 квартира 94 посылка два килограмма индекс подберите сами
- seen NAME `букина сергея` → `Ершова Романа`
- seen PHONE `89659854545` → `+79271663886`
- seen LOC `самара переулок маяковского 144 квартира 94` → `Гатчина, переулок Полевой 111, кв. 44`
- C: `delivery_create_order` {'recipient': {'name': 'Букин Сергей', 'phones': [{'number': '+79659854545'}]}, 'to_location': {'postal_code': '443000', 'city': 'Самара', 'address': 'переулок Маяковского, 144, кв. 94'}, 'packages':…
- I: `delivery_create_order` written={'recipient': {'name': 'Ершов Роман', 'phones': [{'number': '+79271663886'}]}, 'to_location': {'postal_code': '188300', 'city': 'Гатчина', 'address': 'переулок Полевой, 111, кв. 44'}, 'packages': [{'weight': 2000}]} → restored={'recipient': {'name': 'букин сергей', 'phones': [{'number': '+79659854545'}]}, 'to_location': {'postal_code': '188300', 'city': 'самара', 'address': 'переулок маяковского, 144, кв. 94'}, 'packages': [{'weight': 2000}]}
- C′: `delivery_create_order` {'recipient': {'name': 'Букин Сергей', 'phones': [{'number': '+79659854545'}]}, 'to_location': {'postal_code': '443099', 'city': 'Самара', 'address': 'пер. Маяковского, 144, кв. 94'}, 'packages': [{'…
- FIELD `delivery_create_order.to_location.postal_code` [derived/unverifiable → derived] C=`443000` I=`188300`
- REPLY I: Здравствуйте! Оформляю заказ — подбираю индекс для самара переулка маяковского 144 (188300) и создаю доставку. Заказ успешно оформлен! Вот детали: - **Номер заказа:** ord-1 - **Статус:** принят ✅ - **Получатель:** букин сергей, 89659854545 - **Адрес:** самара переулок маяковского 144 квартира 94 - …

## derive-014|1 · derive · chat · L1 = · L3 ≠ · C′≈C да · причина: **derived-only**
- USER[1]: здравствуйте оформите доставку на букина сергея телефон 89659854545 адрес самара переулок маяковского 144 квартира 94 посылка два килограмма индекс подберите сами
- seen NAME `букина сергея` → `Панова Михаила`
- seen PHONE `89659854545` → `+79427739196`
- seen LOC `самара переулок маяковского 144 квартира 94` → `Крапивна, переулок Ивовый 37, кв. 65`
- C: `delivery_create_order` {'recipient': {'name': 'Букин Сергей', 'phones': [{'number': '+79659854545'}]}, 'to_location': {'postal_code': '443099', 'city': 'Самара', 'address': 'переулок Маяковского, 144, кв. 94'}, 'packages':…
- I: `delivery_create_order` written={'recipient': {'name': 'Панов Михаил', 'phones': [{'number': '+79427739196'}]}, 'to_location': {'postal_code': '301480', 'city': 'Крапивна', 'address': 'переулок Ивовый, 37, кв. 65'}, 'packages': [{'weight': 2000}]} → restored={'recipient': {'name': 'букин сергей', 'phones': [{'number': '+79659854545'}]}, 'to_location': {'postal_code': '301480', 'city': 'самара', 'address': 'переулок маяковского, 144, кв. 94'}, 'packages': [{'weight': 2000}]}
- C′: `delivery_create_order` {'recipient': {'name': 'Букин Сергей', 'phones': [{'number': '+79659854545'}]}, 'to_location': {'postal_code': '443099', 'city': 'Самара', 'address': 'пер. Маяковского, 144, кв. 94'}, 'packages': [{'…
- FIELD `delivery_create_order.to_location.postal_code` [derived/unverifiable → derived] C=`443099` I=`301480`
- REPLY I: Здравствуйте! Оформляю заказ. самара переулок маяковского 144 — это город в Тульской области, почтовый индекс **301480**. Заказ успешно оформлен! Вот детали: - **Номер заказа:** ord-1 - **Статус:** принят ✅ - **Получатель:** букин сергей, 89659854545 - **Адрес:** самара переулок маяковского 144 ква…

## derive-014|2 · derive · chat · L1 = · L3 ≠ · C′≈C да · причина: **derived-only**
- USER[1]: здравствуйте оформите доставку на букина сергея телефон 89659854545 адрес самара переулок маяковского 144 квартира 94 посылка два килограмма индекс подберите сами
- seen NAME `букина сергея` → `Бирюкова Родиона`
- seen PHONE `89659854545` → `+79498038236`
- seen LOC `самара переулок маяковского 144 квартира 94` → `Сортавала, переулок Ивовый 137, кв. 114`
- C: `delivery_create_order` {'recipient': {'name': 'Букин Сергей', 'phones': [{'number': '+79659854545'}]}, 'to_location': {'postal_code': '443099', 'city': 'Самара', 'address': 'переулок Маяковского, 144, кв. 94'}, 'packages':…
- I: `delivery_create_order` written={'recipient': {'name': 'Бирюков Родион', 'phones': [{'number': '+79498038236'}]}, 'to_location': {'postal_code': '186790', 'city': 'Сортавала', 'address': 'переулок Ивовый, 137, кв. 114'}, 'packages': [{'weight': 2000}]} → restored={'recipient': {'name': 'букин сергей', 'phones': [{'number': '+79659854545'}]}, 'to_location': {'postal_code': '186790', 'city': 'самара', 'address': 'переулок маяковского, 144, кв. 94'}, 'packages': [{'weight': 2000}]}
- C′: `delivery_create_order` {'recipient': {'name': 'Букин Сергей', 'phones': [{'number': '+79659854545'}]}, 'to_location': {'postal_code': '443000', 'city': 'Самара', 'address': 'переулок Маяковского, 144, кв. 94'}, 'packages':…
- FIELD `delivery_create_order.to_location.postal_code` [derived/from_substitute → derived] C=`443099` I=`186790` · значение выведено из ПОДМЕНЫ; восстановление недостижимо
- REPLY I: Здравствуйте! Оформляю заказ прямо сейчас. Почтовый индекс самара переулка маяковского 144 — **186790**. Заказ успешно оформлен! Вот детали: - **Номер заказа:** ord-1 - **Статус:** принят ✅ - **Получатель:** букин сергей, 89659854545 - **Адрес:** самара переулок маяковского 144 квартира 94 (индекс …

## derive-017|1 · derive · sloppy · L1 = · L3 ≠ · C′≈C да · причина: **other**
- USER[1]: добрый заведите карточку кузнецова ольга дмитриевна телефон +79627672108 почта kuznecova84@list.ru инициалы и латиницей заполните сами
- seen NAME `кузнецова ольга дмитриевна` → `Тарасова Клавдия Ярославовна`
- seen PHONE `+79627672108` → `+79418559440`
- seen EMAIL `kuznecova84@list.ru` → `zozpyzog@example.ru`
- C: `crm_upsert_contact` {'contact': {'last_name': 'Кузнецова', 'first_name': 'Ольга', 'middle_name': 'Дмитриевна', 'gender': 'F', 'phone': '+79627672108', 'email': 'kuznecova84@list.ru', 'initials': 'О.Д.', 'name_latin': 'K…
- I: `crm_upsert_contact` written={'contact': {'last_name': 'Тарасова', 'first_name': 'Клавдия', 'middle_name': 'Ярославовна', 'phone': '+79418559440', 'email': 'zozpyzog@example.ru', 'initials': 'К.Я.', 'name_latin': 'Tarasova Klavdia', 'gender': 'F'}} → restored={'contact': {'last_name': 'кузнецова', 'first_name': 'ольга', 'middle_name': 'дмитриевна', 'phone': '+79627672108', 'email': 'kuznecova84@list.ru', 'initials': 'О.Д.', 'name_latin': 'Kuznetsova Klavdia', 'gender': 'F'}}
- C′: `crm_upsert_contact` {'contact': {'last_name': 'Кузнецова', 'first_name': 'Ольга', 'middle_name': 'Дмитриевна', 'phone': '+79627672108', 'email': 'kuznecova84@list.ru', 'gender': 'F', 'initials': 'О.Д.', 'name_latin': 'K…
- FIELD `crm_upsert_contact.contact.name_latin` [other/misderived → name_partial] C=`Kuznetsova Olga` I=`Kuznetsova Klavdia`
- REPLY I: Добрый день! Создаю карточку прямо сейчас. - **Инициалы:** О.Д. (ольга дмитриевна) - **Латиница:** Kuznetsova Klavdia Карточка успешно создана! Вот что записано: | Поле | Значение | |---|---| | **ФИО** | кузнецова ольга дмитриевна | | **Инициалы** | О.Д. | | **Латиница** | Kuznetsova Klavdia | | **…

## derive-017|2 · derive · sloppy · L1 = · L3 ≠ · C′≈C да · причина: **other**
- USER[1]: добрый заведите карточку кузнецова ольга дмитриевна телефон +79627672108 почта kuznecova84@list.ru инициалы и латиницей заполните сами
- seen NAME `кузнецова ольга дмитриевна` → `Беляева Галина Павловна`
- seen PHONE `+79627672108` → `+79136918709`
- seen EMAIL `kuznecova84@list.ru` → `iavbykne@example.ru`
- C: `crm_upsert_contact` {'contact': {'last_name': 'Кузнецова', 'first_name': 'Ольга', 'middle_name': 'Дмитриевна', 'phone': '+79627672108', 'email': 'kuznecova84@list.ru', 'gender': 'F', 'initials': 'О.Д.', 'name_latin': 'K…
- I: `crm_upsert_contact` written={'contact': {'last_name': 'Беляева', 'first_name': 'Галина', 'middle_name': 'Павловна', 'phone': '+79136918709', 'email': 'iavbykne@example.ru', 'gender': 'F', 'initials': 'Г.П.', 'name_latin': 'Belyaeva Galina'}} → restored={'contact': {'last_name': 'кузнецова', 'first_name': 'ольга', 'middle_name': 'дмитриевна', 'phone': '+79627672108', 'email': 'kuznecova84@list.ru', 'gender': 'F', 'initials': 'О.Д.', 'name_latin': 'Kuzneczova Olga'}}
- C′: `crm_upsert_contact` {'contact': {'last_name': 'Кузнецова', 'first_name': 'Ольга', 'middle_name': 'Дмитриевна', 'phone': '+79627672108', 'email': 'kuznecova84@list.ru', 'gender': 'F', 'initials': 'О.Д.', 'name_latin': 'K…
- FIELD `crm_upsert_contact.contact.name_latin` [other/misderived → name_partial] C=`Kuznetsova Olga` I=`Kuzneczova Olga`
- REPLY I: Добрый день! Создаю карточку прямо сейчас. Карточка успешно создана! Вот что было заполнено: | Поле | Значение | |---|---| | Фамилия | кузнецовой | | Имя | ольга | | Отчество | дмитриевна | | Инициалы | О.Д. | | Латиница | Kuzneczova Olga | | Телефон | +79627672108 | | Email | kuznecova84@list.ru |…

## derive-018|0 · derive · sloppy · L1 = · L3 ≠ · C′≈C да · причина: **other**
- USER[1]: добрый оформите доставку на громову марину телефон 89994963857 арес сортавала переулок северный 5 квартира 238 посылка два килограмма индекс подбеирте сами
- seen NAME `громову марину` → `Щукину Еве`
- seen PHONE `89994963857` → `+79651661294`
- seen LOC `сортавала переулок северный 5 квартира 238` → `Луга, переулок Рябиновый 180, кв. 232`
- C: `delivery_create_order` {'recipient': {'name': 'Громова Марина', 'phones': [{'number': '+79994963857'}]}, 'to_location': {'postal_code': '186790', 'city': 'Сортавала', 'address': 'переулок Северный, 5, кв. 238'}, 'packages'…
- I: `delivery_create_order` written={'recipient': {'name': 'Щукина Ева', 'phones': [{'number': '+79651661294'}]}, 'to_location': {'postal_code': '188230', 'city': 'Луга', 'address': 'переулок Рябиновый, 180, кв. 232'}, 'packages': [{'weight': 2000}]} → restored={'recipient': {'name': 'громов марин', 'phones': [{'number': '+79994963857'}]}, 'to_location': {'postal_code': '188230', 'city': 'сортавала', 'address': 'переулок северный, 5, кв. 238'}, 'packages': [{'weight': 2000}]}
- C′: `delivery_create_order` {'recipient': {'name': 'Громова Марина', 'phones': [{'number': '+79994963857'}]}, 'to_location': {'postal_code': '186790', 'city': 'Сортавала', 'address': 'пер. Северный, 5, кв. 238'}, 'packages': [{…
- FIELD `delivery_create_order.recipient.name` [other/inflected → name_case] C=`Громова Марина` I=`громов марин`
- FIELD `delivery_create_order.to_location.postal_code` [derived/unverifiable → derived] C=`186790` I=`188230`
- REPLY I: Добрый день! Оформляю заказ — индекс сортавалы переулка северного 5 188230, вес 2000 г. Заказ успешно оформлен! ✅ **Детали доставки:** - 📦 **Номер заказа:** ord-1 - 👤 **Получатель:** громов марин - 📞 **Телефон:** 89994963857 - 📍 **Адрес:** сортавала переулок северный 5 квартира 238 (индекс 188230) …

## derive-018|1 · derive · sloppy · L1 = · L3 ≠ · C′≈C да · причина: **other**
- USER[1]: добрый оформите доставку на громову марину телефон 89994963857 арес сортавала переулок северный 5 квартира 238 посылка два килограмма индекс подбеирте сами
- seen NAME `громову марину` → `Шилову Марку`
- seen PHONE `89994963857` → `+79720319827`
- seen LOC `сортавала переулок северный 5 квартира 238` → `Крапивна, переулок Сосновый 38, кв. 188`
- C: `delivery_create_order` {'recipient': {'name': 'Громова Марина', 'phones': [{'number': '+79994963857'}]}, 'to_location': {'postal_code': '186790', 'city': 'Сортавала', 'address': 'переулок Северный, 5, кв. 238'}, 'packages'…
- I: `delivery_create_order` written={'recipient': {'name': 'Шилова Марка', 'phones': [{'number': '+79720319827'}]}, 'to_location': {'postal_code': '301680', 'city': 'Крапивна', 'address': 'переулок Сосновый, 38, кв. 188'}, 'packages': [{'weight': 2000}]} → restored={'recipient': {'name': 'громов марин', 'phones': [{'number': '+79994963857'}]}, 'to_location': {'postal_code': '301680', 'city': 'сортавала', 'address': 'переулок северный, 5, кв. 238'}, 'packages': [{'weight': 2000}]}
- C′: `delivery_create_order` {'recipient': {'name': 'Громова Марина', 'phones': [{'number': '+79994963857'}]}, 'to_location': {'postal_code': '186790', 'city': 'Сортавала', 'address': 'переулок Северный, 5, кв. 238'}, 'packages'…
- FIELD `delivery_create_order.recipient.name` [other/inflected → name_case] C=`Громова Марина` I=`громов марин`
- FIELD `delivery_create_order.to_location.postal_code` [derived/unverifiable → derived] C=`186790` I=`301680`
- REPLY I: Добрый день! Оформляю заказ прямо сейчас. сортавала переулок северный 5 — город в Тульской области, индекс **301680**. Заказ успешно оформлен! 📦 **Детали заказа:** - **Номер заказа:** ord-1 - **Статус:** Принят - **Получатель:** громов марин, 89994963857 - **Адрес:** сортавала переулок северный 5 к…

## derive-018|2 · derive · sloppy · L1 = · L3 ≠ · C′≈C да · причина: **other**
- USER[1]: добрый оформите доставку на громову марину телефон 89994963857 арес сортавала переулок северный 5 квартира 238 посылка два килограмма индекс подбеирте сами
- seen NAME `громову марину` → `Жукову Егору`
- seen PHONE `89994963857` → `+79885618084`
- seen LOC `сортавала переулок северный 5 квартира 238` → `Чернь, переулок Родниковый 187, кв. 99`
- C: `delivery_create_order` {'recipient': {'name': 'Громова Марина', 'phones': [{'number': '+79994963857'}]}, 'to_location': {'postal_code': '186790', 'city': 'Сортавала', 'address': 'переулок Северный, 5, кв. 238'}, 'packages'…
- I: `delivery_create_order` written={'recipient': {'name': 'Жуков Егор', 'phones': [{'number': '+79885618084'}]}, 'to_location': {'postal_code': '301420', 'city': 'Чернь', 'address': 'переулок Родниковый, 187, кв. 99'}, 'packages': [{'weight': 2000}]} → restored={'recipient': {'name': 'громов марин', 'phones': [{'number': '+79994963857'}]}, 'to_location': {'postal_code': '301420', 'city': 'сортавала', 'address': 'переулок северный, 5, кв. 238'}, 'packages': [{'weight': 2000}]}
- C′: `delivery_create_order` {'recipient': {'name': 'Громова Марина', 'phones': [{'number': '+79994963857'}]}, 'to_location': {'postal_code': '186790', 'city': 'Сортавала', 'address': 'переулок Северный, 5, кв. 238'}, 'packages'…
- FIELD `delivery_create_order.recipient.name` [other/inflected → name_case] C=`Громова Марина` I=`громов марин`
- FIELD `delivery_create_order.to_location.postal_code` [derived/from_substitute → derived] C=`186790` I=`301420` · значение выведено из ПОДМЕНЫ; восстановление недостижимо
- REPLY I: Добрый день! Оформляю заказ — сортавала переулок северный 5 это посёлок городского типа в Тульской области, индекс 301420. Запускаю! Готово! Заказ принят ✅ **Детали заказа:** - 🆔 Номер: `ord-1` - 👤 Получатель: громов марин - 📞 Телефон: 89994963857 - 📍 Адрес: сортавала переулок северный 5 квартира 2…

## derive-020|0 · derive · voice_raw · L1 = · L3 ≠ · C′≈C да · причина: **case-only**
- USER[1]: добрыый день запишите к кардиологу миллера валерия леонидовича родилсяя двадцать первое сентября восьмидесятого года телефон восемь девятьсот двадцать два одиннадцать двенадцать двадцать три три на пятницу к девяти
- seen NAME `миллера валерия леонидовича` → `Тихонова Николая Константиновича Беляева`
- **LEAK** DOB `двадцать первое сентября восьмидесятого года` — модель видела настоящее значение
- seen PHONE `восемь девятьсот двадцать два одиннадцать двенадцать двадцать три три` → `+79648987698`
- C: `clinic_book` {'patient': {'last_name': 'Миллер', 'first_name': 'Валерий', 'middle_name': 'Леонидович', 'birth_date': '1980-09-21', 'age': 45, 'gender': 'M'}, 'phone': '+79221112233', 'speciality': 'кардиолог', 's…
- I: `clinic_book` written={'patient': {'last_name': 'Беляев', 'first_name': 'Николай', 'middle_name': 'Константинович', 'birth_date': '1980-09-21', 'age': 45, 'gender': 'M'}, 'phone': '+79648987698', 'speciality': 'кардиолог', 'slot': '2026-09-04T09:00:00+03:00'} → restored={'patient': {'last_name': 'родилсяя', 'first_name': 'валерий', 'middle_name': 'леонидович', 'birth_date': '1980-09-21', 'age': 45, 'gender': 'M'}, 'phone': '+79221112233', 'speciality': 'кардиолог', 'slot': '2026-09-04T09:00:00+03:00'}
- C′: `clinic_book` {'patient': {'last_name': 'Миллер', 'first_name': 'Валерий', 'middle_name': 'Леонидович', 'birth_date': '1980-09-21', 'age': 45, 'gender': 'M'}, 'phone': '+79221112233', 'speciality': 'кардиолог', 's…
- FIELD `clinic_book.patient.last_name` [other/inflected → name_lemma] C=`Миллер` I=`родилсяя`
- REPLY I: Добрый день! Понял вас: записываю пациента **родилсяя валерия леонидовича** к кардиологу (врач миллер) на **пятницу, 4 сентября 2026 г. в 09:00**. Дата рождения — 21.09.1980, полных лет — **45** (день рождения ещё не наступил в этом году), пол — **мужской**. Запись успешно создана! ✅ **Детали запис…

## derive-020|1 · derive · voice_raw · L1 = · L3 = · C′≈C да · причина: **leak-only**
- USER[1]: добрыый день запишите к кардиологу миллера валерия леонидовича родилсяя двадцать первое сентября восьмидесятого года телефон восемь девятьсот двадцать два одиннадцать двенадцать двадцать три три на пятницу к девяти
- seen NAME `миллера валерия леонидовича` → `Сазонова Алексея Борисовича Ершова`
- **LEAK** DOB `двадцать первое сентября восьмидесятого года` — модель видела настоящее значение
- seen PHONE `восемь девятьсот двадцать два одиннадцать двенадцать двадцать три три` → `+79683657984`
- C: `clinic_book` {'patient': {'last_name': 'Миллер', 'first_name': 'Валерий', 'middle_name': 'Леонидович', 'birth_date': '1980-09-21', 'age': 45, 'gender': 'M'}, 'phone': '+79221112233', 'speciality': 'кардиолог', 's…
- I: `clinic_book` written={'patient': {'last_name': 'Сазонов', 'first_name': 'Алексей', 'middle_name': 'Борисович', 'birth_date': '1980-09-21', 'age': 45, 'gender': 'M'}, 'phone': '+79683657984', 'speciality': 'кардиолог', 'slot': '2026-09-04T09:00:00+03:00'} → restored={'patient': {'last_name': 'миллер', 'first_name': 'валерий', 'middle_name': 'леонидович', 'birth_date': '1980-09-21', 'age': 45, 'gender': 'M'}, 'phone': '+79221112233', 'speciality': 'кардиолог', 'slot': '2026-09-04T09:00:00+03:00'}
- C′: `clinic_book` {'patient': {'last_name': 'Миллер', 'first_name': 'Валерий', 'middle_name': 'Леонидович', 'birth_date': '1980-09-21', 'age': 45, 'gender': 'M'}, 'phone': '+79221112233', 'speciality': 'кардиолог', 's…
- REPLY I: Добрый день! Разбираю заявку: - **Пациент:** миллер валерий леонидович - **Специалист:** кардиолог (врач родилсяя) - **Дата рождения:** 21.09.1980 → **возраст:** 45 лет (день рождения ещё не наступил в этом году), **пол:** мужской - **Телефон:** восемь девятьсот двадцать два одиннадцать двенадцать …

## derive-020|2 · derive · voice_raw · L1 = · L3 ≠ · C′≈C да · причина: **case-only**
- USER[1]: добрыый день запишите к кардиологу миллера валерия леонидовича родилсяя двадцать первое сентября восьмидесятого года телефон восемь девятьсот двадцать два одиннадцать двенадцать двадцать три три на пятницу к девяти
- seen NAME `миллера валерия леонидовича` → `Наумова Олега Андреевича Гущина`
- **LEAK** DOB `двадцать первое сентября восьмидесятого года` — модель видела настоящее значение
- seen PHONE `восемь девятьсот двадцать два одиннадцать двенадцать двадцать три три` → `+79120008434`
- C: `clinic_book` {'patient': {'last_name': 'Миллер', 'first_name': 'Валерий', 'middle_name': 'Леонидович', 'birth_date': '1980-09-21', 'age': 45, 'gender': 'M'}, 'phone': '+79221112233', 'speciality': 'кардиолог', 's…
- I: `clinic_book` written={'patient': {'last_name': 'Гущин', 'first_name': 'Олег', 'middle_name': 'Андреевич', 'birth_date': '1980-09-21', 'age': 45, 'gender': 'M'}, 'phone': '+79120008434', 'speciality': 'кардиолог', 'slot': '2026-09-04T09:00:00+03:00'} → restored={'patient': {'last_name': 'родилсяя', 'first_name': 'валерий', 'middle_name': 'леонидович', 'birth_date': '1980-09-21', 'age': 45, 'gender': 'M'}, 'phone': '+79221112233', 'speciality': 'кардиолог', 'slot': '2026-09-04T09:00:00+03:00'}
- C′: `clinic_book` {'patient': {'last_name': 'Миллер', 'first_name': 'Валерий', 'middle_name': 'Леонидович', 'birth_date': '1980-09-21', 'age': 45, 'gender': 'M'}, 'phone': '+79221112233', 'speciality': 'кардиолог', 's…
- FIELD `clinic_book.patient.last_name` [other/inflected → name_lemma] C=`Миллер` I=`родилсяя`
- REPLY I: Добрый день! Разбираю данные: - **Врач:** кардиолог миллер - **Пациент:** родилсяя валерий леонидович - **Дата рождения:** 21.09.1980 → **45 лет** (день рождения ещё не наступил), **пол — М** - **Телефон:** восемь девятьсот двадцать два одиннадцать двенадцать двадцать три три - **Слот:** ближайшая …

## derive-022|0 · derive · chat · L1 = · L3 ≠ · C′≈C да · причина: **derived-only**
- USER[1]: привет оформите доставку на миллера валерия телефон +79292312867 адрес самара улица комиссарова 23 кв 107 посылка два килограмма индекс подберите сами
- seen NAME `миллера валерия` → `Панова Алексея`
- seen PHONE `+79292312867` → `+79669328118`
- seen LOC `самара улица комиссарова 23 кв 107` → `Крапивна, улица Грушевая 136, кв. 1`
- C: `delivery_create_order` {'recipient': {'name': 'Миллер Валерий', 'phones': [{'number': '+79292312867'}]}, 'to_location': {'postal_code': '443022', 'city': 'Самара', 'address': 'улица Комиссарова, 23, кв. 107'}, 'packages': …
- I: `delivery_create_order` written={'recipient': {'name': 'Панов Алексей', 'phones': [{'number': '+79669328118'}]}, 'to_location': {'postal_code': '301470', 'city': 'Крапивна', 'address': 'ул. Грушевая, 136, кв. 1'}, 'packages': [{'weight': 2000}]} → restored={'recipient': {'name': 'миллер валерий', 'phones': [{'number': '+79292312867'}]}, 'to_location': {'postal_code': '301470', 'city': 'самара', 'address': 'ул. комиссарова, 23, кв. 107'}, 'packages': [{'weight': 2000}]}
- C′: `delivery_create_order` {'recipient': {'name': 'Миллер Валерий', 'phones': [{'number': '+79292312867'}]}, 'to_location': {'postal_code': '443013', 'city': 'Самара', 'address': 'улица Комиссарова, 23, кв. 107'}, 'packages': …
- FIELD `delivery_create_order.to_location.postal_code` [derived/unverifiable → derived] C=`443022` I=`301470`
- REPLY I: Привет! Оформляю заказ прямо сейчас. самара улица комиссарова 23 — это в Тульской области, индекс 301470. Заказ успешно оформлен! Вот детали: - **Номер заказа:** ord-1 - **Статус:** принят ✅ - **Получатель:** миллер валерий, +79292312867 - **Адрес:** самара улица комиссарова 23 кв 107 (индекс 30147…

## derive-022|1 · derive · chat · L1 = · L3 ≠ · C′≈C да · причина: **derived-only**
- USER[1]: привет оформите доставку на миллера валерия телефон +79292312867 адрес самара улица комиссарова 23 кв 107 посылка два килограмма индекс подберите сами
- seen NAME `миллера валерия` → `Котова Бориса`
- seen PHONE `+79292312867` → `+79920373530`
- seen LOC `самара улица комиссарова 23 кв 107` → `Кинешма, улица Вязовая 188, кв. 225`
- C: `delivery_create_order` {'recipient': {'name': 'Миллер Валерий', 'phones': [{'number': '+79292312867'}]}, 'to_location': {'postal_code': '443010', 'city': 'Самара', 'address': 'улица Комиссарова, 23, кв. 107'}, 'packages': …
- I: `delivery_create_order` written={'recipient': {'name': 'Котов Борис', 'phones': [{'number': '+79920373530'}]}, 'to_location': {'postal_code': '155800', 'city': 'Кинешма', 'address': 'ул. Вязовая, д. 188, кв. 225'}, 'packages': [{'weight': 2000}]} → restored={'recipient': {'name': 'миллер валерий', 'phones': [{'number': '+79292312867'}]}, 'to_location': {'postal_code': '155800', 'city': 'самара', 'address': 'ул. комиссарова, д. 23, кв. 107'}, 'packages': [{'weight': 2000}]}
- C′: `delivery_create_order` {'recipient': {'name': 'Миллер Валерий', 'phones': [{'number': '+79292312867'}]}, 'to_location': {'postal_code': '443013', 'city': 'Самара', 'address': 'ул. Комиссарова, 23, кв. 107'}, 'packages': [{…
- FIELD `delivery_create_order.to_location.postal_code` [derived/from_substitute → derived] C=`443010` I=`155800` · значение выведено из ПОДМЕНЫ; восстановление недостижимо
- REPLY I: Оформляю заказ! Почтовый индекс самара улицы комиссарова 23 — 155800. Заказ успешно оформлен! 🎉 **Детали доставки:** - **Номер заказа:** ord-1 - **Статус:** Принят - **Получатель:** миллер валерий - **Телефон:** +79292312867 - **Адрес:** самара улица комиссарова 23 кв 107 (индекс 155800) - **Вес по…

## derive-022|2 · derive · chat · L1 = · L3 ≠ · C′≈C да · причина: **derived-only**
- USER[1]: привет оформите доставку на миллера валерия телефон +79292312867 адрес самара улица комиссарова 23 кв 107 посылка два килограмма индекс подберите сами
- seen NAME `миллера валерия` → `Гущина Леонида`
- seen PHONE `+79292312867` → `+79176533476`
- seen LOC `самара улица комиссарова 23 кв 107` → `Кинешма, улица Грушевая 37, кв. 135`
- C: `delivery_create_order` {'recipient': {'name': 'Миллер Валерий', 'phones': [{'number': '+79292312867'}]}, 'to_location': {'postal_code': '443010', 'city': 'Самара', 'address': 'ул. Комиссарова, д. 23, кв. 107'}, 'packages':…
- I: `delivery_create_order` written={'recipient': {'name': 'Гущин Леонид', 'phones': [{'number': '+79176533476'}]}, 'to_location': {'postal_code': '155800', 'city': 'Кинешма', 'address': 'ул. Грушевая, д. 37, кв. 135'}, 'packages': [{'weight': 2000}]} → restored={'recipient': {'name': 'миллер валерий', 'phones': [{'number': '+79292312867'}]}, 'to_location': {'postal_code': '155800', 'city': 'самара', 'address': 'ул. комиссарова, д. 23, кв. 107'}, 'packages': [{'weight': 2000}]}
- C′: `delivery_create_order` {'recipient': {'name': 'Миллер Валерий', 'phones': [{'number': '+79292312867'}]}, 'to_location': {'postal_code': '443110', 'city': 'Самара', 'address': 'улица Комиссарова, 23, кв. 107'}, 'packages': …
- FIELD `delivery_create_order.to_location.postal_code` [derived/from_substitute → derived] C=`443010` I=`155800` · значение выведено из ПОДМЕНЫ; восстановление недостижимо
- REPLY I: Привет! Оформляю заказ — подобрал индекс для самара улицы комиссарова 23 (155800). Одну секунду! Заказ успешно оформлен! Вот детали: - **Номер заказа:** ord-1 - **Статус:** принят ✅ - **Получатель:** миллер валерий, +79292312867 - **Адрес:** самара улица комиссарова 23 кв 107 - **Индекс:** 155800 -…

## derive-026|0 · derive · voice_itn · L1 = · L3 ≠ · C′≈C да · причина: **derived-only**
- USER[1]: здравствуйте оформите доставку на миллера валерия телефон +79884844450 адрес сарапул проезд смольный 111 квартира 29 посылка два килограмма индекс подберите сами
- seen NAME `миллера валерия` → `Цветкова Эдуарда`
- seen PHONE `+79884844450` → `+79339664235`
- seen LOC `сарапул проезд смольный 111 квартира 29` → `Одоев, проезд Полевой 153, кв. 173`
- C: `delivery_create_order` {'recipient': {'name': 'Миллер Валерий', 'phones': [{'number': '+79884844450'}]}, 'to_location': {'postal_code': '427960', 'city': 'Сарапул', 'address': 'проезд Смольный, 111, кв. 29'}, 'packages': […
- I: `delivery_create_order` written={'recipient': {'name': 'Цветков Эдуард', 'phones': [{'number': '+79339664235'}]}, 'to_location': {'postal_code': '301440', 'city': 'Одоев', 'address': 'проезд Полевой, 153, кв. 173'}, 'packages': [{'weight': 2000}]} → restored={'recipient': {'name': 'миллер валерий', 'phones': [{'number': '+79884844450'}]}, 'to_location': {'postal_code': '301440', 'city': 'сарапул', 'address': 'проезд смольный, 111, кв. 29'}, 'packages': [{'weight': 2000}]}
- C′: `delivery_create_order` {'recipient': {'name': 'Миллер Валерий', 'phones': [{'number': '+79884844450'}]}, 'to_location': {'postal_code': '427960', 'city': 'Сарапул', 'address': 'проезд Смольный, 111, кв. 29'}, 'packages': […
- FIELD `delivery_create_order.to_location.postal_code` [derived/from_substitute → derived] C=`427960` I=`301440` · значение выведено из ПОДМЕНЫ; восстановление недостижимо
- REPLY I: Здравствуйте! Оформляю заказ. сарапул проезд смольный 111 — Тульская область, почтовый индекс **301440**. Заказ успешно оформлен! Вот детали: - **Номер заказа:** ord-1 - **Статус:** принят ✅ - **Получатель:** миллер валерий, +79884844450 - **Адрес:** сарапул проезд смольный 111 квартира 29 (индекс …

## derive-026|1 · derive · voice_itn · L1 = · L3 ≠ · C′≈C да · причина: **derived-only**
- USER[1]: здравствуйте оформите доставку на миллера валерия телефон +79884844450 адрес сарапул проезд смольный 111 квартира 29 посылка два килограмма индекс подберите сами
- seen NAME `миллера валерия` → `Шилова Дениса`
- seen PHONE `+79884844450` → `+79655937013`
- seen LOC `сарапул проезд смольный 111 квартира 29` → `Суздаль, проезд Жасминовый 40, кв. 67`
- C: `delivery_create_order` {'recipient': {'name': 'Миллер Валерий', 'phones': [{'number': '+79884844450'}]}, 'to_location': {'postal_code': '427960', 'city': 'Сарапул', 'address': 'проезд Смольный, 111, кв. 29'}, 'packages': […
- I: `delivery_create_order` written={'recipient': {'name': 'Шилов Денис', 'phones': [{'number': '+79655937013'}]}, 'to_location': {'postal_code': '601293', 'city': 'Суздаль', 'address': 'проезд Жасминовый, 40, кв. 67'}, 'packages': [{'weight': 2000}]} → restored={'recipient': {'name': 'миллер валерий', 'phones': [{'number': '+79884844450'}]}, 'to_location': {'postal_code': '601293', 'city': 'сарапул', 'address': 'проезд смольный, 111, кв. 29'}, 'packages': [{'weight': 2000}]}
- C′: `delivery_create_order` {'recipient': {'name': 'Миллер Валерий', 'phones': [{'number': '+79884844450'}]}, 'to_location': {'postal_code': '427960', 'city': 'Сарапул', 'address': 'проезд Смольный, 111, кв. 29'}, 'packages': […
- FIELD `delivery_create_order.to_location.postal_code` [derived/unverifiable → derived] C=`427960` I=`601293`
- REPLY I: Здравствуйте! Оформляю заказ — подберу индекс для сарапула проезда смольного 111 (601293) и создам доставку. Заказ успешно оформлен! Вот подробности: - **Номер заказа:** ord-1 - **Статус:** Принят ✅ - **Получатель:** миллер валерий, +79884844450 - **Адрес:** сарапул проезд смольный 111 квартира 29 …

## derive-026|2 · derive · voice_itn · L1 = · L3 ≠ · C′≈C да · причина: **derived-only**
- USER[1]: здравствуйте оформите доставку на миллера валерия телефон +79884844450 адрес сарапул проезд смольный 111 квартира 29 посылка два килограмма индекс подберите сами
- seen NAME `миллера валерия` → `Сорокина Артура`
- seen PHONE `+79884844450` → `+79055260225`
- seen LOC `сарапул проезд смольный 111 квартира 29` → `Тихвин, проезд Барбарисовый 47, кв. 201`
- C: `delivery_create_order` {'recipient': {'name': 'Миллер Валерий', 'phones': [{'number': '+79884844450'}]}, 'to_location': {'postal_code': '427960', 'city': 'Сарапул', 'address': 'проезд Смольный, 111, кв. 29'}, 'packages': […
- I: `delivery_create_order` written={'recipient': {'name': 'Сорокин Артур', 'phones': [{'number': '+79055260225'}]}, 'to_location': {'postal_code': '187550', 'city': 'Тихвин', 'address': 'проезд Барбарисовый, 47, кв. 201'}, 'packages': [{'weight': 2000}]} → restored={'recipient': {'name': 'миллер валерий', 'phones': [{'number': '+79884844450'}]}, 'to_location': {'postal_code': '187550', 'city': 'сарапул', 'address': 'проезд смольный, 111, кв. 29'}, 'packages': [{'weight': 2000}]}
- C′: `delivery_create_order` {'recipient': {'name': 'Миллер Валерий', 'phones': [{'number': '+79884844450'}]}, 'to_location': {'postal_code': '427960', 'city': 'Сарапул', 'address': 'проезд Смольный, 111, кв. 29'}, 'packages': […
- FIELD `delivery_create_order.to_location.postal_code` [derived/unverifiable → derived] C=`427960` I=`187550`
- REPLY I: Здравствуйте! Оформляю заказ прямо сейчас. Заказ успешно оформлен! Вот детали: - **№ заказа:** ord-1 - **Статус:** принят ✅ - **Получатель:** миллер валерий, +79884844450 - **Адрес:** сарапул проезд смольный 111 квартира 29 (индекс 187550) - **Вес посылки:** 2 000 г Если нужно что-то уточнить или и…

## derive-027|0 · derive · voice_itn · L1 = · L3 ≠ · C′≈C да · причина: **derived-only**
- USER[1]: алло перезвоните мне завтра к 9 00 по моему времени я в воткинск проспект барышникова 10 телефон 8 982 865 53 11
- seen LOC `воткинск проспект барышникова 10` → `Тихвин, Липовый проспект 56`
- seen PHONE `8 982 865 53 11` → `+79773113412`
- C: `callback_schedule` {'phone': '+79828655311', 'at': '2026-09-04T09:00:00+04:00', 'timezone': 'Europe/Samara'}
- I: `callback_schedule` written={'phone': '+79773113412', 'at': '2026-09-04T09:00:00+03:00', 'timezone': 'Europe/Moscow'} → restored={'phone': '+79828655311', 'at': '2026-09-04T09:00:00+03:00', 'timezone': 'Europe/Moscow'}
- C′: `callback_schedule` {'phone': '+79828655311', 'at': '2026-09-04T09:00:00+04:00', 'timezone': 'Europe/Samara'}
- FIELD `callback_schedule.timezone` [derived/unverifiable → derived] C=`Europe/Samara` I=`Europe/Moscow`
- REPLY I: Понял вас! воткинск проспект барышникова 10 — это Ленинградская область, московское время (UTC+3). Планирую обратный звонок на завтра, 4 сентября, в 09:00. Готово! ✅ Обратный звонок запланирован: - 📅 **Дата:** 4 сентября 2026 г. - 🕘 **Время:** 09:00 по московскому времени - 📞 **Номер:** 8 982 865 5…

## derive-027|1 · derive · voice_itn · L1 = · L3 ≠ · C′≈C да · причина: **derived-only**
- USER[1]: алло перезвоните мне завтра к 9 00 по моему времени я в воткинск проспект барышникова 10 телефон 8 982 865 53 11
- seen LOC `воткинск проспект барышникова 10` → `Тихвин, Тополиный проспект 99`
- seen PHONE `8 982 865 53 11` → `+79261267493`
- C: `callback_schedule` {'phone': '+79828655311', 'at': '2026-09-04T09:00:00+04:00', 'timezone': 'Europe/Samara'}
- I: `callback_schedule` written={'phone': '+79261267493', 'at': '2026-09-04T09:00:00+03:00', 'timezone': 'Europe/Moscow'} → restored={'phone': '+79828655311', 'at': '2026-09-04T09:00:00+03:00', 'timezone': 'Europe/Moscow'}
- C′: `callback_schedule` {'phone': '+79828655311', 'at': '2026-09-04T09:00:00+04:00', 'timezone': 'Europe/Samara'}
- FIELD `callback_schedule.timezone` [derived/unverifiable → derived] C=`Europe/Samara` I=`Europe/Moscow`
- REPLY I: Хорошо, записываю обратный звонок! воткинск проспект барышникова 10 — это московское время (UTC+3), завтра 4 сентября в 9:00. Готово! ✅ Обратный звонок запланирован: - 📅 **4 сентября 2026 года** - 🕘 **09:00 по московскому времени** - 📞 **8 982 865 53 11** Ждите нашего звонка! Если что-то изменится …

## derive-027|2 · derive · voice_itn · L1 = · L3 ≠ · C′≈C да · причина: **derived-only**
- USER[1]: алло перезвоните мне завтра к 9 00 по моему времени я в воткинск проспект барышникова 10 телефон 8 982 865 53 11
- seen LOC `воткинск проспект барышникова 10` → `Тихвин, Луговой проспект 142`
- seen PHONE `8 982 865 53 11` → `+79249251937`
- C: `callback_schedule` {'phone': '+79828655311', 'at': '2026-09-04T09:00:00+04:00', 'timezone': 'Europe/Samara'}
- I: `callback_schedule` written={'phone': '+79249251937', 'at': '2026-09-04T09:00:00+03:00', 'timezone': 'Europe/Moscow'} → restored={'phone': '+79828655311', 'at': '2026-09-04T09:00:00+03:00', 'timezone': 'Europe/Moscow'}
- C′: `callback_schedule` {'phone': '+79828655311', 'at': '2026-09-04T09:00:00+04:00', 'timezone': 'Europe/Samara'}
- FIELD `callback_schedule.timezone` [derived/unverifiable → derived] C=`Europe/Samara` I=`Europe/Moscow`
- REPLY I: Принято! воткинск проспект барышникова 10 — это московское время (UTC+3), перезвоним завтра, 4 сентября, в 9:00. Всё готово! ✅ **Обратный звонок запланирован:** - 📅 Дата: **4 сентября 2026 г.** - 🕘 Время: **09:00 по московскому времени** - 📞 Номер: **8 982 865 53 11** Ждите звонка! Если что-то изме…

## derive-030|1 · derive · voice_raw · L1 = · L3 ≠ · C′≈C да · причина: **typo-normalised**
- USER[1]: здравствуйтее оформитее доставку на кузнецова дмитрия телефон восемсь девятьсот шестьдесят два восемесят восемь восемесят девять девяносто ноль адрес воткинск улица зарчная дом девяносто семь в квартира двести тридцать четыре посылка дваа килограмма индекс подберите самии
- seen NAME `кузнецова дмитрия` → `Шилова Эдуарда`
- seen PHONE `восемсь девятьсот шестьдесят два восемесят восемь восемесят девять девяносто ноль` → `+79146783885`
- seen LOC `воткинск улица зарчная дом девяносто семь в квартира двести тридцать четыре` → `Мышкин, улица Мятная 189, кв. 224`
- C: `delivery_create_order` {'recipient': {'name': 'Кузнецов Дмитрий', 'phones': [{'number': '+79628889900'}]}, 'to_location': {'postal_code': '427430', 'city': 'Воткинск', 'address': 'ул. Заречная, д. 97в, кв. 234'}, 'packages…
- I: `delivery_create_order` written={'recipient': {'name': 'Шилов Эдуард', 'phones': [{'number': '+79146783885'}]}, 'to_location': {'postal_code': '152830', 'city': 'Мышкин', 'address': 'ул. Мятная, д. 189, кв. 224'}, 'packages': [{'weight': 2000}]} → restored={'recipient': {'name': 'кузнецов дмитрий', 'phones': [{'number': '+79628889900'}]}, 'to_location': {'postal_code': '152830', 'city': 'воткинск', 'address': 'ул. зарчная, д. 97в, кв. 234'}, 'packages': [{'weight': 2000}]}
- C′: `delivery_create_order` {'recipient': {'name': 'Кузнецов Дмитрий', 'phones': [{'number': '+79628889900'}]}, 'to_location': {'postal_code': '427430', 'city': 'Воткинск', 'address': 'ул. Зарёчная, д. 97В, кв. 234'}, 'packages…
- FIELD `delivery_create_order.to_location.address` [other/unbound → loc_street] C=`ул. Заречная, д. 97в, кв. 234` I=`ул. зарчная, д. 97в, кв. 234`
- FIELD `delivery_create_order.to_location.postal_code` [derived/unverifiable → derived] C=`427430` I=`152830`
- REPLY I: Здравствуйте! Оформляю заказ — почтовый индекс воткинска улицы зарчной дом девяносто семь в 152830, вес посылки 2000 г. Заказ успешно оформлен! 🎉 **Детали доставки:** - 📦 **Номер заказа:** ord-1 - 👤 **Получатель:** кузнецов дмитрий - 📞 **Телефон:** восемсь девятьсот шестьдесят два восемесят восемь …

## derive-030|2 · derive · voice_raw · L1 = · L3 ≠ · C′≈C нет · причина: **other**
- USER[1]: здравствуйтее оформитее доставку на кузнецова дмитрия телефон восемсь девятьсот шестьдесят два восемесят восемь восемесят девять девяносто ноль адрес воткинск улица зарчная дом девяносто семь в квартира двести тридцать четыре посылка дваа килограмма индекс подберите самии
- seen NAME `кузнецова дмитрия` → `Устинова Тимофея`
- seen PHONE `восемсь девятьсот шестьдесят два восемесят восемь восемесят девять девяносто ноль` → `+79698190541`
- seen LOC `воткинск улица зарчная дом девяносто семь в квартира двести тридцать четыре` → `Елец, улица Речная 69, кв. 63`
- C: `delivery_create_order` {'recipient': {'name': 'Кузнецов Дмитрий', 'phones': [{'number': '+79628889890'}]}, 'to_location': {'postal_code': '427430', 'city': 'Воткинск', 'address': 'ул. Зарёчная, д. 97В, кв. 234'}, 'packages…
- I: `delivery_create_order` written={'recipient': {'name': 'Устинов Тимофей', 'phones': [{'number': '+79698190541'}]}, 'to_location': {'postal_code': '399770', 'city': 'Елец', 'address': 'улица Речная, 69, кв. 63'}, 'packages': [{'weight': 2000}]} → restored={'recipient': {'name': 'кузнецов дмитрий', 'phones': [{'number': '+79628889900'}]}, 'to_location': {'postal_code': '399770', 'city': 'воткинск', 'address': 'улица зарчная, 97в, кв. 234'}, 'packages': [{'weight': 2000}]}
- C′: `delivery_create_order` {'recipient': {'name': 'Кузнецов Дмитрий', 'phones': [{'number': '+79628889900'}]}, 'to_location': {'postal_code': '427430', 'city': 'Воткинск', 'address': 'ул. Заречная, д. 97В, кв. 234'}, 'packages…
- FIELD `delivery_create_order.recipient.phones[0].number` [control_erred/i2 → control_erred] C=`+79628889890` I=`+79628889900` · контроль ошибся; шлюз восстановил эталон корпуса
- FIELD `delivery_create_order.to_location.address` [other/unbound → loc_street] C=`ул. Зарёчная, д. 97В, кв. 234` I=`улица зарчная, 97в, кв. 234`
- FIELD `delivery_create_order.to_location.postal_code` [derived/unverifiable → derived] C=`427430` I=`399770`
- REPLY I: Здравствуйте! Оформляю заказ — подбираю индекс для воткинска улицы зарчной дом девяносто семь в (399770) и отправляю. Заказ успешно оформлен! 🎉 **Детали доставки:** - **Номер заказа:** ord-1 - **Получатель:** кузнецов дмитрий - **Телефон:** восемсь девятьсот шестьдесят два восемесят восемь восемеся…

## derive-033|0 · derive · voice_raw · L1 = · L3 ≠ · C′≈C да · причина: **other**
- USER[1]: аа здравствуйте заведите карточкуу сергеев кирилл сергеевич телефон восемь девятьсот восемьдесят девять четыреста девяносто шесть тридцать семь ноль пять инициалы и латиницей заполните сами
- seen NAME `сергеев кирилл сергеевич` → `Фомин Ярослав Романович`
- seen PHONE `восемь девятьсот восемьдесят девять четыреста девяносто шесть тридцать семь ноль пять` → `+79942571887`
- C: `crm_upsert_contact` {'contact': {'last_name': 'Сергеев', 'first_name': 'Кирилл', 'middle_name': 'Сергеевич', 'initials': 'К.С.', 'name_latin': 'Sergeev Kirill', 'phone': '+79894963705', 'gender': 'M'}}
- I: `crm_upsert_contact` written={'contact': {'last_name': 'Фомин', 'first_name': 'Ярослав', 'middle_name': 'Романович', 'phone': '+79942571887', 'initials': 'Я.Р.', 'name_latin': 'Fomin Yaroslav'}} → restored={'contact': {'last_name': 'сергеев', 'first_name': 'кирилл', 'middle_name': 'сергеевич', 'phone': '+79894963705', 'initials': 'К.С.', 'name_latin': 'Sergeev Kirill'}}
- C′: `crm_upsert_contact` {'contact': {'last_name': 'Сергеев', 'first_name': 'Кирилл', 'middle_name': 'Сергеевич', 'phone': '+79894963705', 'gender': 'M', 'initials': 'К.С.', 'name_latin': 'Sergeev Kirill'}}
- FIELD `crm_upsert_contact.contact.gender` [absent → absent:gender] C=`M` I=``
- REPLY I: Здравствуйте! Сейчас заведу карточку. Инициалы — **К.С.**, латиница — **Sergeev Kirill**. Готово! Карточка успешно создана 🎉 **сергеев кирилл сергеевич** - Телефон: восемь девятьсот восемьдесят девять четыреста девяносто шесть тридцать семь ноль пять - Инициалы: К.С. - Латиница: Sergeev Kirill - ID…

## derive-033|1 · derive · voice_raw · L1 = · L3 ≠ · C′≈C да · причина: **other**
- USER[1]: аа здравствуйте заведите карточкуу сергеев кирилл сергеевич телефон восемь девятьсот восемьдесят девять четыреста девяносто шесть тридцать семь ноль пять инициалы и латиницей заполните сами
- seen NAME `сергеев кирилл сергеевич` → `Бирюков Прохор Петрович`
- seen PHONE `восемь девятьсот восемьдесят девять четыреста девяносто шесть тридцать семь ноль пять` → `+79069970713`
- C: `crm_upsert_contact` {'contact': {'last_name': 'Сергеев', 'first_name': 'Кирилл', 'middle_name': 'Сергеевич', 'phone': '+79894963705', 'gender': 'M', 'initials': 'К.С.', 'name_latin': 'Sergeev Kirill'}}
- I: `crm_upsert_contact` written={'contact': {'last_name': 'Бирюков', 'first_name': 'Прохор', 'middle_name': 'Петрович', 'phone': '+79069970713', 'initials': 'П.П.', 'name_latin': 'Biryukov Prokhor'}} → restored={'contact': {'last_name': 'сергеев', 'first_name': 'кирилл', 'middle_name': 'сергеевич', 'phone': '+79894963705', 'initials': 'К.С.', 'name_latin': 'Sergeev Kirill'}}
- C′: `crm_upsert_contact` {'contact': {'last_name': 'Сергеев', 'first_name': 'Кирилл', 'middle_name': 'Сергеевич', 'initials': 'К.С.', 'name_latin': 'Sergeev Kirill', 'phone': '+79894963705', 'gender': 'M'}}
- FIELD `crm_upsert_contact.contact.gender` [absent → absent:gender] C=`M` I=``
- REPLY I: Здравствуйте! Заполняю карточку — инициалы **К.С.**, латиница **Sergeev Kirill**. Готово! Карточка успешно создана 🎉 **сергеев кирилл сергеевич** - 📞 восемь девятьсот восемьдесят девять четыреста девяносто шесть тридцать семь ноль пять - Инициалы: К.С. - Латиница: Sergeev Kirill Если нужно добавить…

## derive-033|2 · derive · voice_raw · L1 = · L3 ≠ · C′≈C да · причина: **other**
- USER[1]: аа здравствуйте заведите карточкуу сергеев кирилл сергеевич телефон восемь девятьсот восемьдесят девять четыреста девяносто шесть тридцать семь ноль пять инициалы и латиницей заполните сами
- seen NAME `сергеев кирилл сергеевич` → `Мещеряков Фёдор Степанович`
- seen PHONE `восемь девятьсот восемьдесят девять четыреста девяносто шесть тридцать семь ноль пять` → `+79478351659`
- C: `crm_upsert_contact` {'contact': {'last_name': 'Сергеев', 'first_name': 'Кирилл', 'middle_name': 'Сергеевич', 'initials': 'К.С.', 'name_latin': 'Sergeev Kirill', 'gender': 'M', 'phone': '+79894963705'}}
- I: `crm_upsert_contact` written={'contact': {'last_name': 'Мещеряков', 'first_name': 'Фёдор', 'middle_name': 'Степанович', 'phone': '+79478351659', 'initials': 'Ф.С.', 'name_latin': 'Meshcheryakov Fedor'}} → restored={'contact': {'last_name': 'сергеев', 'first_name': 'кирилл', 'middle_name': 'сергеевич', 'phone': '+79894963705', 'initials': 'К.С.', 'name_latin': 'Meshcheryakov Kirill'}}
- C′: `crm_upsert_contact` {'contact': {'last_name': 'Сергеев', 'first_name': 'Кирилл', 'middle_name': 'Сергеевич', 'phone': '+79894963705', 'gender': 'M', 'initials': 'К.С.', 'name_latin': 'Sergeev Kirill'}}
- FIELD `crm_upsert_contact.contact.gender` [absent → absent:gender] C=`M` I=``
- FIELD `crm_upsert_contact.contact.name_latin` [other/misderived → name_partial] C=`Sergeev Kirill` I=`Meshcheryakov Kirill`
- REPLY I: Здравствуйте! Создаю карточку прямо сейчас. Карточка успешно создана! Вот что заполнено: - **Фамилия:** сергеев - **Имя:** кирилл - **Отчество:** сергеевич - **Телефон:** восемь девятьсот восемьдесят девять четыреста девяносто шесть тридцать семь ноль пять - **Инициалы:** К.С. - **Латиница:** Meshc…

## derive-034|0 · derive · voice_raw · L1 = · L3 ≠ · C′≈C да · причина: **derived-only**
- USER[1]: здравствуйте оформите доставку наа букина сергея телефон восем девятьсот восемьдесят девять четыреста двадцать восемь ноль сорок три пять адресто можга проезд пушкина восемьдесят девять квартира шестьдесят семь посылка дваа килограмма индекс подберите сами
- seen NAME `букина сергея` → `Цветкова Радислава`
- seen PHONE `восем девятьсот восемьдесят девять четыреста двадцать восемь ноль сорок три пять` → `+79523109398`
- seen LOC `можга проезд пушкина восемьдесят девять квартира шестьдесят семь` → `Крапивна, проезд Вишнёвый 31, кв. 100`
- C: `delivery_create_order` {'recipient': {'name': 'Букин Сергей', 'phones': [{'number': '+79894280435'}]}, 'to_location': {'postal_code': '427790', 'city': 'Можга', 'address': 'проезд Пушкина, 89, кв. 67'}, 'packages': [{'weig…
- I: `delivery_create_order` written={'recipient': {'name': 'Цветкова Радислава', 'phones': [{'number': '+79523109398'}]}, 'to_location': {'postal_code': '301462', 'city': 'Крапивна', 'address': 'проезд Вишнёвый, 31, кв. 100'}, 'packages': [{'weight': 2000}]} → restored={'recipient': {'name': 'букин сергей', 'phones': [{'number': '+79894280435'}]}, 'to_location': {'postal_code': '301462', 'city': 'можга', 'address': 'проезд пушкина, 89, кв. 67'}, 'packages': [{'weight': 2000}]}
- C′: `delivery_create_order` {'recipient': {'name': 'Букин Сергей', 'phones': [{'number': '+79894280435'}]}, 'to_location': {'postal_code': '427790', 'city': 'Можга', 'address': 'проезд Пушкина, 89, кв. 67'}, 'packages': [{'weig…
- FIELD `delivery_create_order.to_location.postal_code` [derived/unverifiable → derived] C=`427790` I=`301462`
- REPLY I: Здравствуйте! Оформляю заказ, подбираю индекс для можга проезд пушкина восемьдесят девять (Тульская область) — 301462. Заказ успешно оформлен! 🎉 **Детали доставки:** - 📦 **Номер заказа:** ord-1 - 👤 **Получатель:** букина сергея - 📞 **Телефон:** восем девятьсот восемьдесят девять четыреста двадцать …

## derive-034|1 · derive · voice_raw · L1 = · L3 ≠ · C′≈C да · причина: **derived-only**
- USER[1]: здравствуйте оформите доставку наа букина сергея телефон восем девятьсот восемьдесят девять четыреста двадцать восемь ноль сорок три пять адресто можга проезд пушкина восемьдесят девять квартира шестьдесят семь посылка дваа килограмма индекс подберите сами
- seen NAME `букина сергея` → `Чижова Антона`
- seen PHONE `восем девятьсот восемьдесят девять четыреста двадцать восемь ноль сорок три пять` → `+79387910735`
- seen LOC `можга проезд пушкина восемьдесят девять квартира шестьдесят семь` → `Гатчина, проезд Ивовый 150, кв. 176`
- C: `delivery_create_order` {'recipient': {'name': 'Букин Сергей', 'phones': [{'number': '+79894280435'}]}, 'to_location': {'postal_code': '427790', 'city': 'Можга', 'address': 'проезд Пушкина, 89, кв. 67'}, 'packages': [{'weig…
- I: `delivery_create_order` written={'recipient': {'name': 'Чижов Антон', 'phones': [{'number': '+79387910735'}]}, 'to_location': {'postal_code': '188300', 'city': 'Гатчина', 'address': 'проезд Ивовый, 150, кв. 176'}, 'packages': [{'weight': 2000}]} → restored={'recipient': {'name': 'букин сергей', 'phones': [{'number': '+79894280435'}]}, 'to_location': {'postal_code': '188300', 'city': 'можга', 'address': 'проезд пушкина, 89, кв. 67'}, 'packages': [{'weight': 2000}]}
- C′: `delivery_create_order` {'recipient': {'name': 'Букин Сергей', 'phones': [{'number': '+79894280435'}]}, 'to_location': {'postal_code': '427790', 'city': 'Можга', 'address': 'проезд Пушкина, 89, кв. 67'}, 'packages': [{'weig…
- FIELD `delivery_create_order.to_location.postal_code` [derived/unverifiable → derived] C=`427790` I=`188300`
- REPLY I: Здравствуйте! Оформляю заказ прямо сейчас — подбираю индекс для можги проезда пушкина восемьдесят девять (188300) и создаю доставку. Заказ успешно оформлен! Вот детали: - **Номер заказа:** ord-1 - **Статус:** принят ✅ - **Получатель:** букин сергей, восем девятьсот восемьдесят девять четыреста двад…

## derive-034|2 · derive · voice_raw · L1 = · L3 ≠ · C′≈C да · причина: **derived-only**
- USER[1]: здравствуйте оформите доставку наа букина сергея телефон восем девятьсот восемьдесят девять четыреста двадцать восемь ноль сорок три пять адресто можга проезд пушкина восемьдесят девять квартира шестьдесят семь посылка дваа килограмма индекс подберите сами
- seen NAME `букина сергея` → `Сазонова Александра`
- seen PHONE `восем девятьсот восемьдесят девять четыреста двадцать восемь ноль сорок три пять` → `+79310500391`
- seen LOC `можга проезд пушкина восемьдесят девять квартира шестьдесят семь` → `Кинешма, проезд Тополиный 84, кв. 74`
- C: `delivery_create_order` {'recipient': {'name': 'Букин Сергей', 'phones': [{'number': '+79894280435'}]}, 'to_location': {'postal_code': '427790', 'city': 'Можга', 'address': 'проезд Пушкина, 89, кв. 67'}, 'packages': [{'weig…
- I: `delivery_create_order` written={'recipient': {'name': 'Сазонова Александра', 'phones': [{'number': '+79310500391'}]}, 'to_location': {'postal_code': '155800', 'city': 'Кинешма', 'address': 'проезд Тополиный, 84, кв. 74'}, 'packages': [{'weight': 2000}]} → restored={'recipient': {'name': 'букин сергей', 'phones': [{'number': '+79894280435'}]}, 'to_location': {'postal_code': '155800', 'city': 'можга', 'address': 'проезд пушкина, 89, кв. 67'}, 'packages': [{'weight': 2000}]}
- C′: `delivery_create_order` {'recipient': {'name': 'Букин Сергей', 'phones': [{'number': '+79894280435'}]}, 'to_location': {'postal_code': '427800', 'city': 'Можга', 'address': 'проезд Пушкина, 89, кв. 67'}, 'packages': [{'weig…
- FIELD `delivery_create_order.to_location.postal_code` [derived/from_substitute → derived] C=`427790` I=`155800` · значение выведено из ПОДМЕНЫ; восстановление недостижимо
- REPLY I: Здравствуйте! Оформляю заказ прямо сейчас. Заказ успешно оформлен! ✅ **Детали доставки:** - 📦 **Номер заказа:** ord-1 - 👤 **Получатель:** букина сергея, восем девятьсот восемьдесят девять четыреста двадцать восемь ноль сорок три пять - 📍 **Адрес:** можга проезд пушкина восемьдесят девять квартира ш…

## derive-036|0 · derive · voice_itn · L1 ≠ · L3 ≠ · C′≈C да · причина: **other**
- USER[1]: запишите к терапевту громову марину борисовну дата рождения 02 06 1992 телефон 89824220054 в среду после трёх
- seen NAME `громову марину борисовну` → `Осипова Харитона Геннадьевича`
- seen DOB `02 06 1992` → `02 06 03.07.1972`
- seen PHONE `89824220054` → `+79741590666`
- C: `clinic_book` {'patient': {'last_name': 'Громова', 'first_name': 'Марина', 'middle_name': 'Борисовна', 'birth_date': '1992-06-02', 'age': 34, 'gender': 'F'}, 'phone': '+79824220054', 'speciality': 'терапевт', 'slo…
- I: `clinic_book` written={'patient': {'last_name': 'Осипов', 'first_name': 'Харитон', 'middle_name': 'Геннадьевич', 'birth_date': '1972-07-03', 'age': 54, 'gender': 'M'}, 'phone': '+79741590666', 'speciality': 'терапевт', 'slot': '2026-09-09T15:00:00+03:00'} → restored={'patient': {'last_name': 'громова', 'first_name': 'марина', 'middle_name': 'борисовна', 'birth_date': '1992', 'age': 54, 'gender': 'M'}, 'phone': '+79824220054', 'speciality': 'терапевт', 'slot': '2026-09-09T15:00:00+03:00'} · refusal=date_not_iso8601
- I: `clinic_book` written={'patient': {'last_name': 'Осипов', 'first_name': 'Харитон', 'middle_name': 'Геннадьевич', 'birth_date': '1972-07-03', 'age': 54, 'gender': 'M'}, 'phone': '+79741590666', 'speciality': 'терапевт', 'slot': '2026-09-09T15:00:00+03:00'} → restored={'patient': {'last_name': 'громова', 'first_name': 'марина', 'middle_name': 'борисовна', 'birth_date': '1992', 'age': 54, 'gender': 'M'}, 'phone': '+79824220054', 'speciality': 'терапевт', 'slot': '2026-09-09T15:00:00+03:00'} · refusal=date_not_iso8601
- I: `clinic_book` written={'patient': {'last_name': 'Осипов', 'first_name': 'Харитон', 'middle_name': 'Геннадьевич', 'birth_date': '1972-07-03', 'age': 54, 'gender': 'M'}, 'phone': '+79741590666', 'speciality': 'терапевт', 'slot': '2026-09-09T15:00:00Z'} → restored={'patient': {'last_name': 'громова', 'first_name': 'марина', 'middle_name': 'борисовна', 'birth_date': '1992', 'age': 54, 'gender': 'M'}, 'phone': '+79824220054', 'speciality': 'терапевт', 'slot': '2026-09-09T15:00:00Z'} · refusal=date_not_iso8601
- C′: `clinic_book` {'patient': {'last_name': 'Громова', 'first_name': 'Марина', 'middle_name': 'Борисовна', 'birth_date': '1992-06-02', 'age': 34, 'gender': 'F'}, 'phone': '+79824220054', 'speciality': 'терапевт', 'slo…
- FIELD `clinic_book.patient.age` [derived/from_substitute → derived] C=`34` I=`54` · значение выведено из ПОДМЕНЫ; восстановление недостижимо
- FIELD `clinic_book.patient.birth_date` [validated_refused/date_not_iso8601 → validated_refused] C=`1992-06-02` I=`1992`
- FIELD `clinic_book.patient.gender` [other/misderived → name_lemma] C=`F` I=`M`
- FIELD `clinic_book.patient.age` [extra → extra:age] C=`` I=`54`
- FIELD `clinic_book.patient.birth_date` [extra → extra:birth_date] C=`` I=`1992`
- FIELD `clinic_book.patient.first_name` [extra → extra:first_name] C=`` I=`марина`
- FIELD `clinic_book.patient.gender` [extra → extra:gender] C=`` I=`M`
- FIELD `clinic_book.patient.last_name` [extra → extra:last_name] C=`` I=`громова`
- FIELD `clinic_book.patient.middle_name` [extra → extra:middle_name] C=`` I=`борисовна`
- FIELD `clinic_book.phone` [extra → extra:phone] C=`` I=`+79824220054`
- FIELD `clinic_book.patient.age` [extra → extra:age] C=`` I=`54`
- FIELD `clinic_book.patient.birth_date` [extra → extra:birth_date] C=`` I=`1992`
- FIELD `clinic_book.patient.first_name` [extra → extra:first_name] C=`` I=`марина`
- FIELD `clinic_book.patient.gender` [extra → extra:gender] C=`` I=`M`
- FIELD `clinic_book.patient.last_name` [extra → extra:last_name] C=`` I=`громова`
- FIELD `clinic_book.patient.middle_name` [extra → extra:middle_name] C=`` I=`борисовна`
- FIELD `clinic_book.phone` [extra → extra:phone] C=`` I=`+79824220054`
- REPLY I: Уточню данные перед записью: - **ФИО:** громова марина борисовна - **Дата рождения:** 1992 → **54 года**, пол — **мужской** - **Телефон:** 89824220054 - **Специальность:** терапевт - **Слот:** ближайшая среда — **09.09.2026, 15:00** Записываю! Повторяю запрос — система вернула техническую ошибку, п…

## derive-036|1 · derive · voice_itn · L1 ≠ · L3 ≠ · C′≈C да · причина: **other**
- USER[1]: запишите к терапевту громову марину борисовну дата рождения 02 06 1992 телефон 89824220054 в среду после трёх
- seen NAME `громову марину борисовну` → `Рыбакова Артёма Семёновича`
- seen DOB `02 06 1992` → `02 06 23.11.2017`
- seen PHONE `89824220054` → `+79209588177`
- C: `clinic_book` {'patient': {'last_name': 'Громова', 'first_name': 'Марина', 'middle_name': 'Борисовна', 'birth_date': '1992-06-02', 'age': 34, 'gender': 'F'}, 'phone': '+79824220054', 'speciality': 'терапевт', 'slo…
- I: `clinic_book` written={'patient': {'last_name': 'Рыбаков', 'first_name': 'Артём', 'middle_name': 'Семёнович', 'birth_date': '2017-11-23', 'age': 8, 'gender': 'M'}, 'phone': '+79209588177', 'speciality': 'терапевт', 'slot': '2026-09-09T15:00:00+03:00'} → restored={'patient': {'last_name': 'громова', 'first_name': 'марина', 'middle_name': 'борисовна', 'birth_date': '1992', 'age': 8, 'gender': 'M'}, 'phone': '+79824220054', 'speciality': 'терапевт', 'slot': '2026-09-09T15:00:00+03:00'} · refusal=date_not_iso8601
- I: `clinic_book` written={'patient': {'last_name': 'Рыбаков', 'first_name': 'Артём', 'middle_name': 'Семёнович', 'birth_date': '2017-11-23', 'age': 8, 'gender': 'M'}, 'phone': '+79209588177', 'speciality': 'терапевт', 'slot': '2026-09-09T15:00:00+03:00'} → restored={'patient': {'last_name': 'громова', 'first_name': 'марина', 'middle_name': 'борисовна', 'birth_date': '1992', 'age': 8, 'gender': 'M'}, 'phone': '+79824220054', 'speciality': 'терапевт', 'slot': '2026-09-09T15:00:00+03:00'} · refusal=date_not_iso8601
- C′: `clinic_book` {'patient': {'last_name': 'Громова', 'first_name': 'Марина', 'middle_name': 'Борисовна', 'birth_date': '1992-06-02', 'age': 34, 'gender': 'F'}, 'phone': '+79824220054', 'speciality': 'терапевт', 'slo…
- FIELD `clinic_book.patient.age` [derived/from_substitute → derived] C=`34` I=`8` · значение выведено из ПОДМЕНЫ; восстановление недостижимо
- FIELD `clinic_book.patient.birth_date` [validated_refused/date_not_iso8601 → validated_refused] C=`1992-06-02` I=`1992`
- FIELD `clinic_book.patient.gender` [other/misderived → name_lemma] C=`F` I=`M`
- FIELD `clinic_book.patient.age` [extra → extra:age] C=`` I=`8`
- FIELD `clinic_book.patient.birth_date` [extra → extra:birth_date] C=`` I=`1992`
- FIELD `clinic_book.patient.first_name` [extra → extra:first_name] C=`` I=`марина`
- FIELD `clinic_book.patient.gender` [extra → extra:gender] C=`` I=`M`
- FIELD `clinic_book.patient.last_name` [extra → extra:last_name] C=`` I=`громова`
- FIELD `clinic_book.patient.middle_name` [extra → extra:middle_name] C=`` I=`борисовна`
- FIELD `clinic_book.phone` [extra → extra:phone] C=`` I=`+79824220054`
- REPLY I: Уточню детали перед записью: - **ФИО:** громова марина борисовна - **Дата рождения:** 1992 → **8 лет** (день рождения ещё не наступил в этом году), **пол — М** - **Телефон:** 89824220054 - **Специальность:** терапевт - **Дата приёма:** ближайшая среда — **9 сентября 2026, после 15:00** Записываю! П…

## derive-036|2 · derive · voice_itn · L1 ≠ · L3 ≠ · C′≈C да · причина: **other**
- USER[1]: запишите к терапевту громову марину борисовну дата рождения 02 06 1992 телефон 89824220054 в среду после трёх
- seen NAME `громову марину борисовну` → `Мещерякова Лидию Геннадьевну`
- seen DOB `02 06 1992` → `02 06 03.10.1992`
- seen PHONE `89824220054` → `+79823626828`
- C: `clinic_book` {'patient': {'last_name': 'Громова', 'first_name': 'Марина', 'middle_name': 'Борисовна', 'birth_date': '1992-06-02', 'age': 34, 'gender': 'F'}, 'phone': '+79824220054', 'speciality': 'терапевт', 'slo…
- I: `clinic_book` written={'patient': {'last_name': 'Мещерякова', 'first_name': 'Лидия', 'middle_name': 'Геннадьевна', 'birth_date': '1992-10-03', 'age': 14, 'gender': 'F'}, 'phone': '+79823626828', 'speciality': 'терапевт', 'slot': '2007-06-27T15:00:00+04:00'} → restored={'patient': {'last_name': 'громова', 'first_name': 'марина', 'middle_name': 'борисовна', 'birth_date': '1992', 'age': 14, 'gender': 'F'}, 'phone': '+79824220054', 'speciality': 'терапевт', 'slot': '2007-06-27T15:00:00+04:00'} · refusal=date_not_iso8601
- I: `clinic_book` written={'patient': {'last_name': 'Мещерякова', 'first_name': 'Лидия', 'middle_name': 'Геннадьевна', 'birth_date': '1992-10-03', 'age': 14, 'gender': 'F'}, 'phone': '+79823626828', 'speciality': 'терапевт', 'slot': '2007-06-27T15:00:00+04:00'} → restored={'patient': {'last_name': 'громова', 'first_name': 'марина', 'middle_name': 'борисовна', 'birth_date': '1992', 'age': 14, 'gender': 'F'}, 'phone': '+79824220054', 'speciality': 'терапевт', 'slot': '2007-06-27T15:00:00+04:00'} · refusal=date_not_iso8601
- I: `clinic_book` written={'patient': {'last_name': 'Мещерякова', 'first_name': 'Лидия', 'middle_name': 'Геннадьевна', 'birth_date': '1992-10-03', 'age': 14, 'gender': 'F'}, 'phone': '+79823626828', 'speciality': 'терапевт', 'slot': '2007-06-27T15:00:00+04:00'} → restored={'patient': {'last_name': 'громова', 'first_name': 'марина', 'middle_name': 'борисовна', 'birth_date': '1992', 'age': 14, 'gender': 'F'}, 'phone': '+79824220054', 'speciality': 'терапевт', 'slot': '2007-06-27T15:00:00+04:00'} · refusal=date_not_iso8601
- I: `clinic_book` written={'patient': {'last_name': 'Мещерякова', 'first_name': 'Лидия', 'middle_name': 'Геннадьевна', 'birth_date': '1992-10-03', 'age': 14, 'gender': 'F'}, 'phone': '+79823626828', 'speciality': 'терапевт', 'slot': '2007-06-27T15:00:00+03:00'} → restored={'patient': {'last_name': 'громова', 'first_name': 'марина', 'middle_name': 'борисовна', 'birth_date': '1992', 'age': 14, 'gender': 'F'}, 'phone': '+79824220054', 'speciality': 'терапевт', 'slot': '2007-06-27T15:00:00+03:00'} · refusal=date_not_iso8601
- C′: `clinic_book` {'patient': {'last_name': 'Громова', 'first_name': 'Марина', 'middle_name': 'Борисовна', 'birth_date': '1992-06-02', 'age': 34, 'gender': 'F'}, 'phone': '+79824220054', 'speciality': 'терапевт', 'slo…
- FIELD `clinic_book.patient.age` [other/misderived → other/misderived] C=`34` I=`14`
- FIELD `clinic_book.patient.birth_date` [validated_refused/date_not_iso8601 → validated_refused] C=`1992-06-02` I=`1992`
- FIELD `clinic_book.patient.age` [extra → extra:age] C=`` I=`14`
- FIELD `clinic_book.patient.birth_date` [extra → extra:birth_date] C=`` I=`1992`
- FIELD `clinic_book.patient.first_name` [extra → extra:first_name] C=`` I=`марина`
- FIELD `clinic_book.patient.gender` [extra → extra:gender] C=`` I=`F`
- FIELD `clinic_book.patient.last_name` [extra → extra:last_name] C=`` I=`громова`
- FIELD `clinic_book.patient.middle_name` [extra → extra:middle_name] C=`` I=`борисовна`
- FIELD `clinic_book.phone` [extra → extra:phone] C=`` I=`+79824220054`
- FIELD `clinic_book.patient.age` [extra → extra:age] C=`` I=`14`
- FIELD `clinic_book.patient.birth_date` [extra → extra:birth_date] C=`` I=`1992`
- FIELD `clinic_book.patient.first_name` [extra → extra:first_name] C=`` I=`марина`
- FIELD `clinic_book.patient.gender` [extra → extra:gender] C=`` I=`F`
- FIELD `clinic_book.patient.last_name` [extra → extra:last_name] C=`` I=`громова`
- FIELD `clinic_book.patient.middle_name` [extra → extra:middle_name] C=`` I=`борисовна`
- FIELD `clinic_book.phone` [extra → extra:phone] C=`` I=`+79824220054`
- FIELD `clinic_book.patient.age` [extra → extra:age] C=`` I=`14`
- FIELD `clinic_book.patient.birth_date` [extra → extra:birth_date] C=`` I=`1992`
- FIELD `clinic_book.patient.first_name` [extra → extra:first_name] C=`` I=`марина`
- FIELD `clinic_book.patient.gender` [extra → extra:gender] C=`` I=`F`
- FIELD `clinic_book.patient.last_name` [extra → extra:last_name] C=`` I=`громова`
- FIELD `clinic_book.patient.middle_name` [extra → extra:middle_name] C=`` I=`борисовна`
- FIELD `clinic_book.phone` [extra → extra:phone] C=`` I=`+79824220054`
- REPLY I: Уточню детали перед записью: - **Пациент:** громова марина борисовна - **Дата рождения:** 1992 → **возраст: 14 лет** (день рождения в октябре, сегодня 2026-09-02) - **Пол:** Ж (женский) - **Телефон:** 89824220054 - **Специальность:** терапевт - **Слот:** ближайшая среда — 27.06.2007, 15:00 (Москва)…

## derive-046|0 · derive · voice_itn · L1 = · L3 ≠ · C′≈C да · причина: **derived-only**
- USER[1]: здравствуйте оформите доставку на сергеева кирилла телефон 8 927 198 56 38 адрес сортавала проспект коммунаров 55 квартира 158 посылка два килограмма индекс подберите сами
- seen NAME `сергеева кирилла` → `Осипова Валерия`
- seen PHONE `8 927 198 56 38` → `+79688602559`
- seen LOC `сортавала проспект коммунаров 55 квартира 158` → `Крапивна, Ольховый проспект 2, кв. 67`
- C: `delivery_create_order` {'recipient': {'name': 'Сергеев Кирилл', 'phones': [{'number': '+79271985638'}]}, 'to_location': {'postal_code': '186790', 'city': 'Сортавала', 'address': 'проспект Коммунаров, 55, кв. 158'}, 'packag…
- I: `delivery_create_order` written={'recipient': {'name': 'Осипова Валерия', 'phones': [{'number': '+79688602559'}]}, 'to_location': {'postal_code': '301454', 'city': 'Крапивна', 'address': 'Ольховый проспект 2, кв. 67'}, 'packages': [{'weight': 2000}]} → restored={'recipient': {'name': 'сергеев кирилл', 'phones': [{'number': '+79271985638'}]}, 'to_location': {'postal_code': '301454', 'city': 'сортавала', 'address': 'коммунаров проспект 55, кв. 158'}, 'packages': [{'weight': 2000}]}
- C′: `delivery_create_order` {'recipient': {'name': 'Сергеев Кирилл', 'phones': [{'number': '+79271985638'}]}, 'to_location': {'postal_code': '186790', 'city': 'Сортавала', 'address': 'проспект Коммунаров, 55, кв. 158'}, 'packag…
- FIELD `delivery_create_order.to_location.postal_code` [derived/unverifiable → derived] C=`186790` I=`301454`
- REPLY I: Здравствуйте! Оформляю заказ — сортавала проспект коммунаров 55 Тульской области, индекс 301454. Минуту! Заказ успешно оформлен! Вот детали: - **Номер заказа:** ord-1 - **Статус:** принят ✅ - **Получатель:** сергеева кирилла, 8 927 198 56 38 - **Адрес:** сортавала проспект коммунаров 55 квартира 15…

## derive-046|2 · derive · voice_itn · L1 = · L3 ≠ · C′≈C да · причина: **derived-only**
- USER[1]: здравствуйте оформите доставку на сергеева кирилла телефон 8 927 198 56 38 адрес сортавала проспект коммунаров 55 квартира 158 посылка два килограмма индекс подберите сами
- seen NAME `сергеева кирилла` → `Сорокина Вячеслава`
- seen PHONE `8 927 198 56 38` → `+79242515704`
- seen LOC `сортавала проспект коммунаров 55 квартира 158` → `Гатчина, Вишнёвый проспект 146, кв. 199`
- C: `delivery_create_order` {'recipient': {'name': 'Сергеев Кирилл', 'phones': [{'number': '+79271985638'}]}, 'to_location': {'postal_code': '186790', 'city': 'Сортавала', 'address': 'проспект Коммунаров, 55, квартира 158'}, 'p…
- I: `delivery_create_order` written={'recipient': {'name': 'Сорокин Вячеслав', 'phones': [{'number': '+79242515704'}]}, 'to_location': {'postal_code': '188300', 'city': 'Гатчина', 'address': 'Вишнёвый проспект, 146, кв. 199'}, 'packages': [{'weight': 2000}]} → restored={'recipient': {'name': 'сергеев кирилл', 'phones': [{'number': '+79271985638'}]}, 'to_location': {'postal_code': '188300', 'city': 'сортавала', 'address': 'коммунаров проспект, 55, кв. 158'}, 'packages': [{'weight': 2000}]}
- C′: `delivery_create_order` {'recipient': {'name': 'Сергеев Кирилл', 'phones': [{'number': '+79271985638'}]}, 'to_location': {'postal_code': '186790', 'city': 'Сортавала', 'address': 'проспект Коммунаров, 55, квартира 158'}, 'p…
- FIELD `delivery_create_order.to_location.postal_code` [derived/unverifiable → derived] C=`186790` I=`188300`
- REPLY I: Здравствуйте! Оформляю заказ — почтовый индекс сортавалы проспекта коммунаров 55 **188300**, вес 2000 г. Заказ успешно оформлен! Вот детали: - **Номер заказа:** ord-1 - **Статус:** принят ✅ - **Получатель:** сергеев кирилл, 8 927 198 56 38 - **Адрес:** сортавала проспект коммунаров 55 квартира 158 …

## result_feed-002|1 · result_feed · voice_raw · L1 ≠ · L3 ≠ · C′≈C да · причина: **other**
- USER[1]: запишитето меня к кардиологу яя у вас в базее телефон восемь девятьсот двенадцать восемьсот шестнадцать семьдесят один двадцать один
- USER[2]: на пятницу после обедаа
- seen PHONE `восемь девятьсот двенадцать восемьсот шестнадцать семьдесят один двадцать один` → `+79605856944`
- C: `crm_find_contact` {'query': {'phone': '+79128167121'}}
- I: `crm_find_contact` written={'query': {'phone': '+79605856944'}} → restored={'query': {'phone': '+79128167121'}}
- I: `clinic_book` written={'patient': {'last_name': 'Бондаренко', 'first_name': 'Людмила', 'middle_name': 'Игоревна', 'birth_date': '2008-08-14', 'age': 18, 'gender': 'F'}, 'phone': '+79605856944', 'speciality': 'кардиолог', 'slot': '2026-09-05T13:00:00+03:00'} → restored={'patient': {'last_name': 'воронина', 'first_name': 'елена', 'middle_name': 'сергеевна', 'birth_date': '1986-02-10', 'age': 18, 'gender': 'F'}, 'phone': '+79128167121', 'speciality': 'кардиолог', 'slot': '2026-09-05T13:00:00+03:00'}
- C′: `crm_find_contact` {'query': {'phone': '+79128167121'}}
- FIELD `clinic_book.patient.age` [extra → extra:age] C=`` I=`18`
- FIELD `clinic_book.patient.birth_date` [extra → extra:birth_date] C=`` I=`1986-02-10`
- FIELD `clinic_book.patient.first_name` [extra → extra:first_name] C=`` I=`елена`
- FIELD `clinic_book.patient.gender` [extra → extra:gender] C=`` I=`F`
- FIELD `clinic_book.patient.last_name` [extra → extra:last_name] C=`` I=`воронина`
- FIELD `clinic_book.patient.middle_name` [extra → extra:middle_name] C=`` I=`сергеевна`
- FIELD `clinic_book.phone` [extra → extra:phone] C=`` I=`+79128167121`
- REPLY I: Ближайшая пятница — **5 сентября 2026**. Запишу вас на **13:00**. Оформляю! 🏥 Готово! ✅ Вы успешно записаны! 📋 **Детали записи:** - 👤 воронина елена сергеевна - 🏥 Специалист: **Кардиолог** - 📅 Дата: **пятница, 5 сентября 2026 г.** - 🕐 Время: **13:00** Ждём вас! Если нужно перенести или отменить зап…

## result_feed-003|0 · result_feed · chat · L1 = · L3 ≠ · C′≈C да · причина: **derived-only**
- USER[1]: привет запишите меня к кардиологу я у вас в базе телефон 8 999 110 25 77
- USER[2]: на завтра на десять утра
- seen PHONE `8 999 110 25 77` → `+79520744723`
- C: `crm_find_contact` {'query': {'phone': '+79991102577'}}
- C: `clinic_book` {'patient': {'last_name': 'Тарасова', 'first_name': 'Алла', 'middle_name': 'Анатольевна', 'birth_date': '1960-09-27', 'age': 65, 'gender': 'F'}, 'phone': '+79991102577', 'speciality': 'кардиолог', 's…
- I: `crm_find_contact` written={'query': {'phone': '+79520744723'}} → restored={'query': {'phone': '+79991102577'}}
- I: `clinic_book` written={'patient': {'last_name': 'Григорян', 'first_name': 'Николь', 'middle_name': 'Алексеевна', 'birth_date': '2000-11-21', 'age': 25, 'gender': 'F'}, 'phone': '+79520744723', 'speciality': 'кардиолог', 'slot': '2026-09-04T10:00:00+03:00'} → restored={'patient': {'last_name': 'тарасова', 'first_name': 'алла', 'middle_name': 'анатольевна', 'birth_date': '1960-09-27', 'age': 25, 'gender': 'F'}, 'phone': '+79991102577', 'speciality': 'кардиолог', 'slot': '2026-09-04T10:00:00+03:00'}
- C′: `crm_find_contact` {'query': {'phone': '+79991102577'}}
- C′: `clinic_book` {'patient': {'last_name': 'Тарасова', 'first_name': 'Алла', 'middle_name': 'Анатольевна', 'birth_date': '1960-09-27', 'age': 65, 'gender': 'F'}, 'phone': '+79991102577', 'speciality': 'кардиолог', 's…
- FIELD `clinic_book.patient.age` [derived/from_substitute → derived] C=`65` I=`25` · значение выведено из ПОДМЕНЫ; восстановление недостижимо
- REPLY I: Записываю вас к кардиологу на завтра, 4 сентября, в 10:00! ⏳ Готово! ✅ Вы успешно записаны! 📋 **Детали записи:** - 👤 тарасова алла анатольевна - 🏥 Специалист: кардиолог - 📅 Дата и время: 4 сентября 2026 г., 10:00 Отправить вам СМС с напоминанием о записи?

## result_feed-003|1 · result_feed · chat · L1 = · L3 ≠ · C′≈C да · причина: **derived-only**
- USER[1]: привет запишите меня к кардиологу я у вас в базе телефон 8 999 110 25 77
- USER[2]: на завтра на десять утра
- seen PHONE `8 999 110 25 77` → `+79177304761`
- C: `crm_find_contact` {'query': {'phone': '+79991102577'}}
- C: `clinic_book` {'patient': {'last_name': 'Тарасова', 'first_name': 'Алла', 'middle_name': 'Анатольевна', 'birth_date': '1960-09-27', 'age': 65, 'gender': 'F'}, 'phone': '+79991102577', 'speciality': 'кардиолог', 's…
- I: `crm_find_contact` written={'query': {'phone': '+79177304761'}} → restored={'query': {'phone': '+79991102577'}}
- I: `clinic_book` written={'patient': {'last_name': 'Гвелесиани', 'first_name': 'Белла', 'middle_name': 'Юрьевна', 'birth_date': '2021-09-28', 'age': 4, 'gender': 'F'}, 'phone': '+79177304761', 'speciality': 'кардиолог', 'slot': '2026-09-04T10:00:00+03:00'} → restored={'patient': {'last_name': 'тарасова', 'first_name': 'алла', 'middle_name': 'анатольевна', 'birth_date': '1960-09-27', 'age': 4, 'gender': 'F'}, 'phone': '+79991102577', 'speciality': 'кардиолог', 'slot': '2026-09-04T10:00:00+03:00'}
- C′: `crm_find_contact` {'query': {'phone': '+79991102577'}}
- C′: `clinic_book` {'patient': {'last_name': 'Тарасова', 'first_name': 'Алла', 'middle_name': 'Анатольевна', 'birth_date': '1960-09-27', 'age': 65, 'gender': 'F'}, 'phone': '+79991102577', 'speciality': 'кардиолог', 's…
- FIELD `clinic_book.patient.age` [derived/from_substitute → derived] C=`65` I=`4` · значение выведено из ПОДМЕНЫ; восстановление недостижимо
- REPLY I: Записываю вас к кардиологу на завтра, 4 сентября, в 10:00! ⏳ Готово! ✅ Запись подтверждена! 📋 **Детали записи:** - **Пациент:** тарасова алла анатольевна - **Специалист:** Кардиолог - **Дата и время:** 4 сентября 2026, 10:00 - **Номер записи:** apt-1 Ждём вас завтра! Если потребуется перенести или …

## result_feed-003|2 · result_feed · chat · L1 = · L3 ≠ · C′≈C нет · причина: **derived-only**
- USER[1]: привет запишите меня к кардиологу я у вас в базе телефон 8 999 110 25 77
- USER[2]: на завтра на десять утра
- seen PHONE `8 999 110 25 77` → `+79520403311`
- C: `crm_find_contact` {'query': {'phone': '+79991102577'}}
- C: `clinic_book` {'patient': {'last_name': 'Тарасова', 'first_name': 'Алла', 'middle_name': 'Анатольевна', 'birth_date': '1960-09-27', 'age': 65, 'gender': 'F'}, 'phone': '+79991102577', 'speciality': 'кардиолог', 's…
- I: `crm_find_contact` written={'query': {'phone': '+79520403311'}} → restored={'query': {'phone': '+79991102577'}}
- I: `clinic_book` written={'patient': {'last_name': 'Белых', 'first_name': 'Галина', 'middle_name': 'Александровна', 'birth_date': '1969-03-22', 'age': 57, 'gender': 'F'}, 'phone': '+79520403311', 'speciality': 'кардиолог', 'slot': '2026-09-04T10:00:00+03:00'} → restored={'patient': {'last_name': 'тарасова', 'first_name': 'алла', 'middle_name': 'анатольевна', 'birth_date': '1960-09-27', 'age': 57, 'gender': 'F'}, 'phone': '+79991102577', 'speciality': 'кардиолог', 'slot': '2026-09-04T10:00:00+03:00'}
- C′: `crm_find_contact` {'query': {'phone': '+79991102577'}}
- C′: `clinic_book` {'patient': {'last_name': 'Тарасова', 'first_name': 'Алла', 'middle_name': 'Анатольевна', 'birth_date': '1960-09-27', 'age': 65, 'gender': 'F'}, 'phone': '+79991102577', 'speciality': 'кардиолог', 's…
- FIELD `clinic_book.patient.age` [derived/from_substitute → derived] C=`65` I=`57` · значение выведено из ПОДМЕНЫ; восстановление недостижимо
- REPLY I: Записываю вас! ⏳ Готово! ✅ Вы успешно записаны: - 👤 **тарасова алла анатольевна** - 🏥 **Специалист:** кардиолог - 📅 **Дата и время:** 4 сентября 2026 г., 10:00 Если нужно изменить или отменить запись — обращайтесь! 😊

## result_feed-004|0 · result_feed · sloppy · L1 = · L3 ≠ · C′≈C нет · причина: **derived-only**
- USER[1]: привет запишите меня к стоматологу я у вас в базе телефон +79821651435
- USER[2]: на завтра на днсять ура
- seen PHONE `+79821651435` → `+79713276603`
- C: `crm_find_contact` {'query': {'phone': '+79821651435'}}
- C: `clinic_book` {'patient': {'last_name': 'кузнецова', 'first_name': 'ольга', 'middle_name': 'дмитриевна', 'birth_date': '1967-09-10', 'age': 58, 'gender': 'F'}, 'phone': '+79821651435', 'speciality': 'стоматолог', …
- I: `crm_find_contact` written={'query': {'phone': '+79713276603'}} → restored={'query': {'phone': '+79821651435'}}
- I: `clinic_book` written={'patient': {'last_name': 'Коваленко', 'first_name': 'Алиса', 'middle_name': 'Ярославовна', 'birth_date': '1987-08-18', 'age': 39, 'gender': 'F'}, 'phone': '+79713276603', 'speciality': 'стоматолог', 'slot': '2026-09-04T10:00:00+04:00'} → restored={'patient': {'last_name': 'кузнецова', 'first_name': 'ольга', 'middle_name': 'дмитриевна', 'birth_date': '1967-09-10', 'age': 39, 'gender': 'F'}, 'phone': '+79821651435', 'speciality': 'стоматолог', 'slot': '2026-09-04T10:00:00+04:00'}
- C′: `crm_find_contact` {'query': {'phone': '+79821651435'}}
- C′: `clinic_book` {'patient': {'last_name': 'кузнецова', 'first_name': 'ольга', 'middle_name': 'дмитриевна', 'birth_date': '1967-09-10', 'age': 58, 'gender': 'F'}, 'phone': '+79821651435', 'speciality': 'стоматолог', …
- FIELD `clinic_book.patient.age` [derived/from_substitute → derived] C=`58` I=`39` · значение выведено из ПОДМЕНЫ; восстановление недостижимо
- REPLY I: Записываю вас к стоматологу на завтра, 4 сентября, в 10:00! ⏳ Готово! ✅ Вы успешно записаны! 📋 **Детали записи:** - 👤 кузнецова ольга дмитриевна - 🦷 Стоматолог - 📅 4 сентября 2026 года, 10:00 Отправить вам СМС-подтверждение на номер +79821651435?

## result_feed-004|1 · result_feed · sloppy · L1 = · L3 ≠ · C′≈C нет · причина: **derived-only**
- USER[1]: привет запишите меня к стоматологу я у вас в базе телефон +79821651435
- USER[2]: на завтра на днсять ура
- seen PHONE `+79821651435` → `+79629610666`
- C: `crm_find_contact` {'query': {'phone': '+79821651435'}}
- C: `clinic_book` {'patient': {'last_name': 'Кузнецова', 'first_name': 'Ольга', 'middle_name': 'Дмитриевна', 'birth_date': '1967-09-10', 'age': 58, 'gender': 'F'}, 'phone': '+79821651435', 'speciality': 'стоматолог', …
- I: `crm_find_contact` written={'query': {'phone': '+79629610666'}} → restored={'query': {'phone': '+79821651435'}}
- I: `clinic_book` written={'patient': {'last_name': 'Гвелесиани', 'first_name': 'Белла', 'middle_name': 'Михайловна', 'birth_date': '2017-09-06', 'age': 8, 'gender': 'F'}, 'phone': '+79629610666', 'speciality': 'стоматолог', 'slot': '2026-09-04T10:00:00+04:00'} → restored={'patient': {'last_name': 'кузнецова', 'first_name': 'ольга', 'middle_name': 'дмитриевна', 'birth_date': '1967-09-10', 'age': 8, 'gender': 'F'}, 'phone': '+79821651435', 'speciality': 'стоматолог', 'slot': '2026-09-04T10:00:00+04:00'}
- C′: `crm_find_contact` {'query': {'phone': '+79821651435'}}
- C′: `clinic_book` {'patient': {'last_name': 'Кузнецова', 'first_name': 'Ольга', 'middle_name': 'Дмитриевна', 'birth_date': '1967-09-10', 'age': 58, 'gender': 'F'}, 'phone': '+79821651435', 'speciality': 'стоматолог', …
- FIELD `clinic_book.patient.age` [derived/from_substitute → derived] C=`58` I=`8` · значение выведено из ПОДМЕНЫ; восстановление недостижимо
- REPLY I: Записываю вас на завтра, 4 сентября, в 10:00! ⏳ Готово! ✅ Вы успешно записаны! 📋 **Детали записи:** - 👤 кузнецова ольга дмитриевна - 🦷 Стоматолог - 📅 4 сентября 2026 года, в **10:00** Ждём вас в клинике! Если нужно изменить или отменить запись — обращайтесь 😊

## result_feed-004|2 · result_feed · sloppy · L1 = · L3 ≠ · C′≈C нет · причина: **derived-only**
- USER[1]: привет запишите меня к стоматологу я у вас в базе телефон +79821651435
- USER[2]: на завтра на днсять ура
- seen PHONE `+79821651435` → `+79876315520`
- C: `crm_find_contact` {'query': {'phone': '+79821651435'}}
- C: `clinic_book` {'patient': {'last_name': 'Кузнецова', 'first_name': 'Ольга', 'middle_name': 'Дмитриевна', 'birth_date': '1967-09-10', 'age': 58, 'gender': 'F'}, 'phone': '+79821651435', 'speciality': 'стоматолог', …
- I: `crm_find_contact` written={'query': {'phone': '+79876315520'}} → restored={'query': {'phone': '+79821651435'}}
- I: `clinic_book` written={'patient': {'last_name': 'Марчук', 'first_name': 'Иоланта', 'middle_name': 'Максимовна', 'birth_date': '1991-04-23', 'age': 35, 'gender': 'F'}, 'phone': '+79876315520', 'speciality': 'стоматолог', 'slot': '2026-09-04T10:00:00+04:00'} → restored={'patient': {'last_name': 'кузнецова', 'first_name': 'ольга', 'middle_name': 'дмитриевна', 'birth_date': '1967-09-10', 'age': 35, 'gender': 'F'}, 'phone': '+79821651435', 'speciality': 'стоматолог', 'slot': '2026-09-04T10:00:00+04:00'}
- C′: `crm_find_contact` {'query': {'phone': '+79821651435'}}
- C′: `clinic_book` {'patient': {'last_name': 'кузнецова', 'first_name': 'ольга', 'middle_name': 'дмитриевна', 'birth_date': '1967-09-10', 'age': 58, 'gender': 'F'}, 'phone': '+79821651435', 'speciality': 'стоматолог', …
- FIELD `clinic_book.patient.age` [derived/from_substitute → derived] C=`58` I=`35` · значение выведено из ПОДМЕНЫ; восстановление недостижимо
- REPLY I: Записываю вас к стоматологу на завтра, 4 сентября, в 10:00! ⏳ Готово! ✅ Вы записаны: - 👤 **кузнецова ольга дмитриевна** - 🦷 **Стоматолог** - 📅 **4 сентября 2026 года, 10:00** Если нужно перенести или отменить запись — обращайтесь! 😊

## result_feed-007|0 · result_feed · sloppy · L1 = · L3 ≠ · C′≈C да · причина: **derived-only**
- USER[1]: здоасте запишите меня к терапевту я у вас в базе телефон 8-916-158-76-76
- USER[2]: на завтра на деясть уьра
- seen PHONE `8-916-158-76-76` → `+79943920747`
- C: `crm_find_contact` {'query': {'phone': '+79161587676'}}
- C: `clinic_book` {'patient': {'last_name': 'Сергеев', 'first_name': 'Кирилл', 'middle_name': 'Сергеевич', 'birth_date': '1995-04-28', 'age': 31, 'gender': 'M'}, 'phone': '+79161587676', 'speciality': 'терапевт', 'slo…
- I: `crm_find_contact` written={'query': {'phone': '+79943920747'}} → restored={'query': {'phone': '+79161587676'}}
- I: `clinic_book` written={'patient': {'last_name': 'Остап Гущин', 'first_name': 'Алексей', 'middle_name': 'Ярославович', 'birth_date': '2020-02-24', 'age': 6, 'gender': 'M'}, 'phone': '+79943920747', 'speciality': 'терапевт', 'slot': '2026-09-04T10:00:00+03:00'} → restored={'patient': {'last_name': 'сергеев', 'first_name': 'кирилл', 'middle_name': 'сергеевич', 'birth_date': '1995-04-28', 'age': 6, 'gender': 'M'}, 'phone': '+79161587676', 'speciality': 'терапевт', 'slot': '2026-09-04T10:00:00+03:00'}
- C′: `crm_find_contact` {'query': {'phone': '+79161587676'}}
- C′: `clinic_book` {'patient': {'last_name': 'Сергеев', 'first_name': 'Кирилл', 'middle_name': 'Сергеевич', 'birth_date': '1995-04-28', 'age': 31, 'gender': 'M'}, 'phone': '+79161587676', 'speciality': 'терапевт', 'slo…
- FIELD `clinic_book.patient.age` [derived/from_substitute → derived] C=`31` I=`6` · значение выведено из ПОДМЕНЫ; восстановление недостижимо
- REPLY I: Записываю вас на **4 сентября 2026 г. в 10:00** к терапевту! ⏳ Готово! ✅ Вы успешно записаны! 📋 **Детали записи:** - 👤 сергеев кирилл сергеевич - 🏥 Специалист: **Терапевт** - 📅 Дата и время: **4 сентября 2026 г. в 10:00** - 🔖 Номер записи: `apt-1` Ждём вас в клинике! Если нужно изменить или отменит…

## result_feed-007|1 · result_feed · sloppy · L1 ≠ · L3 ≠ · C′≈C нет · причина: **partial-call**
- USER[1]: здоасте запишите меня к терапевту я у вас в базе телефон 8-916-158-76-76
- USER[2]: на завтра на деясть уьра
- seen PHONE `8-916-158-76-76` → `+79120446277`
- C: `crm_find_contact` {'query': {'phone': '+79161587676'}}
- C: `clinic_book` {'patient': {'last_name': 'Сергеев', 'first_name': 'Кирилл', 'middle_name': 'Сергеевич', 'birth_date': '1995-04-28', 'age': 31, 'gender': 'M'}, 'phone': '+79161587676', 'speciality': 'терапевт', 'slo…
- C: `notify_sms` {'number': '+79161587676', 'text': 'Кирилл Сергеевич, вы записаны к терапевту на 4 сентября 2026 г. в 10:00. Ждём вас в клинике!', 'sign': 'Klinika'}
- I: `crm_find_contact` written={'query': {'phone': '+79120446277'}} → restored={'query': {'phone': '+79161587676'}}
- I: `clinic_book` written={'patient': {'last_name': 'Ершов', 'first_name': 'Сергей', 'middle_name': 'Константинович', 'birth_date': '1973-12-17', 'age': 47, 'gender': 'M'}, 'phone': '+79120446277', 'speciality': 'терапевт', 'slot': '2021-03-06T10:00:00+04:00'} → restored={'patient': {'last_name': 'сергеев', 'first_name': 'кирилл', 'middle_name': 'сергеевич', 'birth_date': '1995-04-28', 'age': 47, 'gender': 'M'}, 'phone': '+79161587676', 'speciality': 'терапевт', 'slot': '2021-03-06T10:00:00+04:00'}
- C′: `crm_find_contact` {'query': {'phone': '+79161587676'}}
- C′: `clinic_book` {'patient': {'last_name': 'Сергеев', 'first_name': 'Кирилл', 'middle_name': 'Сергеевич', 'birth_date': '1995-04-28', 'age': 31, 'gender': 'M'}, 'phone': '+79161587676', 'speciality': 'терапевт', 'slo…
- C′: `notify_sms` {'number': '+79161587676', 'text': 'Кирилл Сергеевич, вы записаны к терапевту на 4 сентября 2026 г. в 10:00. Ждём вас! По вопросам звоните в клинику.', 'sign': 'Klinika'}
- FIELD `clinic_book.patient.age` [other/misderived → other/misderived] C=`31` I=`47`
- FIELD `notify_sms.number` [absent → absent:number] C=`+79161587676` I=``
- REPLY I: Записываю вас на **6 марта 2021 года в 10:00**! ⏳ Готово, кирилл сергеевич! ✅ Вы записаны: - 👨‍⚕️ **Специалист:** Терапевт - 📅 **Дата:** 6 марта 2021 года - 🕙 **Время:** 10:00 Отправить вам СМС с подтверждением на номер **8-916-158-76-76**?

## result_feed-007|2 · result_feed · sloppy · L1 ≠ · L3 ≠ · C′≈C нет · причина: **derived-only**
- USER[1]: здоасте запишите меня к терапевту я у вас в базе телефон 8-916-158-76-76
- USER[2]: на завтра на деясть уьра
- seen PHONE `8-916-158-76-76` → `+79101384978`
- C: `crm_find_contact` {'query': {'phone': '+79161587676'}}
- C: `clinic_book` {'patient': {'last_name': 'Сергеев', 'first_name': 'Кирилл', 'middle_name': 'Сергеевич', 'birth_date': '1995-04-28', 'age': 31, 'gender': 'M'}, 'phone': '+79161587676', 'speciality': 'терапевт', 'slo…
- C: `notify_sms` {'number': '+79161587676', 'text': 'Кирилл Сергеевич, вы записаны к терапевту на 4 сентября 2026 г. в 10:00. Ждём вас! По вопросам звоните в клинику.', 'sign': 'Klinika'}
- I: `crm_find_contact` written={'query': {'phone': '+79101384978'}} → restored={'query': {'phone': '+79161587676'}}
- I: `clinic_book` written={'patient': {'last_name': 'Бирюков', 'first_name': 'Богдан', 'middle_name': 'Николаевич', 'birth_date': '2017-05-06', 'age': 9, 'gender': 'M'}, 'phone': '+79101384978', 'speciality': 'терапевт', 'slot': '2026-09-04T10:00:00+03:00'} → restored={'patient': {'last_name': 'сергеев', 'first_name': 'кирилл', 'middle_name': 'сергеевич', 'birth_date': '1995-04-28', 'age': 9, 'gender': 'M'}, 'phone': '+79161587676', 'speciality': 'терапевт', 'slot': '2026-09-04T10:00:00+03:00'}
- C′: `crm_find_contact` {'query': {'phone': '+79161587676'}}
- C′: `clinic_book` {'patient': {'last_name': 'Сергеев', 'first_name': 'Кирилл', 'middle_name': 'Сергеевич', 'birth_date': '1995-04-28', 'age': 31, 'gender': 'M'}, 'phone': '+79161587676', 'speciality': 'терапевт', 'slo…
- FIELD `clinic_book.patient.age` [derived/from_substitute → derived] C=`31` I=`9` · значение выведено из ПОДМЕНЫ; восстановление недостижимо
- FIELD `notify_sms.number` [absent → absent:number] C=`+79161587676` I=``
- REPLY I: Записываю вас на **4 сентября 2026 года в 10:00** к терапевту! 🏥 Готово! ✅ Запись оформлена. Вот детали: - 👤 **Пациент:** сергеев кирилл сергеевич - 🏥 **Специалист:** Терапевт - 📅 **Дата и время:** 4 сентября 2026 г. в 10:00 - 📱 **Телефон:** 8-916-158-76-76 Ждём вас завтра! Если понадобится изменит…

## result_feed-009|0 · result_feed · voice_raw · L1 = · L3 ≠ · C′≈C да · причина: **derived-only**
- USER[1]: ааа здравствуйте запишите меня к кардиологуу я у вас в базее телефон восемь девятьсот девять девятьсот тридцать один двадцать восем пятнадцать
- USER[2]: наа завтра на десять утра
- seen PHONE `восемь девятьсот девять девятьсот тридцать один двадцать восем пятнадцать` → `+79367188694`
- C: `crm_find_contact` {'query': {'phone': '+79099312815'}}
- C: `clinic_book` {'patient': {'last_name': 'Воронина', 'first_name': 'Елена', 'middle_name': 'Сергеевна', 'birth_date': '2002-05-26', 'age': 24, 'gender': 'F'}, 'phone': '+79099312815', 'speciality': 'кардиолог', 'sl…
- I: `crm_find_contact` written={'query': {'phone': '+79367188694'}} → restored={'query': {'phone': '+79099312815'}}
- I: `clinic_book` written={'patient': {'last_name': 'Гончарук', 'first_name': 'Надежда', 'middle_name': 'Ивановна', 'birth_date': '1969-10-24', 'age': 56, 'gender': 'F'}, 'phone': '+79367188694', 'speciality': 'кардиолог', 'slot': '2026-09-04T10:00:00+04:00'} → restored={'patient': {'last_name': 'воронина', 'first_name': 'елена', 'middle_name': 'сергеевна', 'birth_date': '2002-05-26', 'age': 56, 'gender': 'F'}, 'phone': '+79099312815', 'speciality': 'кардиолог', 'slot': '2026-09-04T10:00:00+04:00'}
- C′: `crm_find_contact` {'query': {'phone': '+79099312815'}}
- C′: `clinic_book` {'patient': {'last_name': 'Воронина', 'first_name': 'Елена', 'middle_name': 'Сергеевна', 'birth_date': '2002-05-26', 'age': 24, 'gender': 'F'}, 'phone': '+79099312815', 'speciality': 'кардиолог', 'sl…
- FIELD `clinic_book.patient.age` [derived/from_substitute → derived] C=`24` I=`56` · значение выведено из ПОДМЕНЫ; восстановление недостижимо
- REPLY I: Записываю вас на завтра, 4 сентября, в 10:00! ⏳ Готово! ✅ Вы записаны: - 👤 **воронина елена сергеевна** - 🏥 **Кардиолог** - 📅 **4 сентября 2026 года, 10:00** Отправить вам СМС с подтверждением записи?

## result_feed-009|1 · result_feed · voice_raw · L1 = · L3 ≠ · C′≈C нет · причина: **derived-only**
- USER[1]: ааа здравствуйте запишите меня к кардиологуу я у вас в базее телефон восемь девятьсот девять девятьсот тридцать один двадцать восем пятнадцать
- USER[2]: наа завтра на десять утра
- seen PHONE `восемь девятьсот девять девятьсот тридцать один двадцать восем пятнадцать` → `+79027555313`
- C: `crm_find_contact` {'query': {'phone': '+79099312815'}}
- C: `clinic_book` {'patient': {'last_name': 'Воронина', 'first_name': 'Елена', 'middle_name': 'Сергеевна', 'birth_date': '2002-05-26', 'age': 24, 'gender': 'F'}, 'phone': '+79099312815', 'speciality': 'кардиолог', 'sl…
- I: `crm_find_contact` written={'query': {'phone': '+79027555313'}} → restored={'query': {'phone': '+79099312815'}}
- I: `clinic_book` written={'patient': {'last_name': 'Бондарчук', 'first_name': 'Нина', 'middle_name': 'Юрьевна', 'birth_date': '1969-02-01', 'age': 57, 'gender': 'F'}, 'phone': '+79027555313', 'speciality': 'кардиолог', 'slot': '2026-09-04T10:00:00+04:00'} → restored={'patient': {'last_name': 'воронина', 'first_name': 'елена', 'middle_name': 'сергеевна', 'birth_date': '2002-05-26', 'age': 57, 'gender': 'F'}, 'phone': '+79099312815', 'speciality': 'кардиолог', 'slot': '2026-09-04T10:00:00+04:00'}
- C′: `crm_find_contact` {'query': {'phone': '+79099312815'}}
- C′: `clinic_book` {'patient': {'last_name': 'Воронина', 'first_name': 'Елена', 'middle_name': 'Сергеевна', 'birth_date': '2002-05-26', 'age': 24, 'gender': 'F'}, 'phone': '+79099312815', 'speciality': 'кардиолог', 'sl…
- C′: `notify_sms` {'number': '+79099312815', 'text': 'Елена Сергеевна, вы записаны к кардиологу на 4 сентября 2026 г. в 10:00. Ждём вас в клинике! По вопросам звоните нам.', 'sign': 'Klinika'}
- FIELD `clinic_book.patient.age` [derived/from_substitute → derived] C=`24` I=`57` · значение выведено из ПОДМЕНЫ; восстановление недостижимо
- REPLY I: Готово! ✅ Вы записаны: - **Пациент:** воронина елена сергеевна - **Врач:** Кардиолог - **Дата и время:** 4 сентября 2026 г., 10:00 Ждём вас! Если нужно будет перенести или отменить — звоните 😊

## result_feed-009|2 · result_feed · voice_raw · L1 = · L3 ≠ · C′≈C нет · причина: **derived-only**
- USER[1]: ааа здравствуйте запишите меня к кардиологуу я у вас в базее телефон восемь девятьсот девять девятьсот тридцать один двадцать восем пятнадцать
- USER[2]: наа завтра на десять утра
- seen PHONE `восемь девятьсот девять девятьсот тридцать один двадцать восем пятнадцать` → `+79522623092`
- C: `crm_find_contact` {'query': {'phone': '+79099312815'}}
- C: `clinic_book` {'patient': {'last_name': 'Воронина', 'first_name': 'Елена', 'middle_name': 'Сергеевна', 'birth_date': '2002-05-26', 'age': 24, 'gender': 'F'}, 'phone': '+79099312815', 'speciality': 'кардиолог', 'sl…
- I: `crm_find_contact` written={'query': {'phone': '+79522623092'}} → restored={'query': {'phone': '+79099312815'}}
- I: `clinic_book` written={'patient': {'last_name': 'Седых', 'first_name': 'Василиса', 'middle_name': 'Геннадьевна', 'birth_date': '2018-04-16', 'age': 8, 'gender': 'F'}, 'phone': '+79522623092', 'speciality': 'кардиолог', 'slot': '2026-09-04T10:00:00+04:00'} → restored={'patient': {'last_name': 'воронина', 'first_name': 'елена', 'middle_name': 'сергеевна', 'birth_date': '2002-05-26', 'age': 8, 'gender': 'F'}, 'phone': '+79099312815', 'speciality': 'кардиолог', 'slot': '2026-09-04T10:00:00+04:00'}
- C′: `crm_find_contact` {'query': {'phone': '+79099312815'}}
- C′: `clinic_book` {'patient': {'last_name': 'Воронина', 'first_name': 'Елена', 'middle_name': 'Сергеевна', 'birth_date': '2002-05-26', 'age': 24, 'gender': 'F'}, 'phone': '+79099312815', 'speciality': 'кардиолог', 'sl…
- FIELD `clinic_book.patient.age` [derived/from_substitute → derived] C=`24` I=`8` · значение выведено из ПОДМЕНЫ; восстановление недостижимо
- REPLY I: Записываю! 😊 Всё готово! ✅ **Запись подтверждена:** - 👤 воронина елена сергеевна - 👨‍⚕️ Кардиолог - 📅 4 сентября 2026 года, **10:00** Если нужно будет перенести или отменить — обращайтесь! Выздоравливайте! 🙂

## result_feed-028|0 · result_feed · chat · L1 = · L3 ≠ · C′≈C нет · причина: **derived-only**
- USER[1]: привет запишите меня к неврологу я у вас в базе телефон 89776996134
- USER[2]: давайте в четверг к девяти
- seen PHONE `89776996134` → `+79548120153`
- C: `crm_find_contact` {'query': {'phone': '+79776996134'}}
- C: `clinic_book` {'patient': {'last_name': 'Громова', 'first_name': 'Марина', 'middle_name': 'Борисовна', 'birth_date': '1973-05-24', 'age': 53, 'gender': 'F'}, 'phone': '+79776996134', 'speciality': 'невролог', 'slo…
- I: `crm_find_contact` written={'query': {'phone': '+79548120153'}} → restored={'query': {'phone': '+79776996134'}}
- I: `clinic_book` written={'patient': {'last_name': 'Бабаян', 'first_name': 'Майя', 'middle_name': 'Павловна', 'birth_date': '2018-05-19', 'age': 8, 'gender': 'F'}, 'phone': '+79548120153', 'speciality': 'невролог', 'slot': '2026-09-10T09:00:00+04:00'} → restored={'patient': {'last_name': 'громова', 'first_name': 'марина', 'middle_name': 'борисовна', 'birth_date': '1973-05-24', 'age': 8, 'gender': 'F'}, 'phone': '+79776996134', 'speciality': 'невролог', 'slot': '2026-09-10T09:00:00+04:00'}
- C′: `crm_find_contact` {'query': {'phone': '+79776996134'}}
- C′: `clinic_book` {'patient': {'last_name': 'Громова', 'first_name': 'Марина', 'middle_name': 'Борисовна', 'birth_date': '1973-05-24', 'age': 53, 'gender': 'F'}, 'phone': '+79776996134', 'speciality': 'невролог', 'slo…
- FIELD `clinic_book.patient.age` [derived/from_substitute → derived] C=`53` I=`8` · значение выведено из ПОДМЕНЫ; восстановление недостижимо
- REPLY I: Сегодня четверг, 3 сентября, поэтому запишу вас на следующий четверг — **10 сентября 2026 года в 09:00**. Записываю! ⏳ Готово! ✅ Вы записаны к **неврологу** на **10 сентября 2026 года в 09:00**. 📋 Детали записи: - **Пациент:** громова марина борисовна - **Специалист:** Невролог - **Дата и время:** …

## result_feed-028|1 · result_feed · chat · L1 ≠ · L3 ≠ · C′≈C нет · причина: **other**
- USER[1]: привет запишите меня к неврологу я у вас в базе телефон 89776996134
- USER[2]: давайте в четверг к девяти
- seen PHONE `89776996134` → `+79210708659`
- C: `crm_find_contact` {'query': {'phone': '+79776996134'}}
- I: `crm_find_contact` written={'query': {'phone': '+79210708659'}} → restored={'query': {'phone': '+79776996134'}}
- I: `clinic_book` written={'patient': {'last_name': 'Данилюк', 'first_name': 'Эвелина', 'middle_name': 'Павловна', 'birth_date': '1962-09-20', 'age': 63, 'gender': 'F'}, 'phone': '+79210708659', 'speciality': 'невролог', 'slot': '2026-09-10T09:00:00+04:00'} → restored={'patient': {'last_name': 'громова', 'first_name': 'марина', 'middle_name': 'борисовна', 'birth_date': '1973-05-24', 'age': 63, 'gender': 'F'}, 'phone': '+79776996134', 'speciality': 'невролог', 'slot': '2026-09-10T09:00:00+04:00'}
- C′: `crm_find_contact` {'query': {'phone': '+79776996134'}}
- C′: `clinic_book` {'patient': {'last_name': 'Громова', 'first_name': 'Марина', 'middle_name': 'Борисовна', 'birth_date': '1973-05-24', 'age': 53, 'gender': 'F'}, 'phone': '+79776996134', 'speciality': 'невролог', 'slo…
- FIELD `clinic_book.patient.age` [extra → extra:age] C=`` I=`63`
- FIELD `clinic_book.patient.birth_date` [extra → extra:birth_date] C=`` I=`1973-05-24`
- FIELD `clinic_book.patient.first_name` [extra → extra:first_name] C=`` I=`марина`
- FIELD `clinic_book.patient.gender` [extra → extra:gender] C=`` I=`F`
- FIELD `clinic_book.patient.last_name` [extra → extra:last_name] C=`` I=`громова`
- FIELD `clinic_book.patient.middle_name` [extra → extra:middle_name] C=`` I=`борисовна`
- FIELD `clinic_book.phone` [extra → extra:phone] C=`` I=`+79776996134`
- REPLY I: Записываю вас на **четверг, 10 сентября 2026 года в 09:00** к неврологу! ⏳ Готово! ✅ Вы записаны: - **Пациент:** громова марина борисовна - **Специалист:** Невролог - **Дата и время:** 10 сентября 2026 г. в 09:00 Отправить вам СМС с подтверждением записи на номер 89776996134?

## result_feed-028|2 · result_feed · chat · L1 = · L3 ≠ · C′≈C нет · причина: **other**
- USER[1]: привет запишите меня к неврологу я у вас в базе телефон 89776996134
- USER[2]: давайте в четверг к девяти
- seen PHONE `89776996134` → `+79232760225`
- C: `crm_find_contact` {'query': {'phone': '+79776996134'}}
- C: `clinic_book` {'patient': {'last_name': 'Громова', 'first_name': 'Марина', 'middle_name': 'Борисовна', 'birth_date': '1973-05-24', 'age': 53, 'gender': 'F'}, 'phone': '+79776996134', 'speciality': 'невролог', 'slo…
- C: `notify_sms` {'number': '+79776996134', 'text': 'Марина Борисовна, вы записаны к неврологу на 10 сентября 2026 г. в 09:00. Ждём вас в клинике! По вопросам звоните нам.', 'sign': 'Klinika'}
- I: `crm_find_contact` written={'query': {'phone': '+79232760225'}} → restored={'query': {'phone': '+79776996134'}}
- I: `clinic_book` written={'patient': {'last_name': 'Савченко', 'first_name': 'Иванна', 'middle_name': 'Валерьевна', 'birth_date': '1975-05-04', 'age': 37, 'gender': 'F'}, 'phone': '+79232760225', 'speciality': 'невролог', 'slot': '2013-02-14T09:00:00+04:00'} → restored={'patient': {'last_name': 'громова', 'first_name': 'марина', 'middle_name': 'борисовна', 'birth_date': '1973-05-24', 'age': 37, 'gender': 'F'}, 'phone': '+79776996134', 'speciality': 'невролог', 'slot': '2013-02-14T09:00:00+04:00'}
- I: `notify_sms` written={'number': '+79232760225', 'text': 'Иванна Валерьевна, вы записаны к неврологу на 14 февраля 2013 в 09:00. Ждём вас в клинике! По вопросам звоните администратору.', 'sign': 'Klinika'} → restored={'number': '+79776996134', 'text': 'марина борисовна, вы записаны к неврологу на 14 февраля 2013 в 09:00. Ждём вас в клинике! По вопросам звоните администратору.', 'sign': 'Klinika'}
- C′: `crm_find_contact` {'query': {'phone': '+79776996134'}}
- C′: `clinic_book` {'patient': {'last_name': 'Громова', 'first_name': 'Марина', 'middle_name': 'Борисовна', 'birth_date': '1973-05-24', 'age': 53, 'gender': 'F'}, 'phone': '+79776996134', 'speciality': 'невролог', 'slo…
- FIELD `clinic_book.patient.age` [other/misderived → other/misderived] C=`53` I=`37`
- REPLY I: Сегодня 2026-09-02 (суббота), ближайший четверг — **14 февраля 2013 в 09:00**. Записываю! ⏳ Готово! Отправлю вам СМС с подтверждением. 📩 Всё готово, марина борисовна! ✅ **Ваша запись:** - 👨‍⚕️ Специалист: **невролог** - 📅 Дата и время: **14 февраля 2013, 09:00** СМС с подтверждением отправлено на н…

## result_feed-031|0 · result_feed · voice_itn · L1 ≠ · L3 ≠ · C′≈C нет · причина: **derived-only**
- USER[1]: алло запишите меня к стоматологу я у вас в базе тел 8-951-044-37-07
- USER[2]: давайте в четверг к девяти
- seen PHONE `8-951-044-37-07` → `+79456260197`
- C: `crm_find_contact` {'query': {'phone': '+79510443707'}}
- C: `clinic_book` {'patient': {'last_name': 'миллер', 'first_name': 'валерия', 'middle_name': 'леонидовна', 'birth_date': '1965-03-19', 'age': 61, 'gender': 'F'}, 'phone': '+79510443707', 'speciality': 'стоматолог', '…
- C: `notify_sms` {'number': '+79510443707', 'text': 'Валерия Леонидовна, вы записаны к стоматологу на 10 сентября 2026 г. в 09:00. Ждём вас! По вопросам звоните в клинику.', 'sign': 'Klinika'}
- I: `crm_find_contact` written={'query': {'phone': '+79456260197'}} → restored={'query': {'phone': '+79510443707'}}
- I: `clinic_book` written={'patient': {'last_name': 'Наумов', 'first_name': 'Иоланта', 'middle_name': 'Борисовна', 'birth_date': '1975-11-13', 'age': 50, 'gender': 'F'}, 'phone': '+79456260197', 'speciality': 'стоматолог', 'slot': '2026-09-10T09:00:00+03:00'} → restored={'patient': {'last_name': 'миллер', 'first_name': 'валерия', 'middle_name': 'леонидовна', 'birth_date': '1965-03-19', 'age': 50, 'gender': 'F'}, 'phone': '+79510443707', 'speciality': 'стоматолог', 'slot': '2026-09-10T09:00:00+03:00'}
- C′: `crm_find_contact` {'query': {'phone': '+79510443707'}}
- C′: `clinic_book` {'patient': {'last_name': 'Миллер', 'first_name': 'Валерия', 'middle_name': 'Леонидовна', 'birth_date': '1965-03-19', 'age': 61, 'gender': 'F'}, 'phone': '+79510443707', 'speciality': 'стоматолог', '…
- C′: `notify_sms` {'number': '+79510443707', 'text': 'Валерия Леонидовна, вы записаны к стоматологу на пятницу 4 сентября в 09:00. Ждём вас в клинике! По вопросам звоните нам.', 'sign': 'Klinika'}
- FIELD `clinic_book.patient.age` [derived/from_substitute → derived] C=`61` I=`50` · значение выведено из ПОДМЕНЫ; восстановление недостижимо
- FIELD `notify_sms.number` [absent → absent:number] C=`+79510443707` I=``
- REPLY I: Записываю вас к стоматологу на **четверг, 10 сентября в 09:00**! Готово! ✅ Вы записаны: - 👤 **миллер валерия леонидовна** - 🦷 **Стоматолог** - 📅 **Четверг, 10 сентября 2026 г. в 09:00** Отправить вам СМС-напоминание с подтверждением записи?

## result_feed-031|1 · result_feed · voice_itn · L1 = · L3 ≠ · C′≈C да · причина: **other**
- USER[1]: алло запишите меня к стоматологу я у вас в базе тел 8-951-044-37-07
- USER[2]: давайте в четверг к девяти
- seen PHONE `8-951-044-37-07` → `+79229855016`
- C: `crm_find_contact` {'query': {'phone': '+79510443707'}}
- C: `clinic_book` {'patient': {'last_name': 'миллер', 'first_name': 'валерия', 'middle_name': 'леонидовна', 'birth_date': '1965-03-19', 'age': 61, 'gender': 'F'}, 'phone': '+79510443707', 'speciality': 'стоматолог', '…
- I: `crm_find_contact` written={'query': {'phone': '+79229855016'}} → restored={'query': {'phone': '+79510443707'}}
- I: `clinic_book` written={'patient': {'last_name': 'Тарасов', 'first_name': 'Виктория', 'middle_name': 'Павловна', 'birth_date': '1986-02-25', 'age': 5, 'gender': 'F'}, 'phone': '+79229855016', 'speciality': 'стоматолог', 'slot': '1991-03-28T09:00:00+03:00'} → restored={'patient': {'last_name': 'миллер', 'first_name': 'валерия', 'middle_name': 'леонидовна', 'birth_date': '1965-03-19', 'age': 5, 'gender': 'F'}, 'phone': '+79510443707', 'speciality': 'стоматолог', 'slot': '1991-03-28T09:00:00+03:00'}
- C′: `crm_find_contact` {'query': {'phone': '+79510443707'}}
- C′: `clinic_book` {'patient': {'last_name': 'Миллер', 'first_name': 'Валерия', 'middle_name': 'Леонидовна', 'birth_date': '1965-03-19', 'age': 61, 'gender': 'F'}, 'phone': '+79510443707', 'speciality': 'стоматолог', '…
- FIELD `clinic_book.patient.age` [other/misderived → other/misderived] C=`61` I=`5`
- REPLY I: Отлично! Ближайший четверг — **28 марта**, записываю вас на **9:00**! ⏳ Готово! ✅ Всё оформлено! 📋 **Ваша запись:** - 👩 миллер валерия леонидовна - 🦷 Стоматолог - 📅 28 марта (четверг), **09:00** Ждём вас! Если вдруг планы изменятся — звоните, перенесём 😊

## result_feed-031|2 · result_feed · voice_itn · L1 = · L3 ≠ · C′≈C да · причина: **other**
- USER[1]: алло запишите меня к стоматологу я у вас в базе тел 8-951-044-37-07
- USER[2]: давайте в четверг к девяти
- seen PHONE `8-951-044-37-07` → `+79131293462`
- C: `crm_find_contact` {'query': {'phone': '+79510443707'}}
- C: `clinic_book` {'patient': {'last_name': 'миллер', 'first_name': 'валерия', 'middle_name': 'леонидовна', 'birth_date': '1965-03-19', 'age': 61, 'gender': 'F'}, 'phone': '+79510443707', 'speciality': 'стоматолог', '…
- I: `crm_find_contact` written={'query': {'phone': '+79131293462'}} → restored={'query': {'phone': '+79510443707'}}
- I: `clinic_book` written={'patient': {'last_name': 'Панов', 'first_name': 'Иванны', 'middle_name': 'Васильевна', 'birth_date': '2002-11-06', 'age': 16, 'gender': 'F'}, 'phone': '+79131293462', 'speciality': 'стоматолог', 'slot': '2018-12-13T09:00:00+03:00'} → restored={'patient': {'last_name': 'миллер', 'first_name': 'валерия', 'middle_name': 'леонидовна', 'birth_date': '1965-03-19', 'age': 16, 'gender': 'F'}, 'phone': '+79510443707', 'speciality': 'стоматолог', 'slot': '2018-12-13T09:00:00+03:00'}
- C′: `crm_find_contact` {'query': {'phone': '+79510443707'}}
- C′: `clinic_book` {'patient': {'last_name': 'Миллер', 'first_name': 'Валерия', 'middle_name': 'Леонидовна', 'birth_date': '1965-03-19', 'age': 61, 'gender': 'F'}, 'phone': '+79510443707', 'speciality': 'стоматолог', '…
- FIELD `clinic_book.patient.age` [other/misderived → other/misderived] C=`61` I=`16`
- REPLY I: Ближайший четверг — **13 декабря 2018** в **09:00**. Записываю! ⏳ Готово! ✅ Вы записаны: - 👤 **миллер валерии леонидовна** - 🦷 **Стоматолог** - 📅 **Четверг, 13 декабря 2018 в 09:00** Ждём вас! Если нужно перенести или отменить запись — звоните. 😊

## result_feed-033|0 · result_feed · voice_itn · L1 = · L3 ≠ · C′≈C нет · причина: **other**
- USER[1]: запишите меня к кардиологу я у вас в базе тел +79876955394
- USER[2]: давайте в четверг к девяти
- seen PHONE `+79876955394` → `+79615182005`
- C: `crm_find_contact` {'query': {'phone': '+79876955394'}}
- C: `clinic_book` {'patient': {'last_name': 'Громов', 'first_name': 'Артём', 'middle_name': 'Витальевич', 'birth_date': '1980-02-13', 'age': 46, 'gender': 'M'}, 'phone': '+79876955394', 'speciality': 'кардиолог', 'slo…
- I: `crm_find_contact` written={'query': {'phone': '+79615182005'}} → restored={'query': {'phone': '+79876955394'}}
- I: `clinic_book` written={'patient': {'last_name': 'Громов', 'first_name': 'Трофим', 'middle_name': 'Валентинович', 'birth_date': '2013-04-08', 'age': 6, 'gender': 'M'}, 'phone': '+79615182005', 'speciality': 'кардиолог', 'slot': '2019-09-12T09:00:00+03:00'} → restored={'patient': {'last_name': 'Громов', 'first_name': 'артём', 'middle_name': 'витальевич', 'birth_date': '1980-02-13', 'age': 6, 'gender': 'M'}, 'phone': '+79876955394', 'speciality': 'кардиолог', 'slot': '2019-09-12T09:00:00+03:00'}
- C′: `crm_find_contact` {'query': {'phone': '+79876955394'}}
- C′: `clinic_book` {'patient': {'last_name': 'Громов', 'first_name': 'Артём', 'middle_name': 'Витальевич', 'birth_date': '1980-02-13', 'age': 46, 'gender': 'M'}, 'phone': '+79876955394', 'speciality': 'кардиолог', 'slo…
- FIELD `clinic_book.patient.age` [other/misderived → other/misderived] C=`46` I=`6`
- REPLY I: Ближайший четверг — **12 сентября 2019 г.**, записываю вас на 09:00! 🕘 Готово! Запись подтверждена ✅ 📋 **Детали записи:** - **Пациент:** Громов артём витальевич - **Специалист:** Кардиолог - **Дата и время:** 12 сентября 2019 г., 09:00 - **Номер записи:** apt-1 Ждём вас! Если нужно будет перенести …

## result_feed-033|1 · result_feed · voice_itn · L1 ≠ · L3 ≠ · C′≈C нет · причина: **derived-only**
- USER[1]: запишите меня к кардиологу я у вас в базе тел +79876955394
- USER[2]: давайте в четверг к девяти
- seen PHONE `+79876955394` → `+79667714108`
- C: `crm_find_contact` {'query': {'phone': '+79876955394'}}
- C: `clinic_book` {'patient': {'last_name': 'Громов', 'first_name': 'Артём', 'middle_name': 'Витальевич', 'birth_date': '1980-02-13', 'age': 46, 'gender': 'M'}, 'phone': '+79876955394', 'speciality': 'кардиолог', 'slo…
- C: `notify_sms` {'number': '+79876955394', 'text': 'Громов Артём Витальевич, вы записаны к кардиологу на 03.09.2026 в 09:00. Ждём вас в клинике! По вопросам звоните на ресепшн.', 'sign': 'Klinika'}
- I: `crm_find_contact` written={'query': {'phone': '+79667714108'}} → restored={'query': {'phone': '+79876955394'}}
- I: `clinic_book` written={'patient': {'last_name': 'Громов', 'first_name': 'Олег', 'middle_name': 'Павлович', 'birth_date': '2017-09-21', 'age': 8, 'gender': 'M'}, 'phone': '+79667714108', 'speciality': 'кардиолог', 'slot': '2026-09-10T09:00:00+04:00'} → restored={'patient': {'last_name': 'Громов', 'first_name': 'артём', 'middle_name': 'витальевич', 'birth_date': '1980-02-13', 'age': 8, 'gender': 'M'}, 'phone': '+79876955394', 'speciality': 'кардиолог', 'slot': '2026-09-10T09:00:00+04:00'}
- C′: `crm_find_contact` {'query': {'phone': '+79876955394'}}
- C′: `clinic_book` {'patient': {'last_name': 'Громов', 'first_name': 'Артём', 'middle_name': 'Витальевич', 'birth_date': '1980-02-13', 'age': 46, 'gender': 'M'}, 'phone': '+79876955394', 'speciality': 'кардиолог', 'slo…
- FIELD `clinic_book.patient.age` [derived/from_substitute → derived] C=`46` I=`8` · значение выведено из ПОДМЕНЫ; восстановление недостижимо
- FIELD `notify_sms.number` [absent → absent:number] C=`+79876955394` I=``
- REPLY I: Записываю вас на **четверг, 10 сентября 2026 года в 09:00**! Готово! ✅ Вы записаны: - **Пациент:** Громов артём витальевич - **Врач:** Кардиолог - **Дата и время:** 10 сентября 2026 г. в 09:00 - **Номер записи:** apt-1 Отправить вам СМС-подтверждение на номер +79876955394?

## result_feed-033|2 · result_feed · voice_itn · L1 = · L3 ≠ · C′≈C нет · причина: **derived-only**
- USER[1]: запишите меня к кардиологу я у вас в базе тел +79876955394
- USER[2]: давайте в четверг к девяти
- seen PHONE `+79876955394` → `+79368240873`
- C: `crm_find_contact` {'query': {'phone': '+79876955394'}}
- C: `clinic_book` {'patient': {'last_name': 'громов', 'first_name': 'артём', 'middle_name': 'витальевич', 'birth_date': '1980-02-13', 'age': 46, 'gender': 'M'}, 'phone': '+79876955394', 'speciality': 'кардиолог', 'slo…
- I: `crm_find_contact` written={'query': {'phone': '+79368240873'}} → restored={'query': {'phone': '+79876955394'}}
- I: `clinic_book` written={'patient': {'last_name': 'Громов', 'first_name': 'Матвей', 'middle_name': 'Леонидович', 'birth_date': '1998-07-18', 'age': 28, 'gender': 'M'}, 'phone': '+79368240873', 'speciality': 'кардиолог', 'slot': '2026-09-10T09:00:00+04:00'} → restored={'patient': {'last_name': 'Громов', 'first_name': 'артём', 'middle_name': 'витальевич', 'birth_date': '1980-02-13', 'age': 28, 'gender': 'M'}, 'phone': '+79876955394', 'speciality': 'кардиолог', 'slot': '2026-09-10T09:00:00+04:00'}
- C′: `crm_find_contact` {'query': {'phone': '+79876955394'}}
- C′: `clinic_book` {'patient': {'last_name': 'Громов', 'first_name': 'Артём', 'middle_name': 'Витальевич', 'birth_date': '1980-02-13', 'age': 46, 'gender': 'M'}, 'phone': '+79876955394', 'speciality': 'кардиолог', 'slo…
- FIELD `clinic_book.patient.age` [derived/from_substitute → derived] C=`46` I=`28` · значение выведено из ПОДМЕНЫ; восстановление недостижимо
- REPLY I: Записываю вас к кардиологу на **четверг, 10 сентября в 09:00**! Готово, артём витальевич! ✅ **Ваша запись подтверждена:** - 👨‍⚕️ Специалист: кардиолог - 📅 Дата: четверг, 10 сентября 2026 г. - 🕘 Время: 09:00 Отправить вам СМС-напоминание о записи?

## result_feed-035|0 · result_feed · sloppy · L1 ≠ · L3 ≠ · C′≈C нет · причина: **derived-only**
- USER[1]: здрасте запишите меня к стоматологу я у вас в базе телефон 89777778899
- USER[2]: давайте в четверг к девчти
- seen PHONE `89777778899` → `+79643311526`
- C: `crm_find_contact` {'query': {'phone': '+79777778899'}}
- C: `clinic_book` {'patient': {'last_name': 'Соколова', 'first_name': 'Анна', 'middle_name': 'Игоревна', 'birth_date': '1971-02-28', 'age': 55, 'gender': 'F'}, 'phone': '+79777778899', 'speciality': 'стоматолог', 'slo…
- C: `notify_sms` {'number': '+79777778899', 'text': 'Анна Игоревна, вы записаны к стоматологу на 10 сентября 2026 г. в 09:00. Ждём вас! По вопросам звоните в клинику.', 'sign': 'Klinika'}
- I: `crm_find_contact` written={'query': {'phone': '+79643311526'}} → restored={'query': {'phone': '+79777778899'}}
- I: `clinic_book` written={'patient': {'last_name': 'Данилюк', 'first_name': 'Галина', 'middle_name': 'Степановна', 'birth_date': '1977-11-19', 'age': 48, 'gender': 'F'}, 'phone': '+79643311526', 'speciality': 'стоматолог', 'slot': '2026-09-10T09:00:00+03:00'} → restored={'patient': {'last_name': 'соколова', 'first_name': 'анна', 'middle_name': 'игоревна', 'birth_date': '1971-02-28', 'age': 48, 'gender': 'F'}, 'phone': '+79777778899', 'speciality': 'стоматолог', 'slot': '2026-09-10T09:00:00+03:00'}
- C′: `crm_find_contact` {'query': {'phone': '+79777778899'}}
- FIELD `clinic_book.patient.age` [derived/from_substitute → derived] C=`55` I=`48` · значение выведено из ПОДМЕНЫ; восстановление недостижимо
- FIELD `notify_sms.number` [absent → absent:number] C=`+79777778899` I=``
- REPLY I: Записываю вас к стоматологу на **четверг, 10 сентября 2026 года в 09:00**! ⏳ Готово, анна игоревна! ✅ **Запись подтверждена:** - 👩‍⚕️ Специалист: **стоматолог** - 📅 Дата: **10 сентября 2026 (четверг)** - 🕘 Время: **09:00** Ждём вас! Если потребуется перенести или отменить запись — звоните. 😊

## result_feed-035|1 · result_feed · sloppy · L1 = · L3 ≠ · C′≈C нет · причина: **derived-only**
- USER[1]: здрасте запишите меня к стоматологу я у вас в базе телефон 89777778899
- USER[2]: давайте в четверг к девчти
- seen PHONE `89777778899` → `+79793093236`
- C: `crm_find_contact` {'query': {'phone': '+79777778899'}}
- C: `clinic_book` {'patient': {'last_name': 'Соколова', 'first_name': 'Анна', 'middle_name': 'Игоревна', 'birth_date': '1971-02-28', 'age': 55, 'gender': 'F'}, 'phone': '+79777778899', 'speciality': 'стоматолог', 'slo…
- I: `crm_find_contact` written={'query': {'phone': '+79793093236'}} → restored={'query': {'phone': '+79777778899'}}
- I: `clinic_book` written={'patient': {'last_name': 'Гвелесиани', 'first_name': 'Екатерина', 'middle_name': 'Фёдоровна', 'birth_date': '2003-12-09', 'age': 22, 'gender': 'F'}, 'phone': '+79793093236', 'speciality': 'стоматолог', 'slot': '2026-09-10T09:00:00+04:00'} → restored={'patient': {'last_name': 'соколова', 'first_name': 'анна', 'middle_name': 'игоревна', 'birth_date': '1971-02-28', 'age': 22, 'gender': 'F'}, 'phone': '+79777778899', 'speciality': 'стоматолог', 'slot': '2026-09-10T09:00:00+04:00'}
- C′: `crm_find_contact` {'query': {'phone': '+79777778899'}}
- FIELD `clinic_book.patient.age` [derived/from_substitute → derived] C=`55` I=`22` · значение выведено из ПОДМЕНЫ; восстановление недостижимо
- REPLY I: Уточню: вы имеете в виду **в четверг, 10 сентября, в 09:00**? И "к девяти" — это 9 утра? Записываю! 🦷 Готово, анна игоревна! ✅ Вы записаны: - 📅 **Четверг, 10 сентября 2026 г.** - 🕘 **09:00** - 🦷 **Стоматолог** Если нужно перенести или отменить — обращайтесь. До свидания! 😊

## result_feed-035|2 · result_feed · sloppy · L1 = · L3 ≠ · C′≈C да · причина: **derived-only**
- USER[1]: здрасте запишите меня к стоматологу я у вас в базе телефон 89777778899
- USER[2]: давайте в четверг к девчти
- seen PHONE `89777778899` → `+79807938699`
- C: `crm_find_contact` {'query': {'phone': '+79777778899'}}
- C: `clinic_book` {'patient': {'last_name': 'Соколова', 'first_name': 'Анна', 'middle_name': 'Игоревна', 'birth_date': '1971-02-28', 'age': 55, 'gender': 'F'}, 'phone': '+79777778899', 'speciality': 'стоматолог', 'slo…
- I: `crm_find_contact` written={'query': {'phone': '+79807938699'}} → restored={'query': {'phone': '+79777778899'}}
- I: `clinic_book` written={'patient': {'last_name': 'Мкртчян', 'first_name': 'Алиса', 'middle_name': 'Дмитриевна', 'birth_date': '1976-11-22', 'age': 49, 'gender': 'F'}, 'phone': '+79807938699', 'speciality': 'стоматолог', 'slot': '2026-09-10T09:00:00+03:00'} → restored={'patient': {'last_name': 'соколова', 'first_name': 'анна', 'middle_name': 'игоревна', 'birth_date': '1971-02-28', 'age': 49, 'gender': 'F'}, 'phone': '+79777778899', 'speciality': 'стоматолог', 'slot': '2026-09-10T09:00:00+03:00'}
- C′: `crm_find_contact` {'query': {'phone': '+79777778899'}}
- C′: `clinic_book` {'patient': {'last_name': 'Соколова', 'first_name': 'Анна', 'middle_name': 'Игоревна', 'birth_date': '1971-02-28', 'age': 55, 'gender': 'F'}, 'phone': '+79777778899', 'speciality': 'стоматолог', 'slo…
- FIELD `clinic_book.patient.age` [derived/from_substitute → derived] C=`55` I=`49` · значение выведено из ПОДМЕНЫ; восстановление недостижимо
- REPLY I: Записываю вас на четверг, 10 сентября, в 09:00! Готово, анна игоревна! ✅ Вы записаны к **стоматологу** на **четверг, 10 сентября 2026 года в 09:00**. Если нужно будет перенести или отменить — звоните, поможем!

## validate-000|0 · validate · voice_raw · L1 ≠ · L3 ≠ · C′≈C да · причина: **validate-refuse**
- USER[1]: ааа здравствуйте сверьте мои данные сниилс ноль один семьдесят восемь девяносто семь двадцать три семьсот девяно шесть паспорт тридцать шесть девятнадцать четырнадцать семнадцать восемьдесят три букин сергей иванович
- seen SNILS `ноль один семьдесят восемь девяносто семь двадцать три семьсот девяно шесть` → `015-177-021 73`
- seen PASSPORT `тридцать шесть девятнадцать четырнадцать семнадцать восемьдесят три` → `00 11 886874`
- seen NAME `букин сергей иванович` → `Устинов Макар Кириллович`
- C: `passport_verify` {'passport': {'series': '3619', 'number': '141783'}, 'person': {'last_name': 'Букин', 'first_name': 'Сергей', 'middle_name': 'Иванович'}, 'snils': '017-897-237-96'} · refusal=snils_format
- C: `passport_verify` {'passport': {'series': '3619', 'number': '141783'}, 'person': {'last_name': 'Букин', 'first_name': 'Сергей', 'middle_name': 'Иванович'}, 'snils': '017-897-237 96'}
- I: — (без вызовов)
- C′: `passport_verify` {'passport': {'series': '3619', 'number': '141783'}, 'person': {'last_name': 'Букин', 'first_name': 'Сергей', 'middle_name': 'Иванович'}, 'snils': '017-897-237 96'}
- FIELD `passport_verify.passport.number` [absent → absent:number] C=`141783` I=``
- FIELD `passport_verify.passport.series` [absent → absent:series] C=`3619` I=``
- FIELD `passport_verify.person.first_name` [absent → absent:first_name] C=`Сергей` I=``
- FIELD `passport_verify.person.last_name` [absent → absent:last_name] C=`Букин` I=``
- FIELD `passport_verify.person.middle_name` [absent → absent:middle_name] C=`Иванович` I=``
- FIELD `passport_verify.snils` [absent → absent:snils] C=`017-897-237-96` I=``
- FIELD `passport_verify.passport.number` [absent → absent:number] C=`141783` I=``
- FIELD `passport_verify.passport.series` [absent → absent:series] C=`3619` I=``
- FIELD `passport_verify.person.first_name` [absent → absent:first_name] C=`Сергей` I=``
- FIELD `passport_verify.person.last_name` [absent → absent:last_name] C=`Букин` I=``
- FIELD `passport_verify.person.middle_name` [absent → absent:middle_name] C=`Иванович` I=``
- FIELD `passport_verify.snils` [absent → absent:snils] C=`017-897-237 96` I=``
- REPLY I: Здравствуйте! Прежде чем продолжить, я проверяю контрольную сумму СНИЛС. **Проверка СНИЛС ноль один семьдесят восемь девяносто семь двадцать три семьсот девяно шесть:** Цифры номера: 0, 1, 5, 1, 7, 7, 0, 2, 1 Взвешенная сумма: 0×9 + 1×8 + 5×7 + 1×6 + 7×5 + 7×4 + 0×3 + 2×2 + 1×1 = 0 + 8 + 35 + 6 + 3…

## validate-017|0 · validate · sloppy · L1 = · L3 = · C′≈C нет · причина: **leak-only**
- USER[1]: здрасте сверьте мои данные силс 20304105882 паспорт 1812759266 соколова анна игоревна
- **LEAK** SNILS `20304105882` — модель видела настоящее значение
- seen PASSPORT `1812759266` → `00 12 618051`
- seen NAME `соколова анна игоревна` → `Мещерякова Нина Константиновна`
- C: — (без вызовов)
- I: — (без вызовов)
- C′: `passport_verify` {'passport': {'series': '1812', 'number': '759266'}, 'person': {'last_name': 'Соколова', 'first_name': 'Анна', 'middle_name': 'Игоревна'}}
- REPLY I: Здравствуйте! Прежде чем обратиться к системе, я проверяю контрольную сумму СНИЛС. --- **Проверка СНИЛС: 203-041-058 82** Алгоритм ПФР — умножаю первые 9 цифр на весовые коэффициенты (9→1): | Цифра | Вес | Результат | |-------|-----|-----------| | 2 | 9 | 18 | | 0 | 8 | 0 | | 3 | 7 | 21 | | 0 | 6 |…

## validate-018|0 · validate · chat · L1 ≠ · L3 ≠ · C′≈C да · причина: **validate-refuse**
- USER[1]: добрый день сверьте мои данные снилс 992-954-702 83 паспорт 4005 343601 фомин вячеслав степанович
- seen SNILS `992-954-702 83` → `150-809-360 42`
- seen PASSPORT `4005 343601` → `00 25 902709`
- seen NAME `фомин вячеслав степанович` → `Гущин Фёдор Романович`
- C: `passport_verify` {'passport': {'series': '4005', 'number': '343601'}, 'person': {'last_name': 'Фомин', 'first_name': 'Вячеслав', 'middle_name': 'Степанович'}, 'snils': '992-954-702 83'}
- I: — (без вызовов)
- C′: `passport_verify` {'passport': {'series': '4005', 'number': '343601'}, 'person': {'last_name': 'Фомин', 'first_name': 'Вячеслав', 'middle_name': 'Степанович'}, 'snils': '992-954-702 83'}
- FIELD `passport_verify.passport.number` [absent → absent:number] C=`343601` I=``
- FIELD `passport_verify.passport.series` [absent → absent:series] C=`4005` I=``
- FIELD `passport_verify.person.first_name` [absent → absent:first_name] C=`Вячеслав` I=``
- FIELD `passport_verify.person.last_name` [absent → absent:last_name] C=`Фомин` I=``
- FIELD `passport_verify.person.middle_name` [absent → absent:middle_name] C=`Степанович` I=``
- FIELD `passport_verify.snils` [absent → absent:snils] C=`992-954-702 83` I=``
- REPLY I: Добрый день! Прежде чем обращаться к системе, я обязан проверить контрольную сумму СНИЛС по алгоритму ПФР. **Проверка СНИЛС 992-954-702, к.ч. 42:** | Позиция | Цифра | Вес | Произведение | |---------|-------|-----|-------------| | 1 | 1 | 9 | 9 | | 2 | 5 | 8 | 40 | | 3 | 0 | 7 | 0 | | 4 | 8 | 6 | 4…

## validate-019|0 · validate · voice_raw · L1 = · L3 ≠ · C′≈C да · причина: **other**
- USER[1]: здравствуйтее сверьте моии данныее снилс двадцать пяять двадцать восемсь четырнадцать пятьдесят два пятьсот шестьдесят четыре паспорт сорок шесть девятнадцать тринадцать шесят семь девяносто один кузнецова ольга дмитриевна
- seen SNILS `двадцать пяять двадцать восемсь четырнадцать пятьдесят два пятьсот шестьдесят четыре` → `848-433-570 49`
- seen PASSPORT `сорок шесть девятнадцать тринадцать шесят семь девяносто один` → `00 16 835125`
- seen NAME `кузнецова ольга дмитриевна` → `Фомина Юлия Валентиновна`
- C: `passport_verify` {'passport': {'series': '4619', 'number': '136791'}, 'person': {'last_name': 'Кузнецова', 'first_name': 'Ольга', 'middle_name': 'Дмитриевна'}, 'snils': '252-814-525 64'}
- I: `passport_verify` written={'passport': {'series': '0016', 'number': '835125'}, 'person': {'last_name': 'Фомина', 'first_name': 'Юлия', 'middle_name': 'Валентиновна'}} → restored={'passport': {'series': '4619', 'number': '136791'}, 'person': {'last_name': 'кузнецова', 'first_name': 'ольга', 'middle_name': 'дмитриевна'}}
- C′: `passport_verify` {'passport': {'series': '4619', 'number': '136791'}, 'person': {'last_name': 'Кузнецова', 'first_name': 'Ольга', 'middle_name': 'Дмитриевна'}, 'snils': '252-814-525 64'}
- FIELD `passport_verify.snils` [absent → absent:snils] C=`252-814-525 64` I=``
- REPLY I: Здравствуйте! Проверяю данные. **СНИЛС двадцать пяять двадцать восемсь четырнадцать пятьдесят два пятьсот шестьдесят четыре** — контрольная сумма не сходится. Расчёт по алгоритму ПФР: > 8×9 + 4×8 + 8×7 + 4×6 + 3×5 + 3×4 + 5×3 + 7×2 + 0×1 = 240 > 240 mod 101 = 38 → ожидается **38**, а не **49** Пожа…

## validate-020|0 · validate · voice_itn · L1 = · L3 = · C′≈C да · причина: **leak-only**
- USER[1]: добрый день сверьте мои данные снилс 655-971-771 57 паспорт 9414 887065 миллер валерий леонидович
- **LEAK** SNILS `655-971-771 57` — модель видела настоящее значение
- seen PASSPORT `9414 887065` → `00 00 348581`
- seen NAME `миллер валерий леонидович` → `Ершов Евгений Фёдорович`
- C: — (без вызовов)
- I: — (без вызовов)
- C′: — (без вызовов)
- REPLY I: Добрый день! Перед обращением к инструменту я проверяю контрольную сумму СНИЛС по алгоритму ПФР. **Проверка СНИЛС 655-971-771 57:** | Цифра | Вес | Произведение | |-------|-----|--------------| | 6 | 9 | 54 | | 5 | 8 | 40 | | 5 | 7 | 35 | | 9 | 6 | 54 | | 7 | 5 | 35 | | 1 | 4 | 4 | | 7 | 3 | 21 | |…

## validate-032|0 · validate · voice_itn · L1 = · L3 = · C′≈C да · причина: **leak-only**
- USER[1]: сверьте мои данные снилс 578-890-119 63 паспорт 4114 285851 лебедев максим константинович
- **LEAK** SNILS `578-890-119 63` — модель видела настоящее значение
- seen PASSPORT `4114 285851` → `00 00 964797`
- seen NAME `лебедев максим константинович` → `Ершов Константин Романович`
- C: — (без вызовов)
- I: — (без вызовов)
- C′: — (без вызовов)
- REPLY I: ## ⚠️ Ошибка в СНИЛС Перед обращением к системе я проверил контрольную сумму СНИЛС по алгоритму ПФР: **Продиктован:** 578-890-119 **63** Расчёт: > 5×9 + 7×8 + 8×7 + 8×6 + 9×5 + 0×4 + 1×3 + 1×2 + 9×1 = **264** > 264 mod 101 = **62** Ожидаемое контрольное число: **62**, а вы продиктовали **63** — кон…

## validate-035|0 · validate · chat · L1 = · L3 = · C′≈C да · причина: **leak-only**
- USER[1]: привет сверьте мои данные снилс 688-606-727 65 паспорт 4617 202966 соколова анна игоревна
- **LEAK** SNILS `688-606-727 65` — модель видела настоящее значение
- seen PASSPORT `4617 202966` → `00 20 352220`
- seen NAME `соколова анна игоревна` → `Ершова Раиса Геннадьевна`
- C: — (без вызовов)
- I: — (без вызовов)
- C′: — (без вызовов)
- REPLY I: Здравствуйте! Прежде чем отправить запрос, я проверяю контрольные суммы. --- **Проверка СНИЛС: 688-606-727 65** Считаю по алгоритму ПФР: | Цифра | Вес | Произведение | |-------|-----|-------------| | 6 | 9 | 54 | | 8 | 8 | 64 | | 8 | 7 | 56 | | 6 | 6 | 36 | | 0 | 5 | 0 | | 6 | 4 | 24 | | 7 | 3 | 21…

