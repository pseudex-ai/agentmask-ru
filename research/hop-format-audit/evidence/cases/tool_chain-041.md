# tool_chain-041 | source C | repeat 0

Synthetic benchmark evidence. Verbatim serialized fields; no inferred verdicts.

## Case specification

{
  "base": {
    "id": "tool_chain-041",
    "kind": "tool_chain",
    "register": "voice_itn",
    "provenance": {
      "kind": "template",
      "corpus": "authored",
      "key": "",
      "shape": "",
      "selection": "authored",
      "weight": 1.0,
      "licence": "authored"
    },
    "cluster": "PHONE:9620091409",
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
        "content": "здравствуйте повторите прошлую доставку по номеру 8-962-009-14-09 а также к 11 часам",
        "source": null,
        "name": ""
      },
      {
        "role": "user",
        "content": "ничего не диктую всё есть в карточке проверьте адрес и оформите",
        "source": null,
        "name": ""
      },
      {
        "role": "user",
        "content": "потом проверьте что заказ прошёл",
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
          "last_name": "лебедева",
          "first_name": "ирина",
          "middle_name": "петровна",
          "phone": "+79620091409",
          "email": "lebedeva98@yandex.ru",
          "birth_date": "1985-02-22",
          "address": {
            "city": "псков",
            "street": "загородный",
            "house": "177",
            "flat": "49"
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
          "value": "Псковская область, г Псков, ул Загородный, д 177",
          "postal_code": "180136",
          "region": "Псковская область",
          "city": "псков",
          "street": "загородный",
          "house": "177",
          "flat": "",
          "fias_id": "1eab2fa7-bc72-4ced-8504-717d92273d99"
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
        "identity": "p41",
        "value": "лебедева",
        "canonical": "лебедева",
        "parts": {
          "surname": "лебедева",
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
        "identity": "p41",
        "value": "ирина",
        "canonical": "ирина",
        "parts": {
          "given": "ирина",
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
        "identity": "p41",
        "value": "петровна",
        "canonical": "петровна",
        "parts": {
          "patronymic": "петровна",
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
        "identity": "p41",
        "value": "+79620091409",
        "canonical": "+79620091409",
        "parts": {
          "digits": "9620091409"
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
        "identity": "p41",
        "value": "lebedeva98@yandex.ru",
        "canonical": "lebedeva98@yandex.ru",
        "parts": {
          "local": "lebedeva98",
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
        "identity": "p41",
        "value": "1985-02-22",
        "canonical": "1985-02-22",
        "parts": {
          "iso": "1985-02-22"
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
        "identity": "p41.home",
        "value": "загородный",
        "canonical": "загородный",
        "parts": {
          "street": "загородный",
          "street_type": "проспект",
          "house": "177",
          "flat": "49",
          "city": "псков"
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
        "identity": "p41.dir",
        "value": "загородный",
        "canonical": "загородный",
        "parts": {
          "street": "загородный"
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
        "identity": "p41.dir",
        "value": "Псковская область, г Псков, ул Загородный, д 177",
        "canonical": "Псковская область, г Псков, ул Загородный, д 177",
        "parts": {
          "city": "псков",
          "street": "загородный",
          "house": "177"
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
        "identity": "p41",
        "value": "8-962-009-14-09",
        "canonical": "+79620091409",
        "parts": {
          "digits": "9620091409"
        },
        "where": {
          "kind": "message",
          "msg": 1,
          "start": 50,
          "end": 65,
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
        "value": "11 часам",
        "start": 76,
        "end": 84,
        "msg": 1,
        "family": "time_of_day",
        "why": "время, а не номер"
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
      "primary_identity": "p41",
      "must_contain": [],
      "must_not_contain": [],
      "validate_types": []
    },
    "trace": [
      {
        "msg": 1,
        "key": "",
        "start": 0,
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
        "end": 30,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 1,
        "key": "",
        "start": 30,
        "end": 31,
        "origin": "literal"
      },
      {
        "msg": 1,
        "key": "",
        "start": 31,
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
        "end": 42,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 1,
        "key": "",
        "start": 42,
        "end": 43,
        "origin": "literal"
      },
      {
        "msg": 1,
        "key": "",
        "start": 43,
        "end": 49,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 1,
        "key": "",
        "start": 49,
        "end": 50,
        "origin": "literal"
      },
      {
        "msg": 1,
        "key": "ph1",
        "start": 50,
        "end": 65,
        "origin": "value:ph1"
      },
      {
        "msg": 1,
        "key": "",
        "start": 65,
        "end": 66,
        "origin": "literal"
      },
      {
        "msg": 1,
        "key": "",
        "start": 66,
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
        "key": "",
        "start": 68,
        "end": 73,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 1,
        "key": "",
        "start": 73,
        "end": 74,
        "origin": "literal"
      },
      {
        "msg": 1,
        "key": "",
        "start": 74,
        "end": 75,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 1,
        "key": "",
        "start": 75,
        "end": 76,
        "origin": "literal"
      },
      {
        "msg": 1,
        "key": "neg1",
        "start": 76,
        "end": 84,
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
        "end": 19,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 3,
        "key": "",
        "start": 19,
        "end": 20,
        "origin": "literal"
      },
      {
        "msg": 3,
        "key": "",
        "start": 20,
        "end": 25,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 3,
        "key": "",
        "start": 25,
        "end": 26,
        "origin": "literal"
      },
      {
        "msg": 3,
        "key": "",
        "start": 26,
        "end": 32,
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
  "streaming": true,
  "revised_from_v4": true
}

## Actual gateway arm (written/restored calls, tool results, answers, mentions)

{
  "base": {
    "case_id": "tool_chain-041",
    "arm": "I",
    "repeat": 0,
    "calls": [
      {
        "name": "crm_find_contact",
        "written": {
          "query": {
            "phone": "+79623650598"
          }
        },
        "restored": {
          "query": {
            "phone": "+79620091409"
          }
        },
        "residual": {},
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "query": {
            "phone": "+79620091409"
          }
        },
        "seq": 1
      },
      {
        "name": "address_suggest",
        "written": {
          "count": 5,
          "query": "Псков, улица Осиновая, 165"
        },
        "restored": {
          "count": 5,
          "query": "Псков, улица Осиновая, 177"
        },
        "residual": {
          "query": [
            "осиновая"
          ]
        },
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "count": 5,
          "query": "Псков, улица Осиновая, 177"
        },
        "seq": 2
      },
      {
        "name": "address_suggest",
        "written": {
          "count": 5,
          "query": "Осиновая"
        },
        "restored": {
          "count": 5,
          "query": "Загородный"
        },
        "residual": {},
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "count": 5,
          "query": "Загородный"
        },
        "seq": 3
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
            "name": "Петренко Наталья Ильинична",
            "phones": [
              {
                "number": "+79623650598"
              }
            ]
          },
          "to_location": {
            "address": "улица Осиновая, 165, кв. 119",
            "city": "Псков",
            "postal_code": "180136"
          }
        },
        "restored": {
          "packages": [
            {
              "weight": 1000
            }
          ],
          "recipient": {
            "name": "Лебедева Ирина Петровна",
            "phones": [
              {
                "number": "+79620091409"
              }
            ]
          },
          "to_location": {
            "address": "улица Осиновая, 177, кв. 49",
            "city": "Псков",
            "postal_code": "180136"
          }
        },
        "residual": {
          "to_location.address": [
            "осиновая"
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
            "name": "Лебедева Ирина Петровна",
            "phones": [
              "+79620091409"
            ]
          },
          "to_location": {
            "address": "улица Осиновая, 177, кв. 49",
            "city": "псков",
            "postal_code": "180136"
          }
        },
        "seq": 4
      },
      {
        "name": "courier_book",
        "written": {
          "address": {
            "building": "165",
            "locality": "Псков",
            "sflat": "119",
            "street": "Осиновая"
          },
          "contact": {
            "name": "Петренко Наталья Ильинична",
            "phone": "+79623650598"
          },
          "interval": {
            "from": "2026-09-02T11:00:00+03:00",
            "to": "2026-09-02T12:00:00+03:00"
          }
        },
        "restored": {
          "address": {
            "building": "177",
            "locality": "Псков",
            "sflat": "49",
            "street": "Загородный"
          },
          "contact": {
            "name": "Лебедева Ирина Петровна",
            "phone": "+79620091409"
          },
          "interval": {
            "from": "2026-09-02T11:00:00+03:00",
            "to": "2026-09-02T12:00:00+03:00"
          }
        },
        "residual": {},
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "address": {
            "building": "177",
            "locality": "псков",
            "porch": "",
            "sflat": "49",
            "street": "загородный"
          },
          "contact": {
            "name": "Лебедева Ирина Петровна",
            "phone": "+79620091409"
          },
          "interval": {
            "from": "2026-09-02T11:00:00+03:00",
            "to": "2026-09-02T12:00:00+03:00"
          }
        },
        "seq": 5
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
        "seq": 6
      },
      {
        "name": "crm_find_contact",
        "written": {
          "query": {
            "last_name": "Бирюкова"
          }
        },
        "restored": {
          "query": {
            "last_name": "Лебедева"
          }
        },
        "residual": {},
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "query": {
            "last_name": "лебедева"
          }
        },
        "seq": 7
      },
      {
        "name": "address_suggest",
        "written": {
          "count": 5,
          "query": "Псков, улица Липовая, 176"
        },
        "restored": {
          "count": 5,
          "query": "Псков, улица Осиновая, 177"
        },
        "residual": {
          "query": [
            "осиновая"
          ]
        },
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "count": 5,
          "query": "Псков, улица Осиновая, 177"
        },
        "seq": 8
      },
      {
        "name": "crm_add_note",
        "written": {
          "entity_id": "c-1",
          "note_type": "call_in",
          "text": "Повтор прошлой доставки по номеру 8-962-365-05-98. Создан заказ ord-1: получатель Бирюкова Елизавета Викторовна, Псков, ул. Липовая, 176, кв. 72, индекс 180136, вес 1000 г. Вызван курьер (заявка clm-1) на 11:00–12:00 по адресу Псков, ул. Осиновая, 165, кв. 119."
        },
        "restored": {
          "entity_id": "c-1",
          "note_type": "call_in",
          "text": "Повтор прошлой доставки по номеру +79620091409. Создан заказ ord-1: получатель Лебедева Ирина Петровна, Псков, ул. Осиновая, 177, кв. 49, индекс 180136, вес 1000 г. Вызван курьер (заявка clm-1) на 11:00–12:00 по адресу Псков, ул. Осиновая, 177, кв. 49."
        },
        "residual": {
          "text": [
            "осиновая"
          ]
        },
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "entity_id": "c-1",
          "note_type": "call_in",
          "text": "Повтор прошлой доставки по номеру +79620091409. Создан заказ ord-1: получатель Лебедева Ирина Петровна, Псков, ул. Осиновая, 177, кв. 49, индекс 180136, вес 1000 г. Вызван курьер (заявка clm-1) на 11:00–12:00 по адресу Псков, ул. Осиновая, 177, кв. 49."
        },
        "seq": 9
      },
      {
        "name": "crm_find_contact",
        "written": {
          "query": {
            "phone": "+79623650598"
          }
        },
        "restored": {
          "query": {
            "phone": "+79620091409"
          }
        },
        "residual": {},
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "query": {
            "phone": "+79620091409"
          }
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
            "name": "Лебедева Ирина Петровна",
            "phones": [
              "+79620091409"
            ]
          },
          "to_location": {
            "address": "улица Осиновая, 177, кв. 49",
            "city": "псков",
            "postal_code": "180136"
          }
        },
        "id": "ord-1",
        "seq": 4,
        "table": "orders",
        "tool": "delivery_create_order"
      },
      {
        "fields": {
          "address": {
            "building": "177",
            "locality": "псков",
            "porch": "",
            "sflat": "49",
            "street": "загородный"
          },
          "contact": {
            "name": "Лебедева Ирина Петровна",
            "phone": "+79620091409"
          },
          "interval": {
            "from": "2026-09-02T11:00:00+03:00",
            "to": "2026-09-02T12:00:00+03:00"
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
          "text": "Повтор прошлой доставки по номеру +79620091409. Создан заказ ord-1: получатель Лебедева Ирина Петровна, Псков, ул. Осиновая, 177, кв. 49, индекс 180136, вес 1000 г. Вызван курьер (заявка clm-1) на 11:00–12:00 по адресу Псков, ул. Осиновая, 177, кв. 49."
        },
        "id": "note-1",
        "seq": 9,
        "table": "notes",
        "tool": "crm_add_note"
      }
    ],
    "reply": "Проверила — заказ прошёл ✅\n\n**Заказ ord-1:**\n- Статус: **ACCEPTED** (принят)\n- Получатель: Лебедева Ирина Петровна, тел. +79620091409\n- Адрес: г. Псков, улица Осиновая, 177, д. 177, кв. 49, индекс 180136\n\nЗаявка на курьера clm-1 также в работе (статус estimating — идёт расчёт), забор 02.09.2026 в интервале 11:00–12:00 по адресу ул. Осиновая, д. 177, кв. 49.\n\nВсё оформлено успешно.",
    "termination": "done",
    "cost_usd": 0.023176,
    "substitutes": {
      "i1": [
        "петренко",
        {
          "surname": "петренко"
        }
      ],
      "i10": [
        "8-962-365-05-98",
        {
          "digits": "9623650598"
        }
      ],
      "i2": [
        "наталья",
        {
          "given": "наталья"
        }
      ],
      "i3": [
        "ильинична",
        {
          "patronymic": "ильинична"
        }
      ],
      "i4": [
        "8-962-365-05-98",
        {
          "digits": "9623650598"
        }
      ],
      "i5": [
        "rghqywmp@example.ru",
        {
          "domain": "example.ru",
          "local": "rghqywmp"
        }
      ],
      "i6": [
        "1985-09-16",
        {
          "iso": "1985-09-16"
        }
      ],
      "i7": [
        "осиновая",
        {
          "street": "осиновая"
        }
      ],
      "i8": [
        "осиновая",
        {
          "street": "осиновая"
        }
      ]
    },
    "masked_spans": {
      "0": [],
      "1": [
        [
          50,
          65
        ]
      ],
      "2": [],
      "3": []
    }
  },
  "reply_raw": "Проверила — заказ прошёл ✅\n\n**Заказ ord-1:**\n- Статус: **ACCEPTED** (принят)\n- Получатель: Бирюкова Елизавета Викторовна, тел. 8-962-365-05-98\n- Адрес: г. Псков, ул. Липовая, д. 176, кв. 72, индекс 180136\n\nЗаявка на курьера clm-1 также в работе (статус estimating — идёт расчёт), забор 02.09.2026 в интервале 11:00–12:00 по адресу ул. Осиновая, д. 165, кв. 119.\n\nВсё оформлено успешно.",
  "control_reply": "Проверила — заказ прошёл успешно.\n\n**Заказ ord-1**\n- Статус: **ACCEPTED** (принят службой доставки)\n- Получатель: Лебедева Ирина Петровна, +79620091409\n- Адрес: г. Псков, ул. Загородный, д. 177, кв. 49 (индекс 180136)\n\nЗаказ зарегистрирован, курьер вызван на 02.09.2026, интервал 10:00–11:00. Всё в порядке.",
  "tool_results": [
    {
      "tool_name": "crm_find_contact",
      "seq": 1,
      "call_ordinal": 0,
      "turn": 1,
      "return_form": "list",
      "text_real": "{\n  \"contacts\": [\n    {\n      \"id\": \"c-1\",\n      \"last_name\": \"лебедева\",\n      \"first_name\": \"ирина\",\n      \"middle_name\": \"петровна\",\n      \"phone\": \"+79620091409\",\n      \"email\": \"lebedeva98@yandex.ru\",\n      \"birth_date\": \"1985-02-22\",\n      \"address\": {\n        \"city\": \"псков\",\n        \"street\": \"загородный\",\n        \"house\": \"177\",\n        \"flat\": \"49\"\n      }\n    }\n  ]\n}",
      "text_masked": "{\n  \"contacts\": [\n    {\n      \"id\": \"c-1\",\n      \"last_name\": \"петренко\",\n      \"first_name\": \"наталья\",\n      \"middle_name\": \"ильинична\",\n      \"phone\": \"8-962-365-05-98\",\n      \"email\": \"rghqywmp@example.ru\",\n      \"birth_date\": \"1985-09-16\",\n      \"address\": {\n        \"city\": \"псков\",\n        \"street\": \"осиновая\",\n        \"house\": \"165\",\n        \"flat\": \"119\"\n      }\n    }\n  ]\n}",
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
          133
        ],
        "i4": [
          152,
          164
        ],
        "i5": [
          183,
          203
        ],
        "i6": [
          227,
          237
        ],
        "i7": [
          303,
          313
        ]
      },
      "pieces": [
        [
          63,
          71,
          "петренко",
          "NAME"
        ],
        [
          95,
          100,
          "наталья",
          "NAME"
        ],
        [
          125,
          133,
          "ильинична",
          "NAME"
        ],
        [
          152,
          164,
          "8-962-365-05-98",
          "PHONE"
        ],
        [
          183,
          203,
          "rghqywmp@example.ru",
          "EMAIL"
        ],
        [
          227,
          237,
          "1985-09-16",
          "DOB"
        ],
        [
          276,
          281,
          "псков",
          "LOC"
        ],
        [
          303,
          313,
          "осиновая",
          "LOC"
        ],
        [
          334,
          337,
          "165",
          "LOC"
        ],
        [
          357,
          359,
          "119",
          "LOC"
        ]
      ],
      "forced": false
    },
    {
      "tool_name": "address_suggest",
      "seq": 2,
      "call_ordinal": 0,
      "turn": 1,
      "return_form": "canon",
      "text_real": "{\n  \"suggestions\": [\n    {\n      \"value\": \"г Псков, ул Загородный, д 177\",\n      \"confidence\": \"0.50\",\n      \"data\": {\n        \"postal_code\": \"180136\",\n        \"region\": \"Псковская область\",\n        \"city\": \"псков\",\n        \"street\": \"загородный\",\n        \"house\": \"177\",\n        \"flat\": \"\",\n        \"fias_id\": \"1eab2fa7-bc72-4ced-8504-717d92273d99\"\n      }\n    }\n  ]\n}",
      "text_masked": "{\n  \"suggestions\": [\n    {\n      \"value\": \"г Псков, ул Речная, д 108\",\n      \"confidence\": \"0.50\",\n      \"data\": {\n        \"postal_code\": \"180136\",\n        \"region\": \"Псковская область\",\n        \"city\": \"псков\",\n        \"street\": \"речная\",\n        \"house\": \"108\",\n        \"flat\": \"\",\n        \"fias_id\": \"1eab2fa7-bc72-4ced-8504-717d92273d99\"\n      }\n    }\n  ]\n}",
      "spans_real": {
        "i8": [
          55,
          65
        ],
        "i9": [
          43,
          72
        ]
      },
      "pieces": [
        [
          43,
          72,
          "г Псков, ул Речная, д 108",
          "LOC"
        ],
        [
          208,
          213,
          "псков",
          "LOC"
        ],
        [
          235,
          245,
          "речная",
          "LOC"
        ],
        [
          266,
          269,
          "108",
          "LOC"
        ]
      ],
      "forced": false
    },
    {
      "tool_name": "address_suggest",
      "seq": 3,
      "call_ordinal": 1,
      "turn": 1,
      "return_form": "canon",
      "text_real": "{\n  \"suggestions\": [\n    {\n      \"value\": \"г Псков, ул Загородный, д 177\",\n      \"confidence\": \"1.00\",\n      \"data\": {\n        \"postal_code\": \"180136\",\n        \"region\": \"Псковская область\",\n        \"city\": \"псков\",\n        \"street\": \"загородный\",\n        \"house\": \"177\",\n        \"flat\": \"\",\n        \"fias_id\": \"1eab2fa7-bc72-4ced-8504-717d92273d99\"\n      }\n    }\n  ]\n}",
      "text_masked": "{\n  \"suggestions\": [\n    {\n      \"value\": \"г Псков, ул Речная, д 108\",\n      \"confidence\": \"1.00\",\n      \"data\": {\n        \"postal_code\": \"180136\",\n        \"region\": \"Псковская область\",\n        \"city\": \"псков\",\n        \"street\": \"речная\",\n        \"house\": \"108\",\n        \"flat\": \"\",\n        \"fias_id\": \"1eab2fa7-bc72-4ced-8504-717d92273d99\"\n      }\n    }\n  ]\n}",
      "spans_real": {
        "i8": [
          55,
          65
        ],
        "i9": [
          43,
          72
        ]
      },
      "pieces": [
        [
          43,
          72,
          "г Псков, ул Речная, д 108",
          "LOC"
        ],
        [
          208,
          213,
          "псков",
          "LOC"
        ],
        [
          235,
          245,
          "речная",
          "LOC"
        ],
        [
          266,
          269,
          "108",
          "LOC"
        ]
      ],
      "forced": false
    },
    {
      "tool_name": "delivery_create_order",
      "seq": 4,
      "call_ordinal": 0,
      "turn": 1,
      "return_form": "single",
      "text_real": "{\n  \"uuid\": \"ord-1\",\n  \"status\": \"ACCEPTED\",\n  \"recipient\": {\n    \"name\": \"Лебедева Ирина Петровна\",\n    \"phone\": \"+79620091409\"\n  },\n  \"to_location\": {\n    \"postal_code\": \"180136\",\n    \"city\": \"псков\",\n    \"address\": \"улица Осиновая, 177, кв. 49\"\n  }\n}",
      "text_masked": "{\n  \"uuid\": \"ord-1\",\n  \"status\": \"ACCEPTED\",\n  \"recipient\": {\n    \"name\": \"Бирюкова Елизавета Викторовна\",\n    \"phone\": \"8-962-365-05-98\"\n  },\n  \"to_location\": {\n    \"postal_code\": \"180136\",\n    \"city\": \"псков\",\n    \"address\": \"улица Липовая, 176, кв. 72\"\n  }\n}",
      "spans_real": {
        "i4": [
          115,
          127
        ]
      },
      "pieces": [
        [
          75,
          98,
          "Бирюкова Елизавета Викторовна",
          "NAME"
        ],
        [
          115,
          127,
          "8-962-365-05-98",
          "PHONE"
        ],
        [
          219,
          246,
          "улица Липовая, 176, кв. 72",
          "LOC"
        ]
      ],
      "forced": false
    },
    {
      "tool_name": "courier_book",
      "seq": 5,
      "call_ordinal": 0,
      "turn": 1,
      "return_form": "nested",
      "text_real": "{\n  \"claim_id\": \"clm-1\",\n  \"status\": \"estimating\",\n  \"contact\": {\n    \"name\": \"Лебедева Ирина Петровна\",\n    \"phone\": \"+79620091409\"\n  },\n  \"address\": \"г. Псков, ул. Загородный, д. 177, кв. 49\"\n}",
      "text_masked": "{\n  \"claim_id\": \"clm-1\",\n  \"status\": \"estimating\",\n  \"contact\": {\n    \"name\": \"Бирюкова Елизавета Викторовна\",\n    \"phone\": \"8-962-365-05-98\"\n  },\n  \"address\": \"г. Псков, ул. Осиновая, д. 165, кв. 119\"\n}",
      "spans_real": {
        "i4": [
          119,
          131
        ]
      },
      "pieces": [
        [
          79,
          102,
          "Бирюкова Елизавета Викторовна",
          "NAME"
        ],
        [
          119,
          131,
          "8-962-365-05-98",
          "PHONE"
        ],
        [
          152,
          192,
          "г. Псков, ул. Осиновая, д. 165, кв. 119",
          "LOC"
        ]
      ],
      "forced": false
    },
    {
      "tool_name": "order_status",
      "seq": 6,
      "call_ordinal": 0,
      "turn": 1,
      "return_form": "single",
      "text_real": "{\n  \"uuid\": \"ord-1\",\n  \"status\": \"ACCEPTED\",\n  \"date\": \"\",\n  \"recipient\": {\n    \"name\": \"Лебедева Ирина Петровна\",\n    \"phone\": \"+79620091409\"\n  },\n  \"to_location\": {\n    \"city\": \"псков\",\n    \"address\": \"улица Осиновая, 177, кв. 49\"\n  }\n}",
      "text_masked": "{\n  \"uuid\": \"ord-1\",\n  \"status\": \"ACCEPTED\",\n  \"date\": \"\",\n  \"recipient\": {\n    \"name\": \"Бирюкова Елизавета Викторовна\",\n    \"phone\": \"8-962-365-05-98\"\n  },\n  \"to_location\": {\n    \"city\": \"псков\",\n    \"address\": \"улица Липовая, 176, кв. 72\"\n  }\n}",
      "spans_real": {
        "i4": [
          129,
          141
        ]
      },
      "pieces": [
        [
          89,
          112,
          "Бирюкова Елизавета Викторовна",
          "NAME"
        ],
        [
          129,
          141,
          "8-962-365-05-98",
          "PHONE"
        ],
        [
          204,
          231,
          "улица Липовая, 176, кв. 72",
          "LOC"
        ]
      ],
      "forced": false
    },
    {
      "tool_name": "crm_find_contact",
      "seq": 7,
      "call_ordinal": 1,
      "turn": 1,
      "return_form": "list",
      "text_real": "{\n  \"contacts\": [\n    {\n      \"id\": \"c-1\",\n      \"last_name\": \"лебедева\",\n      \"first_name\": \"ирина\",\n      \"middle_name\": \"петровна\",\n      \"phone\": \"+79620091409\",\n      \"email\": \"lebedeva98@yandex.ru\",\n      \"birth_date\": \"1985-02-22\",\n      \"address\": {\n        \"city\": \"псков\",\n        \"street\": \"загородный\",\n        \"house\": \"177\",\n        \"flat\": \"49\"\n      }\n    }\n  ]\n}",
      "text_masked": "{\n  \"contacts\": [\n    {\n      \"id\": \"c-1\",\n      \"last_name\": \"петренко\",\n      \"first_name\": \"наталья\",\n      \"middle_name\": \"ильинична\",\n      \"phone\": \"8-962-365-05-98\",\n      \"email\": \"rghqywmp@example.ru\",\n      \"birth_date\": \"1985-09-16\",\n      \"address\": {\n        \"city\": \"псков\",\n        \"street\": \"осиновая\",\n        \"house\": \"165\",\n        \"flat\": \"119\"\n      }\n    }\n  ]\n}",
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
          133
        ],
        "i4": [
          152,
          164
        ],
        "i5": [
          183,
          203
        ],
        "i6": [
          227,
          237
        ],
        "i7": [
          303,
          313
        ]
      },
      "pieces": [
        [
          63,
          71,
          "петренко",
          "NAME"
        ],
        [
          95,
          100,
          "наталья",
          "NAME"
        ],
        [
          125,
          133,
          "ильинична",
          "NAME"
        ],
        [
          152,
          164,
          "8-962-365-05-98",
          "PHONE"
        ],
        [
          183,
          203,
          "rghqywmp@example.ru",
          "EMAIL"
        ],
        [
          227,
          237,
          "1985-09-16",
          "DOB"
        ],
        [
          276,
          281,
          "псков",
          "LOC"
        ],
        [
          303,
          313,
          "осиновая",
          "LOC"
        ],
        [
          334,
          337,
          "165",
          "LOC"
        ],
        [
          357,
          359,
          "119",
          "LOC"
        ]
      ],
      "forced": false
    },
    {
      "tool_name": "address_suggest",
      "seq": 8,
      "call_ordinal": 2,
      "turn": 1,
      "return_form": "canon",
      "text_real": "{\n  \"suggestions\": [\n    {\n      \"value\": \"г Псков, ул Загородный, д 177\",\n      \"confidence\": \"0.50\",\n      \"data\": {\n        \"postal_code\": \"180136\",\n        \"region\": \"Псковская область\",\n        \"city\": \"псков\",\n        \"street\": \"загородный\",\n        \"house\": \"177\",\n        \"flat\": \"\",\n        \"fias_id\": \"1eab2fa7-bc72-4ced-8504-717d92273d99\"\n      }\n    }\n  ]\n}",
      "text_masked": "{\n  \"suggestions\": [\n    {\n      \"value\": \"г Псков, ул Речная, д 108\",\n      \"confidence\": \"0.50\",\n      \"data\": {\n        \"postal_code\": \"180136\",\n        \"region\": \"Псковская область\",\n        \"city\": \"псков\",\n        \"street\": \"речная\",\n        \"house\": \"108\",\n        \"flat\": \"\",\n        \"fias_id\": \"1eab2fa7-bc72-4ced-8504-717d92273d99\"\n      }\n    }\n  ]\n}",
      "spans_real": {
        "i8": [
          55,
          65
        ],
        "i9": [
          43,
          72
        ]
      },
      "pieces": [
        [
          43,
          72,
          "г Псков, ул Речная, д 108",
          "LOC"
        ],
        [
          208,
          213,
          "псков",
          "LOC"
        ],
        [
          235,
          245,
          "речная",
          "LOC"
        ],
        [
          266,
          269,
          "108",
          "LOC"
        ]
      ],
      "forced": false
    },
    {
      "tool_name": "crm_add_note",
      "seq": 9,
      "call_ordinal": 0,
      "turn": 1,
      "return_form": "single",
      "text_real": "{\n  \"id\": \"note-1\",\n  \"entity_id\": \"c-1\",\n  \"length\": 252,\n  \"entity\": {\n    \"last_name\": \"лебедева\",\n    \"first_name\": \"ирина\",\n    \"phone\": \"+79620091409\"\n  }\n}",
      "text_masked": "{\n  \"id\": \"note-1\",\n  \"entity_id\": \"c-1\",\n  \"length\": 252,\n  \"entity\": {\n    \"last_name\": \"петренко\",\n    \"first_name\": \"наталья\",\n    \"phone\": \"8-962-365-05-98\"\n  }\n}",
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
          "петренко",
          "NAME"
        ],
        [
          121,
          126,
          "наталья",
          "NAME"
        ],
        [
          143,
          155,
          "8-962-365-05-98",
          "PHONE"
        ]
      ],
      "forced": false
    },
    {
      "tool_name": "crm_find_contact",
      "seq": 10,
      "call_ordinal": 0,
      "turn": 2,
      "return_form": "list",
      "text_real": "{\n  \"contacts\": [\n    {\n      \"id\": \"c-1\",\n      \"last_name\": \"лебедева\",\n      \"first_name\": \"ирина\",\n      \"middle_name\": \"петровна\",\n      \"phone\": \"+79620091409\",\n      \"email\": \"lebedeva98@yandex.ru\",\n      \"birth_date\": \"1985-02-22\",\n      \"address\": {\n        \"city\": \"псков\",\n        \"street\": \"загородный\",\n        \"house\": \"177\",\n        \"flat\": \"49\"\n      }\n    }\n  ]\n}",
      "text_masked": "{\n  \"contacts\": [\n    {\n      \"id\": \"c-1\",\n      \"last_name\": \"петренко\",\n      \"first_name\": \"наталья\",\n      \"middle_name\": \"ильинична\",\n      \"phone\": \"8-962-365-05-98\",\n      \"email\": \"rghqywmp@example.ru\",\n      \"birth_date\": \"1985-09-16\",\n      \"address\": {\n        \"city\": \"псков\",\n        \"street\": \"осиновая\",\n        \"house\": \"165\",\n        \"flat\": \"119\"\n      }\n    }\n  ]\n}",
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
          133
        ],
        "i4": [
          152,
          164
        ],
        "i5": [
          183,
          203
        ],
        "i6": [
          227,
          237
        ],
        "i7": [
          303,
          313
        ]
      },
      "pieces": [
        [
          63,
          71,
          "петренко",
          "NAME"
        ],
        [
          95,
          100,
          "наталья",
          "NAME"
        ],
        [
          125,
          133,
          "ильинична",
          "NAME"
        ],
        [
          152,
          164,
          "8-962-365-05-98",
          "PHONE"
        ],
        [
          183,
          203,
          "rghqywmp@example.ru",
          "EMAIL"
        ],
        [
          227,
          237,
          "1985-09-16",
          "DOB"
        ],
        [
          276,
          281,
          "псков",
          "LOC"
        ],
        [
          303,
          313,
          "осиновая",
          "LOC"
        ],
        [
          334,
          337,
          "165",
          "LOC"
        ],
        [
          357,
          359,
          "119",
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
      "text_real": "{\n  \"uuid\": \"ord-1\",\n  \"status\": \"ACCEPTED\",\n  \"date\": \"\",\n  \"recipient\": {\n    \"name\": \"Лебедева Ирина Петровна\",\n    \"phone\": \"+79620091409\"\n  },\n  \"to_location\": {\n    \"city\": \"псков\",\n    \"address\": \"улица Осиновая, 177, кв. 49\"\n  }\n}",
      "text_masked": "{\n  \"uuid\": \"ord-1\",\n  \"status\": \"ACCEPTED\",\n  \"date\": \"\",\n  \"recipient\": {\n    \"name\": \"Бирюкова Елизавета Викторовна\",\n    \"phone\": \"8-962-365-05-98\"\n  },\n  \"to_location\": {\n    \"city\": \"псков\",\n    \"address\": \"улица Липовая, 176, кв. 72\"\n  }\n}",
      "spans_real": {
        "i4": [
          129,
          141
        ]
      },
      "pieces": [
        [
          89,
          112,
          "Бирюкова Елизавета Викторовна",
          "NAME"
        ],
        [
          129,
          141,
          "8-962-365-05-98",
          "PHONE"
        ],
        [
          204,
          231,
          "улица Липовая, 176, кв. 72",
          "LOC"
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
      "substitute": "8-962-365-05-98",
      "request_index": 1
    },
    {
      "item_id": "i1",
      "msg": -1,
      "result_seq": 1,
      "substitute": "петренко",
      "request_index": 2
    },
    {
      "item_id": "i2",
      "msg": -1,
      "result_seq": 1,
      "substitute": "наталья",
      "request_index": 2
    },
    {
      "item_id": "i3",
      "msg": -1,
      "result_seq": 1,
      "substitute": "ильинична",
      "request_index": 2
    },
    {
      "item_id": "i4",
      "msg": -1,
      "result_seq": 1,
      "substitute": "8-962-365-05-98",
      "request_index": 2
    },
    {
      "item_id": "i5",
      "msg": -1,
      "result_seq": 1,
      "substitute": "rghqywmp@example.ru",
      "request_index": 2
    },
    {
      "item_id": "i6",
      "msg": -1,
      "result_seq": 1,
      "substitute": "1985-09-16",
      "request_index": 2
    },
    {
      "item_id": "i7",
      "msg": -1,
      "result_seq": 1,
      "substitute": "осиновая",
      "request_index": 2
    },
    {
      "item_id": "i8",
      "msg": -1,
      "result_seq": 2,
      "substitute": "г Псков, ул Речная, д 108",
      "request_index": 3
    },
    {
      "item_id": "i9",
      "msg": -1,
      "result_seq": 2,
      "substitute": "г Псков, ул Речная, д 108",
      "request_index": 3
    },
    {
      "item_id": "i8",
      "msg": -1,
      "result_seq": 3,
      "substitute": "г Псков, ул Речная, д 108",
      "request_index": 4
    },
    {
      "item_id": "i9",
      "msg": -1,
      "result_seq": 3,
      "substitute": "г Псков, ул Речная, д 108",
      "request_index": 4
    },
    {
      "item_id": "i4",
      "msg": -1,
      "result_seq": 4,
      "substitute": "8-962-365-05-98",
      "request_index": 5
    },
    {
      "item_id": "i4",
      "msg": -1,
      "result_seq": 5,
      "substitute": "8-962-365-05-98",
      "request_index": 6
    },
    {
      "item_id": "i4",
      "msg": -1,
      "result_seq": 6,
      "substitute": "8-962-365-05-98",
      "request_index": 7
    },
    {
      "item_id": "i1",
      "msg": -1,
      "result_seq": 7,
      "substitute": "петренко",
      "request_index": 8
    },
    {
      "item_id": "i2",
      "msg": -1,
      "result_seq": 7,
      "substitute": "наталья",
      "request_index": 8
    },
    {
      "item_id": "i3",
      "msg": -1,
      "result_seq": 7,
      "substitute": "ильинична",
      "request_index": 8
    },
    {
      "item_id": "i4",
      "msg": -1,
      "result_seq": 7,
      "substitute": "8-962-365-05-98",
      "request_index": 8
    },
    {
      "item_id": "i5",
      "msg": -1,
      "result_seq": 7,
      "substitute": "rghqywmp@example.ru",
      "request_index": 8
    },
    {
      "item_id": "i6",
      "msg": -1,
      "result_seq": 7,
      "substitute": "1985-09-16",
      "request_index": 8
    },
    {
      "item_id": "i7",
      "msg": -1,
      "result_seq": 7,
      "substitute": "осиновая",
      "request_index": 8
    },
    {
      "item_id": "i8",
      "msg": -1,
      "result_seq": 8,
      "substitute": "г Псков, ул Речная, д 108",
      "request_index": 9
    },
    {
      "item_id": "i9",
      "msg": -1,
      "result_seq": 8,
      "substitute": "г Псков, ул Речная, д 108",
      "request_index": 9
    },
    {
      "item_id": "i1",
      "msg": -1,
      "result_seq": 9,
      "substitute": "петренко",
      "request_index": 10
    },
    {
      "item_id": "i2",
      "msg": -1,
      "result_seq": 9,
      "substitute": "наталья",
      "request_index": 10
    },
    {
      "item_id": "i4",
      "msg": -1,
      "result_seq": 9,
      "substitute": "8-962-365-05-98",
      "request_index": 10
    },
    {
      "item_id": "i1",
      "msg": -1,
      "result_seq": 10,
      "substitute": "петренко",
      "request_index": 12
    },
    {
      "item_id": "i2",
      "msg": -1,
      "result_seq": 10,
      "substitute": "наталья",
      "request_index": 12
    },
    {
      "item_id": "i3",
      "msg": -1,
      "result_seq": 10,
      "substitute": "ильинична",
      "request_index": 12
    },
    {
      "item_id": "i4",
      "msg": -1,
      "result_seq": 10,
      "substitute": "8-962-365-05-98",
      "request_index": 12
    },
    {
      "item_id": "i5",
      "msg": -1,
      "result_seq": 10,
      "substitute": "rghqywmp@example.ru",
      "request_index": 12
    },
    {
      "item_id": "i6",
      "msg": -1,
      "result_seq": 10,
      "substitute": "1985-09-16",
      "request_index": 12
    },
    {
      "item_id": "i7",
      "msg": -1,
      "result_seq": 10,
      "substitute": "осиновая",
      "request_index": 12
    },
    {
      "item_id": "i4",
      "msg": -1,
      "result_seq": 11,
      "substitute": "8-962-365-05-98",
      "request_index": 14
    }
  ],
  "turn_replies": [
    "Готово! Оформила повтор прошлой доставки и вызов курьера.\n\n**Заказ ord-1** (повтор прошлой доставки по номеру +79620091409):\n- Получатель: Лебедева Ирина Петровна, тел. +79620091409\n- Адрес: г. Псков, улица Осиновая, 177, д. 177, кв. 49, индекс 180136\n- Вес: 1000 г\n- Статус: ACCEPTED\n\n**Вызов курьера (заявка clm-1):**\n- Адрес: г. Псков, ул. псков, загородный, 177, д. 177, кв. 49\n- Контакт: +79620091409\n- Интервал: 11:00–12:00 (к 11 часам), 02.09.2026\n\nЗаметку в карточку клиента добавила.\n\nУточните, пожалуйста, один момент: курьера вызывать **от вас** (псков, загородный, 177, 177) для забора отправления — верно? Если забор должен быть по другому адресу, скажите, и я поправлю заявку.",
    "Проверила карточку клиента — всё сходится:\n\n**Карточка c-1:** Лебедева Ирина Петровна, тел. +79620091409, г. Псков, ул. псков, загородный, 177, д. 177, кв. 49.\n\nАдрес курьера совпадает с адресом в карточке, поэтому заявку оставила без изменений. Итого оформлено:\n\n**Заказ ord-1** (повтор прошлой доставки):\n- Получатель: Лебедева Ирина Петровна, тел. +79620091409\n- Адрес: г. Псков, ул. Липовая, д. 177, кв. 49, индекс 180136\n- Вес: 1000 г\n- Статус: ACCEPTED\n\n**Вызов курьера (заявка clm-1):**\n- Адрес забора: г. Псков, ул. Осиновая, д. 177, кв. 49 (из карточки)\n- Контакт: +79620091409\n- Интервал: 11:00–12:00, 02.09.2026\n\nВсё готово, дополнительно ничего диктовать не нужно.",
    "Проверила — заказ прошёл ✅\n\n**Заказ ord-1:**\n- Статус: **ACCEPTED** (принят)\n- Получатель: Лебедева Ирина Петровна, тел. +79620091409\n- Адрес: г. Псков, улица Осиновая, 177, д. 177, кв. 49, индекс 180136\n\nЗаявка на курьера clm-1 также в работе (статус estimating — идёт расчёт), забор 02.09.2026 в интервале 11:00–12:00 по адресу ул. Осиновая, д. 177, кв. 49.\n\nВсё оформлено успешно."
  ],
  "call_turns": [
    1,
    1,
    1,
    1,
    1,
    1,
    1,
    1,
    1,
    2,
    3
  ],
  "request_count": 14,
  "stream_mismatch": true,
  "reply_whole": "Проверила — заказ прошёл ✅\n\n**Заказ ord-1:**\n- Статус: **ACCEPTED** (принят)\n- Получатель: Лебедева Ирина Петровна, тел. +79620091409\n- Адрес: г. Псков, улица Осиновая, 177, кв. 49, индекс 180136\n\nЗаявка на курьера clm-1 также в работе (статус estimating — идёт расчёт), забор 02.09.2026 в интервале 11:00–12:00 по адресу ул. Осиновая, д. 177, кв. 49.\n\nВсё оформлено успешно.",
  "turn_residual": 2
}

## Recorded observer hops

[
  {
    "case_id": "tool_chain-041",
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
    "produced": "8-962-365-05-98",
    "reference": "8-962-009-14-09",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "tool_chain-041",
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
    "produced": "г Псков, ул Речная, д 108",
    "reference": "г Псков, ул Загородный, д 177",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "tool_chain-041",
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
    "produced": "петренко",
    "reference": "лебедева",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "tool_chain-041",
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
    "produced": "наталья",
    "reference": "ирина",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "tool_chain-041",
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
    "produced": "ильинична",
    "reference": "петровна",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "tool_chain-041",
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
    "produced": "8-962-365-05-98",
    "reference": "+79620091409",
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
    "case_id": "tool_chain-041",
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
    "produced": "rghqywmp@example.ru",
    "reference": "lebedeva98@yandex.ru",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "tool_chain-041",
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
    "produced": "1985-09-16",
    "reference": "1985-02-22",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "tool_chain-041",
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
    "produced": "осиновая",
    "reference": "загородный",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "tool_chain-041",
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
    "case_id": "tool_chain-041",
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
    "case_id": "tool_chain-041",
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
    "case_id": "tool_chain-041",
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
    "case_id": "tool_chain-041",
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
    "case_id": "tool_chain-041",
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
    "case_id": "tool_chain-041",
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
    "produced": "+79620091409",
    "reference": "8-962-365-05-98",
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
    "case_id": "tool_chain-041",
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
    "produced": "+79620091409",
    "reference": "+79623650598",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "tool_chain-041",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i7",
      "hop_index": -1,
      "turn": 1,
      "tool_name": "address_suggest",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": -1,
      "path": "query",
      "optional": false
    },
    "declared": false,
    "pii_type": "LOC",
    "produced": "Псков, улица Осиновая, 177",
    "reference": "Псков, улица Осиновая, 165",
    "status": "residual",
    "verdict": null
  },
  {
    "case_id": "tool_chain-041",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i7",
      "hop_index": -1,
      "turn": 1,
      "tool_name": "address_suggest",
      "call_ordinal": 1,
      "parallel_group": "",
      "source_hop": -1,
      "path": "query",
      "optional": false
    },
    "declared": false,
    "pii_type": "LOC",
    "produced": "Загородный",
    "reference": "Осиновая",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "tool_chain-041",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i1",
      "hop_index": -1,
      "turn": 1,
      "tool_name": "delivery_create_order",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": -1,
      "path": "recipient.name",
      "optional": false
    },
    "declared": false,
    "pii_type": "NAME",
    "produced": "Лебедева Ирина Петровна",
    "reference": "Петренко Наталья Ильинична",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "tool_chain-041",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i4",
      "hop_index": -1,
      "turn": 1,
      "tool_name": "delivery_create_order",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": -1,
      "path": "recipient.phones[0].number",
      "optional": false
    },
    "declared": false,
    "pii_type": "PHONE",
    "produced": "+79620091409",
    "reference": "+79623650598",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "tool_chain-041",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i7",
      "hop_index": -1,
      "turn": 1,
      "tool_name": "delivery_create_order",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": -1,
      "path": "to_location.address",
      "optional": false
    },
    "declared": false,
    "pii_type": "LOC",
    "produced": "улица Осиновая, 177, кв. 49",
    "reference": "улица Осиновая, 165, кв. 119",
    "status": "residual",
    "verdict": null
  },
  {
    "case_id": "tool_chain-041",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i8",
      "hop_index": -1,
      "turn": 1,
      "tool_name": "delivery_create_order",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": -1,
      "path": "to_location.city",
      "optional": false
    },
    "declared": false,
    "pii_type": "LOC",
    "produced": "Псков",
    "reference": "Псков",
    "status": "residual",
    "verdict": null
  },
  {
    "case_id": "tool_chain-041",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "",
      "hop_index": -1,
      "turn": 1,
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
    "reference": "165",
    "status": "unmasked",
    "verdict": null
  },
  {
    "case_id": "tool_chain-041",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i8",
      "hop_index": -1,
      "turn": 1,
      "tool_name": "courier_book",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": -1,
      "path": "address.locality",
      "optional": false
    },
    "declared": false,
    "pii_type": "LOC",
    "produced": "Псков",
    "reference": "Псков",
    "status": "residual",
    "verdict": null
  },
  {
    "case_id": "tool_chain-041",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "",
      "hop_index": -1,
      "turn": 1,
      "tool_name": "courier_book",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": -1,
      "path": "address.sflat",
      "optional": false
    },
    "declared": false,
    "pii_type": "LOC",
    "produced": "49",
    "reference": "119",
    "status": "unmasked",
    "verdict": null
  },
  {
    "case_id": "tool_chain-041",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i7",
      "hop_index": -1,
      "turn": 1,
      "tool_name": "courier_book",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": -1,
      "path": "address.street",
      "optional": false
    },
    "declared": false,
    "pii_type": "LOC",
    "produced": "Загородный",
    "reference": "Осиновая",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "tool_chain-041",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i1",
      "hop_index": -1,
      "turn": 1,
      "tool_name": "courier_book",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": -1,
      "path": "contact.name",
      "optional": false
    },
    "declared": false,
    "pii_type": "NAME",
    "produced": "Лебедева Ирина Петровна",
    "reference": "Петренко Наталья Ильинична",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "tool_chain-041",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i4",
      "hop_index": -1,
      "turn": 1,
      "tool_name": "courier_book",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": -1,
      "path": "contact.phone",
      "optional": false
    },
    "declared": false,
    "pii_type": "PHONE",
    "produced": "+79620091409",
    "reference": "+79623650598",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "tool_chain-041",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "",
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
    "produced": "Лебедева",
    "reference": "Бирюкова",
    "status": "unmasked",
    "verdict": null
  },
  {
    "case_id": "tool_chain-041",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "",
      "hop_index": -1,
      "turn": 1,
      "tool_name": "address_suggest",
      "call_ordinal": 2,
      "parallel_group": "",
      "source_hop": -1,
      "path": "query",
      "optional": false
    },
    "declared": false,
    "pii_type": "LOC",
    "produced": "Псков, улица Осиновая, 177",
    "reference": "Псков, улица Липовая, 176",
    "status": "unmasked",
    "verdict": null
  },
  {
    "case_id": "tool_chain-041",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i4",
      "hop_index": -1,
      "turn": 2,
      "tool_name": "crm_find_contact",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": -1,
      "path": "query.phone",
      "optional": false
    },
    "declared": false,
    "pii_type": "PHONE",
    "produced": "+79620091409",
    "reference": "+79623650598",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "tool_chain-041",
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
    "produced": "+79620091409",
    "reference": "8-962-365-05-98",
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
