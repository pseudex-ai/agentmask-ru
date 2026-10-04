# long_order-014 | source A | repeat 0

Synthetic benchmark evidence. Verbatim serialized fields; no inferred verdicts.

## Case specification

{
  "base": {
    "id": "long_order-014",
    "kind": "long_order",
    "register": "voice_raw",
    "provenance": {
      "kind": "template",
      "corpus": "authored",
      "key": "",
      "shape": "",
      "selection": "authored",
      "weight": 1.0,
      "licence": "authored"
    },
    "cluster": "PHONE:9500640017",
    "conversation_id": "conv-long-order-14",
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
        "content": "аа здравствуйте это лебедев максим хочу отправиить посылкуу телефон восемь девятьсот пятьдесят ноль шесть сорок ноль один семь кстати два места",
        "source": null,
        "name": ""
      },
      {
        "role": "user",
        "content": "везитее наа сарапул проспект строительный сорок шесть квартира двести тридцать девять коробка пять килограммаа",
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
        "content": "да давайте оформим",
        "source": null,
        "name": ""
      },
      {
        "role": "user",
        "content": "получит не я а саркисян карен его телефоон восемсь девятьсот двадцать семь девяносто семь тридц один восемьдесят четыре пять",
        "source": null,
        "name": ""
      },
      {
        "role": "user",
        "content": "аа пункты выдачи рядом есть",
        "source": null,
        "name": ""
      },
      {
        "role": "user",
        "content": "смс отправьте мнее пожалуйстаа на мой телефон",
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
          "last_name": "лебедев",
          "first_name": "максим",
          "middle_name": "константинович",
          "phone": "+79500640017",
          "email": "lebedev70@bk.ru",
          "birth_date": "1997-05-05",
          "address": {
            "city": "сарапул",
            "street": "строительный",
            "house": "46",
            "flat": "239"
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
        "identity": "p14",
        "value": "лебедев",
        "canonical": "лебедев",
        "parts": {
          "surname": "лебедев",
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
        "identity": "p14",
        "value": "максим",
        "canonical": "максим",
        "parts": {
          "given": "максим",
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
        "identity": "p14",
        "value": "константинович",
        "canonical": "константинович",
        "parts": {
          "patronymic": "константинович",
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
        "identity": "p14",
        "value": "+79500640017",
        "canonical": "+79500640017",
        "parts": {
          "digits": "9500640017"
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
        "identity": "p14",
        "value": "lebedev70@bk.ru",
        "canonical": "lebedev70@bk.ru",
        "parts": {
          "local": "lebedev70",
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
        "identity": "p14",
        "value": "1997-05-05",
        "canonical": "1997-05-05",
        "parts": {
          "iso": "1997-05-05"
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
        "identity": "p14.home",
        "value": "строительный",
        "canonical": "строительный",
        "parts": {
          "street": "строительный",
          "street_type": "проспект",
          "house": "46",
          "flat": "239",
          "city": "сарапул"
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
        "identity": "p14",
        "value": "лебедев максим",
        "canonical": "лебедев максим",
        "parts": {
          "surname": "лебедев",
          "given": "максим",
          "gender": "m"
        },
        "where": {
          "kind": "message",
          "msg": 1,
          "start": 20,
          "end": 34,
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
        "identity": "p14",
        "value": "восемь девятьсот пятьдесят ноль шесть сорок ноль один семь",
        "canonical": "+79500640017",
        "parts": {
          "digits": "9500640017"
        },
        "where": {
          "kind": "message",
          "msg": 1,
          "start": 68,
          "end": 126,
          "record": "",
          "path": ""
        },
        "duty": "required",
        "spoken": true,
        "stale": false
      },
      {
        "id": "i10",
        "type": "LOC",
        "identity": "p14.home",
        "value": "сарапул проспект строительный сорок шесть квартира двести тридцать девять",
        "canonical": "сарапул проспект строительный сорок шесть квартира двести тридцать девять",
        "parts": {
          "street": "строительный",
          "street_type": "проспект",
          "house": "46",
          "flat": "239",
          "city": "сарапул"
        },
        "where": {
          "kind": "message",
          "msg": 2,
          "start": 12,
          "end": 85,
          "record": "",
          "path": ""
        },
        "duty": "required",
        "spoken": true,
        "stale": false
      },
      {
        "id": "i11",
        "type": "NAME",
        "identity": "p14r",
        "value": "саркисян карен",
        "canonical": "саркисян карен",
        "parts": {
          "surname": "саркисян",
          "given": "карен",
          "gender": "m"
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
        "identity": "p14r",
        "value": "восемсь девятьсот двадцать семь девяносто семь тридц один восемьдесят четыре пять",
        "canonical": "+79279731845",
        "parts": {
          "digits": "9279731845"
        },
        "where": {
          "kind": "message",
          "msg": 5,
          "start": 43,
          "end": 124,
          "record": "",
          "path": ""
        },
        "duty": "required",
        "spoken": true,
        "stale": false
      }
    ],
    "plain": [
      {
        "value": "пять",
        "where": {
          "kind": "message",
          "msg": 2,
          "start": 94,
          "end": 98,
          "record": "",
          "path": ""
        },
        "family": "weight",
        "why": "вес посылки — не персональные данные, обязан дойти как назван"
      }
    ],
    "negatives": [
      {
        "value": "два места",
        "start": 134,
        "end": 143,
        "msg": 1,
        "family": "quantity",
        "why": "числительное с единицей счёта — не номер дома"
      }
    ],
    "expects": {
      "reachable_tools": [
        "crm_find_contact",
        "delivery_quote",
        "delivery_create_order",
        "order_status",
        "notify_sms",
        "pickup_points_near"
      ],
      "primary_identity": "p14",
      "must_contain": [],
      "must_not_contain": [],
      "validate_types": []
    },
    "trace": [
      {
        "msg": 1,
        "key": "",
        "start": 0,
        "end": 2,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 1,
        "key": "",
        "start": 2,
        "end": 3,
        "origin": "literal"
      },
      {
        "msg": 1,
        "key": "",
        "start": 3,
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
        "key": "",
        "start": 16,
        "end": 19,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 1,
        "key": "",
        "start": 19,
        "end": 20,
        "origin": "literal"
      },
      {
        "msg": 1,
        "key": "n1",
        "start": 20,
        "end": 34,
        "origin": "value:n1"
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
        "end": 39,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 1,
        "key": "",
        "start": 39,
        "end": 40,
        "origin": "literal"
      },
      {
        "msg": 1,
        "key": "",
        "start": 40,
        "end": 50,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 1,
        "key": "",
        "start": 50,
        "end": 51,
        "origin": "literal"
      },
      {
        "msg": 1,
        "key": "",
        "start": 51,
        "end": 59,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 1,
        "key": "",
        "start": 59,
        "end": 60,
        "origin": "literal"
      },
      {
        "msg": 1,
        "key": "",
        "start": 60,
        "end": 67,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 1,
        "key": "",
        "start": 67,
        "end": 68,
        "origin": "literal"
      },
      {
        "msg": 1,
        "key": "ph1",
        "start": 68,
        "end": 126,
        "origin": "value:ph1"
      },
      {
        "msg": 1,
        "key": "",
        "start": 126,
        "end": 127,
        "origin": "literal"
      },
      {
        "msg": 1,
        "key": "",
        "start": 127,
        "end": 133,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 1,
        "key": "",
        "start": 133,
        "end": 134,
        "origin": "literal"
      },
      {
        "msg": 1,
        "key": "neg1",
        "start": 134,
        "end": 143,
        "origin": "negative:neg1"
      },
      {
        "msg": 2,
        "key": "",
        "start": 0,
        "end": 7,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 2,
        "key": "",
        "start": 7,
        "end": 8,
        "origin": "literal"
      },
      {
        "msg": 2,
        "key": "",
        "start": 8,
        "end": 11,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 2,
        "key": "",
        "start": 11,
        "end": 12,
        "origin": "literal"
      },
      {
        "msg": 2,
        "key": "a1",
        "start": 12,
        "end": 85,
        "origin": "value:a1"
      },
      {
        "msg": 2,
        "key": "",
        "start": 85,
        "end": 86,
        "origin": "literal"
      },
      {
        "msg": 2,
        "key": "",
        "start": 86,
        "end": 93,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 2,
        "key": "",
        "start": 93,
        "end": 94,
        "origin": "literal"
      },
      {
        "msg": 2,
        "key": "w1",
        "start": 94,
        "end": 98,
        "origin": "plain:w1"
      },
      {
        "msg": 2,
        "key": "",
        "start": 98,
        "end": 99,
        "origin": "literal"
      },
      {
        "msg": 2,
        "key": "",
        "start": 99,
        "end": 110,
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
        "end": 2,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 4,
        "key": "",
        "start": 2,
        "end": 3,
        "origin": "literal"
      },
      {
        "msg": 4,
        "key": "",
        "start": 3,
        "end": 10,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 4,
        "key": "",
        "start": 10,
        "end": 11,
        "origin": "literal"
      },
      {
        "msg": 4,
        "key": "",
        "start": 11,
        "end": 18,
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
        "end": 33,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 5,
        "key": "",
        "start": 33,
        "end": 34,
        "origin": "literal"
      },
      {
        "msg": 5,
        "key": "",
        "start": 34,
        "end": 42,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 5,
        "key": "",
        "start": 42,
        "end": 43,
        "origin": "literal"
      },
      {
        "msg": 5,
        "key": "ph2",
        "start": 43,
        "end": 124,
        "origin": "value:ph2"
      },
      {
        "msg": 6,
        "key": "",
        "start": 0,
        "end": 2,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 6,
        "key": "",
        "start": 2,
        "end": 3,
        "origin": "literal"
      },
      {
        "msg": 6,
        "key": "",
        "start": 3,
        "end": 9,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 6,
        "key": "",
        "start": 9,
        "end": 10,
        "origin": "literal"
      },
      {
        "msg": 6,
        "key": "",
        "start": 10,
        "end": 16,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 6,
        "key": "",
        "start": 16,
        "end": 17,
        "origin": "literal"
      },
      {
        "msg": 6,
        "key": "",
        "start": 17,
        "end": 22,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 6,
        "key": "",
        "start": 22,
        "end": 23,
        "origin": "literal"
      },
      {
        "msg": 6,
        "key": "",
        "start": 23,
        "end": 27,
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
        "end": 30,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 7,
        "key": "",
        "start": 30,
        "end": 31,
        "origin": "literal"
      },
      {
        "msg": 7,
        "key": "",
        "start": 31,
        "end": 33,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 7,
        "key": "",
        "start": 33,
        "end": 34,
        "origin": "literal"
      },
      {
        "msg": 7,
        "key": "",
        "start": 34,
        "end": 37,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 7,
        "key": "",
        "start": 37,
        "end": 38,
        "origin": "literal"
      },
      {
        "msg": 7,
        "key": "",
        "start": 38,
        "end": 45,
        "origin": "chunk:noisy_word"
      }
    ],
    "note": "семь ходов: поиск, расчёт, оформление, поздний получатель, номер заказа из ответа инструмента, перенос или отмена, смс"
  },
  "behaviour": "sequential_chain",
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
      "owner": "tool_arg",
      "item_id": "i7",
      "hop_index": 19,
      "turn": 7,
      "tool_name": "pickup_points_near",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": 11,
      "path": "address",
      "optional": false
    },
    {
      "kind": "OUT",
      "owner": "answer",
      "item_id": "i1",
      "hop_index": 20,
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
      "hop_index": 21,
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
      "hop_index": 22,
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
      "hop_index": 23,
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
      "hop_index": 24,
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
      "hop_index": 25,
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
    "case_id": "long_order-014",
    "arm": "I",
    "repeat": 0,
    "calls": [
      {
        "name": "crm_find_contact",
        "written": {
          "query": {
            "phone": "+79785192099"
          }
        },
        "restored": {
          "query": {
            "phone": "восемь девятьсот пятьдесят ноль шесть сорок ноль один семь"
          }
        },
        "residual": {},
        "refusal_path": "query.phone",
        "refusal_rule": "phone_not_e164",
        "parsed": null,
        "seq": 1
      },
      {
        "name": "crm_find_contact",
        "written": {
          "query": {
            "last_name": "Ершов"
          }
        },
        "restored": {
          "query": {
            "last_name": "Лебедев"
          }
        },
        "residual": {},
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "query": {
            "last_name": "лебедев"
          }
        },
        "seq": 2
      },
      {
        "name": "delivery_quote",
        "written": {
          "city": "Сарапул",
          "weight": 5000
        },
        "restored": {
          "city": "Сарапул",
          "weight": 5000
        },
        "residual": {},
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "city": "сарапул",
          "weight": 5000
        },
        "seq": 3
      },
      {
        "name": "delivery_quote",
        "written": {
          "city": "Сарапул",
          "weight": 10000
        },
        "restored": {
          "city": "Сарапул",
          "weight": 10000
        },
        "residual": {},
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "city": "сарапул",
          "weight": 10000
        },
        "seq": 4
      },
      {
        "name": "pickup_points_near",
        "written": {
          "address": "Сарапул, улица Абрикосовая, 11",
          "limit": 5
        },
        "restored": {
          "address": "Сарапул, улица Абрикосовая, 46",
          "limit": 5
        },
        "residual": {
          "address": [
            "абрикосовая"
          ]
        },
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "address": "Сарапул, улица Абрикосовая, 46",
          "limit": 5
        },
        "seq": 5
      },
      {
        "name": "notify_sms",
        "written": {
          "number": "+79785192099",
          "sign": "Dostavka",
          "text": "Здравствуйте, Мирослав Алексеевич! Оформляем доставку в Сарапул, ул. Абрикосовая, 11, кв. 68. Получатель: Шилов Виктор. Срок доставки — 2 дня. Для завершения нужно подтвердить вес посылки."
        },
        "restored": {
          "number": "+79500640017",
          "sign": "Dostavka",
          "text": "Здравствуйте, Максим Константинович! Оформляем доставку в Сарапул, ул. Абрикосовая, 46, кв. 239. Получатель: Саркисян Карен. Срок доставки — 2 дня. Для завершения нужно подтвердить вес посылки."
        },
        "residual": {
          "text": [
            "абрикосовая"
          ]
        },
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "number": "+79500640017",
          "sign": "Dostavka",
          "text": "Здравствуйте, Максим Константинович! Оформляем доставку в Сарапул, ул. Абрикосовая, 46, кв. 239. Получатель: Саркисян Карен. Срок доставки — 2 дня. Для завершения нужно подтвердить вес посылки."
        },
        "seq": 6
      }
    ],
    "state": [
      {
        "fields": {
          "number": "+79500640017",
          "sign": "Dostavka",
          "text": "Здравствуйте, Максим Константинович! Оформляем доставку в Сарапул, ул. Абрикосовая, 46, кв. 239. Получатель: Саркисян Карен. Срок доставки — 2 дня. Для завершения нужно подтвердить вес посылки."
        },
        "id": "sms-1",
        "seq": 6,
        "table": "sms",
        "tool": "notify_sms"
      }
    ],
    "reply": "СМС отправил на **+79500640017** — итог: доставка в Сарапул, ул. Абрикосовая, 46, кв. 239, получатель Саркисян Карен, срок 2 дня.\n\nОсталось подтвердить вес (**два места по 5 кг = 10 кг?**) — и оформлю заказ.",
    "termination": "done",
    "cost_usd": 0.005582,
    "substitutes": {
      "i1": [
        "ершов",
        {
          "surname": "ершов"
        }
      ],
      "i10": [
        "Сарапул, улица Абрикосовая 11, кв. 68",
        {
          "city": "сарапул",
          "flat": "68",
          "house": "11",
          "street": "абрикосовая"
        }
      ],
      "i11": [
        "шилов виктор",
        {
          "given": "виктор",
          "surname": "шилов"
        }
      ],
      "i12": [
        "+79448919614",
        {
          "digits": "9448919614"
        }
      ],
      "i2": [
        "мирослав",
        {
          "given": "мирослав"
        }
      ],
      "i3": [
        "алексеевич",
        {
          "patronymic": "алексеевич"
        }
      ],
      "i4": [
        "+79785192099",
        {
          "digits": "9785192099"
        }
      ],
      "i5": [
        "hailmrcb@example.ru",
        {
          "domain": "example.ru",
          "local": "hailmrcb"
        }
      ],
      "i6": [
        "1997-04-19",
        {
          "iso": "1997-04-19"
        }
      ],
      "i7": [
        "абрикосовая",
        {
          "street": "абрикосовая"
        }
      ],
      "i8": [
        "ершов мирослав",
        {
          "given": "мирослав",
          "surname": "ершов"
        }
      ],
      "i9": [
        "+79785192099",
        {
          "digits": "9785192099"
        }
      ]
    },
    "masked_spans": {
      "0": [],
      "1": [
        [
          20,
          34
        ],
        [
          68,
          126
        ]
      ],
      "2": [
        [
          12,
          85
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
          43,
          124
        ]
      ],
      "6": [],
      "7": []
    }
  },
  "reply_raw": "СМС отправил на **+79785192099** — итог: доставка в Сарапул, ул. Абрикосовая, 11, кв. 68, получатель Шилов Виктор, срок 2 дня.\n\nОсталось подтвердить вес (**два места по 5 кг = 10 кг?**) — и оформлю заказ.",
  "control_reply": "Отправил СМС на ваш номер **+79500640017** 📱\n\nТекст: заказ **ord-2** — доставка в Сарапул, проспект Строительный, 46, кв. 239; получатель Саркисян Карен, +79279731845; 2 места по 5 кг (10 кг); стоимость 1000 ₽, срок 2 дня; доставка курьером до двери.\n\nЧто-то ещё нужно?",
  "tool_results": [
    {
      "tool_name": "crm_find_contact",
      "seq": 1,
      "call_ordinal": 0,
      "turn": 1,
      "return_form": "error_with_value",
      "text_real": "{\n  \"error\": {\n    \"code\": \"phone_not_e164\",\n    \"field\": \"query.phone\",\n    \"message\": \"поле query.phone: phone_not_e164: восемь девятьсот пятьдесят ноль шесть сорок ноль один семь\"\n  }\n}",
      "text_masked": "{\n  \"error\": {\n    \"code\": \"phone_not_e164\",\n    \"field\": \"query.phone\",\n    \"message\": \"поле query.phone: phone_not_e164: +79785192099\"\n  }\n}",
      "spans_real": {},
      "pieces": [
        [
          123,
          181,
          "+79785192099",
          "PHONE"
        ]
      ],
      "forced": false
    },
    {
      "tool_name": "crm_find_contact",
      "seq": 2,
      "call_ordinal": 1,
      "turn": 1,
      "return_form": "list",
      "text_real": "{\n  \"contacts\": [\n    {\n      \"id\": \"c-1\",\n      \"last_name\": \"лебедев\",\n      \"first_name\": \"максим\",\n      \"middle_name\": \"константинович\",\n      \"phone\": \"+79500640017\",\n      \"email\": \"lebedev70@bk.ru\",\n      \"birth_date\": \"1997-05-05\",\n      \"address\": {\n        \"city\": \"сарапул\",\n        \"street\": \"строительный\",\n        \"house\": \"46\",\n        \"flat\": \"239\"\n      }\n    }\n  ]\n}",
      "text_masked": "{\n  \"contacts\": [\n    {\n      \"id\": \"c-1\",\n      \"last_name\": \"ершов\",\n      \"first_name\": \"мирослав\",\n      \"middle_name\": \"алексеевич\",\n      \"phone\": \"+79785192099\",\n      \"email\": \"hailmrcb@example.ru\",\n      \"birth_date\": \"1997-04-19\",\n      \"address\": {\n        \"city\": \"сарапул\",\n        \"street\": \"абрикосовая\",\n        \"house\": \"11\",\n        \"flat\": \"68\"\n      }\n    }\n  ]\n}",
      "spans_real": {
        "i1": [
          63,
          70
        ],
        "i2": [
          94,
          100
        ],
        "i3": [
          125,
          139
        ],
        "i4": [
          158,
          170
        ],
        "i5": [
          189,
          204
        ],
        "i6": [
          228,
          238
        ],
        "i7": [
          306,
          318
        ]
      },
      "pieces": [
        [
          63,
          70,
          "ершов",
          "NAME"
        ],
        [
          94,
          100,
          "мирослав",
          "NAME"
        ],
        [
          125,
          139,
          "алексеевич",
          "NAME"
        ],
        [
          158,
          170,
          "+79785192099",
          "PHONE"
        ],
        [
          189,
          204,
          "hailmrcb@example.ru",
          "EMAIL"
        ],
        [
          228,
          238,
          "1997-04-19",
          "DOB"
        ],
        [
          277,
          284,
          "сарапул",
          "LOC"
        ],
        [
          306,
          318,
          "абрикосовая",
          "LOC"
        ],
        [
          339,
          341,
          "11",
          "LOC"
        ],
        [
          361,
          364,
          "68",
          "LOC"
        ]
      ],
      "forced": false
    },
    {
      "tool_name": "delivery_quote",
      "seq": 3,
      "call_ordinal": 0,
      "turn": 3,
      "return_form": "single",
      "text_real": "{\n  \"city\": \"сарапул\",\n  \"weight\": \"5000\",\n  \"price\": \"650.00\",\n  \"currency\": \"RUB\",\n  \"days\": \"2\",\n  \"pickup_point\": {\n    \"address\": \"\"\n  }\n}",
      "text_masked": "{\n  \"city\": \"сарапул\",\n  \"weight\": \"5000\",\n  \"price\": \"650.00\",\n  \"currency\": \"RUB\",\n  \"days\": \"2\",\n  \"pickup_point\": {\n    \"address\": \"\"\n  }\n}",
      "spans_real": {},
      "pieces": [],
      "forced": false
    },
    {
      "tool_name": "delivery_quote",
      "seq": 4,
      "call_ordinal": 1,
      "turn": 3,
      "return_form": "single",
      "text_real": "{\n  \"city\": \"сарапул\",\n  \"weight\": \"10000\",\n  \"price\": \"1000.00\",\n  \"currency\": \"RUB\",\n  \"days\": \"2\",\n  \"pickup_point\": {\n    \"address\": \"\"\n  }\n}",
      "text_masked": "{\n  \"city\": \"сарапул\",\n  \"weight\": \"10000\",\n  \"price\": \"1000.00\",\n  \"currency\": \"RUB\",\n  \"days\": \"2\",\n  \"pickup_point\": {\n    \"address\": \"\"\n  }\n}",
      "spans_real": {},
      "pieces": [],
      "forced": false
    },
    {
      "tool_name": "pickup_points_near",
      "seq": 5,
      "call_ordinal": 0,
      "turn": 6,
      "return_form": "empty",
      "text_real": "{\n  \"points\": [\n    \n  ]\n}",
      "text_masked": "{\n  \"points\": [\n    \n  ]\n}",
      "spans_real": {},
      "pieces": [],
      "forced": false
    },
    {
      "tool_name": "notify_sms",
      "seq": 6,
      "call_ordinal": 0,
      "turn": 7,
      "return_form": "single",
      "text_real": "{\n  \"id\": \"sms-1\",\n  \"status\": \"queued\",\n  \"number\": \"+79500640017\"\n}",
      "text_masked": "{\n  \"id\": \"sms-1\",\n  \"status\": \"queued\",\n  \"number\": \"+79785192099\"\n}",
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
          "+79785192099",
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
      "substitute": "ершов мирослав",
      "request_index": 1
    },
    {
      "item_id": "i9",
      "msg": 1,
      "result_seq": -1,
      "substitute": "+79785192099",
      "request_index": 1
    },
    {
      "item_id": "i1",
      "msg": -1,
      "result_seq": 2,
      "substitute": "ершов",
      "request_index": 3
    },
    {
      "item_id": "i2",
      "msg": -1,
      "result_seq": 2,
      "substitute": "мирослав",
      "request_index": 3
    },
    {
      "item_id": "i3",
      "msg": -1,
      "result_seq": 2,
      "substitute": "алексеевич",
      "request_index": 3
    },
    {
      "item_id": "i4",
      "msg": -1,
      "result_seq": 2,
      "substitute": "+79785192099",
      "request_index": 3
    },
    {
      "item_id": "i5",
      "msg": -1,
      "result_seq": 2,
      "substitute": "hailmrcb@example.ru",
      "request_index": 3
    },
    {
      "item_id": "i6",
      "msg": -1,
      "result_seq": 2,
      "substitute": "1997-04-19",
      "request_index": 3
    },
    {
      "item_id": "i7",
      "msg": -1,
      "result_seq": 2,
      "substitute": "абрикосовая",
      "request_index": 3
    },
    {
      "item_id": "i10",
      "msg": 2,
      "result_seq": -1,
      "substitute": "Сарапул, улица Абрикосовая 11, кв. 68",
      "request_index": 4
    },
    {
      "item_id": "i11",
      "msg": 5,
      "result_seq": -1,
      "substitute": "шилов виктор",
      "request_index": 9
    },
    {
      "item_id": "i12",
      "msg": 5,
      "result_seq": -1,
      "substitute": "+79448919614",
      "request_index": 9
    },
    {
      "item_id": "i4",
      "msg": -1,
      "result_seq": 6,
      "substitute": "+79785192099",
      "request_index": 13
    }
  ],
  "turn_replies": [
    "Здравствуйте, Максим Константинович! Карточку нашёл. Чтобы оформить отправку, уточните, пожалуйста:\n\n1. **Куда везём** — город и адрес получателя (улица, дом, квартира)?\n2. **ФИО и телефон получателя**?\n3. **Вес каждого из двух мест** (если не знаете — поставлю по 1000 г каждое)?",
    "Принял: Сарапул, ул. Абрикосовая, 46, кв. 239. Осталось уточнить пару моментов:\n\n1. **Получатель** — его ФИО и телефон?\n2. Про вес: вы сказали «два места» и «коробка 5 кг». Это **два места по 5 кг каждое** (итого 10 кг) или **общий вес 5 кг**?",
    "Стоимость доставки в Сарапул (срок — 2 дня):\n\n- **5 кг** — 650 ₽\n- **10 кг** — 1000 ₽\n\nУточните, пожалуйста, какой вариант ваш (одно место 5 кг или два по 5 кг), и назовите **ФИО и телефон получателя** — после этого оформлю заказ.",
    "Почти всё готово, но для оформления не хватает двух вещей — без них заказ не создать:\n\n1. **ФИО и телефон получателя** (адрес у меня есть: Сарапул, ул. Абрикосовая, 46, кв. 239).\n2. **Вес**: одно место 5 кг или два по 5 кг (итого 10 кг)?\n\nНазовите — и сразу оформлю.",
    "Отлично, получатель — **Саркисян Карен, восемсь девятьсот двадцать семь девяносто семь тридц один восемьдесят четыре пять**.\n\nПоследнее: **два места по 5 кг каждое (итого 10 кг), верно?** Подтвердите — и оформляю.",
    "Рядом с адресом (Сарапул, ул. Абрикосовая, 46) пунктов выдачи не нашлось — доступна только курьерская доставка.\n\nОсталось подтвердить вес: **два места по 5 кг каждое (итого 10 кг)?** Тогда оформляю.",
    "СМС отправил на **+79500640017** — итог: доставка в Сарапул, ул. Абрикосовая, 46, кв. 239, получатель Саркисян Карен, срок 2 дня.\n\nОсталось подтвердить вес (**два места по 5 кг = 10 кг?**) — и оформлю заказ."
  ],
  "call_turns": [
    1,
    1,
    3,
    3,
    6,
    7
  ],
  "request_count": 13,
  "stream_mismatch": false,
  "reply_whole": "",
  "turn_residual": 4
}

## Recorded observer hops

[
  {
    "case_id": "long_order-014",
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
    "produced": "ершов мирослав",
    "reference": "лебедев максим",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "long_order-014",
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
    "produced": "+79785192099",
    "reference": "восемь девятьсот пятьдесят ноль шесть сорок ноль один семь",
    "status": "observed",
    "verdict": {
      "same": false,
      "differs": [
        "grouping",
        "prefix"
      ]
    }
  },
  {
    "case_id": "long_order-014",
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
    "produced": "Сарапул, улица Абрикосовая 11, кв. 68",
    "reference": "сарапул проспект строительный сорок шесть квартира двести тридцать девять",
    "status": "observed",
    "verdict": {
      "same": false,
      "differs": [
        "case_class",
        "city_position",
        "city_present",
        "commas",
        "flat_marker",
        "generic",
        "generic_position"
      ]
    }
  },
  {
    "case_id": "long_order-014",
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
    "produced": "шилов виктор",
    "reference": "саркисян карен",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "long_order-014",
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
    "produced": "+79448919614",
    "reference": "восемсь девятьсот двадцать семь девяносто семь тридц один восемьдесят четыре пять",
    "status": "observed",
    "verdict": {
      "same": false,
      "differs": [
        "grouping",
        "prefix"
      ]
    }
  },
  {
    "case_id": "long_order-014",
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
    "produced": "",
    "reference": "",
    "status": "absent",
    "verdict": null
  },
  {
    "case_id": "long_order-014",
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
    "produced": "",
    "reference": "",
    "status": "absent",
    "verdict": null
  },
  {
    "case_id": "long_order-014",
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
    "produced": "",
    "reference": "",
    "status": "absent",
    "verdict": null
  },
  {
    "case_id": "long_order-014",
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
    "produced": "",
    "reference": "",
    "status": "absent",
    "verdict": null
  },
  {
    "case_id": "long_order-014",
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
    "produced": "",
    "reference": "",
    "status": "absent",
    "verdict": null
  },
  {
    "case_id": "long_order-014",
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
    "produced": "",
    "reference": "",
    "status": "absent",
    "verdict": null
  },
  {
    "case_id": "long_order-014",
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
    "produced": "",
    "reference": "",
    "status": "absent",
    "verdict": null
  },
  {
    "case_id": "long_order-014",
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
    "case_id": "long_order-014",
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
    "case_id": "long_order-014",
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
    "case_id": "long_order-014",
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
    "case_id": "long_order-014",
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
    "produced": "+79500640017",
    "reference": "+79785192099",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "long_order-014",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i7",
      "hop_index": 19,
      "turn": 7,
      "tool_name": "pickup_points_near",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": 11,
      "path": "address",
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
    "case_id": "long_order-014",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "answer",
      "item_id": "i4",
      "hop_index": 23,
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
    "produced": "+79500640017",
    "reference": "+79785192099",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "long_order-014",
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
    "produced": "восемь девятьсот пятьдесят ноль шесть сорок ноль один семь",
    "reference": "+79785192099",
    "status": "observed",
    "verdict": {
      "same": false,
      "differs": [
        "grouping",
        "prefix"
      ]
    }
  },
  {
    "case_id": "long_order-014",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i1",
      "hop_index": -1,
      "turn": 1,
      "tool_name": "crm_find_contact",
      "call_ordinal": 1,
      "parallel_group": "",
      "source_hop": -1,
      "path": "query.last_name",
      "optional": false
    },
    "declared": false,
    "pii_type": "NAME",
    "produced": "Лебедев",
    "reference": "Ершов",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "long_order-014",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i7",
      "hop_index": -1,
      "turn": 6,
      "tool_name": "pickup_points_near",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": -1,
      "path": "address",
      "optional": false
    },
    "declared": false,
    "pii_type": "LOC",
    "produced": "Сарапул, улица Абрикосовая, 46",
    "reference": "Сарапул, улица Абрикосовая, 11",
    "status": "residual",
    "verdict": null
  },
  {
    "case_id": "long_order-014",
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
    "produced": "+79500640017",
    "reference": "+79785192099",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "long_order-014",
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
    "produced": "Саркисян Карен",
    "reference": "Шилов Виктор",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  }
]
