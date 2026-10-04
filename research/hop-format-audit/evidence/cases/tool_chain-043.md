# tool_chain-043 | source C | repeat 0

Synthetic benchmark evidence. Verbatim serialized fields; no inferred verdicts.

## Case specification

{
  "base": {
    "id": "tool_chain-043",
    "kind": "tool_chain",
    "register": "sloppy",
    "provenance": {
      "kind": "template",
      "corpus": "authored",
      "key": "",
      "shape": "",
      "selection": "authored",
      "weight": 1.0,
      "licence": "authored"
    },
    "cluster": "PHONE:9527054451",
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
        "content": "оформите как в пррошлый раз телефон 8 952 705 44 51 и ещё заказ 241",
        "source": null,
        "name": ""
      },
      {
        "role": "user",
        "content": "ничего не диткую всё есть в карточке проверьте адрес и оформите",
        "source": null,
        "name": ""
      },
      {
        "role": "user",
        "content": "и статус заказа поосмотрите",
        "source": null,
        "name": ""
      }
    ],
    "tools": [
      "crm_find_contact",
      "address_suggest",
      "delivery_create_order",
      "order_status",
      "courier_book",
      "notify_sms",
      "crm_add_note",
      "pickup_points_near"
    ],
    "seed_records": [
      {
        "id": "c-1",
        "table": "contacts",
        "fields": {
          "last_name": "воронина",
          "first_name": "елена",
          "middle_name": "сергеевна",
          "phone": "+79527054451",
          "email": "voronina73@yandex.ru",
          "birth_date": "1972-08-10",
          "address": {
            "city": "брянск",
            "street": "добролюбова",
            "house": "41",
            "flat": "25"
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
      },
      {
        "id": "a-0",
        "table": "addresses",
        "fields": {
          "value": "Брянская область, г Брянск, ул Добролюбова, д 41",
          "postal_code": "241228",
          "region": "Брянская область",
          "city": "брянск",
          "street": "добролюбова",
          "house": "41",
          "flat": "",
          "fias_id": "b585d0c9-bcd2-4127-81fc-3d2029031b56"
        },
        "pii_ids": [
          "i8",
          "i9"
        ]
      }
    ],
    "pii": [
      {
        "id": "i1",
        "type": "NAME",
        "identity": "p43",
        "value": "воронина",
        "canonical": "воронина",
        "parts": {
          "surname": "воронина",
          "gender": "f"
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
        "identity": "p43",
        "value": "елена",
        "canonical": "елена",
        "parts": {
          "given": "елена",
          "gender": "f"
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
        "identity": "p43",
        "value": "сергеевна",
        "canonical": "сергеевна",
        "parts": {
          "patronymic": "сергеевна",
          "gender": "f"
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
        "identity": "p43",
        "value": "+79527054451",
        "canonical": "+79527054451",
        "parts": {
          "digits": "9527054451"
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
        "identity": "p43",
        "value": "voronina73@yandex.ru",
        "canonical": "voronina73@yandex.ru",
        "parts": {
          "local": "voronina73",
          "domain": "yandex.ru"
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
        "identity": "p43",
        "value": "1972-08-10",
        "canonical": "1972-08-10",
        "parts": {
          "iso": "1972-08-10"
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
        "identity": "p43.home",
        "value": "добролюбова",
        "canonical": "добролюбова",
        "parts": {
          "street": "добролюбова",
          "street_type": "проезд",
          "house": "41",
          "flat": "25",
          "city": "брянск"
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
        "type": "LOC",
        "identity": "p43.dir",
        "value": "добролюбова",
        "canonical": "добролюбова",
        "parts": {
          "street": "добролюбова"
        },
        "where": {
          "kind": "seed",
          "msg": -1,
          "start": 0,
          "end": 0,
          "record": "a-0",
          "path": "street"
        },
        "duty": "required",
        "spoken": false,
        "stale": false
      },
      {
        "id": "i9",
        "type": "LOC",
        "identity": "p43.dir",
        "value": "Брянская область, г Брянск, ул Добролюбова, д 41",
        "canonical": "Брянская область, г Брянск, ул Добролюбова, д 41",
        "parts": {
          "city": "брянск",
          "street": "добролюбова",
          "house": "41"
        },
        "where": {
          "kind": "seed",
          "msg": -1,
          "start": 0,
          "end": 0,
          "record": "a-0",
          "path": "value"
        },
        "duty": "required",
        "spoken": false,
        "stale": false
      },
      {
        "id": "i10",
        "type": "PHONE",
        "identity": "p43",
        "value": "8 952 705 44 51",
        "canonical": "+79527054451",
        "parts": {
          "digits": "9527054451"
        },
        "where": {
          "kind": "message",
          "msg": 1,
          "start": 36,
          "end": 51,
          "record": "",
          "path": ""
        },
        "duty": "required",
        "spoken": false,
        "stale": false
      }
    ],
    "plain": [],
    "negatives": [
      {
        "value": "241",
        "start": 64,
        "end": 67,
        "msg": 1,
        "family": "order_number",
        "why": "номер заказа — не персональные данные; продиктованный вслух он маскировался целиком, и это уже отгружалось"
      }
    ],
    "expects": {
      "reachable_tools": [
        "crm_find_contact",
        "address_suggest",
        "delivery_create_order",
        "order_status",
        "notify_sms"
      ],
      "primary_identity": "p43",
      "must_contain": [],
      "must_not_contain": [],
      "validate_types": []
    },
    "trace": [
      {
        "msg": 1,
        "key": "",
        "start": 0,
        "end": 8,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 1,
        "key": "",
        "start": 8,
        "end": 9,
        "origin": "literal"
      },
      {
        "msg": 1,
        "key": "",
        "start": 9,
        "end": 12,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 1,
        "key": "",
        "start": 12,
        "end": 13,
        "origin": "literal"
      },
      {
        "msg": 1,
        "key": "",
        "start": 13,
        "end": 14,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 1,
        "key": "",
        "start": 14,
        "end": 15,
        "origin": "literal"
      },
      {
        "msg": 1,
        "key": "",
        "start": 15,
        "end": 23,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 1,
        "key": "",
        "start": 23,
        "end": 24,
        "origin": "literal"
      },
      {
        "msg": 1,
        "key": "",
        "start": 24,
        "end": 27,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 1,
        "key": "",
        "start": 27,
        "end": 28,
        "origin": "literal"
      },
      {
        "msg": 1,
        "key": "",
        "start": 28,
        "end": 35,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 1,
        "key": "",
        "start": 35,
        "end": 36,
        "origin": "literal"
      },
      {
        "msg": 1,
        "key": "ph1",
        "start": 36,
        "end": 51,
        "origin": "value:ph1"
      },
      {
        "msg": 1,
        "key": "",
        "start": 51,
        "end": 52,
        "origin": "literal"
      },
      {
        "msg": 1,
        "key": "",
        "start": 52,
        "end": 53,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 1,
        "key": "",
        "start": 53,
        "end": 54,
        "origin": "literal"
      },
      {
        "msg": 1,
        "key": "",
        "start": 54,
        "end": 57,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 1,
        "key": "",
        "start": 57,
        "end": 58,
        "origin": "literal"
      },
      {
        "msg": 1,
        "key": "",
        "start": 58,
        "end": 63,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 1,
        "key": "",
        "start": 63,
        "end": 64,
        "origin": "literal"
      },
      {
        "msg": 1,
        "key": "neg1",
        "start": 64,
        "end": 67,
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
        "key": "",
        "start": 10,
        "end": 16,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 2,
        "key": "",
        "start": 16,
        "end": 17,
        "origin": "literal"
      },
      {
        "msg": 2,
        "key": "",
        "start": 17,
        "end": 20,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 2,
        "key": "",
        "start": 20,
        "end": 21,
        "origin": "literal"
      },
      {
        "msg": 2,
        "key": "",
        "start": 21,
        "end": 25,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 2,
        "key": "",
        "start": 25,
        "end": 26,
        "origin": "literal"
      },
      {
        "msg": 2,
        "key": "",
        "start": 26,
        "end": 27,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 2,
        "key": "",
        "start": 27,
        "end": 28,
        "origin": "literal"
      },
      {
        "msg": 2,
        "key": "",
        "start": 28,
        "end": 36,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 2,
        "key": "",
        "start": 36,
        "end": 37,
        "origin": "literal"
      },
      {
        "msg": 2,
        "key": "",
        "start": 37,
        "end": 46,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 2,
        "key": "",
        "start": 46,
        "end": 47,
        "origin": "literal"
      },
      {
        "msg": 2,
        "key": "",
        "start": 47,
        "end": 52,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 2,
        "key": "",
        "start": 52,
        "end": 53,
        "origin": "literal"
      },
      {
        "msg": 2,
        "key": "",
        "start": 53,
        "end": 54,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 2,
        "key": "",
        "start": 54,
        "end": 55,
        "origin": "literal"
      },
      {
        "msg": 2,
        "key": "",
        "start": 55,
        "end": 63,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 3,
        "key": "",
        "start": 0,
        "end": 1,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 3,
        "key": "",
        "start": 1,
        "end": 2,
        "origin": "literal"
      },
      {
        "msg": 3,
        "key": "",
        "start": 2,
        "end": 8,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 3,
        "key": "",
        "start": 8,
        "end": 9,
        "origin": "literal"
      },
      {
        "msg": 3,
        "key": "",
        "start": 9,
        "end": 15,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 3,
        "key": "",
        "start": 15,
        "end": 16,
        "origin": "literal"
      },
      {
        "msg": 3,
        "key": "",
        "start": 16,
        "end": 27,
        "origin": "chunk:noisy_word"
      }
    ],
    "note": "три перехода: карточка -> справочник -> заказ -> статус; номер заказа существует только в ответе инструмента"
  },
  "behaviour": "sequential_chain",
  "hops": [
    {
      "kind": "IN",
      "owner": "user",
      "item_id": "i10",
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
      "owner": "tool",
      "item_id": "i9",
      "hop_index": 1,
      "turn": 1,
      "tool_name": "address_suggest",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": -1,
      "path": "suggestions[].value",
      "optional": false
    },
    {
      "kind": "IN",
      "owner": "tool",
      "item_id": "i1",
      "hop_index": 2,
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
      "hop_index": 3,
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
      "hop_index": 4,
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
      "hop_index": 5,
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
      "hop_index": 6,
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
      "hop_index": 7,
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
      "hop_index": 8,
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
      "item_id": "i10",
      "hop_index": 9,
      "turn": 3,
      "tool_name": "crm_find_contact",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": 0,
      "path": "query.phone",
      "optional": true
    },
    {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i7",
      "hop_index": 10,
      "turn": 3,
      "tool_name": "address_suggest",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": 8,
      "path": "query",
      "optional": false
    },
    {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i1",
      "hop_index": 11,
      "turn": 3,
      "tool_name": "delivery_create_order",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": 2,
      "path": "recipient.name",
      "optional": false
    },
    {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i10",
      "hop_index": 12,
      "turn": 3,
      "tool_name": "delivery_create_order",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": 0,
      "path": "recipient.phones[].number",
      "optional": false
    },
    {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i7",
      "hop_index": 13,
      "turn": 3,
      "tool_name": "delivery_create_order",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": -1,
      "path": "to_location.city",
      "optional": false
    },
    {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i7",
      "hop_index": 14,
      "turn": 3,
      "tool_name": "delivery_create_order",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": 8,
      "path": "to_location.address",
      "optional": false
    },
    {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i10",
      "hop_index": 15,
      "turn": 3,
      "tool_name": "notify_sms",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": 0,
      "path": "number",
      "optional": false
    },
    {
      "kind": "OUT",
      "owner": "answer",
      "item_id": "i1",
      "hop_index": 16,
      "turn": 3,
      "tool_name": "",
      "call_ordinal": -1,
      "parallel_group": "",
      "source_hop": 2,
      "path": "",
      "optional": true
    },
    {
      "kind": "OUT",
      "owner": "answer",
      "item_id": "i2",
      "hop_index": 17,
      "turn": 3,
      "tool_name": "",
      "call_ordinal": -1,
      "parallel_group": "",
      "source_hop": 3,
      "path": "",
      "optional": true
    },
    {
      "kind": "OUT",
      "owner": "answer",
      "item_id": "i3",
      "hop_index": 18,
      "turn": 3,
      "tool_name": "",
      "call_ordinal": -1,
      "parallel_group": "",
      "source_hop": 4,
      "path": "",
      "optional": true
    },
    {
      "kind": "OUT",
      "owner": "answer",
      "item_id": "i4",
      "hop_index": 19,
      "turn": 3,
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
      "item_id": "i5",
      "hop_index": 20,
      "turn": 3,
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
      "item_id": "i6",
      "hop_index": 21,
      "turn": 3,
      "tool_name": "",
      "call_ordinal": -1,
      "parallel_group": "",
      "source_hop": 7,
      "path": "",
      "optional": true
    }
  ],
  "returns": [
    {
      "tool_name": "address_suggest",
      "call_ordinal": 0,
      "return_form": "canon",
      "result_item_ids": [
        "i9"
      ]
    },
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
    "case_id": "tool_chain-043",
    "arm": "I",
    "repeat": 0,
    "calls": [
      {
        "name": "crm_find_contact",
        "written": {
          "query": {
            "phone": "+79353350398"
          }
        },
        "restored": {
          "query": {
            "phone": "+79527054451"
          }
        },
        "residual": {},
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "query": {
            "phone": "+79527054451"
          }
        },
        "seq": 1
      },
      {
        "name": "order_status",
        "written": {
          "order_id": "241"
        },
        "restored": {
          "order_id": "241"
        },
        "residual": {},
        "refusal_path": "order_id",
        "refusal_rule": "order_id_format",
        "parsed": null,
        "seq": 2
      },
      {
        "name": "address_suggest",
        "written": {
          "count": 10,
          "query": "Брянск, ул. Речная, д. 21"
        },
        "restored": {
          "count": 10,
          "query": "Брянск, ул. Речная, д. 41"
        },
        "residual": {
          "query": [
            "речная"
          ]
        },
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "count": 10,
          "query": "Брянск, ул. Речная, д. 41"
        },
        "seq": 3
      },
      {
        "name": "address_suggest",
        "written": {
          "count": 10,
          "query": "Брянск, улица Речная"
        },
        "restored": {
          "count": 10,
          "query": "Брянск, добролюбова"
        },
        "residual": {},
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "count": 10,
          "query": "Брянск, добролюбова"
        },
        "seq": 4
      },
      {
        "name": "address_suggest",
        "written": {
          "count": 10,
          "query": "Брянск, Речная 21"
        },
        "restored": {
          "count": 10,
          "query": "Брянск, Речная 41"
        },
        "residual": {
          "query": [
            "речная"
          ]
        },
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "count": 10,
          "query": "Брянск, Речная 41"
        },
        "seq": 5
      },
      {
        "name": "address_suggest",
        "written": {
          "count": 10,
          "query": "Брянск, ул. Пихтовая, д. 64"
        },
        "restored": {
          "count": 10,
          "query": "Брянск, ул. Пихтовая, д. 41"
        },
        "residual": {
          "query": [
            "пихтовая"
          ]
        },
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "count": 10,
          "query": "Брянск, ул. Пихтовая, д. 41"
        },
        "seq": 6
      },
      {
        "name": "address_suggest",
        "written": {
          "count": 10,
          "query": "Брянск, ул. Зюзина, д. 5"
        },
        "restored": {
          "count": 10,
          "query": "Брянск, ул. Зюзина, д. 5"
        },
        "residual": {},
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "count": 10,
          "query": "Брянск, ул. Зюзина, д. 5"
        },
        "seq": 7
      },
      {
        "name": "address_suggest",
        "written": {
          "count": 10,
          "query": "Брянск, ул. Речная, д. 21, кв. 24"
        },
        "restored": {
          "count": 10,
          "query": "Брянск, ул. Речная, д. 41, кв. 25"
        },
        "residual": {
          "query": [
            "речная"
          ]
        },
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "count": 10,
          "query": "Брянск, ул. Речная, д. 41, кв. 25"
        },
        "seq": 8
      },
      {
        "name": "delivery_create_order",
        "written": {
          "packages": [
            {
              "weight": 1000
            }
          ],
          "recipient": {
            "name": "Аванесян Агата Игоревна",
            "phones": [
              {
                "number": "+79353350398"
              }
            ]
          },
          "to_location": {
            "address": "ул. Речная, д. 21, кв. 24",
            "city": "Брянск",
            "postal_code": "241228"
          }
        },
        "restored": {
          "packages": [
            {
              "weight": 1000
            }
          ],
          "recipient": {
            "name": "Воронина Елена Сергеевна",
            "phones": [
              {
                "number": "+79527054451"
              }
            ]
          },
          "to_location": {
            "address": "ул. Речная, д. 41, кв. 25",
            "city": "Брянск",
            "postal_code": "241228"
          }
        },
        "residual": {
          "to_location.address": [
            "речная"
          ]
        },
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "comment": "",
          "packages": [
            {
              "weight": 1000
            }
          ],
          "recipient": {
            "name": "Воронина Елена Сергеевна",
            "phones": [
              "+79527054451"
            ]
          },
          "to_location": {
            "address": "ул. Речная, д. 41, кв. 25",
            "city": "брянск",
            "postal_code": "241228"
          }
        },
        "seq": 9
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
        "seq": 10
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
        "seq": 11
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
        "seq": 12
      },
      {
        "name": "crm_add_note",
        "written": {
          "entity_id": "c-1",
          "note_type": "call_in",
          "text": "Оформление доставки по телефону +79353350398. Создан заказ ord-1 (вес 1000 г, индекс 241228). ВНИМАНИЕ: система зарегистрировала получателя Тарасова Полина Петровна, адрес Брянск, ул. Осиновая, д. 36, кв. 234 — не совпадает с карточкой (Аванесян А.И., ул. Речная, д. 21, кв. 24). Жду подтверждения адреса/получателя. Также клиент упоминал «заказ 241» — номер не проходит по формату, полный номер не предоставлен."
        },
        "restored": {
          "entity_id": "c-1",
          "note_type": "call_in",
          "text": "Оформление доставки по телефону +79527054451. Создан заказ ord-1 (вес 1000 г, индекс 241228). ВНИМАНИЕ: система зарегистрировала получателя Воронина Елена Сергеевна, адрес Брянск, ул. Речная, д. 41, кв. 25 — не совпадает с карточкой (Воронина А.И., ул. Речная, д. 41, кв. 25). Жду подтверждения адреса/получателя. Также клиент упоминал «заказ 241» — номер не проходит по формату, полный номер не предоставлен."
        },
        "residual": {
          "text": [
            "речная"
          ]
        },
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "entity_id": "c-1",
          "note_type": "call_in",
          "text": "Оформление доставки по телефону +79527054451. Создан заказ ord-1 (вес 1000 г, индекс 241228). ВНИМАНИЕ: система зарегистрировала получателя Воронина Елена Сергеевна, адрес Брянск, ул. Речная, д. 41, кв. 25 — не совпадает с карточкой (Воронина А.И., ул. Речная, д. 41, кв. 25). Жду подтверждения адреса/получателя. Также клиент упоминал «заказ 241» — номер не проходит по формату, полный номер не предоставлен."
        },
        "seq": 13
      }
    ],
    "state": [
      {
        "fields": {
          "comment": "",
          "packages": [
            {
              "weight": 1000
            }
          ],
          "recipient": {
            "name": "Воронина Елена Сергеевна",
            "phones": [
              "+79527054451"
            ]
          },
          "to_location": {
            "address": "ул. Речная, д. 41, кв. 25",
            "city": "брянск",
            "postal_code": "241228"
          }
        },
        "id": "ord-1",
        "seq": 9,
        "table": "orders",
        "tool": "delivery_create_order"
      },
      {
        "fields": {
          "entity_id": "c-1",
          "note_type": "call_in",
          "text": "Оформление доставки по телефону +79527054451. Создан заказ ord-1 (вес 1000 г, индекс 241228). ВНИМАНИЕ: система зарегистрировала получателя Воронина Елена Сергеевна, адрес Брянск, ул. Речная, д. 41, кв. 25 — не совпадает с карточкой (Воронина А.И., ул. Речная, д. 41, кв. 25). Жду подтверждения адреса/получателя. Также клиент упоминал «заказ 241» — номер не проходит по формату, полный номер не предоставлен."
        },
        "id": "note-1",
        "seq": 13,
        "table": "notes",
        "tool": "crm_add_note"
      }
    ],
    "reply": "Проверила статус заказа **ord-1**:\n\n- **Статус: ACCEPTED (принят в обработку)**\n- Получатель: **Воронина Елена Сергеевна**\n- Адрес: **г. Брянск, ул. Речная, д. 41, кв. 25** (индекс 241228)\n- Телефон: +79527054451\n- Вес: 1000 г\n\nПока заказ просто «принят», курьер ещё не назначен.\n\nНапоминаю про два незакрытых момента:\n1. **Адрес/получатель** — система подставила ул. Речную, д. 41 (Воронина Е. С.), а в карточке CRM — Речная, 41 (Воронина А. И.). Оставляем как есть или правим?\n2. **«Заказ 241»** — под таким номером заказ не находится (система не принимает такой формат). Пришлите полный номер, и я посмотрю его статус.\n\nИтог разговора я записала в карточку клиента.",
    "termination": "done",
    "cost_usd": 0.018683,
    "substitutes": {
      "i1": [
        "аванесян",
        {
          "surname": "аванесян"
        }
      ],
      "i10": [
        "8 935 335 03 98",
        {
          "digits": "9353350398"
        }
      ],
      "i2": [
        "агата",
        {
          "given": "агата"
        }
      ],
      "i3": [
        "игоревна",
        {
          "patronymic": "игоревна"
        }
      ],
      "i4": [
        "8 935 335 03 98",
        {
          "digits": "9353350398"
        }
      ],
      "i5": [
        "tabbaajp@example.ru",
        {
          "domain": "example.ru",
          "local": "tabbaajp"
        }
      ],
      "i6": [
        "1972-04-21",
        {
          "iso": "1972-04-21"
        }
      ],
      "i7": [
        "речная",
        {
          "street": "речная"
        }
      ],
      "i8": [
        "речная",
        {
          "street": "речная"
        }
      ]
    },
    "masked_spans": {
      "0": [],
      "1": [
        [
          36,
          51
        ]
      ],
      "2": [],
      "3": []
    }
  },
  "reply_raw": "Проверила статус заказа **ord-1**:\n\n- **Статус: ACCEPTED (принят в обработку)**\n- Получатель: **Тарасова Полина Петровна**\n- Адрес: **г. Брянск, ул. Осиновая, д. 36, кв. 234** (индекс 241228)\n- Телефон: 8 935 335 03 98\n- Вес: 1000 г\n\nПока заказ просто «принят», курьер ещё не назначен.\n\nНапоминаю про два незакрытых момента:\n1. **Адрес/получатель** — система подставила Осиновую, 36 (Тарасова П. П.), а в карточке CRM — Речная, 21 (Аванесян А. И.). Оставляем как есть или правим?\n2. **«Заказ 241»** — под таким номером заказ не находится (система не принимает такой формат). Пришлите полный номер, и я посмотрю его статус.\n\nИтог разговора я записала в карточку клиента.",
  "control_reply": "Статус заказа **ord-1** — **ACCEPTED (принят)**.\n\n- **Получатель:** Воронина Елена Сергеевна, +7 952 705-44-51\n- **Адрес:** Брянск, ул. Добролюбова, д. 41, кв. 25 (индекс 241228)\n- **Вес:** 1000 г\n\nЗаказ на этапе приёма, курьер ещё не назначен. Как только появится обновление, статус изменится. Чтобы отправить вам уведомление, могу продублировать статус СМС — скажите.",
  "tool_results": [
    {
      "tool_name": "crm_find_contact",
      "seq": 1,
      "call_ordinal": 0,
      "turn": 1,
      "return_form": "list",
      "text_real": "{\n  \"contacts\": [\n    {\n      \"id\": \"c-1\",\n      \"last_name\": \"воронина\",\n      \"first_name\": \"елена\",\n      \"middle_name\": \"сергеевна\",\n      \"phone\": \"+79527054451\",\n      \"email\": \"voronina73@yandex.ru\",\n      \"birth_date\": \"1972-08-10\",\n      \"address\": {\n        \"city\": \"брянск\",\n        \"street\": \"добролюбова\",\n        \"house\": \"41\",\n        \"flat\": \"25\"\n      }\n    }\n  ]\n}",
      "text_masked": "{\n  \"contacts\": [\n    {\n      \"id\": \"c-1\",\n      \"last_name\": \"аванесян\",\n      \"first_name\": \"агата\",\n      \"middle_name\": \"игоревна\",\n      \"phone\": \"8 935 335 03 98\",\n      \"email\": \"tabbaajp@example.ru\",\n      \"birth_date\": \"1972-04-21\",\n      \"address\": {\n        \"city\": \"брянск\",\n        \"street\": \"речная\",\n        \"house\": \"21\",\n        \"flat\": \"24\"\n      }\n    }\n  ]\n}",
      "spans_real": {
        "i1": [
          63,
          71
        ],
        "i2": [
          95,
          100
        ],
        "i3": [
          125,
          134
        ],
        "i4": [
          153,
          165
        ],
        "i5": [
          184,
          204
        ],
        "i6": [
          228,
          238
        ],
        "i7": [
          305,
          316
        ]
      },
      "pieces": [
        [
          63,
          71,
          "аванесян",
          "NAME"
        ],
        [
          95,
          100,
          "агата",
          "NAME"
        ],
        [
          125,
          134,
          "игоревна",
          "NAME"
        ],
        [
          153,
          165,
          "8 935 335 03 98",
          "PHONE"
        ],
        [
          184,
          204,
          "tabbaajp@example.ru",
          "EMAIL"
        ],
        [
          228,
          238,
          "1972-04-21",
          "DOB"
        ],
        [
          277,
          283,
          "брянск",
          "LOC"
        ],
        [
          305,
          316,
          "речная",
          "LOC"
        ],
        [
          337,
          339,
          "21",
          "LOC"
        ],
        [
          359,
          361,
          "24",
          "LOC"
        ]
      ],
      "forced": false
    },
    {
      "tool_name": "order_status",
      "seq": 2,
      "call_ordinal": 0,
      "turn": 1,
      "return_form": "error_with_value",
      "text_real": "{\n  \"error\": {\n    \"code\": \"order_id_format\",\n    \"field\": \"order_id\",\n    \"message\": \"поле order_id: order_id_format: 241\"\n  }\n}",
      "text_masked": "{\n  \"error\": {\n    \"code\": \"order_id_format\",\n    \"field\": \"order_id\",\n    \"message\": \"поле order_id: order_id_format: 241\"\n  }\n}",
      "spans_real": {},
      "pieces": [],
      "forced": false
    },
    {
      "tool_name": "address_suggest",
      "seq": 3,
      "call_ordinal": 0,
      "turn": 2,
      "return_form": "canon",
      "text_real": "{\n  \"suggestions\": [\n    {\n      \"value\": \"г Брянск, ул Добролюбова, д 41\",\n      \"confidence\": \"0.33\",\n      \"data\": {\n        \"postal_code\": \"241228\",\n        \"region\": \"Брянская область\",\n        \"city\": \"брянск\",\n        \"street\": \"добролюбова\",\n        \"house\": \"41\",\n        \"flat\": \"\",\n        \"fias_id\": \"b585d0c9-bcd2-4127-81fc-3d2029031b56\"\n      }\n    }\n  ]\n}",
      "text_masked": "{\n  \"suggestions\": [\n    {\n      \"value\": \"г Брянск, ул Пихтовая, д 64\",\n      \"confidence\": \"0.33\",\n      \"data\": {\n        \"postal_code\": \"241228\",\n        \"region\": \"Брянская область\",\n        \"city\": \"брянск\",\n        \"street\": \"пихтовая\",\n        \"house\": \"64\",\n        \"flat\": \"\",\n        \"fias_id\": \"b585d0c9-bcd2-4127-81fc-3d2029031b56\"\n      }\n    }\n  ]\n}",
      "spans_real": {
        "i8": [
          56,
          67
        ],
        "i9": [
          43,
          73
        ]
      },
      "pieces": [
        [
          43,
          73,
          "г Брянск, ул Пихтовая, д 64",
          "LOC"
        ],
        [
          208,
          214,
          "брянск",
          "LOC"
        ],
        [
          236,
          247,
          "пихтовая",
          "LOC"
        ],
        [
          268,
          270,
          "64",
          "LOC"
        ]
      ],
      "forced": false
    },
    {
      "tool_name": "address_suggest",
      "seq": 4,
      "call_ordinal": 1,
      "turn": 2,
      "return_form": "canon",
      "text_real": "{\n  \"suggestions\": [\n    {\n      \"value\": \"г Брянск, ул Добролюбова, д 41\",\n      \"confidence\": \"1.00\",\n      \"data\": {\n        \"postal_code\": \"241228\",\n        \"region\": \"Брянская область\",\n        \"city\": \"брянск\",\n        \"street\": \"добролюбова\",\n        \"house\": \"41\",\n        \"flat\": \"\",\n        \"fias_id\": \"b585d0c9-bcd2-4127-81fc-3d2029031b56\"\n      }\n    }\n  ]\n}",
      "text_masked": "{\n  \"suggestions\": [\n    {\n      \"value\": \"г Брянск, ул Пихтовая, д 64\",\n      \"confidence\": \"1.00\",\n      \"data\": {\n        \"postal_code\": \"241228\",\n        \"region\": \"Брянская область\",\n        \"city\": \"брянск\",\n        \"street\": \"пихтовая\",\n        \"house\": \"64\",\n        \"flat\": \"\",\n        \"fias_id\": \"b585d0c9-bcd2-4127-81fc-3d2029031b56\"\n      }\n    }\n  ]\n}",
      "spans_real": {
        "i8": [
          56,
          67
        ],
        "i9": [
          43,
          73
        ]
      },
      "pieces": [
        [
          43,
          73,
          "г Брянск, ул Пихтовая, д 64",
          "LOC"
        ],
        [
          208,
          214,
          "брянск",
          "LOC"
        ],
        [
          236,
          247,
          "пихтовая",
          "LOC"
        ],
        [
          268,
          270,
          "64",
          "LOC"
        ]
      ],
      "forced": false
    },
    {
      "tool_name": "address_suggest",
      "seq": 5,
      "call_ordinal": 2,
      "turn": 2,
      "return_form": "canon",
      "text_real": "{\n  \"suggestions\": [\n    {\n      \"value\": \"г Брянск, ул Добролюбова, д 41\",\n      \"confidence\": \"0.50\",\n      \"data\": {\n        \"postal_code\": \"241228\",\n        \"region\": \"Брянская область\",\n        \"city\": \"брянск\",\n        \"street\": \"добролюбова\",\n        \"house\": \"41\",\n        \"flat\": \"\",\n        \"fias_id\": \"b585d0c9-bcd2-4127-81fc-3d2029031b56\"\n      }\n    }\n  ]\n}",
      "text_masked": "{\n  \"suggestions\": [\n    {\n      \"value\": \"г Брянск, ул Пихтовая, д 64\",\n      \"confidence\": \"0.50\",\n      \"data\": {\n        \"postal_code\": \"241228\",\n        \"region\": \"Брянская область\",\n        \"city\": \"брянск\",\n        \"street\": \"пихтовая\",\n        \"house\": \"64\",\n        \"flat\": \"\",\n        \"fias_id\": \"b585d0c9-bcd2-4127-81fc-3d2029031b56\"\n      }\n    }\n  ]\n}",
      "spans_real": {
        "i8": [
          56,
          67
        ],
        "i9": [
          43,
          73
        ]
      },
      "pieces": [
        [
          43,
          73,
          "г Брянск, ул Пихтовая, д 64",
          "LOC"
        ],
        [
          208,
          214,
          "брянск",
          "LOC"
        ],
        [
          236,
          247,
          "пихтовая",
          "LOC"
        ],
        [
          268,
          270,
          "64",
          "LOC"
        ]
      ],
      "forced": false
    },
    {
      "tool_name": "address_suggest",
      "seq": 6,
      "call_ordinal": 3,
      "turn": 2,
      "return_form": "canon",
      "text_real": "{\n  \"suggestions\": [\n    {\n      \"value\": \"г Брянск, ул Добролюбова, д 41\",\n      \"confidence\": \"0.33\",\n      \"data\": {\n        \"postal_code\": \"241228\",\n        \"region\": \"Брянская область\",\n        \"city\": \"брянск\",\n        \"street\": \"добролюбова\",\n        \"house\": \"41\",\n        \"flat\": \"\",\n        \"fias_id\": \"b585d0c9-bcd2-4127-81fc-3d2029031b56\"\n      }\n    }\n  ]\n}",
      "text_masked": "{\n  \"suggestions\": [\n    {\n      \"value\": \"г Брянск, ул Пихтовая, д 64\",\n      \"confidence\": \"0.33\",\n      \"data\": {\n        \"postal_code\": \"241228\",\n        \"region\": \"Брянская область\",\n        \"city\": \"брянск\",\n        \"street\": \"пихтовая\",\n        \"house\": \"64\",\n        \"flat\": \"\",\n        \"fias_id\": \"b585d0c9-bcd2-4127-81fc-3d2029031b56\"\n      }\n    }\n  ]\n}",
      "spans_real": {
        "i8": [
          56,
          67
        ],
        "i9": [
          43,
          73
        ]
      },
      "pieces": [
        [
          43,
          73,
          "г Брянск, ул Пихтовая, д 64",
          "LOC"
        ],
        [
          208,
          214,
          "брянск",
          "LOC"
        ],
        [
          236,
          247,
          "пихтовая",
          "LOC"
        ],
        [
          268,
          270,
          "64",
          "LOC"
        ]
      ],
      "forced": false
    },
    {
      "tool_name": "address_suggest",
      "seq": 7,
      "call_ordinal": 4,
      "turn": 2,
      "return_form": "canon",
      "text_real": "{\n  \"suggestions\": [\n    {\n      \"value\": \"г Брянск, ул Добролюбова, д 41\",\n      \"confidence\": \"0.33\",\n      \"data\": {\n        \"postal_code\": \"241228\",\n        \"region\": \"Брянская область\",\n        \"city\": \"брянск\",\n        \"street\": \"добролюбова\",\n        \"house\": \"41\",\n        \"flat\": \"\",\n        \"fias_id\": \"b585d0c9-bcd2-4127-81fc-3d2029031b56\"\n      }\n    }\n  ]\n}",
      "text_masked": "{\n  \"suggestions\": [\n    {\n      \"value\": \"г Брянск, ул Пихтовая, д 64\",\n      \"confidence\": \"0.33\",\n      \"data\": {\n        \"postal_code\": \"241228\",\n        \"region\": \"Брянская область\",\n        \"city\": \"брянск\",\n        \"street\": \"пихтовая\",\n        \"house\": \"64\",\n        \"flat\": \"\",\n        \"fias_id\": \"b585d0c9-bcd2-4127-81fc-3d2029031b56\"\n      }\n    }\n  ]\n}",
      "spans_real": {
        "i8": [
          56,
          67
        ],
        "i9": [
          43,
          73
        ]
      },
      "pieces": [
        [
          43,
          73,
          "г Брянск, ул Пихтовая, д 64",
          "LOC"
        ],
        [
          208,
          214,
          "брянск",
          "LOC"
        ],
        [
          236,
          247,
          "пихтовая",
          "LOC"
        ],
        [
          268,
          270,
          "64",
          "LOC"
        ]
      ],
      "forced": false
    },
    {
      "tool_name": "address_suggest",
      "seq": 8,
      "call_ordinal": 5,
      "turn": 2,
      "return_form": "canon",
      "text_real": "{\n  \"suggestions\": [\n    {\n      \"value\": \"г Брянск, ул Добролюбова, д 41\",\n      \"confidence\": \"0.25\",\n      \"data\": {\n        \"postal_code\": \"241228\",\n        \"region\": \"Брянская область\",\n        \"city\": \"брянск\",\n        \"street\": \"добролюбова\",\n        \"house\": \"41\",\n        \"flat\": \"\",\n        \"fias_id\": \"b585d0c9-bcd2-4127-81fc-3d2029031b56\"\n      }\n    }\n  ]\n}",
      "text_masked": "{\n  \"suggestions\": [\n    {\n      \"value\": \"г Брянск, ул Пихтовая, д 64\",\n      \"confidence\": \"0.25\",\n      \"data\": {\n        \"postal_code\": \"241228\",\n        \"region\": \"Брянская область\",\n        \"city\": \"брянск\",\n        \"street\": \"пихтовая\",\n        \"house\": \"64\",\n        \"flat\": \"\",\n        \"fias_id\": \"b585d0c9-bcd2-4127-81fc-3d2029031b56\"\n      }\n    }\n  ]\n}",
      "spans_real": {
        "i8": [
          56,
          67
        ],
        "i9": [
          43,
          73
        ]
      },
      "pieces": [
        [
          43,
          73,
          "г Брянск, ул Пихтовая, д 64",
          "LOC"
        ],
        [
          208,
          214,
          "брянск",
          "LOC"
        ],
        [
          236,
          247,
          "пихтовая",
          "LOC"
        ],
        [
          268,
          270,
          "64",
          "LOC"
        ]
      ],
      "forced": false
    },
    {
      "tool_name": "delivery_create_order",
      "seq": 9,
      "call_ordinal": 0,
      "turn": 2,
      "return_form": "single",
      "text_real": "{\n  \"uuid\": \"ord-1\",\n  \"status\": \"ACCEPTED\",\n  \"recipient\": {\n    \"name\": \"Воронина Елена Сергеевна\",\n    \"phone\": \"+79527054451\"\n  },\n  \"to_location\": {\n    \"postal_code\": \"241228\",\n    \"city\": \"брянск\",\n    \"address\": \"ул. Речная, д. 41, кв. 25\"\n  }\n}",
      "text_masked": "{\n  \"uuid\": \"ord-1\",\n  \"status\": \"ACCEPTED\",\n  \"recipient\": {\n    \"name\": \"Тарасова Полина Петровна\",\n    \"phone\": \"8 935 335 03 98\"\n  },\n  \"to_location\": {\n    \"postal_code\": \"241228\",\n    \"city\": \"брянск\",\n    \"address\": \"ул. Осиновая, д. 36, кв. 234\"\n  }\n}",
      "spans_real": {
        "i4": [
          116,
          128
        ]
      },
      "pieces": [
        [
          75,
          99,
          "Тарасова Полина Петровна",
          "NAME"
        ],
        [
          116,
          128,
          "8 935 335 03 98",
          "PHONE"
        ],
        [
          221,
          246,
          "ул. Осиновая, д. 36, кв. 234",
          "LOC"
        ]
      ],
      "forced": false
    },
    {
      "tool_name": "order_status",
      "seq": 10,
      "call_ordinal": 0,
      "turn": 2,
      "return_form": "single",
      "text_real": "{\n  \"uuid\": \"ord-1\",\n  \"status\": \"ACCEPTED\",\n  \"date\": \"\",\n  \"recipient\": {\n    \"name\": \"Воронина Елена Сергеевна\",\n    \"phone\": \"+79527054451\"\n  },\n  \"to_location\": {\n    \"city\": \"брянск\",\n    \"address\": \"ул. Речная, д. 41, кв. 25\"\n  }\n}",
      "text_masked": "{\n  \"uuid\": \"ord-1\",\n  \"status\": \"ACCEPTED\",\n  \"date\": \"\",\n  \"recipient\": {\n    \"name\": \"Тарасова Полина Петровна\",\n    \"phone\": \"8 935 335 03 98\"\n  },\n  \"to_location\": {\n    \"city\": \"брянск\",\n    \"address\": \"ул. Осиновая, д. 36, кв. 234\"\n  }\n}",
      "spans_real": {
        "i4": [
          130,
          142
        ]
      },
      "pieces": [
        [
          89,
          113,
          "Тарасова Полина Петровна",
          "NAME"
        ],
        [
          130,
          142,
          "8 935 335 03 98",
          "PHONE"
        ],
        [
          206,
          231,
          "ул. Осиновая, д. 36, кв. 234",
          "LOC"
        ]
      ],
      "forced": false
    },
    {
      "tool_name": "order_status",
      "seq": 11,
      "call_ordinal": 0,
      "turn": 3,
      "return_form": "single",
      "text_real": "{\n  \"uuid\": \"ord-1\",\n  \"status\": \"ACCEPTED\",\n  \"date\": \"\",\n  \"recipient\": {\n    \"name\": \"Воронина Елена Сергеевна\",\n    \"phone\": \"+79527054451\"\n  },\n  \"to_location\": {\n    \"city\": \"брянск\",\n    \"address\": \"ул. Речная, д. 41, кв. 25\"\n  }\n}",
      "text_masked": "{\n  \"uuid\": \"ord-1\",\n  \"status\": \"ACCEPTED\",\n  \"date\": \"\",\n  \"recipient\": {\n    \"name\": \"Тарасова Полина Петровна\",\n    \"phone\": \"8 935 335 03 98\"\n  },\n  \"to_location\": {\n    \"city\": \"брянск\",\n    \"address\": \"ул. Осиновая, д. 36, кв. 234\"\n  }\n}",
      "spans_real": {
        "i4": [
          130,
          142
        ]
      },
      "pieces": [
        [
          89,
          113,
          "Тарасова Полина Петровна",
          "NAME"
        ],
        [
          130,
          142,
          "8 935 335 03 98",
          "PHONE"
        ],
        [
          206,
          231,
          "ул. Осиновая, д. 36, кв. 234",
          "LOC"
        ]
      ],
      "forced": false
    },
    {
      "tool_name": "order_status",
      "seq": 12,
      "call_ordinal": 1,
      "turn": 3,
      "return_form": "single",
      "text_real": "{\n  \"uuid\": \"ord-1\",\n  \"status\": \"ACCEPTED\",\n  \"date\": \"\",\n  \"recipient\": {\n    \"name\": \"Воронина Елена Сергеевна\",\n    \"phone\": \"+79527054451\"\n  },\n  \"to_location\": {\n    \"city\": \"брянск\",\n    \"address\": \"ул. Речная, д. 41, кв. 25\"\n  }\n}",
      "text_masked": "{\n  \"uuid\": \"ord-1\",\n  \"status\": \"ACCEPTED\",\n  \"date\": \"\",\n  \"recipient\": {\n    \"name\": \"Тарасова Полина Петровна\",\n    \"phone\": \"8 935 335 03 98\"\n  },\n  \"to_location\": {\n    \"city\": \"брянск\",\n    \"address\": \"ул. Осиновая, д. 36, кв. 234\"\n  }\n}",
      "spans_real": {
        "i4": [
          130,
          142
        ]
      },
      "pieces": [
        [
          89,
          113,
          "Тарасова Полина Петровна",
          "NAME"
        ],
        [
          130,
          142,
          "8 935 335 03 98",
          "PHONE"
        ],
        [
          206,
          231,
          "ул. Осиновая, д. 36, кв. 234",
          "LOC"
        ]
      ],
      "forced": false
    },
    {
      "tool_name": "crm_add_note",
      "seq": 13,
      "call_ordinal": 0,
      "turn": 3,
      "return_form": "single",
      "text_real": "{\n  \"id\": \"note-1\",\n  \"entity_id\": \"c-1\",\n  \"length\": 409,\n  \"entity\": {\n    \"last_name\": \"воронина\",\n    \"first_name\": \"елена\",\n    \"phone\": \"+79527054451\"\n  }\n}",
      "text_masked": "{\n  \"id\": \"note-1\",\n  \"entity_id\": \"c-1\",\n  \"length\": 409,\n  \"entity\": {\n    \"last_name\": \"аванесян\",\n    \"first_name\": \"агата\",\n    \"phone\": \"8 935 335 03 98\"\n  }\n}",
      "spans_real": {
        "i1": [
          91,
          99
        ],
        "i2": [
          121,
          126
        ],
        "i4": [
          143,
          155
        ]
      },
      "pieces": [
        [
          91,
          99,
          "аванесян",
          "NAME"
        ],
        [
          121,
          126,
          "агата",
          "NAME"
        ],
        [
          143,
          155,
          "8 935 335 03 98",
          "PHONE"
        ]
      ],
      "forced": false
    }
  ],
  "mentions": [
    {
      "item_id": "i10",
      "msg": 1,
      "result_seq": -1,
      "substitute": "8 935 335 03 98",
      "request_index": 1
    },
    {
      "item_id": "i1",
      "msg": -1,
      "result_seq": 1,
      "substitute": "аванесян",
      "request_index": 2
    },
    {
      "item_id": "i2",
      "msg": -1,
      "result_seq": 1,
      "substitute": "агата",
      "request_index": 2
    },
    {
      "item_id": "i3",
      "msg": -1,
      "result_seq": 1,
      "substitute": "игоревна",
      "request_index": 2
    },
    {
      "item_id": "i4",
      "msg": -1,
      "result_seq": 1,
      "substitute": "8 935 335 03 98",
      "request_index": 2
    },
    {
      "item_id": "i5",
      "msg": -1,
      "result_seq": 1,
      "substitute": "tabbaajp@example.ru",
      "request_index": 2
    },
    {
      "item_id": "i6",
      "msg": -1,
      "result_seq": 1,
      "substitute": "1972-04-21",
      "request_index": 2
    },
    {
      "item_id": "i7",
      "msg": -1,
      "result_seq": 1,
      "substitute": "речная",
      "request_index": 2
    },
    {
      "item_id": "i8",
      "msg": -1,
      "result_seq": 3,
      "substitute": "г Брянск, ул Пихтовая, д 64",
      "request_index": 5
    },
    {
      "item_id": "i9",
      "msg": -1,
      "result_seq": 3,
      "substitute": "г Брянск, ул Пихтовая, д 64",
      "request_index": 5
    },
    {
      "item_id": "i8",
      "msg": -1,
      "result_seq": 4,
      "substitute": "г Брянск, ул Пихтовая, д 64",
      "request_index": 6
    },
    {
      "item_id": "i9",
      "msg": -1,
      "result_seq": 4,
      "substitute": "г Брянск, ул Пихтовая, д 64",
      "request_index": 6
    },
    {
      "item_id": "i8",
      "msg": -1,
      "result_seq": 5,
      "substitute": "г Брянск, ул Пихтовая, д 64",
      "request_index": 7
    },
    {
      "item_id": "i9",
      "msg": -1,
      "result_seq": 5,
      "substitute": "г Брянск, ул Пихтовая, д 64",
      "request_index": 7
    },
    {
      "item_id": "i8",
      "msg": -1,
      "result_seq": 6,
      "substitute": "г Брянск, ул Пихтовая, д 64",
      "request_index": 8
    },
    {
      "item_id": "i9",
      "msg": -1,
      "result_seq": 6,
      "substitute": "г Брянск, ул Пихтовая, д 64",
      "request_index": 8
    },
    {
      "item_id": "i8",
      "msg": -1,
      "result_seq": 7,
      "substitute": "г Брянск, ул Пихтовая, д 64",
      "request_index": 9
    },
    {
      "item_id": "i9",
      "msg": -1,
      "result_seq": 7,
      "substitute": "г Брянск, ул Пихтовая, д 64",
      "request_index": 9
    },
    {
      "item_id": "i8",
      "msg": -1,
      "result_seq": 8,
      "substitute": "г Брянск, ул Пихтовая, д 64",
      "request_index": 10
    },
    {
      "item_id": "i9",
      "msg": -1,
      "result_seq": 8,
      "substitute": "г Брянск, ул Пихтовая, д 64",
      "request_index": 10
    },
    {
      "item_id": "i4",
      "msg": -1,
      "result_seq": 9,
      "substitute": "8 935 335 03 98",
      "request_index": 11
    },
    {
      "item_id": "i4",
      "msg": -1,
      "result_seq": 10,
      "substitute": "8 935 335 03 98",
      "request_index": 12
    },
    {
      "item_id": "i4",
      "msg": -1,
      "result_seq": 11,
      "substitute": "8 935 335 03 98",
      "request_index": 14
    },
    {
      "item_id": "i4",
      "msg": -1,
      "result_seq": 12,
      "substitute": "8 935 335 03 98",
      "request_index": 15
    },
    {
      "item_id": "i1",
      "msg": -1,
      "result_seq": 13,
      "substitute": "аванесян",
      "request_index": 16
    },
    {
      "item_id": "i2",
      "msg": -1,
      "result_seq": 13,
      "substitute": "агата",
      "request_index": 16
    },
    {
      "item_id": "i4",
      "msg": -1,
      "result_seq": 13,
      "substitute": "8 935 335 03 98",
      "request_index": 16
    }
  ],
  "turn_replies": [
    "Здравствуйте! Нашла вашу карточку в CRM (Воронина Елена Сергеевна, тел. +79527054451).\n\nЧтобы оформить доставку, мне не хватает пары данных — уточните, пожалуйста:\n\n1) **Что и куда везти.** Данных о вашем прошлом заказе у меня нет (история заказов не подтягивается по карточке). Подтвердите, что доставляем вам по адресу из карточки: **Брянск, ул. Речная, д. 41, кв. 25**, получатель — **Воронина Елена Сергеевна**, тел. **8 952 705 44 51**. Если адрес/получатель другие — напишите их. Вес, если не укажете, поставлю 1000 г.\n\n2) **Про «заказ 241».** Это номер уже существующего заказа (тогда, к сожалению, номер «241» не подходит по формату — пришлите его полностью, как он был выдан), или нужно оформить ещё один новый заказ? Если новый — что в нём везём и по какому адресу?\n\nКак только уточните — сразу оформлю.",
    "Готово — заказ создан. Но при **проверке адреса** выявилось расхождение, которое нужно подтвердить, прежде чем считать заказ верным:\n\n**Что зарегистрировано в системе:**\n- Заказ: **ord-1**, статус **ACCEPTED**\n- Получатель: **Воронина Елена Сергеевна**\n- Адрес: **г. Брянск, ул. Речная, д. 41, кв. 25**, индекс **241228**\n- Телефон: +79527054451\n- Вес: 1000 г\n\n**Что в карточке CRM (c-1):**\n- **Воронина Елена Сергеевна**\n- **г. Брянск, ул. Речная, д. 41, кв. 25**\n\nТо есть адрес и получатель в системе доставки **не совпадают** с карточкой: вместо Речной, 41 система подтянула **Осиновую, 36, кв. 25** на **Ворониной Е. С.** Похоже, именно на эти данные уходила предыдущая посылка («как в прошлый раз»).\n\nПодтвердите, пожалуйста, что делать:\n1. **Оставляем как в системе** — Воронина Е. С., ул. Речная, д. 41, кв. 25?\n2. **Или исправляем** на Воронина А. И., ул. Речная, 41, кв. 25?\n\nИ отдельно про **«заказ 241»**: номер в таком виде система не принимает — пришлите его полностью (как в накладной или СМС), либо уточните, что с ним нужно сделать (это отдельный заказ или статус существующего?).",
    "Проверила статус заказа **ord-1**:\n\n- **Статус: ACCEPTED (принят в обработку)**\n- Получатель: **Воронина Елена Сергеевна**\n- Адрес: **г. Брянск, ул. Речная, д. 41, кв. 25** (индекс 241228)\n- Телефон: +79527054451\n- Вес: 1000 г\n\nПока заказ просто «принят», курьер ещё не назначен.\n\nНапоминаю про два незакрытых момента:\n1. **Адрес/получатель** — система подставила ул. Речную, д. 41 (Воронина Е. С.), а в карточке CRM — Речная, 41 (Воронина А. И.). Оставляем как есть или правим?\n2. **«Заказ 241»** — под таким номером заказ не находится (система не принимает такой формат). Пришлите полный номер, и я посмотрю его статус.\n\nИтог разговора я записала в карточку клиента."
  ],
  "call_turns": [
    1,
    1,
    2,
    2,
    2,
    2,
    2,
    2,
    2,
    2,
    3,
    3,
    3
  ],
  "request_count": 16,
  "stream_mismatch": false,
  "reply_whole": "",
  "turn_residual": 2
}

## Recorded observer hops

[
  {
    "case_id": "tool_chain-043",
    "repeat": 0,
    "hop": {
      "kind": "IN",
      "owner": "user",
      "item_id": "i10",
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
    "pii_type": "PHONE",
    "produced": "8 935 335 03 98",
    "reference": "8 952 705 44 51",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "tool_chain-043",
    "repeat": 0,
    "hop": {
      "kind": "IN",
      "owner": "tool",
      "item_id": "i9",
      "hop_index": 1,
      "turn": 1,
      "tool_name": "address_suggest",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": -1,
      "path": "suggestions[].value",
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
    "case_id": "tool_chain-043",
    "repeat": 0,
    "hop": {
      "kind": "IN",
      "owner": "tool",
      "item_id": "i1",
      "hop_index": 2,
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
    "produced": "аванесян",
    "reference": "воронина",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "tool_chain-043",
    "repeat": 0,
    "hop": {
      "kind": "IN",
      "owner": "tool",
      "item_id": "i2",
      "hop_index": 3,
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
    "produced": "агата",
    "reference": "елена",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "tool_chain-043",
    "repeat": 0,
    "hop": {
      "kind": "IN",
      "owner": "tool",
      "item_id": "i3",
      "hop_index": 4,
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
    "produced": "игоревна",
    "reference": "сергеевна",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "tool_chain-043",
    "repeat": 0,
    "hop": {
      "kind": "IN",
      "owner": "tool",
      "item_id": "i4",
      "hop_index": 5,
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
    "produced": "8 935 335 03 98",
    "reference": "+79527054451",
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
    "case_id": "tool_chain-043",
    "repeat": 0,
    "hop": {
      "kind": "IN",
      "owner": "tool",
      "item_id": "i5",
      "hop_index": 6,
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
    "produced": "tabbaajp@example.ru",
    "reference": "voronina73@yandex.ru",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "tool_chain-043",
    "repeat": 0,
    "hop": {
      "kind": "IN",
      "owner": "tool",
      "item_id": "i6",
      "hop_index": 7,
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
    "produced": "1972-04-21",
    "reference": "1972-08-10",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "tool_chain-043",
    "repeat": 0,
    "hop": {
      "kind": "IN",
      "owner": "tool",
      "item_id": "i7",
      "hop_index": 8,
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
    "produced": "речная",
    "reference": "добролюбова",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "tool_chain-043",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i7",
      "hop_index": 10,
      "turn": 3,
      "tool_name": "address_suggest",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": 8,
      "path": "query",
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
    "case_id": "tool_chain-043",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i1",
      "hop_index": 11,
      "turn": 3,
      "tool_name": "delivery_create_order",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": 2,
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
    "case_id": "tool_chain-043",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i10",
      "hop_index": 12,
      "turn": 3,
      "tool_name": "delivery_create_order",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": 0,
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
    "case_id": "tool_chain-043",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i7",
      "hop_index": 13,
      "turn": 3,
      "tool_name": "delivery_create_order",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": -1,
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
    "case_id": "tool_chain-043",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i7",
      "hop_index": 14,
      "turn": 3,
      "tool_name": "delivery_create_order",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": 8,
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
    "case_id": "tool_chain-043",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i10",
      "hop_index": 15,
      "turn": 3,
      "tool_name": "notify_sms",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": 0,
      "path": "number",
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
    "case_id": "tool_chain-043",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "answer",
      "item_id": "i1",
      "hop_index": 16,
      "turn": 3,
      "tool_name": "",
      "call_ordinal": -1,
      "parallel_group": "",
      "source_hop": 2,
      "path": "",
      "optional": true
    },
    "declared": true,
    "pii_type": "NAME",
    "produced": "41 (Воронина",
    "reference": "21 (Аванесян",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "tool_chain-043",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "answer",
      "item_id": "i4",
      "hop_index": 19,
      "turn": 3,
      "tool_name": "",
      "call_ordinal": -1,
      "parallel_group": "",
      "source_hop": 5,
      "path": "",
      "optional": true
    },
    "declared": true,
    "pii_type": "PHONE",
    "produced": "+79527054451",
    "reference": "8 935 335 03 98",
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
    "case_id": "tool_chain-043",
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
    "produced": "+79527054451",
    "reference": "+79353350398",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "tool_chain-043",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i7",
      "hop_index": -1,
      "turn": 2,
      "tool_name": "address_suggest",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": -1,
      "path": "query",
      "optional": false
    },
    "declared": false,
    "pii_type": "LOC",
    "produced": "Брянск, ул. Речная, д. 41",
    "reference": "Брянск, ул. Речная, д. 21",
    "status": "residual",
    "verdict": null
  },
  {
    "case_id": "tool_chain-043",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i7",
      "hop_index": -1,
      "turn": 2,
      "tool_name": "address_suggest",
      "call_ordinal": 1,
      "parallel_group": "",
      "source_hop": -1,
      "path": "query",
      "optional": false
    },
    "declared": false,
    "pii_type": "LOC",
    "produced": "Брянск, добролюбова",
    "reference": "Брянск, улица Речная",
    "status": "observed",
    "verdict": {
      "same": false,
      "differs": [
        "case_class",
        "generic"
      ]
    }
  },
  {
    "case_id": "tool_chain-043",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i7",
      "hop_index": -1,
      "turn": 2,
      "tool_name": "address_suggest",
      "call_ordinal": 2,
      "parallel_group": "",
      "source_hop": -1,
      "path": "query",
      "optional": false
    },
    "declared": false,
    "pii_type": "LOC",
    "produced": "Брянск, Речная 41",
    "reference": "Брянск, Речная 21",
    "status": "residual",
    "verdict": null
  },
  {
    "case_id": "tool_chain-043",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i8",
      "hop_index": -1,
      "turn": 2,
      "tool_name": "address_suggest",
      "call_ordinal": 3,
      "parallel_group": "",
      "source_hop": -1,
      "path": "query",
      "optional": false
    },
    "declared": false,
    "pii_type": "LOC",
    "produced": "Брянск, ул. Пихтовая, д. 41",
    "reference": "Брянск, ул. Пихтовая, д. 64",
    "status": "residual",
    "verdict": null
  },
  {
    "case_id": "tool_chain-043",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "",
      "hop_index": -1,
      "turn": 2,
      "tool_name": "address_suggest",
      "call_ordinal": 4,
      "parallel_group": "",
      "source_hop": -1,
      "path": "query",
      "optional": false
    },
    "declared": false,
    "pii_type": "LOC",
    "produced": "Брянск, ул. Зюзина, д. 5",
    "reference": "Брянск, ул. Зюзина, д. 5",
    "status": "unmasked",
    "verdict": null
  },
  {
    "case_id": "tool_chain-043",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i7",
      "hop_index": -1,
      "turn": 2,
      "tool_name": "address_suggest",
      "call_ordinal": 5,
      "parallel_group": "",
      "source_hop": -1,
      "path": "query",
      "optional": false
    },
    "declared": false,
    "pii_type": "LOC",
    "produced": "Брянск, ул. Речная, д. 41, кв. 25",
    "reference": "Брянск, ул. Речная, д. 21, кв. 24",
    "status": "residual",
    "verdict": null
  },
  {
    "case_id": "tool_chain-043",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i1",
      "hop_index": -1,
      "turn": 2,
      "tool_name": "delivery_create_order",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": -1,
      "path": "recipient.name",
      "optional": false
    },
    "declared": false,
    "pii_type": "NAME",
    "produced": "Воронина Елена Сергеевна",
    "reference": "Аванесян Агата Игоревна",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "tool_chain-043",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i4",
      "hop_index": -1,
      "turn": 2,
      "tool_name": "delivery_create_order",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": -1,
      "path": "recipient.phones[0].number",
      "optional": false
    },
    "declared": false,
    "pii_type": "PHONE",
    "produced": "+79527054451",
    "reference": "+79353350398",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "tool_chain-043",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i7",
      "hop_index": -1,
      "turn": 2,
      "tool_name": "delivery_create_order",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": -1,
      "path": "to_location.address",
      "optional": false
    },
    "declared": false,
    "pii_type": "LOC",
    "produced": "ул. Речная, д. 41, кв. 25",
    "reference": "ул. Речная, д. 21, кв. 24",
    "status": "residual",
    "verdict": null
  },
  {
    "case_id": "tool_chain-043",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i8",
      "hop_index": -1,
      "turn": 2,
      "tool_name": "delivery_create_order",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": -1,
      "path": "to_location.city",
      "optional": false
    },
    "declared": false,
    "pii_type": "LOC",
    "produced": "Брянск",
    "reference": "Брянск",
    "status": "residual",
    "verdict": null
  },
  {
    "case_id": "tool_chain-043",
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
    "pii_type": "PHONE",
    "produced": "+79527054451",
    "reference": "8 935 335 03 98",
    "status": "observed",
    "verdict": {
      "same": false,
      "differs": [
        "grouping",
        "prefix",
        "separators"
      ]
    }
  }
]
