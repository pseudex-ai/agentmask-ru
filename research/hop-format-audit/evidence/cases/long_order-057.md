# long_order-057 | source A | repeat 0

Synthetic benchmark evidence. Verbatim serialized fields; no inferred verdicts.

## Case specification

{
  "base": {
    "id": "long_order-057",
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
    "cluster": "PHONE:9279030877",
    "conversation_id": "",
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
        "content": "это васильев иван хочу отправить посылку телефон 8-927-903-08-77 а также к 9 часам",
        "source": null,
        "name": ""
      },
      {
        "role": "user",
        "content": "везите на краснодар переулок дзержинского 177кв235 коробка 2 килограмма",
        "source": null,
        "name": ""
      },
      {
        "role": "user",
        "content": "посчитайте сколько это стоит",
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
        "content": "получит не я а ким виктор его телефон 89260742978",
        "source": null,
        "name": ""
      },
      {
        "role": "user",
        "content": "лучше десятого сентября",
        "source": null,
        "name": ""
      },
      {
        "role": "user",
        "content": "смс отправьте мне пожалуйста на мой телефон",
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
          "phone": "+79279030877",
          "email": "vasilev91@list.ru",
          "birth_date": "1991-06-04",
          "address": {
            "city": "краснодар",
            "street": "дзержинского",
            "house": "177",
            "flat": "235"
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
        "identity": "p57",
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
        "identity": "p57",
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
        "identity": "p57",
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
        "identity": "p57",
        "value": "+79279030877",
        "canonical": "+79279030877",
        "parts": {
          "digits": "9279030877"
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
        "identity": "p57",
        "value": "vasilev91@list.ru",
        "canonical": "vasilev91@list.ru",
        "parts": {
          "local": "vasilev91",
          "domain": "list.ru"
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
        "identity": "p57",
        "value": "1991-06-04",
        "canonical": "1991-06-04",
        "parts": {
          "iso": "1991-06-04"
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
        "identity": "p57.home",
        "value": "дзержинского",
        "canonical": "дзержинского",
        "parts": {
          "street": "дзержинского",
          "street_type": "переулок",
          "house": "177",
          "flat": "235",
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
        "identity": "p57",
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
          "start": 4,
          "end": 17,
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
        "identity": "p57",
        "value": "8-927-903-08-77",
        "canonical": "+79279030877",
        "parts": {
          "digits": "9279030877"
        },
        "where": {
          "kind": "message",
          "msg": 1,
          "start": 49,
          "end": 64,
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
        "identity": "p57.home",
        "value": "краснодар переулок дзержинского 177кв235",
        "canonical": "краснодар переулок дзержинского 177кв235",
        "parts": {
          "street": "дзержинского",
          "street_type": "переулок",
          "house": "177",
          "flat": "235",
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
        "identity": "p57r",
        "value": "ким виктор",
        "canonical": "ким виктор",
        "parts": {
          "surname": "ким",
          "given": "виктор",
          "gender": "m"
        },
        "where": {
          "kind": "message",
          "msg": 5,
          "start": 15,
          "end": 25,
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
        "identity": "p57r",
        "value": "89260742978",
        "canonical": "+79260742978",
        "parts": {
          "digits": "9260742978"
        },
        "where": {
          "kind": "message",
          "msg": 5,
          "start": 38,
          "end": 49,
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
        "value": "2",
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
        "value": "9 часам",
        "start": 75,
        "end": 82,
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
        "order_reschedule",
        "crm_add_note"
      ],
      "primary_identity": "p57",
      "must_contain": [],
      "must_not_contain": [],
      "validate_types": []
    },
    "trace": [
      {
        "msg": 1,
        "key": "",
        "start": 0,
        "end": 3,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 1,
        "key": "",
        "start": 3,
        "end": 4,
        "origin": "literal"
      },
      {
        "msg": 1,
        "key": "n1",
        "start": 4,
        "end": 17,
        "origin": "value:n1"
      },
      {
        "msg": 1,
        "key": "",
        "start": 17,
        "end": 18,
        "origin": "literal"
      },
      {
        "msg": 1,
        "key": "",
        "start": 18,
        "end": 22,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 1,
        "key": "",
        "start": 22,
        "end": 23,
        "origin": "literal"
      },
      {
        "msg": 1,
        "key": "",
        "start": 23,
        "end": 32,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 1,
        "key": "",
        "start": 32,
        "end": 33,
        "origin": "literal"
      },
      {
        "msg": 1,
        "key": "",
        "start": 33,
        "end": 40,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 1,
        "key": "",
        "start": 40,
        "end": 41,
        "origin": "literal"
      },
      {
        "msg": 1,
        "key": "",
        "start": 41,
        "end": 48,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 1,
        "key": "",
        "start": 48,
        "end": 49,
        "origin": "literal"
      },
      {
        "msg": 1,
        "key": "ph1",
        "start": 49,
        "end": 64,
        "origin": "value:ph1"
      },
      {
        "msg": 1,
        "key": "",
        "start": 64,
        "end": 65,
        "origin": "literal"
      },
      {
        "msg": 1,
        "key": "",
        "start": 65,
        "end": 66,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 1,
        "key": "",
        "start": 66,
        "end": 67,
        "origin": "literal"
      },
      {
        "msg": 1,
        "key": "",
        "start": 67,
        "end": 72,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 1,
        "key": "",
        "start": 72,
        "end": 73,
        "origin": "literal"
      },
      {
        "msg": 1,
        "key": "",
        "start": 73,
        "end": 74,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 1,
        "key": "",
        "start": 74,
        "end": 75,
        "origin": "literal"
      },
      {
        "msg": 1,
        "key": "neg1",
        "start": 75,
        "end": 82,
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
        "end": 10,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 3,
        "key": "",
        "start": 10,
        "end": 11,
        "origin": "literal"
      },
      {
        "msg": 3,
        "key": "",
        "start": 11,
        "end": 18,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 3,
        "key": "",
        "start": 18,
        "end": 19,
        "origin": "literal"
      },
      {
        "msg": 3,
        "key": "",
        "start": 19,
        "end": 22,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 3,
        "key": "",
        "start": 22,
        "end": 23,
        "origin": "literal"
      },
      {
        "msg": 3,
        "key": "",
        "start": 23,
        "end": 28,
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
        "end": 25,
        "origin": "value:n2"
      },
      {
        "msg": 5,
        "key": "",
        "start": 25,
        "end": 26,
        "origin": "literal"
      },
      {
        "msg": 5,
        "key": "",
        "start": 26,
        "end": 29,
        "origin": "chunk:noisy_word"
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
        "end": 37,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 5,
        "key": "",
        "start": 37,
        "end": 38,
        "origin": "literal"
      },
      {
        "msg": 5,
        "key": "ph2",
        "start": 38,
        "end": 49,
        "origin": "value:ph2"
      },
      {
        "msg": 6,
        "key": "",
        "start": 0,
        "end": 5,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 6,
        "key": "",
        "start": 5,
        "end": 6,
        "origin": "literal"
      },
      {
        "msg": 6,
        "key": "",
        "start": 6,
        "end": 14,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 6,
        "key": "",
        "start": 14,
        "end": 15,
        "origin": "literal"
      },
      {
        "msg": 6,
        "key": "",
        "start": 15,
        "end": 23,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 7,
        "key": "",
        "start": 0,
        "end": 3,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 7,
        "key": "",
        "start": 3,
        "end": 4,
        "origin": "literal"
      },
      {
        "msg": 7,
        "key": "",
        "start": 4,
        "end": 13,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 7,
        "key": "",
        "start": 13,
        "end": 14,
        "origin": "literal"
      },
      {
        "msg": 7,
        "key": "",
        "start": 14,
        "end": 17,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 7,
        "key": "",
        "start": 17,
        "end": 18,
        "origin": "literal"
      },
      {
        "msg": 7,
        "key": "",
        "start": 18,
        "end": 28,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 7,
        "key": "",
        "start": 28,
        "end": 29,
        "origin": "literal"
      },
      {
        "msg": 7,
        "key": "",
        "start": 29,
        "end": 31,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 7,
        "key": "",
        "start": 31,
        "end": 32,
        "origin": "literal"
      },
      {
        "msg": 7,
        "key": "",
        "start": 32,
        "end": 35,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 7,
        "key": "",
        "start": 35,
        "end": 36,
        "origin": "literal"
      },
      {
        "msg": 7,
        "key": "",
        "start": 36,
        "end": 43,
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
    "case_id": "long_order-057",
    "arm": "I",
    "repeat": 0,
    "calls": [
      {
        "name": "crm_find_contact",
        "written": {
          "query": {
            "last_name": "Юдин"
          }
        },
        "restored": {
          "query": {
            "last_name": "Васильев"
          }
        },
        "residual": {},
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "query": {
            "last_name": "васильев"
          }
        },
        "seq": 1
      },
      {
        "name": "delivery_quote",
        "written": {
          "city": "Краснодар",
          "weight": 2000
        },
        "restored": {
          "city": "Краснодар",
          "weight": 2000
        },
        "residual": {},
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "city": "краснодар",
          "weight": 2000
        },
        "seq": 2
      },
      {
        "name": "delivery_create_order",
        "written": {
          "packages": [
            {
              "weight": 2000
            }
          ],
          "recipient": {
            "name": "Чижов Константин",
            "phones": [
              {
                "number": "+79025358847"
              }
            ]
          },
          "to_location": {
            "address": "переулок Луговая, д. 116, кв. 93",
            "city": "Краснодар",
            "postal_code": "350000"
          }
        },
        "restored": {
          "packages": [
            {
              "weight": 2000
            }
          ],
          "recipient": {
            "name": "Ким Виктор",
            "phones": [
              {
                "number": "+79260742978"
              }
            ]
          },
          "to_location": {
            "address": "переулок Луговая, д. 177, кв. 235",
            "city": "Краснодар",
            "postal_code": "350000"
          }
        },
        "residual": {
          "to_location.address": [
            "луговая"
          ]
        },
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "comment": "",
          "packages": [
            {
              "weight": 2000
            }
          ],
          "recipient": {
            "name": "Ким Виктор",
            "phones": [
              "+79260742978"
            ]
          },
          "to_location": {
            "address": "переулок Луговая, д. 177, кв. 235",
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
        "name": "courier_book",
        "written": {
          "address": {
            "building": "116",
            "locality": "Краснодар",
            "sflat": "93",
            "street": "Луговая"
          },
          "contact": {
            "name": "Юдин Лев Максимович",
            "phone": "+79444477144"
          },
          "interval": {
            "from": "2026-09-10T09:00:00+03:00",
            "to": "2026-09-10T10:00:00+03:00"
          }
        },
        "restored": {
          "address": {
            "building": "177",
            "locality": "Краснодар",
            "sflat": "235",
            "street": "Дзержинского"
          },
          "contact": {
            "name": "Васильев Иван Павлович",
            "phone": "+79279030877"
          },
          "interval": {
            "from": "2026-09-10T09:00:00+03:00",
            "to": "2026-09-10T10:00:00+03:00"
          }
        },
        "residual": {},
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "address": {
            "building": "177",
            "locality": "краснодар",
            "porch": "",
            "sflat": "235",
            "street": "дзержинского"
          },
          "contact": {
            "name": "Васильев Иван Павлович",
            "phone": "+79279030877"
          },
          "interval": {
            "from": "2026-09-10T09:00:00+03:00",
            "to": "2026-09-10T10:00:00+03:00"
          }
        },
        "seq": 5
      },
      {
        "name": "crm_add_note",
        "written": {
          "entity_id": "c-1",
          "note_type": "call_in",
          "text": "Клиент Юдин Лев хочет отправить посылку 2 кг в Краснодар получателю Чижову Константину, тел. +79025358847. Оформлен заказ ord-1 (440 ₽, ~2 дня). ВНИМАНИЕ: в заказе адрес записался как «переулок Рябиновый, д. 195, кв. 211», хотя клиент называл «Луговая, 116, кв. 93» — требует уточнения/исправления. Вызван курьер clm-1 на 10.09.2026, окно 09:00–10:00, адрес забора: Краснодар, ул. Луговая, 116, кв. 93, контакт Юдин Лев +79444477144."
        },
        "restored": {
          "entity_id": "c-1",
          "note_type": "call_in",
          "text": "Клиент Васильев Иван хочет отправить посылку 2 кг в Краснодар получателю Киму Виктору, тел. +79260742978. Оформлен заказ ord-1 (440 ₽, ~2 дня). ВНИМАНИЕ: в заказе адрес записался как «переулок Луговая, д. 177, кв. 235», хотя клиент называл «Луговая, 177, кв. 235» — требует уточнения/исправления. Вызван курьер clm-1 на 10.09.2026, окно 09:00–10:00, адрес забора: Краснодар, ул. Луговая, 177, кв. 235, контакт Васильев Иван +79279030877."
        },
        "residual": {
          "text": [
            "луговая"
          ]
        },
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "entity_id": "c-1",
          "note_type": "call_in",
          "text": "Клиент Васильев Иван хочет отправить посылку 2 кг в Краснодар получателю Киму Виктору, тел. +79260742978. Оформлен заказ ord-1 (440 ₽, ~2 дня). ВНИМАНИЕ: в заказе адрес записался как «переулок Луговая, д. 177, кв. 235», хотя клиент называл «Луговая, 177, кв. 235» — требует уточнения/исправления. Вызван курьер clm-1 на 10.09.2026, окно 09:00–10:00, адрес забора: Краснодар, ул. Луговая, 177, кв. 235, контакт Васильев Иван +79279030877."
        },
        "seq": 6
      },
      {
        "name": "notify_sms",
        "written": {
          "number": "+79444477144",
          "sign": "Dostavka",
          "text": "Заказ ord-1: посылка 2 кг в Краснодар получателю Чижов Константин (+79025358847), 440 руб., срок ~2 дня. Курьер приедет 10.09.2026 с 09:00 до 10:00 по адресу: Краснодар, ул. Луговая, д. 116, кв. 93. Юдин Лев, спасибо за обращение!"
        },
        "restored": {
          "number": "+79279030877",
          "sign": "Dostavka",
          "text": "Заказ ord-1: посылка 2 кг в Краснодар получателю Ким Виктор (+79260742978), 440 руб., срок ~2 дня. Курьер приедет 10.09.2026 с 09:00 до 10:00 по адресу: Краснодар, ул. Луговая, д. 177, кв. 235. Васильев Иван, спасибо за обращение!"
        },
        "residual": {
          "text": [
            "луговая"
          ]
        },
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "number": "+79279030877",
          "sign": "Dostavka",
          "text": "Заказ ord-1: посылка 2 кг в Краснодар получателю Ким Виктор (+79260742978), 440 руб., срок ~2 дня. Курьер приедет 10.09.2026 с 09:00 до 10:00 по адресу: Краснодар, ул. Луговая, д. 177, кв. 235. Васильев Иван, спасибо за обращение!"
        },
        "seq": 7
      }
    ],
    "state": [
      {
        "fields": {
          "comment": "",
          "packages": [
            {
              "weight": 2000
            }
          ],
          "recipient": {
            "name": "Ким Виктор",
            "phones": [
              "+79260742978"
            ]
          },
          "to_location": {
            "address": "переулок Луговая, д. 177, кв. 235",
            "city": "краснодар",
            "postal_code": "350000"
          }
        },
        "id": "ord-1",
        "seq": 3,
        "table": "orders",
        "tool": "delivery_create_order"
      },
      {
        "fields": {
          "address": {
            "building": "177",
            "locality": "краснодар",
            "porch": "",
            "sflat": "235",
            "street": "дзержинского"
          },
          "contact": {
            "name": "Васильев Иван Павлович",
            "phone": "+79279030877"
          },
          "interval": {
            "from": "2026-09-10T09:00:00+03:00",
            "to": "2026-09-10T10:00:00+03:00"
          }
        },
        "id": "clm-1",
        "seq": 5,
        "table": "claims",
        "tool": "courier_book"
      },
      {
        "fields": {
          "entity_id": "c-1",
          "note_type": "call_in",
          "text": "Клиент Васильев Иван хочет отправить посылку 2 кг в Краснодар получателю Киму Виктору, тел. +79260742978. Оформлен заказ ord-1 (440 ₽, ~2 дня). ВНИМАНИЕ: в заказе адрес записался как «переулок Луговая, д. 177, кв. 235», хотя клиент называл «Луговая, 177, кв. 235» — требует уточнения/исправления. Вызван курьер clm-1 на 10.09.2026, окно 09:00–10:00, адрес забора: Краснодар, ул. Луговая, 177, кв. 235, контакт Васильев Иван +79279030877."
        },
        "id": "note-1",
        "seq": 6,
        "table": "notes",
        "tool": "crm_add_note"
      },
      {
        "fields": {
          "number": "+79279030877",
          "sign": "Dostavka",
          "text": "Заказ ord-1: посылка 2 кг в Краснодар получателю Ким Виктор (+79260742978), 440 руб., срок ~2 дня. Курьер приедет 10.09.2026 с 09:00 до 10:00 по адресу: Краснодар, ул. Луговая, д. 177, кв. 235. Васильев Иван, спасибо за обращение!"
        },
        "id": "sms-1",
        "seq": 7,
        "table": "sms",
        "tool": "notify_sms"
      }
    ],
    "reply": "СМС отправлена на ваш номер **8-927-903-08-77** ✅\n\nТекст: заказ ord-1 (посылка 2 кг, 440 ₽, ~2 дня, получатель Ким Виктор) и вызов курьера на 10.09.2026, 09:00–10:00 по адресу Краснодар, ул. Луговая, д. 177, кв. 235.\n\nОстаются два вопроса, которые стоит закрыть:\n1. **Адрес заказа** — исправляем на «Луговая, 177, кв. 235» (отменю ord-1 и оформлю заново) или оставляем «Рябиновый, 195, кв. 235»?\n2. **Отчество** — Павлович или Павлович?",
    "termination": "done",
    "cost_usd": 0.020172,
    "substitutes": {
      "i1": [
        "юдин",
        {
          "surname": "юдин"
        }
      ],
      "i10": [
        "краснодар переулок луговая 116кв93",
        {
          "flat": "93",
          "house": "116",
          "street": "краснодар луговая"
        }
      ],
      "i11": [
        "чижов константин",
        {
          "given": "константин",
          "surname": "чижов"
        }
      ],
      "i12": [
        "89025358847",
        {
          "digits": "9025358847"
        }
      ],
      "i2": [
        "лев",
        {
          "given": "лев"
        }
      ],
      "i3": [
        "максимович",
        {
          "patronymic": "максимович"
        }
      ],
      "i4": [
        "8-944-447-71-44",
        {
          "digits": "9444477144"
        }
      ],
      "i5": [
        "wfkfarul@example.ru",
        {
          "domain": "example.ru",
          "local": "wfkfarul"
        }
      ],
      "i6": [
        "1991-06-09",
        {
          "iso": "1991-06-09"
        }
      ],
      "i7": [
        "луговая",
        {
          "street": "луговая"
        }
      ],
      "i8": [
        "юдин лев",
        {
          "given": "лев",
          "surname": "юдин"
        }
      ],
      "i9": [
        "8-944-447-71-44",
        {
          "digits": "9444477144"
        }
      ]
    },
    "masked_spans": {
      "0": [],
      "1": [
        [
          4,
          17
        ],
        [
          49,
          64
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
          25
        ],
        [
          38,
          49
        ]
      ],
      "6": [],
      "7": []
    }
  },
  "reply_raw": "СМС отправлена на ваш номер **+7 944 447-71-44** ✅\n\nТекст: заказ ord-1 (посылка 2 кг, 440 ₽, ~2 дня, получатель Чижов Константин) и вызов курьера на 10.09.2026, 09:00–10:00 по адресу Краснодар, ул. Луговая, д. 116, кв. 93.\n\nОстаются два вопроса, которые стоит закрыть:\n1. **Адрес заказа** — исправляем на «Луговая, 116, кв. 93» (отменю ord-1 и оформлю заново) или оставляем «Рябиновый, 195, кв. 211»?\n2. **Отчество** — Леонидович или Максимович?",
  "control_reply": "СМС отправлено ✅\n\n- **Кому:** +7 927 903-08-77 (ваш номер)\n- **Текст:** заказ ord-1 оформлен — получатель Ким Виктор, Краснодар, пер. Дзержинского 177, кв. 235, вес 2000 г, 440 ₽, срок 2 дня; курьер заберёт посылку 10 сентября с 9:00 до 10:00.\n\nИтог по обращению:\n- Заказ доставки **ord-1** создан.\n- Курьер **clm-1** вызван на 10 сентября, 9:00–10:00, Краснодар, ул. Дзержинского, 177, кв. 235.\n- В карточку клиента добавлена заметка.\n\nЧто-то ещё?",
  "tool_results": [
    {
      "tool_name": "crm_find_contact",
      "seq": 1,
      "call_ordinal": 0,
      "turn": 1,
      "return_form": "list",
      "text_real": "{\n  \"contacts\": [\n    {\n      \"id\": \"c-1\",\n      \"last_name\": \"васильев\",\n      \"first_name\": \"иван\",\n      \"middle_name\": \"павлович\",\n      \"phone\": \"+79279030877\",\n      \"email\": \"vasilev91@list.ru\",\n      \"birth_date\": \"1991-06-04\",\n      \"address\": {\n        \"city\": \"краснодар\",\n        \"street\": \"дзержинского\",\n        \"house\": \"177\",\n        \"flat\": \"235\"\n      }\n    }\n  ]\n}",
      "text_masked": "{\n  \"contacts\": [\n    {\n      \"id\": \"c-1\",\n      \"last_name\": \"юдин\",\n      \"first_name\": \"лев\",\n      \"middle_name\": \"максимович\",\n      \"phone\": \"8-944-447-71-44\",\n      \"email\": \"wfkfarul@example.ru\",\n      \"birth_date\": \"1991-06-09\",\n      \"address\": {\n        \"city\": \"краснодар\",\n        \"street\": \"луговая\",\n        \"house\": \"116\",\n        \"flat\": \"93\"\n      }\n    }\n  ]\n}",
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
          199
        ],
        "i6": [
          223,
          233
        ],
        "i7": [
          303,
          315
        ]
      },
      "pieces": [
        [
          63,
          71,
          "юдин",
          "NAME"
        ],
        [
          95,
          99,
          "лев",
          "NAME"
        ],
        [
          124,
          132,
          "максимович",
          "NAME"
        ],
        [
          151,
          163,
          "8-944-447-71-44",
          "PHONE"
        ],
        [
          182,
          199,
          "wfkfarul@example.ru",
          "EMAIL"
        ],
        [
          223,
          233,
          "1991-06-09",
          "DOB"
        ],
        [
          272,
          281,
          "краснодар",
          "LOC"
        ],
        [
          303,
          315,
          "луговая",
          "LOC"
        ],
        [
          336,
          339,
          "116",
          "LOC"
        ],
        [
          359,
          362,
          "93",
          "LOC"
        ]
      ],
      "forced": false
    },
    {
      "tool_name": "delivery_quote",
      "seq": 2,
      "call_ordinal": 0,
      "turn": 2,
      "return_form": "single",
      "text_real": "{\n  \"city\": \"краснодар\",\n  \"weight\": \"2000\",\n  \"price\": \"440.00\",\n  \"currency\": \"RUB\",\n  \"days\": \"2\",\n  \"pickup_point\": {\n    \"address\": \"\"\n  }\n}",
      "text_masked": "{\n  \"city\": \"краснодар\",\n  \"weight\": \"2000\",\n  \"price\": \"440.00\",\n  \"currency\": \"RUB\",\n  \"days\": \"2\",\n  \"pickup_point\": {\n    \"address\": \"\"\n  }\n}",
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
      "text_real": "{\n  \"uuid\": \"ord-1\",\n  \"status\": \"ACCEPTED\",\n  \"recipient\": {\n    \"name\": \"Ким Виктор\",\n    \"phone\": \"+79260742978\"\n  },\n  \"to_location\": {\n    \"postal_code\": \"350000\",\n    \"city\": \"краснодар\",\n    \"address\": \"переулок Луговая, д. 177, кв. 235\"\n  }\n}",
      "text_masked": "{\n  \"uuid\": \"ord-1\",\n  \"status\": \"ACCEPTED\",\n  \"recipient\": {\n    \"name\": \"Чижов Константин\",\n    \"phone\": \"89025358847\"\n  },\n  \"to_location\": {\n    \"postal_code\": \"350000\",\n    \"city\": \"краснодар\",\n    \"address\": \"переулок Рябиновый, д. 195, кв. 211\"\n  }\n}",
      "spans_real": {},
      "pieces": [
        [
          75,
          85,
          "Чижов Константин",
          "NAME"
        ],
        [
          102,
          114,
          "89025358847",
          "PHONE"
        ],
        [
          210,
          243,
          "переулок Рябиновый, д. 195, кв. 211",
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
      "text_real": "{\n  \"uuid\": \"ord-1\",\n  \"status\": \"ACCEPTED\",\n  \"date\": \"\",\n  \"recipient\": {\n    \"name\": \"Ким Виктор\",\n    \"phone\": \"+79260742978\"\n  },\n  \"to_location\": {\n    \"city\": \"краснодар\",\n    \"address\": \"переулок Луговая, д. 177, кв. 235\"\n  }\n}",
      "text_masked": "{\n  \"uuid\": \"ord-1\",\n  \"status\": \"ACCEPTED\",\n  \"date\": \"\",\n  \"recipient\": {\n    \"name\": \"Чижов Константин\",\n    \"phone\": \"89025358847\"\n  },\n  \"to_location\": {\n    \"city\": \"краснодар\",\n    \"address\": \"переулок Рябиновый, д. 195, кв. 211\"\n  }\n}",
      "spans_real": {},
      "pieces": [
        [
          89,
          99,
          "Чижов Константин",
          "NAME"
        ],
        [
          116,
          128,
          "89025358847",
          "PHONE"
        ],
        [
          195,
          228,
          "переулок Рябиновый, д. 195, кв. 211",
          "LOC"
        ]
      ],
      "forced": false
    },
    {
      "tool_name": "courier_book",
      "seq": 5,
      "call_ordinal": 0,
      "turn": 6,
      "return_form": "nested",
      "text_real": "{\n  \"claim_id\": \"clm-1\",\n  \"status\": \"estimating\",\n  \"contact\": {\n    \"name\": \"Васильев Иван Павлович\",\n    \"phone\": \"+79279030877\"\n  },\n  \"address\": \"г. Краснодар, ул. Дзержинского, д. 177, кв. 235\"\n}",
      "text_masked": "{\n  \"claim_id\": \"clm-1\",\n  \"status\": \"estimating\",\n  \"contact\": {\n    \"name\": \"Юдин Лев Леонидович\",\n    \"phone\": \"8-944-447-71-44\"\n  },\n  \"address\": \"г. Краснодар, ул. Луговая, д. 116, кв. 93\"\n}",
      "spans_real": {
        "i4": [
          118,
          130
        ],
        "i7": [
          169,
          181
        ]
      },
      "pieces": [
        [
          79,
          101,
          "Юдин Лев Леонидович",
          "NAME"
        ],
        [
          118,
          130,
          "8-944-447-71-44",
          "PHONE"
        ],
        [
          151,
          198,
          "г. Краснодар, ул. Луговая, д. 116, кв. 93",
          "LOC"
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
      "text_real": "{\n  \"id\": \"note-1\",\n  \"entity_id\": \"c-1\",\n  \"length\": 437,\n  \"entity\": {\n    \"last_name\": \"васильев\",\n    \"first_name\": \"иван\",\n    \"phone\": \"+79279030877\"\n  }\n}",
      "text_masked": "{\n  \"id\": \"note-1\",\n  \"entity_id\": \"c-1\",\n  \"length\": 437,\n  \"entity\": {\n    \"last_name\": \"юдин\",\n    \"first_name\": \"лев\",\n    \"phone\": \"8-944-447-71-44\"\n  }\n}",
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
          "юдин",
          "NAME"
        ],
        [
          121,
          125,
          "лев",
          "NAME"
        ],
        [
          142,
          154,
          "8-944-447-71-44",
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
      "text_real": "{\n  \"id\": \"sms-1\",\n  \"status\": \"queued\",\n  \"number\": \"+79279030877\"\n}",
      "text_masked": "{\n  \"id\": \"sms-1\",\n  \"status\": \"queued\",\n  \"number\": \"8-944-447-71-44\"\n}",
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
          "8-944-447-71-44",
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
      "substitute": "юдин лев",
      "request_index": 1
    },
    {
      "item_id": "i9",
      "msg": 1,
      "result_seq": -1,
      "substitute": "8-944-447-71-44",
      "request_index": 1
    },
    {
      "item_id": "i1",
      "msg": -1,
      "result_seq": 1,
      "substitute": "юдин",
      "request_index": 2
    },
    {
      "item_id": "i2",
      "msg": -1,
      "result_seq": 1,
      "substitute": "лев",
      "request_index": 2
    },
    {
      "item_id": "i3",
      "msg": -1,
      "result_seq": 1,
      "substitute": "максимович",
      "request_index": 2
    },
    {
      "item_id": "i4",
      "msg": -1,
      "result_seq": 1,
      "substitute": "8-944-447-71-44",
      "request_index": 2
    },
    {
      "item_id": "i5",
      "msg": -1,
      "result_seq": 1,
      "substitute": "wfkfarul@example.ru",
      "request_index": 2
    },
    {
      "item_id": "i6",
      "msg": -1,
      "result_seq": 1,
      "substitute": "1991-06-09",
      "request_index": 2
    },
    {
      "item_id": "i7",
      "msg": -1,
      "result_seq": 1,
      "substitute": "луговая",
      "request_index": 2
    },
    {
      "item_id": "i10",
      "msg": 2,
      "result_seq": -1,
      "substitute": "краснодар переулок луговая 116кв93",
      "request_index": 3
    },
    {
      "item_id": "i11",
      "msg": 5,
      "result_seq": -1,
      "substitute": "чижов константин",
      "request_index": 7
    },
    {
      "item_id": "i12",
      "msg": 5,
      "result_seq": -1,
      "substitute": "89025358847",
      "request_index": 7
    },
    {
      "item_id": "i4",
      "msg": -1,
      "result_seq": 5,
      "substitute": "8-944-447-71-44",
      "request_index": 11
    },
    {
      "item_id": "i7",
      "msg": -1,
      "result_seq": 5,
      "substitute": "г. Краснодар, ул. Луговая, д. 116, кв. 93",
      "request_index": 11
    },
    {
      "item_id": "i1",
      "msg": -1,
      "result_seq": 6,
      "substitute": "юдин",
      "request_index": 12
    },
    {
      "item_id": "i2",
      "msg": -1,
      "result_seq": 6,
      "substitute": "лев",
      "request_index": 12
    },
    {
      "item_id": "i4",
      "msg": -1,
      "result_seq": 6,
      "substitute": "8-944-447-71-44",
      "request_index": 12
    },
    {
      "item_id": "i4",
      "msg": -1,
      "result_seq": 7,
      "substitute": "8-944-447-71-44",
      "request_index": 14
    }
  ],
  "turn_replies": [
    "Нашёл вашу карточку в CRM: Васильев Иван Павлович, Краснодар, ул. Луговая, д. 177, кв. 235.\n\nЧтобы оформить отправку посылки и вызвать курьера, мне не хватает пары деталей:\n\n1. **Куда отправляем** — город и адрес получателя (улица, дом, квартира), а также ФИО и телефон получателя. Индекс подберу сам по городу.\n2. **Вес посылки** — если не знаете, поставлю по умолчанию 1000 г.\n3. **«К 9 часам»** — вы имеете в виду, что курьер должен приехать к вам на Логовую, 177 сегодня к 09:00 за посылкой? Уточните, пожалуйста, время (интервал) и день.",
    "Посчитал доставку 2 кг в Краснодар: **440 ₽**, срок ~2 дня.\n\nОсталось уточнить пару моментов, без них заказ не оформлю:\n\n1. **Кому посылка** — ФИО и телефон получателя. Адрес вы назвали: Краснодар, переулок Луговая, д. 177, кв. 235 (заметьте, это тот же адрес, что и ваш — улица/переулок Луговая, 177, кв. 235; подтвердите, что всё верно).\n2. **Про «к 9 часам»** — нужно, чтобы курьер приехал к вам за посылкой к 09:00? На какой день — сегодня, 2 сентября?",
    "Стоимость доставки коробки 2 кг в Краснодар — **440 ₽** (срок ~2 дня).\n\nЧтобы оформить заказ, всё ещё нужны:\n1. **ФИО и телефон получателя** — кому везём.\n2. Подтверждение адреса: Краснодар, переулок Луговая, д. 177, кв. 235.\n3. Про «к 9 часам» — курьеру приехать к вам за посылкой к 09:00 сегодня?",
    "Пока не хватает данных для оформления — не могу создать заказ без получателя. Подскажите:\n\n1. **ФИО получателя**\n2. **Телефон получателя**\n\nОстальное у меня есть: Краснодар, переулок Луговая, д. 177, кв. 235; вес 2 кг; стоимость 440 ₽.",
    "Заказ создан, но обратите внимание на важное расхождение:\n\n**Заказ ord-1**\n- Получатель: Ким Виктор, 89260742978\n- Вес: 2 кг, стоимость 440 ₽, срок ~2 дня\n- Адрес в системе: **Краснодар, переулок Луговая, д. 177, кв. 235**\n\n⚠️ Это **не тот адрес**, который вы называли (Краснодар, переулок Луговая, д. 177, кв. 235). В заказ записался другой адрес.\n\nПодскажите, пожалуйста:\n1. Какой адрес верный — Луговая, 177, кв. 235 или Рябиновый, 195, кв. 235? Если верный ваш — отменю заказ и оформлю заново.\n2. По поводу «к 9 часам» — нужно вызвать курьера за посылкой к вам (Луговая, 177, кв. 235) к 09:00? На сегодня, 2 сентября?",
    "Готово. Вот итог:\n\n**🚚 Вызов курьера (забор посылки)**\n- Заявка: clm-1 (в обработке)\n- Адрес: Краснодар, ул. Луговая, д. 177, кв. 235\n- Дата и время: **10 сентября 2026, 09:00–10:00**\n- Контакт: Васильев Иван, 8-927-903-08-77\n\n⚠️ Небольшое расхождение: в заявке на курьера отчество записалось как **Павлович**, а в вашей карточке — **Павлович**. Уточните, какое верно, поправлю.\n\n**📦 Заказ на доставку ord-1**\n- Получатель: Ким Виктор, 89260742978\n- Вес: 2 кг, стоимость 440 ₽, срок ~2 дня\n- Адрес в системе: **Краснодар, переулок Луговая, д. 177, кв. 235**\n\n❗ Этот адрес **не совпадает** с тем, что вы называли (Луговая, 177, кв. 235). Пока не подтвердите, я не могу гарантировать, куда поедет посылка. Скажите — исправляем на «Луговая, 177, кв. 235» (тогда отменю ord-1 и оформлю заново) или оставляем как есть?",
    "СМС отправлена на ваш номер **8-927-903-08-77** ✅\n\nТекст: заказ ord-1 (посылка 2 кг, 440 ₽, ~2 дня, получатель Ким Виктор) и вызов курьера на 10.09.2026, 09:00–10:00 по адресу Краснодар, ул. Луговая, д. 177, кв. 235.\n\nОстаются два вопроса, которые стоит закрыть:\n1. **Адрес заказа** — исправляем на «Луговая, 177, кв. 235» (отменю ord-1 и оформлю заново) или оставляем «Рябиновый, 195, кв. 235»?\n2. **Отчество** — Павлович или Павлович?"
  ],
  "call_turns": [
    1,
    2,
    5,
    5,
    6,
    6,
    7
  ],
  "request_count": 14,
  "stream_mismatch": false,
  "reply_whole": "",
  "turn_residual": 6
}

## Recorded observer hops

[
  {
    "case_id": "long_order-057",
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
    "produced": "юдин лев",
    "reference": "васильев иван",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "long_order-057",
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
    "produced": "8-944-447-71-44",
    "reference": "8-927-903-08-77",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "long_order-057",
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
    "produced": "краснодар переулок луговая 116кв93",
    "reference": "краснодар переулок дзержинского 177кв235",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "long_order-057",
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
    "produced": "чижов константин",
    "reference": "ким виктор",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "long_order-057",
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
    "produced": "89025358847",
    "reference": "89260742978",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "long_order-057",
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
    "produced": "юдин",
    "reference": "васильев",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "long_order-057",
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
    "produced": "лев",
    "reference": "иван",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "long_order-057",
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
    "produced": "максимович",
    "reference": "павлович",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "long_order-057",
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
    "produced": "8-944-447-71-44",
    "reference": "+79279030877",
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
    "case_id": "long_order-057",
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
    "produced": "wfkfarul@example.ru",
    "reference": "vasilev91@list.ru",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "long_order-057",
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
    "produced": "1991-06-09",
    "reference": "1991-06-04",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "long_order-057",
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
    "produced": "луговая",
    "reference": "дзержинского",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "long_order-057",
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
    "case_id": "long_order-057",
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
    "case_id": "long_order-057",
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
    "case_id": "long_order-057",
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
    "case_id": "long_order-057",
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
    "produced": "+79279030877",
    "reference": "+79444477144",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "long_order-057",
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
    "reference": "Максимович",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "long_order-057",
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
    "produced": "8-927-903-08-77",
    "reference": "+7 944 447-71-44",
    "status": "observed",
    "verdict": {
      "same": false,
      "differs": [
        "prefix",
        "separators"
      ]
    }
  },
  {
    "case_id": "long_order-057",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i1",
      "hop_index": -1,
      "turn": 1,
      "tool_name": "crm_find_contact",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": -1,
      "path": "query.last_name",
      "optional": false
    },
    "declared": false,
    "pii_type": "NAME",
    "produced": "Васильев",
    "reference": "Юдин",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "long_order-057",
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
    "produced": "Ким Виктор",
    "reference": "Чижов Константин",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "long_order-057",
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
    "produced": "+79260742978",
    "reference": "+79025358847",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "long_order-057",
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
    "produced": "переулок Луговая, д. 177, кв. 235",
    "reference": "переулок Луговая, д. 116, кв. 93",
    "status": "residual",
    "verdict": null
  },
  {
    "case_id": "long_order-057",
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
    "case_id": "long_order-057",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i7",
      "hop_index": -1,
      "turn": 6,
      "tool_name": "courier_book",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": -1,
      "path": "address.building",
      "optional": false
    },
    "declared": false,
    "pii_type": "LOC",
    "produced": "177",
    "reference": "116",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "long_order-057",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "",
      "hop_index": -1,
      "turn": 6,
      "tool_name": "courier_book",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": -1,
      "path": "address.locality",
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
    "case_id": "long_order-057",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i7",
      "hop_index": -1,
      "turn": 6,
      "tool_name": "courier_book",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": -1,
      "path": "address.sflat",
      "optional": false
    },
    "declared": false,
    "pii_type": "LOC",
    "produced": "235",
    "reference": "93",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "long_order-057",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i7",
      "hop_index": -1,
      "turn": 6,
      "tool_name": "courier_book",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": -1,
      "path": "address.street",
      "optional": false
    },
    "declared": false,
    "pii_type": "LOC",
    "produced": "Дзержинского",
    "reference": "Луговая",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "long_order-057",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i1",
      "hop_index": -1,
      "turn": 6,
      "tool_name": "courier_book",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": -1,
      "path": "contact.name",
      "optional": false
    },
    "declared": false,
    "pii_type": "NAME",
    "produced": "Васильев Иван Павлович",
    "reference": "Юдин Лев Максимович",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "long_order-057",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i4",
      "hop_index": -1,
      "turn": 6,
      "tool_name": "courier_book",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": -1,
      "path": "contact.phone",
      "optional": false
    },
    "declared": false,
    "pii_type": "PHONE",
    "produced": "+79279030877",
    "reference": "+79444477144",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "long_order-057",
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
    "produced": "8-927-903-08-77",
    "reference": "+7 944 447-71-44",
    "status": "observed",
    "verdict": {
      "same": false,
      "differs": [
        "prefix",
        "separators"
      ]
    }
  },
  {
    "case_id": "long_order-057",
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
    "produced": "Ким Виктор",
    "reference": "Чижов Константин",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  }
]
