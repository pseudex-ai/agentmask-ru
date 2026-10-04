# long_order-002 | source A | repeat 0

Synthetic benchmark evidence. Verbatim serialized fields; no inferred verdicts.

## Case specification

{
  "base": {
    "id": "long_order-002",
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
    "cluster": "PHONE:9821406572",
    "conversation_id": "conv-long-order-2",
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
        "content": "это захаров владислав хочу отправить посылку телефон 89821406572 а также 3 филиала",
        "source": null,
        "name": ""
      },
      {
        "role": "user",
        "content": "везите на одоев улица солнечная 104 квартира 203 коробка 3 килограмма",
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
        "content": "ой получать будет мкртчян ашот его телефон 8-950-840-78-56",
        "source": null,
        "name": ""
      },
      {
        "role": "user",
        "content": "какие пвз рядом со мной",
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
          "last_name": "захаров",
          "first_name": "владислав",
          "middle_name": "юрьевич",
          "phone": "+79821406572",
          "email": "zaharov71@mail.ru",
          "birth_date": "1986-08-23",
          "address": {
            "city": "одоев",
            "street": "солнечная",
            "house": "104",
            "flat": "203"
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
        "identity": "p2",
        "value": "захаров",
        "canonical": "захаров",
        "parts": {
          "surname": "захаров",
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
        "identity": "p2",
        "value": "владислав",
        "canonical": "владислав",
        "parts": {
          "given": "владислав",
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
        "identity": "p2",
        "value": "юрьевич",
        "canonical": "юрьевич",
        "parts": {
          "patronymic": "юрьевич",
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
        "identity": "p2",
        "value": "+79821406572",
        "canonical": "+79821406572",
        "parts": {
          "digits": "9821406572"
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
        "identity": "p2",
        "value": "zaharov71@mail.ru",
        "canonical": "zaharov71@mail.ru",
        "parts": {
          "local": "zaharov71",
          "domain": "mail.ru"
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
        "identity": "p2",
        "value": "1986-08-23",
        "canonical": "1986-08-23",
        "parts": {
          "iso": "1986-08-23"
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
        "identity": "p2.home",
        "value": "солнечная",
        "canonical": "солнечная",
        "parts": {
          "street": "солнечная",
          "street_type": "улица",
          "house": "104",
          "flat": "203",
          "city": "одоев"
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
        "identity": "p2",
        "value": "захаров владислав",
        "canonical": "захаров владислав",
        "parts": {
          "surname": "захаров",
          "given": "владислав",
          "gender": "m"
        },
        "where": {
          "kind": "message",
          "msg": 1,
          "start": 4,
          "end": 21,
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
        "identity": "p2",
        "value": "89821406572",
        "canonical": "+79821406572",
        "parts": {
          "digits": "9821406572"
        },
        "where": {
          "kind": "message",
          "msg": 1,
          "start": 53,
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
        "identity": "p2.home",
        "value": "одоев улица солнечная 104 квартира 203",
        "canonical": "одоев улица солнечная 104 квартира 203",
        "parts": {
          "street": "солнечная",
          "street_type": "улица",
          "house": "104",
          "flat": "203",
          "city": "одоев"
        },
        "where": {
          "kind": "message",
          "msg": 2,
          "start": 10,
          "end": 48,
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
        "identity": "p2r",
        "value": "мкртчян ашот",
        "canonical": "мкртчян ашот",
        "parts": {
          "surname": "мкртчян",
          "given": "ашот",
          "gender": "m"
        },
        "where": {
          "kind": "message",
          "msg": 5,
          "start": 18,
          "end": 30,
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
        "identity": "p2r",
        "value": "8-950-840-78-56",
        "canonical": "+79508407856",
        "parts": {
          "digits": "9508407856"
        },
        "where": {
          "kind": "message",
          "msg": 5,
          "start": 43,
          "end": 58,
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
          "start": 57,
          "end": 58,
          "record": "",
          "path": ""
        },
        "family": "weight",
        "why": "вес посылки — не персональные данные, обязан дойти как назван"
      }
    ],
    "negatives": [
      {
        "value": "3 филиала",
        "start": 73,
        "end": 82,
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
      "primary_identity": "p2",
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
        "end": 21,
        "origin": "value:n1"
      },
      {
        "msg": 1,
        "key": "",
        "start": 21,
        "end": 22,
        "origin": "literal"
      },
      {
        "msg": 1,
        "key": "",
        "start": 22,
        "end": 26,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 1,
        "key": "",
        "start": 26,
        "end": 27,
        "origin": "literal"
      },
      {
        "msg": 1,
        "key": "",
        "start": 27,
        "end": 36,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 1,
        "key": "",
        "start": 36,
        "end": 37,
        "origin": "literal"
      },
      {
        "msg": 1,
        "key": "",
        "start": 37,
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
        "key": "ph1",
        "start": 53,
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
        "key": "neg1",
        "start": 73,
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
        "end": 48,
        "origin": "value:a1"
      },
      {
        "msg": 2,
        "key": "",
        "start": 48,
        "end": 49,
        "origin": "literal"
      },
      {
        "msg": 2,
        "key": "",
        "start": 49,
        "end": 56,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 2,
        "key": "",
        "start": 56,
        "end": 57,
        "origin": "literal"
      },
      {
        "msg": 2,
        "key": "w1",
        "start": 57,
        "end": 58,
        "origin": "plain:w1"
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
        "key": "",
        "start": 59,
        "end": 69,
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
        "end": 2,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 5,
        "key": "",
        "start": 2,
        "end": 3,
        "origin": "literal"
      },
      {
        "msg": 5,
        "key": "",
        "start": 3,
        "end": 11,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 5,
        "key": "",
        "start": 11,
        "end": 12,
        "origin": "literal"
      },
      {
        "msg": 5,
        "key": "",
        "start": 12,
        "end": 17,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 5,
        "key": "",
        "start": 17,
        "end": 18,
        "origin": "literal"
      },
      {
        "msg": 5,
        "key": "n2",
        "start": 18,
        "end": 30,
        "origin": "value:n2"
      },
      {
        "msg": 5,
        "key": "",
        "start": 30,
        "end": 31,
        "origin": "literal"
      },
      {
        "msg": 5,
        "key": "",
        "start": 31,
        "end": 34,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 5,
        "key": "",
        "start": 34,
        "end": 35,
        "origin": "literal"
      },
      {
        "msg": 5,
        "key": "",
        "start": 35,
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
        "end": 58,
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
        "end": 15,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 6,
        "key": "",
        "start": 15,
        "end": 16,
        "origin": "literal"
      },
      {
        "msg": 6,
        "key": "",
        "start": 16,
        "end": 18,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 6,
        "key": "",
        "start": 18,
        "end": 19,
        "origin": "literal"
      },
      {
        "msg": 6,
        "key": "",
        "start": 19,
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
    "case_id": "long_order-002",
    "arm": "I",
    "repeat": 0,
    "calls": [
      {
        "name": "crm_find_contact",
        "written": {
          "query": {
            "phone": "+79682063083"
          }
        },
        "restored": {
          "query": {
            "phone": "+79821406572"
          }
        },
        "residual": {},
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "query": {
            "phone": "+79821406572"
          }
        },
        "seq": 1
      },
      {
        "name": "pickup_points_near",
        "written": {
          "address": "одоев, лавандовая 155",
          "limit": 3
        },
        "restored": {
          "address": "одоев, солнечная 104",
          "limit": 3
        },
        "residual": {},
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "address": "одоев, солнечная 104",
          "limit": 3
        },
        "seq": 2
      },
      {
        "name": "delivery_quote",
        "written": {
          "city": "Долгих",
          "weight": 3000
        },
        "restored": {
          "city": "Одоеве",
          "weight": 3000
        },
        "residual": {},
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "city": "одоеве",
          "weight": 3000
        },
        "seq": 3
      },
      {
        "name": "pickup_points_near",
        "written": {
          "address": "Долгих, улица Абрикосовая 167",
          "limit": 3
        },
        "restored": {
          "address": "Одоеве, улица Солнечная 104",
          "limit": 3
        },
        "residual": {},
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "address": "Одоеве, улица Солнечная 104",
          "limit": 3
        },
        "seq": 4
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
            "name": "Гущин Степан",
            "phones": [
              {
                "number": "+79256611733"
              }
            ]
          },
          "to_location": {
            "address": "улица Абрикосовая, дом 167, квартира 25",
            "city": "Долгих",
            "postal_code": "303500"
          }
        },
        "restored": {
          "packages": [
            {
              "weight": 3000
            }
          ],
          "recipient": {
            "name": "Мкртчян Ашот",
            "phones": [
              {
                "number": "+79508407856"
              }
            ]
          },
          "to_location": {
            "address": "улица Солнечная, дом 104, квартира 203",
            "city": "Одоеве",
            "postal_code": "303500"
          }
        },
        "residual": {},
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
            "name": "Мкртчян Ашот",
            "phones": [
              "+79508407856"
            ]
          },
          "to_location": {
            "address": "улица Солнечная, дом 104, квартира 203",
            "city": "одоеве",
            "postal_code": "303500"
          }
        },
        "seq": 5
      },
      {
        "name": "crm_add_note",
        "written": {
          "entity_id": "c-1",
          "note_type": "call_in",
          "text": "Оформил доставку посылки 3000 г в г. Долгих, ул. Абрикосовая, д. 167, кв. 25. Получатель: Гущин Степан, +79256611733. Заказ ord-1, 510 ₽, 2 дня. Пункты выдачи рядом с адресом не найдены."
        },
        "restored": {
          "entity_id": "c-1",
          "note_type": "call_in",
          "text": "Оформил доставку посылки 3000 г в г. Одоеве, ул. Солнечная, д. 104, кв. 203. Получатель: Мкртчян Ашот, +79508407856. Заказ ord-1, 510 ₽, 2 дня. Пункты выдачи рядом с адресом не найдены."
        },
        "residual": {},
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "entity_id": "c-1",
          "note_type": "call_in",
          "text": "Оформил доставку посылки 3000 г в г. Одоеве, ул. Солнечная, д. 104, кв. 203. Получатель: Мкртчян Ашот, +79508407856. Заказ ord-1, 510 ₽, 2 дня. Пункты выдачи рядом с адресом не найдены."
        },
        "seq": 6
      },
      {
        "name": "pickup_points_near",
        "written": {
          "address": "Одоев, улица Лавандовая, 155",
          "limit": 10
        },
        "restored": {
          "address": "Одоев, улица Лавандовая, 104",
          "limit": 10
        },
        "residual": {
          "address": [
            "лавандовая"
          ]
        },
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "address": "Одоев, улица Лавандовая, 104",
          "limit": 10
        },
        "seq": 7
      },
      {
        "name": "pickup_points_near",
        "written": {
          "address": "Одоев",
          "limit": 10
        },
        "restored": {
          "address": "Одоев",
          "limit": 10
        },
        "residual": {},
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "address": "Одоев",
          "limit": 10
        },
        "seq": 8
      },
      {
        "name": "pickup_points_near",
        "written": {
          "address": "улица Лавандовая 155",
          "limit": 10
        },
        "restored": {
          "address": "улица Лавандовая 104",
          "limit": 10
        },
        "residual": {
          "address": [
            "лавандовая"
          ]
        },
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "address": "улица Лавандовая 104",
          "limit": 10
        },
        "seq": 9
      },
      {
        "name": "notify_sms",
        "written": {
          "number": "+79682063083",
          "sign": "Dostavka",
          "text": "Заказ ord-1 оформлен. Получатель: Гущин Степан. Адрес: г. Долгих, ул. Абрикосовая, д. 167, кв. 25. Вес 3 кг. Стоимость 510 руб., срок 2 дня."
        },
        "restored": {
          "number": "+79821406572",
          "sign": "Dostavka",
          "text": "Заказ ord-1 оформлен. Получатель: Мкртчян Ашот. Адрес: г. Одоев, ул. Солнечная, д. 104, кв. 203. Вес 3 кг. Стоимость 510 руб., срок 2 дня."
        },
        "residual": {},
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "number": "+79821406572",
          "sign": "Dostavka",
          "text": "Заказ ord-1 оформлен. Получатель: Мкртчян Ашот. Адрес: г. Одоев, ул. Солнечная, д. 104, кв. 203. Вес 3 кг. Стоимость 510 руб., срок 2 дня."
        },
        "seq": 10
      }
    ],
    "state": [
      {
        "fields": {
          "comment": "",
          "packages": [
            {
              "weight": 3000
            }
          ],
          "recipient": {
            "name": "Мкртчян Ашот",
            "phones": [
              "+79508407856"
            ]
          },
          "to_location": {
            "address": "улица Солнечная, дом 104, квартира 203",
            "city": "одоеве",
            "postal_code": "303500"
          }
        },
        "id": "ord-1",
        "seq": 5,
        "table": "orders",
        "tool": "delivery_create_order"
      },
      {
        "fields": {
          "entity_id": "c-1",
          "note_type": "call_in",
          "text": "Оформил доставку посылки 3000 г в г. Одоеве, ул. Солнечная, д. 104, кв. 203. Получатель: Мкртчян Ашот, +79508407856. Заказ ord-1, 510 ₽, 2 дня. Пункты выдачи рядом с адресом не найдены."
        },
        "id": "note-1",
        "seq": 6,
        "table": "notes",
        "tool": "crm_add_note"
      },
      {
        "fields": {
          "number": "+79821406572",
          "sign": "Dostavka",
          "text": "Заказ ord-1 оформлен. Получатель: Мкртчян Ашот. Адрес: г. Одоев, ул. Солнечная, д. 104, кв. 203. Вес 3 кг. Стоимость 510 руб., срок 2 дня."
        },
        "id": "sms-1",
        "seq": 10,
        "table": "sms",
        "tool": "notify_sms"
      }
    ],
    "reply": "Готово! ✅ СМС с деталями заказа отправлено на ваш номер **89821406572**.\n\nТекст сообщения:\n> Заказ ord-1 оформлен. Получатель: Мкртчян Ашот. Адрес: г. Одоев, улица солнечная 104 квартира 203. Вес 3 кг. Стоимость 510 руб., срок 2 дня.\n\nЧто-нибудь ещё нужно?",
    "termination": "done",
    "cost_usd": 0.013746,
    "substitutes": {
      "i1": [
        "титов",
        {
          "surname": "титов"
        }
      ],
      "i10": [
        "долгих улица абрикосовая 167 квартира 25",
        {
          "flat": "25",
          "house": "167",
          "street": "абрикосовая долгих"
        }
      ],
      "i11": [
        "гущин степан",
        {
          "given": "степан",
          "surname": "гущин"
        }
      ],
      "i12": [
        "8-925-661-17-33",
        {
          "digits": "9256611733"
        }
      ],
      "i2": [
        "тарас",
        {
          "given": "тарас"
        }
      ],
      "i3": [
        "сергеевич",
        {
          "patronymic": "сергеевич"
        }
      ],
      "i4": [
        "89682063083",
        {
          "digits": "9682063083"
        }
      ],
      "i5": [
        "lsbulmbp@example.ru",
        {
          "domain": "example.ru",
          "local": "lsbulmbp"
        }
      ],
      "i6": [
        "1986-08-13",
        {
          "iso": "1986-08-13"
        }
      ],
      "i7": [
        "лавандовая",
        {
          "street": "лавандовая"
        }
      ],
      "i8": [
        "титов тарас",
        {
          "given": "тарас",
          "surname": "титов"
        }
      ],
      "i9": [
        "89682063083",
        {
          "digits": "9682063083"
        }
      ]
    },
    "masked_spans": {
      "0": [],
      "1": [
        [
          4,
          21
        ],
        [
          53,
          64
        ]
      ],
      "2": [
        [
          10,
          15
        ],
        [
          16,
          48
        ]
      ],
      "3": [],
      "4": [],
      "5": [
        [
          18,
          30
        ],
        [
          43,
          58
        ]
      ],
      "6": [],
      "7": []
    }
  },
  "reply_raw": "Готово! ✅ СМС с деталями заказа отправлено на ваш номер **+7 968 206-30-83**.\n\nТекст сообщения:\n> Заказ ord-1 оформлен. Получатель: Гущин Степан. Адрес: г. Долгих, ул. Абрикосовая, д. 167, кв. 25. Вес 3 кг. Стоимость 510 руб., срок 2 дня.\n\nЧто-нибудь ещё нужно?",
  "control_reply": "Отправил СМС на ваш номер +79821406572 с деталями заказа ord-1 ✅\n\nЧто-нибудь ещё?",
  "tool_results": [
    {
      "tool_name": "crm_find_contact",
      "seq": 1,
      "call_ordinal": 0,
      "turn": 1,
      "return_form": "list",
      "text_real": "{\n  \"contacts\": [\n    {\n      \"id\": \"c-1\",\n      \"last_name\": \"захаров\",\n      \"first_name\": \"владислав\",\n      \"middle_name\": \"юрьевич\",\n      \"phone\": \"+79821406572\",\n      \"email\": \"zaharov71@mail.ru\",\n      \"birth_date\": \"1986-08-23\",\n      \"address\": {\n        \"city\": \"одоев\",\n        \"street\": \"солнечная\",\n        \"house\": \"104\",\n        \"flat\": \"203\"\n      }\n    }\n  ]\n}",
      "text_masked": "{\n  \"contacts\": [\n    {\n      \"id\": \"c-1\",\n      \"last_name\": \"титов\",\n      \"first_name\": \"тарас\",\n      \"middle_name\": \"сергеевич\",\n      \"phone\": \"89682063083\",\n      \"email\": \"lsbulmbp@example.ru\",\n      \"birth_date\": \"1986-08-13\",\n      \"address\": {\n        \"city\": \"одоев\",\n        \"street\": \"лавандовая\",\n        \"house\": \"155\",\n        \"flat\": \"159\"\n      }\n    }\n  ]\n}",
      "spans_real": {
        "i1": [
          63,
          70
        ],
        "i2": [
          94,
          103
        ],
        "i3": [
          128,
          135
        ],
        "i4": [
          154,
          166
        ],
        "i5": [
          185,
          202
        ],
        "i6": [
          226,
          236
        ],
        "i7": [
          302,
          311
        ]
      },
      "pieces": [
        [
          63,
          70,
          "титов",
          "NAME"
        ],
        [
          94,
          103,
          "тарас",
          "NAME"
        ],
        [
          128,
          135,
          "сергеевич",
          "NAME"
        ],
        [
          154,
          166,
          "89682063083",
          "PHONE"
        ],
        [
          185,
          202,
          "lsbulmbp@example.ru",
          "EMAIL"
        ],
        [
          226,
          236,
          "1986-08-13",
          "DOB"
        ],
        [
          275,
          280,
          "одоев",
          "LOC"
        ],
        [
          302,
          311,
          "лавандовая",
          "LOC"
        ],
        [
          332,
          335,
          "155",
          "LOC"
        ],
        [
          355,
          358,
          "159",
          "LOC"
        ]
      ],
      "forced": false
    },
    {
      "tool_name": "pickup_points_near",
      "seq": 2,
      "call_ordinal": 0,
      "turn": 1,
      "return_form": "empty",
      "text_real": "{\n  \"points\": [\n    \n  ]\n}",
      "text_masked": "{\n  \"points\": [\n    \n  ]\n}",
      "spans_real": {},
      "pieces": [],
      "forced": false
    },
    {
      "tool_name": "delivery_quote",
      "seq": 3,
      "call_ordinal": 0,
      "turn": 3,
      "return_form": "single",
      "text_real": "{\n  \"city\": \"одоеве\",\n  \"weight\": \"3000\",\n  \"price\": \"510.00\",\n  \"currency\": \"RUB\",\n  \"days\": \"2\",\n  \"pickup_point\": {\n    \"address\": \"\"\n  }\n}",
      "text_masked": "{\n  \"city\": \"долгих\",\n  \"weight\": \"3000\",\n  \"price\": \"510.00\",\n  \"currency\": \"RUB\",\n  \"days\": \"2\",\n  \"pickup_point\": {\n    \"address\": \"\"\n  }\n}",
      "spans_real": {},
      "pieces": [
        [
          13,
          19,
          "долгих",
          "NAME"
        ]
      ],
      "forced": false
    },
    {
      "tool_name": "pickup_points_near",
      "seq": 4,
      "call_ordinal": 0,
      "turn": 5,
      "return_form": "empty",
      "text_real": "{\n  \"points\": [\n    \n  ]\n}",
      "text_masked": "{\n  \"points\": [\n    \n  ]\n}",
      "spans_real": {},
      "pieces": [],
      "forced": false
    },
    {
      "tool_name": "delivery_create_order",
      "seq": 5,
      "call_ordinal": 0,
      "turn": 5,
      "return_form": "single",
      "text_real": "{\n  \"uuid\": \"ord-1\",\n  \"status\": \"ACCEPTED\",\n  \"recipient\": {\n    \"name\": \"Мкртчян Ашот\",\n    \"phone\": \"+79508407856\"\n  },\n  \"to_location\": {\n    \"postal_code\": \"303500\",\n    \"city\": \"одоеве\",\n    \"address\": \"улица Солнечная, дом 104, квартира 203\"\n  }\n}",
      "text_masked": "{\n  \"uuid\": \"ord-1\",\n  \"status\": \"ACCEPTED\",\n  \"recipient\": {\n    \"name\": \"Гущин Степан\",\n    \"phone\": \"8-925-661-17-33\"\n  },\n  \"to_location\": {\n    \"postal_code\": \"303500\",\n    \"city\": \"долгих\",\n    \"address\": \"улица Абрикосовая, дом 167, квартира 25\"\n  }\n}",
      "spans_real": {},
      "pieces": [
        [
          75,
          87,
          "Гущин Степан",
          "NAME"
        ],
        [
          104,
          116,
          "8-925-661-17-33",
          "PHONE"
        ],
        [
          184,
          190,
          "долгих",
          "NAME"
        ],
        [
          209,
          247,
          "улица Абрикосовая, дом 167, квартира 25",
          "LOC"
        ]
      ],
      "forced": false
    },
    {
      "tool_name": "crm_add_note",
      "seq": 6,
      "call_ordinal": 0,
      "turn": 5,
      "return_form": "single",
      "text_real": "{\n  \"id\": \"note-1\",\n  \"entity_id\": \"c-1\",\n  \"length\": 185,\n  \"entity\": {\n    \"last_name\": \"захаров\",\n    \"first_name\": \"владислав\",\n    \"phone\": \"+79821406572\"\n  }\n}",
      "text_masked": "{\n  \"id\": \"note-1\",\n  \"entity_id\": \"c-1\",\n  \"length\": 185,\n  \"entity\": {\n    \"last_name\": \"титов\",\n    \"first_name\": \"тарас\",\n    \"phone\": \"89682063083\"\n  }\n}",
      "spans_real": {
        "i1": [
          91,
          98
        ],
        "i2": [
          120,
          129
        ],
        "i4": [
          146,
          158
        ]
      },
      "pieces": [
        [
          91,
          98,
          "титов",
          "NAME"
        ],
        [
          120,
          129,
          "тарас",
          "NAME"
        ],
        [
          146,
          158,
          "89682063083",
          "PHONE"
        ]
      ],
      "forced": false
    },
    {
      "tool_name": "pickup_points_near",
      "seq": 7,
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
      "tool_name": "pickup_points_near",
      "seq": 8,
      "call_ordinal": 1,
      "turn": 6,
      "return_form": "empty",
      "text_real": "{\n  \"points\": [\n    \n  ]\n}",
      "text_masked": "{\n  \"points\": [\n    \n  ]\n}",
      "spans_real": {},
      "pieces": [],
      "forced": false
    },
    {
      "tool_name": "pickup_points_near",
      "seq": 9,
      "call_ordinal": 2,
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
      "seq": 10,
      "call_ordinal": 0,
      "turn": 7,
      "return_form": "single",
      "text_real": "{\n  \"id\": \"sms-1\",\n  \"status\": \"queued\",\n  \"number\": \"+79821406572\"\n}",
      "text_masked": "{\n  \"id\": \"sms-1\",\n  \"status\": \"queued\",\n  \"number\": \"89682063083\"\n}",
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
          "89682063083",
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
      "substitute": "титов тарас",
      "request_index": 1
    },
    {
      "item_id": "i9",
      "msg": 1,
      "result_seq": -1,
      "substitute": "89682063083",
      "request_index": 1
    },
    {
      "item_id": "i1",
      "msg": -1,
      "result_seq": 1,
      "substitute": "титов",
      "request_index": 2
    },
    {
      "item_id": "i2",
      "msg": -1,
      "result_seq": 1,
      "substitute": "тарас",
      "request_index": 2
    },
    {
      "item_id": "i3",
      "msg": -1,
      "result_seq": 1,
      "substitute": "сергеевич",
      "request_index": 2
    },
    {
      "item_id": "i4",
      "msg": -1,
      "result_seq": 1,
      "substitute": "89682063083",
      "request_index": 2
    },
    {
      "item_id": "i5",
      "msg": -1,
      "result_seq": 1,
      "substitute": "lsbulmbp@example.ru",
      "request_index": 2
    },
    {
      "item_id": "i6",
      "msg": -1,
      "result_seq": 1,
      "substitute": "1986-08-13",
      "request_index": 2
    },
    {
      "item_id": "i7",
      "msg": -1,
      "result_seq": 1,
      "substitute": "лавандовая",
      "request_index": 2
    },
    {
      "item_id": "i10",
      "msg": 2,
      "result_seq": -1,
      "substitute": "долгих улица абрикосовая 167 квартира 25",
      "request_index": 4
    },
    {
      "item_id": "i11",
      "msg": 5,
      "result_seq": -1,
      "substitute": "гущин степан",
      "request_index": 8
    },
    {
      "item_id": "i12",
      "msg": 5,
      "result_seq": -1,
      "substitute": "8-925-661-17-33",
      "request_index": 8
    },
    {
      "item_id": "i1",
      "msg": -1,
      "result_seq": 6,
      "substitute": "титов",
      "request_index": 11
    },
    {
      "item_id": "i2",
      "msg": -1,
      "result_seq": 6,
      "substitute": "тарас",
      "request_index": 11
    },
    {
      "item_id": "i4",
      "msg": -1,
      "result_seq": 6,
      "substitute": "89682063083",
      "request_index": 11
    },
    {
      "item_id": "i4",
      "msg": -1,
      "result_seq": 10,
      "substitute": "89682063083",
      "request_index": 17
    }
  ],
  "turn_replies": [
    "Здравствуйте! Сейчас найду вашу карточку в CRM.\nВладислав Юрьевич, карточку нашёл. Чтобы оформить отправку посылки, мне не хватает данных о получателе:\n\n1. **ФИО получателя**\n2. **Телефон получателя**\n3. **Город и адрес** (улица, дом, квартира) — почтовый индекс подберу сам\n4. **Вес посылки** (если не знаете — по умолчанию приму 1000 г)\n\nИ уточните, пожалуйста, что вы имели в виду под «**3 филиала**»: вы хотите, чтобы я подыскал 3 пункта выдачи рядом с каким-то адресом? Если да — рядом с каким именно адресом (и в каком городе)? По вашему адресу в Одоеве, солнечная 104, пунктов выдачи рядом не нашлось.",
    "Понял: посылка 3 кг (3000 г), адрес — улица солнечная 104 квартира 203.\n\nНе хватает данных для оформления:\n\n1. **ФИО получателя**\n2. **Телефон получателя**\n\nИ уточните, пожалуйста, город: вы назвали «**Одоев**» — это город получателя? Хочу убедиться, что правильно оформлю адрес (и подберу индекс).\n\nТакже напомню про «**3 филиала**» из первого сообщения — что именно нужно: подобрать 3 пункта выдачи рядом с адресом доставки (улица солнечная 104)?",
    "Стоимость доставки: **510 ₽**, срок — **2 дня**.\n\nЧтобы оформить заказ, осталось получить:\n1. **ФИО получателя**\n2. **Телефон получателя**\n\nПочтовый индекс по городу Одоев подберу сам.",
    "Для оформления заказа мне обязательно нужны **ФИО и телефон получателя** — без этих данных курьерская служба заказ не примет, а выдумывать их я не могу.\n\nПродиктуйте, пожалуйста:\n1. **ФИО получателя** (кому везём посылку на улицу солнечную 104 квартира 203)\n2. **Телефон получателя**\n\nКак только они будут — сразу оформлю доставку (3 кг, г. Одоев, 510 ₽, 2 дня).",
    "Отлично! Получатель — Мкртчян Ашот. Сейчас подберу пункты выдачи рядом с адресом доставки (те самые «3 филиала») и оформлю заказ.\nЗаказ оформлен! 🎉\n\n**Детали доставки:**\n- **Номер заказа:** ord-1\n- **Получатель:** Мкртчян Ашот, 8-950-840-78-56\n- **Адрес:** г. Одоев, улица солнечная 104 квартира 203\n- **Вес:** 3 кг\n- **Стоимость:** 510 ₽\n- **Срок:** 2 дня\n\nПо поводу «3 филиалов»: к сожалению, пунктов выдачи рядом с адресом (улица солнечная 104, г. Одоев) подобрать не удалось — поблизости их нет в базе. Если нужно, могу поискать в другом районе или городе.\n\nПодскажите, нужно ли отправить СМС получателю или вам с номером заказа?",
    "Владислав Юрьевич, я проверил по вашему адресу (Одоев, ул. Лавандовая, 104) — к сожалению, **пунктов выдачи поблизости не найдено**. Пробовал разные варианты адреса, результат тот же: в базе рядом с вами ПВЗ нет.\n\nЕсли хотите, назовите другой адрес или город (например, где вы бываете) — поищу там. Также напомню, что по адресу доставки в г. Одоев пунктов выдачи тоже не нашлось.",
    "Готово! ✅ СМС с деталями заказа отправлено на ваш номер **89821406572**.\n\nТекст сообщения:\n> Заказ ord-1 оформлен. Получатель: Мкртчян Ашот. Адрес: г. Одоев, улица солнечная 104 квартира 203. Вес 3 кг. Стоимость 510 руб., срок 2 дня.\n\nЧто-нибудь ещё нужно?"
  ],
  "call_turns": [
    1,
    1,
    3,
    5,
    5,
    5,
    6,
    6,
    6,
    7
  ],
  "request_count": 17,
  "stream_mismatch": false,
  "reply_whole": "",
  "turn_residual": 6
}

## Recorded observer hops

[
  {
    "case_id": "long_order-002",
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
    "produced": "титов тарас",
    "reference": "захаров владислав",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "long_order-002",
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
    "produced": "89682063083",
    "reference": "89821406572",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "long_order-002",
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
    "produced": "долгих улица абрикосовая 167 квартира 25",
    "reference": "одоев улица солнечная 104 квартира 203",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "long_order-002",
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
    "produced": "гущин степан",
    "reference": "мкртчян ашот",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "long_order-002",
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
    "produced": "8-925-661-17-33",
    "reference": "8-950-840-78-56",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "long_order-002",
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
    "produced": "титов",
    "reference": "захаров",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "long_order-002",
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
    "produced": "тарас",
    "reference": "владислав",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "long_order-002",
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
    "produced": "сергеевич",
    "reference": "юрьевич",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "long_order-002",
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
    "produced": "89682063083",
    "reference": "+79821406572",
    "status": "observed",
    "verdict": {
      "same": false,
      "differs": [
        "prefix"
      ]
    }
  },
  {
    "case_id": "long_order-002",
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
    "produced": "lsbulmbp@example.ru",
    "reference": "zaharov71@mail.ru",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "long_order-002",
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
    "produced": "1986-08-13",
    "reference": "1986-08-23",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "long_order-002",
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
    "produced": "лавандовая",
    "reference": "солнечная",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "long_order-002",
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
    "case_id": "long_order-002",
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
    "case_id": "long_order-002",
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
    "case_id": "long_order-002",
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
    "case_id": "long_order-002",
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
    "produced": "+79821406572",
    "reference": "+79682063083",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "long_order-002",
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
    "case_id": "long_order-002",
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
    "produced": "89821406572",
    "reference": "+7 968 206-30-83",
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
    "case_id": "long_order-002",
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
    "produced": "+79821406572",
    "reference": "+79682063083",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "long_order-002",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i7",
      "hop_index": -1,
      "turn": 1,
      "tool_name": "pickup_points_near",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": -1,
      "path": "address",
      "optional": false
    },
    "declared": false,
    "pii_type": "LOC",
    "produced": "одоев, солнечная 104",
    "reference": "одоев, лавандовая 155",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "long_order-002",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i10",
      "hop_index": -1,
      "turn": 5,
      "tool_name": "pickup_points_near",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": -1,
      "path": "address",
      "optional": false
    },
    "declared": false,
    "pii_type": "LOC",
    "produced": "Одоеве, улица Солнечная 104",
    "reference": "Долгих, улица Абрикосовая 167",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "long_order-002",
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
    "produced": "Мкртчян Ашот",
    "reference": "Гущин Степан",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "long_order-002",
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
    "produced": "+79508407856",
    "reference": "+79256611733",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "long_order-002",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i10",
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
    "produced": "улица Солнечная, дом 104, квартира 203",
    "reference": "улица Абрикосовая, дом 167, квартира 25",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "long_order-002",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i10",
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
    "produced": "Одоеве",
    "reference": "Долгих",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "long_order-002",
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
    "produced": "Одоев, улица Лавандовая, 104",
    "reference": "Одоев, улица Лавандовая, 155",
    "status": "residual",
    "verdict": null
  },
  {
    "case_id": "long_order-002",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "",
      "hop_index": -1,
      "turn": 6,
      "tool_name": "pickup_points_near",
      "call_ordinal": 1,
      "parallel_group": "",
      "source_hop": -1,
      "path": "address",
      "optional": false
    },
    "declared": false,
    "pii_type": "LOC",
    "produced": "Одоев",
    "reference": "Одоев",
    "status": "unmasked",
    "verdict": null
  },
  {
    "case_id": "long_order-002",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i7",
      "hop_index": -1,
      "turn": 6,
      "tool_name": "pickup_points_near",
      "call_ordinal": 2,
      "parallel_group": "",
      "source_hop": -1,
      "path": "address",
      "optional": false
    },
    "declared": false,
    "pii_type": "LOC",
    "produced": "улица Лавандовая 104",
    "reference": "улица Лавандовая 155",
    "status": "residual",
    "verdict": null
  },
  {
    "case_id": "long_order-002",
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
    "produced": "89821406572",
    "reference": "+7 968 206-30-83",
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
    "case_id": "long_order-002",
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
    "produced": "Мкртчян Ашот",
    "reference": "Гущин Степан",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "long_order-002",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "answer",
      "item_id": "i10",
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
    "pii_type": "LOC",
    "produced": "Одоев",
    "reference": "Долгих",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "long_order-002",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "answer",
      "item_id": "i10",
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
    "pii_type": "LOC",
    "produced": "ица солнечная 104 квартира 203",
    "reference": ". Абрикосовая, д. 167, кв. 25",
    "status": "observed",
    "verdict": {
      "same": false,
      "differs": [
        "case_class",
        "commas",
        "flat_marker",
        "house_marker"
      ]
    }
  }
]
