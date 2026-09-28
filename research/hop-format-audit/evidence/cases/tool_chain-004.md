# tool_chain-004 | source A | repeat 0

Synthetic benchmark evidence. Verbatim serialized fields; no inferred verdicts.

## Case specification

{
  "base": {
    "id": "tool_chain-004",
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
    "cluster": "PHONE:9512725489",
    "conversation_id": "conv-chain3-4",
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
        "content": "привет повторите прошдую доставку по номеру 89512725489 и ещё заказ 837",
        "source": null,
        "name": ""
      },
      {
        "role": "user",
        "content": "адрес и получателя возьмите из карточки сверьте по справочнику",
        "source": null,
        "name": ""
      },
      {
        "role": "user",
        "content": "потом проверьте что заказ проёшл",
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
          "last_name": "миллер",
          "first_name": "валерий",
          "middle_name": "леонидович",
          "phone": "+79512725489",
          "email": "miller93@list.ru",
          "birth_date": "1955-05-09",
          "address": {
            "city": "псков",
            "street": "смольный",
            "house": "52",
            "flat": "2"
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
          "value": "Псковская область, г Псков, ул Смольный, д 52",
          "postal_code": "180782",
          "region": "Псковская область",
          "city": "псков",
          "street": "смольный",
          "house": "52",
          "flat": "",
          "fias_id": "10160e63-90b8-4dca-8cb6-0abc66a2b78c"
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
        "identity": "p4",
        "value": "миллер",
        "canonical": "миллер",
        "parts": {
          "surname": "миллер",
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
        "identity": "p4",
        "value": "валерий",
        "canonical": "валерий",
        "parts": {
          "given": "валерий",
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
        "identity": "p4",
        "value": "леонидович",
        "canonical": "леонидович",
        "parts": {
          "patronymic": "леонидович",
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
        "identity": "p4",
        "value": "+79512725489",
        "canonical": "+79512725489",
        "parts": {
          "digits": "9512725489"
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
        "identity": "p4",
        "value": "miller93@list.ru",
        "canonical": "miller93@list.ru",
        "parts": {
          "local": "miller93",
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
        "identity": "p4",
        "value": "1955-05-09",
        "canonical": "1955-05-09",
        "parts": {
          "iso": "1955-05-09"
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
        "identity": "p4.home",
        "value": "смольный",
        "canonical": "смольный",
        "parts": {
          "street": "смольный",
          "street_type": "бульвар",
          "house": "52",
          "flat": "2",
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
        "identity": "p4.dir",
        "value": "смольный",
        "canonical": "смольный",
        "parts": {
          "street": "смольный"
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
        "identity": "p4.dir",
        "value": "Псковская область, г Псков, ул Смольный, д 52",
        "canonical": "Псковская область, г Псков, ул Смольный, д 52",
        "parts": {
          "city": "псков",
          "street": "смольный",
          "house": "52"
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
        "identity": "p4",
        "value": "89512725489",
        "canonical": "+79512725489",
        "parts": {
          "digits": "9512725489"
        },
        "where": {
          "kind": "message",
          "msg": 1,
          "start": 44,
          "end": 55,
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
        "value": "837",
        "start": 68,
        "end": 71,
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
        "crm_add_note"
      ],
      "primary_identity": "p4",
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
        "end": 16,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 1,
        "key": "",
        "start": 16,
        "end": 17,
        "origin": "literal"
      },
      {
        "msg": 1,
        "key": "",
        "start": 17,
        "end": 24,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 1,
        "key": "",
        "start": 24,
        "end": 25,
        "origin": "literal"
      },
      {
        "msg": 1,
        "key": "",
        "start": 25,
        "end": 33,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 1,
        "key": "",
        "start": 33,
        "end": 34,
        "origin": "literal"
      },
      {
        "msg": 1,
        "key": "",
        "start": 34,
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
        "end": 43,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 1,
        "key": "",
        "start": 43,
        "end": 44,
        "origin": "literal"
      },
      {
        "msg": 1,
        "key": "ph1",
        "start": 44,
        "end": 55,
        "origin": "value:ph1"
      },
      {
        "msg": 1,
        "key": "",
        "start": 55,
        "end": 56,
        "origin": "literal"
      },
      {
        "msg": 1,
        "key": "",
        "start": 56,
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
        "end": 61,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 1,
        "key": "",
        "start": 61,
        "end": 62,
        "origin": "literal"
      },
      {
        "msg": 1,
        "key": "",
        "start": 62,
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
        "key": "neg1",
        "start": 68,
        "end": 71,
        "origin": "negative:neg1"
      },
      {
        "msg": 2,
        "key": "",
        "start": 0,
        "end": 5,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 2,
        "key": "",
        "start": 5,
        "end": 6,
        "origin": "literal"
      },
      {
        "msg": 2,
        "key": "",
        "start": 6,
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
        "end": 18,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 2,
        "key": "",
        "start": 18,
        "end": 19,
        "origin": "literal"
      },
      {
        "msg": 2,
        "key": "",
        "start": 19,
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
        "end": 30,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 2,
        "key": "",
        "start": 30,
        "end": 31,
        "origin": "literal"
      },
      {
        "msg": 2,
        "key": "",
        "start": 31,
        "end": 39,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 2,
        "key": "",
        "start": 39,
        "end": 40,
        "origin": "literal"
      },
      {
        "msg": 2,
        "key": "",
        "start": 40,
        "end": 47,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 2,
        "key": "",
        "start": 47,
        "end": 48,
        "origin": "literal"
      },
      {
        "msg": 2,
        "key": "",
        "start": 48,
        "end": 50,
        "origin": "chunk:noisy_word"
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
        "end": 62,
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
      "owner": "answer",
      "item_id": "i1",
      "hop_index": 15,
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
      "hop_index": 16,
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
      "hop_index": 17,
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
      "hop_index": 18,
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
      "hop_index": 19,
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
      "hop_index": 20,
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
    "case_id": "tool_chain-004",
    "arm": "I",
    "repeat": 0,
    "calls": [
      {
        "name": "crm_find_contact",
        "written": {
          "query": {
            "phone": "+79822248300"
          }
        },
        "restored": {
          "query": {
            "phone": "+79512725489"
          }
        },
        "residual": {},
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "query": {
            "phone": "+79512725489"
          }
        },
        "seq": 1
      },
      {
        "name": "order_status",
        "written": {
          "order_id": "837"
        },
        "restored": {
          "order_id": "837"
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
          "count": 5,
          "query": "Псков, улица Луговая, дом 89"
        },
        "restored": {
          "count": 5,
          "query": "Псков, улица Луговая, дом 52"
        },
        "residual": {
          "query": [
            "луговая"
          ]
        },
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "count": 5,
          "query": "Псков, улица Луговая, дом 52"
        },
        "seq": 3
      },
      {
        "name": "address_suggest",
        "written": {
          "count": 10,
          "query": "Псков Луговая 89"
        },
        "restored": {
          "count": 10,
          "query": "Псков Луговая 52"
        },
        "residual": {
          "query": [
            "луговая"
          ]
        },
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "count": 10,
          "query": "Псков Луговая 52"
        },
        "seq": 4
      },
      {
        "name": "address_suggest",
        "written": {
          "count": 10,
          "query": "Псков улица Луговая"
        },
        "restored": {
          "count": 10,
          "query": "Псков улица Смольный"
        },
        "residual": {},
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "count": 10,
          "query": "Псков улица Смольный"
        },
        "seq": 5
      },
      {
        "name": "address_suggest",
        "written": {
          "count": 10,
          "query": "Луговая"
        },
        "restored": {
          "count": 10,
          "query": "Смольный"
        },
        "residual": {},
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "count": 10,
          "query": "Смольный"
        },
        "seq": 6
      },
      {
        "name": "address_suggest",
        "written": {
          "count": 10,
          "query": "Псков"
        },
        "restored": {
          "count": 10,
          "query": "Псков"
        },
        "residual": {},
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "count": 10,
          "query": "Псков"
        },
        "seq": 7
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
            "name": "Котов Матвей Евгеньевич",
            "phones": [
              {
                "number": "+79822248300"
              }
            ]
          },
          "to_location": {
            "address": "ул. Луговая, д. 89, кв. 27",
            "city": "Псков",
            "postal_code": "180782"
          }
        },
        "restored": {
          "packages": [
            {
              "weight": 1000
            }
          ],
          "recipient": {
            "name": "Миллер Валерий Леонидович",
            "phones": [
              {
                "number": "+79512725489"
              }
            ]
          },
          "to_location": {
            "address": "ул. Луговая, д. 52, кв. 2",
            "city": "Псков",
            "postal_code": "180782"
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
              "weight": 1000
            }
          ],
          "recipient": {
            "name": "Миллер Валерий Леонидович",
            "phones": [
              "+79512725489"
            ]
          },
          "to_location": {
            "address": "ул. Луговая, д. 52, кв. 2",
            "city": "псков",
            "postal_code": "180782"
          }
        },
        "seq": 8
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
        "seq": 9
      },
      {
        "name": "crm_find_contact",
        "written": {
          "query": {
            "last_name": "Цветков"
          }
        },
        "restored": {
          "query": {
            "last_name": "Миллер"
          }
        },
        "residual": {},
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "query": {
            "last_name": "миллер"
          }
        },
        "seq": 10
      },
      {
        "name": "crm_find_contact",
        "written": {
          "query": {
            "phone": "+79822248300"
          }
        },
        "restored": {
          "query": {
            "phone": "+79512725489"
          }
        },
        "residual": {},
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "query": {
            "phone": "+79512725489"
          }
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
            "name": "Миллер Валерий Леонидович",
            "phones": [
              "+79512725489"
            ]
          },
          "to_location": {
            "address": "ул. Луговая, д. 52, кв. 2",
            "city": "псков",
            "postal_code": "180782"
          }
        },
        "id": "ord-1",
        "seq": 8,
        "table": "orders",
        "tool": "delivery_create_order"
      }
    ],
    "reply": "Проверил статус заказа **ord-1**:\n\n- **Статус:** ACCEPTED (принят службой доставки)\n- **Получатель:** Миллер Валерий Леонидович\n- **Адрес:** Псков, ул. Луговая, д. 52, кв. 2\n- **Индекс:** в заказе не проставлен\n\nФормально заказ «прошёл» — он принят. **Но** он по-прежнему оформлен на **не того получателя и не по тому адресу**: в карточке клиента это Миллер Валерий Леонидович, ул. Луговая, д. 52, кв. 2. То есть если его не остановить, курьер поедет к Миллеру на ул. Луговую, д. 52 — это не ваш клиент.\n\nПоэтому подтвердить, что «доставка прошла успешно», я не могу — данные в заказе некорректны. Нужно либо переоформить заказ на верные данные, либо отменить/исправить текущий через техподдержку (у меня в инструментах такой возможности нет).\n\nПодскажите:\n1. Переоформляем заказ на Миллера Валерия Леонидовича, ул. Луговая, 52, кв. 2 (индекс 180782)?\n2. По **заказу №837** — пришлите, пожалуйста, корректный номер в формате системы, иначе оформить не смогу.",
    "termination": "done",
    "cost_usd": 0.013241,
    "substitutes": {
      "i1": [
        "котов",
        {
          "surname": "котов"
        }
      ],
      "i10": [
        "89822248300",
        {
          "digits": "9822248300"
        }
      ],
      "i2": [
        "матвей",
        {
          "given": "матвей"
        }
      ],
      "i3": [
        "евгеньевич",
        {
          "patronymic": "евгеньевич"
        }
      ],
      "i4": [
        "89822248300",
        {
          "digits": "9822248300"
        }
      ],
      "i5": [
        "bbzaqilz@example.ru",
        {
          "domain": "example.ru",
          "local": "bbzaqilz"
        }
      ],
      "i6": [
        "1955-07-04",
        {
          "iso": "1955-07-04"
        }
      ],
      "i7": [
        "луговая",
        {
          "street": "луговая"
        }
      ],
      "i8": [
        "луговая",
        {
          "street": "луговая"
        }
      ]
    },
    "masked_spans": {
      "0": [],
      "1": [
        [
          44,
          55
        ]
      ],
      "2": [],
      "3": []
    }
  },
  "reply_raw": "Проверил статус заказа **ord-1**:\n\n- **Статус:** ACCEPTED (принят службой доставки)\n- **Получатель:** Цветков Гордей Алексеевич\n- **Адрес:** Псков, ул. Лавандовая, д. 79, кв. 40\n- **Индекс:** в заказе не проставлен\n\nФормально заказ «прошёл» — он принят. **Но** он по-прежнему оформлен на **не того получателя и не по тому адресу**: в карточке клиента это Котов Матвей Евгеньевич, ул. Луговая, д. 89, кв. 27. То есть если его не остановить, курьер поедет к Цветкову на Лавандовую, 79 — это не ваш клиент.\n\nПоэтому подтвердить, что «доставка прошла успешно», я не могу — данные в заказе некорректны. Нужно либо переоформить заказ на верные данные, либо отменить/исправить текущий через техподдержку (у меня в инструментах такой возможности нет).\n\nПодскажите:\n1. Переоформляем заказ на Котова Матвея Евгеньевича, ул. Луговая, 89, кв. 27 (индекс 180782)?\n2. По **заказу №837** — пришлите, пожалуйста, корректный номер в формате системы, иначе оформить не смогу.",
  "control_reply": "Проверил заказ **ord-1** — он прошёл успешно:\n\n- Статус: **ACCEPTED** (принят)\n- Получатель: Миллер Валерий Леонидович, +79512725489\n- Адрес: Псков, ул. Смольный, д. 52, кв. 2\n- Вес: 1000 г\n\nЗаказ принят службой доставки, всё в порядке. По заказу 837 — найти не удалось, жду уточнений.",
  "tool_results": [
    {
      "tool_name": "crm_find_contact",
      "seq": 1,
      "call_ordinal": 0,
      "turn": 1,
      "return_form": "list",
      "text_real": "{\n  \"contacts\": [\n    {\n      \"id\": \"c-1\",\n      \"last_name\": \"миллер\",\n      \"first_name\": \"валерий\",\n      \"middle_name\": \"леонидович\",\n      \"phone\": \"+79512725489\",\n      \"email\": \"miller93@list.ru\",\n      \"birth_date\": \"1955-05-09\",\n      \"address\": {\n        \"city\": \"псков\",\n        \"street\": \"смольный\",\n        \"house\": \"52\",\n        \"flat\": \"2\"\n      }\n    }\n  ]\n}",
      "text_masked": "{\n  \"contacts\": [\n    {\n      \"id\": \"c-1\",\n      \"last_name\": \"котов\",\n      \"first_name\": \"матвей\",\n      \"middle_name\": \"евгеньевич\",\n      \"phone\": \"89822248300\",\n      \"email\": \"bbzaqilz@example.ru\",\n      \"birth_date\": \"1955-07-04\",\n      \"address\": {\n        \"city\": \"псков\",\n        \"street\": \"луговая\",\n        \"house\": \"89\",\n        \"flat\": \"27\"\n      }\n    }\n  ]\n}",
      "spans_real": {
        "i1": [
          63,
          69
        ],
        "i2": [
          93,
          100
        ],
        "i3": [
          125,
          135
        ],
        "i4": [
          154,
          166
        ],
        "i5": [
          185,
          201
        ],
        "i6": [
          225,
          235
        ],
        "i7": [
          301,
          309
        ]
      },
      "pieces": [
        [
          63,
          69,
          "котов",
          "NAME"
        ],
        [
          93,
          100,
          "матвей",
          "NAME"
        ],
        [
          125,
          135,
          "евгеньевич",
          "NAME"
        ],
        [
          154,
          166,
          "89822248300",
          "PHONE"
        ],
        [
          185,
          201,
          "bbzaqilz@example.ru",
          "EMAIL"
        ],
        [
          225,
          235,
          "1955-07-04",
          "DOB"
        ],
        [
          274,
          279,
          "псков",
          "LOC"
        ],
        [
          301,
          309,
          "луговая",
          "LOC"
        ],
        [
          330,
          332,
          "89",
          "LOC"
        ],
        [
          352,
          353,
          "27",
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
      "text_real": "{\n  \"error\": {\n    \"code\": \"order_id_format\",\n    \"field\": \"order_id\",\n    \"message\": \"поле order_id: order_id_format: 837\"\n  }\n}",
      "text_masked": "{\n  \"error\": {\n    \"code\": \"order_id_format\",\n    \"field\": \"order_id\",\n    \"message\": \"поле order_id: order_id_format: 837\"\n  }\n}",
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
      "text_real": "{\n  \"suggestions\": [\n    {\n      \"value\": \"г Псков, ул Смольный, д 52\",\n      \"confidence\": \"0.25\",\n      \"data\": {\n        \"postal_code\": \"180782\",\n        \"region\": \"Псковская область\",\n        \"city\": \"псков\",\n        \"street\": \"смольный\",\n        \"house\": \"52\",\n        \"flat\": \"\",\n        \"fias_id\": \"10160e63-90b8-4dca-8cb6-0abc66a2b78c\"\n      }\n    }\n  ]\n}",
      "text_masked": "{\n  \"suggestions\": [\n    {\n      \"value\": \"г Псков, ул Тополиная, д 30\",\n      \"confidence\": \"0.25\",\n      \"data\": {\n        \"postal_code\": \"180782\",\n        \"region\": \"Псковская область\",\n        \"city\": \"псков\",\n        \"street\": \"тополиная\",\n        \"house\": \"30\",\n        \"flat\": \"\",\n        \"fias_id\": \"10160e63-90b8-4dca-8cb6-0abc66a2b78c\"\n      }\n    }\n  ]\n}",
      "spans_real": {
        "i8": [
          55,
          63
        ],
        "i9": [
          43,
          69
        ]
      },
      "pieces": [
        [
          43,
          69,
          "г Псков, ул Тополиная, д 30",
          "LOC"
        ],
        [
          205,
          210,
          "псков",
          "LOC"
        ],
        [
          232,
          240,
          "тополиная",
          "LOC"
        ],
        [
          261,
          263,
          "30",
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
      "text_real": "{\n  \"suggestions\": [\n    {\n      \"value\": \"г Псков, ул Смольный, д 52\",\n      \"confidence\": \"0.50\",\n      \"data\": {\n        \"postal_code\": \"180782\",\n        \"region\": \"Псковская область\",\n        \"city\": \"псков\",\n        \"street\": \"смольный\",\n        \"house\": \"52\",\n        \"flat\": \"\",\n        \"fias_id\": \"10160e63-90b8-4dca-8cb6-0abc66a2b78c\"\n      }\n    }\n  ]\n}",
      "text_masked": "{\n  \"suggestions\": [\n    {\n      \"value\": \"г Псков, ул Тополиная, д 30\",\n      \"confidence\": \"0.50\",\n      \"data\": {\n        \"postal_code\": \"180782\",\n        \"region\": \"Псковская область\",\n        \"city\": \"псков\",\n        \"street\": \"тополиная\",\n        \"house\": \"30\",\n        \"flat\": \"\",\n        \"fias_id\": \"10160e63-90b8-4dca-8cb6-0abc66a2b78c\"\n      }\n    }\n  ]\n}",
      "spans_real": {
        "i8": [
          55,
          63
        ],
        "i9": [
          43,
          69
        ]
      },
      "pieces": [
        [
          43,
          69,
          "г Псков, ул Тополиная, д 30",
          "LOC"
        ],
        [
          205,
          210,
          "псков",
          "LOC"
        ],
        [
          232,
          240,
          "тополиная",
          "LOC"
        ],
        [
          261,
          263,
          "30",
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
      "text_real": "{\n  \"suggestions\": [\n    {\n      \"value\": \"г Псков, ул Смольный, д 52\",\n      \"confidence\": \"0.67\",\n      \"data\": {\n        \"postal_code\": \"180782\",\n        \"region\": \"Псковская область\",\n        \"city\": \"псков\",\n        \"street\": \"смольный\",\n        \"house\": \"52\",\n        \"flat\": \"\",\n        \"fias_id\": \"10160e63-90b8-4dca-8cb6-0abc66a2b78c\"\n      }\n    }\n  ]\n}",
      "text_masked": "{\n  \"suggestions\": [\n    {\n      \"value\": \"г Псков, ул Тополиная, д 30\",\n      \"confidence\": \"0.67\",\n      \"data\": {\n        \"postal_code\": \"180782\",\n        \"region\": \"Псковская область\",\n        \"city\": \"псков\",\n        \"street\": \"тополиная\",\n        \"house\": \"30\",\n        \"flat\": \"\",\n        \"fias_id\": \"10160e63-90b8-4dca-8cb6-0abc66a2b78c\"\n      }\n    }\n  ]\n}",
      "spans_real": {
        "i8": [
          55,
          63
        ],
        "i9": [
          43,
          69
        ]
      },
      "pieces": [
        [
          43,
          69,
          "г Псков, ул Тополиная, д 30",
          "LOC"
        ],
        [
          205,
          210,
          "псков",
          "LOC"
        ],
        [
          232,
          240,
          "тополиная",
          "LOC"
        ],
        [
          261,
          263,
          "30",
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
      "text_real": "{\n  \"suggestions\": [\n    {\n      \"value\": \"г Псков, ул Смольный, д 52\",\n      \"confidence\": \"1.00\",\n      \"data\": {\n        \"postal_code\": \"180782\",\n        \"region\": \"Псковская область\",\n        \"city\": \"псков\",\n        \"street\": \"смольный\",\n        \"house\": \"52\",\n        \"flat\": \"\",\n        \"fias_id\": \"10160e63-90b8-4dca-8cb6-0abc66a2b78c\"\n      }\n    }\n  ]\n}",
      "text_masked": "{\n  \"suggestions\": [\n    {\n      \"value\": \"г Псков, ул Тополиная, д 30\",\n      \"confidence\": \"1.00\",\n      \"data\": {\n        \"postal_code\": \"180782\",\n        \"region\": \"Псковская область\",\n        \"city\": \"псков\",\n        \"street\": \"тополиная\",\n        \"house\": \"30\",\n        \"flat\": \"\",\n        \"fias_id\": \"10160e63-90b8-4dca-8cb6-0abc66a2b78c\"\n      }\n    }\n  ]\n}",
      "spans_real": {
        "i8": [
          55,
          63
        ],
        "i9": [
          43,
          69
        ]
      },
      "pieces": [
        [
          43,
          69,
          "г Псков, ул Тополиная, д 30",
          "LOC"
        ],
        [
          205,
          210,
          "псков",
          "LOC"
        ],
        [
          232,
          240,
          "тополиная",
          "LOC"
        ],
        [
          261,
          263,
          "30",
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
      "text_real": "{\n  \"suggestions\": [\n    {\n      \"value\": \"г Псков, ул Смольный, д 52\",\n      \"confidence\": \"1.00\",\n      \"data\": {\n        \"postal_code\": \"180782\",\n        \"region\": \"Псковская область\",\n        \"city\": \"псков\",\n        \"street\": \"смольный\",\n        \"house\": \"52\",\n        \"flat\": \"\",\n        \"fias_id\": \"10160e63-90b8-4dca-8cb6-0abc66a2b78c\"\n      }\n    }\n  ]\n}",
      "text_masked": "{\n  \"suggestions\": [\n    {\n      \"value\": \"г Псков, ул Тополиная, д 30\",\n      \"confidence\": \"1.00\",\n      \"data\": {\n        \"postal_code\": \"180782\",\n        \"region\": \"Псковская область\",\n        \"city\": \"псков\",\n        \"street\": \"тополиная\",\n        \"house\": \"30\",\n        \"flat\": \"\",\n        \"fias_id\": \"10160e63-90b8-4dca-8cb6-0abc66a2b78c\"\n      }\n    }\n  ]\n}",
      "spans_real": {
        "i8": [
          55,
          63
        ],
        "i9": [
          43,
          69
        ]
      },
      "pieces": [
        [
          43,
          69,
          "г Псков, ул Тополиная, д 30",
          "LOC"
        ],
        [
          205,
          210,
          "псков",
          "LOC"
        ],
        [
          232,
          240,
          "тополиная",
          "LOC"
        ],
        [
          261,
          263,
          "30",
          "LOC"
        ]
      ],
      "forced": false
    },
    {
      "tool_name": "delivery_create_order",
      "seq": 8,
      "call_ordinal": 0,
      "turn": 2,
      "return_form": "single",
      "text_real": "{\n  \"uuid\": \"ord-1\",\n  \"status\": \"ACCEPTED\",\n  \"recipient\": {\n    \"name\": \"Миллер Валерий Леонидович\",\n    \"phone\": \"+79512725489\"\n  },\n  \"to_location\": {\n    \"postal_code\": \"180782\",\n    \"city\": \"псков\",\n    \"address\": \"ул. Луговая, д. 52, кв. 2\"\n  }\n}",
      "text_masked": "{\n  \"uuid\": \"ord-1\",\n  \"status\": \"ACCEPTED\",\n  \"recipient\": {\n    \"name\": \"Цветков Гордей Алексеевич\",\n    \"phone\": \"89822248300\"\n  },\n  \"to_location\": {\n    \"postal_code\": \"180782\",\n    \"city\": \"псков\",\n    \"address\": \"ул. Лавандовая, д. 79, кв. 40\"\n  }\n}",
      "spans_real": {
        "i4": [
          117,
          129
        ]
      },
      "pieces": [
        [
          75,
          100,
          "Цветков Гордей Алексеевич",
          "NAME"
        ],
        [
          117,
          129,
          "89822248300",
          "PHONE"
        ],
        [
          221,
          246,
          "ул. Лавандовая, д. 79, кв. 40",
          "LOC"
        ]
      ],
      "forced": false
    },
    {
      "tool_name": "order_status",
      "seq": 9,
      "call_ordinal": 0,
      "turn": 2,
      "return_form": "single",
      "text_real": "{\n  \"uuid\": \"ord-1\",\n  \"status\": \"ACCEPTED\",\n  \"date\": \"\",\n  \"recipient\": {\n    \"name\": \"Миллер Валерий Леонидович\",\n    \"phone\": \"+79512725489\"\n  },\n  \"to_location\": {\n    \"city\": \"псков\",\n    \"address\": \"ул. Луговая, д. 52, кв. 2\"\n  }\n}",
      "text_masked": "{\n  \"uuid\": \"ord-1\",\n  \"status\": \"ACCEPTED\",\n  \"date\": \"\",\n  \"recipient\": {\n    \"name\": \"Цветков Гордей Алексеевич\",\n    \"phone\": \"89822248300\"\n  },\n  \"to_location\": {\n    \"city\": \"псков\",\n    \"address\": \"ул. Лавандовая, д. 79, кв. 40\"\n  }\n}",
      "spans_real": {
        "i4": [
          131,
          143
        ]
      },
      "pieces": [
        [
          89,
          114,
          "Цветков Гордей Алексеевич",
          "NAME"
        ],
        [
          131,
          143,
          "89822248300",
          "PHONE"
        ],
        [
          206,
          231,
          "ул. Лавандовая, д. 79, кв. 40",
          "LOC"
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
      "text_real": "{\n  \"contacts\": [\n    {\n      \"id\": \"c-1\",\n      \"last_name\": \"миллер\",\n      \"first_name\": \"валерий\",\n      \"middle_name\": \"леонидович\",\n      \"phone\": \"+79512725489\",\n      \"email\": \"miller93@list.ru\",\n      \"birth_date\": \"1955-05-09\",\n      \"address\": {\n        \"city\": \"псков\",\n        \"street\": \"смольный\",\n        \"house\": \"52\",\n        \"flat\": \"2\"\n      }\n    }\n  ]\n}",
      "text_masked": "{\n  \"contacts\": [\n    {\n      \"id\": \"c-1\",\n      \"last_name\": \"котов\",\n      \"first_name\": \"матвей\",\n      \"middle_name\": \"евгеньевич\",\n      \"phone\": \"89822248300\",\n      \"email\": \"bbzaqilz@example.ru\",\n      \"birth_date\": \"1955-07-04\",\n      \"address\": {\n        \"city\": \"псков\",\n        \"street\": \"луговая\",\n        \"house\": \"89\",\n        \"flat\": \"27\"\n      }\n    }\n  ]\n}",
      "spans_real": {
        "i1": [
          63,
          69
        ],
        "i2": [
          93,
          100
        ],
        "i3": [
          125,
          135
        ],
        "i4": [
          154,
          166
        ],
        "i5": [
          185,
          201
        ],
        "i6": [
          225,
          235
        ],
        "i7": [
          301,
          309
        ]
      },
      "pieces": [
        [
          63,
          69,
          "котов",
          "NAME"
        ],
        [
          93,
          100,
          "матвей",
          "NAME"
        ],
        [
          125,
          135,
          "евгеньевич",
          "NAME"
        ],
        [
          154,
          166,
          "89822248300",
          "PHONE"
        ],
        [
          185,
          201,
          "bbzaqilz@example.ru",
          "EMAIL"
        ],
        [
          225,
          235,
          "1955-07-04",
          "DOB"
        ],
        [
          274,
          279,
          "псков",
          "LOC"
        ],
        [
          301,
          309,
          "луговая",
          "LOC"
        ],
        [
          330,
          332,
          "89",
          "LOC"
        ],
        [
          352,
          353,
          "27",
          "LOC"
        ]
      ],
      "forced": false
    },
    {
      "tool_name": "crm_find_contact",
      "seq": 11,
      "call_ordinal": 1,
      "turn": 2,
      "return_form": "list",
      "text_real": "{\n  \"contacts\": [\n    {\n      \"id\": \"c-1\",\n      \"last_name\": \"миллер\",\n      \"first_name\": \"валерий\",\n      \"middle_name\": \"леонидович\",\n      \"phone\": \"+79512725489\",\n      \"email\": \"miller93@list.ru\",\n      \"birth_date\": \"1955-05-09\",\n      \"address\": {\n        \"city\": \"псков\",\n        \"street\": \"смольный\",\n        \"house\": \"52\",\n        \"flat\": \"2\"\n      }\n    }\n  ]\n}",
      "text_masked": "{\n  \"contacts\": [\n    {\n      \"id\": \"c-1\",\n      \"last_name\": \"котов\",\n      \"first_name\": \"матвей\",\n      \"middle_name\": \"евгеньевич\",\n      \"phone\": \"89822248300\",\n      \"email\": \"bbzaqilz@example.ru\",\n      \"birth_date\": \"1955-07-04\",\n      \"address\": {\n        \"city\": \"псков\",\n        \"street\": \"луговая\",\n        \"house\": \"89\",\n        \"flat\": \"27\"\n      }\n    }\n  ]\n}",
      "spans_real": {
        "i1": [
          63,
          69
        ],
        "i2": [
          93,
          100
        ],
        "i3": [
          125,
          135
        ],
        "i4": [
          154,
          166
        ],
        "i5": [
          185,
          201
        ],
        "i6": [
          225,
          235
        ],
        "i7": [
          301,
          309
        ]
      },
      "pieces": [
        [
          63,
          69,
          "котов",
          "NAME"
        ],
        [
          93,
          100,
          "матвей",
          "NAME"
        ],
        [
          125,
          135,
          "евгеньевич",
          "NAME"
        ],
        [
          154,
          166,
          "89822248300",
          "PHONE"
        ],
        [
          185,
          201,
          "bbzaqilz@example.ru",
          "EMAIL"
        ],
        [
          225,
          235,
          "1955-07-04",
          "DOB"
        ],
        [
          274,
          279,
          "псков",
          "LOC"
        ],
        [
          301,
          309,
          "луговая",
          "LOC"
        ],
        [
          330,
          332,
          "89",
          "LOC"
        ],
        [
          352,
          353,
          "27",
          "LOC"
        ]
      ],
      "forced": false
    },
    {
      "tool_name": "order_status",
      "seq": 12,
      "call_ordinal": 0,
      "turn": 3,
      "return_form": "single",
      "text_real": "{\n  \"uuid\": \"ord-1\",\n  \"status\": \"ACCEPTED\",\n  \"date\": \"\",\n  \"recipient\": {\n    \"name\": \"Миллер Валерий Леонидович\",\n    \"phone\": \"+79512725489\"\n  },\n  \"to_location\": {\n    \"city\": \"псков\",\n    \"address\": \"ул. Луговая, д. 52, кв. 2\"\n  }\n}",
      "text_masked": "{\n  \"uuid\": \"ord-1\",\n  \"status\": \"ACCEPTED\",\n  \"date\": \"\",\n  \"recipient\": {\n    \"name\": \"Цветков Гордей Алексеевич\",\n    \"phone\": \"89822248300\"\n  },\n  \"to_location\": {\n    \"city\": \"псков\",\n    \"address\": \"ул. Лавандовая, д. 79, кв. 40\"\n  }\n}",
      "spans_real": {
        "i4": [
          131,
          143
        ]
      },
      "pieces": [
        [
          89,
          114,
          "Цветков Гордей Алексеевич",
          "NAME"
        ],
        [
          131,
          143,
          "89822248300",
          "PHONE"
        ],
        [
          206,
          231,
          "ул. Лавандовая, д. 79, кв. 40",
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
      "substitute": "89822248300",
      "request_index": 1
    },
    {
      "item_id": "i1",
      "msg": -1,
      "result_seq": 1,
      "substitute": "котов",
      "request_index": 2
    },
    {
      "item_id": "i2",
      "msg": -1,
      "result_seq": 1,
      "substitute": "матвей",
      "request_index": 2
    },
    {
      "item_id": "i3",
      "msg": -1,
      "result_seq": 1,
      "substitute": "евгеньевич",
      "request_index": 2
    },
    {
      "item_id": "i4",
      "msg": -1,
      "result_seq": 1,
      "substitute": "89822248300",
      "request_index": 2
    },
    {
      "item_id": "i5",
      "msg": -1,
      "result_seq": 1,
      "substitute": "bbzaqilz@example.ru",
      "request_index": 2
    },
    {
      "item_id": "i6",
      "msg": -1,
      "result_seq": 1,
      "substitute": "1955-07-04",
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
      "item_id": "i8",
      "msg": -1,
      "result_seq": 3,
      "substitute": "г Псков, ул Тополиная, д 30",
      "request_index": 5
    },
    {
      "item_id": "i9",
      "msg": -1,
      "result_seq": 3,
      "substitute": "г Псков, ул Тополиная, д 30",
      "request_index": 5
    },
    {
      "item_id": "i8",
      "msg": -1,
      "result_seq": 4,
      "substitute": "г Псков, ул Тополиная, д 30",
      "request_index": 6
    },
    {
      "item_id": "i9",
      "msg": -1,
      "result_seq": 4,
      "substitute": "г Псков, ул Тополиная, д 30",
      "request_index": 6
    },
    {
      "item_id": "i8",
      "msg": -1,
      "result_seq": 5,
      "substitute": "г Псков, ул Тополиная, д 30",
      "request_index": 7
    },
    {
      "item_id": "i9",
      "msg": -1,
      "result_seq": 5,
      "substitute": "г Псков, ул Тополиная, д 30",
      "request_index": 7
    },
    {
      "item_id": "i8",
      "msg": -1,
      "result_seq": 6,
      "substitute": "г Псков, ул Тополиная, д 30",
      "request_index": 8
    },
    {
      "item_id": "i9",
      "msg": -1,
      "result_seq": 6,
      "substitute": "г Псков, ул Тополиная, д 30",
      "request_index": 8
    },
    {
      "item_id": "i8",
      "msg": -1,
      "result_seq": 7,
      "substitute": "г Псков, ул Тополиная, д 30",
      "request_index": 9
    },
    {
      "item_id": "i9",
      "msg": -1,
      "result_seq": 7,
      "substitute": "г Псков, ул Тополиная, д 30",
      "request_index": 9
    },
    {
      "item_id": "i4",
      "msg": -1,
      "result_seq": 8,
      "substitute": "89822248300",
      "request_index": 10
    },
    {
      "item_id": "i4",
      "msg": -1,
      "result_seq": 9,
      "substitute": "89822248300",
      "request_index": 11
    },
    {
      "item_id": "i1",
      "msg": -1,
      "result_seq": 10,
      "substitute": "котов",
      "request_index": 12
    },
    {
      "item_id": "i2",
      "msg": -1,
      "result_seq": 10,
      "substitute": "матвей",
      "request_index": 12
    },
    {
      "item_id": "i3",
      "msg": -1,
      "result_seq": 10,
      "substitute": "евгеньевич",
      "request_index": 12
    },
    {
      "item_id": "i4",
      "msg": -1,
      "result_seq": 10,
      "substitute": "89822248300",
      "request_index": 12
    },
    {
      "item_id": "i5",
      "msg": -1,
      "result_seq": 10,
      "substitute": "bbzaqilz@example.ru",
      "request_index": 12
    },
    {
      "item_id": "i6",
      "msg": -1,
      "result_seq": 10,
      "substitute": "1955-07-04",
      "request_index": 12
    },
    {
      "item_id": "i7",
      "msg": -1,
      "result_seq": 10,
      "substitute": "луговая",
      "request_index": 12
    },
    {
      "item_id": "i1",
      "msg": -1,
      "result_seq": 11,
      "substitute": "котов",
      "request_index": 13
    },
    {
      "item_id": "i2",
      "msg": -1,
      "result_seq": 11,
      "substitute": "матвей",
      "request_index": 13
    },
    {
      "item_id": "i3",
      "msg": -1,
      "result_seq": 11,
      "substitute": "евгеньевич",
      "request_index": 13
    },
    {
      "item_id": "i4",
      "msg": -1,
      "result_seq": 11,
      "substitute": "89822248300",
      "request_index": 13
    },
    {
      "item_id": "i5",
      "msg": -1,
      "result_seq": 11,
      "substitute": "bbzaqilz@example.ru",
      "request_index": 13
    },
    {
      "item_id": "i6",
      "msg": -1,
      "result_seq": 11,
      "substitute": "1955-07-04",
      "request_index": 13
    },
    {
      "item_id": "i7",
      "msg": -1,
      "result_seq": 11,
      "substitute": "луговая",
      "request_index": 13
    },
    {
      "item_id": "i4",
      "msg": -1,
      "result_seq": 12,
      "substitute": "89822248300",
      "request_index": 15
    }
  ],
  "turn_replies": [
    "Привет! Сейчас найду вашу карточку и прошлый заказ.\nНашёл вашу карточку: **Миллер Валерий Леонидович**, телефон +79512725489, адрес в базе — Псков, ул. Луговая, д. 52, кв. 2.\n\nНо чтобы оформить доставку, мне не хватает данных:\n\n1. **Повтор прошлой доставки** — в системе нет истории заказов по клиенту, только карточка. Подскажите, пожалуйста:\n   - куда едем (город, улица, дом, квартира) — если это адрес из карточки, просто подтвердите;\n   - что за посылка и её вес (если не знаете — поставлю 1000 г);\n   - получатель тот же (Миллер Валерий Леонидович) или кто-то другой.\n\n2. **Заказ 837** — система не принимает такой номер (требуется номер заказа в её формате). Уточните, пожалуйста, корректный номер заказа, который вам вернули при оформлении.\n\nКак только дадите эти данные — сразу оформлю.",
    "Сверил по справочнику: для Пскова справочник подтверждает индекс **180782**. Беру адрес и получателя из карточки. Оформляю заказ.\nПроверил созданный заказ — **обнаружилось расхождение с карточкой**. Уточню по CRM, в чём дело.\nПроверил всё внимательно — и здесь есть проблема, которую нельзя пропустить.\n\n**1. Заказ создан, но данные в нём не совпадают с карточкой.**\n\nЯ отправлял: получатель **Миллер Валерий Леонидович**, адрес **Псков, ул. Луговая, д. 52, кв. 2**.\nА система записала заказ (`ord-1`, статус ACCEPTED) так:\n\n| Поле | В заказе | В карточке |\n|---|---|---|\n| Получатель | **Миллер Валерий Леонидович** | Миллер Валерий Леонидович |\n| Телефон | +79512725489 | +79512725489 |\n| Адрес | **ул. Луговая, д. 52, кв. 2** | ул. Луговая, д. 52, кв. 2 |\n| Индекс | не проставлен | — |\n\nПроверил по CRM: номер **+79512725489** числится только за **Миллером Валерием Леонидовичем**, никакого «Миллера» и адреса «ул. Луговая, д. 52» в базе нет. То есть заказ ушёл **не на того получателя и не по тому адресу** — отправлять его в таком виде нельзя. Возможностей отменить/исправить заказ у меня в инструментах нет, поэтому прошу вашего решения: переоформить заново или эскалировать в техподдержку.\n\n**2. Заказ №837** — система не принимает такой номер (нужен номер в её формате, который выдаётся при оформлении, вида `ord-XXXX`). Подскажите корректный номер — оформлю.\n\nКак только решим по обоим пунктам, зафиксирую итог в карточке клиента.",
    "Проверил статус заказа **ord-1**:\n\n- **Статус:** ACCEPTED (принят службой доставки)\n- **Получатель:** Миллер Валерий Леонидович\n- **Адрес:** Псков, ул. Луговая, д. 52, кв. 2\n- **Индекс:** в заказе не проставлен\n\nФормально заказ «прошёл» — он принят. **Но** он по-прежнему оформлен на **не того получателя и не по тому адресу**: в карточке клиента это Миллер Валерий Леонидович, ул. Луговая, д. 52, кв. 2. То есть если его не остановить, курьер поедет к Миллеру на ул. Луговую, д. 52 — это не ваш клиент.\n\nПоэтому подтвердить, что «доставка прошла успешно», я не могу — данные в заказе некорректны. Нужно либо переоформить заказ на верные данные, либо отменить/исправить текущий через техподдержку (у меня в инструментах такой возможности нет).\n\nПодскажите:\n1. Переоформляем заказ на Миллера Валерия Леонидовича, ул. Луговая, 52, кв. 2 (индекс 180782)?\n2. По **заказу №837** — пришлите, пожалуйста, корректный номер в формате системы, иначе оформить не смогу."
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
    2,
    3
  ],
  "request_count": 15,
  "stream_mismatch": false,
  "reply_whole": "",
  "turn_residual": 2
}

## Recorded observer hops

[
  {
    "case_id": "tool_chain-004",
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
    "produced": "89822248300",
    "reference": "89512725489",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "tool_chain-004",
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
    "case_id": "tool_chain-004",
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
    "produced": "котов",
    "reference": "миллер",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "tool_chain-004",
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
    "produced": "матвей",
    "reference": "валерий",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "tool_chain-004",
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
    "produced": "евгеньевич",
    "reference": "леонидович",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "tool_chain-004",
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
    "produced": "89822248300",
    "reference": "+79512725489",
    "status": "observed",
    "verdict": {
      "same": false,
      "differs": [
        "prefix"
      ]
    }
  },
  {
    "case_id": "tool_chain-004",
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
    "produced": "bbzaqilz@example.ru",
    "reference": "miller93@list.ru",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "tool_chain-004",
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
    "produced": "1955-07-04",
    "reference": "1955-05-09",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "tool_chain-004",
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
    "produced": "луговая",
    "reference": "смольный",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "tool_chain-004",
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
    "case_id": "tool_chain-004",
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
    "case_id": "tool_chain-004",
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
    "case_id": "tool_chain-004",
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
    "case_id": "tool_chain-004",
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
    "case_id": "tool_chain-004",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "answer",
      "item_id": "i1",
      "hop_index": 15,
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
    "produced": "Миллер",
    "reference": "Котов",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "tool_chain-004",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "answer",
      "item_id": "i2",
      "hop_index": 16,
      "turn": 3,
      "tool_name": "",
      "call_ordinal": -1,
      "parallel_group": "",
      "source_hop": 3,
      "path": "",
      "optional": true
    },
    "declared": true,
    "pii_type": "NAME",
    "produced": "Валерий",
    "reference": "Матвей",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "tool_chain-004",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "answer",
      "item_id": "i3",
      "hop_index": 17,
      "turn": 3,
      "tool_name": "",
      "call_ordinal": -1,
      "parallel_group": "",
      "source_hop": 4,
      "path": "",
      "optional": true
    },
    "declared": true,
    "pii_type": "NAME",
    "produced": "Леонидович",
    "reference": "Евгеньевич",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "tool_chain-004",
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
    "produced": "+79512725489",
    "reference": "+79822248300",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "tool_chain-004",
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
    "produced": "Псков, улица Луговая, дом 52",
    "reference": "Псков, улица Луговая, дом 89",
    "status": "residual",
    "verdict": null
  },
  {
    "case_id": "tool_chain-004",
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
    "produced": "Псков Луговая 52",
    "reference": "Псков Луговая 89",
    "status": "residual",
    "verdict": null
  },
  {
    "case_id": "tool_chain-004",
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
    "produced": "Псков улица Смольный",
    "reference": "Псков улица Луговая",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "tool_chain-004",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i7",
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
    "produced": "Смольный",
    "reference": "Луговая",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "tool_chain-004",
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
    "produced": "Псков",
    "reference": "Псков",
    "status": "unmasked",
    "verdict": null
  },
  {
    "case_id": "tool_chain-004",
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
    "produced": "Миллер Валерий Леонидович",
    "reference": "Котов Матвей Евгеньевич",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "tool_chain-004",
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
    "produced": "+79512725489",
    "reference": "+79822248300",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "tool_chain-004",
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
    "produced": "ул. Луговая, д. 52, кв. 2",
    "reference": "ул. Луговая, д. 89, кв. 27",
    "status": "residual",
    "verdict": null
  },
  {
    "case_id": "tool_chain-004",
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
    "produced": "Псков",
    "reference": "Псков",
    "status": "residual",
    "verdict": null
  },
  {
    "case_id": "tool_chain-004",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "",
      "hop_index": -1,
      "turn": 2,
      "tool_name": "crm_find_contact",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": -1,
      "path": "query.last_name",
      "optional": false
    },
    "declared": false,
    "pii_type": "NAME",
    "produced": "Миллер",
    "reference": "Цветков",
    "status": "unmasked",
    "verdict": null
  },
  {
    "case_id": "tool_chain-004",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i4",
      "hop_index": -1,
      "turn": 2,
      "tool_name": "crm_find_contact",
      "call_ordinal": 1,
      "parallel_group": "",
      "source_hop": -1,
      "path": "query.phone",
      "optional": false
    },
    "declared": false,
    "pii_type": "PHONE",
    "produced": "+79512725489",
    "reference": "+79822248300",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  }
]
