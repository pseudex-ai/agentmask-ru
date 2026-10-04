# long_order-058 | source A | repeat 0

Synthetic benchmark evidence. Verbatim serialized fields; no inferred verdicts.

## Case specification

{
  "base": {
    "id": "long_order-058",
    "kind": "long_order",
    "register": "chat",
    "provenance": {
      "kind": "template",
      "corpus": "authored",
      "key": "",
      "shape": "",
      "selection": "authored",
      "weight": 1.0,
      "licence": "authored"
    },
    "cluster": "PHONE:9889990949",
    "conversation_id": "conv-long-order-58",
    "now": "2026-09-02",
    "messages": [
      {
        "role": "system",
        "content": "Ты оператор службы доставки. Оформляй заказы и вызовы курьера инструментами, переспрашивай только то, чего не хватает для вызова. Вес посылки, если не назван, — 1000 г; почтовый индекс подбери сам по городу получателя. Сегодня 2026-09-02.",
        "source": null,
        "name": ""
      },
      {
        "role": "user",
        "content": "добрый день это васильев иван хочу отправить посылку телефон 8 988 999 09 49 кстати к 10 часам",
        "source": null,
        "name": ""
      },
      {
        "role": "user",
        "content": "везите на краснодар проспект кирова 53 квартира 79 коробка 3 килограмма",
        "source": null,
        "name": ""
      },
      {
        "role": "user",
        "content": "почём выйдет",
        "source": null,
        "name": ""
      },
      {
        "role": "user",
        "content": "хорошо оформляйте",
        "source": null,
        "name": ""
      },
      {
        "role": "user",
        "content": "получит не я а мамедова лейла её телефон 89228231652",
        "source": null,
        "name": ""
      },
      {
        "role": "user",
        "content": "а знаете отмените заказ",
        "source": null,
        "name": ""
      },
      {
        "role": "user",
        "content": "и смс пришлите мне на мой номер",
        "source": null,
        "name": ""
      }
    ],
    "tools": [
      "crm_find_contact",
      "delivery_quote",
      "delivery_create_order",
      "pickup_points_near",
      "order_status",
      "order_reschedule",
      "order_cancel",
      "courier_book",
      "notify_sms",
      "callback_schedule",
      "crm_add_note",
      "crm_upsert_contact"
    ],
    "seed_records": [
      {
        "id": "c-1",
        "table": "contacts",
        "fields": {
          "last_name": "васильев",
          "first_name": "иван",
          "middle_name": "павлович",
          "phone": "+79889990949",
          "email": "vasilev76@bk.ru",
          "birth_date": "1982-08-12",
          "address": {
            "city": "краснодар",
            "street": "кирова",
            "house": "53",
            "flat": "79"
          }
        },
        "pii_ids": [
          "i1",
          "i2",
          "i3",
          "i4",
          "i5",
          "i6",
          "i7"
        ]
      }
    ],
    "pii": [
      {
        "id": "i1",
        "type": "NAME",
        "identity": "p58",
        "value": "васильев",
        "canonical": "васильев",
        "parts": {
          "surname": "васильев",
          "gender": "m"
        },
        "where": {
          "kind": "seed",
          "msg": -1,
          "start": 0,
          "end": 0,
          "record": "c-1",
          "path": "last_name"
        },
        "duty": "required",
        "spoken": false,
        "stale": false
      },
      {
        "id": "i2",
        "type": "NAME",
        "identity": "p58",
        "value": "иван",
        "canonical": "иван",
        "parts": {
          "given": "иван",
          "gender": "m"
        },
        "where": {
          "kind": "seed",
          "msg": -1,
          "start": 0,
          "end": 0,
          "record": "c-1",
          "path": "first_name"
        },
        "duty": "required",
        "spoken": false,
        "stale": false
      },
      {
        "id": "i3",
        "type": "NAME",
        "identity": "p58",
        "value": "павлович",
        "canonical": "павлович",
        "parts": {
          "patronymic": "павлович",
          "gender": "m"
        },
        "where": {
          "kind": "seed",
          "msg": -1,
          "start": 0,
          "end": 0,
          "record": "c-1",
          "path": "middle_name"
        },
        "duty": "required",
        "spoken": false,
        "stale": false
      },
      {
        "id": "i4",
        "type": "PHONE",
        "identity": "p58",
        "value": "+79889990949",
        "canonical": "+79889990949",
        "parts": {
          "digits": "9889990949"
        },
        "where": {
          "kind": "seed",
          "msg": -1,
          "start": 0,
          "end": 0,
          "record": "c-1",
          "path": "phone"
        },
        "duty": "required",
        "spoken": false,
        "stale": false
      },
      {
        "id": "i5",
        "type": "EMAIL",
        "identity": "p58",
        "value": "vasilev76@bk.ru",
        "canonical": "vasilev76@bk.ru",
        "parts": {
          "local": "vasilev76",
          "domain": "bk.ru"
        },
        "where": {
          "kind": "seed",
          "msg": -1,
          "start": 0,
          "end": 0,
          "record": "c-1",
          "path": "email"
        },
        "duty": "required",
        "spoken": false,
        "stale": false
      },
      {
        "id": "i6",
        "type": "DOB",
        "identity": "p58",
        "value": "1982-08-12",
        "canonical": "1982-08-12",
        "parts": {
          "iso": "1982-08-12"
        },
        "where": {
          "kind": "seed",
          "msg": -1,
          "start": 0,
          "end": 0,
          "record": "c-1",
          "path": "birth_date"
        },
        "duty": "required",
        "spoken": false,
        "stale": false
      },
      {
        "id": "i7",
        "type": "LOC",
        "identity": "p58.home",
        "value": "кирова",
        "canonical": "кирова",
        "parts": {
          "street": "кирова",
          "street_type": "проспект",
          "house": "53",
          "flat": "79",
          "city": "краснодар"
        },
        "where": {
          "kind": "seed",
          "msg": -1,
          "start": 0,
          "end": 0,
          "record": "c-1",
          "path": "address.street"
        },
        "duty": "required",
        "spoken": false,
        "stale": false
      },
      {
        "id": "i8",
        "type": "NAME",
        "identity": "p58",
        "value": "васильев иван",
        "canonical": "васильев иван",
        "parts": {
          "surname": "васильев",
          "given": "иван",
          "gender": "m"
        },
        "where": {
          "kind": "message",
          "msg": 1,
          "start": 16,
          "end": 29,
          "record": "",
          "path": ""
        },
        "duty": "required",
        "spoken": false,
        "stale": false
      },
      {
        "id": "i9",
        "type": "PHONE",
        "identity": "p58",
        "value": "8 988 999 09 49",
        "canonical": "+79889990949",
        "parts": {
          "digits": "9889990949"
        },
        "where": {
          "kind": "message",
          "msg": 1,
          "start": 61,
          "end": 76,
          "record": "",
          "path": ""
        },
        "duty": "required",
        "spoken": false,
        "stale": false
      },
      {
        "id": "i10",
        "type": "LOC",
        "identity": "p58.home",
        "value": "краснодар проспект кирова 53 квартира 79",
        "canonical": "краснодар проспект кирова 53 квартира 79",
        "parts": {
          "street": "кирова",
          "street_type": "проспект",
          "house": "53",
          "flat": "79",
          "city": "краснодар"
        },
        "where": {
          "kind": "message",
          "msg": 2,
          "start": 10,
          "end": 50,
          "record": "",
          "path": ""
        },
        "duty": "required",
        "spoken": false,
        "stale": false
      },
      {
        "id": "i11",
        "type": "NAME",
        "identity": "p58r",
        "value": "мамедова лейла",
        "canonical": "мамедова лейла",
        "parts": {
          "surname": "мамедова",
          "given": "лейла",
          "gender": "f"
        },
        "where": {
          "kind": "message",
          "msg": 5,
          "start": 15,
          "end": 29,
          "record": "",
          "path": ""
        },
        "duty": "required",
        "spoken": false,
        "stale": false
      },
      {
        "id": "i12",
        "type": "PHONE",
        "identity": "p58r",
        "value": "89228231652",
        "canonical": "+79228231652",
        "parts": {
          "digits": "9228231652"
        },
        "where": {
          "kind": "message",
          "msg": 5,
          "start": 41,
          "end": 52,
          "record": "",
          "path": ""
        },
        "duty": "required",
        "spoken": false,
        "stale": false
      }
    ],
    "plain": [
      {
        "value": "3",
        "where": {
          "kind": "message",
          "msg": 2,
          "start": 59,
          "end": 60,
          "record": "",
          "path": ""
        },
        "family": "weight",
        "why": "вес посылки — не персональные данные, обязан дойти как назван"
      }
    ],
    "negatives": [
      {
        "value": "10 часам",
        "start": 86,
        "end": 94,
        "msg": 1,
        "family": "time_of_day",
        "why": "время, а не номер"
      }
    ],
    "expects": {
      "reachable_tools": [
        "crm_find_contact",
        "delivery_quote",
        "delivery_create_order",
        "order_status",
        "notify_sms",
        "order_cancel"
      ],
      "primary_identity": "p58",
      "must_contain": [],
      "must_not_contain": [],
      "validate_types": []
    },
    "trace": [
      {
        "msg": 1,
        "key": "",
        "start": 0,
        "end": 6,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 1,
        "key": "",
        "start": 6,
        "end": 7,
        "origin": "literal"
      },
      {
        "msg": 1,
        "key": "",
        "start": 7,
        "end": 11,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 1,
        "key": "",
        "start": 11,
        "end": 12,
        "origin": "literal"
      },
      {
        "msg": 1,
        "key": "",
        "start": 12,
        "end": 15,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 1,
        "key": "",
        "start": 15,
        "end": 16,
        "origin": "literal"
      },
      {
        "msg": 1,
        "key": "n1",
        "start": 16,
        "end": 29,
        "origin": "value:n1"
      },
      {
        "msg": 1,
        "key": "",
        "start": 29,
        "end": 30,
        "origin": "literal"
      },
      {
        "msg": 1,
        "key": "",
        "start": 30,
        "end": 34,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 1,
        "key": "",
        "start": 34,
        "end": 35,
        "origin": "literal"
      },
      {
        "msg": 1,
        "key": "",
        "start": 35,
        "end": 44,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 1,
        "key": "",
        "start": 44,
        "end": 45,
        "origin": "literal"
      },
      {
        "msg": 1,
        "key": "",
        "start": 45,
        "end": 52,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 1,
        "key": "",
        "start": 52,
        "end": 53,
        "origin": "literal"
      },
      {
        "msg": 1,
        "key": "",
        "start": 53,
        "end": 60,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 1,
        "key": "",
        "start": 60,
        "end": 61,
        "origin": "literal"
      },
      {
        "msg": 1,
        "key": "ph1",
        "start": 61,
        "end": 76,
        "origin": "value:ph1"
      },
      {
        "msg": 1,
        "key": "",
        "start": 76,
        "end": 77,
        "origin": "literal"
      },
      {
        "msg": 1,
        "key": "",
        "start": 77,
        "end": 83,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 1,
        "key": "",
        "start": 83,
        "end": 84,
        "origin": "literal"
      },
      {
        "msg": 1,
        "key": "",
        "start": 84,
        "end": 85,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 1,
        "key": "",
        "start": 85,
        "end": 86,
        "origin": "literal"
      },
      {
        "msg": 1,
        "key": "neg1",
        "start": 86,
        "end": 94,
        "origin": "negative:neg1"
      },
      {
        "msg": 2,
        "key": "",
        "start": 0,
        "end": 6,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 2,
        "key": "",
        "start": 6,
        "end": 7,
        "origin": "literal"
      },
      {
        "msg": 2,
        "key": "",
        "start": 7,
        "end": 9,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 2,
        "key": "",
        "start": 9,
        "end": 10,
        "origin": "literal"
      },
      {
        "msg": 2,
        "key": "a1",
        "start": 10,
        "end": 50,
        "origin": "value:a1"
      },
      {
        "msg": 2,
        "key": "",
        "start": 50,
        "end": 51,
        "origin": "literal"
      },
      {
        "msg": 2,
        "key": "",
        "start": 51,
        "end": 58,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 2,
        "key": "",
        "start": 58,
        "end": 59,
        "origin": "literal"
      },
      {
        "msg": 2,
        "key": "w1",
        "start": 59,
        "end": 60,
        "origin": "plain:w1"
      },
      {
        "msg": 2,
        "key": "",
        "start": 60,
        "end": 61,
        "origin": "literal"
      },
      {
        "msg": 2,
        "key": "",
        "start": 61,
        "end": 71,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 3,
        "key": "",
        "start": 0,
        "end": 5,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 3,
        "key": "",
        "start": 5,
        "end": 6,
        "origin": "literal"
      },
      {
        "msg": 3,
        "key": "",
        "start": 6,
        "end": 12,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 4,
        "key": "",
        "start": 0,
        "end": 6,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 4,
        "key": "",
        "start": 6,
        "end": 7,
        "origin": "literal"
      },
      {
        "msg": 4,
        "key": "",
        "start": 7,
        "end": 17,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 5,
        "key": "",
        "start": 0,
        "end": 7,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 5,
        "key": "",
        "start": 7,
        "end": 8,
        "origin": "literal"
      },
      {
        "msg": 5,
        "key": "",
        "start": 8,
        "end": 10,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 5,
        "key": "",
        "start": 10,
        "end": 11,
        "origin": "literal"
      },
      {
        "msg": 5,
        "key": "",
        "start": 11,
        "end": 12,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 5,
        "key": "",
        "start": 12,
        "end": 13,
        "origin": "literal"
      },
      {
        "msg": 5,
        "key": "",
        "start": 13,
        "end": 14,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 5,
        "key": "",
        "start": 14,
        "end": 15,
        "origin": "literal"
      },
      {
        "msg": 5,
        "key": "n2",
        "start": 15,
        "end": 29,
        "origin": "value:n2"
      },
      {
        "msg": 5,
        "key": "",
        "start": 29,
        "end": 30,
        "origin": "literal"
      },
      {
        "msg": 5,
        "key": "",
        "start": 30,
        "end": 32,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 5,
        "key": "",
        "start": 32,
        "end": 33,
        "origin": "literal"
      },
      {
        "msg": 5,
        "key": "",
        "start": 33,
        "end": 40,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 5,
        "key": "",
        "start": 40,
        "end": 41,
        "origin": "literal"
      },
      {
        "msg": 5,
        "key": "ph2",
        "start": 41,
        "end": 52,
        "origin": "value:ph2"
      },
      {
        "msg": 6,
        "key": "",
        "start": 0,
        "end": 1,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 6,
        "key": "",
        "start": 1,
        "end": 2,
        "origin": "literal"
      },
      {
        "msg": 6,
        "key": "",
        "start": 2,
        "end": 8,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 6,
        "key": "",
        "start": 8,
        "end": 9,
        "origin": "literal"
      },
      {
        "msg": 6,
        "key": "",
        "start": 9,
        "end": 17,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 6,
        "key": "",
        "start": 17,
        "end": 18,
        "origin": "literal"
      },
      {
        "msg": 6,
        "key": "",
        "start": 18,
        "end": 23,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 7,
        "key": "",
        "start": 0,
        "end": 1,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 7,
        "key": "",
        "start": 1,
        "end": 2,
        "origin": "literal"
      },
      {
        "msg": 7,
        "key": "",
        "start": 2,
        "end": 5,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 7,
        "key": "",
        "start": 5,
        "end": 6,
        "origin": "literal"
      },
      {
        "msg": 7,
        "key": "",
        "start": 6,
        "end": 14,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 7,
        "key": "",
        "start": 14,
        "end": 15,
        "origin": "literal"
      },
      {
        "msg": 7,
        "key": "",
        "start": 15,
        "end": 18,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 7,
        "key": "",
        "start": 18,
        "end": 19,
        "origin": "literal"
      },
      {
        "msg": 7,
        "key": "",
        "start": 19,
        "end": 21,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 7,
        "key": "",
        "start": 21,
        "end": 22,
        "origin": "literal"
      },
      {
        "msg": 7,
        "key": "",
        "start": 22,
        "end": 25,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 7,
        "key": "",
        "start": 25,
        "end": 26,
        "origin": "literal"
      },
      {
        "msg": 7,
        "key": "",
        "start": 26,
        "end": 31,
        "origin": "chunk:noisy_word"
      }
    ],
    "note": "семь ходов: поиск, расчёт, оформление, поздний получатель, номер заказа из ответа инструмента, перенос или отмена, смс"
  },
  "behaviour": "single",
  "hops": [
    {
      "kind": "IN",
      "owner": "user",
      "item_id": "i8",
      "hop_index": 0,
      "turn": 1,
      "tool_name": "",
      "call_ordinal": -1,
      "parallel_group": "",
      "source_hop": -1,
      "path": "",
      "optional": false
    },
    {
      "kind": "IN",
      "owner": "user",
      "item_id": "i9",
      "hop_index": 1,
      "turn": 1,
      "tool_name": "",
      "call_ordinal": -1,
      "parallel_group": "",
      "source_hop": -1,
      "path": "",
      "optional": false
    },
    {
      "kind": "IN",
      "owner": "user",
      "item_id": "i10",
      "hop_index": 2,
      "turn": 2,
      "tool_name": "",
      "call_ordinal": -1,
      "parallel_group": "",
      "source_hop": -1,
      "path": "",
      "optional": false
    },
    {
      "kind": "IN",
      "owner": "user",
      "item_id": "i11",
      "hop_index": 3,
      "turn": 5,
      "tool_name": "",
      "call_ordinal": -1,
      "parallel_group": "",
      "source_hop": -1,
      "path": "",
      "optional": false
    },
    {
      "kind": "IN",
      "owner": "user",
      "item_id": "i12",
      "hop_index": 4,
      "turn": 5,
      "tool_name": "",
      "call_ordinal": -1,
      "parallel_group": "",
      "source_hop": -1,
      "path": "",
      "optional": false
    },
    {
      "kind": "IN",
      "owner": "tool",
      "item_id": "i1",
      "hop_index": 5,
      "turn": 1,
      "tool_name": "crm_find_contact",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": -1,
      "path": "contacts[].last_name",
      "optional": false
    },
    {
      "kind": "IN",
      "owner": "tool",
      "item_id": "i2",
      "hop_index": 6,
      "turn": 1,
      "tool_name": "crm_find_contact",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": -1,
      "path": "contacts[].first_name",
      "optional": false
    },
    {
      "kind": "IN",
      "owner": "tool",
      "item_id": "i3",
      "hop_index": 7,
      "turn": 1,
      "tool_name": "crm_find_contact",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": -1,
      "path": "contacts[].middle_name",
      "optional": false
    },
    {
      "kind": "IN",
      "owner": "tool",
      "item_id": "i4",
      "hop_index": 8,
      "turn": 1,
      "tool_name": "crm_find_contact",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": -1,
      "path": "contacts[].phone",
      "optional": false
    },
    {
      "kind": "IN",
      "owner": "tool",
      "item_id": "i5",
      "hop_index": 9,
      "turn": 1,
      "tool_name": "crm_find_contact",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": -1,
      "path": "contacts[].email",
      "optional": false
    },
    {
      "kind": "IN",
      "owner": "tool",
      "item_id": "i6",
      "hop_index": 10,
      "turn": 1,
      "tool_name": "crm_find_contact",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": -1,
      "path": "contacts[].birth_date",
      "optional": false
    },
    {
      "kind": "IN",
      "owner": "tool",
      "item_id": "i7",
      "hop_index": 11,
      "turn": 1,
      "tool_name": "crm_find_contact",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": -1,
      "path": "contacts[].address.street",
      "optional": false
    },
    {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i9",
      "hop_index": 12,
      "turn": 7,
      "tool_name": "crm_find_contact",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": 1,
      "path": "query.phone",
      "optional": true
    },
    {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i8",
      "hop_index": 13,
      "turn": 7,
      "tool_name": "crm_find_contact",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": 0,
      "path": "query.last_name",
      "optional": true
    },
    {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i8",
      "hop_index": 14,
      "turn": 7,
      "tool_name": "delivery_create_order",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": 0,
      "path": "recipient.name",
      "optional": false
    },
    {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i9",
      "hop_index": 15,
      "turn": 7,
      "tool_name": "delivery_create_order",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": 1,
      "path": "recipient.phones[].number",
      "optional": false
    },
    {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i10",
      "hop_index": 16,
      "turn": 7,
      "tool_name": "delivery_create_order",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": 2,
      "path": "to_location.city",
      "optional": false
    },
    {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i10",
      "hop_index": 17,
      "turn": 7,
      "tool_name": "delivery_create_order",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": 2,
      "path": "to_location.address",
      "optional": false
    },
    {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i9",
      "hop_index": 18,
      "turn": 7,
      "tool_name": "notify_sms",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": 1,
      "path": "number",
      "optional": false
    },
    {
      "kind": "OUT",
      "owner": "answer",
      "item_id": "i1",
      "hop_index": 19,
      "turn": 7,
      "tool_name": "",
      "call_ordinal": -1,
      "parallel_group": "",
      "source_hop": 5,
      "path": "",
      "optional": true
    },
    {
      "kind": "OUT",
      "owner": "answer",
      "item_id": "i2",
      "hop_index": 20,
      "turn": 7,
      "tool_name": "",
      "call_ordinal": -1,
      "parallel_group": "",
      "source_hop": 6,
      "path": "",
      "optional": true
    },
    {
      "kind": "OUT",
      "owner": "answer",
      "item_id": "i3",
      "hop_index": 21,
      "turn": 7,
      "tool_name": "",
      "call_ordinal": -1,
      "parallel_group": "",
      "source_hop": 7,
      "path": "",
      "optional": true
    },
    {
      "kind": "OUT",
      "owner": "answer",
      "item_id": "i4",
      "hop_index": 22,
      "turn": 7,
      "tool_name": "",
      "call_ordinal": -1,
      "parallel_group": "",
      "source_hop": 8,
      "path": "",
      "optional": true
    },
    {
      "kind": "OUT",
      "owner": "answer",
      "item_id": "i5",
      "hop_index": 23,
      "turn": 7,
      "tool_name": "",
      "call_ordinal": -1,
      "parallel_group": "",
      "source_hop": 9,
      "path": "",
      "optional": true
    },
    {
      "kind": "OUT",
      "owner": "answer",
      "item_id": "i6",
      "hop_index": 24,
      "turn": 7,
      "tool_name": "",
      "call_ordinal": -1,
      "parallel_group": "",
      "source_hop": 10,
      "path": "",
      "optional": true
    }
  ],
  "returns": [
    {
      "tool_name": "crm_find_contact",
      "call_ordinal": 0,
      "return_form": "list",
      "result_item_ids": [
        "i1",
        "i2",
        "i3",
        "i4",
        "i5",
        "i6",
        "i7"
      ]
    }
  ],
  "forced": [],
  "memory": [],
  "pick": null,
  "branch": null,
  "loop": null,
  "rag": null,
  "document": null,
  "has_result": true,
  "streaming": false,
  "revised_from_v4": true
}

## Actual gateway arm (written/restored calls, tool results, answers, mentions)

{
  "base": {
    "case_id": "long_order-058",
    "arm": "I",
    "repeat": 0,
    "calls": [
      {
        "name": "crm_find_contact",
        "written": {
          "query": {
            "phone": "+79908072770"
          }
        },
        "restored": {
          "query": {
            "phone": "+79889990949"
          }
        },
        "residual": {},
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "query": {
            "phone": "+79889990949"
          }
        },
        "seq": 1
      },
      {
        "name": "delivery_quote",
        "written": {
          "city": "Краснодар",
          "weight": 3000
        },
        "restored": {
          "city": "Краснодар",
          "weight": 3000
        },
        "residual": {},
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "city": "краснодар",
          "weight": 3000
        },
        "seq": 2
      },
      {
        "name": "delivery_create_order",
        "written": {
          "packages": [
            {
              "weight": 3000
            }
          ],
          "recipient": {
            "name": "Сазонова Таисия",
            "phones": [
              {
                "number": "+79431366533"
              }
            ]
          },
          "to_location": {
            "address": "Сосновая, 59, кв. 109",
            "city": "Краснодар",
            "postal_code": "350000"
          }
        },
        "restored": {
          "packages": [
            {
              "weight": 3000
            }
          ],
          "recipient": {
            "name": "Мамедова Лейла",
            "phones": [
              {
                "number": "+79228231652"
              }
            ]
          },
          "to_location": {
            "address": "Сосновая, 53, кв. 79",
            "city": "Краснодар",
            "postal_code": "350000"
          }
        },
        "residual": {
          "to_location.address": [
            "сосновая"
          ]
        },
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "comment": "",
          "packages": [
            {
              "weight": 3000
            }
          ],
          "recipient": {
            "name": "Мамедова Лейла",
            "phones": [
              "+79228231652"
            ]
          },
          "to_location": {
            "address": "Сосновая, 53, кв. 79",
            "city": "краснодар",
            "postal_code": "350000"
          }
        },
        "seq": 3
      },
      {
        "name": "order_status",
        "written": {
          "order_id": "ord-1"
        },
        "restored": {
          "order_id": "ord-1"
        },
        "residual": {},
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "order_id": "ord-1"
        },
        "seq": 4
      },
      {
        "name": "order_cancel",
        "written": {
          "order_id": "ord-1",
          "reason": "Отмена по просьбе клиента; адрес доставки в заказе не совпал с названным"
        },
        "restored": {
          "order_id": "ord-1",
          "reason": "Отмена по просьбе клиента; адрес доставки в заказе не совпал с названным"
        },
        "residual": {},
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "order_id": "ord-1",
          "reason": "Отмена по просьбе клиента; адрес доставки в заказе не совпал с названным"
        },
        "seq": 5
      },
      {
        "name": "crm_add_note",
        "written": {
          "entity_id": "c-1",
          "note_type": "call_in",
          "text": "Клиент Сорокин Макар Борисович обратился по отправке посылки: Краснодар, 3 кг, получатель Сазонова Таисия (+79431366533). Заказ ord-1 создан (510 ₽, 2 дня), но адрес доставки в системе не совпал с названным (Лавандовая, 71, кв. 208 vs Сосновая, 59, кв. 109). Заказ отменён по просьбе клиента. Вызов курьера не оформлялся."
        },
        "restored": {
          "entity_id": "c-1",
          "note_type": "call_in",
          "text": "Клиент Васильев Иван Павлович обратился по отправке посылки: Краснодар, 3 кг, получатель Мамедова Лейла (+79228231652). Заказ ord-1 создан (510 ₽, 2 дня), но адрес доставки в системе не совпал с названным (Сосновая, 53, кв. 79 vs Сосновая, 53, кв. 79). Заказ отменён по просьбе клиента. Вызов курьера не оформлялся."
        },
        "residual": {
          "text": [
            "сосновая"
          ]
        },
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "entity_id": "c-1",
          "note_type": "call_in",
          "text": "Клиент Васильев Иван Павлович обратился по отправке посылки: Краснодар, 3 кг, получатель Мамедова Лейла (+79228231652). Заказ ord-1 создан (510 ₽, 2 дня), но адрес доставки в системе не совпал с названным (Сосновая, 53, кв. 79 vs Сосновая, 53, кв. 79). Заказ отменён по просьбе клиента. Вызов курьера не оформлялся."
        },
        "seq": 6
      },
      {
        "name": "notify_sms",
        "written": {
          "number": "+79908072770",
          "sign": "Dostavka",
          "text": "Заказ ord-1 отменён. Отправку в Краснодар (получатель Сазонова Таисия, 3 кг, 510 руб.) отменили по вашему запросу. Курьер не вызывался. Если нужно оформить заново — ответьте на это сообщение."
        },
        "restored": {
          "number": "+79889990949",
          "sign": "Dostavka",
          "text": "Заказ ord-1 отменён. Отправку в Краснодар (получатель Мамедова Лейла, 3 кг, 510 руб.) отменили по вашему запросу. Курьер не вызывался. Если нужно оформить заново — ответьте на это сообщение."
        },
        "residual": {},
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "number": "+79889990949",
          "sign": "Dostavka",
          "text": "Заказ ord-1 отменён. Отправку в Краснодар (получатель Мамедова Лейла, 3 кг, 510 руб.) отменили по вашему запросу. Курьер не вызывался. Если нужно оформить заново — ответьте на это сообщение."
        },
        "seq": 7
      }
    ],
    "state": [
      {
        "fields": {
          "cancel_reason": "Отмена по просьбе клиента; адрес доставки в заказе не совпал с названным",
          "comment": "",
          "packages": [
            {
              "weight": 3000
            }
          ],
          "recipient": {
            "name": "Мамедова Лейла",
            "phones": [
              "+79228231652"
            ]
          },
          "status": "CANCELLED",
          "to_location": {
            "address": "Сосновая, 53, кв. 79",
            "city": "краснодар",
            "postal_code": "350000"
          }
        },
        "id": "ord-1",
        "seq": 5,
        "table": "orders",
        "tool": "order_cancel"
      },
      {
        "fields": {
          "entity_id": "c-1",
          "note_type": "call_in",
          "text": "Клиент Васильев Иван Павлович обратился по отправке посылки: Краснодар, 3 кг, получатель Мамедова Лейла (+79228231652). Заказ ord-1 создан (510 ₽, 2 дня), но адрес доставки в системе не совпал с названным (Сосновая, 53, кв. 79 vs Сосновая, 53, кв. 79). Заказ отменён по просьбе клиента. Вызов курьера не оформлялся."
        },
        "id": "note-1",
        "seq": 6,
        "table": "notes",
        "tool": "crm_add_note"
      },
      {
        "fields": {
          "number": "+79889990949",
          "sign": "Dostavka",
          "text": "Заказ ord-1 отменён. Отправку в Краснодар (получатель Мамедова Лейла, 3 кг, 510 руб.) отменили по вашему запросу. Курьер не вызывался. Если нужно оформить заново — ответьте на это сообщение."
        },
        "id": "sms-1",
        "seq": 7,
        "table": "sms",
        "tool": "notify_sms"
      }
    ],
    "reply": "СМС отправлена на ваш номер **8 988 999 09 49** 📩\n\nТекст: «Заказ ord-1 отменён. Отправку в Краснодар (получатель Мамедова Лейла, 3 кг, 510 руб.) отменили по вашему запросу. Курьер не вызывался. Если нужно оформить заново — ответьте на это сообщение.»\n\nЧто-нибудь ещё, Иван Павлович?",
    "termination": "done",
    "cost_usd": 0.009699,
    "substitutes": {
      "i1": [
        "сорокин",
        {
          "surname": "сорокин"
        }
      ],
      "i10": [
        "краснодар проспект сосновая 59 квартира 109",
        {
          "flat": "109",
          "house": "59",
          "street": "краснодар сосновая"
        }
      ],
      "i11": [
        "сазонова таисия",
        {
          "given": "таисия",
          "surname": "сазонова"
        }
      ],
      "i12": [
        "89431366533",
        {
          "digits": "9431366533"
        }
      ],
      "i2": [
        "макар",
        {
          "given": "макар"
        }
      ],
      "i3": [
        "борисович",
        {
          "patronymic": "борисович"
        }
      ],
      "i4": [
        "8 990 807 27 70",
        {
          "digits": "9908072770"
        }
      ],
      "i5": [
        "teywsrsv@example.ru",
        {
          "domain": "example.ru",
          "local": "teywsrsv"
        }
      ],
      "i6": [
        "1982-06-16",
        {
          "iso": "1982-06-16"
        }
      ],
      "i7": [
        "сосновая",
        {
          "street": "сосновая"
        }
      ],
      "i8": [
        "сорокин макар",
        {
          "given": "макар",
          "surname": "сорокин"
        }
      ],
      "i9": [
        "8 990 807 27 70",
        {
          "digits": "9908072770"
        }
      ]
    },
    "masked_spans": {
      "0": [],
      "1": [
        [
          16,
          29
        ],
        [
          61,
          76
        ]
      ],
      "2": [
        [
          10,
          50
        ]
      ],
      "3": [],
      "4": [],
      "5": [
        [
          15,
          29
        ],
        [
          41,
          52
        ]
      ],
      "6": [],
      "7": []
    }
  },
  "reply_raw": "СМС отправлена на ваш номер **8 990 807-27-70** 📩\n\nТекст: «Заказ ord-1 отменён. Отправку в Краснодар (получатель Сазонова Таисия, 3 кг, 510 руб.) отменили по вашему запросу. Курьер не вызывался. Если нужно оформить заново — ответьте на это сообщение.»\n\nЧто-нибудь ещё, Макар Борисович?",
  "control_reply": "Отправил СМС на ваш номер **+7 988 999 09 49**:\n\n> Заказ на доставку ord-2 отменён. Активных заказов нет. Вызов курьера на 02.09, 09:00–10:00 (Кирова 53, кв. 79) пока остаётся активным. Для его отмены свяжитесь с оператором.\n\nЕсли нужно ещё что-то — я на связи.",
  "tool_results": [
    {
      "tool_name": "crm_find_contact",
      "seq": 1,
      "call_ordinal": 0,
      "turn": 1,
      "return_form": "list",
      "text_real": "{\n  \"contacts\": [\n    {\n      \"id\": \"c-1\",\n      \"last_name\": \"васильев\",\n      \"first_name\": \"иван\",\n      \"middle_name\": \"павлович\",\n      \"phone\": \"+79889990949\",\n      \"email\": \"vasilev76@bk.ru\",\n      \"birth_date\": \"1982-08-12\",\n      \"address\": {\n        \"city\": \"краснодар\",\n        \"street\": \"кирова\",\n        \"house\": \"53\",\n        \"flat\": \"79\"\n      }\n    }\n  ]\n}",
      "text_masked": "{\n  \"contacts\": [\n    {\n      \"id\": \"c-1\",\n      \"last_name\": \"сорокин\",\n      \"first_name\": \"макар\",\n      \"middle_name\": \"борисович\",\n      \"phone\": \"8 990 807 27 70\",\n      \"email\": \"teywsrsv@example.ru\",\n      \"birth_date\": \"1982-06-16\",\n      \"address\": {\n        \"city\": \"краснодар\",\n        \"street\": \"сосновая\",\n        \"house\": \"59\",\n        \"flat\": \"109\"\n      }\n    }\n  ]\n}",
      "spans_real": {
        "i1": [
          63,
          71
        ],
        "i2": [
          95,
          99
        ],
        "i3": [
          124,
          132
        ],
        "i4": [
          151,
          163
        ],
        "i5": [
          182,
          197
        ],
        "i6": [
          221,
          231
        ],
        "i7": [
          301,
          307
        ]
      },
      "pieces": [
        [
          63,
          71,
          "сорокин",
          "NAME"
        ],
        [
          95,
          99,
          "макар",
          "NAME"
        ],
        [
          124,
          132,
          "борисович",
          "NAME"
        ],
        [
          151,
          163,
          "8 990 807 27 70",
          "PHONE"
        ],
        [
          182,
          197,
          "teywsrsv@example.ru",
          "EMAIL"
        ],
        [
          221,
          231,
          "1982-06-16",
          "DOB"
        ],
        [
          270,
          279,
          "краснодар",
          "LOC"
        ],
        [
          301,
          307,
          "сосновая",
          "LOC"
        ],
        [
          328,
          330,
          "59",
          "LOC"
        ],
        [
          350,
          352,
          "109",
          "LOC"
        ]
      ],
      "forced": false
    },
    {
      "tool_name": "delivery_quote",
      "seq": 2,
      "call_ordinal": 0,
      "turn": 3,
      "return_form": "single",
      "text_real": "{\n  \"city\": \"краснодар\",\n  \"weight\": \"3000\",\n  \"price\": \"510.00\",\n  \"currency\": \"RUB\",\n  \"days\": \"2\",\n  \"pickup_point\": {\n    \"address\": \"\"\n  }\n}",
      "text_masked": "{\n  \"city\": \"краснодар\",\n  \"weight\": \"3000\",\n  \"price\": \"510.00\",\n  \"currency\": \"RUB\",\n  \"days\": \"2\",\n  \"pickup_point\": {\n    \"address\": \"\"\n  }\n}",
      "spans_real": {},
      "pieces": [],
      "forced": false
    },
    {
      "tool_name": "delivery_create_order",
      "seq": 3,
      "call_ordinal": 0,
      "turn": 5,
      "return_form": "single",
      "text_real": "{\n  \"uuid\": \"ord-1\",\n  \"status\": \"ACCEPTED\",\n  \"recipient\": {\n    \"name\": \"Мамедова Лейла\",\n    \"phone\": \"+79228231652\"\n  },\n  \"to_location\": {\n    \"postal_code\": \"350000\",\n    \"city\": \"краснодар\",\n    \"address\": \"Сосновая, 53, кв. 79\"\n  }\n}",
      "text_masked": "{\n  \"uuid\": \"ord-1\",\n  \"status\": \"ACCEPTED\",\n  \"recipient\": {\n    \"name\": \"Сазонова Таисия\",\n    \"phone\": \"89431366533\"\n  },\n  \"to_location\": {\n    \"postal_code\": \"350000\",\n    \"city\": \"краснодар\",\n    \"address\": \"Лавандовая, 71, кв. 208\"\n  }\n}",
      "spans_real": {},
      "pieces": [
        [
          75,
          89,
          "Сазонова Таисия",
          "NAME"
        ],
        [
          106,
          118,
          "89431366533",
          "PHONE"
        ],
        [
          214,
          234,
          "Лавандовая, 71, кв. 208",
          "LOC"
        ]
      ],
      "forced": false
    },
    {
      "tool_name": "order_status",
      "seq": 4,
      "call_ordinal": 0,
      "turn": 5,
      "return_form": "single",
      "text_real": "{\n  \"uuid\": \"ord-1\",\n  \"status\": \"ACCEPTED\",\n  \"date\": \"\",\n  \"recipient\": {\n    \"name\": \"Мамедова Лейла\",\n    \"phone\": \"+79228231652\"\n  },\n  \"to_location\": {\n    \"city\": \"краснодар\",\n    \"address\": \"Сосновая, 53, кв. 79\"\n  }\n}",
      "text_masked": "{\n  \"uuid\": \"ord-1\",\n  \"status\": \"ACCEPTED\",\n  \"date\": \"\",\n  \"recipient\": {\n    \"name\": \"Сазонова Таисия\",\n    \"phone\": \"89431366533\"\n  },\n  \"to_location\": {\n    \"city\": \"краснодар\",\n    \"address\": \"Лавандовая, 71, кв. 208\"\n  }\n}",
      "spans_real": {},
      "pieces": [
        [
          89,
          103,
          "Сазонова Таисия",
          "NAME"
        ],
        [
          120,
          132,
          "89431366533",
          "PHONE"
        ],
        [
          199,
          219,
          "Лавандовая, 71, кв. 208",
          "LOC"
        ]
      ],
      "forced": false
    },
    {
      "tool_name": "order_cancel",
      "seq": 5,
      "call_ordinal": 0,
      "turn": 6,
      "return_form": "single",
      "text_real": "{\n  \"uuid\": \"ord-1\",\n  \"status\": \"CANCELLED\",\n  \"recipient\": {\n    \"name\": \"Мамедова Лейла\",\n    \"phone\": \"+79228231652\"\n  }\n}",
      "text_masked": "{\n  \"uuid\": \"ord-1\",\n  \"status\": \"CANCELLED\",\n  \"recipient\": {\n    \"name\": \"Сазонова Таисия\",\n    \"phone\": \"89431366533\"\n  }\n}",
      "spans_real": {},
      "pieces": [
        [
          76,
          90,
          "Сазонова Таисия",
          "NAME"
        ],
        [
          107,
          119,
          "89431366533",
          "PHONE"
        ]
      ],
      "forced": false
    },
    {
      "tool_name": "crm_add_note",
      "seq": 6,
      "call_ordinal": 0,
      "turn": 6,
      "return_form": "single",
      "text_real": "{\n  \"id\": \"note-1\",\n  \"entity_id\": \"c-1\",\n  \"length\": 315,\n  \"entity\": {\n    \"last_name\": \"васильев\",\n    \"first_name\": \"иван\",\n    \"phone\": \"+79889990949\"\n  }\n}",
      "text_masked": "{\n  \"id\": \"note-1\",\n  \"entity_id\": \"c-1\",\n  \"length\": 315,\n  \"entity\": {\n    \"last_name\": \"сорокин\",\n    \"first_name\": \"макар\",\n    \"phone\": \"8 990 807 27 70\"\n  }\n}",
      "spans_real": {
        "i1": [
          91,
          99
        ],
        "i2": [
          121,
          125
        ],
        "i4": [
          142,
          154
        ]
      },
      "pieces": [
        [
          91,
          99,
          "сорокин",
          "NAME"
        ],
        [
          121,
          125,
          "макар",
          "NAME"
        ],
        [
          142,
          154,
          "8 990 807 27 70",
          "PHONE"
        ]
      ],
      "forced": false
    },
    {
      "tool_name": "notify_sms",
      "seq": 7,
      "call_ordinal": 0,
      "turn": 7,
      "return_form": "single",
      "text_real": "{\n  \"id\": \"sms-1\",\n  \"status\": \"queued\",\n  \"number\": \"+79889990949\"\n}",
      "text_masked": "{\n  \"id\": \"sms-1\",\n  \"status\": \"queued\",\n  \"number\": \"8 990 807 27 70\"\n}",
      "spans_real": {
        "i4": [
          54,
          66
        ]
      },
      "pieces": [
        [
          54,
          66,
          "8 990 807 27 70",
          "PHONE"
        ]
      ],
      "forced": false
    }
  ],
  "mentions": [
    {
      "item_id": "i8",
      "msg": 1,
      "result_seq": -1,
      "substitute": "сорокин макар",
      "request_index": 1
    },
    {
      "item_id": "i9",
      "msg": 1,
      "result_seq": -1,
      "substitute": "8 990 807 27 70",
      "request_index": 1
    },
    {
      "item_id": "i1",
      "msg": -1,
      "result_seq": 1,
      "substitute": "сорокин",
      "request_index": 2
    },
    {
      "item_id": "i2",
      "msg": -1,
      "result_seq": 1,
      "substitute": "макар",
      "request_index": 2
    },
    {
      "item_id": "i3",
      "msg": -1,
      "result_seq": 1,
      "substitute": "борисович",
      "request_index": 2
    },
    {
      "item_id": "i4",
      "msg": -1,
      "result_seq": 1,
      "substitute": "8 990 807 27 70",
      "request_index": 2
    },
    {
      "item_id": "i5",
      "msg": -1,
      "result_seq": 1,
      "substitute": "teywsrsv@example.ru",
      "request_index": 2
    },
    {
      "item_id": "i6",
      "msg": -1,
      "result_seq": 1,
      "substitute": "1982-06-16",
      "request_index": 2
    },
    {
      "item_id": "i7",
      "msg": -1,
      "result_seq": 1,
      "substitute": "сосновая",
      "request_index": 2
    },
    {
      "item_id": "i10",
      "msg": 2,
      "result_seq": -1,
      "substitute": "краснодар проспект сосновая 59 квартира 109",
      "request_index": 3
    },
    {
      "item_id": "i11",
      "msg": 5,
      "result_seq": -1,
      "substitute": "сазонова таисия",
      "request_index": 7
    },
    {
      "item_id": "i12",
      "msg": 5,
      "result_seq": -1,
      "substitute": "89431366533",
      "request_index": 7
    },
    {
      "item_id": "i1",
      "msg": -1,
      "result_seq": 6,
      "substitute": "сорокин",
      "request_index": 12
    },
    {
      "item_id": "i2",
      "msg": -1,
      "result_seq": 6,
      "substitute": "макар",
      "request_index": 12
    },
    {
      "item_id": "i4",
      "msg": -1,
      "result_seq": 6,
      "substitute": "8 990 807 27 70",
      "request_index": 12
    },
    {
      "item_id": "i4",
      "msg": -1,
      "result_seq": 7,
      "substitute": "8 990 807 27 70",
      "request_index": 14
    }
  ],
  "turn_replies": [
    "Добрый день, Иван! Сейчас найду вашу карточку в CRM.\nНашёл вашу карточку, Иван Павлович. Чтобы оформить отправку, подскажите, пожалуйста:\n\n1. **Куда** везём — город и адрес получателя (улица, дом, квартира)?\n2. **Кому** — ФИО и телефон получателя?\n3. **Вес посылки** (если не знаете — приму за 1000 г).\n\nИ уточните, что значит «к 10 часам» — вам нужен **забор курьером** от вас сегодня к 10:00 или доставка получателю к 10:00?",
    "Принял: Краснодар, Сосновая 53, кв. 79, вес 3 кг.\n\nЗамечу: этот адрес совпадает с вашим адресом в карточке. Уточните, пожалуйста:\n\n1. **Кому** доставляем — ФИО и телефон получателя?\n2. Что именно значит «**к 10 часам**» — забор курьером от вас сегодня к 10:00 или доставка получателю к 10:00?",
    "Доставка в Краснодар, 3 кг — **510 ₽**, срок **2 дня**.\n\nДля оформления заказа мне ещё нужны:\n1. **ФИО и телефон получателя**.\n2. Уточните про «**к 10 часам**» — забор курьером от вас к 10:00 или доставка получателю к 10:00?\n\nКак только пришлёте — оформлю.",
    "Для оформления не хватает только одного — **данных получателя**. Назовите, пожалуйста, ФИО и телефон получателя. Или получатель — это вы (Васильев Иван, 8 988 999 09 49)?\n\nИ подтвердите, пожалуйста, про «к 10 часам»: нужен забор курьером от вас к 10:00?",
    "Спасибо! Оформляю заказ.\nЗаказ оформлен — **№ ord-1**, получатель Мамедова Лейла, Краснодар, 3 кг, 510 ₽.\n\n⚠️ Но я вижу расхождение: в системе адрес доставки стоит **«Сосновая, 53, кв. 79»**, а вы называли **«Сосновая, 53, кв. 79»**. Подскажите, какой адрес верный — при необходимости переоформлю заказ.\n\nИ по времени: оформить **вызов курьера** на забор посылки от вас (Краснодар, Сосновая 53, кв. 79) **сегодня к 10:00**? Подтвердите — и я вызову.",
    "Готово — заказ **ord-1 отменён** ✅\n\nИтог: отправку в Краснодар (получатель Мамедова Лейла, 3 кг, 510 ₽) отменили по вашему запросу, вызов курьера не оформлял. Заметку в вашу карточку добавил.\n\nЕсли захотите оформить заново — скажите, просто уточним правильный адрес доставки и время. Что-то ещё?",
    "СМС отправлена на ваш номер **8 988 999 09 49** 📩\n\nТекст: «Заказ ord-1 отменён. Отправку в Краснодар (получатель Мамедова Лейла, 3 кг, 510 руб.) отменили по вашему запросу. Курьер не вызывался. Если нужно оформить заново — ответьте на это сообщение.»\n\nЧто-нибудь ещё, Иван Павлович?"
  ],
  "call_turns": [
    1,
    3,
    5,
    5,
    6,
    6,
    7
  ],
  "request_count": 14,
  "stream_mismatch": false,
  "reply_whole": "",
  "turn_residual": 4
}

## Recorded observer hops

[
  {
    "case_id": "long_order-058",
    "repeat": 0,
    "hop": {
      "kind": "IN",
      "owner": "user",
      "item_id": "i8",
      "hop_index": 0,
      "turn": 1,
      "tool_name": "",
      "call_ordinal": -1,
      "parallel_group": "",
      "source_hop": -1,
      "path": "",
      "optional": false
    },
    "declared": true,
    "pii_type": "NAME",
    "produced": "сорокин макар",
    "reference": "васильев иван",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "long_order-058",
    "repeat": 0,
    "hop": {
      "kind": "IN",
      "owner": "user",
      "item_id": "i9",
      "hop_index": 1,
      "turn": 1,
      "tool_name": "",
      "call_ordinal": -1,
      "parallel_group": "",
      "source_hop": -1,
      "path": "",
      "optional": false
    },
    "declared": true,
    "pii_type": "PHONE",
    "produced": "8 990 807 27 70",
    "reference": "8 988 999 09 49",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "long_order-058",
    "repeat": 0,
    "hop": {
      "kind": "IN",
      "owner": "user",
      "item_id": "i10",
      "hop_index": 2,
      "turn": 2,
      "tool_name": "",
      "call_ordinal": -1,
      "parallel_group": "",
      "source_hop": -1,
      "path": "",
      "optional": false
    },
    "declared": true,
    "pii_type": "LOC",
    "produced": "краснодар проспект сосновая 59 квартира 109",
    "reference": "краснодар проспект кирова 53 квартира 79",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "long_order-058",
    "repeat": 0,
    "hop": {
      "kind": "IN",
      "owner": "user",
      "item_id": "i11",
      "hop_index": 3,
      "turn": 5,
      "tool_name": "",
      "call_ordinal": -1,
      "parallel_group": "",
      "source_hop": -1,
      "path": "",
      "optional": false
    },
    "declared": true,
    "pii_type": "NAME",
    "produced": "сазонова таисия",
    "reference": "мамедова лейла",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "long_order-058",
    "repeat": 0,
    "hop": {
      "kind": "IN",
      "owner": "user",
      "item_id": "i12",
      "hop_index": 4,
      "turn": 5,
      "tool_name": "",
      "call_ordinal": -1,
      "parallel_group": "",
      "source_hop": -1,
      "path": "",
      "optional": false
    },
    "declared": true,
    "pii_type": "PHONE",
    "produced": "89431366533",
    "reference": "89228231652",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "long_order-058",
    "repeat": 0,
    "hop": {
      "kind": "IN",
      "owner": "tool",
      "item_id": "i1",
      "hop_index": 5,
      "turn": 1,
      "tool_name": "crm_find_contact",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": -1,
      "path": "contacts[].last_name",
      "optional": false
    },
    "declared": true,
    "pii_type": "NAME",
    "produced": "сорокин",
    "reference": "васильев",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "long_order-058",
    "repeat": 0,
    "hop": {
      "kind": "IN",
      "owner": "tool",
      "item_id": "i2",
      "hop_index": 6,
      "turn": 1,
      "tool_name": "crm_find_contact",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": -1,
      "path": "contacts[].first_name",
      "optional": false
    },
    "declared": true,
    "pii_type": "NAME",
    "produced": "макар",
    "reference": "иван",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "long_order-058",
    "repeat": 0,
    "hop": {
      "kind": "IN",
      "owner": "tool",
      "item_id": "i3",
      "hop_index": 7,
      "turn": 1,
      "tool_name": "crm_find_contact",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": -1,
      "path": "contacts[].middle_name",
      "optional": false
    },
    "declared": true,
    "pii_type": "NAME",
    "produced": "борисович",
    "reference": "павлович",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "long_order-058",
    "repeat": 0,
    "hop": {
      "kind": "IN",
      "owner": "tool",
      "item_id": "i4",
      "hop_index": 8,
      "turn": 1,
      "tool_name": "crm_find_contact",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": -1,
      "path": "contacts[].phone",
      "optional": false
    },
    "declared": true,
    "pii_type": "PHONE",
    "produced": "8 990 807 27 70",
    "reference": "+79889990949",
    "status": "observed",
    "verdict": {
      "same": false,
      "differs": [
        "grouping",
        "prefix",
        "separators"
      ]
    }
  },
  {
    "case_id": "long_order-058",
    "repeat": 0,
    "hop": {
      "kind": "IN",
      "owner": "tool",
      "item_id": "i5",
      "hop_index": 9,
      "turn": 1,
      "tool_name": "crm_find_contact",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": -1,
      "path": "contacts[].email",
      "optional": false
    },
    "declared": true,
    "pii_type": "EMAIL",
    "produced": "teywsrsv@example.ru",
    "reference": "vasilev76@bk.ru",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "long_order-058",
    "repeat": 0,
    "hop": {
      "kind": "IN",
      "owner": "tool",
      "item_id": "i6",
      "hop_index": 10,
      "turn": 1,
      "tool_name": "crm_find_contact",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": -1,
      "path": "contacts[].birth_date",
      "optional": false
    },
    "declared": true,
    "pii_type": "DOB",
    "produced": "1982-06-16",
    "reference": "1982-08-12",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "long_order-058",
    "repeat": 0,
    "hop": {
      "kind": "IN",
      "owner": "tool",
      "item_id": "i7",
      "hop_index": 11,
      "turn": 1,
      "tool_name": "crm_find_contact",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": -1,
      "path": "contacts[].address.street",
      "optional": false
    },
    "declared": true,
    "pii_type": "LOC",
    "produced": "сосновая",
    "reference": "кирова",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "long_order-058",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i8",
      "hop_index": 14,
      "turn": 7,
      "tool_name": "delivery_create_order",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": 0,
      "path": "recipient.name",
      "optional": false
    },
    "declared": true,
    "pii_type": "NAME",
    "produced": "",
    "reference": "",
    "status": "absent",
    "verdict": null
  },
  {
    "case_id": "long_order-058",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i9",
      "hop_index": 15,
      "turn": 7,
      "tool_name": "delivery_create_order",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": 1,
      "path": "recipient.phones[].number",
      "optional": false
    },
    "declared": true,
    "pii_type": "PHONE",
    "produced": "",
    "reference": "",
    "status": "absent",
    "verdict": null
  },
  {
    "case_id": "long_order-058",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i10",
      "hop_index": 16,
      "turn": 7,
      "tool_name": "delivery_create_order",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": 2,
      "path": "to_location.city",
      "optional": false
    },
    "declared": true,
    "pii_type": "LOC",
    "produced": "",
    "reference": "",
    "status": "absent",
    "verdict": null
  },
  {
    "case_id": "long_order-058",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i10",
      "hop_index": 17,
      "turn": 7,
      "tool_name": "delivery_create_order",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": 2,
      "path": "to_location.address",
      "optional": false
    },
    "declared": true,
    "pii_type": "LOC",
    "produced": "",
    "reference": "",
    "status": "absent",
    "verdict": null
  },
  {
    "case_id": "long_order-058",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i9",
      "hop_index": 18,
      "turn": 7,
      "tool_name": "notify_sms",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": 1,
      "path": "number",
      "optional": false
    },
    "declared": true,
    "pii_type": "PHONE",
    "produced": "+79889990949",
    "reference": "+79908072770",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "long_order-058",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "answer",
      "item_id": "i2",
      "hop_index": 20,
      "turn": 7,
      "tool_name": "",
      "call_ordinal": -1,
      "parallel_group": "",
      "source_hop": 6,
      "path": "",
      "optional": true
    },
    "declared": true,
    "pii_type": "NAME",
    "produced": "Иван",
    "reference": "Макар",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "long_order-058",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "answer",
      "item_id": "i3",
      "hop_index": 21,
      "turn": 7,
      "tool_name": "",
      "call_ordinal": -1,
      "parallel_group": "",
      "source_hop": 7,
      "path": "",
      "optional": true
    },
    "declared": true,
    "pii_type": "NAME",
    "produced": "Павлович",
    "reference": "Борисович",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "long_order-058",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "answer",
      "item_id": "i4",
      "hop_index": 22,
      "turn": 7,
      "tool_name": "",
      "call_ordinal": -1,
      "parallel_group": "",
      "source_hop": 8,
      "path": "",
      "optional": true
    },
    "declared": true,
    "pii_type": "PHONE",
    "produced": "8 988 999 09 49",
    "reference": "8 990 807-27-70",
    "status": "observed",
    "verdict": {
      "same": false,
      "differs": [
        "separators"
      ]
    }
  },
  {
    "case_id": "long_order-058",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i4",
      "hop_index": -1,
      "turn": 1,
      "tool_name": "crm_find_contact",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": -1,
      "path": "query.phone",
      "optional": false
    },
    "declared": false,
    "pii_type": "PHONE",
    "produced": "+79889990949",
    "reference": "+79908072770",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "long_order-058",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i11",
      "hop_index": -1,
      "turn": 5,
      "tool_name": "delivery_create_order",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": -1,
      "path": "recipient.name",
      "optional": false
    },
    "declared": false,
    "pii_type": "NAME",
    "produced": "Мамедова Лейла",
    "reference": "Сазонова Таисия",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "long_order-058",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i12",
      "hop_index": -1,
      "turn": 5,
      "tool_name": "delivery_create_order",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": -1,
      "path": "recipient.phones[0].number",
      "optional": false
    },
    "declared": false,
    "pii_type": "PHONE",
    "produced": "+79228231652",
    "reference": "+79431366533",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "long_order-058",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i7",
      "hop_index": -1,
      "turn": 5,
      "tool_name": "delivery_create_order",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": -1,
      "path": "to_location.address",
      "optional": false
    },
    "declared": false,
    "pii_type": "LOC",
    "produced": "Сосновая, 53, кв. 79",
    "reference": "Сосновая, 59, кв. 109",
    "status": "residual",
    "verdict": null
  },
  {
    "case_id": "long_order-058",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "",
      "hop_index": -1,
      "turn": 5,
      "tool_name": "delivery_create_order",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": -1,
      "path": "to_location.city",
      "optional": false
    },
    "declared": false,
    "pii_type": "LOC",
    "produced": "Краснодар",
    "reference": "Краснодар",
    "status": "unmasked",
    "verdict": null
  },
  {
    "case_id": "long_order-058",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "answer",
      "item_id": "i9",
      "hop_index": -1,
      "turn": -1,
      "tool_name": "",
      "call_ordinal": -1,
      "parallel_group": "",
      "source_hop": -1,
      "path": "",
      "optional": false
    },
    "declared": false,
    "pii_type": "PHONE",
    "produced": "8 988 999 09 49",
    "reference": "8 990 807-27-70",
    "status": "observed",
    "verdict": {
      "same": false,
      "differs": [
        "separators"
      ]
    }
  },
  {
    "case_id": "long_order-058",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "answer",
      "item_id": "i11",
      "hop_index": -1,
      "turn": -1,
      "tool_name": "",
      "call_ordinal": -1,
      "parallel_group": "",
      "source_hop": -1,
      "path": "",
      "optional": false
    },
    "declared": false,
    "pii_type": "NAME",
    "produced": "Мамедова Лейла",
    "reference": "Сазонова Таисия",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "long_order-058",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "answer",
      "item_id": "i8",
      "hop_index": -1,
      "turn": -1,
      "tool_name": "",
      "call_ordinal": -1,
      "parallel_group": "",
      "source_hop": -1,
      "path": "",
      "optional": false
    },
    "declared": false,
    "pii_type": "NAME",
    "produced": "Иван Павлович",
    "reference": "Макар Борисович",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  }
]
