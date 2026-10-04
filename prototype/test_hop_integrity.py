"""Cross-boundary invariants, not exceptions for benchmark case IDs.

Each check drives actual masking/restoration with an isolated scoped vault.
Controls cover ordinary business data, real PII and multiple distinct owners.
The counterexamples intentionally combine individually valid operations.
"""
import json
import sys
from collections.abc import Callable

from testkit import load_dev_bundle
load_dev_bundle()

from pseudex.detect_all import Detector
from pseudex.morph_places import split_roles
from pseudex.redact import mask_text, unmask_arguments, unmask_text
from pseudex.vault import Vault

DETECTOR = Detector()


def fresh(label: str) -> Vault:
    return Vault(':memory:', 'hop-integrity-' + label).for_conversation('dialogue')


def mask(text: str, vault: Vault) -> str:
    return mask_text(text, vault, DETECTOR.detect(text))


def restore_args(value: object, vault: Vault) -> object:
    return json.loads(unmask_arguments(json.dumps(value, ensure_ascii=False), vault))


def address_record(vault: Vault, city: str = 'Курск', house: str = '9') -> dict:
    raw = {'address': {'city': city, 'street': 'Некрасова', 'house': house, 'flat': '69'}}
    return json.loads(mask(json.dumps(raw, ensure_ascii=False), vault))['address']


def address_identity(text: str) -> tuple:
    roles = split_roles(text)
    return tuple(roles.get(key, '').casefold() for key in ('street_name', 'house', 'flat'))


def test_short_numeric_components_do_not_rewrite_business_values() -> None:
    vault = fresh('numeric')
    fake = address_record(vault)
    for number in (fake['house'], fake['flat']):
        for text in (f'ord-{number}', f'c-{number}', f'Срок {number} дня',
                     f'{number}. Проверить заказ', f'{number}:00'):
            assert unmask_text(text, vault) == text, (text, unmask_text(text, vault))
        source = {'order_id': f'ord-{number}', 'entity_id': f'c-{number}',
                  'count': number, 'comment': f'Количество: {number}'}
        assert restore_args(source, vault) == source, (source, restore_args(source, vault))
    # The same numeric leaves still restore when the object supplies address roles.
    restored = restore_args({'address': fake}, vault)['address']
    assert restored['house'] == '9' and restored['flat'] == '69', restored


def test_complete_phone_outranks_unrelated_house_literal() -> None:
    # Use genuine minting, not manual insertion of synthetic provenance rows.
    # Two possible phone prefixes provide frequent witnesses for the small house pool.
    for attempt in range(64):
        vault = fresh('phone-' + str(attempt))
        raw = {'phone': '+79164021187', 'address': {
            'city': 'Курск', 'street': 'Некрасова', 'house': '6', 'flat': '74'}}
        fake = json.loads(mask(json.dumps(raw, ensure_ascii=False), vault))
        if fake['address']['house'] != '7':
            continue
        digits = ''.join(c for c in fake['phone'] if c.isdigit())
        text = f'+{digits[0]} {digits[1:4]} {digits[4:7]}-{digits[7:9]}-{digits[9:]}'
        restored = unmask_text(text, vault)
        assert ''.join(c for c in restored if c.isdigit()) == '79164021187', (text, restored)
        return
    raise AssertionError('did not exercise house/phone-prefix overlap in64 draws')


def test_city_omission_keeps_core_and_apartment() -> None:
    for street in ('Строительный', 'Мончегорский'):
        vault = fresh('projection-' + street)
        a = vault.tokenize(f'Курск, переулок {street}, дом 6, квартира 74', 'LOC')
        b = vault.tokenize(f'переулок {street}, 6, кв. 74', 'LOC')
        assert address_identity(a) == address_identity(b), (a, b)
        # Another apartment remains distinct and restores its own content.
        c = vault.tokenize(f'переулок {street}, 6, кв. 75', 'LOC')
        ar, cr = split_roles(a), split_roles(c)
        assert ar['house'] == cr['house'] and ar['street_name'] == cr['street_name'], (a, c)
        assert ar['flat'] != cr['flat'], (a, c)


def test_city_family_cannot_steal_full_address_owner() -> None:
    vault = fresh('family')
    fake = address_record(vault, city='Чернь', house='108')
    text = f"Чернь, {fake['street']} ул., {fake['house']}, кв. {fake['flat']}"
    before = restore_args({'address': text}, vault)['address']
    mask('Адрес: Чернь', vault)
    after = restore_args({'address': text}, vault)['address']
    assert address_identity(before) == address_identity(after), (before, after)
    assert split_roles(after).get('house') == '108' and split_roles(after).get('flat') == '69', after


def test_ambiguous_cityless_address_never_picks_a_city_owner() -> None:
    vault = fresh('two-cities')
    first = vault.tokenize('Курск, улица Пушкина, 6, кв. 74', 'LOC')
    second = vault.tokenize('Москва, улица Пушкина, 6, кв. 74', 'LOC')
    assert first != second, (first, second)
    short = vault.tokenize('улица Пушкина, 6, кв. 74', 'LOC')
    assert address_identity(short) not in (address_identity(first), address_identity(second)), (first, second, short)


def test_projected_parts_restore_without_city_or_other_flat() -> None:
    vault = fresh('projected-parts')
    full = vault.tokenize('Курск, улица Пушкина, 6, кв. 74', 'LOC')
    other = vault.tokenize('Курск, улица Пушкина, 6, кв. 75', 'LOC')
    brief = vault.tokenize('улица Пушкина, 6, кв. 74', 'LOC')
    changed = vault.tokenize('улица Пушкина, 6, кв. 75', 'LOC')
    assert address_identity(full) == address_identity(brief), (full, brief)
    assert address_identity(other) == address_identity(changed), (other, changed)
    assert brief != changed and 'Курск' not in brief, (brief, changed)
    for fake, flat in ((brief, '74'), (changed, '75')):
        real = restore_args({'address': fake}, vault)['address']
        parts = split_roles(real)
        assert parts.get('house') == '6' and parts.get('flat') == flat, real
        assert 'city' not in parts, real


def test_missing_city_projection_is_conversation_scoped() -> None:
    base = Vault(':memory:', 'projection-isolation')
    first = base.for_conversation('first-city')
    second = base.for_conversation('second-city')
    a = first.tokenize('Курск, улица Пушкина, 6, кв. 74', 'LOC')
    short_a = first.tokenize('улица Пушкина, 6, кв. 74', 'LOC')
    b = second.tokenize('Москва, улица Пушкина, 6, кв. 74', 'LOC')
    short_b = second.tokenize('улица Пушкина, 6, кв. 74', 'LOC')
    assert address_identity(a) == address_identity(short_a), (a, short_a)
    assert address_identity(b) == address_identity(short_b), (b, short_b)
    assert short_a != short_b, (short_a, short_b)
    assert first.tokenize('улица Пушкина, 6, кв. 74', 'LOC') == short_a


def test_explicit_street_types_remain_distinct() -> None:
    vault = fresh('types')
    first = vault.tokenize('Курск, улица Пушкина, 6, кв. 74', 'LOC')
    second = vault.tokenize('Курск, переулок Пушкина, 6, кв. 74', 'LOC')
    assert first != second, (first, second)


def test_operational_json_dates_ignore_adjacent_person_fields() -> None:
    for key, value in (('date', '2026-09-10'), ('delivery_date', '2026-09-10'),
                       ('slot', '2026-09-08T09:00:00+04:00'), ('at', '2026-09-02T12:00:00+03:00')):
        text = json.dumps({key: value, 'recipient': {'name': 'Иванов Пётр', 'phone': '+79164021187'}}, ensure_ascii=False)
        spans = DETECTOR.detect(text)
        assert not any(s.entity_type in ('DATE', 'DOB') and value.startswith(text[s.start:s.end]) for s in spans), (key, spans)
        assert any(s.entity_type == 'NAME' for s in spans) and any(s.entity_type == 'PHONE' for s in spans), spans
    for value in (
        {'birth_date': '1985-02-26', 'slot': '2026-09-10', 'name': 'Иванов Пётр'},
        {'slot': '2026-09-10', 'birth_date': '1985-02-26', 'name': 'Иванов Пётр'},
        {'dob': ['1985-02-26'], 'slots': ['2026-09-10'], 'name': 'Иванов Пётр'},
        {'patient': {'name': 'Иванов Пётр', 'birth_date': '1985-02-26'},
         'booking': {'at': '2026-09-10'}},
        {'note': 'Дата рождения: 1985-02-26', 'message': 'Приём 2026-09-10'},
    ):
        text = json.dumps(value, ensure_ascii=False)
        dates = [text[s.start:s.end] for s in DETECTOR.detect(text) if s.entity_type in ('DATE', 'DOB')]
        assert '1985-02-26' in dates and not any('2026-09-10' in d for d in dates), (text, dates)


def test_birth_evidence_in_json_keeps_supported_typo_and_pronoun_forms() -> None:
    for value, date in (('рдилась 22.04.1994', '22.04.1994'),
                        ('др 13.01.1991', '13.01.1991'),
                        ('он 19 12 1992', '19 12 1992')):
        text = json.dumps({'note': value, 'slot': '2026-09-10'}, ensure_ascii=False)
        dates = [text[s.start:s.end] for s in DETECTOR.detect(text) if s.entity_type == 'DOB']
        assert date in dates and '2026-09-10' not in dates, (text, dates)


def test_short_address_cues_still_restore_role_projections() -> None:
    vault = fresh('abbreviations')
    fake = address_record(vault)
    for house, flat in (('дом', 'квартира'), ('д.', 'кв.'), ('д', 'кв')):
        text = f"{house} {fake['house']}, {flat} {fake['flat']}"
        expected = f'{house} 9, {flat} 69'
        assert unmask_text(text, vault) == expected, (text, unmask_text(text, vault))
        assert restore_args({'comment': text}, vault)['comment'] == expected


def test_repeated_shortening_keeps_scoped_address_owner() -> None:
    vault = fresh('repeated-shortening')
    full = vault.tokenize('Курск, улица Пушкина, 6, кв. 74', 'LOC')
    brief = vault.tokenize('улица Пушкина, 6, кв. 74', 'LOC')
    shortest = vault.tokenize('Пушкина 6 кв 74', 'LOC')
    assert address_identity(full) == address_identity(brief) == address_identity(shortest)


def test_name_fragment_does_not_claim_adjacent_time_or_quantity() -> None:
    from unittest.mock import patch
    vault = fresh('name-versus-place-window')
    with patch('pseudex.vault._fake_name', return_value='Лев Юдин'):
        assert vault.tokenize('Никита Гущин', 'NAME') == 'Лев Юдин'
    for tail in ('на 15:00', 'на 21:30', 'на 15 минут'):
        text = 'Записать Льва Юдина ' + tail
        restored = unmask_text(text, vault)
        assert restored.endswith(' ' + tail), (text, restored)
        assert 'Юдин' not in restored and 'Гущин' in restored, (text, restored)
    assert unmask_text('Позвоните Льву Юдину', vault) == 'Позвоните Никите Гущину'


def test_coherent_latin_name_outranks_colliding_single_token() -> None:
    from unittest.mock import patch
    vault = fresh('legacy-script-collision')
    # Simulate existing rows produced by the old script-blind mint guard.
    # A full, uniquely aligned NAME remains stronger than an unrelated exact
    # single-word token that happens to occur inside that NAME.
    with patch('pseudex.vault._fake_name', return_value='Артур'):
        assert vault.tokenize('ISO', 'NAME') == 'ARTUR'
    with patch.object(vault, '_shares_a_stem_in_conversation', return_value=False), \
            patch('pseudex.vault._fake_name', return_value='Ершов Артур'):
        assert vault.tokenize('Букин Сергей', 'NAME') == 'Ершов Артур'
    expected = 'BUKIN SERGEI'
    assert unmask_text('ERSHOV ARTUR', vault) == expected
    assert restore_args({'cardholder': 'ERSHOV ARTUR'}, vault)['cardholder'] == expected
    # Without the full-name evidence, the complete standalone token still has
    # its original meaning; never globally change ARTUR to Sergei.
    assert unmask_text('ARTUR', vault) == 'ISO'


def test_full_transliterated_name_keeps_all_roles_and_script() -> None:
    from unittest.mock import patch
    vault = fresh('three-part-latin')
    with patch('pseudex.vault._fake_name', return_value='Котова Карина Валерьевна'):
        assert vault.tokenize('соколова анна игоревна', 'NAME') == 'Котова Карина Валерьевна'
    for value in ('Соколова', 'Анна', 'Игоревна'):
        vault.tokenize(value, 'NAME')
    written = 'Kotova Karina Valerevna'
    expected = 'Sokolova Anna Igorevna'
    assert restore_args({'name_latin': written}, vault)['name_latin'] == expected
    assert unmask_text(written, vault) == expected


def test_initials_index_does_not_rewrite_ordinary_words() -> None:
    from unittest.mock import patch
    vault = fresh('initials-versus-prose')
    with patch('pseudex.vault._fake_name', return_value='Фролов Платон Олегович'):
        assert vault.tokenize('Иванов Сергей Петрович', 'NAME') == 'Фролов Платон Олегович'
    for text in ('по', 'по заявке', 'Свяжемся по телефону'):
        assert restore_args({'text': text}, vault)['text'] == text
        assert unmask_text(text, vault) == text
    assert restore_args({'text': 'Фролов ПО'}, vault)['text'] == 'Иванов СП'
    assert unmask_text('П.О.', vault) == 'С.П.'
    assert unmask_text('Платон Олегович', vault) == 'Сергей Петрович'


def test_adjacent_markdown_fields_do_not_get_consumed() -> None:
    for key, value, next_label, following in (
        ('Телефон', '+79164021187', 'Статус', 'подтвержден'),
        ('Email', 'ivan@example.com', 'Status', 'active'),
    ):
        text = f'**{key}**: {value} **{next_label}**: {following}'
        vault = fresh('adjacent-' + key)
        masked = mask(text, vault)
        assert f' **{next_label}**: {following}' in masked, (text, masked)
        assert value not in masked


def test_json_value_context_preserves_source_offsets() -> None:
    from pseudex.json_fields import string_leaves
    text = '{"a": ["quote \\" and date", {"dob": "1985-02-26"}], "note": "test"}'
    leaves = string_leaves(text)
    assert [leaf.path for leaf in leaves] == [('a', 0), ('a', 1, 'dob'), ('note',)], leaves
    assert [text[leaf.start:leaf.end] for leaf in leaves] == ['quote \\" and date', '1985-02-26', 'test']
    assert string_leaves('{"incomplete": [') == ()
    assert string_leaves('Дата рождения 1985-02-26') == ()


def test_markdown_name_caption_is_not_part_of_identity() -> None:
    vault = fresh('markdown')
    name = json.loads(mask('{"name":"Мкртчян Ашот"}', vault))['name']
    for label in ('Получатель', 'Имя'):
        for pattern in ('{label}: {name}', '**{label}:** {name}', '**{label}**: {name}'):
            text = pattern.format(label=label, name=name)
            assert mask(text, vault) == text, (text, mask(text, vault))
    # Markup isn't a pass-through exemption for an actual unseen person.
    real = '**Получатель:** Иванов Пётр'
    assert mask(real, vault) != real


def test_dictated_house_litera_unifies_with_digit_form() -> None:
    from pseudex.morph_places import address_key
    assert address_key('г Брянск, ул. Пушкина, д. 145а, кв. 44') == \
           address_key('брянск улица пушкина дом сто сорок пять а квартира сорок четыре'), \
           ('dictated litera must fold to the same identity as the digit form',
            address_key('г Брянск, ул. Пушкина, д. 145а, кв. 44'),
            address_key('брянск улица пушкина дом сто сорок пять а квартира сорок четыре'))


def test_city_plus_bare_street_restores() -> None:
    import pseudex.vault as vault_mod
    vault_mod.seed_token_rng(42)
    v = fresh('city-bare-street')
    seed = '{"address": {"city": "красноярск", "street": "энгельса", "house": "54"}}'
    mask_text(seed, v, DETECTOR.detect(seed))
    token = v._conn.execute("SELECT token FROM tokens WHERE entity_type='LOC'", ()).fetchone()[0]
    roles = split_roles(token)
    city, street = roles['city'], roles.get('street_name') or roles.get('street')
    assert unmask_text(f'{city}, {street}', v) == f'{city}, Энгельса', (token, city, street)
    assert unmask_text(f'{city.lower()}, {street.lower()}', v) == f'{city.lower()}, энгельса'
    vault_mod.seed_token_rng(None)


def test_token_mint_is_deterministic_when_seeded() -> None:
    import pseudex.vault as vault_mod
    def mint_one() -> str:
        v = fresh('seed-det')
        return mask_text('Букин Сергей', v, DETECTOR.detect('Букин Сергей')) \
            + '|' + mask_text('г. Тверь, ул. Речная, д. 5', v, DETECTOR.detect('г. Тверь, ул. Речная, д. 5'))
    vault_mod.seed_token_rng(42)
    a = mint_one()
    vault_mod.seed_token_rng(42)
    b = mint_one()
    assert a == b, ('seeded mint is not reproducible', a, b)
    vault_mod.seed_token_rng(None)


def test_spaced_house_litera_is_detected_not_leaked() -> None:
    d = Detector()
    full = d.detect('псков, проезд маросейка, 152 б, кв. 105')
    assert [(s.entity_type, 'псков, проезд маросейка, 152 б, кв. 105'[s.start:s.end]) for s in full] \
        == [('LOC', 'псков, проезд маросейка, 152 б, кв. 105')], full
    # the same litera followed by a surname or a quantity must still be trimmed
    assert [(s.entity_type, 'советская 66 а широкову ларису'[s.start:s.end]) for s in d.detect('советская 66 а широкову ларису')] \
        == [('LOC', 'советская 66'), ('NAME', 'широкову ларису')]
    assert d.detect('счёт 152 б рублей') == []


def test_masked_card_shape_restores_head_and_tail() -> None:
    vault = fresh('card-masked-shape')
    real = '5469205917105692'
    fake = vault.tokenize(real, 'CARD')
    digits = ''.join(c for c in fake if c.isdigit())
    first4, last4 = digits[:4], digits[-4:]
    written = f'{first4} **** **** {last4}'
    restored = unmask_text(written, vault)
    expected = f'{real[:4]} **** **** {real[-4:]}'
    assert restored == expected, (written, restored)
    assert restore_args({'note': written}, vault)['note'] == expected


def test_quantity_tail_is_not_a_second_address() -> None:
    for unit in ('кг', 'килограмма', 'килограммов', 'тонны', 'граммов', 'миллиграммов', 'миллилитров'):
        text = 'везитее наа красноярск бульвар маяковского дом четырнадцать квартира сто девяносто пять коробкаа пять ' + unit
        spans = DETECTOR.detect(text)
        assert not any('коробкаа' in text[s.start:s.end] for s in spans), (unit, spans)
        masked = mask_text(text, fresh('weight-' + unit), spans)
        assert 'коробкаа пять ' + unit in masked, (text, masked)
        assert any(s.entity_type == 'LOC' for s in spans), spans


TESTS: tuple[Callable[[], None], ...] = (
    test_short_numeric_components_do_not_rewrite_business_values,
    test_complete_phone_outranks_unrelated_house_literal,
    test_city_omission_keeps_core_and_apartment,
    test_city_family_cannot_steal_full_address_owner,
    test_ambiguous_cityless_address_never_picks_a_city_owner,
    test_explicit_street_types_remain_distinct,
    test_projected_parts_restore_without_city_or_other_flat,
    test_missing_city_projection_is_conversation_scoped,
    test_operational_json_dates_ignore_adjacent_person_fields,
    test_json_value_context_preserves_source_offsets,
    test_markdown_name_caption_is_not_part_of_identity,
    test_quantity_tail_is_not_a_second_address,
    test_birth_evidence_in_json_keeps_supported_typo_and_pronoun_forms,
    test_short_address_cues_still_restore_role_projections,
    test_repeated_shortening_keeps_scoped_address_owner,
    test_adjacent_markdown_fields_do_not_get_consumed,
    test_name_fragment_does_not_claim_adjacent_time_or_quantity,
    test_coherent_latin_name_outranks_colliding_single_token,
    test_full_transliterated_name_keeps_all_roles_and_script,
    test_initials_index_does_not_rewrite_ordinary_words,
    test_masked_card_shape_restores_head_and_tail,
    test_spaced_house_litera_is_detected_not_leaked,
    test_token_mint_is_deterministic_when_seeded,
    test_city_plus_bare_street_restores,
    test_dictated_house_litera_unifies_with_digit_form,
)

if __name__ == '__main__':
    failures = []
    selected = sys.argv[1:]
    for test in TESTS:
        if selected and test.__name__ not in selected:
            continue
        try:
            test()
            print('PASS', test.__name__, flush=True)
        except Exception as exc:
            failures.append(test.__name__)
            print('FAIL', test.__name__, type(exc).__name__, str(exc), flush=True)
    print('Failures:', len(failures), failures)
    raise SystemExit(bool(failures))
