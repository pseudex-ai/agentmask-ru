# Микроскоп — v4-live-small

троек: 222 · разобрано: 123 · исключено: 0

## Причины (по тройкам)

| причина | троек |
|---|---|
| other | 59 |
| derived-only | 20 |
| validate-refuse | 12 |
| Б8-echo | 10 |
| partial-call | 9 |
| control_erred | 7 |
| Б10-city | 2 |
| typo-normalised | 2 |
| residual | 1 |
| Б9-span | 1 |

## Поля (по расходящимся полям)

| подпричина | полей |
|---|---|
| derived | 29 |
| absent:last_name | 27 |
| absent:first_name | 26 |
| absent:gender | 25 |
| absent:phone | 25 |
| absent:number | 23 |
| absent:street | 21 |
| absent:middle_name | 20 |
| name_partial | 20 |
| absent:series | 14 |
| absent:snils | 14 |
| control_erred | 13 |
| extra:gender | 12 |
| absent:name | 12 |
| extra:csv | 12 |
| absent:city | 11 |
| absent:building | 11 |
| absent:locality | 11 |
| absent:flat | 10 |
| absent:house | 10 |
| absent:initials | 10 |
| absent:name_latin | 10 |
| extra:last_name | 9 |
| loc_street | 9 |
| extra:phone | 8 |
| extra:first_name | 8 |
| absent:birth_date | 8 |
| extra:middle_name | 6 |
| extra:number | 6 |
| absent:email | 6 |
| extra:city | 4 |
| extra:flat | 4 |
| extra:house | 4 |
| extra:street | 4 |
| extra:birth_date | 4 |
| extra:initials | 4 |
| extra:name_latin | 4 |
| other/misderived | 3 |
| extra:email | 2 |
| ref_refused | 2 |
| name_case | 2 |
| absent:age | 2 |
| validated_refused | 2 |
| extra:age | 2 |
| extra:series | 2 |
| loc_other | 1 |
| name_lemma | 1 |
| absent:address | 1 |
| absent:postal_code | 1 |

## УТЕЧКИ В МОДЕЛЬ — 0 из 638 значений в сообщениях

| тип/регистр | значений |
|---|---|

| тройка | регистр | тип | значение | реплика |
|---|---|---|---|---|

## chain-000|0 · chain · sloppy · L1 = · L3 ≠ · C′≈C нет · причина: **other**
- USER[1]: привет это букин сергей иванович хочу поменять ардес доставки телефон 89164021187
- USER[2]: теперь переулок барышникова 7 кв 111
- USER[3]: и пришлите смс с подтверждением
- seen NAME `букин сергей иванович` → `Наумов Леонид Валентинович`
- seen PHONE `89164021187` → `+79462086497`
- seen LOC `переулок барышникова 7 кв 111` → `переулок Лавандовый 97, кв. 76`
- C: `crm_find_contact` {'query': {'phone': '+79164021187'}}
- C: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Букин', 'first_name': 'Сергей', 'middle_name': 'Иванович', 'initials': 'С.И.', 'name_latin': 'Bukin Sergei', 'phone': '+79164021187', 'email': 'bukin76@yandex.…
- C: `notify_sms` {'number': '+79164021187', 'text': 'Здравствуйте, Сергей Иванович! Ваш адрес доставки успешно изменён: г. Сарапул, пер. Барышникова, д. 7, кв. 111. Если вы не делали этот запрос, свяжитесь с нами.', …
- I: `crm_find_contact` written={'query': {'phone': '+79462086497'}} → restored={'query': {'phone': '+79164021187'}}
- I: `crm_upsert_contact` written={'id': 'c-1', 'contact': {'last_name': 'Наумов', 'first_name': 'Леонид', 'middle_name': 'Валентинович', 'phone': '+79462086497', 'email': 'rzdcexvp@example.ru', 'birth_date': '1987-07-25', 'initials': 'Л.В.', 'name_latin': 'Naumov Leonid', 'address': {'city':… → restored={'id': 'c-1', 'contact': {'last_name': 'букин', 'first_name': 'сергей', 'middle_name': 'иванович', 'phone': '+79164021187', 'email': 'bukin76@yandex.ru', 'birth_date': '1987-03-14', 'initials': 'С.И.', 'name_latin': 'Bukin Sergei', 'address': {'city': 'Сарапу…
- I: `notify_sms` written={'number': '+79462086497', 'sign': 'Dostavka', 'text': 'Леонид Валентинович, ваш адрес доставки успешно изменён: г. Сарапул, пер. Лавандовый, д. 97, кв. 76. Если это были не вы, свяжитесь с нами.'} → restored={'number': '+79164021187', 'sign': 'Dostavka', 'text': 'сергей иванович, ваш адрес доставки успешно изменён: г. Сарапул, пер. барышникова, д. 7, кв. 111. Если это были не вы, свяжитесь с нами.'}
- C′: `crm_find_contact` {'query': {'phone': '+79164021187'}}
- C′: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Букин', 'first_name': 'Сергей', 'middle_name': 'Иванович', 'initials': 'С.И.', 'name_latin': 'Bukin Sergey', 'phone': '+79164021187', 'email': 'bukin76@yandex.…
- C′: `notify_sms` {'number': '+79164021187', 'sign': 'Dostavka', 'text': 'Сергей Иванович, адрес доставки успешно изменён на: г. Сарапул, пер. Барышникова, д. 7, кв. 111. Если это были не вы, позвоните нам.'}
- FIELD `crm_upsert_contact.contact.gender` [absent → absent:gender] C=`M` I=``
- REPLY I: СМС отправлено на номер 89164021187! 📱 Если возникнут ещё вопросы — всегда рады помочь!

## chain-003|0 · chain · voice_raw · L1 = · L3 ≠ · C′≈C да · причина: **derived-only**
- USER[1]: девушка здравствуйте этоо полякова валентина ивановна хочу поменяять адрес доставки телефон восемь девятьсот семьдесят семь восемьсот девяно семь шеесят два двадцать шесть
- USER[2]: записывайте маяковского дом двадцать три квартира сто восемь
- USER[3]: ии смс пришлите чтоо адреес поменяли
- seen NAME `полякова валентина ивановна` → `Осипова Кристина Евгеньевна`
- seen PHONE `восемь девятьсот семьдесят семь восемьсот девяно семь шеесят два двадцать шесть` → `+79331509014`
- seen LOC `маяковского дом двадцать три квартира сто восемь` → `улица Еловая 19, кв. 72`
- C: `crm_find_contact` {'query': {'phone': '+79778976226'}}
- C: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Полякова', 'first_name': 'Валентина', 'middle_name': 'Ивановна', 'initials': 'В.И.', 'name_latin': 'Polyakova Valentina', 'phone': '+79778976226', 'email': 'po…
- C: `notify_sms` {'number': '+79778976226', 'text': 'Валентина Ивановна, адрес доставки в вашем профиле успешно изменён на: г. Самара, ул. Маяковского, д. 23, кв. 108.', 'sign': 'Dostavka'}
- I: `crm_find_contact` written={'query': {'phone': '+79331509014'}} → restored={'query': {'phone': '+79778976226'}}
- I: `crm_upsert_contact` written={'id': 'c-1', 'contact': {'last_name': 'Осипова', 'first_name': 'Кристина', 'middle_name': 'Евгеньевна', 'initials': 'К.Е.', 'name_latin': 'Osipova Kristina', 'phone': '+79331509014', 'email': 'ndwlecii@example.ru', 'birth_date': '1974-03-21', 'gender': 'F', … → restored={'id': 'c-1', 'contact': {'last_name': 'полякова', 'first_name': 'валентина', 'middle_name': 'ивановна', 'initials': 'В.И.', 'name_latin': 'Poliakova Valentina', 'phone': '+79778976226', 'email': 'polyakova72@mail.ru', 'birth_date': '1974-10-08', 'gender': 'F…
- I: `notify_sms` written={'number': '+79331509014', 'text': 'Здравствуйте, Кристина Евгеньевна! Адрес доставки в вашей карточке успешно изменён на: г. Самара, ул. Еловая, д. 19, кв. 72.', 'sign': 'Dostavka'} → restored={'number': '+79778976226', 'text': 'Здравствуйте, валентина ивановна! Адрес доставки в вашей карточке успешно изменён на: г. Самара, маяковского, д. 23, кв. 108.', 'sign': 'Dostavka'}
- C′: `crm_find_contact` {'query': {'phone': '+79778976226'}}
- C′: `crm_find_contact` {'query': {'last_name': 'Полякова'}}
- C′: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Полякова', 'first_name': 'Валентина', 'middle_name': 'Ивановна', 'initials': 'В.И.', 'name_latin': 'Polyakova Valentina', 'phone': '+79778976226', 'email': 'po…
- C′: `notify_sms` {'number': '+79778976226', 'text': 'Валентина Ивановна, адрес доставки успешно изменён на: г. Самара, ул. Маяковского, д. 23, кв. 108.', 'sign': 'Dostavka'}
- FIELD `crm_upsert_contact.contact.name_latin` [derived/unverifiable → derived] C=`Polyakova Valentina` I=`Poliakova Valentina`
- REPLY I: СМС отправлено! 📱 Скоро придёт сообщение на номер **восемь девятьсот семьдесят семь восемьсот девяно семь шеесят два двадцать шесть**. Ещё чем-то могу помочь, валентина ивановна?

## chain-003|1 · chain · voice_raw · L1 = · L3 ≠ · C′≈C да · причина: **derived-only**
- USER[1]: девушка здравствуйте этоо полякова валентина ивановна хочу поменяять адрес доставки телефон восемь девятьсот семьдесят семь восемьсот девяно семь шеесят два двадцать шесть
- USER[2]: записывайте маяковского дом двадцать три квартира сто восемь
- USER[3]: ии смс пришлите чтоо адреес поменяли
- seen NAME `полякова валентина ивановна` → `Фомина Светлана Алексеевна`
- seen PHONE `восемь девятьсот семьдесят семь восемьсот девяно семь шеесят два двадцать шесть` → `+79663235503`
- seen LOC `маяковского дом двадцать три квартира сто восемь` → `улица Каштановая 142, кв. 32`
- C: `crm_find_contact` {'query': {'phone': '+79778976226'}}
- C: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Полякова', 'first_name': 'Валентина', 'middle_name': 'Ивановна', 'initials': 'В.И.', 'name_latin': 'Polyakova Valentina', 'phone': '+79778976226', 'email': 'po…
- C: `notify_sms` {'number': '+79778976226', 'sign': 'Dostavka', 'text': 'Здравствуйте, Валентина Ивановна! Адрес доставки в вашем профиле успешно изменён на: г. Самара, ул. Маяковского, д. 23, кв. 108. Если это были …
- I: `crm_find_contact` written={'query': {'phone': '+79663235503'}} → restored={'query': {'phone': '+79778976226'}}
- I: `crm_upsert_contact` written={'id': 'c-1', 'contact': {'last_name': 'Фомина', 'first_name': 'Светлана', 'middle_name': 'Алексеевна', 'initials': 'С.А.', 'name_latin': 'Fomina Svetlana', 'phone': '+79663235503', 'email': 'qzphtfst@example.ru', 'birth_date': '1974-04-20', 'gender': 'F', 'a… → restored={'id': 'c-1', 'contact': {'last_name': 'полякова', 'first_name': 'валентина', 'middle_name': 'ивановна', 'initials': 'В.И.', 'name_latin': 'Poliakova Valentina', 'phone': '+79778976226', 'email': 'polyakova72@mail.ru', 'birth_date': '1974-10-08', 'gender': 'F…
- I: `notify_sms` written={'number': '+79663235503', 'text': 'Светлана Алексеевна, адрес доставки в вашей карточке успешно изменён на: Самара, ул. Каштановая, д. 142, кв. 32. Если это были не вы, пожалуйста, свяжитесь с нами.', 'sign': 'Dostavka'} → restored={'number': '+79778976226', 'text': 'валентина ивановна, адрес доставки в вашей карточке успешно изменён на: Самара, маяковского, д. 23, кв. 108. Если это были не вы, пожалуйста, свяжитесь с нами.', 'sign': 'Dostavka'}
- C′: `crm_find_contact` {'query': {'phone': '+79778976226'}}
- C′: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Полякова', 'first_name': 'Валентина', 'middle_name': 'Ивановна', 'initials': 'В.И.', 'name_latin': 'Polyakova Valentina', 'phone': '+79778976226', 'email': 'po…
- C′: `notify_sms` {'number': '+79778976226', 'text': 'Валентина Ивановна, адрес доставки успешно изменён: г. Самара, ул. Маяковского, д. 23, кв. 108. Если это были не вы — свяжитесь с нами.', 'sign': 'Dostavka'}
- FIELD `crm_upsert_contact.contact.name_latin` [derived/unverifiable → derived] C=`Polyakova Valentina` I=`Poliakova Valentina`
- REPLY I: СМС отправлено! 📱 валентина ивановна, сообщение с подтверждением смены адреса уже на вашем телефоне. Если будут вопросы — обращайтесь. Всего доброго! 😊

## chain-004|0 · chain · voice_raw · L1 = · L3 ≠ · C′≈C нет · причина: **derived-only**
- USER[1]: добрыый деень этоо захаров владислав юрьевич хочу поменять адресто доставки телефоон восемь девятьсот пятьдесят восемесят ноль восемь восемьдесят восемь один
- USER[2]: теперь бульвар репина сорок квартира двести сорок восемь
- USER[3]: ии смс пришлитее что адрес поменяли
- seen NAME `захаров владислав юрьевич` → `Мещеряков Николай Валерьевич`
- seen PHONE `восемь девятьсот пятьдесят восемесят ноль восемь восемьдесят восемь один` → `+79998296225`
- seen LOC `бульвар репина сорок квартира двести сорок восемь` → `Барбарисовый бульвар 42, кв. 107`
- C: `crm_find_contact` {'query': {'last_name': 'Захаров'}}
- C: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Захаров', 'first_name': 'Владислав', 'middle_name': 'Юрьевич', 'phone': '+79508008881', 'email': 'zaharov97@list.ru', 'birth_date': '1997-06-17', 'initials': '…
- C: `notify_sms` {'number': '+79508008881', 'sign': 'Dostavka', 'text': 'Владислав Юрьевич, адрес доставки в вашей карточке успешно изменён на: г. Колпино, бульвар Репина, д. 40, кв. 248. Если это были не вы, позвони…
- I: `crm_find_contact` written={'query': {'phone': '+79998296225'}} → restored={'query': {'phone': '+79508008881'}}
- I: `crm_upsert_contact` written={'id': 'c-1', 'contact': {'last_name': 'Мещеряков', 'first_name': 'Николай', 'middle_name': 'Валерьевич', 'phone': '+79998296225', 'email': 'ziadzpcu@example.ru', 'birth_date': '1997-05-08', 'initials': 'Н.В.', 'name_latin': 'Meshcheryakov Nikolai', 'gender':… → restored={'id': 'c-1', 'contact': {'last_name': 'захаров', 'first_name': 'владислав', 'middle_name': 'юрьевич', 'phone': '+79508008881', 'email': 'zaharov97@list.ru', 'birth_date': '1997-06-17', 'initials': 'В.Ю.', 'name_latin': 'Meshcheryakov Vladislav', 'gender': 'M…
- I: `notify_sms` written={'number': '+79998296225', 'text': 'Николай Валерьевич, ваш адрес доставки успешно изменён на: г. Колпино, Барбарисовый бульвар, д. 42, кв. 107. Если это были не вы, свяжитесь с нами.', 'sign': 'Dostavka'} → restored={'number': '+79508008881', 'text': 'владислав юрьевич, ваш адрес доставки успешно изменён на: г. Колпино, репина бульвар, д. 40, кв. 248. Если это были не вы, свяжитесь с нами.', 'sign': 'Dostavka'}
- C′: `crm_find_contact` {'query': {'last_name': 'Захаров'}}
- C′: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Захаров', 'first_name': 'Владислав', 'middle_name': 'Юрьевич', 'initials': 'В.Ю.', 'name_latin': 'Zakharov Vladislav', 'phone': '+79508008881', 'email': 'zahar…
- C′: `notify_sms` {'number': '+79508008881', 'sign': 'Dostavka', 'text': 'Владислав Юрьевич, адрес доставки в вашей карточке успешно изменён на: г. Колпино, бульвар Репина, д. 40, кв. 248. Если это были не вы, пожалуй…
- FIELD `crm_find_contact.query.last_name` [absent → absent:last_name] C=`Захаров` I=``
- FIELD `crm_find_contact.query.phone` [extra → extra:phone] C=`` I=`+79508008881`
- FIELD `crm_upsert_contact.contact.name_latin` [derived/unverifiable → derived] C=`Zakharov Vladislav` I=`Meshcheryakov Vladislav`
- REPLY I: СМС отправлено! 📱 владислав юрьевич получит уведомление об изменении адреса доставки. Если нужно что-то ещё — обращайтесь!

## chain-004|1 · chain · voice_raw · L1 ≠ · L3 ≠ · C′≈C нет · причина: **other**
- USER[1]: добрыый деень этоо захаров владислав юрьевич хочу поменять адресто доставки телефоон восемь девятьсот пятьдесят восемесят ноль восемь восемьдесят восемь один
- USER[2]: теперь бульвар репина сорок квартира двести сорок восемь
- USER[3]: ии смс пришлитее что адрес поменяли
- seen NAME `захаров владислав юрьевич` → `Цветков Пётр Максимович`
- seen PHONE `восемь девятьсот пятьдесят восемесят ноль восемь восемьдесят восемь один` → `+79956864640`
- seen LOC `бульвар репина сорок квартира двести сорок восемь` → `Каштановый бульвар 107, кв. 101`
- C: — (без вызовов)
- I: `crm_find_contact` written={'query': {'phone': '+79956864640'}} → restored={'query': {'phone': '+79508008881'}}
- I: `crm_upsert_contact` written={'id': 'c-1', 'contact': {'last_name': 'Цветков', 'first_name': 'Пётр', 'middle_name': 'Максимович', 'initials': 'П.М.', 'name_latin': 'Tsvetkov Pyotr', 'phone': '+79956864640', 'email': 'vuaguyha@example.ru', 'birth_date': '1997-09-16', 'address': {'city': '… → restored={'id': 'c-1', 'contact': {'last_name': 'захаров', 'first_name': 'владислав', 'middle_name': 'юрьевич', 'initials': 'В.Ю.', 'name_latin': 'Zakharov Vladislav', 'phone': '+79508008881', 'email': 'zaharov97@list.ru', 'birth_date': '1997-06-17', 'address': {'city…
- I: `notify_sms` written={'number': '+79956864640', 'sign': 'Dostavka', 'text': 'Уважаемый Пётр Максимович, адрес доставки в вашей карточке успешно изменён на: г. Колпино, Каштановый бульвар, д. 107, кв. 101. Если это были не вы, свяжитесь с нами.'} → restored={'number': '+79508008881', 'sign': 'Dostavka', 'text': 'Уважаемый владислав юрьевич, адрес доставки в вашей карточке успешно изменён на: г. Колпино, репина бульвар, д. 40, кв. 248. Если это были не вы, свяжитесь с нами.'}
- C′: `crm_find_contact` {'query': {'last_name': 'Захаров'}}
- C′: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Захаров', 'first_name': 'Владислав', 'middle_name': 'Юрьевич', 'initials': 'В.Ю.', 'name_latin': 'Zakharov Vladislav', 'phone': '+79508008881', 'email': 'zahar…
- C′: `notify_sms` {'number': '+79508008881', 'sign': 'Dostavka', 'text': 'Владислав Юрьевич, адрес доставки в вашем профиле успешно изменён на: г. Колпино, бульвар Репина, д. 40, кв. 248.'}
- FIELD `crm_find_contact.query.phone` [extra → extra:phone] C=`` I=`+79508008881`
- FIELD `crm_upsert_contact.contact.address.city` [extra → extra:city] C=`` I=`Колпино`
- FIELD `crm_upsert_contact.contact.address.flat` [extra → extra:flat] C=`` I=`248`
- FIELD `crm_upsert_contact.contact.address.house` [extra → extra:house] C=`` I=`40`
- FIELD `crm_upsert_contact.contact.address.street` [extra → extra:street] C=`` I=`репина бульвар`
- FIELD `crm_upsert_contact.contact.birth_date` [extra → extra:birth_date] C=`` I=`1997-06-17`
- FIELD `crm_upsert_contact.contact.email` [extra → extra:email] C=`` I=`zaharov97@list.ru`
- FIELD `crm_upsert_contact.contact.first_name` [extra → extra:first_name] C=`` I=`владислав`
- FIELD `crm_upsert_contact.contact.initials` [extra → extra:initials] C=`` I=`В.Ю.`
- FIELD `crm_upsert_contact.contact.last_name` [extra → extra:last_name] C=`` I=`захаров`
- FIELD `crm_upsert_contact.contact.middle_name` [extra → extra:middle_name] C=`` I=`юрьевич`
- FIELD `crm_upsert_contact.contact.name_latin` [extra → extra:name_latin] C=`` I=`Zakharov Vladislav`
- FIELD `crm_upsert_contact.contact.phone` [extra → extra:phone] C=`` I=`+79508008881`
- FIELD `notify_sms.number` [extra → extra:number] C=`` I=`+79508008881`
- REPLY I: СМС отправлено на номер **восемь девятьсот пятьдесят восемесят ноль восемь восемьдесят восемь один**! Если есть ещё вопросы — обращайтесь! 😊

## chain-008|0 · chain · sloppy · L1 ≠ · L3 ≠ · C′≈C нет · причина: **other**
- USER[1]: это громов артём витальевич хчоу поменять адрес доставки телефон 8-925-011-15-03
- USER[2]: записывйате тельмана 94 кв 56
- USER[3]: и отпарвьте мне смс что всё запсиали
- seen NAME `громов артём витальевич` → `Шилов Андрей Ильич`
- seen PHONE `8-925-011-15-03` → `+79388479395`
- seen LOC `тельмана 94 кв 56` → `улицы Рябиновой 81, кв. 6`
- C: `crm_find_contact` {'query': {'phone': '+79250111503'}}
- C: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Громов', 'first_name': 'Артём', 'middle_name': 'Витальевич', 'initials': 'А.В.', 'name_latin': 'Gromov Artem', 'phone': '+79250111503', 'email': 'gromov94@yand…
- I: `crm_find_contact` written={'query': {'phone': '+79388479395'}} → restored={'query': {'phone': '+79250111503'}}
- I: `crm_upsert_contact` written={'id': 'c-1', 'contact': {'last_name': 'громов', 'first_name': 'Андрей', 'middle_name': 'Ильич', 'phone': '+79388479395', 'email': 'wzlazuxc@example.ru', 'birth_date': '1987-08-10', 'initials': 'А.И.', 'name_latin': 'Gromov Andrey', 'address': {'city': 'самар… → restored={'id': 'c-1', 'contact': {'last_name': 'громов', 'first_name': 'артём', 'middle_name': 'витальевич', 'phone': '+79250111503', 'email': 'gromov94@yandex.ru', 'birth_date': '1987-01-14', 'initials': 'А.В.', 'name_latin': 'Gromov Artem', 'address': {'city': 'сам…
- I: `notify_sms` written={'number': '+79388479395', 'text': 'Андрей Ильич, ваш адрес доставки успешно обновлён: г. Самара, ул. Рябиновая, д. 81, кв. 6. Если что-то не так — свяжитесь с нами.', 'sign': 'Dostavka'} → restored={'number': '+79250111503', 'text': 'артём витальевич, ваш адрес доставки успешно обновлён: г. Самара, тельмана, д. 94, кв. 56. Если что-то не так — свяжитесь с нами.', 'sign': 'Dostavka'}
- C′: `crm_find_contact` {'query': {'phone': '+79250111503'}}
- C′: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Громов', 'first_name': 'Артём', 'middle_name': 'Витальевич', 'initials': 'А.В.', 'name_latin': 'Gromov Artem', 'phone': '+79250111503', 'email': 'gromov94@yand…
- C′: `notify_sms` {'number': '+79250111503', 'text': 'Артём Витальевич, ваш адрес доставки успешно обновлён: г. Самара, ул. Тельмана, д. 94, кв. 56.', 'sign': 'Dostavka'}
- FIELD `crm_upsert_contact.contact.gender` [absent → absent:gender] C=`M` I=``
- FIELD `notify_sms.number` [extra → extra:number] C=`` I=`+79250111503`
- REPLY I: СМС отправлено на номер **8-925-011-15-03**! Клиент получит подтверждение об обновлении адреса. Если нужно что-то ещё — обращайтесь! 😊

## chain-008|1 · chain · sloppy · L1 ≠ · L3 ≠ · C′≈C нет · причина: **Б10-city**
- USER[1]: это громов артём витальевич хчоу поменять адрес доставки телефон 8-925-011-15-03
- USER[2]: записывйате тельмана 94 кв 56
- USER[3]: и отпарвьте мне смс что всё запсиали
- seen NAME `громов артём витальевич` → `Юдин Святослав Валентинович`
- seen PHONE `8-925-011-15-03` → `+79227117526`
- seen LOC `тельмана 94 кв 56` → `улицы Липовой 111, кв. 161`
- C: `crm_find_contact` {'query': {'phone': '+79250111503'}}
- C: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Громов', 'first_name': 'Артём', 'middle_name': 'Витальевич', 'initials': 'А.В.', 'name_latin': 'Gromov Artem', 'phone': '+79250111503', 'email': 'gromov94@yand…
- C: `notify_sms` {'number': '+79250111503', 'text': 'Артём Витальевич, ваш адрес доставки успешно обновлён: г. Самара, ул. Тельмана, д. 94, кв. 56. Если что-то не так — свяжитесь с нами.', 'sign': 'Dostavka'}
- I: — (без вызовов)
- C′: `crm_find_contact` {'query': {'phone': '+79250111503'}}
- C′: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Громов', 'first_name': 'Артём', 'middle_name': 'Витальевич', 'initials': 'А.В.', 'name_latin': 'Gromov Artem', 'phone': '+79250111503', 'email': 'gromov94@yand…
- C′: `notify_sms` {'number': '+79250111503', 'text': 'Артём Витальевич, ваш адрес доставки успешно обновлён: г. Самара, ул. Тельмана, д. 94, кв. 56.', 'sign': 'Dostavka'}
- FIELD `crm_find_contact.query.phone` [absent → absent:phone] C=`+79250111503` I=``
- FIELD `crm_upsert_contact.contact.address.city` [absent → absent:city] C=`Самара` I=``
- FIELD `crm_upsert_contact.contact.address.flat` [absent → absent:flat] C=`56` I=``
- FIELD `crm_upsert_contact.contact.address.house` [absent → absent:house] C=`94` I=``
- FIELD `crm_upsert_contact.contact.address.street` [absent → absent:street] C=`Тельмана` I=``
- FIELD `crm_upsert_contact.contact.birth_date` [absent → absent:birth_date] C=`1987-01-14` I=``
- FIELD `crm_upsert_contact.contact.email` [absent → absent:email] C=`gromov94@yandex.ru` I=``
- FIELD `crm_upsert_contact.contact.first_name` [absent → absent:first_name] C=`Артём` I=``
- FIELD `crm_upsert_contact.contact.gender` [absent → absent:gender] C=`M` I=``
- FIELD `crm_upsert_contact.contact.initials` [absent → absent:initials] C=`А.В.` I=``
- FIELD `crm_upsert_contact.contact.last_name` [absent → absent:last_name] C=`Громов` I=``
- FIELD `crm_upsert_contact.contact.middle_name` [absent → absent:middle_name] C=`Витальевич` I=``
- FIELD `crm_upsert_contact.contact.name_latin` [absent → absent:name_latin] C=`Gromov Artem` I=``
- FIELD `crm_upsert_contact.contact.phone` [absent → absent:phone] C=`+79250111503` I=``
- FIELD `notify_sms.number` [absent → absent:number] C=`+79250111503` I=``
- REPLY I: Город всё ещё нужен — без него не смогу сохранить адрес. В каком городе тельмана 94?

## chain-009|0 · chain · sloppy · L1 ≠ · L3 ≠ · C′≈C да · причина: **Б8-echo**
- USER[1]: здрасте это захаров владислав юрьевич хочу поменять адрес доставки телефон 8 960 746 48 97
- USER[2]: заптсывайте вишнёвая 8 кв 176
- USER[3]: и пришлите смс с подтверждением
- seen NAME `захаров владислав юрьевич` → `Тарасов Вячеслав Павлович`
- seen PHONE `8 960 746 48 97` → `+79105014120`
- seen LOC `вишнёвая 8 кв 176` → `улица Берёзовая 71, кв. 65`
- C: `crm_find_contact` {'query': {'phone': '+79607464897'}}
- C: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Захаров', 'first_name': 'Владислав', 'middle_name': 'Юрьевич', 'initials': 'В.Ю.', 'name_latin': 'Zakharov Vladislav', 'phone': '+79607464897', 'email': 'zahar…
- C: `notify_sms` {'number': '+79607464897', 'text': 'Захаров В.Ю., ваш адрес доставки успешно изменён: г. Глазов, ул. Вишнёвая, д. 8, кв. 176.', 'sign': 'Dostavka'}
- I: `crm_find_contact` written={'query': {'phone': '+79105014120'}} → restored={'query': {'phone': '+79607464897'}}
- C′: `crm_find_contact` {'query': {'phone': '+79607464897'}}
- C′: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Захаров', 'first_name': 'Владислав', 'middle_name': 'Юрьевич', 'initials': 'В.Ю.', 'name_latin': 'Zakharov Vladislav', 'phone': '+79607464897', 'email': 'zahar…
- C′: `notify_sms` {'number': '+79607464897', 'text': 'Захаров В.Ю., ваш адрес доставки успешно обновлён: г. Глазов, ул. Вишнёвая, д. 8, кв. 176.', 'sign': 'Dostavka'}
- FIELD `crm_upsert_contact.contact.address.city` [absent → absent:city] C=`Глазов` I=``
- FIELD `crm_upsert_contact.contact.address.flat` [absent → absent:flat] C=`176` I=``
- FIELD `crm_upsert_contact.contact.address.house` [absent → absent:house] C=`8` I=``
- FIELD `crm_upsert_contact.contact.address.street` [absent → absent:street] C=`Вишнёвая` I=``
- FIELD `crm_upsert_contact.contact.birth_date` [absent → absent:birth_date] C=`1984-05-22` I=``
- FIELD `crm_upsert_contact.contact.email` [absent → absent:email] C=`zaharov70@list.ru` I=``
- FIELD `crm_upsert_contact.contact.first_name` [absent → absent:first_name] C=`Владислав` I=``
- FIELD `crm_upsert_contact.contact.gender` [absent → absent:gender] C=`M` I=``
- FIELD `crm_upsert_contact.contact.initials` [absent → absent:initials] C=`В.Ю.` I=``
- FIELD `crm_upsert_contact.contact.last_name` [absent → absent:last_name] C=`Захаров` I=``
- FIELD `crm_upsert_contact.contact.middle_name` [absent → absent:middle_name] C=`Юрьевич` I=``
- FIELD `crm_upsert_contact.contact.name_latin` [absent → absent:name_latin] C=`Zakharov Vladislav` I=``
- FIELD `crm_upsert_contact.contact.phone` [absent → absent:phone] C=`+79607464897` I=``
- FIELD `notify_sms.number` [absent → absent:number] C=`+79607464897` I=``
- REPLY I: владислав юрьевич, прежде чем обновить и отправить подтверждение — укажите, пожалуйста, **город**? Без него не смогу корректно сохранить адрес.

## chain-009|1 · chain · sloppy · L1 ≠ · L3 ≠ · C′≈C да · причина: **Б8-echo**
- USER[1]: здрасте это захаров владислав юрьевич хочу поменять адрес доставки телефон 8 960 746 48 97
- USER[2]: заптсывайте вишнёвая 8 кв 176
- USER[3]: и пришлите смс с подтверждением
- seen NAME `захаров владислав юрьевич` → `Сазонов Фёдор Владимирович`
- seen PHONE `8 960 746 48 97` → `+79896301555`
- seen LOC `вишнёвая 8 кв 176` → `улица Липовая 163, кв. 181`
- C: `crm_find_contact` {'query': {'phone': '+79607464897'}}
- C: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Захаров', 'first_name': 'Владислав', 'middle_name': 'Юрьевич', 'initials': 'В.Ю.', 'name_latin': 'Zakharov Vladislav', 'phone': '+79607464897', 'email': 'zahar…
- C: `notify_sms` {'number': '+79607464897', 'sign': 'Dostavka', 'text': 'Захаров В.Ю., адрес доставки успешно изменён: г. Глазов, ул. Вишнёвая, д. 8, кв. 176. Если это были не вы, свяжитесь с нами.'}
- I: `crm_find_contact` written={'query': {'phone': '+79896301555'}} → restored={'query': {'phone': '+79607464897'}}
- C′: `crm_find_contact` {'query': {'phone': '+79607464897'}}
- C′: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Захаров', 'first_name': 'Владислав', 'middle_name': 'Юрьевич', 'initials': 'В.Ю.', 'name_latin': 'Zakharov Vladislav', 'phone': '+79607464897', 'email': 'zahar…
- C′: `notify_sms` {'number': '+79607464897', 'sign': 'Dostavka', 'text': 'Здравствуйте, Владислав Юрьевич! Адрес доставки успешно изменён: г. Глазов, ул. Вишнёвая, д. 8, кв. 176. Если вы не делали этот запрос, свяжите…
- FIELD `crm_upsert_contact.contact.address.city` [absent → absent:city] C=`Глазов` I=``
- FIELD `crm_upsert_contact.contact.address.flat` [absent → absent:flat] C=`176` I=``
- FIELD `crm_upsert_contact.contact.address.house` [absent → absent:house] C=`8` I=``
- FIELD `crm_upsert_contact.contact.address.street` [absent → absent:street] C=`Вишнёвая` I=``
- FIELD `crm_upsert_contact.contact.birth_date` [absent → absent:birth_date] C=`1984-05-22` I=``
- FIELD `crm_upsert_contact.contact.email` [absent → absent:email] C=`zaharov70@list.ru` I=``
- FIELD `crm_upsert_contact.contact.first_name` [absent → absent:first_name] C=`Владислав` I=``
- FIELD `crm_upsert_contact.contact.initials` [absent → absent:initials] C=`В.Ю.` I=``
- FIELD `crm_upsert_contact.contact.last_name` [absent → absent:last_name] C=`Захаров` I=``
- FIELD `crm_upsert_contact.contact.middle_name` [absent → absent:middle_name] C=`Юрьевич` I=``
- FIELD `crm_upsert_contact.contact.name_latin` [absent → absent:name_latin] C=`Zakharov Vladislav` I=``
- FIELD `crm_upsert_contact.contact.phone` [absent → absent:phone] C=`+79607464897` I=``
- FIELD `notify_sms.number` [absent → absent:number] C=`+79607464897` I=``
- REPLY I: Понял насчёт СМС! Только уточните, пожалуйста — в каком **городе** новый адрес? Без него не могу сохранить. 😊

## chain-013|1 · chain · chat · L1 = · L3 ≠ · C′≈C да · причина: **other**
- USER[1]: привет это сергеев кирилл сергеевич хочу поменять адрес доставки телефон +79053336570
- USER[2]: записывайте лермонтова 178 кв 77
- USER[3]: и смс пришлите что адрес поменяли
- seen NAME `сергеев кирилл сергеевич` → `Жуков Радислав Дмитриевич`
- seen PHONE `+79053336570` → `+79078713941`
- seen LOC `лермонтова 178 кв 77` → `улицы Сиреневой 146, кв. 216`
- C: `crm_find_contact` {'query': {'phone': '+79053336570'}}
- C: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Сергеев', 'first_name': 'Кирилл', 'middle_name': 'Сергеевич', 'initials': 'К.С.', 'name_latin': 'Sergeev Kirill', 'phone': '+79053336570', 'email': 'sergeev83@…
- C: `notify_sms` {'number': '+79053336570', 'text': 'Кирилл Сергеевич, адрес доставки успешно изменён: г. Воткинск, ул. Лермонтова, д. 178, кв. 77.', 'sign': 'Dostavka'}
- I: `crm_find_contact` written={'query': {'phone': '+79078713941'}} → restored={'query': {'phone': '+79053336570'}}
- I: `crm_upsert_contact` written={'id': 'c-1', 'contact': {'last_name': 'Жуков', 'first_name': 'Радислав', 'middle_name': 'Дмитриевич', 'initials': 'Р.Д.', 'name_latin': 'Zhukov Radislav', 'phone': '+79078713941', 'email': 'ztsthina@example.ru', 'birth_date': '1990-08-19', 'gender': 'M', 'ad… → restored={'id': 'c-1', 'contact': {'last_name': 'сергеев', 'first_name': 'кирилл', 'middle_name': 'сергеевич', 'initials': 'К.С.', 'name_latin': 'Sergeev Kirill', 'phone': '+79053336570', 'email': 'sergeev83@bk.ru', 'birth_date': '1990-11-24', 'gender': 'M', 'address'…
- I: `notify_sms` written={'number': '+79078713941', 'text': 'Радислав Дмитриевич, адрес доставки в вашей карточке успешно изменён на: г. Воткинск, ул. Сиреневая, д. 146, кв. 216. Если это были не вы — свяжитесь с нами.', 'sign': 'Dostavka'} → restored={'number': '+79053336570', 'text': 'кирилл сергеевич, адрес доставки в вашей карточке успешно изменён на: г. Воткинск, лермонтова, д. 178, кв. 77. Если это были не вы — свяжитесь с нами.', 'sign': 'Dostavka'}
- C′: `crm_find_contact` {'query': {'phone': '+79053336570'}}
- C′: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Сергеев', 'first_name': 'Кирилл', 'middle_name': 'Сергеевич', 'initials': 'К.С.', 'name_latin': 'Sergeev Kirill', 'phone': '+79053336570', 'email': 'sergeev83@…
- C′: `notify_sms` {'number': '+79053336570', 'text': 'Кирилл Сергеевич, ваш адрес доставки успешно изменён на: г. Воткинск, ул. Лермонтова, д. 178, кв. 77. Если это были не вы — свяжитесь с нами.', 'sign': 'Dostavka'}
- FIELD `crm_upsert_contact.contact.gender` [extra → extra:gender] C=`` I=`M`
- REPLY I: СМС отправлено! 📱 Всё готово, кирилл сергеевич. Если будут ещё вопросы — обращайтесь!

## chain-014|0 · chain · voice_raw · L1 ≠ · L3 ≠ · C′≈C нет · причина: **Б8-echo**
- USER[1]: девушка здравствуйте этоо кузнецов дмитрий андреевич хочуу поменять адрес доставки телефон восемсь девятьсот двадцать семь тристо девятьсот четырнадцать ноль
- USER[2]: записывайте проезд репина дом сто девяносто восемь квартира шестьдесят два
- USER[3]: и пришлите смс с подтверждением
- seen NAME `кузнецов дмитрий андреевич` → `Карпов Тарас Ильич`
- seen PHONE `восемсь девятьсот двадцать семь тристо девятьсот четырнадцать ноль` → `+79820066994`
- seen LOC `проезд репина дом сто девяносто восемь квартира шестьдесят два` → `проезд Речной 49, кв. 247`
- C: `crm_find_contact` {'query': {'phone': '+79273009140'}}
- C: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Кузнецов', 'first_name': 'Дмитрий', 'middle_name': 'Андреевич', 'initials': 'Д.А.', 'name_latin': 'Kuznetsov Dmitry', 'phone': '+79273009140', 'email': 'kuznec…
- C: `notify_sms` {'number': '+79273009140', 'sign': 'Dostavka', 'text': 'Здравствуйте, Дмитрий Андреевич! Ваш адрес доставки успешно обновлён: г. Абакан, пр. Репина, д. 198, кв. 62.'}
- I: `crm_find_contact` written={'query': {'phone': '+79820066994'}} → restored={'query': {'phone': '+79273009140'}}
- C′: `crm_find_contact` {'query': {'phone': '+79273009140'}}
- C′: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Кузнецов', 'first_name': 'Дмитрий', 'middle_name': 'Андреевич', 'initials': 'Д.А.', 'name_latin': 'Kuznetsov Dmitry', 'phone': '+79273009140', 'email': 'kuznec…
- C′: `notify_sms` {'number': '+79273009140', 'sign': 'Dostavka', 'text': 'Дмитрий Андреевич, адрес доставки успешно изменён: г. Абакан, проезд Репина, д. 198, кв. 62. Если это были не вы, позвоните нам.'}
- FIELD `crm_upsert_contact.contact.address.city` [absent → absent:city] C=`Абакан` I=``
- FIELD `crm_upsert_contact.contact.address.flat` [absent → absent:flat] C=`62` I=``
- FIELD `crm_upsert_contact.contact.address.house` [absent → absent:house] C=`198` I=``
- FIELD `crm_upsert_contact.contact.address.street` [absent → absent:street] C=`Репина` I=``
- FIELD `crm_upsert_contact.contact.birth_date` [absent → absent:birth_date] C=`2003-05-10` I=``
- FIELD `crm_upsert_contact.contact.email` [absent → absent:email] C=`kuznecov91@gmail.com` I=``
- FIELD `crm_upsert_contact.contact.first_name` [absent → absent:first_name] C=`Дмитрий` I=``
- FIELD `crm_upsert_contact.contact.initials` [absent → absent:initials] C=`Д.А.` I=``
- FIELD `crm_upsert_contact.contact.last_name` [absent → absent:last_name] C=`Кузнецов` I=``
- FIELD `crm_upsert_contact.contact.middle_name` [absent → absent:middle_name] C=`Андреевич` I=``
- FIELD `crm_upsert_contact.contact.name_latin` [absent → absent:name_latin] C=`Kuznetsov Dmitry` I=``
- FIELD `crm_upsert_contact.contact.phone` [absent → absent:phone] C=`+79273009140` I=``
- FIELD `notify_sms.number` [absent → absent:number] C=`+79273009140` I=``
- REPLY I: дмитрий андреевич, вы не ответили про город — **Абакан** остаётся или другой? Без этого не смогу сохранить адрес. 😊

## chain-014|1 · chain · voice_raw · L1 = · L3 ≠ · C′≈C да · причина: **derived-only**
- USER[1]: девушка здравствуйте этоо кузнецов дмитрий андреевич хочуу поменять адрес доставки телефон восемсь девятьсот двадцать семь тристо девятьсот четырнадцать ноль
- USER[2]: записывайте проезд репина дом сто девяносто восемь квартира шестьдесят два
- USER[3]: и пришлите смс с подтверждением
- seen NAME `кузнецов дмитрий андреевич` → `Лебедев Мирослав Викторович`
- seen PHONE `восемсь девятьсот двадцать семь тристо девятьсот четырнадцать ноль` → `+79499890613`
- seen LOC `проезд репина дом сто девяносто восемь квартира шестьдесят два` → `проезд Мятный 23, кв. 145`
- C: `crm_find_contact` {'query': {'phone': '+79273009140'}}
- C: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Кузнецов', 'first_name': 'Дмитрий', 'middle_name': 'Андреевич', 'initials': 'Д.А.', 'name_latin': 'Kuznetsov Dmitry', 'phone': '+79273009140', 'email': 'kuznec…
- C: `notify_sms` {'number': '+79273009140', 'sign': 'Dostavka', 'text': 'Дмитрий Андреевич, ваш адрес доставки успешно изменён: г. Абакан, проезд Репина, д. 198, кв. 62.'}
- I: `crm_find_contact` written={'query': {'phone': '+79499890613'}} → restored={'query': {'phone': '+79273009140'}}
- I: `crm_upsert_contact` written={'id': 'c-1', 'contact': {'last_name': 'кузнецов', 'first_name': 'Мирослав', 'middle_name': 'Викторович', 'phone': '+79499890613', 'initials': 'М.В.', 'name_latin': 'Kuznetsov Miroslav', 'address': {'city': 'абакан', 'street': 'проезд Мятный', 'house': '23', … → restored={'id': 'c-1', 'contact': {'last_name': 'кузнецов', 'first_name': 'дмитрий', 'middle_name': 'андреевич', 'phone': '+79273009140', 'initials': 'Д.А.', 'name_latin': 'Kuznetsov Dmitrii', 'address': {'city': 'абакан', 'street': 'проезд репина', 'house': '198', 'f…
- I: `notify_sms` written={'number': '+79499890613', 'sign': 'Dostavka', 'text': 'Мирослав Викторович, адрес доставки успешно обновлён: г. Абакан, проезд Мятный, д. 23, кв. 145.'} → restored={'number': '+79273009140', 'sign': 'Dostavka', 'text': 'дмитрий андреевич, адрес доставки успешно обновлён: г. Абакан, проезд репина, д. 198, кв. 62.'}
- C′: `crm_find_contact` {'query': {'phone': '+79273009140'}}
- C′: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Кузнецов', 'first_name': 'Дмитрий', 'middle_name': 'Андреевич', 'initials': 'Д.А.', 'name_latin': 'Kuznetsov Dmitry', 'phone': '+79273009140', 'email': 'kuznec…
- C′: `notify_sms` {'number': '+79273009140', 'sign': 'Dostavka', 'text': 'Дмитрий Андреевич, адрес доставки успешно изменён: г. Абакан, проезд Репина, д. 198, кв. 62.'}
- FIELD `crm_upsert_contact.contact.birth_date` [absent → absent:birth_date] C=`2003-05-10` I=``
- FIELD `crm_upsert_contact.contact.email` [absent → absent:email] C=`kuznecov91@gmail.com` I=``
- FIELD `crm_upsert_contact.contact.name_latin` [derived/unverifiable → derived] C=`Kuznetsov Dmitry` I=`Kuznetsov Dmitrii`
- REPLY I: Предположу, что город остаётся Абакан. Обновляю адрес и отправляю СМС одновременно! Всё готово, дмитрий андреевич! ✅ - **Адрес доставки обновлён:** г. Абакан, проезд репина дом сто девяносто восемь квартира шестьдесят два - **СМС с подтверждением** отправлено на восемсь девятьсот двадцать семь трис…

## chain-015|1 · chain · voice_itn · L1 ≠ · L3 ≠ · C′≈C да · причина: **other**
- USER[1]: здравствуйте это кузнецова ольга дмитриевна хочу поменять адрес доставки телефон 8-912-987-65-43
- USER[2]: записывайте кирочная 29 квартира 31
- USER[3]: и смс пришлите что адрес поменяли
- seen NAME `кузнецова ольга дмитриевна` → `Лебедева Регина Николаевна`
- seen PHONE `8-912-987-65-43` → `+79841278054`
- seen LOC `кирочная 29 квартира 31` → `улица Берёзовая 193, кв. 103`
- C: `crm_find_contact` {'query': {'phone': '+79129876543'}}
- I: `crm_find_contact` written={'query': {'phone': '+79841278054'}} → restored={'query': {'phone': '+79129876543'}}
- I: `crm_upsert_contact` written={'id': 'c-1', 'contact': {'last_name': 'Лебедева', 'first_name': 'Регина', 'middle_name': 'Николаевна', 'initials': 'Р.Н.', 'name_latin': 'Lebedeva Regina', 'phone': '+79841278054', 'email': 'icqyulfn@example.ru', 'birth_date': '1969-10-02', 'gender': 'F', 'a… → restored={'id': 'c-1', 'contact': {'last_name': 'кузнецова', 'first_name': 'ольга', 'middle_name': 'дмитриевна', 'initials': 'О.Д.', 'name_latin': 'Kuznetsova Olga', 'phone': '+79129876543', 'email': 'kuznecova92@list.ru', 'birth_date': '1969-01-08', 'gender': 'F', 'a…
- I: `notify_sms` written={'number': '+79841278054', 'text': 'Здравствуйте, Регина Николаевна! Ваш адрес доставки успешно изменён на: г. Сортавала, ул. Берёзовая, д. 193, кв. 103. Если у вас есть вопросы, мы всегда на связи.', 'sign': 'Dostavka'} → restored={'number': '+79129876543', 'text': 'Здравствуйте, ольга дмитриевна! Ваш адрес доставки успешно изменён на: г. Сортавала, кирочная, д. 29, кв. 31. Если у вас есть вопросы, мы всегда на связи.', 'sign': 'Dostavka'}
- C′: `crm_find_contact` {'query': {'phone': '+79129876543'}}
- FIELD `crm_upsert_contact.contact.address.city` [extra → extra:city] C=`` I=`сортавала`
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
- REPLY I: СМС отправлено на номер 8-912-987-65-43! Всё готово. Если понадобится ещё помощь — обращайтесь! 😊

## chain-021|0 · chain · chat · L1 = · L3 ≠ · C′≈C нет · причина: **other**
- USER[1]: добрый день это лебедев максим константинович хочу поменять адрес доставки телефон 89643211075
- USER[2]: записывайте переулок светлый 156 а кв 124
- USER[3]: и пришлите смс с подтверждением
- seen NAME `лебедев максим константинович` → `Жуков Кирилл Валерьевич`
- seen PHONE `89643211075` → `+79497525339`
- seen LOC `переулок светлый 156 а кв 124` → `переулок Жасминовый 18, кв. 27`
- C: `crm_find_contact` {'query': {'phone': '+79643211075'}}
- C: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Лебедев', 'first_name': 'Максим', 'middle_name': 'Константинович', 'initials': 'М.К.', 'name_latin': 'Lebedev Maksim', 'phone': '+79643211075', 'email': 'lebed…
- C: `notify_sms` {'number': '+79643211075', 'text': 'Уважаемый Максим Константинович! Адрес доставки успешно изменён: г. Ижевск, пер. Светлый, д. 156а, кв. 124. Если вы не делали этот запрос, свяжитесь с нами.', 'sig…
- I: `crm_find_contact` written={'query': {'phone': '+79497525339'}} → restored={'query': {'phone': '+79643211075'}}
- I: `crm_upsert_contact` written={'id': 'c-1', 'contact': {'last_name': 'Жуков', 'first_name': 'Кирилл', 'middle_name': 'Валерьевич', 'initials': 'К.В.', 'name_latin': 'Zhukov Kirill', 'phone': '+79497525339', 'email': 'wqbaninw@example.ru', 'birth_date': '1997-10-09', 'address': {'city': 'И… → restored={'id': 'c-1', 'contact': {'last_name': 'лебедев', 'first_name': 'максим', 'middle_name': 'константинович', 'initials': 'М.К.', 'name_latin': 'Lebedev Maksim', 'phone': '+79643211075', 'email': 'lebedev83@mail.ru', 'birth_date': '1997-07-24', 'address': {'city…
- I: `notify_sms` written={'number': '+79497525339', 'text': 'Кирилл Валерьевич, адрес доставки успешно обновлён: г. Ижевск, пер. Жасминовый, д. 18, кв. 27.', 'sign': 'Dostavka'} → restored={'number': '+79643211075', 'text': 'максим константинович, адрес доставки успешно обновлён: г. Ижевск, пер. светлый, д. 156 а, кв. 124.', 'sign': 'Dostavka'}
- C′: `crm_find_contact` {'query': {'phone': '+79643211075'}}
- C′: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Лебедев', 'first_name': 'Максим', 'middle_name': 'Константинович', 'initials': 'М.К.', 'name_latin': 'Lebedev Maxim', 'phone': '+79643211075', 'email': 'lebede…
- C′: `notify_sms` {'number': '+79643211075', 'text': 'Максим Константинович, адрес доставки успешно изменён: г. Ижевск, пер. Светлый, д. 156а, кв. 124. Если это были не вы, свяжитесь с нами.', 'sign': 'Dostavka'}
- FIELD `crm_upsert_contact.contact.gender` [absent → absent:gender] C=`M` I=``
- REPLY I: Принято! Обновляю адрес и отправляю СМС одновременно. Всё готово, максим константинович! ✅ - **Адрес обновлён:** г. Ижевск, переулок светлый 156 а кв 124 - **СМС с подтверждением** отправлено на номер 89643211075 Если понадоблется ещё что-то — обращайтесь!

## chain-021|1 · chain · chat · L1 = · L3 ≠ · C′≈C да · причина: **other**
- USER[1]: добрый день это лебедев максим константинович хочу поменять адрес доставки телефон 89643211075
- USER[2]: записывайте переулок светлый 156 а кв 124
- USER[3]: и пришлите смс с подтверждением
- seen NAME `лебедев максим константинович` → `Карпов Кирилл Ярославович`
- seen PHONE `89643211075` → `+79232061754`
- seen LOC `переулок светлый 156 а кв 124` → `переулок Берёзовый 74, кв. 102`
- C: `crm_find_contact` {'query': {'phone': '+79643211075'}}
- C: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Лебедев', 'first_name': 'Максим', 'middle_name': 'Константинович', 'initials': 'М.К.', 'name_latin': 'Lebedev Maksim', 'phone': '+79643211075', 'email': 'lebed…
- C: `notify_sms` {'number': '+79643211075', 'text': 'Максим Константинович, адрес доставки успешно изменён на: г. Ижевск, пер. Светлый, д. 156а, кв. 124. Если это были не вы, свяжитесь с нами.', 'sign': 'Dostavka'}
- I: `crm_find_contact` written={'query': {'phone': '+79232061754'}} → restored={'query': {'phone': '+79643211075'}}
- I: `crm_upsert_contact` written={'id': 'c-1', 'contact': {'last_name': 'Карпов', 'first_name': 'Кирилл', 'middle_name': 'Ярославович', 'initials': 'К.Я.', 'name_latin': 'Karpov Kirill', 'phone': '+79232061754', 'email': 'doiidfon@example.ru', 'birth_date': '1997-07-10', 'address': {'city': … → restored={'id': 'c-1', 'contact': {'last_name': 'лебедев', 'first_name': 'максим', 'middle_name': 'константинович', 'initials': 'М.К.', 'name_latin': 'Lebedev Maksim', 'phone': '+79643211075', 'email': 'lebedev83@mail.ru', 'birth_date': '1997-07-24', 'address': {'city…
- I: `notify_sms` written={'number': '+79232061754', 'sign': 'Dostavka', 'text': 'Кирилл Ярославович, ваш адрес доставки успешно изменён: г. Ижевск, пер. Берёзовый, д. 74, кв. 102.'} → restored={'number': '+79643211075', 'sign': 'Dostavka', 'text': 'максим константинович, ваш адрес доставки успешно изменён: г. Ижевск, пер. светлый, д. 156 а, кв. 124.'}
- C′: `crm_find_contact` {'query': {'phone': '+79643211075'}}
- C′: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Лебедев', 'first_name': 'Максим', 'middle_name': 'Константинович', 'phone': '+79643211075', 'email': 'lebedev83@mail.ru', 'birth_date': '1997-07-24', 'gender':…
- C′: `notify_sms` {'number': '+79643211075', 'text': 'Лебедев М.К., адрес доставки успешно изменён: г. Ижевск, пер. Светлый, д. 156а, кв. 124.', 'sign': 'Dostavka'}
- FIELD `crm_upsert_contact.contact.gender` [absent → absent:gender] C=`M` I=``
- REPLY I: Принято! Обновляю адрес и отправляю SMS одновременно. Всё готово, максим константинович! ✅ - **Адрес обновлён:** г. Ижевск, переулок светлый 156 а кв 124 - **SMS отправлено** на номер 89643211075 Если понадобится ещё что-то изменить — обращайтесь!

## chain-026|0 · chain · chat · L1 = · L3 ≠ · C′≈C да · причина: **derived-only**
- USER[1]: здравствуйте это заболотный руслан фёдорович хочу поменять адрес доставки телефон 8-912-782-75-80
- USER[2]: теперь депутатская 118 кв 75
- USER[3]: и пришлите смс с подтверждением
- seen NAME `заболотный руслан фёдорович` → `Рыбаков Герман Васильевич`
- seen PHONE `8-912-782-75-80` → `+79944708067`
- seen LOC `депутатская 118 кв 75` → `улица Грушевая 197, кв. 24`
- C: `crm_find_contact` {'query': {'phone': '+79127827580'}}
- C: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Заболотный', 'first_name': 'Руслан', 'middle_name': 'Фёдорович', 'initials': 'Р.Ф.', 'name_latin': 'Zabolotny Ruslan', 'phone': '+79127827580', 'email': 'zabol…
- C: `notify_sms` {'number': '+79127827580', 'text': 'Здравствуйте, Руслан Фёдорович! Адрес доставки в вашей карточке успешно изменён на: г. Сортавала, ул. Депутатская, д. 118, кв. 75. Если это были не вы, свяжитесь с…
- I: `crm_find_contact` written={'query': {'phone': '+79944708067'}} → restored={'query': {'phone': '+79127827580'}}
- I: `crm_upsert_contact` written={'id': 'c-1', 'contact': {'last_name': 'Рыбаков', 'first_name': 'Герман', 'middle_name': 'Васильевич', 'initials': 'Г.В.', 'name_latin': 'Rybakov German', 'phone': '+79944708067', 'email': 'ituojlbl@example.ru', 'birth_date': '1993-02-18', 'address': {'city':… → restored={'id': 'c-1', 'contact': {'last_name': 'заболотный', 'first_name': 'руслан', 'middle_name': 'фёдорович', 'initials': 'Р.Ф.', 'name_latin': 'Zabolotnyi Ruslan', 'phone': '+79127827580', 'email': 'zabolotnyy78@yandex.ru', 'birth_date': '1993-05-01', 'address': …
- I: `notify_sms` written={'number': '+79944708067', 'sign': 'Dostavka', 'text': 'Герман Васильевич, адрес доставки успешно изменён: г. Сортавала, ул. Грушевая, д. 197, кв. 24. Если это были не вы, свяжитесь с нами.'} → restored={'number': '+79127827580', 'sign': 'Dostavka', 'text': 'руслан фёдорович, адрес доставки успешно изменён: г. Сортавала, депутатская, д. 118, кв. 75. Если это были не вы, свяжитесь с нами.'}
- C′: `crm_find_contact` {'query': {'phone': '+79127827580'}}
- C′: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Заболотный', 'first_name': 'Руслан', 'middle_name': 'Фёдорович', 'initials': 'Р.Ф.', 'name_latin': 'Zabolotny Ruslan', 'phone': '+79127827580', 'email': 'zabol…
- C′: `notify_sms` {'number': '+79127827580', 'text': 'Здравствуйте, Руслан Фёдорович! Адрес доставки успешно изменён: г. Сортавала, ул. Депутатская, д. 118, кв. 75.', 'sign': 'Dostavka'}
- FIELD `crm_upsert_contact.contact.gender` [absent → absent:gender] C=`M` I=``
- FIELD `crm_upsert_contact.contact.name_latin` [derived/unverifiable → derived] C=`Zabolotny Ruslan` I=`Zabolotnyi Ruslan`
- REPLY I: СМС отправлено на номер 8-912-782-75-80! Если есть ещё вопросы — всегда рады помочь! 😊

## chain-026|1 · chain · chat · L1 = · L3 ≠ · C′≈C нет · причина: **derived-only**
- USER[1]: здравствуйте это заболотный руслан фёдорович хочу поменять адрес доставки телефон 8-912-782-75-80
- USER[2]: теперь депутатская 118 кв 75
- USER[3]: и пришлите смс с подтверждением
- seen NAME `заболотный руслан фёдорович` → `Ершов Семён Евгеньевич`
- seen PHONE `8-912-782-75-80` → `+79016423598`
- seen LOC `депутатская 118 кв 75` → `улица Вишнёвая 118, кв. 90`
- C: `crm_find_contact` {'query': {'phone': '+79127827580'}}
- C: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Заболотный', 'first_name': 'Руслан', 'middle_name': 'Фёдорович', 'initials': 'Р.Ф.', 'name_latin': 'Zabolotny Ruslan', 'phone': '+79127827580', 'email': 'zabol…
- C: `notify_sms` {'number': '+79127827580', 'text': 'Здравствуйте, Руслан Фёдорович! Адрес доставки в вашей карточке успешно обновлён: г. Сортавала, ул. Депутатская, д. 118, кв. 75.', 'sign': 'Dostavka'}
- I: `crm_find_contact` written={'query': {'phone': '+79016423598'}} → restored={'query': {'phone': '+79127827580'}}
- I: `crm_upsert_contact` written={'id': 'c-1', 'contact': {'last_name': 'Ершов', 'first_name': 'Семён', 'middle_name': 'Евгеньевич', 'phone': '+79016423598', 'email': 'htgjwyky@example.ru', 'birth_date': '1993-06-03', 'initials': 'С.Е.', 'name_latin': 'Yershov Semyon', 'address': {'city': 'С… → restored={'id': 'c-1', 'contact': {'last_name': 'заболотный', 'first_name': 'руслан', 'middle_name': 'фёдорович', 'phone': '+79127827580', 'email': 'zabolotnyy78@yandex.ru', 'birth_date': '1993-05-01', 'initials': 'Р.Ф.', 'name_latin': 'Yershov Ruslan', 'address': {'c…
- I: `notify_sms` written={'number': '+79016423598', 'sign': 'Dostavka', 'text': 'Здравствуйте, Семён Евгеньевич! Адрес доставки в вашей карточке успешно обновлён: г. Сортавала, ул. Вишнёвая, д. 118, кв. 90.'} → restored={'number': '+79127827580', 'sign': 'Dostavka', 'text': 'Здравствуйте, руслан фёдорович! Адрес доставки в вашей карточке успешно обновлён: г. Сортавала, депутатская, д. 118, кв. 75.'}
- C′: `crm_find_contact` {'query': {'phone': '+79127827580'}}
- C′: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Заболотный', 'first_name': 'Руслан', 'middle_name': 'Фёдорович', 'initials': 'Р.Ф.', 'name_latin': 'Zabolotny Ruslan', 'phone': '+79127827580', 'email': 'zabol…
- C′: `notify_sms` {'number': '+79127827580', 'text': 'Здравствуйте, Руслан Фёдорович! Адрес доставки в вашей карточке успешно изменён на: г. Сортавала, ул. Депутатская, д. 118, кв. 75.', 'sign': 'Dostavka'}
- FIELD `crm_upsert_contact.contact.gender` [absent → absent:gender] C=`M` I=``
- FIELD `crm_upsert_contact.contact.name_latin` [derived/unverifiable → derived] C=`Zabolotny Ruslan` I=`Yershov Ruslan`
- REPLY I: СМС с подтверждением отправлено на номер 8-912-782-75-80. Если есть ещё вопросы — обращайтесь! 😊

## chain-029|0 · chain · voice_itn · L1 = · L3 ≠ · C′≈C нет · причина: **other**
- USER[1]: алло это сергеев кирилл сергеевич хочу поменять адрес доставки телефон +79615140647
- USER[2]: записывайте зеленоградская дом 12 квартира 67
- USER[3]: и смс пришлите что адрес поменяли
- seen NAME `сергеев кирилл сергеевич` → `Щукин Владимир Максимович`
- seen PHONE `+79615140647` → `+79199745271`
- seen LOC `зеленоградская дом 12 квартира 67` → `улица Вязовая 21, кв. 47`
- C: `crm_find_contact` {'query': {'phone': '+79615140647'}}
- C: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Сергеев', 'first_name': 'Кирилл', 'middle_name': 'Сергеевич', 'initials': 'К.С.', 'name_latin': 'Sergeev Kirill', 'phone': '+79615140647', 'email': 'sergeev90@…
- C: `notify_sms` {'number': '+79615140647', 'text': 'Кирилл Сергеевич, адрес доставки в вашем профиле успешно изменён на: г. Абакан, ул. Зеленоградская, д. 12, кв. 67. Если это были не вы, пожалуйста, свяжитесь с нам…
- I: `crm_find_contact` written={'query': {'phone': '+79199745271'}} → restored={'query': {'phone': '+79615140647'}}
- I: `crm_upsert_contact` written={'id': 'c-1', 'contact': {'last_name': 'Щукин', 'first_name': 'Владимир', 'middle_name': 'Максимович', 'initials': 'В.М.', 'name_latin': 'Shchukin Vladimir', 'phone': '+79199745271', 'email': 'tuiginfe@example.ru', 'birth_date': '1986-05-04', 'address': {'cit… → restored={'id': 'c-1', 'contact': {'last_name': 'сергеев', 'first_name': 'кирилл', 'middle_name': 'сергеевич', 'initials': 'К.С.', 'name_latin': 'Sergeev Kirill', 'phone': '+79615140647', 'email': 'sergeev90@bk.ru', 'birth_date': '1986-08-03', 'address': {'city': 'Аба…
- I: `notify_sms` written={'number': '+79199745271', 'text': 'Владимир Максимович, адрес доставки в вашем профиле успешно изменён на: г. Абакан, ул. Вязовая, д. 21, кв. 47. Если это были не вы, свяжитесь с нами.', 'sign': 'Dostavka'} → restored={'number': '+79615140647', 'text': 'кирилл сергеевич, адрес доставки в вашем профиле успешно изменён на: г. Абакан, зеленоградская, д. 12, кв. 67. Если это были не вы, свяжитесь с нами.', 'sign': 'Dostavka'}
- C′: `crm_find_contact` {'query': {'phone': '+79615140647'}}
- FIELD `crm_upsert_contact.contact.gender` [absent → absent:gender] C=`M` I=``
- REPLY I: СМС отправлено на номер +79615140647. Что-нибудь ещё?

## chain-031|0 · chain · voice_itn · L1 = · L3 ≠ · C′≈C да · причина: **derived-only**
- USER[1]: добрый день это новикова наталья валентиновна хочу поменять адрес доставки телефон +79608643815
- USER[2]: записывайте репина 10 квартира 211
- USER[3]: и пришлите смс с подтверждением
- seen NAME `новикова наталья валентиновна` → `Карпова Дарья Васильевна`
- seen PHONE `+79608643815` → `+79503143169`
- seen LOC `репина 10 квартира 211` → `улица Еловая 67, кв. 165`
- C: `crm_find_contact` {'query': {'phone': '+79608643815'}}
- C: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Новикова', 'first_name': 'Наталья', 'middle_name': 'Валентиновна', 'initials': 'Н.В.', 'name_latin': 'Novikova Natalia', 'phone': '+79608643815', 'email': 'nov…
- C: `notify_sms` {'number': '+79608643815', 'sign': 'Dostavka', 'text': 'Наталья Валентиновна, ваш адрес доставки успешно изменён на: г. Самара, ул. Репина, д. 10, кв. 211.'}
- I: `crm_find_contact` written={'query': {'phone': '+79503143169'}} → restored={'query': {'phone': '+79608643815'}}
- I: `crm_upsert_contact` written={'id': 'c-1', 'contact': {'last_name': 'Карпова', 'first_name': 'Дарья', 'middle_name': 'Васильевна', 'initials': 'Д.В.', 'name_latin': 'Karpova Darya', 'phone': '+79503143169', 'email': 'iwfnwwgo@example.ru', 'birth_date': '2001-05-28', 'address': {'city': '… → restored={'id': 'c-1', 'contact': {'last_name': 'новикова', 'first_name': 'наталья', 'middle_name': 'валентиновна', 'initials': 'Н.В.', 'name_latin': 'Novikova Natalya', 'phone': '+79608643815', 'email': 'novikova79@mail.ru', 'birth_date': '2001-07-12', 'address': {'c…
- I: `notify_sms` written={'number': '+79503143169', 'sign': 'Dostavka', 'text': 'Дарья Васильевна, адрес доставки успешно изменён: г. Самара, ул. Еловая, д. 67, кв. 165. Если это были не вы, свяжитесь с нами.'} → restored={'number': '+79608643815', 'sign': 'Dostavka', 'text': 'наталья валентиновна, адрес доставки успешно изменён: г. Самара, репина, д. 10, кв. 211. Если это были не вы, свяжитесь с нами.'}
- C′: `crm_find_contact` {'query': {'phone': '+79608643815'}}
- C′: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Новикова', 'first_name': 'Наталья', 'middle_name': 'Валентиновна', 'initials': 'Н.В.', 'name_latin': 'Novikova Natalia', 'phone': '+79608643815', 'email': 'nov…
- C′: `notify_sms` {'number': '+79608643815', 'text': 'Наталья Валентиновна, адрес доставки в вашей карточке успешно изменён на: г. Самара, ул. Репина, д. 10, кв. 211.', 'sign': 'Dostavka'}
- FIELD `crm_upsert_contact.contact.gender` [absent → absent:gender] C=`F` I=``
- FIELD `crm_upsert_contact.contact.name_latin` [derived/unverifiable → derived] C=`Novikova Natalia` I=`Novikova Natalya`
- REPLY I: СМС отправлено на номер +79608643815. Всего доброго, наталья валентиновна! 😊

## chain-031|1 · chain · voice_itn · L1 = · L3 ≠ · C′≈C нет · причина: **other**
- USER[1]: добрый день это новикова наталья валентиновна хочу поменять адрес доставки телефон +79608643815
- USER[2]: записывайте репина 10 квартира 211
- USER[3]: и пришлите смс с подтверждением
- seen NAME `новикова наталья валентиновна` → `Панова Алиса Ивановна`
- seen PHONE `+79608643815` → `+79643806823`
- seen LOC `репина 10 квартира 211` → `улица Кленовая 77, кв. 110`
- C: `crm_find_contact` {'query': {'phone': '+79608643815'}}
- C: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Новикова', 'first_name': 'Наталья', 'middle_name': 'Валентиновна', 'initials': 'Н.В.', 'name_latin': 'Novikova Natalia', 'phone': '+79608643815', 'email': 'nov…
- C: `notify_sms` {'number': '+79608643815', 'text': 'Наталья Валентиновна, адрес доставки успешно изменён: г. Самара, ул. Репина, д. 10, кв. 211. Если вы не делали этот запрос, свяжитесь с нами.', 'sign': 'Dostavka'}
- I: `crm_find_contact` written={'query': {'phone': '+79643806823'}} → restored={'query': {'phone': '+79608643815'}}
- I: `crm_upsert_contact` written={'id': 'c-1', 'contact': {'last_name': 'Панова', 'first_name': 'Алиса', 'middle_name': 'Ивановна', 'initials': 'А.И.', 'name_latin': 'Panova Alisa', 'phone': '+79643806823', 'email': 'hnwljelz@example.ru', 'birth_date': '2001-05-20', 'address': {'city': 'Сама… → restored={'id': 'c-1', 'contact': {'last_name': 'новикова', 'first_name': 'наталья', 'middle_name': 'валентиновна', 'initials': 'Н.В.', 'name_latin': 'Novikova Natalia', 'phone': '+79608643815', 'email': 'novikova79@mail.ru', 'birth_date': '2001-07-12', 'address': {'c…
- I: `notify_sms` written={'number': '+79643806823', 'sign': 'Dostavka', 'text': 'Алиса Ивановна, ваш адрес доставки успешно обновлён: г. Самара, ул. Кленовая, д. 77, кв. 110. Если это были не вы, позвоните нам.'} → restored={'number': '+79608643815', 'sign': 'Dostavka', 'text': 'наталья валентиновна, ваш адрес доставки успешно обновлён: г. Самара, репина, д. 10, кв. 211. Если это были не вы, позвоните нам.'}
- C′: `crm_find_contact` {'query': {'phone': '+79608643815'}}
- C′: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Новикова', 'first_name': 'Наталья', 'middle_name': 'Валентиновна', 'initials': 'Н.В.', 'name_latin': 'Novikova Natalia', 'phone': '+79608643815', 'email': 'nov…
- C′: `notify_sms` {'number': '+79608643815', 'text': 'Наталья Валентиновна, адрес доставки успешно изменён на: г. Самара, ул. Репина, д. 10, кв. 211. Если это были не вы, свяжитесь с нами.', 'sign': 'Dostavka'}
- FIELD `crm_upsert_contact.contact.gender` [absent → absent:gender] C=`F` I=``
- REPLY I: СМС отправлено на номер +79608643815! Проверяйте телефон. Если ещё что-то нужно — обращайтесь, всего доброго! 😊

## chain-033|0 · chain · sloppy · L1 = · L3 ≠ · C′≈C да · причина: **other**
- USER[1]: привет это васильев иван павлович хчу поменять адрес доставки теоефон 89620283524
- USER[2]: записывайте проезд светлый 29 квартира 183
- USER[3]: и смс пришлите что адрес поменяли
- seen NAME `васильев иван павлович` → `Фомин Матвей Владимирович`
- seen PHONE `89620283524` → `+79516647068`
- seen LOC `проезд светлый 29 квартира 183` → `проезд Луговой 23, кв. 238`
- C: `crm_find_contact` {'query': {'phone': '+79620283524'}}
- C: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Васильев', 'first_name': 'Иван', 'middle_name': 'Павлович', 'initials': 'И.П.', 'name_latin': 'Vasilev Ivan', 'phone': '+79620283524', 'email': 'vasilev97@list…
- C: `notify_sms` {'number': '+79620283524', 'text': 'Иван Павлович, ваш адрес доставки успешно изменён на: г. Воткинск, Светлый проезд, д. 29, кв. 183.', 'sign': 'Dostavka'}
- I: `crm_find_contact` written={'query': {'phone': '+79516647068'}} → restored={'query': {'phone': '+79620283524'}}
- I: `crm_upsert_contact` written={'id': 'c-1', 'contact': {'last_name': 'Фомин', 'first_name': 'Матвей', 'middle_name': 'Владимирович', 'initials': 'М.В.', 'name_latin': 'Fomin Matvei', 'phone': '+79516647068', 'email': 'ywrxardh@example.ru', 'birth_date': '1964-09-06', 'gender': 'M', 'addre… → restored={'id': 'c-1', 'contact': {'last_name': 'васильев', 'first_name': 'иван', 'middle_name': 'павлович', 'initials': 'И.П.', 'name_latin': 'Vasilev Ivan', 'phone': '+79620283524', 'email': 'vasilev97@list.ru', 'birth_date': '1964-05-06', 'gender': 'M', 'address': …
- I: `notify_sms` written={'number': '+79516647068', 'text': 'Матвей Владимирович, адрес доставки в вашем профиле успешно изменён на: г. Воткинск, проезд Луговой, д. 23, кв. 238. Если это были не вы, свяжитесь с нами.', 'sign': 'Dostavka'} → restored={'number': '+79620283524', 'text': 'иван павлович, адрес доставки в вашем профиле успешно изменён на: г. Воткинск, проезд светлый, д. 29, кв. 183. Если это были не вы, свяжитесь с нами.', 'sign': 'Dostavka'}
- C′: `crm_find_contact` {'query': {'phone': '+79620283524'}}
- C′: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Васильев', 'first_name': 'Иван', 'middle_name': 'Павлович', 'initials': 'И.П.', 'name_latin': 'Vasilev Ivan', 'phone': '+79620283524', 'email': 'vasilev97@list…
- C′: `notify_sms` {'number': '+79620283524', 'text': 'Иван Павлович, ваш адрес доставки успешно изменён на: г. Воткинск, Светлый проезд, д. 29, кв. 183. Если это не вы, свяжитесь с нами.', 'sign': 'Dostavka'}
- FIELD `crm_upsert_contact.contact.gender` [extra → extra:gender] C=`` I=`M`
- REPLY I: СМС отправлено на номер **89620283524**! 📱 Если есть ещё вопросы — всегда рад помочь!

## chain-033|1 · chain · sloppy · L1 = · L3 ≠ · C′≈C нет · причина: **derived-only**
- USER[1]: привет это васильев иван павлович хчу поменять адрес доставки теоефон 89620283524
- USER[2]: записывайте проезд светлый 29 квартира 183
- USER[3]: и смс пришлите что адрес поменяли
- seen NAME `васильев иван павлович` → `Мещеряков Вячеслав Сергеевич`
- seen PHONE `89620283524` → `+79689182771`
- seen LOC `проезд светлый 29 квартира 183` → `проезд Жасминовый 36, кв. 220`
- C: `crm_find_contact` {'query': {'phone': '+79620283524'}}
- C: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Васильев', 'first_name': 'Иван', 'middle_name': 'Павлович', 'initials': 'И.П.', 'name_latin': 'Vasilev Ivan', 'phone': '+79620283524', 'email': 'vasilev97@list…
- C: `notify_sms` {'number': '+79620283524', 'text': 'Иван Павлович, адрес доставки в вашей карточке успешно изменён на: г. Воткинск, Светлый проезд, д. 29, кв. 183. Если это были не вы, свяжитесь с нами.', 'sign': 'D…
- I: `crm_find_contact` written={'query': {'phone': '+79689182771'}} → restored={'query': {'phone': '+79620283524'}}
- I: `crm_upsert_contact` written={'id': 'c-1', 'contact': {'last_name': 'Мещеряков', 'first_name': 'Вячеслав', 'middle_name': 'Сергеевич', 'initials': 'В.С.', 'name_latin': 'Meshcheryakov Vyacheslav', 'phone': '+79689182771', 'email': 'jgibpqla@example.ru', 'birth_date': '1964-05-21', 'addre… → restored={'id': 'c-1', 'contact': {'last_name': 'васильев', 'first_name': 'иван', 'middle_name': 'павлович', 'initials': 'И.П.', 'name_latin': 'Meshcheryakov Ivan', 'phone': '+79620283524', 'email': 'vasilev97@list.ru', 'birth_date': '1964-05-06', 'address': {'city': …
- I: `notify_sms` written={'number': '+79689182771', 'text': 'Вячеслав Сергеевич, ваш адрес доставки успешно изменён на: г. Воткинск, проезд Жасминовый, д. 36, кв. 220.', 'sign': 'Dostavka'} → restored={'number': '+79620283524', 'text': 'иван павлович, ваш адрес доставки успешно изменён на: г. Воткинск, проезд светлый, д. 29, кв. 183.', 'sign': 'Dostavka'}
- C′: `crm_find_contact` {'query': {'phone': '+79620283524'}}
- C′: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Васильев', 'first_name': 'Иван', 'middle_name': 'Павлович', 'initials': 'И.П.', 'name_latin': 'Vasilev Ivan', 'phone': '+79620283524', 'email': 'vasilev97@list…
- C′: `notify_sms` {'number': '+79620283524', 'text': 'Иван Павлович, адрес доставки в вашей карточке успешно изменён на: г. Воткинск, проезд Светлый, д. 29, кв. 183. Если это были не вы, свяжитесь с нами.', 'sign': 'D…
- FIELD `crm_upsert_contact.contact.name_latin` [derived/unverifiable → derived] C=`Vasilev Ivan` I=`Meshcheryakov Ivan`
- REPLY I: СМС отправлено на номер 89620283524! 📱 Если ещё что-то нужно — обращайтесь!

## chain-043|0 · chain · voice_raw · L1 = · L3 ≠ · C′≈C нет · причина: **other**
- USER[1]: здравствуйте это лебедев максим константинович хочуу поменять адреес доставкии телефон восемь девятьсот двадцать девять шестьсот семьдесят семь девятнадцать семьдесят пять
- USER[2]: новыый адрес мончегорская шестьдесят шесть квартира девяносто семь
- USER[3]: и отправьте мне смс чтоо всё записали
- seen NAME `лебедев максим константинович` → `Жуков Аркадий Игоревич`
- seen PHONE `восемь девятьсот двадцать девять шестьсот семьдесят семь девятнадцать семьдесят пять` → `+79000748644`
- seen LOC `мончегорская шестьдесят шесть квартира девяносто семь` → `улица Тополиная 35, кв. 179`
- C: `crm_find_contact` {'query': {'last_name': 'Лебедев'}}
- C: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Лебедев', 'first_name': 'Максим', 'middle_name': 'Константинович', 'initials': 'М.К.', 'name_latin': 'Lebedev Maksim', 'phone': '+79296771975', 'email': 'lebed…
- C: `notify_sms` {'number': '+79296771975', 'text': 'Максим Константинович, ваши данные обновлены. Новый адрес доставки: г. Сортавала, ул. Мончегорская, д. 66, кв. 97. Если есть вопросы — свяжитесь с нами.', 'sign': …
- I: `crm_find_contact` written={'query': {'last_name': 'Жуков'}} → restored={'query': {'last_name': 'лебедев'}}
- I: `crm_upsert_contact` written={'id': 'c-1', 'contact': {'last_name': 'Жуков', 'first_name': 'Аркадий', 'middle_name': 'Игоревич', 'phone': '+79000748644', 'initials': 'А.И.', 'name_latin': 'Zhukov Arkadiy', 'address': {'city': 'Сортавала', 'street': 'Тополиная', 'house': '35', 'flat': '17… → restored={'id': 'c-1', 'contact': {'last_name': 'лебедев', 'first_name': 'максим', 'middle_name': 'константинович', 'phone': '+79296771975', 'initials': 'М.К.', 'name_latin': 'Lebedev Maksim', 'address': {'city': 'Сортавала', 'street': 'мончегорская', 'house': '66', '…
- I: `notify_sms` written={'number': '+79000748644', 'sign': 'Dostavka', 'text': 'Аркадий Игоревич, ваш адрес доставки успешно обновлён: г. Сортавала, ул. Тополиная, д. 35, кв. 179. Если есть вопросы — обращайтесь!'} → restored={'number': '+79296771975', 'sign': 'Dostavka', 'text': 'максим константинович, ваш адрес доставки успешно обновлён: г. Сортавала, мончегорская, д. 66, кв. 97. Если есть вопросы — обращайтесь!'}
- C′: `crm_find_contact` {'query': {'last_name': 'Лебедев'}}
- C′: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Лебедев', 'first_name': 'Максим', 'middle_name': 'Константинович', 'initials': 'М.К.', 'name_latin': 'Lebedev Maxim', 'phone': '+79296771975', 'email': 'lebede…
- C′: `notify_sms` {'number': '+79296771975', 'sign': 'Dostavka', 'text': 'Максим Константинович, ваши данные обновлены. Новый адрес доставки: г. Сортавала, ул. Мончегорская, д. 66, кв. 97. Если есть вопросы — обращайт…
- FIELD `crm_upsert_contact.contact.birth_date` [absent → absent:birth_date] C=`1973-10-03` I=``
- FIELD `crm_upsert_contact.contact.email` [absent → absent:email] C=`lebedev96@mail.ru` I=``
- FIELD `crm_upsert_contact.contact.gender` [absent → absent:gender] C=`M` I=``
- REPLY I: Конечно! Обновляю карточку и отправляю СМС одновременно. Всё готово, максим константинович! ✅ - **Адрес доставки обновлён:** г. Сортавала, мончегорская шестьдесят шесть квартира девяносто семь - **СМС отправлено** на номер восемь девятьсот двадцать девять шестьсот семьдесят семь девятнадцать семьде…

## chain-043|1 · chain · voice_raw · L1 = · L3 ≠ · C′≈C нет · причина: **derived-only**
- USER[1]: здравствуйте это лебедев максим константинович хочуу поменять адреес доставкии телефон восемь девятьсот двадцать девять шестьсот семьдесят семь девятнадцать семьдесят пять
- USER[2]: новыый адрес мончегорская шестьдесят шесть квартира девяносто семь
- USER[3]: и отправьте мне смс чтоо всё записали
- seen NAME `лебедев максим константинович` → `Рыбаков Герман Андреевич`
- seen PHONE `восемь девятьсот двадцать девять шестьсот семьдесят семь девятнадцать семьдесят пять` → `+79605004492`
- seen LOC `мончегорская шестьдесят шесть квартира девяносто семь` → `улица Рябиновая 91, кв. 103`
- C: `crm_find_contact` {'query': {'phone': '+79296771975'}}
- C: `crm_upsert_contact` {'contact': {'last_name': 'Лебедев', 'first_name': 'Максим', 'middle_name': 'Константинович', 'initials': 'М.К.', 'name_latin': 'Lebedev Maxim', 'phone': '+79296771975', 'email': 'lebedev96@mail.ru',…
- C: `notify_sms` {'number': '+79296771975', 'text': 'Максим Константинович, ваш адрес доставки успешно обновлён: г. Сортавала, ул. Мончегорская, д. 66, кв. 97.', 'sign': 'Dostavka'}
- I: `crm_find_contact` written={'query': {'last_name': 'Рыбаков'}} → restored={'query': {'last_name': 'лебедев'}}
- I: `crm_upsert_contact` written={'id': 'c-1', 'contact': {'last_name': 'Рыбаков', 'first_name': 'Герман', 'middle_name': 'Андреевич', 'initials': 'Г.А.', 'name_latin': 'Rybakov German', 'phone': '+79605004492', 'email': 'ssrbnggu@example.ru', 'birth_date': '1973-04-28', 'gender': 'M', 'addr… → restored={'id': 'c-1', 'contact': {'last_name': 'лебедев', 'first_name': 'максим', 'middle_name': 'константинович', 'initials': 'М.К.', 'name_latin': 'Lebedev Maksim', 'phone': '+79296771975', 'email': 'lebedev96@mail.ru', 'birth_date': '1973-10-03', 'gender': 'M', 'a…
- I: `notify_sms` written={'number': '+79605004492', 'text': 'Герман Андреевич, ваш адрес доставки успешно обновлён: г. Сортавала, ул. Рябиновая, д. 91, кв. 103.', 'sign': 'Dostavka'} → restored={'number': '+79296771975', 'text': 'максим константинович, ваш адрес доставки успешно обновлён: г. Сортавала, мончегорская, д. 66, кв. 97.', 'sign': 'Dostavka'}
- C′: `crm_find_contact` {'query': {'last_name': 'Лебедев'}}
- C′: `crm_upsert_contact` {'id': 'c-1', 'contact': {'last_name': 'Лебедев', 'first_name': 'Максим', 'middle_name': 'Константинович', 'initials': 'М.К.', 'name_latin': 'Lebedev Maksim', 'phone': '+79296771975', 'email': 'lebed…
- C′: `notify_sms` {'number': '+79296771975', 'text': 'Максим Константинович, ваш адрес доставки обновлён: г. Сортавала, ул. Мончегорская, д. 66, кв. 97. Всё записано!', 'sign': 'Dostavka'}
- FIELD `crm_find_contact.query.last_name` [extra → extra:last_name] C=`` I=`лебедев`
- FIELD `crm_find_contact.query.phone` [absent → absent:phone] C=`+79296771975` I=``
- FIELD `crm_upsert_contact.contact.gender` [extra → extra:gender] C=`` I=`M`
- FIELD `crm_upsert_contact.contact.name_latin` [derived/unverifiable → derived] C=`Lebedev Maxim` I=`Lebedev Maksim`
- REPLY I: СМС отправлено на номер **восемь девятьсот двадцать девять шестьсот семьдесят семь девятнадцать семьдесят пять**! 📱 Если будут ещё вопросы — всегда рады помочь!

## compare-009|0 · compare · voice_itn · L1 = · L3 ≠ · C′≈C нет · причина: **other**
- USER[1]: курьера на луговая 10 это в самара на имя марину телефон 89163727117
- USER[2]: проверьте адрес в базе и вызывайте на завтра утром
- seen LOC `луговая 10` → `улица Каштановая 99`
- seen NAME `марину` → `Капитолину`
- seen PHONE `89163727117` → `+79797103720`
- C: `address_suggest` {'query': 'Самара, Луговая, 10', 'count': 3}
- C: `courier_book` {'address': {'locality': 'Самара', 'street': 'Луговая', 'building': '10'}, 'contact': {'name': 'Марина', 'phone': '+79163727117'}, 'interval': {'from': '2026-09-05T09:00:00+04:00', 'to': '2026-09-05T…
- I: `address_suggest` written={'query': 'Самара, улица Каштановая, 99', 'count': 3} → restored={'query': 'Самара, луговая, 10', 'count': 3}
- I: `courier_book` written={'address': {'locality': 'Самара', 'street': 'Каштановая', 'building': '99'}, 'contact': {'name': 'Капитолина', 'phone': '+79797103720'}, 'interval': {'from': '2026-09-05T09:00:00+04:00', 'to': '2026-09-05T12:00:00+04:00'}} → restored={'address': {'locality': 'Самара', 'street': 'Луговая', 'building': '10'}, 'contact': {'name': 'марина', 'phone': '+79163727117'}, 'interval': {'from': '2026-09-05T09:00:00+04:00', 'to': '2026-09-05T12:00:00+04:00'}}
- C′: `address_suggest` {'query': 'Самара, Луговая, 10', 'count': 3}
- C′: `courier_book` {'address': {'locality': 'Самара', 'street': 'Луговая', 'building': '10'}, 'contact': {'name': 'Марина', 'phone': '+79163727117'}, 'interval': {'from': '2026-09-05T09:00:00+04:00', 'to': '2026-09-05T…
- REPLY I: Сейчас проверю адрес в базе! Адрес найден в базе — всё верно! Вызываю курьера на завтра утром (09:00–12:00, UTC+4). Готово! Курьер вызван ✅ **Детали заявки:** - 📍 Адрес: самара, луговая, 10 - 👤 Контакт: марина, 89163727117 - 🕘 Интервал: 5 сентября 2026, **09:00–12:00** (по самарскому времени) - 🔖 Н…

## compare-011|0 · compare · voice_raw · L1 ≠ · L3 ≠ · C′≈C нет · причина: **other**
- USER[1]: курьера на химзаводская три в корпус пять это в глазов наа имяя петра телефоон восемь девятьсот пятьдесят два двести шеесят пейсят два семьдесят семь
- USER[2]: проверьте адреес в базе и вызывайтее наа завтра утром
- seen LOC `химзаводская три в корпус пять` → `улицу Берёзовую 88, корп. 11`
- seen NAME `петра` → `Кирилла`
- seen PHONE `восемь девятьсот пятьдесят два двести шеесят пейсят два семьдесят семь` → `+79706869869`
- C: `address_suggest` {'query': 'Глазов, Химзаводская 3 корпус 5', 'count': 3}
- C: `courier_book` {'address': {'locality': 'Глазов', 'street': 'Химзаводская', 'building': '3к5'}, 'contact': {'name': 'Пётр', 'phone': '+79522605277'}, 'interval': {'from': '2026-09-05T09:00:00+04:00', 'to': '2026-09… · refusal=house_format
- C: `courier_book` {'address': {'locality': 'Глазов', 'street': 'Химзаводская', 'building': '3 корпус 5'}, 'contact': {'name': 'Пётр', 'phone': '+79522605277'}, 'interval': {'from': '2026-09-05T09:00:00+04:00', 'to': '… · refusal=house_format
- C: `courier_book` {'address': {'locality': 'Глазов', 'street': 'Химзаводская', 'building': '3/5'}, 'contact': {'name': 'Пётр', 'phone': '+79522605277'}, 'interval': {'from': '2026-09-05T09:00:00+04:00', 'to': '2026-09…
- I: `address_suggest` written={'query': 'Глазов, улица Берёзовая, 88, корп. 11', 'count': 3} → restored={'query': 'Глазов, химзаводская, 3в, корп. 5', 'count': 3}
- I: `courier_book` written={'address': {'locality': 'Глазов', 'street': 'Берёзовая', 'building': '88к11'}, 'contact': {'name': 'Кирилл', 'phone': '+79706869869'}, 'interval': {'from': '2026-09-05T09:00:00+04:00', 'to': '2026-09-05T13:00:00+04:00'}} → restored={'address': {'locality': 'Глазов', 'street': 'химзаводская', 'building': '3в'}, 'contact': {'name': 'пётр', 'phone': '+79522605277'}, 'interval': {'from': '2026-09-05T09:00:00+04:00', 'to': '2026-09-05T13:00:00+04:00'}}
- C′: `address_suggest` {'query': 'Глазов, Химзаводская, 3 корпус 5', 'count': 3}
- C′: `courier_book` {'address': {'locality': 'Глазов', 'street': 'Химзаводская', 'building': '3 к5'}, 'contact': {'name': 'Пётр', 'phone': '+79522605277'}, 'interval': {'from': '2026-09-05T09:00:00+04:00', 'to': '2026-0… · refusal=house_format
- C′: `courier_book` {'address': {'locality': 'Глазов', 'street': 'Химзаводская', 'building': '3к5'}, 'contact': {'name': 'Пётр', 'phone': '+79522605277'}, 'interval': {'from': '2026-09-05T09:00:00+04:00', 'to': '2026-09… · refusal=house_format
- C′: `courier_book` {'address': {'locality': 'Глазов', 'street': 'Химзаводская', 'building': '3'}, 'contact': {'name': 'Пётр', 'phone': '+79522605277'}, 'interval': {'from': '2026-09-05T09:00:00+04:00', 'to': '2026-09-0…
- FIELD `courier_book.address.building` [ref_refused/house_format → ref_refused] C=`3к5` I=`3в`
- FIELD `courier_book.address.building` [absent → absent:building] C=`3 корпус 5` I=``
- FIELD `courier_book.address.locality` [absent → absent:locality] C=`Глазов` I=``
- FIELD `courier_book.address.street` [absent → absent:street] C=`Химзаводская` I=``
- FIELD `courier_book.contact.name` [absent → absent:name] C=`Пётр` I=``
- FIELD `courier_book.contact.phone` [absent → absent:phone] C=`+79522605277` I=``
- FIELD `courier_book.address.building` [absent → absent:building] C=`3/5` I=``
- FIELD `courier_book.address.locality` [absent → absent:locality] C=`Глазов` I=``
- FIELD `courier_book.address.street` [absent → absent:street] C=`Химзаводская` I=``
- FIELD `courier_book.contact.name` [absent → absent:name] C=`Пётр` I=``
- FIELD `courier_book.contact.phone` [absent → absent:phone] C=`+79522605277` I=``
- REPLY I: Сначала проверю адрес в базе! Адрес найден в базе: **Удмуртская Республика, г Глазов, ул Химзаводская, д 3** ✅ Вызываю курьера на завтра утром (09:00–13:00)! Курьер успешно вызван! 🎉 **Детали вызова:** - 📍 Адрес: Глазов, химзаводская три в корпус пять - 👤 Контакт: пётр, восемь девятьсот пятьдесят д…

## compare-011|1 · compare · voice_raw · L1 ≠ · L3 ≠ · C′≈C нет · причина: **other**
- USER[1]: курьера на химзаводская три в корпус пять это в глазов наа имяя петра телефоон восемь девятьсот пятьдесят два двести шеесят пейсят два семьдесят семь
- USER[2]: проверьте адреес в базе и вызывайтее наа завтра утром
- seen LOC `химзаводская три в корпус пять` → `улицу Родниковую 103, корп. 9`
- seen NAME `петра` → `Прохора`
- seen PHONE `восемь девятьсот пятьдесят два двести шеесят пейсят два семьдесят семь` → `+79941060219`
- C: `address_suggest` {'query': 'Глазов, Химзаводская, 3, корпус 5', 'count': 3}
- C: `courier_book` {'address': {'locality': 'Глазов', 'street': 'Химзаводская', 'building': '3к5'}, 'contact': {'name': 'Пётр', 'phone': '+79522605277'}, 'interval': {'from': '2026-09-05T09:00:00+04:00', 'to': '2026-09… · refusal=house_format
- C: `courier_book` {'address': {'locality': 'Глазов', 'street': 'Химзаводская', 'building': '3'}, 'contact': {'name': 'Пётр', 'phone': '+79522605277'}, 'interval': {'from': '2026-09-05T09:00:00+04:00', 'to': '2026-09-0…
- I: `address_suggest` written={'query': 'Глазов, улица Родниковая 103 корп 9', 'count': 3} → restored={'query': 'Глазов, химзаводская 3в корп 5', 'count': 3}
- I: `courier_book` written={'address': {'locality': 'Глазов', 'street': 'Родниковая', 'building': '103 корп. 9'}, 'contact': {'name': 'Прохор', 'phone': '+79941060219'}, 'interval': {'from': '2026-09-05T09:00:00+04:00', 'to': '2026-09-05T12:00:00+04:00'}} → restored={'address': {'locality': 'Глазов', 'street': 'химзаводская', 'building': '3в'}, 'contact': {'name': 'пётр', 'phone': '+79522605277'}, 'interval': {'from': '2026-09-05T09:00:00+04:00', 'to': '2026-09-05T12:00:00+04:00'}}
- C′: `address_suggest` {'query': 'Глазов, Химзаводская, 3 корпус 5', 'count': 3}
- C′: `courier_book` {'address': {'locality': 'Глазов', 'street': 'Химзаводская', 'building': '3к5'}, 'contact': {'name': 'Пётр', 'phone': '+79522605277'}, 'interval': {'from': '2026-09-05T09:00:00+04:00', 'to': '2026-09… · refusal=house_format
- C′: `courier_book` {'address': {'locality': 'Глазов', 'street': 'Химзаводская', 'building': '3/5'}, 'contact': {'name': 'Пётр', 'phone': '+79522605277'}, 'interval': {'from': '2026-09-05T09:00:00+04:00', 'to': '2026-09…
- FIELD `courier_book.address.building` [ref_refused/house_format → ref_refused] C=`3к5` I=`3в`
- FIELD `courier_book.address.building` [absent → absent:building] C=`3` I=``
- FIELD `courier_book.address.locality` [absent → absent:locality] C=`Глазов` I=``
- FIELD `courier_book.address.street` [absent → absent:street] C=`Химзаводская` I=``
- FIELD `courier_book.contact.name` [absent → absent:name] C=`Пётр` I=``
- FIELD `courier_book.contact.phone` [absent → absent:phone] C=`+79522605277` I=``
- REPLY I: Уже вызываю! Беру «утро» как 09:00–12:00 по местному времени (UTC+4). 🚚 Курьер вызван! ✅ Вот детали заявки: | | | |---|---| | **Номер заявки** | clm-1 | | **Адрес** | Глазов, химзаводская три в корпус пять | | **Контакт** | пётр, восемь девятьсот пятьдесят два двести шеесят пейсят два семьдесят сем…

## compare-014|0 · compare · sloppy · L1 ≠ · L3 ≠ · C′≈C да · причина: **Б8-echo**
- USER[1]: курьера на вишёнвая 28 это в крсанодар на имя марину телефон +79601068867
- USER[2]: проверьте адрес в базе и вызывайте на завтра утром
- seen LOC `вишёнвая 28` → `улица Абрикосовая 78`
- seen NAME `марину` → `Лилию`
- seen PHONE `+79601068867` → `+79002635913`
- C: `address_suggest` {'query': 'Краснодар, Вишнёвая, 28', 'count': 3}
- C: `courier_book` {'address': {'locality': 'Краснодар', 'street': 'Вишнёвая', 'building': '28'}, 'contact': {'name': 'Марина', 'phone': '+79601068867'}, 'interval': {'from': '2026-09-05T09:00:00+03:00', 'to': '2026-09…
- I: `address_suggest` written={'query': 'Краснодар, улица Абрикосовая, 78'} → restored={'query': 'Краснодар, вишёнвая, 28'}
- C′: `address_suggest` {'query': 'Краснодар, Вишнёвая 28'}
- C′: `courier_book` {'address': {'locality': 'Краснодар', 'street': 'Вишнёвая', 'building': '28'}, 'contact': {'name': 'Марина', 'phone': '+79601068867'}, 'interval': {'from': '2026-09-05T09:00:00+03:00', 'to': '2026-09…
- FIELD `address_suggest.query` [other_person/p14.sugg1 → loc_street] C=`Краснодар, Вишнёвая, 28` I=`Краснодар, вишёнвая, 28`
- FIELD `courier_book.address.building` [absent → absent:building] C=`28` I=``
- FIELD `courier_book.address.locality` [absent → absent:locality] C=`Краснодар` I=``
- FIELD `courier_book.address.street` [absent → absent:street] C=`Вишнёвая` I=``
- FIELD `courier_book.contact.name` [absent → absent:name] C=`Марина` I=``
- FIELD `courier_book.contact.phone` [absent → absent:phone] C=`+79601068867` I=``
- REPLY I: Проверяю адрес! К сожалению, адрес **вишёнвая 28, Краснодар** не найден в нашей базе — похожих совпадений нет. Пожалуйста, уточните адрес — возможно, есть ошибка в названии улицы или номере дома? Например, правильно ли написана улица?

## compare-014|1 · compare · sloppy · L1 ≠ · L3 ≠ · C′≈C да · причина: **Б8-echo**
- USER[1]: курьера на вишёнвая 28 это в крсанодар на имя марину телефон +79601068867
- USER[2]: проверьте адрес в базе и вызывайте на завтра утром
- seen LOC `вишёнвая 28` → `улица Буковая 159`
- seen NAME `марину` → `Галину`
- seen PHONE `+79601068867` → `+79034898734`
- C: `address_suggest` {'query': 'Краснодар, Вишнёвая, 28', 'count': 3}
- C: `courier_book` {'address': {'locality': 'Краснодар', 'street': 'Вишнёвая', 'building': '28'}, 'contact': {'name': 'Марина', 'phone': '+79601068867'}, 'interval': {'from': '2026-09-05T09:00:00+03:00', 'to': '2026-09…
- I: `address_suggest` written={'query': 'Краснодар, улица Буковая, 159', 'count': 3} → restored={'query': 'Краснодар, вишёнвая, 28', 'count': 3}
- C′: `address_suggest` {'query': 'Краснодар, Вишнёвая 28', 'count': 3}
- C′: `courier_book` {'address': {'locality': 'Краснодар', 'street': 'Вишнёвая', 'building': '28'}, 'contact': {'name': 'Марина', 'phone': '+79601068867'}, 'interval': {'from': '2026-09-05T09:00:00+03:00', 'to': '2026-09…
- FIELD `address_suggest.query` [other_person/p14.sugg1 → loc_street] C=`Краснодар, Вишнёвая, 28` I=`Краснодар, вишёнвая, 28`
- FIELD `courier_book.address.building` [absent → absent:building] C=`28` I=``
- FIELD `courier_book.address.locality` [absent → absent:locality] C=`Краснодар` I=``
- FIELD `courier_book.address.street` [absent → absent:street] C=`Вишнёвая` I=``
- FIELD `courier_book.contact.name` [absent → absent:name] C=`Марина` I=``
- FIELD `courier_book.contact.phone` [absent → absent:phone] C=`+79601068867` I=``
- REPLY I: Сейчас проверю адрес! К сожалению, адрес **вишёнвая 28, Краснодар** не найден в базе — похожих совпадений нет. Пожалуйста, уточните: - Правильно ли написана улица? (Возможно, другое название?) - Верно ли указан номер дома — **28**? Как только подтвердите адрес, сразу вызову курьера!

## compare-021|0 · compare · sloppy · L1 = · L3 ≠ · C′≈C да · причина: **Б8-echo**
- USER[1]: курьера на нидняя 59 это в соравала на имя кирилла тлефон 8-909-528-76-24
- USER[2]: провертте адрес в базе и вызывайте на завтра утром
- seen LOC `нидняя 59` → `улица Кленовая 147`
- seen NAME `кирилла` → `Мирона`
- seen PHONE `8-909-528-76-24` → `+79669455595`
- C: `address_suggest` {'query': 'Сортавала улица Нижняя 59', 'count': 3}
- C: `courier_book` {'address': {'locality': 'Сортавала', 'street': 'Нижняя', 'building': '59'}, 'contact': {'name': 'Кирилл', 'phone': '+79095287624'}, 'interval': {'from': '2026-09-05T09:00:00+03:00', 'to': '2026-09-0…
- I: `address_suggest` written={'query': 'Сортавала, улица Кленовая 147', 'count': 3} → restored={'query': 'Сортавала, нидняя 59', 'count': 3}
- I: `courier_book` written={'address': {'locality': 'Сортавала', 'street': 'Кленовая', 'building': '147'}, 'contact': {'name': 'Мирон', 'phone': '+79669455595'}, 'interval': {'from': '2026-09-05T09:00:00+03:00', 'to': '2026-09-05T13:00:00+03:00'}} → restored={'address': {'locality': 'Сортавала', 'street': 'Нижняя', 'building': '59'}, 'contact': {'name': 'кирилл', 'phone': '+79095287624'}, 'interval': {'from': '2026-09-05T09:00:00+03:00', 'to': '2026-09-05T13:00:00+03:00'}}
- C′: `address_suggest` {'query': 'Сортавала, улица Нижняя, 59', 'count': 3}
- C′: `courier_book` {'address': {'locality': 'Сортавала', 'street': 'Нижняя', 'building': '59'}, 'contact': {'name': 'Кирилл', 'phone': '+79095287624'}, 'interval': {'from': '2026-09-05T09:00:00+03:00', 'to': '2026-09-0…
- FIELD `address_suggest.query` [other_person/p21.sugg1 → loc_other] C=`Сортавала улица Нижняя 59` I=`Сортавала, нидняя 59`
- REPLY I: Сейчас проверю адрес в справочнике! Адрес найден в базе! Вызываю курьера на завтра утром (09:00–13:00). Готово! Курьер вызван ✅ **Детали вызова:** - 📍 Адрес: сортавала, нижняя, 59 (Республика Карелия) - 👤 Контакт: кирилл, 8-909-528-76-24 - 🗓 Дата: 5 сентября 2026 г. - 🕘 Интервал: 09:00 – 13:00 (МСК…

## compare-028|0 · compare · voice_itn · L1 = · L3 ≠ · C′≈C нет · причина: **other**
- USER[1]: здравствуйте курьера на садовая 155 это в абакан на имя евгения телефон 89854133360
- USER[2]: проверьте адрес в базе и вызывайте на завтра утром
- seen LOC `садовая 155` → `улица Черёмуховая 73`
- seen NAME `евгения` → `Ивана`
- seen PHONE `89854133360` → `+79934391736`
- C: `address_suggest` {'query': 'Абакан, Садовая 155'}
- C: `courier_book` {'address': {'locality': 'Абакан', 'street': 'Садовая', 'building': '155'}, 'contact': {'name': 'Евгения', 'phone': '+79854133360'}, 'interval': {'from': '2026-09-05T09:00:00+07:00', 'to': '2026-09-0…
- I: `address_suggest` written={'query': 'Абакан, улица Черёмуховая 73', 'count': 1} → restored={'query': 'Абакан, садовая 155', 'count': 1}
- I: `courier_book` written={'address': {'locality': 'Абакан', 'street': 'Черёмуховая', 'building': '73'}, 'contact': {'name': 'Иван', 'phone': '+79934391736'}, 'interval': {'from': '2026-09-05T09:00:00+07:00', 'to': '2026-09-05T12:00:00+07:00'}} → restored={'address': {'locality': 'Абакан', 'street': 'Садовая', 'building': '155'}, 'contact': {'name': 'евгений', 'phone': '+79854133360'}, 'interval': {'from': '2026-09-05T09:00:00+07:00', 'to': '2026-09-05T12:00:00+07:00'}}
- C′: `address_suggest` {'query': 'Абакан, Садовая, 155', 'count': 3}
- C′: `courier_book` {'address': {'locality': 'Абакан', 'street': 'Садовая', 'building': '155'}, 'contact': {'name': 'Евгений', 'phone': '+79854133360'}, 'interval': {'from': '2026-09-05T09:00:00+07:00', 'to': '2026-09-0…
- FIELD `courier_book.contact.name` [fragment/given → name_case] C=`Евгения` I=`евгений`
- REPLY I: Проверяю адрес в справочнике! Адрес найден в базе: **Республика Хакасия, абакан, садовая, 155** ✅ Вызываю курьера на завтра утром (09:00–12:00)! Готово! Курьер вызван ✅ **Детали заявки:** - 🆔 Номер заявки: **clm-1** - 📍 Адрес: абакан, садовая, 155 - 👤 Контакт: евгений, 89854133360 - 🗓 Дата: **5 сен…

## compare-028|1 · compare · voice_itn · L1 = · L3 ≠ · C′≈C нет · причина: **other**
- USER[1]: здравствуйте курьера на садовая 155 это в абакан на имя евгения телефон 89854133360
- USER[2]: проверьте адрес в базе и вызывайте на завтра утром
- seen LOC `садовая 155` → `улица Кедровая 196`
- seen NAME `евгения` → `Владимира`
- seen PHONE `89854133360` → `+79397221349`
- C: `address_suggest` {'query': 'Абакан, Садовая 155', 'count': 3}
- C: `courier_book` {'address': {'locality': 'Абакан', 'street': 'Садовая', 'building': '155'}, 'contact': {'name': 'Евгения', 'phone': '+79854133360'}, 'interval': {'from': '2026-09-05T09:00:00+07:00', 'to': '2026-09-0…
- I: `address_suggest` written={'query': 'Абакан, улица Кедровая, 196', 'count': 3} → restored={'query': 'Абакан, садовая, 155', 'count': 3}
- I: `courier_book` written={'address': {'locality': 'Абакан', 'street': 'Кедровая', 'building': '196'}, 'contact': {'name': 'Владимир', 'phone': '+79397221349'}, 'interval': {'from': '2026-09-05T09:00:00+07:00', 'to': '2026-09-05T13:00:00+07:00'}} → restored={'address': {'locality': 'Абакан', 'street': 'Садовая', 'building': '155'}, 'contact': {'name': 'евгений', 'phone': '+79854133360'}, 'interval': {'from': '2026-09-05T09:00:00+07:00', 'to': '2026-09-05T13:00:00+07:00'}}
- C′: `address_suggest` {'query': 'Абакан, Садовая 155', 'count': 3}
- C′: `courier_book` {'address': {'locality': 'Абакан', 'street': 'Садовая', 'building': '155'}, 'contact': {'name': 'Евгений', 'phone': '+79854133360'}, 'interval': {'from': '2026-09-05T09:00:00+07:00', 'to': '2026-09-0…
- FIELD `courier_book.contact.name` [fragment/given → name_case] C=`Евгения` I=`евгений`
- REPLY I: Сейчас проверю адрес! Адрес подтверждён — **абакан, садовая, 155**. Вызываю курьера на завтра утром (5 сентября, 09:00–13:00)! Готово! Курьер вызван. ✅ **Детали заявки:** - 🆔 Номер заявки: **clm-1** - 📍 Адрес: абакан, садовая, 155 - 👤 Контакт: евгений, 89854133360 - 🕘 Интервал: **5 сентября 2026, с…

## compare-034|0 · compare · voice_raw · L1 ≠ · L3 ≠ · C′≈C нет · причина: **Б8-echo**
- USER[1]: курьераа на пушкна шестьдесят пять корпус один этоо в самара на имя петра телефон восемь девятьсот восемьдесят семь четыреста девяносто четыре пятьсот тридцать три пять
- USER[2]: проверьте адрес в базее ии вызывайтее на завтра утром
- seen LOC `пушкна шестьдесят пять корпус один` → `улицу Речную 47, корп. 10`
- seen NAME `петра` → `Василия`
- seen PHONE `восемь девятьсот восемьдесят семь четыреста девяносто четыре пятьсот тридцать три пять` → `+79402726830`
- C: `address_suggest` {'query': 'Самара, улица Пушкина, 65 корпус 1', 'count': 3}
- C: `courier_book` {'address': {'locality': 'Самара', 'street': 'Пушкина', 'building': '65 корп. 1'}, 'contact': {'name': 'Пётр', 'phone': '+79874945335'}, 'interval': {'from': '2026-09-05T09:00:00+04:00', 'to': '2026-… · refusal=house_format
- C: `courier_book` {'address': {'locality': 'Самара', 'street': 'Пушкина', 'building': '65к1'}, 'contact': {'name': 'Пётр', 'phone': '+79874945335'}, 'interval': {'from': '2026-09-05T09:00:00+04:00', 'to': '2026-09-05T… · refusal=house_format
- C: `courier_book` {'address': {'locality': 'Самара', 'street': 'Пушкина', 'building': '65/1'}, 'contact': {'name': 'Пётр', 'phone': '+79874945335'}, 'interval': {'from': '2026-09-05T09:00:00+04:00', 'to': '2026-09-05T…
- I: `address_suggest` written={'query': 'Самара, улица Речная, 47, корп. 10', 'count': 3} → restored={'query': 'Самара, пушкна, 65, корп. 1', 'count': 3}
- C′: `address_suggest` {'query': 'Самара, Пушкина, 65 корпус 1', 'count': 3}
- C′: `courier_book` {'address': {'locality': 'Самара', 'street': 'Пушкина', 'building': '65 корп. 1'}, 'contact': {'name': 'Петр', 'phone': '+79874945335'}, 'interval': {'from': '2026-09-05T09:00:00+04:00', 'to': '2026-… · refusal=house_format
- C′: `courier_book` {'address': {'locality': 'Самара', 'street': 'Пушкина', 'building': '65к1'}, 'contact': {'name': 'Петр', 'phone': '+79874945335'}, 'interval': {'from': '2026-09-05T09:00:00+04:00', 'to': '2026-09-05T… · refusal=house_format
- C′: `courier_book` {'address': {'locality': 'Самара', 'street': 'Пушкина', 'building': '65'}, 'contact': {'name': 'Петр', 'phone': '+79874945335'}, 'interval': {'from': '2026-09-05T09:00:00+04:00', 'to': '2026-09-05T12…
- FIELD `address_suggest.query` [other/unbound → loc_street] C=`Самара, улица Пушкина, 65 корпус 1` I=`Самара, пушкна, 65, корп. 1`
- FIELD `courier_book.address.building` [absent → absent:building] C=`65 корп. 1` I=``
- FIELD `courier_book.address.locality` [absent → absent:locality] C=`Самара` I=``
- FIELD `courier_book.address.street` [absent → absent:street] C=`Пушкина` I=``
- FIELD `courier_book.contact.name` [absent → absent:name] C=`Пётр` I=``
- FIELD `courier_book.contact.phone` [absent → absent:phone] C=`+79874945335` I=``
- FIELD `courier_book.address.building` [absent → absent:building] C=`65к1` I=``
- FIELD `courier_book.address.locality` [absent → absent:locality] C=`Самара` I=``
- FIELD `courier_book.address.street` [absent → absent:street] C=`Пушкина` I=``
- FIELD `courier_book.contact.name` [absent → absent:name] C=`Пётр` I=``
- FIELD `courier_book.contact.phone` [absent → absent:phone] C=`+79874945335` I=``
- FIELD `courier_book.address.building` [absent → absent:building] C=`65/1` I=``
- FIELD `courier_book.address.locality` [absent → absent:locality] C=`Самара` I=``
- FIELD `courier_book.address.street` [absent → absent:street] C=`Пушкина` I=``
- FIELD `courier_book.contact.name` [absent → absent:name] C=`Пётр` I=``
- FIELD `courier_book.contact.phone` [absent → absent:phone] C=`+79874945335` I=``
- REPLY I: Проверяю адрес в базе! К сожалению, адрес **пушкна шестьдесят пять корпус один, Самара** не найден в нашей базе — справочник вернул совершенно другие улицы, которые не совпадают с указанным адресом. Пожалуйста, проверьте адрес: - Верно ли написание улицы? (может быть «Речников», «Прибрежная» и т.п.…

## compare-034|1 · compare · voice_raw · L1 ≠ · L3 ≠ · C′≈C да · причина: **Б8-echo**
- USER[1]: курьераа на пушкна шестьдесят пять корпус один этоо в самара на имя петра телефон восемь девятьсот восемьдесят семь четыреста девяносто четыре пятьсот тридцать три пять
- USER[2]: проверьте адрес в базее ии вызывайтее на завтра утром
- seen LOC `пушкна шестьдесят пять корпус один` → `улицу Озёрную 180, корп. 1`
- seen NAME `петра` → `Артёма`
- seen PHONE `восемь девятьсот восемьдесят семь четыреста девяносто четыре пятьсот тридцать три пять` → `+79261042820`
- C: `address_suggest` {'query': 'Самара, улица Пушкина, 65 корпус 1', 'count': 3}
- C: `courier_book` {'address': {'locality': 'Самара', 'street': 'Пушкина', 'building': '65 к1'}, 'contact': {'name': 'Пётр', 'phone': '+79874945335'}, 'interval': {'from': '2026-09-05T09:00:00+04:00', 'to': '2026-09-05… · refusal=house_format
- C: `courier_book` {'address': {'locality': 'Самара', 'street': 'Пушкина', 'building': '65'}, 'contact': {'name': 'Пётр', 'phone': '+79874945335'}, 'interval': {'from': '2026-09-05T09:00:00+04:00', 'to': '2026-09-05T12…
- I: `address_suggest` written={'query': 'Самара, улица Озёрная, 180, корп. 1', 'count': 3} → restored={'query': 'Самара, пушкна, 65, корп. 1', 'count': 3}
- C′: `address_suggest` {'query': 'Самара, улица Пушкина, 65 корпус 1', 'count': 3}
- C′: `courier_book` {'address': {'locality': 'Самара', 'street': 'Пушкина', 'building': '65 к1'}, 'contact': {'name': 'Пётр', 'phone': '+79874945335'}, 'interval': {'from': '2026-09-05T09:00:00+04:00', 'to': '2026-09-05… · refusal=house_format
- C′: `courier_book` {'address': {'locality': 'Самара', 'street': 'Пушкина', 'building': '65к1'}, 'contact': {'name': 'Пётр', 'phone': '+79874945335'}, 'interval': {'from': '2026-09-05T09:00:00+04:00', 'to': '2026-09-05T… · refusal=house_format
- C′: `courier_book` {'address': {'locality': 'Самара', 'street': 'Пушкина', 'building': '65'}, 'contact': {'name': 'Пётр', 'phone': '+79874945335'}, 'interval': {'from': '2026-09-05T09:00:00+04:00', 'to': '2026-09-05T12…
- FIELD `address_suggest.query` [other/unbound → loc_street] C=`Самара, улица Пушкина, 65 корпус 1` I=`Самара, пушкна, 65, корп. 1`
- FIELD `courier_book.address.building` [absent → absent:building] C=`65 к1` I=``
- FIELD `courier_book.address.locality` [absent → absent:locality] C=`Самара` I=``
- FIELD `courier_book.address.street` [absent → absent:street] C=`Пушкина` I=``
- FIELD `courier_book.contact.name` [absent → absent:name] C=`Пётр` I=``
- FIELD `courier_book.contact.phone` [absent → absent:phone] C=`+79874945335` I=``
- FIELD `courier_book.address.building` [absent → absent:building] C=`65` I=``
- FIELD `courier_book.address.locality` [absent → absent:locality] C=`Самара` I=``
- FIELD `courier_book.address.street` [absent → absent:street] C=`Пушкина` I=``
- FIELD `courier_book.contact.name` [absent → absent:name] C=`Пётр` I=``
- FIELD `courier_book.contact.phone` [absent → absent:phone] C=`+79874945335` I=``
- REPLY I: Проверяю адрес в базе! К сожалению, точного адреса **пушкна шестьдесят пять корпус один** в Самаре в базе не нашлось — ближайший результат: **Самарская область, г Самара, ул Пушкина, д 65**. Это другой дом. Пожалуйста, уточните адрес — возможно, другой номер дома или улица называется иначе? Как тол…

## compare-035|1 · compare · voice_itn · L1 ≠ · L3 ≠ · C′≈C да · причина: **Б8-echo**
- USER[1]: алло курьера на кирова 79 это в глазов на имя анну телефон 8 977 777 88 99
- USER[2]: сверьте по справочнику и оформляйте на завтра с десяти до четырёх
- seen LOC `кирова 79` → `улицы Сосновой 123`
- seen NAME `анну` → `Ольгу`
- seen PHONE `8 977 777 88 99` → `+79888471580`
- C: `address_suggest` {'query': 'Глазов, улица Кирова, 79'}
- C: `courier_book` {'address': {'locality': 'Глазов', 'street': 'Кирова', 'building': '79'}, 'contact': {'name': 'Анна', 'phone': '+79777778899'}, 'interval': {'from': '2026-09-05T10:00:00+04:00', 'to': '2026-09-05T16:…
- I: `address_suggest` written={'query': 'Глазов, улица Сосновая, 123'} → restored={'query': 'Глазов, кирова, 79'}
- C′: `address_suggest` {'query': 'Глазов, улица Кирова, 79', 'count': 3}
- C′: `courier_book` {'address': {'locality': 'Глазов', 'street': 'Кирова', 'building': '79'}, 'contact': {'name': 'Анна', 'phone': '+79777778899'}, 'interval': {'from': '2026-09-05T10:00:00+04:00', 'to': '2026-09-05T16:…
- FIELD `courier_book.address.building` [absent → absent:building] C=`79` I=``
- FIELD `courier_book.address.locality` [absent → absent:locality] C=`Глазов` I=``
- FIELD `courier_book.address.street` [absent → absent:street] C=`Кирова` I=``
- FIELD `courier_book.contact.name` [absent → absent:name] C=`Анна` I=``
- FIELD `courier_book.contact.phone` [absent → absent:phone] C=`+79777778899` I=``
- REPLY I: Сначала проверю адрес по справочнику! По справочнику адрес **Глазов, кирова 79** не нашёлся — похожих записей нет. Возможно, улица или номер дома указаны с ошибкой. Можете уточнить адрес? Например, проверить название улицы или номер дома — и тогда сразу оформим вызов.

## compare-036|0 · compare · chat · L1 = · L3 ≠ · C′≈C нет · причина: **other**
- USER[1]: здравствуйте курьера на маяковского 82 это в можга на имя валерию телефон 8-952-114-78-01
- USER[2]: проверьте адрес в базе и вызывайте на завтра утром
- seen LOC `маяковского 82` → `улицы Полевой 97`
- seen NAME `валерию` → `Фаину`
- seen PHONE `8-952-114-78-01` → `+79953034735`
- C: `address_suggest` {'query': 'Можга, улица Маяковского 82', 'count': 3}
- C: `courier_book` {'address': {'locality': 'Можга', 'street': 'Маяковского', 'building': '82'}, 'contact': {'name': 'Валерия', 'phone': '+79521147801'}, 'interval': {'from': '2026-09-05T09:00:00+04:00', 'to': '2026-09…
- I: `address_suggest` written={'query': 'Можга, улица Полевая, 97', 'count': 3} → restored={'query': 'Можга, маяковского, 82', 'count': 3}
- I: `courier_book` written={'address': {'locality': 'Можга', 'street': 'Полевая', 'building': '97'}, 'contact': {'name': 'Фаина', 'phone': '+79953034735'}, 'interval': {'from': '2026-09-05T09:00:00+04:00', 'to': '2026-09-05T12:00:00+04:00'}} → restored={'address': {'locality': 'Можга', 'street': 'Маяковского', 'building': '82'}, 'contact': {'name': 'валерия', 'phone': '+79521147801'}, 'interval': {'from': '2026-09-05T09:00:00+04:00', 'to': '2026-09-05T12:00:00+04:00'}}
- C′: `address_suggest` {'query': 'Можга, улица Маяковского, 82', 'count': 3}
- C′: `courier_book` {'address': {'locality': 'Можга', 'street': 'Маяковского', 'building': '82'}, 'contact': {'name': 'Валерия', 'phone': '+79521147801'}, 'interval': {'from': '2026-09-05T09:00:00+04:00', 'to': '2026-09…
- REPLY I: Проверяю адрес в справочнике! Адрес найден в базе! Вызываю курьера на завтра утром (09:00–12:00). Готово! Курьер вызван. Детали заявки: - **Номер заявки:** clm-1 - **Адрес:** г. можга, маяковского, 82 - **Получатель:** валерия, 8-952-114-78-01 - **Дата и время:** 5 сентября 2026, с 09:00 до 12:00 Е…

## container-005|0 · container · sloppy · L1 = · L3 ≠ · C′≈C да · причина: **other**
- USER[1]: здрасте занесите двоих в бауз одной выгрузкой битюкова зинаида тлеефон +79261234567 и джонсон майкл телефон 8 962 836 50 92 дата рождения второго 07.08.1989
- seen NAME `битюкова зинаида` → `Бирюкова Ева`
- seen PHONE `+79261234567` → `+79311681199`
- seen NAME `джонсон майкл` → `Олег Константин`
- seen PHONE `8 962 836 50 92` → `+79503505044`
- seen DOB `07.08.1989` → `13.07.1989`
- C: `crm_import_csv` {'csv': 'last_name;first_name;phone;email;birth_date\nБитюкова;Зинаида;+79261234567;;\nДжонсон;Майкл;+79628365092;;1989-08-07'}
- I: `crm_import_csv` written={'csv': 'last_name;first_name;phone;email;birth_date\nБирюкова;Ева;+79311681199;;\nКонстантин;Олег;+79503505044;;1989-07-13'} → restored={'csv': 'last_name;first_name;phone;email;birth_date\nбитюкова;зинаида;+79261234567;;\nмайкл;джонсон;+79628365092;;1989-08-07'}
- C′: `crm_import_csv` {'csv': 'last_name;first_name;phone;email;birth_date\nБитюкова;Зинаида;+79261234567;;\nДжонсон;Майкл;+79628365092;;1989-08-07'}
- FIELD `crm_import_csv.csv` [container_embedded/differs_inside → name_partial] C=`last_name;first_name;phone;email;birth_date Битюкова;Зинаида;+79261234567;; Джо…` I=`last_name;first_name;phone;email;birth_date битюкова;зинаида;+79261234567;; май…`
- REPLY I: Здравствуйте! Принял данные, загружаю одной пачкой: - **битюкова зинаида** — +79261234567 - **джонсон майкл** — 8 962 836 50 92, д.р. 07.08.1989 Готово! ✅ Оба контакта успешно занесены в базу: | # | Фамилия | Имя | Телефон | Дата рождения | |---|---------|-----|---------|---------------| | 1 | битю…

## container-015|0 · container · voice_raw · L1 ≠ · L3 ≠ · C′≈C да · причина: **residual**
- USER[1]: занесите двоих в базуу одной выгрузкоой кузнецова ольга телефон восемь девятьсот двенадцать девяносто восемь семьдесят шесть пятьдесят четыре три и абдуллаев тимур телефон восемь девятьсот пятьдесят один пятьсот сорок шесть восемесят два семьдесят семь дата рождения второгоо шестое января шестьдесят четвёртого года
- seen NAME `кузнецова ольга` → `Котова Мария`
- seen PHONE `восемь девятьсот двенадцать девяносто восемь семьдесят шесть пятьдесят четыре три` → `+79929126180`
- seen NAME `абдуллаев тимур` → `Котов Никита`
- seen PHONE `восемь девятьсот пятьдесят один пятьсот сорок шесть восемесят два семьдесят семь` → `+79901622948`
- seen DOB `шестое января шестьдесят четвёртого года` → `04.09.1972`
- C: `crm_import_csv` {'csv': 'last_name;first_name;phone;email;birth_date\nКузнецова;Ольга;+79129876543;;\nАбдуллаев;Тимур;+79515468277;;1964-01-06'}
- I: `crm_import_csv` written={'csv': 'last_name;first_name;phone;email;birth_date\nКотова;Мария;+79929126180;;\nКотов;Никита;+79901622948;;1972-09-04'} → restored={'csv': 'last_name;first_name;phone;email;birth_date\nКотова;ольга;+79129876543;;\nабдуллаев;тимур;+79515468277;;шестое января шестьдесят четвёртого года'} · residual={'csv': ('котова',)} · refusal=date_not_iso8601
- I: `crm_import_csv` written={'csv': 'last_name;first_name;phone;email;birth_date\nКотова;Мария;+79929126180;;\nКотов;Никита;+79901622948;;1972-09-04'} → restored={'csv': 'last_name;first_name;phone;email;birth_date\nКотова;ольга;+79129876543;;\nабдуллаев;тимур;+79515468277;;шестое января шестьдесят четвёртого года'} · residual={'csv': ('котова',)} · refusal=date_not_iso8601
- I: `crm_import_csv` written={'csv': 'last_name;first_name;phone;email;birth_date\nКотова;Мария;+79929126180;;\nКотов;Никита;+79901622948;;'} → restored={'csv': 'last_name;first_name;phone;email;birth_date\nКотова;ольга;+79129876543;;\nабдуллаев;тимур;+79515468277;;'} · residual={'csv': ('котова',)}
- C′: `crm_import_csv` {'csv': 'last_name;first_name;phone;email;birth_date\nКузнецова;Ольга;+79129876543;;\nАбдуллаев;Тимур;+79515468277;;1964-01-06'}
- FIELD `crm_import_csv.csv` [residual → name_partial] C=`last_name;first_name;phone;email;birth_date Кузнецова;Ольга;+79129876543;; Абду…` I=`last_name;first_name;phone;email;birth_date Котова;ольга;+79129876543;; абдулла…` · подмена дошла до инструмента: котова
- FIELD `crm_import_csv.csv` [extra → extra:csv] C=`` I=`last_name;first_name;phone;email;birth_date Котова;ольга;+79129876543;; абдулла…`
- FIELD `crm_import_csv.csv` [extra → extra:csv] C=`` I=`last_name;first_name;phone;email;birth_date Котова;ольга;+79129876543;; абдулла…`
- REPLY I: Импортирую обоих одной выгрузкой! Система не приняла дату. Повторю с кавычками вокруг даты рождения: Попробую ещё раз без кавычек — второй ответ был техническим сбоем при передаче: Система упорно отклоняет дату. Занесу обоих без даты рождения, чтобы не потерять контакты, а потом разберёмся с датой:…

## container-017|0 · container · voice_itn · L1 ≠ · L3 ≠ · C′≈C да · причина: **other**
- USER[1]: занесите двоих в базу одной выгрузкой битюкова зинаида телефон 8 950 116 66 45 и ким виктор телефон +79890102656 дата рождения второго 18 02 1996
- seen NAME `битюкова зинаида` → `Беляева Екатерина`
- seen PHONE `8 950 116 66 45` → `+79654035015`
- seen NAME `ким виктор` → `Панов Яков`
- seen PHONE `+79890102656` → `+79508938416`
- seen DOB `18 02 1996` → `09.07.2000`
- C: `crm_import_csv` {'csv': 'last_name;first_name;phone;email;birth_date\nБитюкова;Зинаида;+79501166645;;\nКим;Виктор;+79890102656;;1996-02-18'}
- I: `crm_import_csv` written={'csv': 'last_name;first_name;phone;email;birth_date\nБеляева;Екатерина;+79654035015;;\nПанов;Яков;+79508938416;;2000-07-09'} → restored={'csv': 'last_name;first_name;phone;email;birth_date\nбитюкова;зинаида;+79501166645;;\nким;виктор;+79890102656;;1802-19-96'} · refusal=date_invalid
- I: `crm_import_csv` written={'csv': 'last_name;first_name;phone;email;birth_date\nБеляева;Екатерина;+79654035015;;\nПанов;Яков;+79508938416;;09.07.2000'} → restored={'csv': 'last_name;first_name;phone;email;birth_date\nбитюкова;зинаида;+79501166645;;\nким;виктор;+79890102656;;18.02.1996'} · refusal=date_not_iso8601
- I: `crm_import_csv` written={'csv': 'last_name;first_name;phone;email;birth_date\nБеляева;Екатерина;+79654035015;;\nПанов;Яков;+79508938416;;2000-07-09'} → restored={'csv': 'last_name;first_name;phone;email;birth_date\nбитюкова;зинаида;+79501166645;;\nким;виктор;+79890102656;;1802-19-96'} · refusal=date_invalid
- I: `crm_import_csv` written={'csv': 'last_name;first_name;phone;email;birth_date\nБеляева;Екатерина;+79654035015;;\nПанов;Яков;+79508938416;;07/09/2000'} → restored={'csv': 'last_name;first_name;phone;email;birth_date\nбитюкова;зинаида;+79501166645;;\nким;виктор;+79890102656;;18/02/1996'} · refusal=date_not_iso8601
- I: `crm_import_csv` written={'csv': 'last_name;first_name;phone;email;birth_date\nБеляева;Екатерина;+79654035015;;\nПанов;Яков;+79508938416;;2000-07-09'} → restored={'csv': 'last_name;first_name;phone;email;birth_date\nбитюкова;зинаида;+79501166645;;\nким;виктор;+79890102656;;1802-19-96'} · refusal=date_invalid
- I: `crm_import_csv` written={'csv': 'last_name;first_name;phone;email;birth_date\nБеляева;Екатерина;+79654035015;;\nПанов;Яков;+79508938416;;'} → restored={'csv': 'last_name;first_name;phone;email;birth_date\nбитюкова;зинаида;+79501166645;;\nким;виктор;+79890102656;;'}
- C′: `crm_import_csv` {'csv': 'last_name;first_name;phone;email;birth_date\nБитюкова;Зинаида;+79501166645;;\nКим;Виктор;+79890102656;;1996-02-18'}
- FIELD `crm_import_csv.csv` [container_embedded/differs_inside → name_partial] C=`last_name;first_name;phone;email;birth_date Битюкова;Зинаида;+79501166645;; Ким…` I=`last_name;first_name;phone;email;birth_date битюкова;зинаида;+79501166645;; ким…`
- FIELD `crm_import_csv.csv` [extra → extra:csv] C=`` I=`last_name;first_name;phone;email;birth_date битюкова;зинаида;+79501166645;; ким…`
- FIELD `crm_import_csv.csv` [extra → extra:csv] C=`` I=`last_name;first_name;phone;email;birth_date битюкова;зинаида;+79501166645;; ким…`
- FIELD `crm_import_csv.csv` [extra → extra:csv] C=`` I=`last_name;first_name;phone;email;birth_date битюкова;зинаида;+79501166645;; ким…`
- FIELD `crm_import_csv.csv` [extra → extra:csv] C=`` I=`last_name;first_name;phone;email;birth_date битюкова;зинаида;+79501166645;; ким…`
- FIELD `crm_import_csv.csv` [extra → extra:csv] C=`` I=`last_name;first_name;phone;email;birth_date битюкова;зинаида;+79501166645;; ким…`
- REPLY I: Импортирую обоих одной выгрузкой! Попробую другой формат даты рождения: Система требует ISO 8601, пробую ещё раз с форматом YYYY-MM-DD: Попробую другой вариант формата даты: Система принимает только ISO 8601 но считает дату невалидной — попробую ещё один вариант: Система упорно возвращает ошибку дл…

## container-023|0 · container · voice_itn · L1 ≠ · L3 ≠ · C′≈C да · причина: **other**
- USER[1]: здравствуйте занесите двоих в базу одной выгрузкой васильев иван телефон 89897340815 и валиахметов ильдар телефон 89052503568 дата рождения второго 19 05 1998
- seen NAME `васильев иван` → `Лебедев Вадим`
- seen PHONE `89897340815` → `+79710597760`
- seen NAME `валиахметов ильдар` → `Щукин Константин`
- seen PHONE `89052503568` → `+79954373207`
- seen DOB `19 05 1998` → `20.10.1978`
- C: `crm_import_csv` {'csv': 'last_name;first_name;phone;email;birth_date\nВасильев;Иван;+79897340815;;\nВалиахметов;Ильдар;+79052503568;;1998-05-19'}
- I: `crm_import_csv` written={'csv': 'last_name;first_name;phone;email;birth_date\nЛебедев;Вадим;+79710597760;;\nЩукин;Константин;+79954373207;;1978-10-20'} → restored={'csv': 'last_name;first_name;phone;email;birth_date\nвасильев;иван;+79897340815;;\nвалиахметов;ильдар;+79052503568;;1905-19-98'} · refusal=date_invalid
- I: `crm_import_csv` written={'csv': 'last_name;first_name;phone;email;birth_date\nЛебедев;Вадим;+79710597760;;\nЩукин;Константин;+79954373207;;20.10.1978'} → restored={'csv': 'last_name;first_name;phone;email;birth_date\nвасильев;иван;+79897340815;;\nЩукин;ильдар;+79052503568;;19.05.1998'} · residual={'csv': ('щукин',)} · refusal=date_not_iso8601
- I: `crm_import_csv` written={'csv': 'last_name;first_name;phone;email;birth_date\nЛебедев;Вадим;+79710597760;;\nЩукин;Константин;+79954373207;;1978-10-20'} → restored={'csv': 'last_name;first_name;phone;email;birth_date\nвасильев;иван;+79897340815;;\nЩукин;ильдар;+79052503568;;1905-19-98'} · residual={'csv': ('щукин',)} · refusal=date_invalid
- I: `crm_import_csv` written={'csv': 'last_name;first_name;phone;email;birth_date\nЛебедев;Вадим;+79710597760;;\nЩукин;Константин;+79954373207;;'} → restored={'csv': 'last_name;first_name;phone;email;birth_date\nвасильев;иван;+79897340815;;\nЩукин;ильдар;+79052503568;;'} · residual={'csv': ('щукин',)}
- C′: `crm_import_csv` {'csv': 'last_name;first_name;phone;email;birth_date\nВасильев;Иван;+79897340815;;\nВалиахметов;Ильдар;+79052503568;;1998-05-19'}
- FIELD `crm_import_csv.csv` [container_embedded/differs_inside → name_partial] C=`last_name;first_name;phone;email;birth_date Васильев;Иван;+79897340815;; Валиах…` I=`last_name;first_name;phone;email;birth_date васильев;иван;+79897340815;; валиах…`
- FIELD `crm_import_csv.csv` [extra → extra:csv] C=`` I=`last_name;first_name;phone;email;birth_date васильев;иван;+79897340815;; Щукин;…`
- FIELD `crm_import_csv.csv` [extra → extra:csv] C=`` I=`last_name;first_name;phone;email;birth_date васильев;иван;+79897340815;; Щукин;…`
- FIELD `crm_import_csv.csv` [extra → extra:csv] C=`` I=`last_name;first_name;phone;email;birth_date васильев;иван;+79897340815;; Щукин;…`
- REPLY I: Здравствуйте! Импортирую оба контакта одной выгрузкой. Ошибка формата даты, попробую другой вариант. Система требует ISO 8601, но прежде отклонила этот формат. Попробую ещё раз точно в нём. Поле с датой рождения возвращает ошибку при любом формате. Импортирую обоих без даты рождения, чтобы записи п…

## container-029|0 · container · voice_raw · L1 ≠ · L3 ≠ · C′≈C да · причина: **other**
- USER[1]: аа здравствуйте занесите двоиих в базу одной выгрузкоой фёдорова юлия телефон восемь девятьсот пятьдесят два ноль пятьдесят четыыре двадцать пяять ноль девять и ким виктор телефонто восемь девятьсот шейсят три сто шестьдесят шесть четыреста сорок шесть два дата рождения второго третье сентября семьдесят четвёртого года
- seen NAME `фёдорова юлия` → `Шилова Лариса`
- seen PHONE `восемь девятьсот пятьдесят два ноль пятьдесят четыыре двадцать пяять ноль девять` → `+79672394519`
- seen NAME `ким виктор` → `Ершов Владимир`
- seen PHONE `восемь девятьсот шейсят три сто шестьдесят шесть четыреста сорок шесть два` → `+79775200538`
- seen DOB `третье сентября семьдесят четвёртого года` → `13.06.2021`
- C: `crm_import_csv` {'csv': 'last_name;first_name;phone;email;birth_date\nФёдорова;Юлия;+79520542509;;\nКим;Виктор;+79631664462;;1974-09-03'}
- I: `crm_import_csv` written={'csv': 'last_name;first_name;phone;email;birth_date\nШилова;Лариса;+79672394519;;\nЕршов;Владимир;+79775200538;;2021-06-13'} → restored={'csv': 'last_name;first_name;phone;email;birth_date\nфёдорова;юлия;+79520542509;;\nким;виктор;+79631664462;;третье сентября семьдесят четвёртого года'} · refusal=date_not_iso8601
- I: `crm_import_csv` written={'csv': 'last_name;first_name;phone;email;birth_date\nШилова;Лариса;+79672394519;;\nЕршов;Владимир;+79775200538;;2021-06-13'} → restored={'csv': 'last_name;first_name;phone;email;birth_date\nфёдорова;юлия;+79520542509;;\nким;виктор;+79631664462;;третье сентября семьдесят четвёртого года'} · refusal=date_not_iso8601
- I: `crm_import_csv` written={'csv': 'last_name;first_name;phone;email;birth_date\nШилова;Лариса;+79672394519;;\nЕршов;Владимир;+79775200538;;'} → restored={'csv': 'last_name;first_name;phone;email;birth_date\nфёдорова;юлия;+79520542509;;\nким;виктор;+79631664462;;'}
- C′: `crm_import_csv` {'csv': 'last_name;first_name;phone;email;birth_date\nФёдорова;Юлия;+79520542509;;\nКим;Виктор;+79631664462;;1974-09-03'}
- FIELD `crm_import_csv.csv` [container_embedded/differs_inside → name_partial] C=`last_name;first_name;phone;email;birth_date Фёдорова;Юлия;+79520542509;; Ким;Ви…` I=`last_name;first_name;phone;email;birth_date фёдорова;юлия;+79520542509;; ким;ви…`
- FIELD `crm_import_csv.csv` [extra → extra:csv] C=`` I=`last_name;first_name;phone;email;birth_date фёдорова;юлия;+79520542509;; ким;ви…`
- FIELD `crm_import_csv.csv` [extra → extra:csv] C=`` I=`last_name;first_name;phone;email;birth_date фёдорова;юлия;+79520542509;; ким;ви…`
- REPLY I: Здравствуйте! Сейчас занесу обоих одной выгрузкой. Похоже, небольшой сбой по дате. Повторяю запрос. Система упорно отвергает дату — похоже, технический сбой на стороне CRM. Занесу обоих без даты рождения ким, а потом сообщу о проблеме. Готово! Оба контакта успешно занесены в базу: | # | Фамилия | И…

## correction-010|0 · correction · chat · L1 = · L3 ≠ · C′≈C нет · причина: **other**
- USER[1]: курьера на полевая 30 кв 150 нет не так правильно полевая 2 квартира 150 это в ижевск это ерохин пётр телефон 8-903-765-43-21
- USER[2]: завтра с десяти до двух
- seen LOC `полевая 30 кв 150` → `улица Рябиновая 147, кв. 113`
- seen LOC `полевая 2 квартира 150` → `улица Каштановая 166, кв. 125`
- seen NAME `ерохин пётр` → `Фомин Даниил`
- seen PHONE `8-903-765-43-21` → `+79709119333`
- C: `courier_book` {'address': {'locality': 'Ижевск', 'street': 'Полевая', 'building': '2', 'sflat': '150'}, 'contact': {'name': 'Ерохин Пётр', 'phone': '+79037654321'}, 'interval': {'from': '2026-09-05T10:00:00+04:00'…
- C: `crm_upsert_contact` {'contact': {'last_name': 'Ерохин', 'first_name': 'Пётр', 'initials': 'П.', 'name_latin': 'Erokhin Pyotr', 'phone': '+79037654321', 'address': {'city': 'Ижевск', 'street': 'Полевая', 'house': '2', 'f…
- I: `courier_book` written={'address': {'locality': 'Ижевск', 'street': 'Каштановая', 'building': '166', 'sflat': '125'}, 'contact': {'name': 'Фомин Даниил', 'phone': '+79709119333'}, 'interval': {'from': '2026-09-05T10:00:00+04:00', 'to': '2026-09-05T14:00:00+04:00'}} → restored={'address': {'locality': 'Ижевск', 'street': 'полевая', 'building': '2', 'sflat': '150'}, 'contact': {'name': 'ерохин пётр', 'phone': '+79037654321'}, 'interval': {'from': '2026-09-05T10:00:00+04:00', 'to': '2026-09-05T14:00:00+04:00'}}
- I: `crm_upsert_contact` written={'contact': {'first_name': 'Даниил', 'last_name': 'Фомин', 'initials': 'Д.', 'name_latin': 'Fomin Daniil', 'phone': '+79709119333', 'gender': 'M', 'address': {'city': 'Ижевск', 'street': 'Каштановая', 'house': '166', 'flat': '125'}}} → restored={'contact': {'first_name': 'пётр', 'last_name': 'ерохин', 'initials': 'Д.', 'name_latin': 'Erokhin Petr', 'phone': '+79037654321', 'gender': 'M', 'address': {'city': 'Ижевск', 'street': 'полевая', 'house': '2', 'flat': '150'}}}
- C′: `courier_book` {'address': {'locality': 'Ижевск', 'street': 'Полевая', 'building': '2', 'sflat': '150'}, 'contact': {'name': 'Ерохин Пётр', 'phone': '+79037654321'}, 'interval': {'from': '2026-09-05T10:00:00+04:00'…
- FIELD `crm_upsert_contact.contact.gender` [extra → extra:gender] C=`` I=`M`
- FIELD `crm_upsert_contact.contact.initials` [derived/from_substitute → derived] C=`П.` I=`Д.` · значение выведено из ПОДМЕНЫ; восстановление недостижимо
- FIELD `crm_upsert_contact.contact.name_latin` [other/misderived → name_partial] C=`Erokhin Pyotr` I=`Erokhin Petr`
- REPLY I: Оформляю всё одновременно — вызов курьера и карточку клиента! Всё готово! Вот итог: **🚚 Курьер вызван** (заявка `clm-1`) - 📍 Ижевск, полевая 2 квартира 150 - 👤 ерохин пётр, 8-903-765-43-21 - 🕙 5 сентября 2026, с 10:00 до 14:00 **📋 Карточка клиента** обновлена в CRM (`c-1`) Если нужно что-то изменит…

## correction-010|1 · correction · chat · L1 ≠ · L3 ≠ · C′≈C нет · причина: **other**
- USER[1]: курьера на полевая 30 кв 150 нет не так правильно полевая 2 квартира 150 это в ижевск это ерохин пётр телефон 8-903-765-43-21
- USER[2]: завтра с десяти до двух
- seen LOC `полевая 30 кв 150` → `улица Ольховая 117, кв. 216`
- seen LOC `полевая 2 квартира 150` → `улица Вишнёвая 5, кв. 94`
- seen NAME `ерохин пётр` → `Бирюков Демьян`
- seen PHONE `8-903-765-43-21` → `+79364877806`
- C: `courier_book` {'address': {'locality': 'Ижевск', 'street': 'Полевая', 'building': '2', 'sflat': '150'}, 'contact': {'name': 'Ерохин Пётр', 'phone': '+79037654321'}, 'interval': {'from': '2026-09-05T10:00:00+04:00'…
- I: `courier_book` written={'address': {'locality': 'Ижевск', 'street': 'Вишнёвая', 'building': '5', 'sflat': '94'}, 'contact': {'name': 'Бирюков Демьян', 'phone': '+79364877806'}, 'interval': {'from': '2026-09-05T10:00:00+04:00', 'to': '2026-09-05T14:00:00+04:00'}} → restored={'address': {'locality': 'Ижевск', 'street': 'полевая', 'building': '2', 'sflat': '150'}, 'contact': {'name': 'ерохин пётр', 'phone': '+79037654321'}, 'interval': {'from': '2026-09-05T10:00:00+04:00', 'to': '2026-09-05T14:00:00+04:00'}}
- I: `crm_upsert_contact` written={'contact': {'last_name': 'Бирюков', 'first_name': 'Демьян', 'initials': 'Д.', 'name_latin': 'Biryukov Demyan', 'phone': '+79364877806', 'address': {'city': 'Ижевск', 'street': 'Вишнёвая', 'house': '5', 'flat': '94'}}} → restored={'contact': {'last_name': 'ерохин', 'first_name': 'пётр', 'initials': 'Д.', 'name_latin': 'Eroxin Pyotr', 'phone': '+79037654321', 'address': {'city': 'Ижевск', 'street': 'полевая', 'house': '2', 'flat': '150'}}}
- C′: `courier_book` {'address': {'locality': 'Ижевск', 'street': 'Полевая', 'building': '2', 'sflat': '150'}, 'contact': {'name': 'Ерохин Пётр', 'phone': '+79037654321'}, 'interval': {'from': '2026-09-05T10:00:00+04:00'…
- C′: `crm_upsert_contact` {'contact': {'last_name': 'Ерохин', 'first_name': 'Пётр', 'initials': 'П.', 'name_latin': 'Erokhin Pyotr', 'phone': '+79037654321', 'address': {'city': 'Ижевск', 'street': 'Полевая', 'house': '2', 'f…
- FIELD `crm_upsert_contact.contact.address.city` [extra → extra:city] C=`` I=`Ижевск`
- FIELD `crm_upsert_contact.contact.address.flat` [extra → extra:flat] C=`` I=`150`
- FIELD `crm_upsert_contact.contact.address.house` [extra → extra:house] C=`` I=`2`
- FIELD `crm_upsert_contact.contact.address.street` [extra → extra:street] C=`` I=`полевая`
- FIELD `crm_upsert_contact.contact.first_name` [extra → extra:first_name] C=`` I=`пётр`
- FIELD `crm_upsert_contact.contact.initials` [extra → extra:initials] C=`` I=`Д.`
- FIELD `crm_upsert_contact.contact.last_name` [extra → extra:last_name] C=`` I=`ерохин`
- FIELD `crm_upsert_contact.contact.name_latin` [extra → extra:name_latin] C=`` I=`Eroxin Pyotr`
- FIELD `crm_upsert_contact.contact.phone` [extra → extra:phone] C=`` I=`+79037654321`
- REPLY I: Отлично, оформляю всё сразу! Всё готово! Вот итог: 🚚 **Курьер вызван** (заявка `clm-1`) - **Адрес:** г. Ижевск, полевая 2 квартира 150 - **Получатель:** ерохин пётр, 8-903-765-43-21 - **Время:** 5 сентября 2026, с 10:00 до 14:00 👤 **Карточка клиента** в CRM создана/обновлена. Если нужно что-то ещё …

## correction-012|0 · correction · chat · L1 = · L3 ≠ · C′≈C нет · причина: **derived-only**
- USER[1]: добрый день курьера на адрес добролюбова 50 квартира 193 стоп правильно добролюбова 22 квартира 193 это в можга это кузнецова ольга телефон 8-961-473-24-80
- USER[2]: в любой день с девяти до шести
- seen LOC `добролюбова 50 квартира 193` → `улица Берёзовая 33, кв. 182`
- seen LOC `добролюбова 22 квартира 193` → `улица Ивовая 99, кв. 53`
- seen NAME `кузнецова ольга` → `Тарасова Инга`
- seen PHONE `8-961-473-24-80` → `+79699474829`
- C: `courier_book` {'address': {'locality': 'Можга', 'street': 'Добролюбова', 'building': '22', 'sflat': '193'}, 'contact': {'name': 'Кузнецова Ольга', 'phone': '+79614732480'}, 'interval': {'from': '2026-09-04T09:00:0…
- C: `crm_upsert_contact` {'contact': {'last_name': 'Кузнецова', 'first_name': 'Ольга', 'initials': 'О.', 'name_latin': 'Kuznetsova Olga', 'gender': 'F', 'phone': '+79614732480', 'address': {'city': 'Можга', 'street': 'Доброл…
- I: `courier_book` written={'address': {'locality': 'Можга', 'street': 'Ивовая', 'building': '99', 'sflat': '53'}, 'contact': {'name': 'Тарасова Инга', 'phone': '+79699474829'}, 'interval': {'from': '2026-09-04T09:00:00+04:00', 'to': '2026-09-04T18:00:00+04:00'}} → restored={'address': {'locality': 'Можга', 'street': 'добролюбова', 'building': '22', 'sflat': '193'}, 'contact': {'name': 'кузнецова ольга', 'phone': '+79614732480'}, 'interval': {'from': '2026-09-04T09:00:00+04:00', 'to': '2026-09-04T18:00:00+04:00'}}
- I: `crm_upsert_contact` written={'contact': {'last_name': 'Тарасова', 'first_name': 'Инга', 'initials': 'И.', 'name_latin': 'Tarasova Inga', 'gender': 'F', 'phone': '+79699474829', 'address': {'city': 'Можга', 'street': 'Ивовая', 'house': '99', 'flat': '53'}}} → restored={'contact': {'last_name': 'кузнецова', 'first_name': 'ольга', 'initials': 'И.', 'name_latin': 'Kuznetsova Olga', 'gender': 'F', 'phone': '+79614732480', 'address': {'city': 'Можга', 'street': 'добролюбова', 'house': '22', 'flat': '193'}}}
- C′: `courier_book` {'address': {'locality': 'Можга', 'street': 'Добролюбова', 'building': '22', 'sflat': '193'}, 'contact': {'name': 'Кузнецова Ольга', 'phone': '+79614732480'}, 'interval': {'from': '2026-09-04T09:00:0…
- C′: `crm_upsert_contact` {'contact': {'last_name': 'Кузнецова', 'first_name': 'Ольга', 'initials': 'О.', 'name_latin': 'Kuznetsova Olga', 'phone': '+79614732480', 'address': {'city': 'Можга', 'street': 'Добролюбова', 'house'…
- FIELD `crm_upsert_contact.contact.initials` [derived/from_substitute → derived] C=`О.` I=`И.` · значение выведено из ПОДМЕНЫ; восстановление недостижимо
- REPLY I: Принял! Оформляю вызов курьера и карточку клиента одновременно. Всё оформлено! Вот итог: **Вызов курьера** ✅ (№ clm-1) - 📍 Можга, добролюбова 22 квартира 193 - 👤 кузнецова ольга, 8-961-473-24-80 - 🕘 Сегодня, 04.09.2026, с 09:00 до 18:00 **Карточка клиента** ✅ обновлена в CRM (№ c-1) Если потребуетс…

## correction-012|1 · correction · chat · L1 = · L3 ≠ · C′≈C нет · причина: **derived-only**
- USER[1]: добрый день курьера на адрес добролюбова 50 квартира 193 стоп правильно добролюбова 22 квартира 193 это в можга это кузнецова ольга телефон 8-961-473-24-80
- USER[2]: в любой день с девяти до шести
- seen LOC `добролюбова 50 квартира 193` → `улица Осиновая 113, кв. 82`
- seen LOC `добролюбова 22 квартира 193` → `улица Речная 68, кв. 57`
- seen NAME `кузнецова ольга` → `Котова Галина`
- seen PHONE `8-961-473-24-80` → `+79964042896`
- C: `courier_book` {'address': {'locality': 'Можга', 'street': 'Добролюбова', 'building': '22', 'sflat': '193'}, 'contact': {'name': 'Кузнецова Ольга', 'phone': '+79614732480'}, 'interval': {'from': '2026-09-04T09:00:0…
- C: `crm_upsert_contact` {'contact': {'last_name': 'Кузнецова', 'first_name': 'Ольга', 'initials': 'О.', 'name_latin': 'Kuznetsova Olga', 'phone': '+79614732480', 'gender': 'F', 'address': {'city': 'Можга', 'street': 'Доброл…
- I: `courier_book` written={'address': {'locality': 'Можга', 'street': 'Речная', 'building': '68', 'sflat': '57'}, 'contact': {'name': 'Котова Галина', 'phone': '+79964042896'}, 'interval': {'from': '2026-09-04T09:00:00+04:00', 'to': '2026-09-04T18:00:00+04:00'}} → restored={'address': {'locality': 'Можга', 'street': 'добролюбова', 'building': '22', 'sflat': '193'}, 'contact': {'name': 'кузнецова ольга', 'phone': '+79614732480'}, 'interval': {'from': '2026-09-04T09:00:00+04:00', 'to': '2026-09-04T18:00:00+04:00'}}
- I: `crm_upsert_contact` written={'contact': {'last_name': 'Котова', 'first_name': 'Галина', 'gender': 'F', 'initials': 'Г.', 'name_latin': 'Kotova Galina', 'phone': '+79964042896', 'address': {'city': 'Можга', 'street': 'Речная', 'house': '68', 'flat': '57'}}} → restored={'contact': {'last_name': 'кузнецова', 'first_name': 'ольга', 'gender': 'F', 'initials': 'Г.', 'name_latin': 'Kuznetsova Olga', 'phone': '+79614732480', 'address': {'city': 'Можга', 'street': 'добролюбова', 'house': '22', 'flat': '193'}}}
- C′: `courier_book` {'address': {'locality': 'Можга', 'street': 'Добролюбова', 'building': '22', 'sflat': '193'}, 'contact': {'name': 'Кузнецова Ольга', 'phone': '+79614732480'}, 'interval': {'from': '2026-09-04T09:00:0…
- C′: `crm_upsert_contact` {'contact': {'last_name': 'Кузнецова', 'first_name': 'Ольга', 'initials': 'О.', 'name_latin': 'Kuznetsova Olga', 'phone': '+79614732480', 'address': {'city': 'Можга', 'street': 'Добролюбова', 'house'…
- FIELD `crm_upsert_contact.contact.initials` [derived/from_substitute → derived] C=`О.` I=`Г.` · значение выведено из ПОДМЕНЫ; восстановление недостижимо
- REPLY I: Оформляю всё прямо сейчас! Всё готово! Вот что сделано: 🚚 **Курьер вызван** (заявка `clm-1`) - **Адрес:** г. Можга, добролюбова 22 квартира 193 - **Получатель:** кузнецова ольга, 8-961-473-24-80 - **Интервал:** сегодня, 4 сентября, с 09:00 до 18:00 👤 **Карточка клиента** обновлена в CRM. Если понад…

## correction-013|0 · correction · sloppy · L1 = · L3 ≠ · C′≈C да · причина: **other**
- USER[1]: добрый курьера на мяаковского 11 квартира 197 ой нет правильно маяковского 163 квартира 197 это в сарапул это миллер валерия телефлн 89502880554
- USER[2]: в любой день с девяти до шетси
- seen LOC `мяаковского 11 квартира 197` → `улица Вязовая 86, кв. 150`
- seen LOC `маяковского 163 квартира 197` → `улица Тополиная 53, кв. 62`
- seen NAME `миллер валерия` → `Юдина Ева`
- seen PHONE `89502880554` → `+79561766136`
- C: `courier_book` {'address': {'locality': 'Сарапул', 'street': 'Маяковского', 'building': '163', 'sflat': '197'}, 'contact': {'name': 'Миллер Валерия', 'phone': '+79502880554'}, 'interval': {'from': '2026-09-04T09:00…
- C: `crm_upsert_contact` {'contact': {'last_name': 'Миллер', 'first_name': 'Валерия', 'initials': 'В.', 'name_latin': 'Miller Valeria', 'gender': 'F', 'phone': '+79502880554', 'address': {'city': 'Сарапул', 'street': 'Маяков…
- I: `courier_book` written={'address': {'locality': 'Сарапул', 'street': 'Тополиная', 'building': '53', 'sflat': '62'}, 'contact': {'name': 'Юдина Ева', 'phone': '+79561766136'}, 'interval': {'from': '2026-09-04T09:00:00+04:00', 'to': '2026-09-04T18:00:00+04:00'}} → restored={'address': {'locality': 'Сарапул', 'street': 'маяковского', 'building': '163', 'sflat': '197'}, 'contact': {'name': 'миллер валерия', 'phone': '+79502880554'}, 'interval': {'from': '2026-09-04T09:00:00+04:00', 'to': '2026-09-04T18:00:00+04:00'}}
- I: `crm_upsert_contact` written={'contact': {'last_name': 'Юдина', 'first_name': 'Ева', 'initials': 'Е.', 'name_latin': 'Yudina Eva', 'gender': 'F', 'phone': '+79561766136', 'address': {'city': 'Сарапул', 'street': 'Тополиная', 'house': '53', 'flat': '62'}}} → restored={'contact': {'last_name': 'миллер', 'first_name': 'валерия', 'initials': 'Е.', 'name_latin': 'Miller Valeriia', 'gender': 'F', 'phone': '+79502880554', 'address': {'city': 'Сарапул', 'street': 'маяковского', 'house': '163', 'flat': '197'}}}
- C′: `courier_book` {'address': {'locality': 'Сарапул', 'street': 'Маяковского', 'building': '163', 'sflat': '197'}, 'contact': {'name': 'Миллер Валерия', 'phone': '+79502880554'}, 'interval': {'from': '2026-09-04T09:00…
- C′: `crm_upsert_contact` {'contact': {'last_name': 'Миллер', 'first_name': 'Валерия', 'gender': 'F', 'phone': '+79502880554', 'initials': 'В.', 'name_latin': 'Miller Valeria', 'address': {'city': 'Сарапул', 'street': 'Маяков…
- FIELD `crm_upsert_contact.contact.initials` [derived/from_substitute → derived] C=`В.` I=`Е.` · значение выведено из ПОДМЕНЫ; восстановление недостижимо
- FIELD `crm_upsert_contact.contact.name_latin` [other/misderived → name_partial] C=`Miller Valeria` I=`Miller Valeriia`
- REPLY I: Отлично, оформляю сразу всё! Всё готово! ✅ **Курьер вызван** (заявка `clm-1`): - 📍 Сарапул, маяковского 163 квартира 197 - 👤 миллер валерия, 89502880554 - 🕘 Сегодня, 04.09.2026, с 09:00 до 18:00 **Карточка клиента** в CRM создана/обновлена. Если что-то нужно изменить — говорите! 😊

## correction-013|1 · correction · sloppy · L1 = · L3 ≠ · C′≈C да · причина: **other**
- USER[1]: добрый курьера на мяаковского 11 квартира 197 ой нет правильно маяковского 163 квартира 197 это в сарапул это миллер валерия телефлн 89502880554
- USER[2]: в любой день с девяти до шетси
- seen LOC `мяаковского 11 квартира 197` → `улица Лавандовая 20, кв. 227`
- seen LOC `маяковского 163 квартира 197` → `улица Мятная 109, кв. 80`
- seen NAME `миллер валерия` → `Осипова Варвара`
- seen PHONE `89502880554` → `+79227915333`
- C: `courier_book` {'address': {'locality': 'Сарапул', 'street': 'Маяковского', 'building': '163', 'sflat': '197'}, 'contact': {'name': 'Миллер Валерия', 'phone': '+79502880554'}, 'interval': {'from': '2026-09-04T09:00…
- C: `crm_upsert_contact` {'contact': {'last_name': 'Миллер', 'first_name': 'Валерия', 'initials': 'В.', 'name_latin': 'Miller Valeria', 'gender': 'F', 'phone': '+79502880554', 'address': {'city': 'Сарапул', 'street': 'Маяков…
- I: `courier_book` written={'address': {'locality': 'Сарапул', 'street': 'Мятная', 'building': '109', 'sflat': '80'}, 'contact': {'name': 'Осипова Варвара', 'phone': '+79227915333'}, 'interval': {'from': '2026-09-04T09:00:00+04:00', 'to': '2026-09-04T18:00:00+04:00'}} → restored={'address': {'locality': 'Сарапул', 'street': 'маяковского', 'building': '163', 'sflat': '197'}, 'contact': {'name': 'миллер валерия', 'phone': '+79502880554'}, 'interval': {'from': '2026-09-04T09:00:00+04:00', 'to': '2026-09-04T18:00:00+04:00'}}
- I: `crm_upsert_contact` written={'contact': {'last_name': 'Осипова', 'first_name': 'Варвара', 'initials': 'В.', 'name_latin': 'Osipova Varvara', 'phone': '+79227915333', 'address': {'city': 'Сарапул', 'street': 'Мятная', 'house': '109', 'flat': '80'}}} → restored={'contact': {'last_name': 'миллер', 'first_name': 'валерия', 'initials': 'В.', 'name_latin': 'Miller Valeriia', 'phone': '+79502880554', 'address': {'city': 'Сарапул', 'street': 'маяковского', 'house': '163', 'flat': '197'}}}
- C′: `courier_book` {'address': {'locality': 'Сарапул', 'street': 'Маяковского', 'building': '163', 'sflat': '197'}, 'contact': {'name': 'Миллер Валерия', 'phone': '+79502880554'}, 'interval': {'from': '2026-09-04T09:00…
- C′: `crm_upsert_contact` {'contact': {'last_name': 'Миллер', 'first_name': 'Валерия', 'gender': 'F', 'phone': '+79502880554', 'initials': 'В.', 'name_latin': 'Miller Valeria', 'address': {'city': 'Сарапул', 'street': 'Маяков…
- FIELD `crm_upsert_contact.contact.gender` [absent → absent:gender] C=`F` I=``
- FIELD `crm_upsert_contact.contact.name_latin` [other/misderived → name_partial] C=`Miller Valeria` I=`Miller Valeriia`
- REPLY I: Оформляю курьера и карточку клиента одновременно! Всё готово! 🎉 **Курьер вызван** (заявка `clm-1`): - 📍 Сарапул, маяковского 163 квартира 197 - 👤 миллер валерия, 89502880554 - 🕘 Сегодня, 04.09.2026, с 09:00 до 18:00 **Карточка клиента** в CRM также создана/обновлена. Если нужно что-то ещё — обращай…

## correction-016|0 · correction · chat · L1 = · L3 ≠ · C′≈C нет · причина: **derived-only**
- USER[1]: курьера на адрес химзаводская 31 кв 170 стоп правильно химзаводская 3кв170 это в колпино это морозов леонид телефон 89827992458
- USER[2]: в четверг после обеда
- seen LOC `химзаводская 31 кв 170` → `улица Буковая 15, кв. 182`
- seen LOC `химзаводская 3кв170` → `улица Осиновая 46, кв. 98`
- seen NAME `морозов леонид` → `Цветков Тимофей`
- seen PHONE `89827992458` → `+79847219384`
- C: `courier_book` {'address': {'locality': 'Колпино', 'street': 'Химзаводская', 'building': '3', 'sflat': '170'}, 'contact': {'name': 'Морозов Леонид', 'phone': '+79827992458'}, 'interval': {'from': '2026-09-10T13:00:…
- C: `crm_upsert_contact` {'contact': {'last_name': 'Морозов', 'first_name': 'Леонид', 'initials': 'Л.', 'name_latin': 'Morozov Leonid', 'phone': '+79827992458', 'address': {'city': 'Колпино', 'street': 'Химзаводская', 'house…
- I: `courier_book` written={'address': {'locality': 'Колпино', 'street': 'Осиновая', 'building': '46', 'sflat': '98'}, 'contact': {'name': 'Цветков Тимофей', 'phone': '+79847219384'}, 'interval': {'from': '2026-09-10T14:00:00+03:00', 'to': '2026-09-10T18:00:00+03:00'}} → restored={'address': {'locality': 'Колпино', 'street': 'химзаводская', 'building': '3', 'sflat': '170'}, 'contact': {'name': 'морозов леонид', 'phone': '+79827992458'}, 'interval': {'from': '2026-09-10T14:00:00+03:00', 'to': '2026-09-10T18:00:00+03:00'}}
- I: `crm_upsert_contact` written={'contact': {'first_name': 'Тимофей', 'last_name': 'Цветков', 'phone': '+79847219384', 'gender': 'M', 'initials': 'Т.', 'name_latin': 'Tsvetkov Timofey', 'address': {'city': 'Колпино', 'street': 'Осиновая', 'house': '46', 'flat': '98'}}} → restored={'contact': {'first_name': 'леонид', 'last_name': 'морозов', 'phone': '+79827992458', 'gender': 'M', 'initials': 'Т.', 'name_latin': 'Morozov Leonid', 'address': {'city': 'Колпино', 'street': 'химзаводская', 'house': '3', 'flat': '170'}}}
- C′: `courier_book` {'address': {'locality': 'Колпино', 'street': 'Химзаводская', 'building': '3', 'sflat': '170'}, 'contact': {'name': 'Морозов Леонид', 'phone': '+79827992458'}, 'interval': {'from': '2026-09-10T13:00:…
- C′: `crm_upsert_contact` {'contact': {'last_name': 'Морозов', 'first_name': 'Леонид', 'initials': 'Л.', 'name_latin': 'Morozov Leonid', 'gender': 'M', 'phone': '+79827992458', 'address': {'city': 'Колпино', 'street': 'Химзав…
- FIELD `crm_upsert_contact.contact.gender` [extra → extra:gender] C=`` I=`M`
- FIELD `crm_upsert_contact.contact.initials` [derived/from_substitute → derived] C=`Л.` I=`Т.` · значение выведено из ПОДМЕНЫ; восстановление недостижимо
- REPLY I: Сегодня пятница, 5 сентября — значит, **ближайший четверг** — **10 сентября**. Возьму интервал «после обеда»: **14:00–18:00**. Оформляю! Всё готово! ✅ **Курьер вызван** (заявка `clm-1`): - 📍 Колпино, химзаводская 3кв170 - 👤 морозов леонид, 89827992458 - 🗓 10 сентября, с 14:00 до 18:00 Карточка клие…

## correction-016|1 · correction · chat · L1 ≠ · L3 ≠ · C′≈C да · причина: **partial-call**
- USER[1]: курьера на адрес химзаводская 31 кв 170 стоп правильно химзаводская 3кв170 это в колпино это морозов леонид телефон 89827992458
- USER[2]: в четверг после обеда
- seen LOC `химзаводская 31 кв 170` → `улица Вязовая 67, кв. 154`
- seen LOC `химзаводская 3кв170` → `улица Кедровая 127, кв. 169`
- seen NAME `морозов леонид` → `Тарасов Савва`
- seen PHONE `89827992458` → `+79056974622`
- C: `courier_book` {'address': {'locality': 'Колпино', 'street': 'Химзаводская', 'building': '3', 'sflat': '170'}, 'contact': {'name': 'Морозов Леонид', 'phone': '+79827992458'}, 'interval': {'from': '2026-09-10T13:00:…
- C: `crm_upsert_contact` {'contact': {'last_name': 'Морозов', 'first_name': 'Леонид', 'initials': 'Л.', 'name_latin': 'Morozov Leonid', 'phone': '+79827992458', 'gender': 'M', 'address': {'city': 'Колпино', 'street': 'Химзав…
- I: `courier_book` written={'address': {'locality': 'Колпино', 'street': 'Кедровая', 'building': '127', 'sflat': '169'}, 'contact': {'name': 'Тарасов Савва', 'phone': '+79056974622'}, 'interval': {'from': '2026-09-10T13:00:00+03:00', 'to': '2026-09-10T18:00:00+03:00'}} → restored={'address': {'locality': 'Колпино', 'street': 'химзаводская', 'building': '3', 'sflat': '170'}, 'contact': {'name': 'морозов леонид', 'phone': '+79827992458'}, 'interval': {'from': '2026-09-10T13:00:00+03:00', 'to': '2026-09-10T18:00:00+03:00'}}
- C′: `courier_book` {'address': {'locality': 'Колпино', 'street': 'Химзаводская', 'building': '3', 'sflat': '170'}, 'contact': {'name': 'Морозов Леонид', 'phone': '+79827992458'}, 'interval': {'from': '2026-09-10T13:00:…
- C′: `crm_upsert_contact` {'contact': {'last_name': 'Морозов', 'first_name': 'Леонид', 'initials': 'Л.', 'name_latin': 'Morozov Leonid', 'gender': 'M', 'phone': '+79827992458', 'address': {'city': 'Колпино', 'street': 'Химзав…
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
- REPLY I: Принято — четверг, 10 сентября, после обеда (13:00–18:00). Оформляю! Готово! Курьер вызван. 🎉 **Детали заявки:** - 🆔 Номер заявки: **clm-1** - 📍 Адрес: Колпино, химзаводская 3кв170 - 👤 Контакт: морозов леонид, 89827992458 - 📅 Дата и время: **10 сентября (четверг), 13:00–18:00** - Статус: на оценке …

## correction-017|0 · correction · voice_itn · L1 = · L3 ≠ · C′≈C да · причина: **other**
- USER[1]: добрый день курьера на барышникова 34 квартира 164 нет не так правильно барышникова 6 квартира 164 это в глазов это фёдорова юлия телефон 8-960-708-39-07
- USER[2]: завтра с десяти до двух
- seen LOC `барышникова 34 квартира 164` → `улица Барбарисовая 95, кв. 178`
- seen LOC `барышникова 6 квартира 164` → `улица Кленовая 143, кв. 195`
- seen NAME `фёдорова юлия` → `Тарасова Альбина`
- seen PHONE `8-960-708-39-07` → `+79843330964`
- C: `courier_book` {'address': {'locality': 'Глазов', 'street': 'Барышникова', 'building': '6', 'sflat': '164'}, 'contact': {'name': 'Фёдорова Юлия', 'phone': '+79607083907'}, 'interval': {'from': '2026-09-05T10:00:00+…
- C: `crm_upsert_contact` {'contact': {'last_name': 'Фёдорова', 'first_name': 'Юлия', 'initials': 'Ю.', 'name_latin': 'Fedorova Yulia', 'phone': '+79607083907', 'gender': 'F', 'address': {'city': 'Глазов', 'street': 'Барышник…
- I: `courier_book` written={'address': {'locality': 'Глазов', 'street': 'Кленовая', 'building': '143', 'sflat': '195'}, 'contact': {'name': 'Тарасова Альбина', 'phone': '+79843330964'}, 'interval': {'from': '2026-09-05T10:00:00+04:00', 'to': '2026-09-05T14:00:00+04:00'}} → restored={'address': {'locality': 'Глазов', 'street': 'барышникова', 'building': '6', 'sflat': '164'}, 'contact': {'name': 'фёдорова юлия', 'phone': '+79607083907'}, 'interval': {'from': '2026-09-05T10:00:00+04:00', 'to': '2026-09-05T14:00:00+04:00'}}
- I: `crm_upsert_contact` written={'contact': {'last_name': 'Тарасова', 'first_name': 'Альбина', 'initials': 'А.', 'name_latin': 'Tarasova Albina', 'phone': '+79843330964', 'address': {'city': 'Глазов', 'street': 'Кленовая', 'house': '143', 'flat': '195'}}} → restored={'contact': {'last_name': 'фёдорова', 'first_name': 'юлия', 'initials': 'А.', 'name_latin': 'Fedorova Iuliia', 'phone': '+79607083907', 'address': {'city': 'Глазов', 'street': 'барышникова', 'house': '6', 'flat': '164'}}}
- C′: `courier_book` {'address': {'locality': 'Глазов', 'street': 'Барышникова', 'building': '6', 'sflat': '164'}, 'contact': {'name': 'Фёдорова Юлия', 'phone': '+79607083907'}, 'interval': {'from': '2026-09-05T10:00:00+…
- C′: `crm_upsert_contact` {'contact': {'last_name': 'Фёдорова', 'first_name': 'Юлия', 'initials': 'Ю.', 'name_latin': 'Fedorova Yulia', 'gender': 'F', 'phone': '+79607083907', 'address': {'city': 'Глазов', 'street': 'Барышник…
- FIELD `crm_upsert_contact.contact.gender` [absent → absent:gender] C=`F` I=``
- FIELD `crm_upsert_contact.contact.initials` [derived/from_substitute → derived] C=`Ю.` I=`А.` · значение выведено из ПОДМЕНЫ; восстановление недостижимо
- FIELD `crm_upsert_contact.contact.name_latin` [other/misderived → name_partial] C=`Fedorova Yulia` I=`Fedorova Iuliia`
- REPLY I: Оформляю! Запускаю сразу оба действия — вызов курьера и карточку клиента. Всё оформлено! Вот итог: **Вызов курьера** ✅ - 📍 Глазов, барышникова 6 квартира 164 - 👤 фёдорова юлия, 8-960-708-39-07 - 🗓 5 сентября, с 10:00 до 14:00 **Карточка клиента в CRM** ✅ — создана/обновлена. Если что-то нужно измен…

## correction-017|1 · correction · voice_itn · L1 = · L3 ≠ · C′≈C нет · причина: **other**
- USER[1]: добрый день курьера на барышникова 34 квартира 164 нет не так правильно барышникова 6 квартира 164 это в глазов это фёдорова юлия телефон 8-960-708-39-07
- USER[2]: завтра с десяти до двух
- seen LOC `барышникова 34 квартира 164` → `улица Абрикосовая 148, кв. 47`
- seen LOC `барышникова 6 квартира 164` → `улица Осиновая 24, кв. 62`
- seen NAME `фёдорова юлия` → `Тихонова Надежда`
- seen PHONE `8-960-708-39-07` → `+79500865886`
- C: `courier_book` {'address': {'locality': 'Глазов', 'street': 'Барышникова', 'building': '6', 'sflat': '164'}, 'contact': {'name': 'Фёдорова Юлия', 'phone': '+79607083907'}, 'interval': {'from': '2026-09-05T10:00:00+…
- C: `crm_upsert_contact` {'contact': {'last_name': 'Фёдорова', 'first_name': 'Юлия', 'initials': 'Ю.', 'name_latin': 'Fedorova Yulia', 'gender': 'F', 'phone': '+79607083907', 'address': {'city': 'Глазов', 'street': 'Барышник…
- I: `courier_book` written={'address': {'locality': 'Глазов', 'street': 'Осиновая', 'building': '24', 'sflat': '62'}, 'contact': {'name': 'Тихонова Надежда', 'phone': '+79500865886'}, 'interval': {'from': '2026-09-05T10:00:00+04:00', 'to': '2026-09-05T14:00:00+04:00'}} → restored={'address': {'locality': 'Глазов', 'street': 'барышникова', 'building': '6', 'sflat': '164'}, 'contact': {'name': 'фёдорова юлия', 'phone': '+79607083907'}, 'interval': {'from': '2026-09-05T10:00:00+04:00', 'to': '2026-09-05T14:00:00+04:00'}}
- I: `crm_upsert_contact` written={'contact': {'last_name': 'Тихонова', 'first_name': 'Надежда', 'initials': 'Н.', 'name_latin': 'Tikhonova Nadezhda', 'gender': 'F', 'phone': '+79500865886', 'address': {'city': 'Глазов', 'street': 'Осиновая', 'house': '24', 'flat': '62'}}} → restored={'contact': {'last_name': 'фёдорова', 'first_name': 'юлия', 'initials': 'Н.', 'name_latin': 'Fedorova Iuliia', 'gender': 'F', 'phone': '+79607083907', 'address': {'city': 'Глазов', 'street': 'барышникова', 'house': '6', 'flat': '164'}}}
- C′: `courier_book` {'address': {'locality': 'Глазов', 'street': 'Барышникова', 'building': '6', 'sflat': '164'}, 'contact': {'name': 'Фёдорова Юлия', 'phone': '+79607083907'}, 'interval': {'from': '2026-09-05T10:00:00+…
- FIELD `crm_upsert_contact.contact.initials` [derived/from_substitute → derived] C=`Ю.` I=`Н.` · значение выведено из ПОДМЕНЫ; восстановление недостижимо
- FIELD `crm_upsert_contact.contact.name_latin` [other/misderived → name_partial] C=`Fedorova Yulia` I=`Fedorova Iuliia`
- REPLY I: Принято! Оформляю всё сразу — вызов курьера и карточку клиента. Всё готово! ✅ **Вызов курьера** — оформлен (№ clm-1) - 📍 г. Глазов, барышникова 6 квартира 164 - 👤 фёдорова юлия, 8-960-708-39-07 - 🕙 5 сентября, с 10:00 до 14:00 **Карточка клиента** — создана/обновлена в CRM. Если нужно что-то ещё — …

## correction-018|0 · correction · voice_raw · L1 ≠ · L3 ≠ · C′≈C нет · причина: **partial-call**
- USER[1]: добрый день курьера на адрес кирочная двадцать пять квартира сто пятьдесят ой нет правильно кирочная сто семьдесят семь квартира сто пятьдесят это в воткинск это захаров владислав телефон восем девятьсот двадцать пяять семьсот двадцать трииста четырнадцать пять
- USER[2]: завтра с десятии до двух
- seen LOC `кирочная двадцать пять квартира сто пятьдесят` → `улица Еловая 47, кв. 52`
- seen LOC `кирочная сто семьдесят семь квартира сто пятьдесят` → `улица Еловая 104, кв. 161`
- seen NAME `захаров владислав` → `Чижов Юрий`
- seen PHONE `восем девятьсот двадцать пяять семьсот двадцать трииста четырнадцать пять` → `+79346552166`
- C: `courier_book` {'address': {'locality': 'Воткинск', 'street': 'Кирочная', 'building': '177', 'sflat': '150'}, 'contact': {'name': 'Захаров Владислав', 'phone': '+79257231145'}, 'interval': {'from': '2026-09-05T10:0…
- C: `crm_upsert_contact` {'contact': {'last_name': 'Захаров', 'first_name': 'Владислав', 'initials': 'В.', 'name_latin': 'Zakharov Vladislav', 'gender': 'M', 'phone': '+79257231145', 'address': {'city': 'Воткинск', 'street':…
- I: `courier_book` written={'address': {'locality': 'Воткинск', 'street': 'Еловая', 'building': '104', 'sflat': '161'}, 'contact': {'name': 'Чижов Юрий', 'phone': '+79346552166'}, 'interval': {'from': '2026-09-05T10:00:00+04:00', 'to': '2026-09-05T14:00:00+04:00'}} → restored={'address': {'locality': 'Воткинск', 'street': 'кирочная', 'building': '177', 'sflat': '150'}, 'contact': {'name': 'захаров владислав', 'phone': '+79257203145'}, 'interval': {'from': '2026-09-05T10:00:00+04:00', 'to': '2026-09-05T14:00:00+04:00'}}
- C′: — (без вызовов)
- FIELD `courier_book.contact.phone` [control_erred/i4 → control_erred] C=`+79257231145` I=`+79257203145` · контроль ошибся; шлюз восстановил эталон корпуса
- FIELD `crm_upsert_contact.contact.address.city` [absent → absent:city] C=`Воткинск` I=``
- FIELD `crm_upsert_contact.contact.address.flat` [absent → absent:flat] C=`150` I=``
- FIELD `crm_upsert_contact.contact.address.house` [absent → absent:house] C=`177` I=``
- FIELD `crm_upsert_contact.contact.address.street` [absent → absent:street] C=`Кирочная` I=``
- FIELD `crm_upsert_contact.contact.first_name` [absent → absent:first_name] C=`Владислав` I=``
- FIELD `crm_upsert_contact.contact.gender` [absent → absent:gender] C=`M` I=``
- FIELD `crm_upsert_contact.contact.initials` [absent → absent:initials] C=`В.` I=``
- FIELD `crm_upsert_contact.contact.last_name` [absent → absent:last_name] C=`Захаров` I=``
- FIELD `crm_upsert_contact.contact.name_latin` [absent → absent:name_latin] C=`Zakharov Vladislav` I=``
- FIELD `crm_upsert_contact.contact.phone` [absent → absent:phone] C=`+79257231145` I=``
- REPLY I: Отлично, оформляю! Готово! Курьер оформлен ✅ **Детали заказа (clm-1):** - 📍 Воткинск, кирочная сто семьдесят семь квартира сто пятьдесят - 👤 захаров владислав, восем девятьсот двадцать пяять семьсот двадцать трииста четырнадцать пять - 🗓 5 сентября 2026, с 10:00 до 14:00 Если нужно что-то изменить …

## correction-018|1 · correction · voice_raw · L1 = · L3 ≠ · C′≈C да · причина: **other**
- USER[1]: добрый день курьера на адрес кирочная двадцать пять квартира сто пятьдесят ой нет правильно кирочная сто семьдесят семь квартира сто пятьдесят это в воткинск это захаров владислав телефон восем девятьсот двадцать пяять семьсот двадцать трииста четырнадцать пять
- USER[2]: завтра с десятии до двух
- seen LOC `кирочная двадцать пять квартира сто пятьдесят` → `улица Ивовая 192, кв. 182`
- seen LOC `кирочная сто семьдесят семь квартира сто пятьдесят` → `улица Кленовая 192, кв. 81`
- seen NAME `захаров владислав` → `Цветков Денис`
- seen PHONE `восем девятьсот двадцать пяять семьсот двадцать трииста четырнадцать пять` → `+79828550688`
- C: `courier_book` {'address': {'locality': 'Воткинск', 'street': 'Кирочная', 'building': '177', 'sflat': '150'}, 'contact': {'name': 'Захаров Владислав', 'phone': '+79257231145'}, 'interval': {'from': '2026-09-05T10:0…
- C: `crm_upsert_contact` {'contact': {'last_name': 'Захаров', 'first_name': 'Владислав', 'initials': 'В.', 'name_latin': 'Zakharov Vladislav', 'gender': 'M', 'phone': '+79257231145', 'address': {'city': 'Воткинск', 'street':…
- I: `courier_book` written={'address': {'locality': 'Воткинск', 'street': 'Кленовая', 'building': '192', 'sflat': '81'}, 'contact': {'name': 'Цветков Денис', 'phone': '+79828550688'}, 'interval': {'from': '2026-09-05T10:00:00+04:00', 'to': '2026-09-05T14:00:00+04:00'}} → restored={'address': {'locality': 'Воткинск', 'street': 'кирочная', 'building': '177', 'sflat': '150'}, 'contact': {'name': 'захаров владислав', 'phone': '+79257203145'}, 'interval': {'from': '2026-09-05T10:00:00+04:00', 'to': '2026-09-05T14:00:00+04:00'}}
- I: `crm_upsert_contact` written={'contact': {'first_name': 'Денис', 'last_name': 'Цветков', 'initials': 'Д.', 'name_latin': 'Tsvetkov Denis', 'phone': '+79828550688', 'address': {'city': 'Воткинск', 'street': 'Кленовая', 'house': '192', 'flat': '81'}}} → restored={'contact': {'first_name': 'владислав', 'last_name': 'захаров', 'initials': 'Д.', 'name_latin': 'Zakharov Vladislav', 'phone': '+79257203145', 'address': {'city': 'Воткинск', 'street': 'кирочная', 'house': '177', 'flat': '150'}}}
- C′: `courier_book` {'address': {'locality': 'Воткинск', 'street': 'Кирочная', 'building': '177', 'sflat': '150'}, 'contact': {'name': 'Захаров Владислав', 'phone': '+79257231145'}, 'interval': {'from': '2026-09-05T10:0…
- C′: `crm_upsert_contact` {'contact': {'last_name': 'Захаров', 'first_name': 'Владислав', 'initials': 'В.', 'name_latin': 'Zakharov Vladislav', 'gender': 'M', 'phone': '+79257231145', 'address': {'city': 'Воткинск', 'street':…
- FIELD `courier_book.contact.phone` [control_erred/i4 → control_erred] C=`+79257231145` I=`+79257203145` · контроль ошибся; шлюз восстановил эталон корпуса
- FIELD `crm_upsert_contact.contact.gender` [absent → absent:gender] C=`M` I=``
- FIELD `crm_upsert_contact.contact.initials` [derived/from_substitute → derived] C=`В.` I=`Д.` · значение выведено из ПОДМЕНЫ; восстановление недостижимо
- FIELD `crm_upsert_contact.contact.phone` [control_erred/i4 → control_erred] C=`+79257231145` I=`+79257203145` · контроль ошибся; шлюз восстановил эталон корпуса
- REPLY I: Отлично, оформляю! Всё оформлено! Вот итог: **Вызов курьера** — заявка `clm-1` - 📍 Воткинск, кирочная сто семьдесят семь квартира сто пятьдесят - 👤 захаров владислав, восем девятьсот двадцать пяять семьсот двадцать трииста четырнадцать пять - 🕙 5 сентября 2026, с 10:00 до 14:00 Карточка клиента в C…

## correction-021|0 · correction · sloppy · L1 = · L3 ≠ · C′≈C нет · причина: **derived-only**
- USER[1]: привет курьера на добролюбова 29кв73 простите ошиблась правильно добролюбова 1кв73 это в можга это новиков игорь телефон 8-999-106-11-83
- USER[2]: в любой день с девяти до шести
- seen LOC `добролюбова 29кв73` → `улицы Родниковой 70, кв. 107`
- seen LOC `добролюбова 1кв73` → `улицы Еловой 110, кв. 39`
- seen NAME `новиков игорь` → `Сазонов Леонид`
- seen PHONE `8-999-106-11-83` → `+79766885283`
- C: `courier_book` {'address': {'locality': 'Можга', 'street': 'Добролюбова', 'building': '1', 'sflat': '73'}, 'contact': {'name': 'Новиков Игорь', 'phone': '+79991061183'}, 'interval': {'from': '2026-09-04T09:00:00+04…
- C: `crm_upsert_contact` {'contact': {'last_name': 'Новиков', 'first_name': 'Игорь', 'initials': 'И.', 'name_latin': 'Novikov Igor', 'gender': 'M', 'phone': '+79991061183', 'address': {'city': 'Можга', 'street': 'Добролюбова…
- I: `courier_book` written={'address': {'locality': 'Можга', 'street': 'Еловая', 'building': '110', 'sflat': '39'}, 'contact': {'name': 'Сазонов Леонид', 'phone': '+79766885283'}, 'interval': {'from': '2026-09-04T09:00:00+04:00', 'to': '2026-09-04T18:00:00+04:00'}} → restored={'address': {'locality': 'Можга', 'street': 'добролюбова', 'building': '1', 'sflat': '73'}, 'contact': {'name': 'новиков игорь', 'phone': '+79991061183'}, 'interval': {'from': '2026-09-04T09:00:00+04:00', 'to': '2026-09-04T18:00:00+04:00'}}
- I: `crm_upsert_contact` written={'contact': {'last_name': 'Сазонов', 'first_name': 'Леонид', 'initials': 'Л.', 'name_latin': 'Sazonov Leonid', 'gender': 'M', 'phone': '+79766885283', 'address': {'city': 'Можга', 'street': 'Еловая', 'house': '110', 'flat': '39'}}} → restored={'contact': {'last_name': 'новиков', 'first_name': 'игорь', 'initials': 'Л.', 'name_latin': 'Novikov Igor', 'gender': 'M', 'phone': '+79991061183', 'address': {'city': 'Можга', 'street': 'добролюбова', 'house': '1', 'flat': '73'}}}
- C′: `courier_book` {'address': {'locality': 'Можга', 'street': 'Добролюбова', 'building': '1', 'sflat': '73'}, 'contact': {'name': 'Новиков Игорь', 'phone': '+79991061183'}, 'interval': {'from': '2026-09-04T09:00:00+04…
- C′: `crm_upsert_contact` {'contact': {'first_name': 'Игорь', 'last_name': 'Новиков', 'phone': '+79991061183', 'initials': 'И.', 'name_latin': 'Novikov Igor', 'address': {'city': 'Можга', 'street': 'Добролюбова', 'house': '1'…
- FIELD `crm_upsert_contact.contact.initials` [derived/from_substitute → derived] C=`И.` I=`Л.` · значение выведено из ПОДМЕНЫ; восстановление недостижимо
- REPLY I: Отлично, оформляю заявку на сегодня с 9:00 до 18:00! Всё готово! Вот итог: **🚚 Курьер вызван** (заявка `clm-1`) - **Адрес:** Можга, добролюбова 1кв73 - **Получатель:** новиков игорь, 8-999-106-11-83 - **Время:** сегодня, 4 сентября, с 09:00 до 18:00 **📋 Карточка клиента** обновлена в CRM. Если что-…

## correction-021|1 · correction · sloppy · L1 ≠ · L3 ≠ · C′≈C нет · причина: **partial-call**
- USER[1]: привет курьера на добролюбова 29кв73 простите ошиблась правильно добролюбова 1кв73 это в можга это новиков игорь телефон 8-999-106-11-83
- USER[2]: в любой день с девяти до шести
- seen LOC `добролюбова 29кв73` → `улицы Берёзовой 190, кв. 144`
- seen LOC `добролюбова 1кв73` → `улицы Кленовой 4, кв. 117`
- seen NAME `новиков игорь` → `Фомин Филипп`
- seen PHONE `8-999-106-11-83` → `+79912616514`
- C: `courier_book` {'address': {'locality': 'Можга', 'street': 'Добролюбова', 'building': '1', 'sflat': '73'}, 'contact': {'name': 'Новиков Игорь', 'phone': '+79991061183'}, 'interval': {'from': '2026-09-04T09:00:00+04…
- C: `crm_upsert_contact` {'contact': {'last_name': 'Новиков', 'first_name': 'Игорь', 'initials': 'И.', 'name_latin': 'Novikov Igor', 'phone': '+79991061183', 'address': {'city': 'Можга', 'street': 'Добролюбова', 'house': '1'…
- I: `courier_book` written={'address': {'locality': 'Можга', 'street': 'Кленовая', 'building': '4', 'sflat': '117'}, 'contact': {'name': 'Фомин Филипп', 'phone': '+79912616514'}, 'interval': {'from': '2026-09-04T09:00:00+04:00', 'to': '2026-09-04T18:00:00+04:00'}} → restored={'address': {'locality': 'Можга', 'street': 'добролюбова', 'building': '1', 'sflat': '73'}, 'contact': {'name': 'новиков игорь', 'phone': '+79991061183'}, 'interval': {'from': '2026-09-04T09:00:00+04:00', 'to': '2026-09-04T18:00:00+04:00'}}
- C′: `courier_book` {'address': {'locality': 'Можга', 'street': 'Добролюбова', 'building': '1', 'sflat': '73'}, 'contact': {'name': 'Новиков Игорь', 'phone': '+79991061183'}, 'interval': {'from': '2026-09-04T09:00:00+04…
- C′: `crm_upsert_contact` {'contact': {'first_name': 'Игорь', 'last_name': 'Новиков', 'phone': '+79991061183', 'gender': 'M', 'initials': 'И.', 'name_latin': 'Novikov Igor', 'address': {'city': 'Можга', 'street': 'Добролюбова…
- FIELD `crm_upsert_contact.contact.address.city` [absent → absent:city] C=`Можга` I=``
- FIELD `crm_upsert_contact.contact.address.flat` [absent → absent:flat] C=`73` I=``
- FIELD `crm_upsert_contact.contact.address.house` [absent → absent:house] C=`1` I=``
- FIELD `crm_upsert_contact.contact.address.street` [absent → absent:street] C=`Добролюбова` I=``
- FIELD `crm_upsert_contact.contact.first_name` [absent → absent:first_name] C=`Игорь` I=``
- FIELD `crm_upsert_contact.contact.initials` [absent → absent:initials] C=`И.` I=``
- FIELD `crm_upsert_contact.contact.last_name` [absent → absent:last_name] C=`Новиков` I=``
- FIELD `crm_upsert_contact.contact.name_latin` [absent → absent:name_latin] C=`Novikov Igor` I=``
- FIELD `crm_upsert_contact.contact.phone` [absent → absent:phone] C=`+79991061183` I=``
- REPLY I: Оформляю на сегодня, 4 сентября, с 09:00 до 18:00! Готово! Курьер вызван. 🎉 **Детали заявки:** - 📍 Можга, добролюбова 1кв73 - 👤 новиков игорь, 8-999-106-11-83 - 🕘 Сегодня, 4 сентября, с 09:00 до 18:00 - 🆔 Номер заявки: **clm-1** Если что-то изменится — обращайтесь!

## correction-024|0 · correction · voice_raw · L1 = · L3 ≠ · C′≈C нет · причина: **derived-only**
- USER[1]: здравствуйтее курьера на базисная три квартира сто семьдесят один нет не таак правильно базисная сто пятьдесят пять квартира сто семьдесят один этоо в сортавала этоо морозов леонид телефонто восемь девятьсот шестьдесят девятьсот семь восемьдесят пять девяносто два
- USER[2]: завтра с десяти до двух
- seen LOC `базисная три квартира сто семьдесят один` → `улица Вязовая 5, кв. 91`
- seen LOC `базисная сто пятьдесят пять квартира сто семьдесят один` → `улица Родниковая 91, кв. 225`
- seen NAME `морозов леонид` → `Лебедев Тимофей`
- seen PHONE `восемь девятьсот шестьдесят девятьсот семь восемьдесят пять девяносто два` → `+79539836592`
- C: `courier_book` {'address': {'locality': 'Сортавала', 'street': 'Базисная', 'building': '155', 'sflat': '171'}, 'contact': {'name': 'Морозов Леонид', 'phone': '+79609078592'}, 'interval': {'from': '2026-09-05T10:00:…
- C: `crm_upsert_contact` {'contact': {'last_name': 'Морозов', 'first_name': 'Леонид', 'initials': 'Л.', 'name_latin': 'Morozov Leonid', 'phone': '+79609078592', 'address': {'city': 'Сортавала', 'street': 'Базисная', 'house':…
- I: `courier_book` written={'address': {'locality': 'Сортавала', 'street': 'Родниковая', 'building': '91', 'sflat': '225'}, 'contact': {'name': 'Лебедев Тимофей', 'phone': '+79539836592'}, 'interval': {'from': '2026-09-05T10:00:00+03:00', 'to': '2026-09-05T14:00:00+03:00'}} → restored={'address': {'locality': 'Сортавала', 'street': 'базисная', 'building': '155', 'sflat': '171'}, 'contact': {'name': 'морозов леонид', 'phone': '+79609078592'}, 'interval': {'from': '2026-09-05T10:00:00+03:00', 'to': '2026-09-05T14:00:00+03:00'}}
- I: `crm_upsert_contact` written={'contact': {'last_name': 'Лебедев', 'first_name': 'Тимофей', 'initials': 'Т.', 'name_latin': 'Lebedev Timofey', 'phone': '+79539836592', 'gender': 'M', 'address': {'city': 'Сортавала', 'street': 'Родниковая', 'house': '91', 'flat': '225'}}} → restored={'contact': {'last_name': 'морозов', 'first_name': 'леонид', 'initials': 'Т.', 'name_latin': 'Morozov Leonid', 'phone': '+79609078592', 'gender': 'M', 'address': {'city': 'Сортавала', 'street': 'базисная', 'house': '155', 'flat': '171'}}}
- C′: `courier_book` {'address': {'locality': 'Сортавала', 'street': 'Базисная', 'building': '155', 'sflat': '171'}, 'contact': {'name': 'Морозов Леонид', 'phone': '+79609078592'}, 'interval': {'from': '2026-09-05T10:00:…
- C′: `crm_upsert_contact` {'contact': {'first_name': 'Леонид', 'last_name': 'Морозов', 'gender': 'M', 'initials': 'Л.', 'name_latin': 'Morozov Leonid', 'phone': '+79609078592', 'address': {'city': 'Сортавала', 'street': 'Бази…
- FIELD `crm_upsert_contact.contact.gender` [extra → extra:gender] C=`` I=`M`
- FIELD `crm_upsert_contact.contact.initials` [derived/from_substitute → derived] C=`Л.` I=`Т.` · значение выведено из ПОДМЕНЫ; восстановление недостижимо
- REPLY I: Оформляю всё сразу! Всё готово! ✅ **Курьер вызван** — завтра, 5 сентября, с 10:00 до 14:00 📍 г. Сортавала, базисная сто пятьдесят пять квартира сто семьдесят один 👤 морозов леонид, восемь девятьсот шестьдесят девятьсот семь восемьдесят пять девяносто два 🆔 Заявка: `clm-1` Карточка клиента в CRM так…

## correction-024|1 · correction · voice_raw · L1 = · L3 ≠ · C′≈C да · причина: **derived-only**
- USER[1]: здравствуйтее курьера на базисная три квартира сто семьдесят один нет не таак правильно базисная сто пятьдесят пять квартира сто семьдесят один этоо в сортавала этоо морозов леонид телефонто восемь девятьсот шестьдесят девятьсот семь восемьдесят пять девяносто два
- USER[2]: завтра с десяти до двух
- seen LOC `базисная три квартира сто семьдесят один` → `улица Берёзовая 193, кв. 182`
- seen LOC `базисная сто пятьдесят пять квартира сто семьдесят один` → `улица Полевая 128, кв. 1`
- seen NAME `морозов леонид` → `Беляев Мирослав`
- seen PHONE `восемь девятьсот шестьдесят девятьсот семь восемьдесят пять девяносто два` → `+79410983596`
- C: `courier_book` {'address': {'locality': 'Сортавала', 'street': 'Базисная', 'building': '155', 'sflat': '171'}, 'contact': {'name': 'Морозов Леонид', 'phone': '+79609078592'}, 'interval': {'from': '2026-09-05T10:00:…
- C: `crm_upsert_contact` {'contact': {'last_name': 'Морозов', 'first_name': 'Леонид', 'initials': 'Л.', 'name_latin': 'Morozov Leonid', 'gender': 'M', 'phone': '+79609078592', 'address': {'city': 'Сортавала', 'street': 'Бази…
- I: `courier_book` written={'address': {'locality': 'Сортавала', 'street': 'Полевая', 'building': '128', 'sflat': '1'}, 'contact': {'name': 'Беляев Мирослав', 'phone': '+79410983596'}, 'interval': {'from': '2026-09-05T10:00:00+03:00', 'to': '2026-09-05T14:00:00+03:00'}} → restored={'address': {'locality': 'Сортавала', 'street': 'базисная', 'building': '155', 'sflat': '171'}, 'contact': {'name': 'морозов леонид', 'phone': '+79609078592'}, 'interval': {'from': '2026-09-05T10:00:00+03:00', 'to': '2026-09-05T14:00:00+03:00'}}
- I: `crm_upsert_contact` written={'contact': {'last_name': 'Беляев', 'first_name': 'Мирослав', 'initials': 'М.', 'name_latin': 'Belyaev Miroslav', 'phone': '+79410983596', 'address': {'city': 'Сортавала', 'street': 'Полевая', 'house': '128', 'flat': '1'}}} → restored={'contact': {'last_name': 'морозов', 'first_name': 'леонид', 'initials': 'М.', 'name_latin': 'Morozov Leonid', 'phone': '+79609078592', 'address': {'city': 'Сортавала', 'street': 'базисная', 'house': '155', 'flat': '171'}}}
- C′: `courier_book` {'address': {'locality': 'Сортавала', 'street': 'Базисная', 'building': '155', 'sflat': '171'}, 'contact': {'name': 'Морозов Леонид', 'phone': '+79609078592'}, 'interval': {'from': '2026-09-05T10:00:…
- C′: `crm_upsert_contact` {'contact': {'last_name': 'Морозов', 'first_name': 'Леонид', 'initials': 'Л.', 'name_latin': 'Morozov Leonid', 'gender': 'M', 'phone': '+79609078592', 'address': {'city': 'Сортавала', 'street': 'Бази…
- FIELD `crm_upsert_contact.contact.gender` [absent → absent:gender] C=`M` I=``
- FIELD `crm_upsert_contact.contact.initials` [derived/from_substitute → derived] C=`Л.` I=`М.` · значение выведено из ПОДМЕНЫ; восстановление недостижимо
- REPLY I: Принято! Оформляю вызов курьера и карточку клиента одновременно. Всё готово! Вот итог: - 🚚 **Курьер вызван** — г. Сортавала, базисная сто пятьдесят пять квартира сто семьдесят один, **5 сентября с 10:00 до 14:00** - 👤 **Карточка клиента** морозов леонид создана/обновлена в CRM Если нужно что-то ещё…

## correction-025|0 · correction · voice_itn · L1 = · L3 ≠ · C′≈C да · причина: **derived-only**
- USER[1]: здравствуйте курьера на калашникова дом 65 квартира 143 стоп правильно калашникова 37 квартира 143 это в краснодар это громова марина телефон 89505556677
- USER[2]: в любой день с девяти до шести
- seen LOC `калашникова дом 65 квартира 143` → `улица Берёзовая 152, кв. 194`
- seen LOC `калашникова 37 квартира 143` → `улица Осиновая 191, кв. 28`
- seen NAME `громова марина` → `Шилова Тамара`
- seen PHONE `89505556677` → `+79850224211`
- C: `courier_book` {'address': {'locality': 'Краснодар', 'street': 'Калашникова', 'building': '37', 'sflat': '143'}, 'contact': {'name': 'Громова Марина', 'phone': '+79505556677'}, 'interval': {'from': '2026-09-04T09:0…
- C: `crm_upsert_contact` {'contact': {'last_name': 'Громова', 'first_name': 'Марина', 'phone': '+79505556677', 'initials': 'М.', 'name_latin': 'Gromova Marina', 'address': {'city': 'Краснодар', 'street': 'Калашникова', 'hous…
- I: `courier_book` written={'address': {'locality': 'Краснодар', 'street': 'Осиновая', 'building': '191', 'sflat': '28'}, 'contact': {'name': 'Шилова Тамара', 'phone': '+79850224211'}, 'interval': {'from': '2026-09-04T09:00:00+03:00', 'to': '2026-09-04T18:00:00+03:00'}} → restored={'address': {'locality': 'Краснодар', 'street': 'калашникова', 'building': '37', 'sflat': '143'}, 'contact': {'name': 'громова марина', 'phone': '+79505556677'}, 'interval': {'from': '2026-09-04T09:00:00+03:00', 'to': '2026-09-04T18:00:00+03:00'}}
- I: `crm_upsert_contact` written={'contact': {'last_name': 'Шилова', 'first_name': 'Тамара', 'initials': 'Т.', 'name_latin': 'Shilova Tamara', 'phone': '+79850224211', 'gender': 'F', 'address': {'city': 'Краснодар', 'street': 'Осиновая', 'house': '191', 'flat': '28'}}} → restored={'contact': {'last_name': 'громова', 'first_name': 'марина', 'initials': 'Т.', 'name_latin': 'Gromova Marina', 'phone': '+79505556677', 'gender': 'F', 'address': {'city': 'Краснодар', 'street': 'калашникова', 'house': '37', 'flat': '143'}}}
- C′: `courier_book` {'address': {'locality': 'Краснодар', 'street': 'Калашникова', 'building': '37', 'sflat': '143'}, 'contact': {'name': 'Громова Марина', 'phone': '+79505556677'}, 'interval': {'from': '2026-09-04T09:0…
- C′: `crm_upsert_contact` {'contact': {'last_name': 'Громова', 'first_name': 'Марина', 'initials': 'М.', 'name_latin': 'Gromova Marina', 'phone': '+79505556677', 'address': {'city': 'Краснодар', 'street': 'Калашникова', 'hous…
- FIELD `crm_upsert_contact.contact.gender` [extra → extra:gender] C=`` I=`F`
- FIELD `crm_upsert_contact.contact.initials` [derived/from_substitute → derived] C=`М.` I=`Т.` · значение выведено из ПОДМЕНЫ; восстановление недостижимо
- REPLY I: Оформляю на сегодня, 4 сентября, с 09:00 до 18:00 — и сразу создаю карточку клиента! Всё готово! ✅ **Курьер вызван** (№ clm-1) - 📍 Краснодар, калашникова 37 квартира 143 - 👤 громова марина, 89505556677 - 🕘 Сегодня, 4 сентября, с 09:00 до 18:00 Карточка клиента в CRM также создана. Если нужно что-то…

## correction-025|1 · correction · voice_itn · L1 ≠ · L3 ≠ · C′≈C нет · причина: **derived-only**
- USER[1]: здравствуйте курьера на калашникова дом 65 квартира 143 стоп правильно калашникова 37 квартира 143 это в краснодар это громова марина телефон 89505556677
- USER[2]: в любой день с девяти до шести
- seen LOC `калашникова дом 65 квартира 143` → `улица Абрикосовая 21, кв. 85`
- seen LOC `калашникова 37 квартира 143` → `улица Ольховая 26, кв. 31`
- seen NAME `громова марина` → `Бирюкова Альбина`
- seen PHONE `89505556677` → `+79463540080`
- C: `courier_book` {'address': {'locality': 'Краснодар', 'street': 'Калашникова', 'building': '37', 'sflat': '143'}, 'contact': {'name': 'Громова Марина', 'phone': '+79505556677'}, 'interval': {'from': '2026-09-04T09:0…
- C: `crm_upsert_contact` {'contact': {'last_name': 'Громова', 'first_name': 'Марина', 'initials': 'М.', 'name_latin': 'Gromova Marina', 'phone': '+79505556677', 'address': {'city': 'Краснодар', 'street': 'Калашникова', 'hous…
- I: `crm_upsert_contact` written={'contact': {'last_name': 'Бирюкова', 'first_name': 'Альбина', 'initials': 'А.', 'name_latin': 'Biryukova Albina', 'gender': 'F', 'phone': '+79463540080', 'address': {'city': 'Краснодар', 'street': 'Ольховая', 'house': '26', 'flat': '31'}}} → restored={'contact': {'last_name': 'громова', 'first_name': 'марина', 'initials': 'А.', 'name_latin': 'Gromova Marina', 'gender': 'F', 'phone': '+79505556677', 'address': {'city': 'Краснодар', 'street': 'калашникова', 'house': '37', 'flat': '143'}}}
- I: `courier_book` written={'address': {'locality': 'Краснодар', 'street': 'Ольховая', 'building': '26', 'sflat': '31'}, 'contact': {'name': 'Бирюкова Альбина', 'phone': '+79463540080'}, 'interval': {'from': '2026-09-04T09:00:00+03:00', 'to': '2026-09-04T18:00:00+03:00'}} → restored={'address': {'locality': 'Краснодар', 'street': 'калашникова', 'building': '37', 'sflat': '143'}, 'contact': {'name': 'громова марина', 'phone': '+79505556677'}, 'interval': {'from': '2026-09-04T09:00:00+03:00', 'to': '2026-09-04T18:00:00+03:00'}}
- C′: `courier_book` {'address': {'locality': 'Краснодар', 'street': 'Калашникова', 'building': '37', 'sflat': '143'}, 'contact': {'name': 'Громова Марина', 'phone': '+79505556677'}, 'interval': {'from': '2026-09-04T09:0…
- C′: `crm_upsert_contact` {'contact': {'last_name': 'Громова', 'first_name': 'Марина', 'initials': 'М.', 'name_latin': 'Gromova Marina', 'gender': 'F', 'phone': '+79505556677', 'address': {'city': 'Краснодар', 'street': 'Кала…
- FIELD `crm_upsert_contact.contact.gender` [extra → extra:gender] C=`` I=`F`
- FIELD `crm_upsert_contact.contact.initials` [derived/from_substitute → derived] C=`М.` I=`А.` · значение выведено из ПОДМЕНЫ; восстановление недостижимо
- REPLY I: Оформляю на сегодня, 4 сентября, с 09:00 до 18:00! Курьер вызван ✅ **Детали заказа (clm-1):** - 📍 Краснодар, калашникова 37 квартира 143 - 👤 громова марина, 89505556677 - 🕐 4 сентября, с 09:00 до 18:00 Заявка принята, курьер свяжется с клиентом. Если нужно что-то ещё — обращайтесь!

## correction-030|0 · correction · voice_raw · L1 ≠ · L3 ≠ · C′≈C нет · причина: **partial-call**
- USER[1]: алло курьера наа адрес мончегорская триц три квартира пятьдесят шесть неет не так правильно мончегорская дом сто восемьдесят пять квартира пятьдесят шесть это в сарапул это кузнецов дмитрий телефон восемь девятьсот шестьдесят два восемест восемьдесят восемь девяно девять ноль ноль
- USER[2]: завтра с десятии до двух
- seen LOC `мончегорская триц три квартира пятьдесят шесть` → `улица Липовая 59, кв. 6`
- seen LOC `мончегорская дом сто восемьдесят пять квартира пятьдесят шесть` → `улица Тополиная 16, кв. 94`
- seen NAME `кузнецов дмитрий` → `Жуков Георгий`
- seen PHONE `восемь девятьсот шестьдесят два восемест восемьдесят восемь девяно девять ноль ноль` → `+79971886997`
- C: `courier_book` {'address': {'locality': 'Сарапул', 'street': 'Мончегорская', 'building': '185', 'sflat': '56'}, 'contact': {'name': 'Кузнецов Дмитрий', 'phone': '+79628889900'}, 'interval': {'from': '2026-09-05T10:…
- C: `crm_upsert_contact` {'contact': {'last_name': 'Кузнецов', 'first_name': 'Дмитрий', 'initials': 'Д.', 'name_latin': 'Kuznetsov Dmitry', 'phone': '+79628889900', 'address': {'city': 'Сарапул', 'street': 'Мончегорская', 'h…
- I: `courier_book` written={'address': {'locality': 'Сарапул', 'street': 'Тополиная', 'building': '16', 'sflat': '94'}, 'contact': {'name': 'Жуков Георгий', 'phone': '+79971886997'}, 'interval': {'from': '2026-09-05T10:00:00+04:00', 'to': '2026-09-05T14:00:00+04:00'}} → restored={'address': {'locality': 'Сарапул', 'street': 'мончегорская', 'building': '185', 'sflat': '56'}, 'contact': {'name': 'кузнецов дмитрий', 'phone': '+79628889900'}, 'interval': {'from': '2026-09-05T10:00:00+04:00', 'to': '2026-09-05T14:00:00+04:00'}}
- C′: `crm_upsert_contact` {'contact': {'last_name': 'Кузнецов', 'first_name': 'Дмитрий', 'initials': 'Д.', 'name_latin': 'Kuznetsov Dmitry', 'phone': '+79628889900', 'address': {'city': 'Сарапул', 'street': 'Мончегорская', 'h…
- C′: `courier_book` {'address': {'locality': 'Сарапул', 'street': 'Мончегорская', 'building': '185', 'sflat': '56'}, 'contact': {'name': 'Кузнецов Дмитрий', 'phone': '+79628889900'}, 'interval': {'from': '2026-09-05T10:…
- FIELD `crm_upsert_contact.contact.address.city` [absent → absent:city] C=`Сарапул` I=``
- FIELD `crm_upsert_contact.contact.address.flat` [absent → absent:flat] C=`56` I=``
- FIELD `crm_upsert_contact.contact.address.house` [absent → absent:house] C=`185` I=``
- FIELD `crm_upsert_contact.contact.address.street` [absent → absent:street] C=`Мончегорская` I=``
- FIELD `crm_upsert_contact.contact.first_name` [absent → absent:first_name] C=`Дмитрий` I=``
- FIELD `crm_upsert_contact.contact.initials` [absent → absent:initials] C=`Д.` I=``
- FIELD `crm_upsert_contact.contact.last_name` [absent → absent:last_name] C=`Кузнецов` I=``
- FIELD `crm_upsert_contact.contact.name_latin` [absent → absent:name_latin] C=`Kuznetsov Dmitry` I=``
- FIELD `crm_upsert_contact.contact.phone` [absent → absent:phone] C=`+79628889900` I=``
- REPLY I: Оформляю вызов курьера на завтра, 5 сентября, с 10:00 до 14:00! Готово! Курьер вызван ✅ **Детали заказа (clm-1):** - 📍 Сарапул, мончегорская дом сто восемьдесят пять квартира пятьдесят шесть - 👤 кузнецов дмитрий, восемь девятьсот шестьдесят два восемест восемьдесят восемь девяно девять ноль ноль - …

## correction-030|1 · correction · voice_raw · L1 ≠ · L3 ≠ · C′≈C нет · причина: **partial-call**
- USER[1]: алло курьера наа адрес мончегорская триц три квартира пятьдесят шесть неет не так правильно мончегорская дом сто восемьдесят пять квартира пятьдесят шесть это в сарапул это кузнецов дмитрий телефон восемь девятьсот шестьдесят два восемест восемьдесят восемь девяно девять ноль ноль
- USER[2]: завтра с десятии до двух
- seen LOC `мончегорская триц три квартира пятьдесят шесть` → `улица Лавандовая 162, кв. 97`
- seen LOC `мончегорская дом сто восемьдесят пять квартира пятьдесят шесть` → `улица Грушевая 180, кв. 240`
- seen NAME `кузнецов дмитрий` → `Наумов Эдуард`
- seen PHONE `восемь девятьсот шестьдесят два восемест восемьдесят восемь девяно девять ноль ноль` → `+79357986617`
- C: `crm_upsert_contact` {'contact': {'last_name': 'Кузнецов', 'first_name': 'Дмитрий', 'initials': 'Д.', 'name_latin': 'Kuznetsov Dmitriy', 'gender': 'M', 'phone': '+79628889900', 'address': {'city': 'Сарапул', 'street': 'М…
- C: `courier_book` {'address': {'locality': 'Сарапул', 'street': 'Мончегорская', 'building': '185', 'sflat': '56'}, 'contact': {'name': 'Кузнецов Дмитрий', 'phone': '+79628889900'}, 'interval': {'from': '2026-09-05T10:…
- I: `courier_book` written={'address': {'locality': 'Сарапул', 'street': 'Грушевая', 'building': '180', 'sflat': '240'}, 'contact': {'name': 'Наумов Эдуард', 'phone': '+79357986617'}, 'interval': {'from': '2026-09-05T10:00:00+04:00', 'to': '2026-09-05T14:00:00+04:00'}} → restored={'address': {'locality': 'Сарапул', 'street': 'мончегорская', 'building': '185', 'sflat': '56'}, 'contact': {'name': 'кузнецов дмитрий', 'phone': '+79628889900'}, 'interval': {'from': '2026-09-05T10:00:00+04:00', 'to': '2026-09-05T14:00:00+04:00'}}
- C′: `courier_book` {'address': {'locality': 'Сарапул', 'street': 'Мончегорская', 'building': '185', 'sflat': '56'}, 'contact': {'name': 'Кузнецов Дмитрий', 'phone': '+79628889900'}, 'interval': {'from': '2026-09-05T10:…
- C′: `crm_upsert_contact` {'contact': {'last_name': 'Кузнецов', 'first_name': 'Дмитрий', 'initials': 'Д.', 'name_latin': 'Kuznetсov Dmitry', 'gender': 'M', 'phone': '+79628889900', 'address': {'city': 'Сарапул', 'street': 'Мо… · refusal=latin_letters_only
- C′: `crm_upsert_contact` {'contact': {'last_name': 'Кузнецов', 'first_name': 'Дмитрий', 'initials': 'Д.', 'name_latin': 'Kuznetsov Dmitry', 'gender': 'M', 'phone': '+79628889900', 'address': {'city': 'Сарапул', 'street': 'Мо…
- FIELD `crm_upsert_contact.contact.address.city` [absent → absent:city] C=`Сарапул` I=``
- FIELD `crm_upsert_contact.contact.address.flat` [absent → absent:flat] C=`56` I=``
- FIELD `crm_upsert_contact.contact.address.house` [absent → absent:house] C=`185` I=``
- FIELD `crm_upsert_contact.contact.address.street` [absent → absent:street] C=`Мончегорская` I=``
- FIELD `crm_upsert_contact.contact.first_name` [absent → absent:first_name] C=`Дмитрий` I=``
- FIELD `crm_upsert_contact.contact.gender` [absent → absent:gender] C=`M` I=``
- FIELD `crm_upsert_contact.contact.initials` [absent → absent:initials] C=`Д.` I=``
- FIELD `crm_upsert_contact.contact.last_name` [absent → absent:last_name] C=`Кузнецов` I=``
- FIELD `crm_upsert_contact.contact.name_latin` [absent → absent:name_latin] C=`Kuznetsov Dmitriy` I=``
- FIELD `crm_upsert_contact.contact.phone` [absent → absent:phone] C=`+79628889900` I=``
- REPLY I: Вызываю курьера! Готово! ✅ Курьер вызван, заявка принята (№ **clm-1**). **Детали:** - 📍 Сарапул, мончегорская дом сто восемьдесят пять квартира пятьдесят шесть - 👤 кузнецов дмитрий, восемь девятьсот шестьдесят два восемест восемьдесят восемь девяно девять ноль ноль - 🕙 5 сентября, с 10:00 до 14:00 …

## correction-031|0 · correction · sloppy · L1 ≠ · L3 ≠ · C′≈C нет · причина: **partial-call**
- USER[1]: добрый курьерра на адрес новвя 81 кв 6 нет не так правилньо нвоая 53кв6 это в сарапул это битюков олег телефон 89896866953
- USER[2]: в четверг после обеда
- seen LOC `новвя 81 кв 6` → `улицы Ивовой 114, кв. 41`
- seen LOC `нвоая 53кв6` → `улица Еловая 174, кв. 179`
- seen NAME `битюков олег` → `Щукин Даниил`
- seen PHONE `89896866953` → `+79782727764`
- C: `courier_book` {'address': {'locality': 'Сарапул', 'street': 'Новая', 'building': '53', 'sflat': '6'}, 'contact': {'name': 'Битюков Олег', 'phone': '+79896866953'}, 'interval': {'from': '2026-09-10T14:00:00+04:00',…
- C: `crm_upsert_contact` {'contact': {'last_name': 'Битюков', 'first_name': 'Олег', 'initials': 'О.', 'name_latin': 'Bityukov Oleg', 'gender': 'M', 'phone': '+79896866953', 'address': {'city': 'Сарапул', 'street': 'Новая', '…
- I: `courier_book` written={'address': {'locality': 'Сарапул', 'street': 'Еловая', 'building': '174', 'sflat': '179'}, 'contact': {'name': 'Щукин Даниил', 'phone': '+79782727764'}, 'interval': {'from': '2026-09-10T14:00:00+04:00', 'to': '2026-09-10T18:00:00+04:00'}} → restored={'address': {'locality': 'Сарапул', 'street': 'нвоая', 'building': '53', 'sflat': '6'}, 'contact': {'name': 'битюков олег', 'phone': '+79896866953'}, 'interval': {'from': '2026-09-10T14:00:00+04:00', 'to': '2026-09-10T18:00:00+04:00'}}
- C′: `crm_upsert_contact` {'contact': {'last_name': 'Битюков', 'first_name': 'Олег', 'initials': 'О.', 'name_latin': 'Bityukov Oleg', 'phone': '+79896866953', 'gender': 'M', 'address': {'city': 'Сарапул', 'street': 'Новая', '…
- C′: `courier_book` {'address': {'locality': 'Сарапул', 'street': 'Новая', 'building': '53', 'sflat': '6'}, 'contact': {'name': 'Битюков Олег', 'phone': '+79896866953'}, 'interval': {'from': '2026-09-10T14:00:00+04:00',…
- FIELD `courier_book.address.street` [control_erred/i2 → control_erred] C=`Новая` I=`нвоая` · контроль ошибся; шлюз восстановил эталон корпуса
- FIELD `crm_upsert_contact.contact.address.city` [absent → absent:city] C=`Сарапул` I=``
- FIELD `crm_upsert_contact.contact.address.flat` [absent → absent:flat] C=`6` I=``
- FIELD `crm_upsert_contact.contact.address.house` [absent → absent:house] C=`53` I=``
- FIELD `crm_upsert_contact.contact.address.street` [absent → absent:street] C=`Новая` I=``
- FIELD `crm_upsert_contact.contact.first_name` [absent → absent:first_name] C=`Олег` I=``
- FIELD `crm_upsert_contact.contact.gender` [absent → absent:gender] C=`M` I=``
- FIELD `crm_upsert_contact.contact.initials` [absent → absent:initials] C=`О.` I=``
- FIELD `crm_upsert_contact.contact.last_name` [absent → absent:last_name] C=`Битюков` I=``
- FIELD `crm_upsert_contact.contact.name_latin` [absent → absent:name_latin] C=`Bityukov Oleg` I=``
- FIELD `crm_upsert_contact.contact.phone` [absent → absent:phone] C=`+79896866953` I=``
- REPLY I: Ближайший четверг — **10 сентября**, возьму стандартное послеобеденное окно **14:00–18:00**. Оформляю! Готово! ✅ **Заявка на курьера оформлена** (№ clm-1): - 📍 Сарапул, нвоая 53кв6 - 👤 битюков олег, 89896866953 - 📅 10 сентября (четверг), 14:00–18:00 Если нужно что-то изменить или добавить — говорит…

## correction-031|1 · correction · sloppy · L1 ≠ · L3 ≠ · C′≈C нет · причина: **other**
- USER[1]: добрый курьерра на адрес новвя 81 кв 6 нет не так правилньо нвоая 53кв6 это в сарапул это битюков олег телефон 89896866953
- USER[2]: в четверг после обеда
- seen LOC `новвя 81 кв 6` → `улицы Кленовой 110, кв. 65`
- seen LOC `нвоая 53кв6` → `улица Берёзовая 190, кв. 102`
- seen NAME `битюков олег` → `Наумов Иван`
- seen PHONE `89896866953` → `+79619441277`
- C: `crm_upsert_contact` {'contact': {'last_name': 'Битюков', 'first_name': 'Олег', 'initials': 'О.', 'name_latin': 'Bityukov Oleg', 'phone': '+79896866953', 'gender': 'M', 'address': {'city': 'Сарапул', 'street': 'Новая', '…
- C: `courier_book` {'address': {'locality': 'Сарапул', 'street': 'Новая', 'building': '53', 'sflat': '6'}, 'contact': {'name': 'Битюков Олег', 'phone': '+79896866953'}, 'interval': {'from': '2026-09-10T13:00:00+04:00',…
- I: `courier_book` written={'address': {'locality': 'Сарапул', 'street': 'Берёзовая', 'building': '190', 'sflat': '102'}, 'contact': {'name': 'Наумов Иван', 'phone': '+79619441277'}, 'interval': {'from': '2026-09-10T14:00:00+04:00', 'to': '2026-09-10T18:00:00+04:00'}} → restored={'address': {'locality': 'Сарапул', 'street': 'нвоая', 'building': '53', 'sflat': '6'}, 'contact': {'name': 'битюков олег', 'phone': '+79896866953'}, 'interval': {'from': '2026-09-10T14:00:00+04:00', 'to': '2026-09-10T18:00:00+04:00'}}
- I: `crm_upsert_contact` written={'contact': {'first_name': 'Иван', 'last_name': 'Наумов', 'phone': '+79619441277', 'gender': 'M', 'initials': 'И.', 'name_latin': 'Naumov Ivan', 'address': {'city': 'Сарапул', 'street': 'Берёзовая', 'house': '190', 'flat': '102'}}} → restored={'contact': {'first_name': 'олег', 'last_name': 'битюков', 'phone': '+79896866953', 'gender': 'M', 'initials': 'И.', 'name_latin': 'Bitiukov Oleg', 'address': {'city': 'Сарапул', 'street': 'нвоая', 'house': '53', 'flat': '6'}}}
- C′: `courier_book` {'address': {'locality': 'Сарапул', 'street': 'Новая', 'building': '53', 'sflat': '6'}, 'contact': {'name': 'Битюков Олег', 'phone': '+79896866953'}, 'interval': {'from': '2026-09-10T13:00:00+04:00',…
- C′: `crm_upsert_contact` {'contact': {'first_name': 'Олег', 'last_name': 'Битюков', 'initials': 'О.', 'name_latin': 'Bityukov Oleg', 'phone': '+79896866953', 'address': {'city': 'Сарапул', 'street': 'Новая', 'house': '53', '…
- FIELD `crm_upsert_contact.contact.address.street` [control_erred/i2 → control_erred] C=`Новая` I=`нвоая` · контроль ошибся; шлюз восстановил эталон корпуса
- FIELD `crm_upsert_contact.contact.initials` [derived/from_substitute → derived] C=`О.` I=`И.` · значение выведено из ПОДМЕНЫ; восстановление недостижимо
- FIELD `crm_upsert_contact.contact.name_latin` [other/misderived → name_partial] C=`Bityukov Oleg` I=`Bitiukov Oleg`
- FIELD `courier_book.address.street` [control_erred/i2 → control_erred] C=`Новая` I=`нвоая` · контроль ошибся; шлюз восстановил эталон корпуса
- REPLY I: Ближайший четверг — **10 сентября**. Возьму интервал «после обеда» как **14:00–18:00**. Оформляю всё сразу! Всё оформлено! Вот итог: **🚚 Вызов курьера** - **Адрес:** Сарапул, нвоая 53кв6 - **Получатель:** битюков олег, 89896866953 - **Дата и время:** 10 сентября (четверг), 14:00–18:00 - **Номер зая…

## correction-032|0 · correction · voice_itn · L1 = · L3 ≠ · C′≈C да · причина: **other**
- USER[1]: добрый день курьера на кирочная 129 квартира 59 нет не так правильно кирочная дом 101 квартира 59 это в ижевск это букин сергей телефон 8-982-513-94-60
- USER[2]: завтра с десяти до двух
- seen LOC `кирочная 129 квартира 59` → `улица Буковая 6, кв. 52`
- seen LOC `кирочная дом 101 квартира 59` → `улица Липовая 141, кв. 245`
- seen NAME `букин сергей` → `Тарасов Владислав`
- seen PHONE `8-982-513-94-60` → `+79681775987`
- C: `courier_book` {'address': {'locality': 'Ижевск', 'street': 'Кирочная', 'building': '101', 'sflat': '59'}, 'contact': {'name': 'Букин Сергей', 'phone': '+79825139460'}, 'interval': {'from': '2026-09-05T10:00:00+04:…
- C: `crm_upsert_contact` {'contact': {'first_name': 'Сергей', 'last_name': 'Букин', 'initials': 'С.', 'name_latin': 'Bukin Sergey', 'phone': '+79825139460', 'gender': 'M', 'address': {'city': 'Ижевск', 'street': 'Кирочная', …
- I: `courier_book` written={'address': {'locality': 'Ижевск', 'street': 'Липовая', 'building': '141', 'sflat': '245'}, 'contact': {'name': 'Тарасов Владислав', 'phone': '+79681775987'}, 'interval': {'from': '2026-09-05T10:00:00+04:00', 'to': '2026-09-05T14:00:00+04:00'}} → restored={'address': {'locality': 'Ижевск', 'street': 'кирочная', 'building': '101', 'sflat': '59'}, 'contact': {'name': 'букин сергей', 'phone': '+79825139460'}, 'interval': {'from': '2026-09-05T10:00:00+04:00', 'to': '2026-09-05T14:00:00+04:00'}}
- I: `crm_upsert_contact` written={'contact': {'last_name': 'Тарасов', 'first_name': 'Владислав', 'initials': 'В.', 'name_latin': 'Tarasov Vladislav', 'gender': 'M', 'phone': '+79681775987', 'address': {'city': 'Ижевск', 'street': 'Липовая', 'house': '141', 'flat': '245'}}} → restored={'contact': {'last_name': 'букин', 'first_name': 'сергей', 'initials': 'В.', 'name_latin': 'Bukin Sergei', 'gender': 'M', 'phone': '+79825139460', 'address': {'city': 'Ижевск', 'street': 'кирочная', 'house': '101', 'flat': '59'}}}
- C′: `courier_book` {'address': {'locality': 'Ижевск', 'street': 'Кирочная', 'building': '101', 'sflat': '59'}, 'contact': {'name': 'Букин Сергей', 'phone': '+79825139460'}, 'interval': {'from': '2026-09-05T10:00:00+04:…
- C′: `crm_upsert_contact` {'contact': {'last_name': 'Букин', 'first_name': 'Сергей', 'initials': 'С.', 'name_latin': 'Bukin Sergey', 'gender': 'M', 'phone': '+79825139460', 'address': {'city': 'Ижевск', 'street': 'Кирочная', …
- FIELD `crm_upsert_contact.contact.initials` [derived/from_substitute → derived] C=`С.` I=`В.` · значение выведено из ПОДМЕНЫ; восстановление недостижимо
- FIELD `crm_upsert_contact.contact.name_latin` [other/misderived → name_partial] C=`Bukin Sergey` I=`Bukin Sergei`
- REPLY I: Отлично, оформляю! Запускаю оба действия одновременно: вызов курьера и карточку клиента. Всё оформлено! ✅ **Курьер вызван:** - 📍 Ижевск, кирочная дом 101 квартира 59 - 👤 букин сергей, 8-982-513-94-60 - 🕐 Завтра, 5 сентября, с 10:00 до 14:00 - 🔖 Номер заявки: **clm-1** **Карточка клиента** в CRM соз…

## correction-032|1 · correction · voice_itn · L1 ≠ · L3 ≠ · C′≈C нет · причина: **other**
- USER[1]: добрый день курьера на кирочная 129 квартира 59 нет не так правильно кирочная дом 101 квартира 59 это в ижевск это букин сергей телефон 8-982-513-94-60
- USER[2]: завтра с десяти до двух
- seen LOC `кирочная 129 квартира 59` → `улица Буковая 120, кв. 49`
- seen LOC `кирочная дом 101 квартира 59` → `улица Рябиновая 98, кв. 196`
- seen NAME `букин сергей` → `Шилов Гордей`
- seen PHONE `8-982-513-94-60` → `+79703564508`
- C: `courier_book` {'address': {'locality': 'Ижевск', 'street': 'Кирочная', 'building': '101', 'sflat': '59'}, 'contact': {'name': 'Букин Сергей', 'phone': '+79825139460'}, 'interval': {'from': '2026-09-05T10:00:00+04:…
- I: `crm_upsert_contact` written={'contact': {'last_name': 'Шилов', 'first_name': 'Гордей', 'initials': 'Г.', 'name_latin': 'Shilov Gordey', 'phone': '+79703564508', 'address': {'city': 'Ижевск', 'street': 'Рябиновая', 'house': '98', 'flat': '196'}}} → restored={'contact': {'last_name': 'букин', 'first_name': 'сергей', 'initials': 'Г.', 'name_latin': 'Bukin Sergey', 'phone': '+79825139460', 'address': {'city': 'Ижевск', 'street': 'кирочная', 'house': '101', 'flat': '59'}}}
- I: `courier_book` written={'address': {'locality': 'Ижевск', 'street': 'Рябиновая', 'building': '98', 'sflat': '196'}, 'contact': {'name': 'Шилов Гордей', 'phone': '+79703564508'}, 'interval': {'from': '2026-09-05T10:00:00+04:00', 'to': '2026-09-05T14:00:00+04:00'}} → restored={'address': {'locality': 'Ижевск', 'street': 'кирочная', 'building': '101', 'sflat': '59'}, 'contact': {'name': 'букин сергей', 'phone': '+79825139460'}, 'interval': {'from': '2026-09-05T10:00:00+04:00', 'to': '2026-09-05T14:00:00+04:00'}}
- C′: `courier_book` {'address': {'locality': 'Ижевск', 'street': 'Кирочная', 'building': '101', 'sflat': '59'}, 'contact': {'name': 'Букин Сергей', 'phone': '+79825139460'}, 'interval': {'from': '2026-09-05T10:00:00+04:…
- C′: `crm_upsert_contact` {'contact': {'last_name': 'Букин', 'first_name': 'Сергей', 'initials': 'С.', 'name_latin': 'Bukin Sergei', 'phone': '+79825139460', 'address': {'city': 'Ижевск', 'street': 'Кирочная', 'house': '101',…
- FIELD `crm_upsert_contact.contact.address.city` [extra → extra:city] C=`` I=`Ижевск`
- FIELD `crm_upsert_contact.contact.address.flat` [extra → extra:flat] C=`` I=`59`
- FIELD `crm_upsert_contact.contact.address.house` [extra → extra:house] C=`` I=`101`
- FIELD `crm_upsert_contact.contact.address.street` [extra → extra:street] C=`` I=`кирочная`
- FIELD `crm_upsert_contact.contact.first_name` [extra → extra:first_name] C=`` I=`сергей`
- FIELD `crm_upsert_contact.contact.initials` [extra → extra:initials] C=`` I=`Г.`
- FIELD `crm_upsert_contact.contact.last_name` [extra → extra:last_name] C=`` I=`букин`
- FIELD `crm_upsert_contact.contact.name_latin` [extra → extra:name_latin] C=`` I=`Bukin Sergey`
- FIELD `crm_upsert_contact.contact.phone` [extra → extra:phone] C=`` I=`+79825139460`
- REPLY I: Принято, оформляю! Всё оформлено! Вот итог: - 📦 **Курьер вызван** (заявка `clm-1`) - 📍 **Адрес:** Ижевск, кирочная дом 101 квартира 59 - 👤 **Получатель:** букин сергей, 8-982-513-94-60 - 🕙 **Интервал:** 5 сентября 2026, с 10:00 до 14:00 - ✅ **Карточка клиента** в CRM создана/обновлена Если нужно чт…

## decompose-007|0 · decompose · sloppy · L1 = · L3 ≠ · C′≈C да · причина: **typo-normalised**
- USER[1]: дообрый курьера на глазов проезд неркасова 170 подъезд 6 квартира 119 это в глазов полуачтель лебедева ирина телефон +79875487262 завтра с десяти до двух
- seen LOC `глазов проезд неркасова 170 подъезд 6 квартира 119` → `Глазов, проезд Луговой 123, подъезд 6, кв. 248`
- seen NAME `лебедева ирина` → `Сазонова Мещерякова Тамара`
- seen PHONE `+79875487262` → `+79779657964`
- C: `courier_book` {'address': {'locality': 'Глазов', 'street': 'проезд Некрасова', 'building': '170', 'porch': '6', 'sflat': '119'}, 'contact': {'name': 'Лебедева Ирина', 'phone': '+79875487262'}, 'interval': {'from':…
- I: `courier_book` written={'address': {'locality': 'Глазов', 'street': 'проезд Луговой', 'building': '123', 'porch': '6', 'sflat': '248'}, 'contact': {'name': 'Сазонова Мещерякова Тамара', 'phone': '+79779657964'}, 'interval': {'from': '2026-09-05T10:00:00+04:00', 'to': '2026-09-05T14… → restored={'address': {'locality': 'глазов', 'street': 'проезд неркасова', 'building': '170', 'porch': '6', 'sflat': '119'}, 'contact': {'name': 'полуачтель лебедева ирина', 'phone': '+79875487262'}, 'interval': {'from': '2026-09-05T10:00:00+04:00', 'to': '2026-09-05T1…
- C′: `courier_book` {'address': {'locality': 'Глазов', 'street': 'проезд Некрасова', 'building': '170', 'porch': '6', 'sflat': '119'}, 'contact': {'name': 'Лебедева Ирина', 'phone': '+79875487262'}, 'interval': {'from':…
- FIELD `courier_book.address.street` [other/unbound → loc_street] C=`проезд Некрасова` I=`проезд неркасова`
- FIELD `courier_book.contact.name` [other/inflected → name_partial] C=`Лебедева Ирина` I=`полуачтель лебедева ирина`
- REPLY I: Добрый день! Оформляю вызов курьера, одну секунду. Готово! Курьер оформлен ✅ **Детали вызова:** - 📍 глазов проезд неркасова 170 подъезд 6 квартира 119 - 👤 полуачтель лебедева ирина, +79875487262 - 🗓 5 сентября 2026 г., с **10:00 до 14:00** - 🆔 Заявка: **clm-1** Курьер приедет в указанный интервал. …

## decompose-007|1 · decompose · sloppy · L1 = · L3 ≠ · C′≈C да · причина: **typo-normalised**
- USER[1]: дообрый курьера на глазов проезд неркасова 170 подъезд 6 квартира 119 это в глазов полуачтель лебедева ирина телефон +79875487262 завтра с десяти до двух
- seen LOC `глазов проезд неркасова 170 подъезд 6 квартира 119` → `Глазов, проезд Ивовый 189, подъезд 16, кв. 56`
- seen NAME `лебедева ирина` → `Панова Наумова Виктория`
- seen PHONE `+79875487262` → `+79286615737`
- C: `courier_book` {'address': {'locality': 'Глазов', 'street': 'Проезд Некрасова', 'building': '170', 'porch': '6', 'sflat': '119'}, 'contact': {'name': 'Лебедева Ирина', 'phone': '+79875487262'}, 'interval': {'from':…
- I: `courier_book` written={'address': {'locality': 'Глазов', 'street': 'проезд Ивовый', 'building': '189', 'porch': '16', 'sflat': '56'}, 'contact': {'name': 'Панова Наумова Виктория', 'phone': '+79286615737'}, 'interval': {'from': '2026-09-05T10:00:00+04:00', 'to': '2026-09-05T14:00:… → restored={'address': {'locality': 'глазов', 'street': 'проезд неркасова', 'building': '170', 'porch': '6', 'sflat': '119'}, 'contact': {'name': 'полуачтель лебедева ирина', 'phone': '+79875487262'}, 'interval': {'from': '2026-09-05T10:00:00+04:00', 'to': '2026-09-05T1…
- C′: `courier_book` {'address': {'locality': 'Глазов', 'street': 'Проезд Некрасова', 'building': '170', 'porch': '6', 'sflat': '119'}, 'contact': {'name': 'Лебедева Ирина', 'phone': '+79875487262'}, 'interval': {'from':…
- FIELD `courier_book.address.street` [other/unbound → loc_street] C=`Проезд Некрасова` I=`проезд неркасова`
- FIELD `courier_book.contact.name` [other/inflected → name_partial] C=`Лебедева Ирина` I=`полуачтель лебедева ирина`
- REPLY I: Оформляю вызов курьера! 🚚 Готово! ✅ Курьер вызван. **Детали заявки `clm-1`:** - 📍 Глазов, глазов проезд неркасова 170, подъ. 16, кв. 119 - 👤 полуачтель лебедева ирина, +79875487262 - 🗓 5 сентября 2026, с **10:00 до 14:00** - Статус: *оценивается* Если нужно что-то изменить — скажите!

## decompose-008|1 · decompose · sloppy · L1 = · L3 ≠ · C′≈C нет · причина: **other**
- USER[1]: привет проведите оплату 620 рублей карта 4276945545660784 срок 09/27 дерржатель пётр ерохин
- seen CARD `4276945545660784` → `0975 8134 8574 0606`
- seen NAME `пётр ерохин` → `Георгий Карпов`
- C: `payment_create` {'amount': {'value': '620.00', 'currency': 'RUB'}, 'payment_method_data': {'type': 'bank_card', 'card': {'number': '4276945545660784', 'expiry_month': '09', 'expiry_year': '2027', 'cardholder': 'PETR…
- I: `payment_create` written={'amount': {'value': '620.00', 'currency': 'RUB'}, 'payment_method_data': {'type': 'bank_card', 'card': {'number': '0975813485740606', 'expiry_month': '09', 'expiry_year': '2027', 'cardholder': 'GEORGIY KARPOV'}}} → restored={'amount': {'value': '620.00', 'currency': 'RUB'}, 'payment_method_data': {'type': 'bank_card', 'card': {'number': '4276945545660784', 'expiry_month': '09', 'expiry_year': '2027', 'cardholder': 'PETR EROKHIN'}}}
- C′: `payment_create` {'amount': {'value': '620.00', 'currency': 'RUB'}, 'payment_method_data': {'type': 'bank_card', 'card': {'number': '4276945545660784', 'expiry_month': '09', 'expiry_year': '2027', 'cardholder': 'PETR…
- FIELD `payment_create.payment_method_data.card.cardholder` [other/misderived → name_partial] C=`PETR YEROKHIN` I=`PETR EROKHIN`
- REPLY I: Провожу платёж, сейчас всё оформлю! Платёж создан! Вот детали: | Параметр | Значение | |---|---| | **ID платежа** | pay-1 | | **Статус** | 🕐 Pending (в обработке) | | **Сумма** | 620.00 RUB | | **Карта** | **** **** **** 0784 | | **Срок действия** | 09/2027 | | **Держатель** | PETR EROKHIN | Платёж…

## decompose-019|0 · decompose · sloppy · L1 = · L3 ≠ · C′≈C да · причина: **control_erred**
- USER[1]: добрый курьера на абакан луогвая 5 подъезд 7 кв 30 это в абпкан получатель миллер валерий телефон 8 952 279 93 12 завтра с десяти до двкх
- seen LOC `абакан луогвая 5 подъезд 7 кв 30` → `Абакан, улицу Липовую 173, подъезд 5, кв. 1`
- seen NAME `миллер валерий` → `Осипов Виталий`
- seen PHONE `8 952 279 93 12` → `+79031796794`
- C: `courier_book` {'address': {'locality': 'Абакан', 'street': 'Луговая', 'building': '5', 'porch': '7', 'sflat': '30'}, 'contact': {'name': 'Миллер Валерий', 'phone': '+79522799312'}, 'interval': {'from': '2026-09-05…
- I: `courier_book` written={'address': {'locality': 'Абакан', 'street': 'Липовая', 'building': '173', 'porch': '5', 'sflat': '1'}, 'contact': {'name': 'Осипов Виталий', 'phone': '+79031796794'}, 'interval': {'from': '2026-09-05T10:00:00+07:00', 'to': '2026-09-05T14:00:00+07:00'}} → restored={'address': {'locality': 'абакан', 'street': 'луогвая', 'building': '5', 'porch': '7', 'sflat': '30'}, 'contact': {'name': 'миллер валерий', 'phone': '+79522799312'}, 'interval': {'from': '2026-09-05T10:00:00+07:00', 'to': '2026-09-05T14:00:00+07:00'}}
- C′: `courier_book` {'address': {'locality': 'Абакан', 'street': 'Луговая', 'building': '5', 'porch': '7', 'sflat': '30'}, 'contact': {'name': 'Миллер Валерий', 'phone': '+79522799312'}, 'interval': {'from': '2026-09-05…
- FIELD `courier_book.address.street` [control_erred/i1 → control_erred] C=`Луговая` I=`луогвая` · контроль ошибся; шлюз восстановил эталон корпуса
- REPLY I: Оформляю вызов курьера! Абакан — UTC+7, завтра с 10:00 до 14:00. Готово! Курьер оформлен ✅ **Детали заявки:** - 🆔 Номер заявки: `clm-1` - 📍 Адрес: абакан луогвая 5 подъезд 7 кв 30 - 👤 Получатель: миллер валерий (8 952 279 93 12) - 🕙 Интервал: 5 сентября 2026, с 10:00 до 14:00 (Абакан, UTC+7) - 📋 Ст…

## decompose-019|1 · decompose · sloppy · L1 = · L3 ≠ · C′≈C да · причина: **control_erred**
- USER[1]: добрый курьера на абакан луогвая 5 подъезд 7 кв 30 это в абпкан получатель миллер валерий телефон 8 952 279 93 12 завтра с десяти до двкх
- seen LOC `абакан луогвая 5 подъезд 7 кв 30` → `Абакан, улицу Осиновую 107, подъезд 18, кв. 158`
- seen NAME `миллер валерий` → `Котов Яков`
- seen PHONE `8 952 279 93 12` → `+79485007301`
- C: `courier_book` {'address': {'locality': 'Абакан', 'street': 'Луговая', 'building': '5', 'porch': '7', 'sflat': '30'}, 'contact': {'name': 'Миллер Валерий', 'phone': '+79522799312'}, 'interval': {'from': '2026-09-05…
- I: `courier_book` written={'address': {'locality': 'Абакан', 'street': 'Осиновая', 'building': '107', 'porch': '18', 'sflat': '158'}, 'contact': {'name': 'Котов Яков', 'phone': '+79485007301'}, 'interval': {'from': '2026-09-05T10:00:00+07:00', 'to': '2026-09-05T14:00:00+07:00'}} → restored={'address': {'locality': 'абакан', 'street': 'луогвая', 'building': '5', 'porch': '7', 'sflat': '30'}, 'contact': {'name': 'миллер валерий', 'phone': '+79522799312'}, 'interval': {'from': '2026-09-05T10:00:00+07:00', 'to': '2026-09-05T14:00:00+07:00'}}
- C′: `courier_book` {'address': {'locality': 'Абакан', 'street': 'Луговая', 'building': '5', 'porch': '7', 'sflat': '30'}, 'contact': {'name': 'Миллер Валерий', 'phone': '+79522799312'}, 'interval': {'from': '2026-09-05…
- FIELD `courier_book.address.street` [control_erred/i1 → control_erred] C=`Луговая` I=`луогвая` · контроль ошибся; шлюз восстановил эталон корпуса
- REPLY I: Вызываю курьера прямо сейчас! Готово! Курьер вызван ✅ **Детали заказа (clm-1):** - 📍 абакан луогвая 5 подъезд 7 кв 30 - 👤 миллер валерий, 8 952 279 93 12 - 🗓 5 сентября 2026 г., с **10:00 до 14:00** (местное время) Заявка принята, статус: *оценивается*. Если понадобится что-то изменить — обращайтес…

## decompose-025|0 · decompose · voice_raw · L1 = · L3 ≠ · C′≈C нет · причина: **control_erred**
- USER[1]: алло курьераа на глазов проезд октябрьский семнадцать шестой подъезд квартира восемь это в глазов получатель громова марина телефон восемь девятьсот пятьдесят пятьдесят пяять пятьдесят шесть шестьдесят семь семь в четверг с двуух до шести
- seen LOC `глазов проезд октябрьский семнадцать шестой подъезд квартира восемь` → `Глазов, проезд Озёрный 183, подъезд 13, кв. 110`
- seen NAME `громова марина` → `Карпова Вера`
- seen PHONE `восемь девятьсот пятьдесят пятьдесят пяять пятьдесят шесть шестьдесят семь семь` → `+79620595540`
- C: `courier_book` {'address': {'locality': 'Глазов', 'street': 'Октябрьский проезд', 'building': '17', 'porch': '6', 'sflat': '8'}, 'contact': {'name': 'Громова Марина', 'phone': '+79005055677'}, 'interval': {'from': …
- I: `courier_book` written={'address': {'locality': 'Глазов', 'street': 'проезд Озёрный', 'building': '183', 'porch': '13', 'sflat': '110'}, 'contact': {'name': 'Карпова Вера', 'phone': '+79620595540'}, 'interval': {'from': '2026-09-10T14:00:00+04:00', 'to': '2026-09-10T18:00:00+04:00'… → restored={'address': {'locality': 'глазов', 'street': 'проезд октябрьский', 'building': '17', 'porch': '6', 'sflat': '8'}, 'contact': {'name': 'громова марина', 'phone': '+79505556677'}, 'interval': {'from': '2026-09-10T14:00:00+04:00', 'to': '2026-09-10T18:00:00+04:0…
- C′: `courier_book` {'address': {'locality': 'Глазов', 'street': 'Октябрьский проезд', 'building': '17', 'porch': '6', 'sflat': '8'}, 'contact': {'name': 'Громова Марина', 'phone': '+79005556677'}, 'interval': {'from': …
- FIELD `courier_book.contact.phone` [control_erred/i3 → control_erred] C=`+79005055677` I=`+79505556677` · контроль ошибся; шлюз восстановил эталон корпуса
- REPLY I: Принял! Вызываю курьера на четверг, 10 сентября, с 14:00 до 18:00. 🚚 Готово! ✅ Курьер оформлен. **Детали заказа:** - 📍 глазов проезд октябрьский семнадцать шестой подъезд квартира восемь - 👤 громова марина, восемь девятьсот пятьдесят пятьдесят пяять пятьдесят шесть шестьдесят семь семь - 📅 Четверг,…

## decompose-025|1 · decompose · voice_raw · L1 = · L3 ≠ · C′≈C нет · причина: **control_erred**
- USER[1]: алло курьераа на глазов проезд октябрьский семнадцать шестой подъезд квартира восемь это в глазов получатель громова марина телефон восемь девятьсот пятьдесят пятьдесят пяять пятьдесят шесть шестьдесят семь семь в четверг с двуух до шести
- seen LOC `глазов проезд октябрьский семнадцать шестой подъезд квартира восемь` → `Глазов, проезд Тополиный 51, подъезд 13, кв. 144`
- seen NAME `громова марина` → `Шилова Зинаида`
- seen PHONE `восемь девятьсот пятьдесят пятьдесят пяять пятьдесят шесть шестьдесят семь семь` → `+79095508814`
- C: `courier_book` {'address': {'locality': 'Глазов', 'street': 'проезд Октябрьский', 'building': '17', 'porch': '6', 'sflat': '8'}, 'contact': {'name': 'Громова Марина', 'phone': '+79005556677'}, 'interval': {'from': …
- I: `courier_book` written={'address': {'locality': 'Глазов', 'street': 'Тополиный проезд', 'building': '51', 'porch': '13', 'sflat': '144'}, 'contact': {'name': 'Шилова Зинаида', 'phone': '+79095508814'}, 'interval': {'from': '2026-09-10T14:00:00+04:00', 'to': '2026-09-10T18:00:00+04:… → restored={'address': {'locality': 'глазов', 'street': 'октябрьский проезд', 'building': '17', 'porch': '6', 'sflat': '8'}, 'contact': {'name': 'громова марина', 'phone': '+79505556677'}, 'interval': {'from': '2026-09-10T14:00:00+04:00', 'to': '2026-09-10T18:00:00+04:0…
- C′: `courier_book` {'address': {'locality': 'Глазов', 'street': 'Октябрьский проезд', 'building': '17', 'porch': '6', 'sflat': '8'}, 'contact': {'name': 'Громова Марина', 'phone': '+79005555677'}, 'interval': {'from': …
- FIELD `courier_book.contact.phone` [control_erred/i3 → control_erred] C=`+79005556677` I=`+79505556677` · контроль ошибся; шлюз восстановил эталон корпуса
- REPLY I: Оформляю вызов курьера! Ближайший четверг — **10 сентября 2026**, интервал 14:00–18:00 по Глазову (UTC+4). Готово! ✅ **Курьер вызван**, заявка принята (№ `clm-1`). 📦 **Детали вызова:** - 📍 глазов проезд октябрьский семнадцать шестой подъезд квартира восемь - 👤 громова марина, восемь девятьсот пятьд…

## decompose-029|0 · decompose · clean · L1 = · L3 ≠ · C′≈C да · причина: **other**
- USER[1]: Добрый день! проведите оплату 450 рублей карта 5469 5614 0463 3756 срок 07/30 держатель Валерий Миллер.
- seen CARD `5469 5614 0463 3756` → `0841 0404 3151 2036`
- seen NAME `Валерий Миллер` → `Иван Жуков`
- C: `payment_create` {'amount': {'value': '450.00', 'currency': 'RUB'}, 'payment_method_data': {'type': 'bank_card', 'card': {'number': '5469561404633756', 'expiry_month': '07', 'expiry_year': '2030', 'cardholder': 'VALE…
- I: `payment_create` written={'amount': {'value': '450.00', 'currency': 'RUB'}, 'payment_method_data': {'type': 'bank_card', 'card': {'number': '0841040431512036', 'expiry_month': '07', 'expiry_year': '2030', 'cardholder': 'IVAN ZHUKOV'}}} → restored={'amount': {'value': '450.00', 'currency': 'RUB'}, 'payment_method_data': {'type': 'bank_card', 'card': {'number': '5469561404633756', 'expiry_month': '07', 'expiry_year': '2030', 'cardholder': 'VALERII MILLER'}}}
- C′: `payment_create` {'amount': {'value': '450.00', 'currency': 'RUB'}, 'payment_method_data': {'type': 'bank_card', 'card': {'number': '5469561404633756', 'expiry_month': '07', 'expiry_year': '2030', 'cardholder': 'VALE…
- FIELD `payment_create.payment_method_data.card.cardholder` [other/misderived → name_partial] C=`VALERIY MILLER` I=`VALERII MILLER`
- REPLY I: Добрый день! Провожу платёж, держатель карты — латиницей заглавными. Платёж создан! Вот детали: | Параметр | Значение | |---|---| | **ID платежа** | pay-1 | | **Статус** | ⏳ Pending (в обработке) | | **Сумма** | 450,00 ₽ | | **Карта** | **** **** **** 3756 | | **Держатель** | VALERII MILLER | | **С…

## decompose-029|1 · decompose · clean · L1 = · L3 ≠ · C′≈C да · причина: **other**
- USER[1]: Добрый день! проведите оплату 450 рублей карта 5469 5614 0463 3756 срок 07/30 держатель Валерий Миллер.
- seen CARD `5469 5614 0463 3756` → `0180 0111 4693 0697`
- seen NAME `Валерий Миллер` → `Артём Тихонов`
- C: `payment_create` {'amount': {'value': '450.00', 'currency': 'RUB'}, 'payment_method_data': {'type': 'bank_card', 'card': {'number': '5469561404633756', 'expiry_month': '07', 'expiry_year': '2030', 'cardholder': 'VALE…
- I: `payment_create` written={'amount': {'value': '450.00', 'currency': 'RUB'}, 'payment_method_data': {'type': 'bank_card', 'card': {'number': '0180011146930697', 'expiry_month': '07', 'expiry_year': '2030', 'cardholder': 'ARTEM TIKHONOV'}}} → restored={'amount': {'value': '450.00', 'currency': 'RUB'}, 'payment_method_data': {'type': 'bank_card', 'card': {'number': '5469561404633756', 'expiry_month': '07', 'expiry_year': '2030', 'cardholder': 'VALERII MILLER'}}}
- C′: `payment_create` {'amount': {'value': '450.00', 'currency': 'RUB'}, 'payment_method_data': {'type': 'bank_card', 'card': {'number': '5469561404633756', 'expiry_month': '07', 'expiry_year': '2030', 'cardholder': 'VALE…
- FIELD `payment_create.payment_method_data.card.cardholder` [other/misderived → name_partial] C=`VALERIY MILLER` I=`VALERII MILLER`
- REPLY I: Добрый день! Провожу платёж, сейчас всё оформлю. Платёж создан! Вот детали: - **ID платежа:** pay-1 - **Статус:** в обработке (pending) - **Сумма:** 450,00 ₽ - **Карта:** **** **** **** 3756, срок 07/2030, VALERII MILLER Как только статус изменится, вы получите уведомление. Если появятся вопросы — …

## decompose-033|0 · decompose · voice_raw · L1 = · L3 ≠ · C′≈C да · причина: **control_erred**
- USER[1]: алло сверьте паспорт сорок девятнадцать трииста тринадцать пятьсот пятьдесят девять выдан гу мвд россии по краснодарскому краю код подразделенияя сто сорок семь шестьсот пятьдесят семь сниилс ноль семьдесят три двести пейсят три ноль восемьдесят семь сорок восемсь кукушкин валерий михайлович
- seen PASSPORT `сорок девятнадцать трииста тринадцать пятьсот пятьдесят девять` → `00 18 156126`
- seen SNILS `ноль семьдесят три двести пейсят три ноль восемьдесят семь сорок восемсь` → `336-851-458 77`
- seen NAME `кукушкин валерий михайлович` → `Сорокин Максим Константинович`
- C: `passport_verify` {'passport': {'series': '4919', 'number': '313559', 'issued_by': 'ГУ МВД России по Краснодарскому краю', 'department_code': '147-657'}, 'person': {'last_name': 'Кукушкин', 'first_name': 'Валерий', 'm…
- I: `passport_verify` written={'passport': {'series': '0018', 'number': '156126', 'issued_by': 'ГУ МВД России по Краснодарскому краю', 'department_code': '147-657'}, 'person': {'last_name': 'Сорокин', 'first_name': 'Максим', 'middle_name': 'Константинович'}, 'snils': '336-851-458 77'} → restored={'passport': {'series': '4019', 'number': '313559', 'issued_by': 'ГУ МВД России по Краснодарскому краю', 'department_code': '147-657'}, 'person': {'last_name': 'кукушкин', 'first_name': 'валерий', 'middle_name': 'михайлович'}, 'snils': '073-253-087 48'}
- C′: `passport_verify` {'passport': {'series': '4919', 'number': '313559', 'issued_by': 'ГУ МВД России по Краснодарскому краю', 'department_code': '147-657'}, 'person': {'last_name': 'Кукушкин', 'first_name': 'Валерий', 'm…
- FIELD `passport_verify.passport.series` [control_erred/i1 → control_erred] C=`4919` I=`4019` · контроль ошибся; шлюз восстановил эталон корпуса
- REPLY I: Понял, проверяю! Одну секунду. ✅ **Паспорт подтверждён!** Данные успешно сверены: | Поле | Данные | |---|---| | **ФИО** | кукушкин валерий михайлович | | **Серия / Номер** | 00 18 / 156126 | | **Выдан** | ГУ МВД России по Краснодарскому краю | | **Код подразделения** | 147-657 | | **СНИЛС** | ноль …

## decompose-033|1 · decompose · voice_raw · L1 = · L3 ≠ · C′≈C да · причина: **control_erred**
- USER[1]: алло сверьте паспорт сорок девятнадцать трииста тринадцать пятьсот пятьдесят девять выдан гу мвд россии по краснодарскому краю код подразделенияя сто сорок семь шестьсот пятьдесят семь сниилс ноль семьдесят три двести пейсят три ноль восемьдесят семь сорок восемсь кукушкин валерий михайлович
- seen PASSPORT `сорок девятнадцать трииста тринадцать пятьсот пятьдесят девять` → `00 07 551372`
- seen SNILS `ноль семьдесят три двести пейсят три ноль восемьдесят семь сорок восемсь` → `755-775-889 14`
- seen NAME `кукушкин валерий михайлович` → `Тарасов Евгений Геннадьевич`
- C: `passport_verify` {'passport': {'series': '4919', 'number': '313559', 'issued_by': 'ГУ МВД России по Краснодарскому краю', 'department_code': '147-657'}, 'person': {'last_name': 'Кукушкин', 'first_name': 'Валерий', 'm…
- I: `passport_verify` written={'passport': {'series': '0007', 'number': '551372', 'issued_by': 'ГУ МВД России по Краснодарскому краю', 'department_code': '147-657'}, 'person': {'last_name': 'Тарасов', 'first_name': 'Евгений', 'middle_name': 'Геннадьевич'}, 'snils': '755-775-889 14'} → restored={'passport': {'series': '4019', 'number': '313559', 'issued_by': 'ГУ МВД России по Краснодарскому краю', 'department_code': '147-657'}, 'person': {'last_name': 'кукушкин', 'first_name': 'валерий', 'middle_name': 'михайлович'}, 'snils': '073-253-087 48'}
- C′: `passport_verify` {'passport': {'series': '4919', 'number': '313559', 'issued_by': 'ГУ МВД России по Краснодарскому краю', 'department_code': '147-657'}, 'person': {'last_name': 'Кукушкин', 'first_name': 'Валерий', 'm…
- FIELD `passport_verify.passport.series` [control_erred/i1 → control_erred] C=`4919` I=`4019` · контроль ошибся; шлюз восстановил эталон корпуса
- REPLY I: Принято, сверяю паспорт кукушкина валерия михайловича. Одну минуту! ✅ **Паспорт подтверждён!** | Поле | Данные | |---|---| | **ФИО** | кукушкин валерий михайлович | | **Серия / Номер** | 0007 / 551372 | | **Выдан** | ГУ МВД России по Краснодарскому краю | | **Код подразделения** | 147-657 | | **СНИ…

## decompose-041|0 · decompose · voice_raw · L1 = · L3 ≠ · C′≈C да · причина: **other**
- USER[1]: ааа здравствуйте проведите оплатуу шестьсот двадцать рублей карта двадцать два ноль ноль девяносто два двадцать шесть шестьдесят один шестьдесят пять одиннадцать тридцать два сроок один двадцать девятого держатель владислав захаров
- seen CARD `двадцать два ноль ноль девяносто два двадцать шесть шестьдесят один шестьдесят пять одиннадцать тридцать два` → `0351 0367 2005 2934`
- seen NAME `владислав захаров` → `Олег Мещеряков`
- C: `payment_create` {'amount': {'value': '620.00', 'currency': 'RUB'}, 'payment_method_data': {'type': 'bank_card', 'card': {'number': '2200922661651132', 'expiry_month': '01', 'expiry_year': '2029', 'cardholder': 'VLAD…
- I: `payment_create` written={'amount': {'value': '620.00', 'currency': 'RUB'}, 'payment_method_data': {'type': 'bank_card', 'card': {'number': '0351036720052934', 'expiry_month': '01', 'expiry_year': '2029', 'cardholder': 'OLEG MESHCHERYAKOV'}}} → restored={'amount': {'value': '620.00', 'currency': 'RUB'}, 'payment_method_data': {'type': 'bank_card', 'card': {'number': '2200922661651132', 'expiry_month': '01', 'expiry_year': '2029', 'cardholder': 'VLADISLAV MESHCHERYAKOV'}}}
- C′: `payment_create` {'amount': {'value': '620.00', 'currency': 'RUB'}, 'payment_method_data': {'type': 'bank_card', 'card': {'number': '2200922661651132', 'expiry_month': '01', 'expiry_year': '2029', 'cardholder': 'VLAD…
- FIELD `payment_create.payment_method_data.card.cardholder` [other/misderived → name_partial] C=`VLADISLAV ZAKHAROV` I=`VLADISLAV MESHCHERYAKOV`
- REPLY I: Здравствуйте! Создаю платёж, одну секунду! Платёж создан! Вот детали: | Параметр | Значение | |---|---| | **ID платежа** | pay-1 | | **Статус** | ⏳ В обработке (pending) | | **Сумма** | 620,00 ₽ | | **Карта** | **** **** **** 1132 | | **Держатель** | VLADISLAV MESHCHERYAKOV | | **Срок действия** | …

## derive-008|0 · derive · sloppy · L1 = · L3 ≠ · C′≈C да · причина: **derived-only**
- USER[1]: добырй заипшите к офтальмологу соколову анну игоревну дата рождения 08.10.1997 телефон +79166983686 на завира на дсять утра
- seen NAME `соколову анну игоревну` → `Карпову Светлану Владимировну`
- seen DOB `08.10.1997` → `23.07.1997`
- seen PHONE `+79166983686` → `+79867888578`
- C: `clinic_book` {'patient': {'last_name': 'Соколова', 'first_name': 'Анна', 'middle_name': 'Игоревна', 'birth_date': '1997-10-08', 'age': 28, 'gender': 'F'}, 'phone': '+79166983686', 'speciality': 'офтальмолог', 'sl…
- I: `clinic_book` written={'patient': {'last_name': 'Карпова', 'first_name': 'Светлана', 'middle_name': 'Владимировна', 'birth_date': '1997-07-23', 'age': 29, 'gender': 'F'}, 'phone': '+79867888578', 'speciality': 'офтальмолог', 'slot': '2026-11-03T10:00:00+03:00'} → restored={'patient': {'last_name': 'соколова', 'first_name': 'анна', 'middle_name': 'игоревна', 'birth_date': '1997-10-08', 'age': 29, 'gender': 'F'}, 'phone': '+79166983686', 'speciality': 'офтальмолог', 'slot': '2026-11-03T10:00:00+03:00'}
- C′: `clinic_book` {'patient': {'last_name': 'Соколова', 'first_name': 'Анна', 'middle_name': 'Игоревна', 'birth_date': '1997-10-08', 'age': 28, 'gender': 'F'}, 'phone': '+79166983686', 'speciality': 'офтальмолог', 'sl…
- FIELD `clinic_book.patient.age` [derived/from_substitute → derived] C=`28` I=`29` · значение выведено из ПОДМЕНЫ; восстановление недостижимо
- REPLY I: Записываю! Всё нужное у меня есть — сейчас оформлю. **Данные:** - Пациент: соколова анна игоревна, 08.10.1997, пол — Ж, возраст — **29 лет** - Специалист: офтальмолог - Дата и время: **03.11.2026, 10:00** Готово! ✅ Запись успешно создана. **соколова анна игоревна** записана к **офтальмологу** на **…

## derive-008|1 · derive · sloppy · L1 = · L3 ≠ · C′≈C да · причина: **derived-only**
- USER[1]: добырй заипшите к офтальмологу соколову анну игоревну дата рождения 08.10.1997 телефон +79166983686 на завира на дсять утра
- seen NAME `соколову анну игоревну` → `Карпову Аглаю Валерьевну`
- seen DOB `08.10.1997` → `23.04.1997`
- seen PHONE `+79166983686` → `+79069605484`
- C: `clinic_book` {'patient': {'last_name': 'Соколова', 'first_name': 'Анна', 'middle_name': 'Игоревна', 'birth_date': '1997-10-08', 'age': 28, 'gender': 'F'}, 'phone': '+79166983686', 'speciality': 'офтальмолог', 'sl…
- I: `clinic_book` written={'patient': {'last_name': 'Карпова', 'first_name': 'Аглая', 'middle_name': 'Валерьевна', 'birth_date': '1997-04-23', 'age': 29, 'gender': 'F'}, 'phone': '+79069605484', 'speciality': 'офтальмолог', 'slot': '2026-10-27T10:00:00+03:00'} → restored={'patient': {'last_name': 'соколова', 'first_name': 'анна', 'middle_name': 'игоревна', 'birth_date': '1997-10-08', 'age': 29, 'gender': 'F'}, 'phone': '+79166983686', 'speciality': 'офтальмолог', 'slot': '2026-10-27T10:00:00+03:00'}
- C′: `clinic_book` {'patient': {'last_name': 'Соколова', 'first_name': 'Анна', 'middle_name': 'Игоревна', 'birth_date': '1997-10-08', 'age': 28, 'gender': 'F'}, 'phone': '+79166983686', 'speciality': 'офтальмолог', 'sl…
- FIELD `clinic_book.patient.age` [derived/from_substitute → derived] C=`28` I=`29` · значение выведено из ПОДМЕНЫ; восстановление недостижимо
- REPLY I: Добрый день! Записываю анну игоревну к офтальмологу на завтра, 27.10.2026, в 10:00. 🗓️ Готово! ✅ Запись подтверждена. **Детали записи:** - 👤 Пациент: соколова анна игоревна - 🏥 Специалист: Офтальмолог - 📅 Дата и время: 27 октября 2026 г., 10:00 - 📞 Телефон: +79166983686 Если нужно изменить или отме…

## derive-013|0 · derive · voice_raw · L1 = · L3 ≠ · C′≈C нет · причина: **other**
- USER[1]: заведитее карточкуу букин сергей иванович телефон восемь девятьсот двенадцать пятьсот сорок шесть пятьдесят девять пятьдесят инициалыы и латиницей заполните самии
- seen NAME `букин сергей иванович` → `Мещеряков Эдуард Максимович`
- seen PHONE `восемь девятьсот двенадцать пятьсот сорок шесть пятьдесят девять пятьдесят` → `+79485035936`
- C: `crm_upsert_contact` {'contact': {'last_name': 'Букин', 'first_name': 'Сергей', 'middle_name': 'Иванович', 'initials': 'С.И.', 'name_latin': 'Bukin Sergei', 'phone': '+79125465950', 'gender': 'M'}}
- I: `crm_upsert_contact` written={'contact': {'last_name': 'Мещеряков', 'first_name': 'Эдуард', 'middle_name': 'Максимович', 'phone': '+79485035936', 'initials': 'Э.М.', 'name_latin': 'Meshcheryakov Eduard', 'gender': 'M'}} → restored={'contact': {'last_name': 'букин', 'first_name': 'сергей', 'middle_name': 'иванович', 'phone': '+79125465950', 'initials': 'С.И.', 'name_latin': 'Meshcheryakov Sergei', 'gender': 'M'}}
- C′: `crm_upsert_contact` {'contact': {'last_name': 'Букин', 'first_name': 'Сергей', 'middle_name': 'Иванович', 'initials': 'С.И.', 'name_latin': 'Bukin Sergey', 'phone': '+79125465950'}}
- FIELD `crm_upsert_contact.contact.name_latin` [other/misderived → name_partial] C=`Bukin Sergei` I=`Meshcheryakov Sergei`
- REPLY I: Создаю карточку для букина сергея ивановича — инициалы и латиницу заполняю самостоятельно! Карточка успешно создана! Вот что заполнено: | Поле | Значение | |---|---| | Фамилия | букин | | Имя | сергей | | Отчество | иванович | | Телефон | восемь девятьсот двенадцать пятьсот сорок шесть пятьдесят де…

## derive-013|1 · derive · voice_raw · L1 = · L3 ≠ · C′≈C нет · причина: **other**
- USER[1]: заведитее карточкуу букин сергей иванович телефон восемь девятьсот двенадцать пятьсот сорок шесть пятьдесят девять пятьдесят инициалыы и латиницей заполните самии
- seen NAME `букин сергей иванович` → `Панов Илья Степанович`
- seen PHONE `восемь девятьсот двенадцать пятьсот сорок шесть пятьдесят девять пятьдесят` → `+79406814714`
- C: `crm_upsert_contact` {'contact': {'last_name': 'Букин', 'first_name': 'Сергей', 'middle_name': 'Иванович', 'initials': 'С.И.', 'name_latin': 'Bukin Sergey', 'phone': '+79125465950'}}
- I: `crm_upsert_contact` written={'contact': {'last_name': 'Панов', 'first_name': 'Илья', 'middle_name': 'Степанович', 'phone': '+79406814714', 'initials': 'И.С.', 'name_latin': 'Panov Ilya', 'gender': 'M'}} → restored={'contact': {'last_name': 'букин', 'first_name': 'сергей', 'middle_name': 'иванович', 'phone': '+79125465950', 'initials': 'С.И.', 'name_latin': 'Bukin Sergej', 'gender': 'M'}}
- C′: `crm_upsert_contact` {'contact': {'last_name': 'Букин', 'first_name': 'Сергей', 'middle_name': 'Иванович', 'gender': 'M', 'initials': 'С.И.', 'name_latin': 'Bukin Sergey', 'phone': '+79125465950'}}
- FIELD `crm_upsert_contact.contact.gender` [extra → extra:gender] C=`` I=`M`
- FIELD `crm_upsert_contact.contact.name_latin` [other/misderived → name_partial] C=`Bukin Sergey` I=`Bukin Sergej`
- REPLY I: Создаю карточку! Инициалы и латиницу заполню сам по ФИО: **С.И.** и **Bukin Sergej**. Карточка успешно создана! Вот что заполнено: - **ФИО:** букин сергей иванович - **Телефон:** восемь девятьсот двенадцать пятьсот сорок шесть пятьдесят девять пятьдесят - **Инициалы:** С.И. - **Латиница:** Bukin Se…

## derive-020|0 · derive · voice_raw · L1 = · L3 ≠ · C′≈C нет · причина: **other**
- USER[1]: добрыый день запишите к кардиологу миллера валерия леонидовича родилсяя двадцать первое сентября восьмидесятого года телефон восемь девятьсот двадцать два одиннадцать двенадцать двадцать три три на пятницу к девяти
- seen NAME `миллера валерия леонидовича` → `Чижова Захара Михайловича Лебедева`
- seen DOB `двадцать первое сентября восьмидесятого года` → `25.01.1980`
- seen PHONE `восемь девятьсот двадцать два одиннадцать двенадцать двадцать три три` → `+79767973911`
- C: `clinic_book` {'patient': {'last_name': 'Миллер', 'first_name': 'Валерий', 'middle_name': 'Леонидович', 'birth_date': '1980-09-21', 'age': 45, 'gender': 'M'}, 'phone': '+79221112233', 'speciality': 'кардиолог', 's…
- I: `clinic_book` written={'patient': {'last_name': 'Лебедев', 'first_name': 'Захар', 'middle_name': 'Михайлович', 'birth_date': '1980-01-25', 'age': 46, 'gender': 'M'}, 'phone': '+79767973911', 'speciality': 'кардиолог', 'slot': '2026-03-13T09:00:00+03:00'} → restored={'patient': {'last_name': 'родилсяя', 'first_name': 'валерий', 'middle_name': 'леонидович', 'birth_date': '1980-09-21', 'age': 46, 'gender': 'M'}, 'phone': '+79221112233', 'speciality': 'кардиолог', 'slot': '2026-03-13T09:00:00+03:00'}
- C′: `clinic_book` {'patient': {'last_name': 'Миллер', 'first_name': 'Валерий', 'middle_name': 'Леонидович', 'birth_date': '1980-09-21', 'age': 45, 'gender': 'M'}, 'phone': '+79221112233', 'speciality': 'кардиолог', 's…
- FIELD `clinic_book.patient.age` [derived/from_substitute → derived] C=`45` I=`46` · значение выведено из ПОДМЕНЫ; восстановление недостижимо
- FIELD `clinic_book.patient.last_name` [other/inflected → name_lemma] C=`Миллер` I=`родилсяя`
- REPLY I: Добрый день! Уточняю перед записью: понял вас так, что пациент — **родилсяя валерий леонидович** (двадцать первое сентября восьмидесятого года), и вы хотите записать его к кардиологу **миллеру** на **пятницу, 13 марта 2026 г., в 09:00**. Записываю! *(Возраст: 46 лет, пол: мужской)* Запись оформлена…

## derive-020|1 · derive · voice_raw · L1 ≠ · L3 ≠ · C′≈C нет · причина: **Б9-span**
- USER[1]: добрыый день запишите к кардиологу миллера валерия леонидовича родилсяя двадцать первое сентября восьмидесятого года телефон восемь девятьсот двадцать два одиннадцать двенадцать двадцать три три на пятницу к девяти
- seen NAME `миллера валерия леонидовича` → `Бирюкова Дмитрия Романовича Сазонова`
- seen DOB `двадцать первое сентября восьмидесятого года` → `01.01.1980`
- seen PHONE `восемь девятьсот двадцать два одиннадцать двенадцать двадцать три три` → `+79056280293`
- C: `clinic_book` {'patient': {'last_name': 'Миллер', 'first_name': 'Валерий', 'middle_name': 'Леонидович', 'birth_date': '1980-09-21', 'age': 45, 'gender': 'M'}, 'phone': '+79221112233', 'speciality': 'кардиолог', 's…
- I: — (без вызовов)
- C′: `clinic_book` {'patient': {'last_name': 'Миллер', 'first_name': 'Валерий', 'middle_name': 'Леонидович', 'birth_date': '1980-09-21', 'age': 45, 'gender': 'M'}, 'phone': '+79221112233', 'speciality': 'кардиолог', 's…
- FIELD `clinic_book.patient.age` [absent → absent:age] C=`45` I=``
- FIELD `clinic_book.patient.birth_date` [absent → absent:birth_date] C=`1980-09-21` I=``
- FIELD `clinic_book.patient.first_name` [absent → absent:first_name] C=`Валерий` I=``
- FIELD `clinic_book.patient.gender` [absent → absent:gender] C=`M` I=``
- FIELD `clinic_book.patient.last_name` [absent → absent:last_name] C=`Миллер` I=``
- FIELD `clinic_book.patient.middle_name` [absent → absent:middle_name] C=`Леонидович` I=``
- FIELD `clinic_book.phone` [absent → absent:phone] C=`+79221112233` I=``
- REPLY I: Добрый день! Уточните, пожалуйста, **полное ФИО пациента** — в вашем сообщении упоминаются и «миллер валерий леонидович», и «родилсяя(а)». Как правильно: пациент **миллер валерий леонидович** или **родилсяя валерий леонидович** (или иначе)? Остальное я понял: - 📅 Дата рождения: двадцать первое сент…

## derive-030|1 · derive · voice_raw · L1 = · L3 ≠ · C′≈C нет · причина: **other**
- USER[1]: здравствуйтее оформитее доставку на кузнецова дмитрия телефон восемсь девятьсот шестьдесят два восемесят восемь восемесят девять девяносто ноль адрес воткинск улица зарчная дом девяносто семь в квартира двести тридцать четыре посылка дваа килограмма индекс подберите самии
- seen NAME `кузнецова дмитрия` → `Цветкова Игната`
- seen PHONE `восемсь девятьсот шестьдесят два восемесят восемь восемесят девять девяносто ноль` → `+79330587644`
- seen LOC `воткинск улица зарчная дом девяносто семь в квартира двести тридцать четыре` → `Воткинск, улица Вязовая 116, кв. 92`
- C: `delivery_create_order` {'recipient': {'name': 'Кузнецов Дмитрий', 'phones': [{'number': '+79628889900'}]}, 'to_location': {'postal_code': '427430', 'city': 'Воткинск', 'address': 'ул. Зарничная, д. 97В, кв. 234'}, 'package…
- I: `delivery_create_order` written={'recipient': {'name': 'Цветков Игнат', 'phones': [{'number': '+79330587644'}]}, 'to_location': {'postal_code': '427430', 'city': 'Воткинск', 'address': 'ул. Вязовая, д. 116, кв. 92'}, 'packages': [{'weight': 2000}]} → restored={'recipient': {'name': 'кузнецов дмитрий', 'phones': [{'number': '+79628889900'}]}, 'to_location': {'postal_code': '427430', 'city': 'Воткинск', 'address': 'ул. зарчная, д. 97в, кв. 234'}, 'packages': [{'weight': 2000}]}
- C′: `delivery_create_order` {'recipient': {'name': 'Кузнецов Дмитрий', 'phones': [{'number': '+79628889900'}]}, 'to_location': {'postal_code': '427430', 'city': 'Воткинск', 'address': 'ул. Заречная, 97в, кв. 234'}, 'packages': …
- FIELD `delivery_create_order.to_location.address` [other/unbound → loc_street] C=`ул. Зарничная, д. 97В, кв. 234` I=`ул. зарчная, д. 97в, кв. 234`
- REPLY I: Здравствуйте! Оформляю заказ прямо сейчас! *(«самии» в конце — похоже, голосовой ввод, понял как «сами» — подбираю индекс самостоятельно.)* Заказ успешно оформлен! ✅ **Детали доставки:** - 📦 **Номер заказа:** ord-1 - 👤 **Получатель:** кузнецов дмитрий - 📞 **Телефон:** восемсь девятьсот шестьдесят д…

## derive-033|1 · derive · voice_raw · L1 = · L3 ≠ · C′≈C да · причина: **other**
- USER[1]: аа здравствуйте заведите карточкуу сергеев кирилл сергеевич телефон восемь девятьсот восемьдесят девять четыреста девяносто шесть тридцать семь ноль пять инициалы и латиницей заполните сами
- seen NAME `сергеев кирилл сергеевич` → `Сазонов Тарас Семёнович`
- seen PHONE `восемь девятьсот восемьдесят девять четыреста девяносто шесть тридцать семь ноль пять` → `+79104584181`
- C: `crm_upsert_contact` {'contact': {'last_name': 'Сергеев', 'first_name': 'Кирилл', 'middle_name': 'Сергеевич', 'phone': '+79894963705', 'gender': 'M', 'initials': 'К.С.', 'name_latin': 'Sergeev Kirill'}}
- I: `crm_upsert_contact` written={'contact': {'last_name': 'Сазонов', 'first_name': 'Тарас', 'middle_name': 'Семёнович', 'phone': '+79104584181', 'initials': 'Т.С.', 'name_latin': 'Sazonov Taras'}} → restored={'contact': {'last_name': 'сергеев', 'first_name': 'кирилл', 'middle_name': 'сергеевич', 'phone': '+79894963705', 'initials': 'К.С.', 'name_latin': 'Sergeev Kirill'}}
- C′: `crm_upsert_contact` {'contact': {'last_name': 'Сергеев', 'first_name': 'Кирилл', 'middle_name': 'Сергеевич', 'initials': 'К.С.', 'name_latin': 'Sergeev Kirill', 'gender': 'M', 'phone': '+79894963705'}}
- FIELD `crm_upsert_contact.contact.gender` [absent → absent:gender] C=`M` I=``
- REPLY I: Здравствуйте! Сейчас заведу карточку — инициалы **К.С.**, латиницей **Sergeev Kirill**. Готово! Карточка успешно создана: - **ФИО:** сергеев кирилл сергеевич - **Телефон:** восемь девятьсот восемьдесят девять четыреста девяносто шесть тридцать семь ноль пять - **Инициалы:** К.С. - **Латиница:** Ser…

## derive-036|0 · derive · voice_itn · L1 ≠ · L3 ≠ · C′≈C да · причина: **other**
- USER[1]: запишите к терапевту громову марину борисовну дата рождения 02 06 1992 телефон 89824220054 в среду после трёх
- seen NAME `громову марину борисовну` → `Гущину Беллу Михайловну`
- seen DOB `02 06 1992` → `08.10.1962`
- seen PHONE `89824220054` → `+79260610419`
- C: `clinic_book` {'patient': {'last_name': 'Громова', 'first_name': 'Марина', 'middle_name': 'Борисовна', 'birth_date': '1992-06-02', 'age': 34, 'gender': 'F'}, 'phone': '+79824220054', 'speciality': 'терапевт', 'slo…
- I: `clinic_book` written={'patient': {'last_name': 'Гущина', 'first_name': 'Белла', 'middle_name': 'Михайловна', 'birth_date': '1962-10-08', 'age': 64, 'gender': 'F'}, 'phone': '+79260610419', 'speciality': 'терапевт', 'slot': '2026-11-11T15:00:00+03:00'} → restored={'patient': {'last_name': 'громова', 'first_name': 'марина', 'middle_name': 'борисовна', 'birth_date': '0206-19-92', 'age': 64, 'gender': 'F'}, 'phone': '+79824220054', 'speciality': 'терапевт', 'slot': '2026-11-11T15:00:00+03:00'} · refusal=date_invalid
- I: `clinic_book` written={'patient': {'last_name': 'Гущина', 'first_name': 'Белла', 'middle_name': 'Михайловна', 'birth_date': '1962-10-08', 'age': 64, 'gender': 'F'}, 'phone': '+79260610419', 'speciality': 'терапевт', 'slot': '2026-11-11T15:00:00+03:00'} → restored={'patient': {'last_name': 'громова', 'first_name': 'марина', 'middle_name': 'борисовна', 'birth_date': '0206-19-92', 'age': 64, 'gender': 'F'}, 'phone': '+79824220054', 'speciality': 'терапевт', 'slot': '2026-11-11T15:00:00+03:00'} · refusal=date_invalid
- C′: `clinic_book` {'patient': {'last_name': 'Громова', 'first_name': 'Марина', 'middle_name': 'Борисовна', 'birth_date': '1992-06-02', 'age': 34, 'gender': 'F'}, 'phone': '+79824220054', 'speciality': 'терапевт', 'slo…
- FIELD `clinic_book.patient.age` [other/misderived → other/misderived] C=`34` I=`64`
- FIELD `clinic_book.patient.birth_date` [validated_refused/date_invalid → validated_refused] C=`1992-06-02` I=`0206-19-92`
- FIELD `clinic_book.patient.age` [extra → extra:age] C=`` I=`64`
- FIELD `clinic_book.patient.birth_date` [extra → extra:birth_date] C=`` I=`0206-19-92`
- FIELD `clinic_book.patient.first_name` [extra → extra:first_name] C=`` I=`марина`
- FIELD `clinic_book.patient.gender` [extra → extra:gender] C=`` I=`F`
- FIELD `clinic_book.patient.last_name` [extra → extra:last_name] C=`` I=`громова`
- FIELD `clinic_book.patient.middle_name` [extra → extra:middle_name] C=`` I=`борисовна`
- FIELD `clinic_book.phone` [extra → extra:phone] C=`` I=`+79824220054`
- REPLY I: Сейчас всё оформлю! Сегодня четверг, 2026-09-02 — ближайшая среда будет **11 ноября**. Запишу на **15:00** (первый слот после трёх). марина — женское имя, возраст на сегодня: **64 года** (день рождения 02 06 1992 уже прошёл в этом году). Попробую ещё раз с корректной датой рождения: К сожалению, си…

## derive-036|1 · derive · voice_itn · L1 ≠ · L3 ≠ · C′≈C да · причина: **other**
- USER[1]: запишите к терапевту громову марину борисовну дата рождения 02 06 1992 телефон 89824220054 в среду после трёх
- seen NAME `громову марину борисовну` → `Ершову Агату Васильевну`
- seen DOB `02 06 1992` → `26.11.2015`
- seen PHONE `89824220054` → `+79522646051`
- C: `clinic_book` {'patient': {'last_name': 'Громова', 'first_name': 'Марина', 'middle_name': 'Борисовна', 'birth_date': '1992-06-02', 'age': 34, 'gender': 'F'}, 'phone': '+79824220054', 'speciality': 'терапевт', 'slo…
- I: `clinic_book` written={'patient': {'last_name': 'Ершова', 'first_name': 'Агата', 'middle_name': 'Васильевна', 'birth_date': '2015-11-26', 'age': 10, 'gender': 'F'}, 'phone': '+79522646051', 'speciality': 'терапевт', 'slot': '2026-09-09T15:00:00+03:00'} → restored={'patient': {'last_name': 'громова', 'first_name': 'марина', 'middle_name': 'борисовна', 'birth_date': '0206-19-92', 'age': 10, 'gender': 'F'}, 'phone': '+79824220054', 'speciality': 'терапевт', 'slot': '2026-09-09T15:00:00+03:00'} · refusal=date_invalid
- I: `clinic_book` written={'patient': {'last_name': 'Ершова', 'first_name': 'Агата', 'middle_name': 'Васильевна', 'birth_date': '2015-11-26', 'age': 10, 'gender': 'F'}, 'phone': '+79522646051', 'speciality': 'терапевт', 'slot': '2026-09-09T15:00:00+03:00'} → restored={'patient': {'last_name': 'громова', 'first_name': 'марина', 'middle_name': 'борисовна', 'birth_date': '0206-19-92', 'age': 10, 'gender': 'F'}, 'phone': '+79824220054', 'speciality': 'терапевт', 'slot': '2026-09-09T15:00:00+03:00'} · refusal=date_invalid
- C′: `clinic_book` {'patient': {'last_name': 'Громова', 'first_name': 'Марина', 'middle_name': 'Борисовна', 'birth_date': '1992-06-02', 'age': 34, 'gender': 'F'}, 'phone': '+79824220054', 'speciality': 'терапевт', 'slo…
- FIELD `clinic_book.patient.age` [derived/from_substitute → derived] C=`34` I=`10` · значение выведено из ПОДМЕНЫ; восстановление недостижимо
- FIELD `clinic_book.patient.birth_date` [validated_refused/date_invalid → validated_refused] C=`1992-06-02` I=`0206-19-92`
- FIELD `clinic_book.patient.age` [extra → extra:age] C=`` I=`10`
- FIELD `clinic_book.patient.birth_date` [extra → extra:birth_date] C=`` I=`0206-19-92`
- FIELD `clinic_book.patient.first_name` [extra → extra:first_name] C=`` I=`марина`
- FIELD `clinic_book.patient.gender` [extra → extra:gender] C=`` I=`F`
- FIELD `clinic_book.patient.last_name` [extra → extra:last_name] C=`` I=`громова`
- FIELD `clinic_book.patient.middle_name` [extra → extra:middle_name] C=`` I=`борисовна`
- FIELD `clinic_book.phone` [extra → extra:phone] C=`` I=`+79824220054`
- REPLY I: Вычислю данные пациентки: - **Пол:** женский (марина — женское имя) → F - **Возраст:** с 02 06 1992 по 04.09.2026 = **10 лет** (день рождения ещё не наступил в этом году) - **Ближайшая среда после 15:00:** 09.09.2026, 15:00 (МСК) Записываю! Система вернула ошибку по дате рождения — попробую ещё раз…

## derive-053|0 · derive · chat · L1 = · L3 ≠ · C′≈C нет · причина: **other**
- USER[1]: добрый день заведите карточку новиков игорь валентинович телефон 8-951-076-29-71 почта novikov96@gmail.com инициалы и латиницей заполните сами
- seen NAME `новиков игорь валентинович` → `Шилов Сергей Олегович`
- seen PHONE `8-951-076-29-71` → `+79212132394`
- seen EMAIL `novikov96@gmail.com` → `jairzvug@example.ru`
- C: `crm_upsert_contact` {'contact': {'last_name': 'Новиков', 'first_name': 'Игорь', 'middle_name': 'Валентинович', 'gender': 'M', 'phone': '+79510762971', 'email': 'novikov96@gmail.com', 'initials': 'И.В.', 'name_latin': 'N…
- I: `crm_upsert_contact` written={'contact': {'last_name': 'Шилов', 'first_name': 'Сергей', 'middle_name': 'Олегович', 'initials': 'С.О.', 'name_latin': 'Shilov Sergey', 'phone': '+79212132394', 'email': 'jairzvug@example.ru'}} → restored={'contact': {'last_name': 'новиков', 'first_name': 'игорь', 'middle_name': 'валентинович', 'initials': 'И.В.', 'name_latin': 'Novikov Igor', 'phone': '+79510762971', 'email': 'novikov96@gmail.com'}}
- C′: `crm_upsert_contact` {'contact': {'last_name': 'Новиков', 'first_name': 'Игорь', 'middle_name': 'Валентинович', 'initials': 'И.В.', 'name_latin': 'Novikov Igor', 'phone': '+79510762971', 'email': 'novikov96@gmail.com'}}
- FIELD `crm_upsert_contact.contact.gender` [absent → absent:gender] C=`M` I=``
- REPLY I: Добрый день! Заполняю карточку — инициалы **И.В.**, латиница **Novikov Igor**. Карточка успешно создана! Вот что записано: - **ФИО:** новиков игорь валентинович - **Инициалы:** И.В. - **Латиница:** Novikov Igor - **Телефон:** 8-951-076-29-71 - **E-mail:** novikov96@gmail.com - **ID карточки:** c-1 …

## derive-053|1 · derive · chat · L1 = · L3 ≠ · C′≈C да · причина: **other**
- USER[1]: добрый день заведите карточку новиков игорь валентинович телефон 8-951-076-29-71 почта novikov96@gmail.com инициалы и латиницей заполните сами
- seen NAME `новиков игорь валентинович` → `Устинов Кузьма Васильевич`
- seen PHONE `8-951-076-29-71` → `+79733692535`
- seen EMAIL `novikov96@gmail.com` → `ycajeuvo@example.ru`
- C: `crm_upsert_contact` {'contact': {'last_name': 'Новиков', 'first_name': 'Игорь', 'middle_name': 'Валентинович', 'initials': 'И.В.', 'name_latin': 'Novikov Igor', 'gender': 'M', 'phone': '+79510762971', 'email': 'novikov9…
- I: `crm_upsert_contact` written={'contact': {'last_name': 'Устинов', 'first_name': 'Кузьма', 'middle_name': 'Васильевич', 'phone': '+79733692535', 'email': 'ycajeuvo@example.ru', 'initials': 'К.В.', 'name_latin': 'Ustinov Kuzma'}} → restored={'contact': {'last_name': 'новиков', 'first_name': 'игорь', 'middle_name': 'валентинович', 'phone': '+79510762971', 'email': 'novikov96@gmail.com', 'initials': 'И.В.', 'name_latin': 'Novikov Igor'}}
- C′: `crm_upsert_contact` {'contact': {'last_name': 'Новиков', 'first_name': 'Игорь', 'middle_name': 'Валентинович', 'phone': '+79510762971', 'email': 'novikov96@gmail.com', 'gender': 'M', 'initials': 'И.В.', 'name_latin': 'N…
- FIELD `crm_upsert_contact.contact.gender` [absent → absent:gender] C=`M` I=``
- REPLY I: Добрый день! Заполняю карточку прямо сейчас. - **Инициалы:** И.В. - **Латиница:** Novikov Igor Карточка успешно создана! Вот что записано: | Поле | Значение | |---|---| | **Фамилия** | новиков | | **Имя** | игорь | | **Отчество** | валентинович | | **Инициалы** | И.В. | | **Латиница** | Novikov Igo…

## result_feed-003|1 · result_feed · chat · L1 = · L3 ≠ · C′≈C да · причина: **other**
- USER[1]: привет запишите меня к кардиологу я у вас в базе телефон 8 999 110 25 77
- USER[2]: на завтра на десять утра
- seen PHONE `8 999 110 25 77` → `+79391143983`
- C: `crm_find_contact` {'query': {'phone': '+79991102577'}}
- C: `clinic_book` {'patient': {'last_name': 'Тарасова', 'first_name': 'Алла', 'middle_name': 'Анатольевна', 'birth_date': '1960-09-27', 'age': 65, 'gender': 'F'}, 'phone': '+79991102577', 'speciality': 'кардиолог', 's…
- I: `crm_find_contact` written={'query': {'phone': '+79391143983'}} → restored={'query': {'phone': '+79991102577'}}
- I: `clinic_book` written={'patient': {'last_name': 'Рыжих', 'first_name': 'Елена', 'middle_name': 'Петровна', 'birth_date': '1960-10-01', 'age': 65, 'gender': 'F'}, 'phone': '+79391143983', 'speciality': 'кардиолог', 'slot': '2026-01-15T10:00:00+03:00'} → restored={'patient': {'last_name': 'тарасова', 'first_name': 'алла', 'middle_name': 'анатольевна', 'birth_date': '1960-09-27', 'age': 65, 'gender': 'F'}, 'phone': '+79991102577', 'speciality': 'кардиолог', 'slot': '2026-01-15T10:00:00+03:00'}
- C′: `crm_find_contact` {'query': {'phone': '+79991102577'}}
- C′: `clinic_book` {'patient': {'last_name': 'Тарасова', 'first_name': 'Алла', 'middle_name': 'Анатольевна', 'birth_date': '1960-09-27', 'age': 65, 'gender': 'F'}, 'phone': '+79991102577', 'speciality': 'кардиолог', 's…
- REPLY I: Записываю вас к кардиологу на завтра, 15 января в 10:00! ⏳ Готово! ✅ Вы записаны: - **Пациент:** тарасова алла анатольевна - **Специалист:** Кардиолог - **Дата и время:** 15 января 2026, 10:00 Отправить вам СМС с подтверждением записи?

## result_feed-004|0 · result_feed · sloppy · L1 = · L3 ≠ · C′≈C да · причина: **other**
- USER[1]: привет запишите меня к стоматологу я у вас в базе телефон +79821651435
- USER[2]: на завтра на днсять ура
- seen PHONE `+79821651435` → `+79483219136`
- C: `crm_find_contact` {'query': {'phone': '+79821651435'}}
- C: `clinic_book` {'patient': {'last_name': 'Кузнецова', 'first_name': 'Ольга', 'middle_name': 'Дмитриевна', 'birth_date': '1967-09-10', 'age': 58, 'gender': 'F'}, 'phone': '+79821651435', 'speciality': 'стоматолог', …
- I: `crm_find_contact` written={'query': {'phone': '+79483219136'}} → restored={'query': {'phone': '+79821651435'}}
- I: `clinic_book` written={'patient': {'last_name': 'Савченко', 'first_name': 'Николь', 'middle_name': 'Андреевна', 'birth_date': '1967-11-06', 'age': 58, 'gender': 'F'}, 'phone': '+79483219136', 'speciality': 'стоматолог', 'slot': '2026-01-29T10:00:00+04:00'} → restored={'patient': {'last_name': 'кузнецова', 'first_name': 'ольга', 'middle_name': 'дмитриевна', 'birth_date': '1967-09-10', 'age': 58, 'gender': 'F'}, 'phone': '+79821651435', 'speciality': 'стоматолог', 'slot': '2026-01-29T10:00:00+04:00'}
- C′: `crm_find_contact` {'query': {'phone': '+79821651435'}}
- C′: `clinic_book` {'patient': {'last_name': 'кузнецова', 'first_name': 'ольга', 'middle_name': 'дмитриевна', 'birth_date': '1967-09-10', 'age': 58, 'gender': 'F'}, 'phone': '+79821651435', 'speciality': 'стоматолог', …
- REPLY I: Записываю вас на завтра, 29 января в 10:00! ⏳ Готово! ✅ Вы записаны! 📋 **Детали записи:** - 👤 кузнецову ольга дмитриевна - 🦷 Стоматолог - 📅 29 января 2026 года в 10:00 Отправить вам СМС с подтверждением на номер +79821651435?

## result_feed-007|0 · result_feed · sloppy · L1 = · L3 ≠ · C′≈C нет · причина: **other**
- USER[1]: здоасте запишите меня к терапевту я у вас в базе телефон 8-916-158-76-76
- USER[2]: на завтра на деясть уьра
- seen PHONE `8-916-158-76-76` → `+79815972095`
- C: `crm_find_contact` {'query': {'phone': '+79161587676'}}
- C: `clinic_book` {'patient': {'last_name': 'Сергеев', 'first_name': 'Кирилл', 'middle_name': 'Сергеевич', 'birth_date': '1995-04-28', 'age': 31, 'gender': 'M'}, 'phone': '+79161587676', 'speciality': 'терапевт', 'slo…
- I: `crm_find_contact` written={'query': {'phone': '+79815972095'}} → restored={'query': {'phone': '+79161587676'}}
- I: `clinic_book` written={'patient': {'last_name': 'Сазонов', 'first_name': 'Виктор', 'middle_name': 'Юрьевич', 'birth_date': '1995-07-16', 'age': 31, 'gender': 'M'}, 'phone': '+79815972095', 'speciality': 'терапевт', 'slot': '2026-09-05T10:00:00+03:00'} → restored={'patient': {'last_name': 'сергеев', 'first_name': 'кирилл', 'middle_name': 'сергеевич', 'birth_date': '1995-04-28', 'age': 31, 'gender': 'M'}, 'phone': '+79161587676', 'speciality': 'терапевт', 'slot': '2026-09-05T10:00:00+03:00'}
- C′: `crm_find_contact` {'query': {'phone': '+79161587676'}}
- C′: `clinic_book` {'patient': {'last_name': 'Сергеев', 'first_name': 'Кирилл', 'middle_name': 'Сергеевич', 'birth_date': '1995-04-28', 'age': 31, 'gender': 'M'}, 'phone': '+79161587676', 'speciality': 'терапевт', 'slo…
- REPLY I: Записываю вас на завтра, 5 сентября, в 10:00! ⏳ Готово! ✅ Вы записаны: - 👤 **сергеев кирилл сергеевич** - 👨‍⚕️ **Специалист:** терапевт - 📅 **Дата и время:** 5 сентября 2026 г., 10:00 Если хотите, могу отправить вам СМС-напоминание на номер 8-916-158-76-76. Скажите — отправить?

## result_feed-007|1 · result_feed · sloppy · L1 = · L3 ≠ · C′≈C нет · причина: **other**
- USER[1]: здоасте запишите меня к терапевту я у вас в базе телефон 8-916-158-76-76
- USER[2]: на завтра на деясть уьра
- seen PHONE `8-916-158-76-76` → `+79042655788`
- C: `crm_find_contact` {'query': {'phone': '+79161587676'}}
- C: `clinic_book` {'patient': {'last_name': 'Сергеев', 'first_name': 'Кирилл', 'middle_name': 'Сергеевич', 'birth_date': '1995-04-28', 'age': 31, 'gender': 'M'}, 'phone': '+79161587676', 'speciality': 'терапевт', 'slo…
- I: `crm_find_contact` written={'query': {'phone': '+79042655788'}} → restored={'query': {'phone': '+79161587676'}}
- I: `clinic_book` written={'patient': {'last_name': 'Гущин', 'first_name': 'Максим', 'middle_name': 'Григорьевич', 'birth_date': '1995-09-11', 'age': 31, 'gender': 'M'}, 'phone': '+79042655788', 'speciality': 'терапевт', 'slot': '2026-09-28T10:00:00+03:00'} → restored={'patient': {'last_name': 'сергеев', 'first_name': 'кирилл', 'middle_name': 'сергеевич', 'birth_date': '1995-04-28', 'age': 31, 'gender': 'M'}, 'phone': '+79161587676', 'speciality': 'терапевт', 'slot': '2026-09-28T10:00:00+03:00'}
- C′: `crm_find_contact` {'query': {'phone': '+79161587676'}}
- C′: `clinic_book` {'patient': {'last_name': 'Сергеев', 'first_name': 'Кирилл', 'middle_name': 'Сергеевич', 'birth_date': '1995-04-28', 'age': 31, 'gender': 'M'}, 'phone': '+79161587676', 'speciality': 'терапевт', 'slo…
- REPLY I: Записываю вас на **28 сентября 2026 в 10:00**! ⏳ Готово! ✅ Вы успешно записаны! 📋 **Детали записи:** - **Пациент:** сергеев кирилл сергеевич - **Врач:** Терапевт - **Дата и время:** 28 сентября 2026, 10:00 - **Номер записи:** apt-1 Ждём вас завтра! Если нужно будет перенести или отменить запись — о…

## result_feed-009|0 · result_feed · voice_raw · L1 ≠ · L3 ≠ · C′≈C нет · причина: **other**
- USER[1]: ааа здравствуйте запишите меня к кардиологуу я у вас в базее телефон восемь девятьсот девять девятьсот тридцать один двадцать восем пятнадцать
- USER[2]: наа завтра на десять утра
- seen PHONE `восемь девятьсот девять девятьсот тридцать один двадцать восем пятнадцать` → `+79031513366`
- C: `crm_find_contact` {'query': {'phone': '+79099312815'}}
- C: `clinic_book` {'patient': {'last_name': 'Воронина', 'first_name': 'Елена', 'middle_name': 'Сергеевна', 'birth_date': '2002-05-26', 'age': 24, 'gender': 'F'}, 'phone': '+79099312815', 'speciality': 'кардиолог', 'sl…
- I: `crm_find_contact` written={'query': {'phone': '+79031513366'}} → restored={'query': {'phone': '+79099312815'}}
- I: `clinic_book` written={'patient': {'last_name': 'Мкртчян', 'first_name': 'Мария', 'middle_name': 'Григорьевна', 'birth_date': '2002-04-18', 'age': 24, 'gender': 'F'}, 'phone': '+79031513366', 'speciality': 'кардиолог', 'slot': '2026-12-12T10:00:00+03:00'} → restored={'patient': {'last_name': 'воронина', 'first_name': 'елена', 'middle_name': 'сергеевна', 'birth_date': '2002-05-26', 'age': 24, 'gender': 'F'}, 'phone': '+79099312815', 'speciality': 'кардиолог', 'slot': '2026-12-12T10:00:00+03:00'}
- I: `notify_sms` written={'number': '+79031513366', 'text': 'Мария Григорьевна, вы записаны к кардиологу на 12.12.2026 в 10:00. Ждём вас в клинике! По вопросам звоните администратору.', 'sign': 'Klinika'} → restored={'number': '+79099312815', 'text': 'елена сергеевна, вы записаны к кардиологу на 12.12.2026 в 10:00. Ждём вас в клинике! По вопросам звоните администратору.', 'sign': 'Klinika'}
- C′: `crm_find_contact` {'query': {'phone': '+79099312815'}}
- C′: `clinic_book` {'patient': {'last_name': 'Воронина', 'first_name': 'Елена', 'middle_name': 'Сергеевна', 'birth_date': '2002-05-26', 'age': 24, 'gender': 'F'}, 'phone': '+79099312815', 'speciality': 'кардиолог', 'sl…
- C′: `notify_sms` {'number': '+79099312815', 'text': 'Елена Сергеевна, вы записаны к кардиологу на 5 сентября 2026 г. в 10:00. Ждём вас! По вопросам звоните в клинику.', 'sign': 'Klinika'}
- FIELD `notify_sms.number` [extra → extra:number] C=`` I=`+79099312815`
- REPLY I: Записываю вас на **12 декабря 2026 года в 10:00**! ⏳ Готово! ✅ Вы записаны к кардиологу. Отправлю вам СМС с подтверждением! Всё готово! 🎉 **Ваша запись:** - 👤 воронина елена сергеевна - 🏥 Кардиолог - 📅 12 декабря 2026 г. в 10:00 СМС с подтверждением отправлено на номер восемь девятьсот девять девят…

## result_feed-009|1 · result_feed · voice_raw · L1 = · L3 ≠ · C′≈C да · причина: **other**
- USER[1]: ааа здравствуйте запишите меня к кардиологуу я у вас в базее телефон восемь девятьсот девять девятьсот тридцать один двадцать восем пятнадцать
- USER[2]: наа завтра на десять утра
- seen PHONE `восемь девятьсот девять девятьсот тридцать один двадцать восем пятнадцать` → `+79040003459`
- C: `crm_find_contact` {'query': {'phone': '+79099312815'}}
- C: `clinic_book` {'patient': {'last_name': 'Воронина', 'first_name': 'Елена', 'middle_name': 'Сергеевна', 'birth_date': '2002-05-26', 'age': 24, 'gender': 'F'}, 'phone': '+79099312815', 'speciality': 'кардиолог', 'sl…
- I: `crm_find_contact` written={'query': {'phone': '+79040003459'}} → restored={'query': {'phone': '+79099312815'}}
- I: `clinic_book` written={'patient': {'last_name': 'Савчук', 'first_name': 'Иоланта', 'middle_name': 'Борисовна', 'birth_date': '2002-09-22', 'age': 24, 'gender': 'F'}, 'phone': '+79040003459', 'speciality': 'кардиолог', 'slot': '2026-11-21T10:00:00+04:00'} → restored={'patient': {'last_name': 'воронина', 'first_name': 'елена', 'middle_name': 'сергеевна', 'birth_date': '2002-05-26', 'age': 24, 'gender': 'F'}, 'phone': '+79099312815', 'speciality': 'кардиолог', 'slot': '2026-11-21T10:00:00+04:00'}
- C′: `crm_find_contact` {'query': {'phone': '+79099312815'}}
- C′: `clinic_book` {'patient': {'last_name': 'Воронина', 'first_name': 'Елена', 'middle_name': 'Сергеевна', 'birth_date': '2002-05-26', 'age': 24, 'gender': 'F'}, 'phone': '+79099312815', 'speciality': 'кардиолог', 'sl…
- REPLY I: Готово! ✅ Вы записаны к кардиологу! 📋 **Детали записи:** - 👤 воронина елена сергеевна - 👨‍⚕️ Кардиолог - 📅 21 ноября 2026 г., **10:00** Ждём вас! Если нужно будет перенести или отменить запись — обращайтесь 😊

## result_feed-028|0 · result_feed · chat · L1 ≠ · L3 ≠ · C′≈C нет · причина: **partial-call**
- USER[1]: привет запишите меня к неврологу я у вас в базе телефон 89776996134
- USER[2]: давайте в четверг к девяти
- seen PHONE `89776996134` → `+79321356317`
- C: `crm_find_contact` {'query': {'phone': '+79776996134'}}
- C: `clinic_book` {'patient': {'last_name': 'Громова', 'first_name': 'Марина', 'middle_name': 'Борисовна', 'birth_date': '1973-05-24', 'age': 53, 'gender': 'F'}, 'phone': '+79776996134', 'speciality': 'невролог', 'slo…
- C: `notify_sms` {'number': '+79776996134', 'text': 'Марина Борисовна, вы записаны к неврологу на 10 сентября 2026 в 09:00. Ждём вас в клинике! По вопросам звоните администратору.', 'sign': 'Klinika'}
- I: `crm_find_contact` written={'query': {'phone': '+79321356317'}} → restored={'query': {'phone': '+79776996134'}}
- I: `clinic_book` written={'patient': {'last_name': 'Седых', 'first_name': 'Эльвира', 'middle_name': 'Сергеевна', 'birth_date': '1973-04-18', 'age': 53, 'gender': 'F'}, 'phone': '+79321356317', 'speciality': 'невролог', 'slot': '2026-09-10T09:00:00+04:00'} → restored={'patient': {'last_name': 'громова', 'first_name': 'марина', 'middle_name': 'борисовна', 'birth_date': '1973-05-24', 'age': 53, 'gender': 'F'}, 'phone': '+79776996134', 'speciality': 'невролог', 'slot': '2026-09-10T09:00:00+04:00'}
- C′: `crm_find_contact` {'query': {'phone': '+79776996134'}}
- C′: `clinic_book` {'patient': {'last_name': 'Громова', 'first_name': 'Марина', 'middle_name': 'Борисовна', 'birth_date': '1973-05-24', 'age': 53, 'gender': 'F'}, 'phone': '+79776996134', 'speciality': 'невролог', 'slo…
- FIELD `notify_sms.number` [absent → absent:number] C=`+79776996134` I=``
- REPLY I: Сегодня пятница, 4 сентября — значит, ближайший четверг — **10 сентября 2026 года**. Записываю вас на 09:00! 📅 Готово, марина борисовна! ✅ **Запись подтверждена:** - 👩‍⚕️ Специалист: невролог - 📅 Дата: 10 сентября 2026 (четверг) - 🕘 Время: 09:00 - 📞 Телефон: 89776996134 Если захотите перенести или …

## result_feed-028|1 · result_feed · chat · L1 ≠ · L3 ≠ · C′≈C нет · причина: **Б8-echo**
- USER[1]: привет запишите меня к неврологу я у вас в базе телефон 89776996134
- USER[2]: давайте в четверг к девяти
- seen PHONE `89776996134` → `+79102969683`
- C: `crm_find_contact` {'query': {'phone': '+79776996134'}}
- C: `clinic_book` {'patient': {'last_name': 'Громова', 'first_name': 'Марина', 'middle_name': 'Борисовна', 'birth_date': '1973-05-24', 'age': 53, 'gender': 'F'}, 'phone': '+79776996134', 'speciality': 'невролог', 'slo…
- C: `notify_sms` {'number': '+79776996134', 'text': 'Марина Борисовна, вы записаны к неврологу на 4 сентября 2026 года в 09:00. Ждём вас в клинике! Если нужно перенести — позвоните нам.', 'sign': 'Klinika'}
- I: `crm_find_contact` written={'query': {'phone': '+79102969683'}} → restored={'query': {'phone': '+79776996134'}}
- C′: `crm_find_contact` {'query': {'phone': '+79776996134'}}
- C′: `clinic_book` {'patient': {'last_name': 'Громова', 'first_name': 'Марина', 'middle_name': 'Борисовна', 'birth_date': '1973-05-24', 'age': 53, 'gender': 'F'}, 'phone': '+79776996134', 'speciality': 'невролог', 'slo…
- FIELD `clinic_book.patient.age` [absent → absent:age] C=`53` I=``
- FIELD `clinic_book.patient.birth_date` [absent → absent:birth_date] C=`1973-05-24` I=``
- FIELD `clinic_book.patient.first_name` [absent → absent:first_name] C=`Марина` I=``
- FIELD `clinic_book.patient.gender` [absent → absent:gender] C=`F` I=``
- FIELD `clinic_book.patient.last_name` [absent → absent:last_name] C=`Громова` I=``
- FIELD `clinic_book.patient.middle_name` [absent → absent:middle_name] C=`Борисовна` I=``
- FIELD `clinic_book.phone` [absent → absent:phone] C=`+79776996134` I=``
- FIELD `notify_sms.number` [absent → absent:number] C=`+79776996134` I=``
- REPLY I: Уточню — сегодня как раз **четверг, 4 сентября**. Вы имеете в виду **сегодня в 09:00** или **следующий четверг, 11 сентября**?

## result_feed-031|0 · result_feed · voice_itn · L1 ≠ · L3 ≠ · C′≈C нет · причина: **partial-call**
- USER[1]: алло запишите меня к стоматологу я у вас в базе тел 8-951-044-37-07
- USER[2]: давайте в четверг к девяти
- seen PHONE `8-951-044-37-07` → `+79278808172`
- C: `crm_find_contact` {'query': {'phone': '+79510443707'}}
- C: `clinic_book` {'patient': {'last_name': 'миллер', 'first_name': 'валерия', 'middle_name': 'леонидовна', 'birth_date': '1965-03-19', 'age': 61, 'gender': 'F'}, 'phone': '+79510443707', 'speciality': 'стоматолог', '…
- C: `notify_sms` {'number': '+79510443707', 'text': 'Валерия Леонидовна, вы записаны к стоматологу на 3 сентября в 09:00. Ждём вас в клинике! По вопросам звоните нам.', 'sign': 'Klinika'}
- I: `crm_find_contact` written={'query': {'phone': '+79278808172'}} → restored={'query': {'phone': '+79510443707'}}
- I: `clinic_book` written={'patient': {'last_name': 'Платон Шилов', 'first_name': 'Милена', 'middle_name': 'Андреевна', 'birth_date': '1965-02-25', 'age': 61, 'gender': 'F'}, 'phone': '+79278808172', 'speciality': 'стоматолог', 'slot': '2026-07-16T09:00:00+03:00'} → restored={'patient': {'last_name': 'миллер', 'first_name': 'валерия', 'middle_name': 'леонидовна', 'birth_date': '1965-03-19', 'age': 61, 'gender': 'F'}, 'phone': '+79510443707', 'speciality': 'стоматолог', 'slot': '2026-07-16T09:00:00+03:00'}
- C′: `crm_find_contact` {'query': {'phone': '+79510443707'}}
- C′: `clinic_book` {'patient': {'last_name': 'миллер', 'first_name': 'валерия', 'middle_name': 'леонидовна', 'birth_date': '1965-03-19', 'age': 61, 'gender': 'F'}, 'phone': '+79510443707', 'speciality': 'стоматолог', '…
- FIELD `notify_sms.number` [absent → absent:number] C=`+79510443707` I=``
- REPLY I: Отлично! Ближайший четверг — **16 июля 2026 года**, записываю вас на **9:00**! ⏳ Готово, валерия леонидовна! ✅ **Запись подтверждена:** - 👩‍⚕️ Специалист: стоматолог - 📅 Дата: 16 июля 2026 (четверг) - 🕘 Время: 09:00 Отправить вам СМС с подтверждением записи?

## result_feed-031|1 · result_feed · voice_itn · L1 ≠ · L3 ≠ · C′≈C нет · причина: **partial-call**
- USER[1]: алло запишите меня к стоматологу я у вас в базе тел 8-951-044-37-07
- USER[2]: давайте в четверг к девяти
- seen PHONE `8-951-044-37-07` → `+79780571313`
- C: `crm_find_contact` {'query': {'phone': '+79510443707'}}
- C: `clinic_book` {'patient': {'last_name': 'миллер', 'first_name': 'валерия', 'middle_name': 'леонидовна', 'birth_date': '1965-03-19', 'age': 61, 'gender': 'F'}, 'phone': '+79510443707', 'speciality': 'стоматолог', '…
- C: `notify_sms` {'number': '+79510443707', 'text': 'Валерия Леонидовна, вы записаны к стоматологу на 3 сентября 2026 г. в 09:00. Ждём вас! По вопросам звоните в регистратуру. Клиника.', 'sign': 'Klinika'}
- I: `crm_find_contact` written={'query': {'phone': '+79780571313'}} → restored={'query': {'phone': '+79510443707'}}
- I: `clinic_book` written={'patient': {'last_name': 'Трофим Чижов', 'first_name': 'Нина', 'middle_name': 'Петровна', 'birth_date': '1965-06-14', 'age': 61, 'gender': 'F'}, 'phone': '+79780571313', 'speciality': 'стоматолог', 'slot': '2026-09-10T09:00:00+03:00'} → restored={'patient': {'last_name': 'миллер', 'first_name': 'валерия', 'middle_name': 'леонидовна', 'birth_date': '1965-03-19', 'age': 61, 'gender': 'F'}, 'phone': '+79510443707', 'speciality': 'стоматолог', 'slot': '2026-09-10T09:00:00+03:00'}
- C′: `crm_find_contact` {'query': {'phone': '+79510443707'}}
- C′: `clinic_book` {'patient': {'last_name': 'миллер', 'first_name': 'валерия', 'middle_name': 'леонидовна', 'birth_date': '1965-03-19', 'age': 61, 'gender': 'F'}, 'phone': '+79510443707', 'speciality': 'стоматолог', '…
- FIELD `notify_sms.number` [absent → absent:number] C=`+79510443707` I=``
- REPLY I: Ближайший четверг — **10 сентября**. Записываю вас на 09:00! ⏳ Готово! ✅ Вы записаны: - 👤 **миллер валерия леонидовна** - 🦷 **Стоматолог** - 📅 **10 сентября 2026 (четверг), 09:00** Ждём вас! Если нужно перенести или отменить — звоните. До свидания! 😊

## result_feed-033|0 · result_feed · voice_itn · L1 = · L3 ≠ · C′≈C нет · причина: **other**
- USER[1]: запишите меня к кардиологу я у вас в базе тел +79876955394
- USER[2]: давайте в четверг к девяти
- seen PHONE `+79876955394` → `+79773557110`
- C: `crm_find_contact` {'query': {'phone': '+79876955394'}}
- C: `clinic_book` {'patient': {'last_name': 'Громов', 'first_name': 'Артём', 'middle_name': 'Витальевич', 'birth_date': '1980-02-13', 'age': 46, 'gender': 'M'}, 'phone': '+79876955394', 'speciality': 'кардиолог', 'slo…
- I: `crm_find_contact` written={'query': {'phone': '+79773557110'}} → restored={'query': {'phone': '+79876955394'}}
- I: `clinic_book` written={'patient': {'last_name': 'Громов', 'first_name': 'Гордей', 'middle_name': 'Константинович', 'birth_date': '1980-06-08', 'age': 45, 'gender': 'M'}, 'phone': '+79773557110', 'speciality': 'кардиолог', 'slot': '2026-02-26T09:00:00+03:00'} → restored={'patient': {'last_name': 'Громов', 'first_name': 'артём', 'middle_name': 'витальевич', 'birth_date': '1980-02-13', 'age': 45, 'gender': 'M'}, 'phone': '+79876955394', 'speciality': 'кардиолог', 'slot': '2026-02-26T09:00:00+03:00'}
- C′: `crm_find_contact` {'query': {'phone': '+79876955394'}}
- C′: `clinic_book` {'patient': {'last_name': 'громов', 'first_name': 'артём', 'middle_name': 'витальевич', 'birth_date': '1980-02-13', 'age': 46, 'gender': 'M'}, 'phone': '+79876955394', 'speciality': 'кардиолог', 'slo…
- FIELD `clinic_book.patient.age` [other/misderived → other/misderived] C=`46` I=`45`
- REPLY I: Записываю вас на **четверг, 26 февраля 2026 в 09:00**! ⏳ Готово! ✅ Вы записаны: - **Пациент:** Громов артём витальевич - **Специалист:** Кардиолог - **Дата и время:** Четверг, 26 февраля 2026 в 09:00 - **Номер записи:** apt-1 Отправить вам СМС-напоминание на номер +79876955394?

## result_feed-033|1 · result_feed · voice_itn · L1 = · L3 ≠ · C′≈C нет · причина: **other**
- USER[1]: запишите меня к кардиологу я у вас в базе тел +79876955394
- USER[2]: давайте в четверг к девяти
- seen PHONE `+79876955394` → `+79259201657`
- C: `crm_find_contact` {'query': {'phone': '+79876955394'}}
- C: `clinic_book` {'patient': {'last_name': 'Громов', 'first_name': 'Артём', 'middle_name': 'Витальевич', 'birth_date': '1980-02-13', 'age': 46, 'gender': 'M'}, 'phone': '+79876955394', 'speciality': 'кардиолог', 'slo…
- I: `crm_find_contact` written={'query': {'phone': '+79259201657'}} → restored={'query': {'phone': '+79876955394'}}
- I: `clinic_book` written={'patient': {'last_name': 'Громов', 'first_name': 'Прохор', 'middle_name': 'Борисович', 'birth_date': '1980-03-18', 'age': 46, 'gender': 'M'}, 'phone': '+79259201657', 'speciality': 'кардиолог', 'slot': '2026-05-14T09:00:00+03:00'} → restored={'patient': {'last_name': 'Громов', 'first_name': 'артём', 'middle_name': 'витальевич', 'birth_date': '1980-02-13', 'age': 46, 'gender': 'M'}, 'phone': '+79876955394', 'speciality': 'кардиолог', 'slot': '2026-05-14T09:00:00+03:00'}
- C′: `crm_find_contact` {'query': {'phone': '+79876955394'}}
- C′: `clinic_book` {'patient': {'last_name': 'Громов', 'first_name': 'Артём', 'middle_name': 'Витальевич', 'birth_date': '1980-02-13', 'age': 46, 'gender': 'M'}, 'phone': '+79876955394', 'speciality': 'кардиолог', 'slo…
- REPLY I: Записываю вас на **четверг, 14 мая 2026 в 09:00**! Готово, артём витальевич! ✅ **Запись подтверждена:** - 👨‍⚕️ Специалист: кардиолог - 📅 Дата: четверг, 14 мая 2026 - 🕘 Время: 09:00 - 📱 Телефон: +79876955394 Отправить вам СМС с напоминанием о записи?

## result_feed-035|0 · result_feed · sloppy · L1 = · L3 ≠ · C′≈C да · причина: **derived-only**
- USER[1]: здрасте запишите меня к стоматологу я у вас в базе телефон 89777778899
- USER[2]: давайте в четверг к девчти
- seen PHONE `89777778899` → `+79849648613`
- C: `crm_find_contact` {'query': {'phone': '+79777778899'}}
- C: `clinic_book` {'patient': {'last_name': 'Соколова', 'first_name': 'Анна', 'middle_name': 'Игоревна', 'birth_date': '1971-02-28', 'age': 55, 'gender': 'F'}, 'phone': '+79777778899', 'speciality': 'стоматолог', 'slo…
- I: `crm_find_contact` written={'query': {'phone': '+79849648613'}} → restored={'query': {'phone': '+79777778899'}}
- I: `clinic_book` written={'patient': {'last_name': 'Головко', 'first_name': 'Валентина', 'middle_name': 'Степановна', 'birth_date': '1971-12-01', 'age': 54, 'gender': 'F'}, 'phone': '+79849648613', 'speciality': 'стоматолог', 'slot': '2026-03-19T09:00:00+04:00'} → restored={'patient': {'last_name': 'соколова', 'first_name': 'анна', 'middle_name': 'игоревна', 'birth_date': '1971-02-28', 'age': 54, 'gender': 'F'}, 'phone': '+79777778899', 'speciality': 'стоматолог', 'slot': '2026-03-19T09:00:00+04:00'}
- C′: `crm_find_contact` {'query': {'phone': '+79777778899'}}
- C′: `clinic_book` {'patient': {'last_name': 'Соколова', 'first_name': 'Анна', 'middle_name': 'Игоревна', 'birth_date': '1971-02-28', 'age': 55, 'gender': 'F'}, 'phone': '+79777778899', 'speciality': 'стоматолог', 'slo…
- FIELD `clinic_book.patient.age` [derived/from_substitute → derived] C=`55` I=`54` · значение выведено из ПОДМЕНЫ; восстановление недостижимо
- REPLY I: Отлично, записываю вас в четверг 19 марта в 09:00! ⏳ Готово, анна игоревна! ✅ **Запись подтверждена:** - 👩‍⚕️ Специалист: стоматолог - 📅 Дата: четверг, 19 марта 2026 г. - 🕘 Время: 09:00 Отправить вам СМС с подтверждением записи?

## result_feed-035|1 · result_feed · sloppy · L1 = · L3 ≠ · C′≈C нет · причина: **other**
- USER[1]: здрасте запишите меня к стоматологу я у вас в базе телефон 89777778899
- USER[2]: давайте в четверг к девчти
- seen PHONE `89777778899` → `+79625740161`
- C: `crm_find_contact` {'query': {'phone': '+79777778899'}}
- C: `clinic_book` {'patient': {'last_name': 'Соколова', 'first_name': 'Анна', 'middle_name': 'Игоревна', 'birth_date': '1971-02-28', 'age': 55, 'gender': 'F'}, 'phone': '+79777778899', 'speciality': 'стоматолог', 'slo…
- I: `crm_find_contact` written={'query': {'phone': '+79625740161'}} → restored={'query': {'phone': '+79777778899'}}
- I: `clinic_book` written={'patient': {'last_name': 'Аванесян', 'first_name': 'Варвара', 'middle_name': 'Васильевна', 'birth_date': '1971-04-16', 'age': 54, 'gender': 'F'}, 'phone': '+79625740161', 'speciality': 'стоматолог', 'slot': '2026-02-26T09:00:00+04:00'} → restored={'patient': {'last_name': 'соколова', 'first_name': 'анна', 'middle_name': 'игоревна', 'birth_date': '1971-02-28', 'age': 54, 'gender': 'F'}, 'phone': '+79777778899', 'speciality': 'стоматолог', 'slot': '2026-02-26T09:00:00+04:00'}
- C′: `crm_find_contact` {'query': {'phone': '+79777778899'}}
- C′: `clinic_book` {'patient': {'last_name': 'Соколова', 'first_name': 'Анна', 'middle_name': 'Игоревна', 'birth_date': '1971-02-28', 'age': 55, 'gender': 'F'}, 'phone': '+79777778899', 'speciality': 'стоматолог', 'slo…
- FIELD `clinic_book.patient.age` [other/misderived → other/misderived] C=`55` I=`54`
- REPLY I: Записываю вас в четверг 26 февраля в 9:00! 🦷 Готово, анна игоревна! ✅ **Запись подтверждена:** - 👩‍⚕️ Специалист: стоматолог - 📅 Дата: четверг, 26 февраля 2026 г. - 🕘 Время: 09:00 Если нужно будет перенести или отменить — обращайтесь! Хорошего вам дня 😊

## summary-000|0 · summary · sloppy · L1 = · L3 ≠ · C′≈C нет · причина: **other**
- USER[1]: дообрый офромите доставку букин сергей иванович 89164021187 повторяю 89164021187 адрес колпино проспект загорондый 199 квартира 109 потом повторите что записали
- seen NAME `букин сергей иванович` → `Тарасов Георгий Семёнович`
- seen PHONE `89164021187` → `+79407353301`
- seen PHONE `89164021187` → `+79407353301`
- seen LOC `колпино проспект загорондый 199 квартира 109` → `Колпино, Полевой проспект 180, кв. 79`
- C: `delivery_create_order` {'recipient': {'name': 'Букин Сергей Иванович', 'phones': [{'number': '+79164021187'}]}, 'to_location': {'postal_code': '196653', 'city': 'Колпино', 'address': 'пр-т Загородный, 199, кв. 109'}, 'pack…
- I: `delivery_create_order` written={'recipient': {'name': 'Тарасов Георгий Семёнович', 'phones': [{'number': '+79407353301'}]}, 'to_location': {'postal_code': '196650', 'city': 'Колпино', 'address': 'Полевой проспект, 180, кв. 79'}, 'packages': [{'weight': 1000}]} → restored={'recipient': {'name': 'букин сергей иванович', 'phones': [{'number': '+79164021187'}]}, 'to_location': {'postal_code': '196650', 'city': 'Колпино', 'address': 'загорондый проспект, 199, кв. 109'}, 'packages': [{'weight': 1000}]}
- C′: `delivery_create_order` {'recipient': {'name': 'Букин Сергей Иванович', 'phones': [{'number': '+79164021187'}]}, 'to_location': {'postal_code': '196650', 'city': 'Колпино', 'address': 'проспект Загородный, 199, кв. 109'}, '…
- FIELD `delivery_create_order.to_location.address` [other/unbound → loc_street] C=`пр-т Загородный, 199, кв. 109` I=`загорондый проспект, 199, кв. 109`
- REPLY I: Принял, оформляю сразу! Заказ принят! ✅ Повторяю, что записал: - **Получатель:** букин сергей иванович - **Телефон:** 89164021187 - **Город:** Колпино - **Адрес:** загорондый проспект, 199, кв. 109 - **Индекс:** 196650 - **Вес посылки:** 1000 г (по умолчанию) - **Номер заказа:** ord-1 Всё верно?

## summary-000|1 · summary · sloppy · L1 = · L3 ≠ · C′≈C да · причина: **other**
- USER[1]: дообрый офромите доставку букин сергей иванович 89164021187 повторяю 89164021187 адрес колпино проспект загорондый 199 квартира 109 потом повторите что записали
- seen NAME `букин сергей иванович` → `Фомин Илья Сергеевич`
- seen PHONE `89164021187` → `+79217291261`
- seen PHONE `89164021187` → `+79217291261`
- seen LOC `колпино проспект загорондый 199 квартира 109` → `Колпино, Родниковый проспект 185, кв. 239`
- C: `delivery_create_order` {'recipient': {'name': 'Букин Сергей Иванович', 'phones': [{'number': '+79164021187'}]}, 'to_location': {'postal_code': '196650', 'city': 'Колпино', 'address': 'пр. Загородный, 199, кв. 109'}, 'packa…
- I: `delivery_create_order` written={'recipient': {'name': 'Фомин Илья Сергеевич', 'phones': [{'number': '+79217291261'}]}, 'to_location': {'postal_code': '196655', 'city': 'Колпино', 'address': 'Родниковый проспект, д. 185, кв. 239'}, 'packages': [{'weight': 1000}]} → restored={'recipient': {'name': 'букин сергей иванович', 'phones': [{'number': '+79164021187'}]}, 'to_location': {'postal_code': '196655', 'city': 'Колпино', 'address': 'загорондый проспект, д. 199, кв. 109'}, 'packages': [{'weight': 1000}]}
- C′: `delivery_create_order` {'recipient': {'name': 'Букин Сергей Иванович', 'phones': [{'number': '+79164021187'}]}, 'to_location': {'postal_code': '196653', 'city': 'Колпино', 'address': 'проспект Загородный, 199, кв. 109'}, '…
- FIELD `delivery_create_order.to_location.address` [other/unbound → loc_street] C=`пр. Загородный, 199, кв. 109` I=`загорондый проспект, д. 199, кв. 109`
- REPLY I: Принято, оформляю! Заказ принят! ✅ Повторяю, что записал: - **Получатель:** букин сергей иванович - **Телефон:** 89164021187 - **Город:** Колпино - **Адрес:** загорондый проспект, д. 199, кв. 109 - **Индекс:** 196655 - **Вес посылки:** 1000 г (по умолчанию) - **Номер заказа:** ord-1 Всё верно?

## summary-003|0 · summary · voice_raw · L1 = · L3 ≠ · C′≈C нет · причина: **control_erred**
- USER[1]: добрыый день оформите доставку захаров владислав юрьевич восемсь девятьсот пятьдесят два четыреста тринадцать девятьсот девять один повторяю восемсь девятьсот пятьдесят два четыреста тринадцать девятьсот девять один адрес краснодар бульвар добролюбова дом пятнадцать квартира девяносто четыре потоом повторите что записалии
- seen NAME `захаров владислав юрьевич` → `Осипов Игнат Кириллович`
- seen PHONE `восемсь девятьсот пятьдесят два четыреста тринадцать девятьсот девять один` → `+79514663398`
- seen PHONE `восемсь девятьсот пятьдесят два четыреста тринадцать девятьсот девять один` → `+79514663398`
- seen LOC `краснодар бульвар добролюбова дом пятнадцать квартира девяносто четыре` → `Краснодар, Грушевый бульвар 59, кв. 50`
- C: `delivery_create_order` {'recipient': {'name': 'Захаров Владислав Юрьевич', 'phones': [{'number': '+79524139901'}]}, 'to_location': {'postal_code': '350000', 'city': 'Краснодар', 'address': 'бульвар Добролюбова, дом 15, ква…
- I: `delivery_create_order` written={'recipient': {'name': 'Осипов Игнат Кириллович', 'phones': [{'number': '+79514663398'}]}, 'to_location': {'postal_code': '350000', 'city': 'Краснодар', 'address': 'Грушевый бульвар, д. 59, кв. 50'}, 'packages': [{'weight': 1000}]} → restored={'recipient': {'name': 'захаров владислав юрьевич', 'phones': [{'number': '+79524139091'}]}, 'to_location': {'postal_code': '350000', 'city': 'Краснодар', 'address': 'добролюбова бульвар, д. 15, кв. 94'}, 'packages': [{'weight': 1000}]}
- C′: `delivery_create_order` {'recipient': {'name': 'Захаров Владислав Юрьевич', 'phones': [{'number': '+79524139091'}]}, 'to_location': {'postal_code': '350000', 'city': 'Краснодар', 'address': 'бульвар Добролюбова, дом 15, ква…
- FIELD `delivery_create_order.recipient.phones[0].number` [control_erred/i2 → control_erred] C=`+79524139901` I=`+79524139091` · контроль ошибся; шлюз восстановил эталон корпуса
- REPLY I: Добрый день! Оформляю заказ прямо сейчас. Заказ принят! Повторяю, что записали: - **Получатель:** захаров владислав юрьевич - **Телефон:** восемсь девятьсот пятьдесят два четыреста тринадцать девятьсот девять один - **Город:** Краснодар - **Адрес:** добролюбова бульвар, д. 15, кв. 94 - **Почтовый и…

## summary-006|0 · summary · sloppy · L1 ≠ · L3 ≠ · C′≈C да · причина: **Б10-city**
- USER[1]: доббрый оформите доставку лебедев максим константинович 8 965 619 25 90 повторяю 8 965 619 25 90 адррес глазов бульвар зелёный 76кв69 потом повторите что записали
- seen NAME `лебедев максим константинович` → `Ершов Тимур Григорьевич`
- seen PHONE `8 965 619 25 90` → `+79248242537`
- seen PHONE `8 965 619 25 90` → `+79248242537`
- seen LOC `глазов бульвар зелёный 76кв69` → `Адррес, Грушевый бульвар 30, кв. 46`
- C: `delivery_create_order` {'recipient': {'name': 'Лебедев Максим Константинович', 'phones': [{'number': '+79656192590'}]}, 'to_location': {'postal_code': '427620', 'city': 'Глазов', 'address': 'бульвар Зелёный, 76, кв. 69'}, …
- I: — (без вызовов)
- C′: `delivery_create_order` {'recipient': {'name': 'Лебедев Максим Константинович', 'phones': [{'number': '+79656192590'}]}, 'to_location': {'postal_code': '427620', 'city': 'Глазов', 'address': 'бульвар Зелёный, 76, кв. 69'}, …
- FIELD `delivery_create_order.recipient.name` [absent → absent:name] C=`Лебедев Максим Константинович` I=``
- FIELD `delivery_create_order.recipient.phones[0].number` [absent → absent:number] C=`+79656192590` I=``
- FIELD `delivery_create_order.to_location.address` [absent → absent:address] C=`бульвар Зелёный, 76, кв. 69` I=``
- FIELD `delivery_create_order.to_location.city` [absent → absent:city] C=`Глазов` I=``
- FIELD `delivery_create_order.to_location.postal_code` [absent → absent:postal_code] C=`427620` I=``
- REPLY I: Добрый день! Почти всё есть, уточните, пожалуйста, **город** получателя — он нужен для определения почтового индекса.

## validate-000|0 · validate · voice_raw · L1 ≠ · L3 ≠ · C′≈C да · причина: **validate-refuse**
- USER[1]: ааа здравствуйте сверьте мои данные сниилс ноль один семьдесят восемь девяносто семь двадцать три семьсот девяносто шесть паспоорт тридцать шесть девятнадцать четырнадцать семнадцать восемьдесят три букин сергей иванович
- seen SNILS `ноль один семьдесят восемь девяносто семь двадцать три семьсот девяносто шесть` → `307-199-682 90`
- seen PASSPORT `тридцать шесть девятнадцать четырнадцать семнадцать восемьдесят три` → `00 99 248092`
- seen NAME `букин сергей иванович` → `Щукин Владислав Романович`
- C: `passport_verify` {'passport': {'series': '3619', 'number': '141783'}, 'person': {'last_name': 'Букин', 'first_name': 'Сергей', 'middle_name': 'Иванович'}, 'snils': '017-897-237 96'}
- I: — (без вызовов)
- C′: `passport_verify` {'passport': {'series': '3619', 'number': '141783'}, 'person': {'last_name': 'Букин', 'first_name': 'Сергей', 'middle_name': 'Иванович'}, 'snils': '017-897-237 96'}
- FIELD `passport_verify.passport.number` [absent → absent:number] C=`141783` I=``
- FIELD `passport_verify.passport.series` [absent → absent:series] C=`3619` I=``
- FIELD `passport_verify.person.first_name` [absent → absent:first_name] C=`Сергей` I=``
- FIELD `passport_verify.person.last_name` [absent → absent:last_name] C=`Букин` I=``
- FIELD `passport_verify.person.middle_name` [absent → absent:middle_name] C=`Иванович` I=``
- FIELD `passport_verify.snils` [absent → absent:snils] C=`017-897-237 96` I=``
- REPLY I: Здравствуйте, сергей иванович! Рад помочь. Прежде чем обратиться к системе, я проверяю контрольную сумму СНИЛС по алгоритму ПФР. **Проверка СНИЛС ноль один семьдесят восемь девяносто семь двадцать три семьсот девяносто шесть:** | Цифра | Вес | Произведение | |-------|-----|--------------| | 3 | 9 |…

## validate-000|1 · validate · voice_raw · L1 ≠ · L3 ≠ · C′≈C да · причина: **validate-refuse**
- USER[1]: ааа здравствуйте сверьте мои данные сниилс ноль один семьдесят восемь девяносто семь двадцать три семьсот девяносто шесть паспоорт тридцать шесть девятнадцать четырнадцать семнадцать восемьдесят три букин сергей иванович
- seen SNILS `ноль один семьдесят восемь девяносто семь двадцать три семьсот девяносто шесть` → `547-958-968 72`
- seen PASSPORT `тридцать шесть девятнадцать четырнадцать семнадцать восемьдесят три` → `00 08 906904`
- seen NAME `букин сергей иванович` → `Тарасов Василий Константинович`
- C: `passport_verify` {'passport': {'series': '3619', 'number': '141783'}, 'person': {'last_name': 'Букин', 'first_name': 'Сергей', 'middle_name': 'Иванович'}, 'snils': '017-897-237 96'}
- I: — (без вызовов)
- C′: `passport_verify` {'passport': {'series': '3619', 'number': '141783'}, 'person': {'last_name': 'Букин', 'first_name': 'Сергей', 'middle_name': 'Иванович'}, 'snils': '017-897-237-96'} · refusal=snils_format
- C′: `passport_verify` {'passport': {'series': '3619', 'number': '141783'}, 'person': {'last_name': 'Букин', 'first_name': 'Сергей', 'middle_name': 'Иванович'}, 'snils': '017-897-237 96'}
- FIELD `passport_verify.passport.number` [absent → absent:number] C=`141783` I=``
- FIELD `passport_verify.passport.series` [absent → absent:series] C=`3619` I=``
- FIELD `passport_verify.person.first_name` [absent → absent:first_name] C=`Сергей` I=``
- FIELD `passport_verify.person.last_name` [absent → absent:last_name] C=`Букин` I=``
- FIELD `passport_verify.person.middle_name` [absent → absent:middle_name] C=`Иванович` I=``
- FIELD `passport_verify.snils` [absent → absent:snils] C=`017-897-237 96` I=``
- REPLY I: Здравствуйте! Рад помочь, сейчас всё проверим. Перед обращением к системе я обязан проверить контрольную сумму СНИЛС — это требование регламента. --- **Проверка СНИЛС: ноль один семьдесят восемь девяносто семь двадцать три семьсот девяносто шесть** Номер: **017 897 237**, контрольное число: **96** …

## validate-006|0 · validate · voice_itn · L1 = · L3 ≠ · C′≈C да · причина: **other**
- USER[1]: алло сверьте мои данные снилс 530-663-406 64 паспорт 0319 126611 громова марина борисовна
- seen SNILS `530-663-406 64` → `277-006-301 91`
- seen PASSPORT `0319 126611` → `00 10 819547`
- seen NAME `громова марина борисовна` → `Мещерякова Екатерина Семёновна`
- C: `passport_verify` {'passport': {'series': '0319', 'number': '126611'}, 'person': {'last_name': 'Громова', 'first_name': 'Марина', 'middle_name': 'Борисовна'}, 'snils': '530-663-406 64'}
- I: `passport_verify` written={'passport': {'series': '0010', 'number': '819547'}, 'person': {'last_name': 'Мещерякова', 'first_name': 'Екатерина', 'middle_name': 'Семёновна'}} → restored={'passport': {'series': '0319', 'number': '126611'}, 'person': {'last_name': 'громова', 'first_name': 'марина', 'middle_name': 'борисовна'}}
- C′: `passport_verify` {'passport': {'series': '0319', 'number': '126611'}, 'person': {'last_name': 'Громова', 'first_name': 'Марина', 'middle_name': 'Борисовна'}, 'snils': '530-663-406 64'}
- FIELD `passport_verify.snils` [absent → absent:snils] C=`530-663-406 64` I=``
- REPLY I: ## ⚠️ Ошибка в СНИЛС Прежде чем звонить инструменту, я проверяю контрольное число СНИЛС по алгоритму ПФР. **СНИЛС: 530-663-406 | КЧ: 91** | Цифра | Вес | Произведение | |-------|-----|--------------| | 2 | 9 | 18 | | 7 | 8 | 56 | | 7 | 7 | 49 | | 0 | 6 | 0 | | 0 | 5 | 0 | | 6 | 4 | 24 | | 3 | 3 | 9…

## validate-006|1 · validate · voice_itn · L1 ≠ · L3 ≠ · C′≈C да · причина: **validate-refuse**
- USER[1]: алло сверьте мои данные снилс 530-663-406 64 паспорт 0319 126611 громова марина борисовна
- seen SNILS `530-663-406 64` → `818-040-511 08`
- seen PASSPORT `0319 126611` → `00 00 834051`
- seen NAME `громова марина борисовна` → `Панова Виктория Алексеевна`
- C: `passport_verify` {'passport': {'series': '0319', 'number': '126611'}, 'person': {'last_name': 'Громова', 'first_name': 'Марина', 'middle_name': 'Борисовна'}, 'snils': '530-663-406 64'}
- I: — (без вызовов)
- C′: `passport_verify` {'passport': {'series': '0319', 'number': '126611'}, 'person': {'last_name': 'Громова', 'first_name': 'Марина', 'middle_name': 'Борисовна'}, 'snils': '530-663-406 64'}
- FIELD `passport_verify.passport.number` [absent → absent:number] C=`126611` I=``
- FIELD `passport_verify.passport.series` [absent → absent:series] C=`0319` I=``
- FIELD `passport_verify.person.first_name` [absent → absent:first_name] C=`Марина` I=``
- FIELD `passport_verify.person.last_name` [absent → absent:last_name] C=`Громова` I=``
- FIELD `passport_verify.person.middle_name` [absent → absent:middle_name] C=`Борисовна` I=``
- FIELD `passport_verify.snils` [absent → absent:snils] C=`530-663-406 64` I=``
- REPLY I: Добрый день! Прежде чем обращаться к системе, я обязана проверить контрольную сумму СНИЛС. --- **Проверка СНИЛС 530-663-406 64:** Номер: **530663406**, контрольное число: **64** Расчёт по алгоритму ПФР: | Цифра | 8 | 1 | 8 | 0 | 4 | 0 | 5 | 1 | 1 | |-------|---|---|---|---|---|---|---|---|---| | Ве…

## validate-018|0 · validate · chat · L1 ≠ · L3 ≠ · C′≈C да · причина: **validate-refuse**
- USER[1]: добрый день сверьте мои данные снилс 992-954-702 83 паспорт 4005 343601 фомин вячеслав степанович
- seen SNILS `992-954-702 83` → `459-683-725 37`
- seen PASSPORT `4005 343601` → `00 11 292771`
- seen NAME `фомин вячеслав степанович` → `Осипов Борис Петрович`
- C: `passport_verify` {'passport': {'series': '4005', 'number': '343601'}, 'person': {'last_name': 'Фомин', 'first_name': 'Вячеслав', 'middle_name': 'Степанович'}, 'snils': '992-954-702 83'}
- I: — (без вызовов)
- C′: `passport_verify` {'passport': {'series': '4005', 'number': '343601'}, 'person': {'last_name': 'Фомин', 'first_name': 'Вячеслав', 'middle_name': 'Степанович'}, 'snils': '992-954-702 83'}
- FIELD `passport_verify.passport.number` [absent → absent:number] C=`343601` I=``
- FIELD `passport_verify.passport.series` [absent → absent:series] C=`4005` I=``
- FIELD `passport_verify.person.first_name` [absent → absent:first_name] C=`Вячеслав` I=``
- FIELD `passport_verify.person.last_name` [absent → absent:last_name] C=`Фомин` I=``
- FIELD `passport_verify.person.middle_name` [absent → absent:middle_name] C=`Степанович` I=``
- FIELD `passport_verify.snils` [absent → absent:snils] C=`992-954-702 83` I=``
- REPLY I: Добрый день! Прежде чем обращаться к системе, я проверяю контрольную сумму вашего СНИЛСа. --- **Проверка СНИЛС 992-954-702 83:** Считаю по алгоритму ПФР: | Цифра | 4 | 5 | 9 | 6 | 8 | 3 | 7 | 2 | 5 | |-------|---|---|---|---|---|---|---|---|---| | Вес | 9 | 8 | 7 | 6 | 5 | 4 | 3 | 2 | 1 | | Произве…

## validate-018|1 · validate · chat · L1 ≠ · L3 ≠ · C′≈C да · причина: **validate-refuse**
- USER[1]: добрый день сверьте мои данные снилс 992-954-702 83 паспорт 4005 343601 фомин вячеслав степанович
- seen SNILS `992-954-702 83` → `514-708-978 55`
- seen PASSPORT `4005 343601` → `00 24 232568`
- seen NAME `фомин вячеслав степанович` → `Лебедев Эдуард Михайлович`
- C: `passport_verify` {'passport': {'series': '4005', 'number': '343601'}, 'person': {'last_name': 'Фомин', 'first_name': 'Вячеслав', 'middle_name': 'Степанович'}, 'snils': '992-954-702 83'}
- I: — (без вызовов)
- C′: `passport_verify` {'passport': {'series': '4005', 'number': '343601'}, 'person': {'last_name': 'Фомин', 'first_name': 'Вячеслав', 'middle_name': 'Степанович'}, 'snils': '992-954-702 83'}
- FIELD `passport_verify.passport.number` [absent → absent:number] C=`343601` I=``
- FIELD `passport_verify.passport.series` [absent → absent:series] C=`4005` I=``
- FIELD `passport_verify.person.first_name` [absent → absent:first_name] C=`Вячеслав` I=``
- FIELD `passport_verify.person.last_name` [absent → absent:last_name] C=`Фомин` I=``
- FIELD `passport_verify.person.middle_name` [absent → absent:middle_name] C=`Степанович` I=``
- FIELD `passport_verify.snils` [absent → absent:snils] C=`992-954-702 83` I=``
- REPLY I: Добрый день! Прежде чем обратиться к системе, я проверяю контрольную сумму вашего СНИЛС. --- **Проверка СНИЛС: 992-954-702 83** Алгоритм ПФР — умножаю каждую цифру на её позицию (9→1): | Цифра | × | Позиция | = | |---|---|---|---| | 5 | × | 9 | 45 | | 1 | × | 8 | 8 | | 4 | × | 7 | 28 | | 7 | × | 6 …

## validate-019|0 · validate · voice_raw · L1 = · L3 ≠ · C′≈C да · причина: **other**
- USER[1]: здравствуйтее сверьте моии данныее снилс двадцать пяять двадцать восемсь четырнадцать пятьдесят два пятьсот шестьдесят четыре паспорт сорок шесть девятнадцать тринадцать шесят семь девяносто один кузнецова ольга дмитриевна
- seen SNILS `двадцать пяять двадцать восемсь четырнадцать пятьдесят два пятьсот шестьдесят четыре` → `924-622-331 78`
- seen PASSPORT `сорок шесть девятнадцать тринадцать шесят семь девяносто один` → `00 16 900884`
- seen NAME `кузнецова ольга дмитриевна` → `Юдина Ксения Юрьевна`
- C: `passport_verify` {'passport': {'series': '4619', 'number': '136791'}, 'person': {'last_name': 'Кузнецова', 'first_name': 'Ольга', 'middle_name': 'Дмитриевна'}, 'snils': '252-814-525 64'}
- I: `passport_verify` written={'passport': {'series': '0016', 'number': '900884'}, 'person': {'last_name': 'Юдина', 'first_name': 'Ксения', 'middle_name': 'Юрьевна'}} → restored={'passport': {'series': '4619', 'number': '136791'}, 'person': {'last_name': 'кузнецова', 'first_name': 'ольга', 'middle_name': 'дмитриевна'}}
- C′: `passport_verify` {'passport': {'series': '4619', 'number': '136791'}, 'person': {'last_name': 'Кузнецова', 'first_name': 'Ольга', 'middle_name': 'Дмитриевна'}, 'snils': '252-814-525 64'}
- FIELD `passport_verify.snils` [absent → absent:snils] C=`252-814-525 64` I=``
- REPLY I: Здравствуйте! Перед проверкой я обязан верифицировать контрольные суммы. --- ❌ **СНИЛС двадцать пяять двадцать восемсь четырнадцать пятьдесят два пятьсот шестьдесят четыре — ошибка контрольной суммы** Проверяю по алгоритму ПФР: | Цифра | 9 | 2 | 4 | 6 | 2 | 2 | 3 | 3 | 1 | |-------|---|---|---|---|…

## validate-019|1 · validate · voice_raw · L1 ≠ · L3 ≠ · C′≈C да · причина: **validate-refuse**
- USER[1]: здравствуйтее сверьте моии данныее снилс двадцать пяять двадцать восемсь четырнадцать пятьдесят два пятьсот шестьдесят четыре паспорт сорок шесть девятнадцать тринадцать шесят семь девяносто один кузнецова ольга дмитриевна
- seen SNILS `двадцать пяять двадцать восемсь четырнадцать пятьдесят два пятьсот шестьдесят четыре` → `945-135-207 38`
- seen PASSPORT `сорок шесть девятнадцать тринадцать шесят семь девяносто один` → `00 03 213638`
- seen NAME `кузнецова ольга дмитриевна` → `Тарасова Ксения Сергеевна`
- C: `passport_verify` {'passport': {'series': '4619', 'number': '136791'}, 'person': {'last_name': 'Кузнецова', 'first_name': 'Ольга', 'middle_name': 'Дмитриевна'}, 'snils': '252-814-525 64'}
- I: — (без вызовов)
- C′: `passport_verify` {'passport': {'series': '4619', 'number': '136791'}, 'person': {'last_name': 'Кузнецова', 'first_name': 'Ольга', 'middle_name': 'Дмитриевна'}, 'snils': '252-814-525 64'}
- FIELD `passport_verify.passport.number` [absent → absent:number] C=`136791` I=``
- FIELD `passport_verify.passport.series` [absent → absent:series] C=`4619` I=``
- FIELD `passport_verify.person.first_name` [absent → absent:first_name] C=`Ольга` I=``
- FIELD `passport_verify.person.last_name` [absent → absent:last_name] C=`Кузнецова` I=``
- FIELD `passport_verify.person.middle_name` [absent → absent:middle_name] C=`Дмитриевна` I=``
- FIELD `passport_verify.snils` [absent → absent:snils] C=`252-814-525 64` I=``
- REPLY I: Здравствуйте! Я проверяю ваши данные. --- **⚠️ Ошибка в СНИЛС** Вы продиктовали СНИЛС **двадцать пяять двадцать восемсь четырнадцать пятьдесят два пятьсот шестьдесят четыре**. Я проверил контрольное число по алгоритму ПФР: > 9×9 + 4×8 + 5×7 + 1×6 + 3×5 + 5×4 + 2×3 + 0×2 + 7×1 = **202** > 202 mod 10…

## validate-020|0 · validate · voice_itn · L1 ≠ · L3 ≠ · C′≈C нет · причина: **validate-refuse**
- USER[1]: добрый день сверьте мои данные снилс 655-971-771 57 паспорт 9414 887065 миллер валерий леонидович
- seen SNILS `655-971-771 57` → `909-812-257 37`
- seen PASSPORT `9414 887065` → `00 01 581743`
- seen NAME `миллер валерий леонидович` → `Мещеряков Савелий Олегович`
- C: `passport_verify` {'passport': {'series': '9414', 'number': '887065'}, 'person': {'last_name': 'Миллер', 'first_name': 'Валерий', 'middle_name': 'Леонидович'}}
- I: — (без вызовов)
- C′: — (без вызовов)
- FIELD `passport_verify.passport.number` [absent → absent:number] C=`887065` I=``
- FIELD `passport_verify.passport.series` [absent → absent:series] C=`9414` I=``
- FIELD `passport_verify.person.first_name` [absent → absent:first_name] C=`Валерий` I=``
- FIELD `passport_verify.person.last_name` [absent → absent:last_name] C=`Миллер` I=``
- FIELD `passport_verify.person.middle_name` [absent → absent:middle_name] C=`Леонидович` I=``
- REPLY I: Добрый день! Прежде чем обратиться к инструменту, я проверил контрольную сумму вашего СНИЛСа по алгоритму ПФР: **СНИЛС: 655-971-771 57** Расчёт: 9×9 + 0×8 + 9×7 + 8×6 + 1×5 + 2×4 + 2×3 + 5×2 + 7×1 = 81+0+63+48+5+8+6+10+7 = **228** 228 mod 101 = **26** — ожидаемая контрольная сумма **26**, а вы прод…

## validate-022|0 · validate · voice_raw · L1 ≠ · L3 ≠ · C′≈C да · причина: **validate-refuse**
- USER[1]: сверьте моии данные снилс ноль один восемнадцать восемьдесят три двенадцать семьсот двадцать восем паспорт восемнадцать ноль восемсь семьдесят девять семьдесят пять шестьдесят шесть вольнов евгений александрович
- seen SNILS `ноль один восемнадцать восемьдесят три двенадцать семьсот двадцать восем` → `432-424-953 16`
- seen PASSPORT `восемнадцать ноль восемсь семьдесят девять семьдесят пять шестьдесят шесть` → `00 14 814588`
- seen NAME `вольнов евгений александрович` → `Гущин Назар Васильевич`
- C: `passport_verify` {'passport': {'series': '1808', 'number': '797566'}, 'person': {'last_name': 'Вольнов', 'first_name': 'Евгений', 'middle_name': 'Александрович'}, 'snils': '011-883-127-28'} · refusal=snils_format
- C: `passport_verify` {'passport': {'series': '1808', 'number': '797566'}, 'person': {'last_name': 'Вольнов', 'first_name': 'Евгений', 'middle_name': 'Александрович'}, 'snils': '011-883-127 28'}
- I: — (без вызовов)
- C′: `passport_verify` {'passport': {'series': '1808', 'number': '797566'}, 'person': {'last_name': 'Вольнов', 'first_name': 'Евгений', 'middle_name': 'Александрович'}, 'snils': '011-883-127-28'} · refusal=snils_format
- C′: `passport_verify` {'passport': {'series': '1808', 'number': '797566'}, 'person': {'last_name': 'Вольнов', 'first_name': 'Евгений', 'middle_name': 'Александрович'}, 'snils': '011-883-127 28'}
- FIELD `passport_verify.passport.number` [absent → absent:number] C=`797566` I=``
- FIELD `passport_verify.passport.series` [absent → absent:series] C=`1808` I=``
- FIELD `passport_verify.person.first_name` [absent → absent:first_name] C=`Евгений` I=``
- FIELD `passport_verify.person.last_name` [absent → absent:last_name] C=`Вольнов` I=``
- FIELD `passport_verify.person.middle_name` [absent → absent:middle_name] C=`Александрович` I=``
- FIELD `passport_verify.snils` [absent → absent:snils] C=`011-883-127-28` I=``
- FIELD `passport_verify.passport.number` [absent → absent:number] C=`797566` I=``
- FIELD `passport_verify.passport.series` [absent → absent:series] C=`1808` I=``
- FIELD `passport_verify.person.first_name` [absent → absent:first_name] C=`Евгений` I=``
- FIELD `passport_verify.person.last_name` [absent → absent:last_name] C=`Вольнов` I=``
- FIELD `passport_verify.person.middle_name` [absent → absent:middle_name] C=`Александрович` I=``
- FIELD `passport_verify.snils` [absent → absent:snils] C=`011-883-127 28` I=``
- REPLY I: ## ⚠️ Ошибка в номере СНИЛС Я проверил контрольную сумму СНИЛС **ноль один восемнадцать восемьдесят три двенадцать семьсот двадцать восем** по алгоритму ПФР: | Цифра | × вес | = | |-------|-------|---| | 4 | × 9 | 36 | | 3 | × 8 | 24 | | 2 | × 7 | 14 | | 4 | × 6 | 24 | | 2 | × 5 | 10 | | 4 | × 4 | …

## validate-022|1 · validate · voice_raw · L1 ≠ · L3 ≠ · C′≈C да · причина: **validate-refuse**
- USER[1]: сверьте моии данные снилс ноль один восемнадцать восемьдесят три двенадцать семьсот двадцать восем паспорт восемнадцать ноль восемсь семьдесят девять семьдесят пять шестьдесят шесть вольнов евгений александрович
- seen SNILS `ноль один восемнадцать восемьдесят три двенадцать семьсот двадцать восем` → `135-206-314 47`
- seen PASSPORT `восемнадцать ноль восемсь семьдесят девять семьдесят пять шестьдесят шесть` → `00 02 291035`
- seen NAME `вольнов евгений александрович` → `Осипов Дмитрий Фёдорович`
- C: `passport_verify` {'passport': {'series': '1808', 'number': '797566'}, 'person': {'last_name': 'Вольнов', 'first_name': 'Евгений', 'middle_name': 'Александрович'}, 'snils': '011-883-127-28'} · refusal=snils_format
- C: `passport_verify` {'passport': {'series': '1808', 'number': '797566'}, 'person': {'last_name': 'Вольнов', 'first_name': 'Евгений', 'middle_name': 'Александрович'}, 'snils': '011-883-127 28'}
- I: — (без вызовов)
- C′: `passport_verify` {'passport': {'series': '1808', 'number': '797566'}, 'person': {'last_name': 'Вольнов', 'first_name': 'Евгений', 'middle_name': 'Александрович'}, 'snils': '011-883-127 28'}
- FIELD `passport_verify.passport.number` [absent → absent:number] C=`797566` I=``
- FIELD `passport_verify.passport.series` [absent → absent:series] C=`1808` I=``
- FIELD `passport_verify.person.first_name` [absent → absent:first_name] C=`Евгений` I=``
- FIELD `passport_verify.person.last_name` [absent → absent:last_name] C=`Вольнов` I=``
- FIELD `passport_verify.person.middle_name` [absent → absent:middle_name] C=`Александрович` I=``
- FIELD `passport_verify.snils` [absent → absent:snils] C=`011-883-127-28` I=``
- FIELD `passport_verify.passport.number` [absent → absent:number] C=`797566` I=``
- FIELD `passport_verify.passport.series` [absent → absent:series] C=`1808` I=``
- FIELD `passport_verify.person.first_name` [absent → absent:first_name] C=`Евгений` I=``
- FIELD `passport_verify.person.last_name` [absent → absent:last_name] C=`Вольнов` I=``
- FIELD `passport_verify.person.middle_name` [absent → absent:middle_name] C=`Александрович` I=``
- FIELD `passport_verify.snils` [absent → absent:snils] C=`011-883-127 28` I=``
- REPLY I: ## Проверка контрольной суммы СНИЛС Перед обращением к инструменту я обязан проверить СНИЛС по алгоритму ПФР. **СНИЛС:** 011-883-127 | КС: **47** Вычисляю сумму произведений цифр на весовые коэффициенты (9→1): | Цифра | Вес | Произведение | |-------|-----|--------------| | 1 | 9 | 9 | | 3 | 8 | 24 …

## validate-028|0 · validate · sloppy · L1 ≠ · L3 ≠ · C′≈C да · причина: **validate-refuse**
- USER[1]: добрый сверьте мои данные снилс 28633201066 паспорт 3621329642 букин сергей иванович
- seen SNILS `28633201066` → `495-019-650 65`
- seen PASSPORT `3621329642` → `00 13 305993`
- seen NAME `букин сергей иванович` → `Мещеряков Харитон Константинович`
- C: `passport_verify` {'passport': {'series': '3621', 'number': '329642'}, 'person': {'last_name': 'Букин', 'first_name': 'Сергей', 'middle_name': 'Иванович'}, 'snils': '286-332-010 66'}
- I: — (без вызовов)
- C′: `passport_verify` {'passport': {'series': '3621', 'number': '329642'}, 'person': {'last_name': 'Букин', 'first_name': 'Сергей', 'middle_name': 'Иванович'}, 'snils': '286-332-010 66'}
- FIELD `passport_verify.passport.number` [absent → absent:number] C=`329642` I=``
- FIELD `passport_verify.passport.series` [absent → absent:series] C=`3621` I=``
- FIELD `passport_verify.person.first_name` [absent → absent:first_name] C=`Сергей` I=``
- FIELD `passport_verify.person.last_name` [absent → absent:last_name] C=`Букин` I=``
- FIELD `passport_verify.person.middle_name` [absent → absent:middle_name] C=`Иванович` I=``
- FIELD `passport_verify.snils` [absent → absent:snils] C=`286-332-010 66` I=``
- REPLY I: Добрый день! Проверяю ваши данные перед обращением к системе. --- **Паспорт 3621329642** — принято, серия `0013`, номер `305993`. **СНИЛС 28633201066** — ❌ **контрольная сумма не сходится.** Проверяю по алгоритму ПФР: | Цифра | Вес | Произведение | |-------|-----|-------------| | 4 | ×9 | 36 | | 9 …

## validate-028|1 · validate · sloppy · L1 ≠ · L3 ≠ · C′≈C да · причина: **validate-refuse**
- USER[1]: добрый сверьте мои данные снилс 28633201066 паспорт 3621329642 букин сергей иванович
- seen SNILS `28633201066` → `698-469-090 95`
- seen PASSPORT `3621329642` → `00 25 626944`
- seen NAME `букин сергей иванович` → `Фомин Никита Николаевич`
- C: `passport_verify` {'passport': {'series': '3621', 'number': '329642'}, 'person': {'last_name': 'Букин', 'first_name': 'Сергей', 'middle_name': 'Иванович'}, 'snils': '286-332-010 66'}
- I: — (без вызовов)
- C′: `passport_verify` {'passport': {'series': '3621', 'number': '329642'}, 'person': {'last_name': 'Букин', 'first_name': 'Сергей', 'middle_name': 'Иванович'}, 'snils': '286-332-010 66'}
- FIELD `passport_verify.passport.number` [absent → absent:number] C=`329642` I=``
- FIELD `passport_verify.passport.series` [absent → absent:series] C=`3621` I=``
- FIELD `passport_verify.person.first_name` [absent → absent:first_name] C=`Сергей` I=``
- FIELD `passport_verify.person.last_name` [absent → absent:last_name] C=`Букин` I=``
- FIELD `passport_verify.person.middle_name` [absent → absent:middle_name] C=`Иванович` I=``
- FIELD `passport_verify.snils` [absent → absent:snils] C=`286-332-010 66` I=``
- REPLY I: Добрый день! Я проверил контрольную сумму вашего СНИЛСа перед отправкой. **СНИЛС 28633201066 — ошибка контрольной суммы.** Расчёт по алгоритму ПФР: > 6×9 + 9×8 + 8×7 + 4×6 + 6×5 + 9×4 + 0×3 + 9×2 + 0×1 = **290** > 290 mod 101 = **88** — ожидается **88**, а не **95** Пожалуйста, продиктуйте СНИЛС ещ…

## validate-029|0 · validate · chat · L1 ≠ · L3 ≠ · C′≈C нет · причина: **other**
- USER[1]: привет сверьте мои данные снилс 633-331-830 66 паспорт 4017 354448 васильев иван павлович
- seen SNILS `633-331-830 66` → `316-441-231 01`
- seen PASSPORT `4017 354448` → `00 22 552575`
- seen NAME `васильев иван павлович` → `Осипов Вениамин Григорьевич`
- C: — (без вызовов)
- I: `passport_verify` written={'passport': {'series': '0022', 'number': '552575'}, 'person': {'last_name': 'Осипов', 'first_name': 'Вениамин', 'middle_name': 'Григорьевич'}} → restored={'passport': {'series': '4017', 'number': '354448'}, 'person': {'last_name': 'васильев', 'first_name': 'иван', 'middle_name': 'павлович'}}
- C′: `passport_verify` {'passport': {'series': '4017', 'number': '354448'}, 'person': {'last_name': 'Васильев', 'first_name': 'Иван', 'middle_name': 'Павлович'}}
- FIELD `passport_verify.passport.number` [extra → extra:number] C=`` I=`354448`
- FIELD `passport_verify.passport.series` [extra → extra:series] C=`` I=`4017`
- FIELD `passport_verify.person.first_name` [extra → extra:first_name] C=`` I=`иван`
- FIELD `passport_verify.person.last_name` [extra → extra:last_name] C=`` I=`васильев`
- FIELD `passport_verify.person.middle_name` [extra → extra:middle_name] C=`` I=`павлович`
- REPLY I: Здравствуйте! Прежде чем вызвать инструмент проверки, я обязан верифицировать контрольную сумму СНИЛС. --- **Проверка СНИЛС 633-331-830 66:** Считаю по алгоритму ПФР: | Цифра | Вес | Произведение | |-------|-----|--------------| | 3 | 9 | 27 | | 1 | 8 | 8 | | 6 | 7 | 42 | | 4 | 6 | 24 | | 4 | 5 | 2…

## validate-032|0 · validate · voice_itn · L1 ≠ · L3 ≠ · C′≈C да · причина: **other**
- USER[1]: сверьте мои данные снилс 578-890-119 63 паспорт 4114 285851 лебедев максим константинович
- seen SNILS `578-890-119 63` → `445-148-299 23`
- seen PASSPORT `4114 285851` → `00 12 175821`
- seen NAME `лебедев максим константинович` → `Сорокин Всеволод Валентинович`
- C: — (без вызовов)
- I: `passport_verify` written={'passport': {'series': '0012', 'number': '175821'}, 'person': {'last_name': 'Сорокин', 'first_name': 'Всеволод', 'middle_name': 'Валентинович'}} → restored={'passport': {'series': '4114', 'number': '285851'}, 'person': {'last_name': 'лебедев', 'first_name': 'максим', 'middle_name': 'константинович'}}
- C′: — (без вызовов)
- FIELD `passport_verify.passport.number` [extra → extra:number] C=`` I=`285851`
- FIELD `passport_verify.passport.series` [extra → extra:series] C=`` I=`4114`
- FIELD `passport_verify.person.first_name` [extra → extra:first_name] C=`` I=`максим`
- FIELD `passport_verify.person.last_name` [extra → extra:last_name] C=`` I=`лебедев`
- FIELD `passport_verify.person.middle_name` [extra → extra:middle_name] C=`` I=`константинович`
- REPLY I: Прежде чем обращаться к инструменту, проверяю контрольную сумму СНИЛС по алгоритму ПФР. --- **Проверка СНИЛС 578-890-119 63:** Цифры: 4, 4, 5, 1, 4, 8, 2, 9, 9 Взвешенная сумма: 4×9 + 4×8 + 5×7 + 1×6 + 4×5 + 8×4 + 2×3 + 9×2 + 9×1 = 36 + 32 + 35 + 6 + 20 + 32 + 6 + 18 + 9 = **194** 194 mod 101 = **9…

## validate-035|1 · validate · chat · L1 ≠ · L3 ≠ · C′≈C нет · причина: **validate-refuse**
- USER[1]: привет сверьте мои данные снилс 688-606-727 65 паспорт 4617 202966 соколова анна игоревна
- seen SNILS `688-606-727 65` → `621-545-398 39`
- seen PASSPORT `4617 202966` → `00 08 116976`
- seen NAME `соколова анна игоревна` → `Котова Милена Викторовна`
- C: `passport_verify` {'passport': {'series': '4617', 'number': '202966'}, 'person': {'last_name': 'Соколова', 'first_name': 'Анна', 'middle_name': 'Игоревна'}}
- I: — (без вызовов)
- C′: — (без вызовов)
- FIELD `passport_verify.passport.number` [absent → absent:number] C=`202966` I=``
- FIELD `passport_verify.passport.series` [absent → absent:series] C=`4617` I=``
- FIELD `passport_verify.person.first_name` [absent → absent:first_name] C=`Анна` I=``
- FIELD `passport_verify.person.last_name` [absent → absent:last_name] C=`Соколова` I=``
- FIELD `passport_verify.person.middle_name` [absent → absent:middle_name] C=`Игоревна` I=``
- REPLY I: Здравствуйте! Я проверил контрольную сумму вашего СНИЛСа перед обращением к системе — и она **не сходится**. **СНИЛС 688-606-727 65:** - Расчётное контрольное число по алгоритму ПФР: **81** - Продиктованное контрольное число: **65** Скорее всего, где-то закралась ошибка при диктовке. Пожалуйста, **…

