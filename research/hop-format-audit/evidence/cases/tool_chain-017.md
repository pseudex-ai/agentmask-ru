# tool_chain-017 | source C | repeat 0

Synthetic benchmark evidence. Verbatim serialized fields; no inferred verdicts.

## Case specification

{
  "base": {
    "id": "tool_chain-017",
    "kind": "tool_chain",
    "register": "chat",
    "provenance": {
      "kind": "template",
      "corpus": "authored",
      "key": "",
      "shape": "",
      "selection": "rare",
      "weight": 1.0,
      "licence": "authored"
    },
    "cluster": "PHONE:9823859329",
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
        "content": "повторите прошлую доставку по номеру 8-982-385-93-29 а также 2 гектаров",
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
        "content": "и статус заказа посмотрите",
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
          "last_name": "бударин",
          "first_name": "ефим",
          "middle_name": "ефимович",
          "phone": "+79823859329",
          "email": "budarin81@gmail.com",
          "birth_date": "1984-08-14",
          "address": {
            "city": "казань",
            "street": "зацепская",
            "house": "7",
            "flat": "31"
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
          "value": "Республика Татарстан, г Казань, ул Зацепская, д 7",
          "postal_code": "420282",
          "region": "Республика Татарстан",
          "city": "казань",
          "street": "зацепская",
          "house": "7",
          "flat": "",
          "fias_id": "5668a343-10b5-40f6-8e0e-5709e5c76a7a"
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
        "identity": "p17",
        "value": "бударин",
        "canonical": "бударин",
        "parts": {
          "surname": "бударин",
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
        "identity": "p17",
        "value": "ефим",
        "canonical": "ефим",
        "parts": {
          "given": "ефим",
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
        "identity": "p17",
        "value": "ефимович",
        "canonical": "ефимович",
        "parts": {
          "patronymic": "ефимович",
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
        "identity": "p17",
        "value": "+79823859329",
        "canonical": "+79823859329",
        "parts": {
          "digits": "9823859329"
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
        "identity": "p17",
        "value": "budarin81@gmail.com",
        "canonical": "budarin81@gmail.com",
        "parts": {
          "local": "budarin81",
          "domain": "gmail.com"
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
        "identity": "p17",
        "value": "1984-08-14",
        "canonical": "1984-08-14",
        "parts": {
          "iso": "1984-08-14"
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
        "identity": "p17.home",
        "value": "зацепская",
        "canonical": "зацепская",
        "parts": {
          "street": "зацепская",
          "street_type": "проезд",
          "house": "7",
          "flat": "31",
          "city": "казань"
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
        "identity": "p17.dir",
        "value": "зацепская",
        "canonical": "зацепская",
        "parts": {
          "street": "зацепская"
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
        "identity": "p17.dir",
        "value": "Республика Татарстан, г Казань, ул Зацепская, д 7",
        "canonical": "Республика Татарстан, г Казань, ул Зацепская, д 7",
        "parts": {
          "city": "казань",
          "street": "зацепская",
          "house": "7"
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
        "identity": "p17",
        "value": "8-982-385-93-29",
        "canonical": "+79823859329",
        "parts": {
          "digits": "9823859329"
        },
        "where": {
          "kind": "message",
          "msg": 1,
          "start": 37,
          "end": 52,
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
        "value": "2 гектаров",
        "start": 61,
        "end": 71,
        "msg": 1,
        "family": "measure",
        "why": "число с единицей измерения: «территория пять гектаров» проходит все адресные признаки и адресом не является"
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
      "primary_identity": "p17",
      "must_contain": [],
      "must_not_contain": [],
      "validate_types": []
    },
    "trace": [
      {
        "msg": 1,
        "key": "",
        "start": 0,
        "end": 9,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 1,
        "key": "",
        "start": 9,
        "end": 10,
        "origin": "literal"
      },
      {
        "msg": 1,
        "key": "",
        "start": 10,
        "end": 17,
        "origin": "chunk:noisy_word"
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
        "end": 29,
        "origin": "chunk:noisy_word"
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
        "key": "ph1",
        "start": 37,
        "end": 52,
        "origin": "value:ph1"
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
        "end": 54,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 1,
        "key": "",
        "start": 54,
        "end": 55,
        "origin": "literal"
      },
      {
        "msg": 1,
        "key": "",
        "start": 55,
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
        "key": "neg1",
        "start": 61,
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
        "end": 26,
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
    "case_id": "tool_chain-017",
    "arm": "I",
    "repeat": 0,
    "calls": [
      {
        "name": "crm_find_contact",
        "written": {
          "query": {
            "phone": "+79521906213"
          }
        },
        "restored": {
          "query": {
            "phone": "+79823859329"
          }
        },
        "residual": {},
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "query": {
            "phone": "+79823859329"
          }
        },
        "seq": 1
      },
      {
        "name": "address_suggest",
        "written": {
          "count": 10,
          "query": "2 гектаров"
        },
        "restored": {
          "count": 10,
          "query": "2 гектаров"
        },
        "residual": {},
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "count": 10,
          "query": "2 гектаров"
        },
        "seq": 2
      },
      {
        "name": "address_suggest",
        "written": {
          "count": 10,
          "query": "гектар казань"
        },
        "restored": {
          "count": 10,
          "query": "гектар казань"
        },
        "residual": {},
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "count": 10,
          "query": "гектар казань"
        },
        "seq": 3
      },
      {
        "name": "address_suggest",
        "written": {
          "count": 10,
          "query": "гектар"
        },
        "restored": {
          "count": 10,
          "query": "гектар"
        },
        "residual": {},
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "count": 10,
          "query": "гектар"
        },
        "seq": 4
      },
      {
        "name": "address_suggest",
        "written": {
          "count": 10,
          "query": "грушевая"
        },
        "restored": {
          "count": 10,
          "query": "зацепская"
        },
        "residual": {},
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "count": 10,
          "query": "зацепская"
        },
        "seq": 5
      },
      {
        "name": "address_suggest",
        "written": {
          "count": 5,
          "query": "казань барбарисовая 3"
        },
        "restored": {
          "count": 5,
          "query": "казань зацепская 7"
        },
        "residual": {},
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "count": 5,
          "query": "казань зацепская 7"
        },
        "seq": 6
      },
      {
        "name": "crm_find_contact",
        "written": {
          "query": {
            "last_name": "гектаров"
          }
        },
        "restored": {
          "query": {
            "last_name": "гектаров"
          }
        },
        "residual": {},
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "query": {
            "last_name": "гектаров"
          }
        },
        "seq": 7
      },
      {
        "name": "crm_find_contact",
        "written": {
          "query": {
            "last_name": "гектар"
          }
        },
        "restored": {
          "query": {
            "last_name": "гектар"
          }
        },
        "residual": {},
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "query": {
            "last_name": "гектар"
          }
        },
        "seq": 8
      },
      {
        "name": "address_suggest",
        "written": {
          "count": 10,
          "query": "барбарисовая"
        },
        "restored": {
          "count": 10,
          "query": "зацепская"
        },
        "residual": {},
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "count": 10,
          "query": "зацепская"
        },
        "seq": 9
      },
      {
        "name": "address_suggest",
        "written": {
          "count": 10,
          "query": "казань барбарисовая 3"
        },
        "restored": {
          "count": 10,
          "query": "казань зацепская 7"
        },
        "residual": {},
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "count": 10,
          "query": "казань зацепская 7"
        },
        "seq": 10
      },
      {
        "name": "delivery_create_order",
        "written": {
          "comment": "Повтор предыдущей доставки; получатель — владелец карточки",
          "packages": [
            {
              "weight": 1000
            }
          ],
          "recipient": {
            "name": "Петренко Василий Семёнович",
            "phones": [
              {
                "number": "+79521906213"
              }
            ]
          },
          "to_location": {
            "address": "ул. Барбарисовая, д. 3, кв. 228",
            "city": "Казань",
            "postal_code": "420282"
          }
        },
        "restored": {
          "comment": "Повтор предыдущей доставки; получатель — владелец карточки",
          "packages": [
            {
              "weight": 1000
            }
          ],
          "recipient": {
            "name": "Бударин Ефим Ефимович",
            "phones": [
              {
                "number": "+79823859329"
              }
            ]
          },
          "to_location": {
            "address": "ул. Барбарисовая, д. 7, кв. 31",
            "city": "Казань",
            "postal_code": "420282"
          }
        },
        "residual": {
          "to_location.address": [
            "барбарисовая"
          ]
        },
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "comment": "Повтор предыдущей доставки; получатель — владелец карточки",
          "packages": [
            {
              "weight": 1000
            }
          ],
          "recipient": {
            "name": "Бударин Ефим Ефимович",
            "phones": [
              "+79823859329"
            ]
          },
          "to_location": {
            "address": "ул. Барбарисовая, д. 7, кв. 31",
            "city": "казань",
            "postal_code": "420282"
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
          "order_id": "ord-7"
        },
        "residual": {},
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "order_id": "ord-7"
        },
        "seq": 12
      },
      {
        "name": "crm_find_contact",
        "written": {
          "query": {
            "last_name": "бобров"
          }
        },
        "restored": {
          "query": {
            "last_name": "бударин"
          }
        },
        "residual": {},
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "query": {
            "last_name": "бударин"
          }
        },
        "seq": 13
      },
      {
        "name": "order_status",
        "written": {
          "order_id": "ord-7"
        },
        "restored": {
          "order_id": "ord-7"
        },
        "residual": {},
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "order_id": "ord-7"
        },
        "seq": 14
      },
      {
        "name": "crm_add_note",
        "written": {
          "entity_id": "c-1",
          "note_type": "call_in",
          "text": "Повтор прошлой доставки по номеру 8-952-190-62-13. Создан заказ ord-1 (ACCEPTED), служба записала получателя: Бобров Матвей Михайлович, г. Казань, ул. Кленовая, д. 5, кв. 140, индекс 420282, вес 1000 г. В карточке клиента получатель/адрес иные: Петренко Василий Семёнович, г. Казань, ул. Барбарисовая, д. 3, кв. 228. Расхождение — уточняется у клиента. Также не расшифровано «2 гектаров»."
        },
        "restored": {
          "entity_id": "c-7",
          "note_type": "call_in",
          "text": "Повтор прошлой доставки по номеру +79823859329. Создан заказ ord-7 (ACCEPTED), служба записала получателя: Бударин Ефим Ефимович, г. Казань, ул. Барбарисовая, д. 7, кв. 31, индекс 420282, вес 1000 г. В карточке клиента получатель/адрес иные: Бударин Ефим Ефимович, г. Казань, ул. Барбарисовая, д. 7, кв. 31. Расхождение — уточняется у клиента. Также не расшифровано «2 гектаров»."
        },
        "residual": {
          "text": [
            "барбарисовая"
          ]
        },
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "entity_id": "c-7",
          "note_type": "call_in",
          "text": "Повтор прошлой доставки по номеру +79823859329. Создан заказ ord-7 (ACCEPTED), служба записала получателя: Бударин Ефим Ефимович, г. Казань, ул. Барбарисовая, д. 7, кв. 31, индекс 420282, вес 1000 г. В карточке клиента получатель/адрес иные: Бударин Ефим Ефимович, г. Казань, ул. Барбарисовая, д. 7, кв. 31. Расхождение — уточняется у клиента. Также не расшифровано «2 гектаров»."
        },
        "seq": 15
      },
      {
        "name": "order_status",
        "written": {
          "order_id": "ord-1"
        },
        "restored": {
          "order_id": "ord-7"
        },
        "residual": {},
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "order_id": "ord-7"
        },
        "seq": 16
      },
      {
        "name": "order_status",
        "written": {
          "order_id": "1"
        },
        "restored": {
          "order_id": "7"
        },
        "residual": {},
        "refusal_path": "order_id",
        "refusal_rule": "order_id_format",
        "parsed": null,
        "seq": 17
      },
      {
        "name": "order_status",
        "written": {
          "order_id": "ord-1"
        },
        "restored": {
          "order_id": "ord-7"
        },
        "residual": {},
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "order_id": "ord-7"
        },
        "seq": 18
      }
    ],
    "state": [
      {
        "fields": {
          "comment": "Повтор предыдущей доставки; получатель — владелец карточки",
          "packages": [
            {
              "weight": 1000
            }
          ],
          "recipient": {
            "name": "Бударин Ефим Ефимович",
            "phones": [
              "+79823859329"
            ]
          },
          "to_location": {
            "address": "ул. Барбарисовая, д. 7, кв. 31",
            "city": "казань",
            "postal_code": "420282"
          }
        },
        "id": "ord-1",
        "seq": 11,
        "table": "orders",
        "tool": "delivery_create_order"
      },
      {
        "fields": {
          "entity_id": "c-7",
          "note_type": "call_in",
          "text": "Повтор прошлой доставки по номеру +79823859329. Создан заказ ord-7 (ACCEPTED), служба записала получателя: Бударин Ефим Ефимович, г. Казань, ул. Барбарисовая, д. 7, кв. 31, индекс 420282, вес 1000 г. В карточке клиента получатель/адрес иные: Бударин Ефим Ефимович, г. Казань, ул. Барбарисовая, д. 7, кв. 31. Расхождение — уточняется у клиента. Также не расшифровано «2 гектаров»."
        },
        "id": "note-1",
        "seq": 15,
        "table": "notes",
        "tool": "crm_add_note"
      }
    ],
    "reply": "Проверил статус — и здесь проблема.\n\n**Статус заказа: `ORDER_NOT_FOUND` («заказ не найден»).**\n\nЗапрос по номеру `ord-7` (который выдала система при оформлении) возвращает ошибку «заказ не найден»; в тексте ошибки при этом фигурирует subject **`ord-7`**. То есть, несмотря на то, что при создании заказ прошёл со статусом **ACCEPTED**, по этому номеру сервис его сейчас не находит — запись, похоже, ещё не синхронизировалась либо номер заказа иной.\n\nИтого на текущий момент:\n7. **Заказ оформлен** (`ord-7`, ACCEPTED), но **проверить его статус по номеру не удаётся** — система отдаёт «не найдено».\n2. Напоминаю про нерешённое: в заказе получатель/адрес — **Бударин Ефим Ефимович, ул. Барбарисовая, д. 7–140**, а в карточке — **Бударин Ефим Ефимович, ул. Барбарисовая, 7–31**. Нужно решить, какой вариант верный.\n7. По-прежнему не расшифровано **«2 гектаров»**.\n\nПодскажите, пожалуйста:\n- есть ли у вас на руках **номер заказа** (или смс с ним) — попробую статус по нему;\n- какой получатель/адрес всё-таки нужен;\n- что означает «2 гектаров».",
    "termination": "done",
    "cost_usd": 0.032188,
    "substitutes": {
      "i1": [
        "петренко",
        {
          "surname": "петренко"
        }
      ],
      "i10": [
        "8-952-190-62-13",
        {
          "digits": "9521906213"
        }
      ],
      "i2": [
        "василий",
        {
          "given": "василий"
        }
      ],
      "i3": [
        "семёнович",
        {
          "patronymic": "семёнович"
        }
      ],
      "i4": [
        "8-952-190-62-13",
        {
          "digits": "9521906213"
        }
      ],
      "i5": [
        "zdshxzeq@example.ru",
        {
          "domain": "example.ru",
          "local": "zdshxzeq"
        }
      ],
      "i6": [
        "1984-01-07",
        {
          "iso": "1984-01-07"
        }
      ],
      "i7": [
        "барбарисовая",
        {
          "street": "барбарисовая"
        }
      ],
      "i8": [
        "барбарисовая",
        {
          "street": "барбарисовая"
        }
      ]
    },
    "masked_spans": {
      "0": [],
      "1": [
        [
          37,
          52
        ]
      ],
      "2": [],
      "3": []
    }
  },
  "reply_raw": "Проверил статус — и здесь проблема.\n\n**Статус заказа: `ORDER_NOT_FOUND` («заказ не найден»).**\n\nЗапрос по номеру `ord-1` (который выдала система при оформлении) возвращает ошибку «заказ не найден»; в тексте ошибки при этом фигурирует subject **`ord-7`**. То есть, несмотря на то, что при создании заказ прошёл со статусом **ACCEPTED**, по этому номеру сервис его сейчас не находит — запись, похоже, ещё не синхронизировалась либо номер заказа иной.\n\nИтого на текущий момент:\n1. **Заказ оформлен** (`ord-1`, ACCEPTED), но **проверить его статус по номеру не удаётся** — система отдаёт «не найдено».\n2. Напоминаю про нерешённое: в заказе получатель/адрес — **Бобров Матвей Михайлович, ул. Кленовая, 5–140**, а в карточке — **Петренко Василий Семёнович, ул. Барбарисовая, 3–228**. Нужно решить, какой вариант верный.\n3. По-прежнему не расшифровано **«2 гектаров»**.\n\nПодскажите, пожалуйста:\n- есть ли у вас на руках **номер заказа** (или смс с ним) — попробую статус по нему;\n- какой получатель/адрес всё-таки нужен;\n- что означает «2 гектаров».",
  "control_reply": "Проверил статус заказа **ord-1**:\n\n- **Статус:** ACCEPTED (принят в службу доставки)\n- **Получатель:** Бударин Ефим Ефимович, +7 982 385-93-29\n- **Адрес:** Казань, ул. Зацепская, д. 7, кв. 31\n\nЗаказ оформлен и принят.\n\nНапоминаю про два незакрытых вопроса:\n1. **Курьер** — вызывать? Нужен интервал (дата и часы).\n2. **«2 гектаров»** — уточните, что это, или скажите, что не требуется.",
  "tool_results": [
    {
      "tool_name": "crm_find_contact",
      "seq": 1,
      "call_ordinal": 0,
      "turn": 1,
      "return_form": "list",
      "text_real": "{\n  \"contacts\": [\n    {\n      \"id\": \"c-1\",\n      \"last_name\": \"бударин\",\n      \"first_name\": \"ефим\",\n      \"middle_name\": \"ефимович\",\n      \"phone\": \"+79823859329\",\n      \"email\": \"budarin81@gmail.com\",\n      \"birth_date\": \"1984-08-14\",\n      \"address\": {\n        \"city\": \"казань\",\n        \"street\": \"зацепская\",\n        \"house\": \"7\",\n        \"flat\": \"31\"\n      }\n    }\n  ]\n}",
      "text_masked": "{\n  \"contacts\": [\n    {\n      \"id\": \"c-1\",\n      \"last_name\": \"петренко\",\n      \"first_name\": \"василий\",\n      \"middle_name\": \"семёнович\",\n      \"phone\": \"8-952-190-62-13\",\n      \"email\": \"zdshxzeq@example.ru\",\n      \"birth_date\": \"1984-01-07\",\n      \"address\": {\n        \"city\": \"казань\",\n        \"street\": \"барбарисовая\",\n        \"house\": \"3\",\n        \"flat\": \"228\"\n      }\n    }\n  ]\n}",
      "spans_real": {
        "i1": [
          63,
          70
        ],
        "i2": [
          94,
          98
        ],
        "i3": [
          123,
          131
        ],
        "i4": [
          150,
          162
        ],
        "i5": [
          181,
          200
        ],
        "i6": [
          224,
          234
        ],
        "i7": [
          301,
          310
        ]
      },
      "pieces": [
        [
          63,
          70,
          "петренко",
          "NAME"
        ],
        [
          94,
          98,
          "василий",
          "NAME"
        ],
        [
          123,
          131,
          "семёнович",
          "NAME"
        ],
        [
          150,
          162,
          "8-952-190-62-13",
          "PHONE"
        ],
        [
          181,
          200,
          "zdshxzeq@example.ru",
          "EMAIL"
        ],
        [
          224,
          234,
          "1984-01-07",
          "DOB"
        ],
        [
          273,
          279,
          "казань",
          "LOC"
        ],
        [
          301,
          310,
          "барбарисовая",
          "LOC"
        ],
        [
          331,
          332,
          "3",
          "LOC"
        ],
        [
          352,
          354,
          "228",
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
      "text_real": "{\n  \"suggestions\": [\n    {\n      \"value\": \"г Казань, ул Зацепская, д 7\",\n      \"confidence\": \"0.00\",\n      \"data\": {\n        \"postal_code\": \"420282\",\n        \"region\": \"Республика Татарстан\",\n        \"city\": \"казань\",\n        \"street\": \"зацепская\",\n        \"house\": \"7\",\n        \"flat\": \"\",\n        \"fias_id\": \"5668a343-10b5-40f6-8e0e-5709e5c76a7a\"\n      }\n    }\n  ]\n}",
      "text_masked": "{\n  \"suggestions\": [\n    {\n      \"value\": \"г Казань, ул Грушевая, д 1\",\n      \"confidence\": \"0.00\",\n      \"data\": {\n        \"postal_code\": \"420282\",\n        \"region\": \"Республика Татарстан\",\n        \"city\": \"казань\",\n        \"street\": \"грушевая\",\n        \"house\": \"1\",\n        \"flat\": \"\",\n        \"fias_id\": \"5668a343-10b5-40f6-8e0e-5709e5c76a7a\"\n      }\n    }\n  ]\n}",
      "spans_real": {
        "i8": [
          56,
          65
        ],
        "i9": [
          43,
          70
        ]
      },
      "pieces": [
        [
          43,
          70,
          "г Казань, ул Грушевая, д 1",
          "LOC"
        ],
        [
          209,
          215,
          "казань",
          "LOC"
        ],
        [
          237,
          246,
          "грушевая",
          "LOC"
        ],
        [
          267,
          268,
          "1",
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
      "text_real": "{\n  \"suggestions\": [\n    {\n      \"value\": \"г Казань, ул Зацепская, д 7\",\n      \"confidence\": \"0.50\",\n      \"data\": {\n        \"postal_code\": \"420282\",\n        \"region\": \"Республика Татарстан\",\n        \"city\": \"казань\",\n        \"street\": \"зацепская\",\n        \"house\": \"7\",\n        \"flat\": \"\",\n        \"fias_id\": \"5668a343-10b5-40f6-8e0e-5709e5c76a7a\"\n      }\n    }\n  ]\n}",
      "text_masked": "{\n  \"suggestions\": [\n    {\n      \"value\": \"г Казань, ул Грушевая, д 1\",\n      \"confidence\": \"0.50\",\n      \"data\": {\n        \"postal_code\": \"420282\",\n        \"region\": \"Республика Татарстан\",\n        \"city\": \"казань\",\n        \"street\": \"грушевая\",\n        \"house\": \"1\",\n        \"flat\": \"\",\n        \"fias_id\": \"5668a343-10b5-40f6-8e0e-5709e5c76a7a\"\n      }\n    }\n  ]\n}",
      "spans_real": {
        "i8": [
          56,
          65
        ],
        "i9": [
          43,
          70
        ]
      },
      "pieces": [
        [
          43,
          70,
          "г Казань, ул Грушевая, д 1",
          "LOC"
        ],
        [
          209,
          215,
          "казань",
          "LOC"
        ],
        [
          237,
          246,
          "грушевая",
          "LOC"
        ],
        [
          267,
          268,
          "1",
          "LOC"
        ]
      ],
      "forced": false
    },
    {
      "tool_name": "address_suggest",
      "seq": 4,
      "call_ordinal": 2,
      "turn": 1,
      "return_form": "canon",
      "text_real": "{\n  \"suggestions\": [\n    {\n      \"value\": \"г Казань, ул Зацепская, д 7\",\n      \"confidence\": \"0.00\",\n      \"data\": {\n        \"postal_code\": \"420282\",\n        \"region\": \"Республика Татарстан\",\n        \"city\": \"казань\",\n        \"street\": \"зацепская\",\n        \"house\": \"7\",\n        \"flat\": \"\",\n        \"fias_id\": \"5668a343-10b5-40f6-8e0e-5709e5c76a7a\"\n      }\n    }\n  ]\n}",
      "text_masked": "{\n  \"suggestions\": [\n    {\n      \"value\": \"г Казань, ул Грушевая, д 1\",\n      \"confidence\": \"0.00\",\n      \"data\": {\n        \"postal_code\": \"420282\",\n        \"region\": \"Республика Татарстан\",\n        \"city\": \"казань\",\n        \"street\": \"грушевая\",\n        \"house\": \"1\",\n        \"flat\": \"\",\n        \"fias_id\": \"5668a343-10b5-40f6-8e0e-5709e5c76a7a\"\n      }\n    }\n  ]\n}",
      "spans_real": {
        "i8": [
          56,
          65
        ],
        "i9": [
          43,
          70
        ]
      },
      "pieces": [
        [
          43,
          70,
          "г Казань, ул Грушевая, д 1",
          "LOC"
        ],
        [
          209,
          215,
          "казань",
          "LOC"
        ],
        [
          237,
          246,
          "грушевая",
          "LOC"
        ],
        [
          267,
          268,
          "1",
          "LOC"
        ]
      ],
      "forced": false
    },
    {
      "tool_name": "address_suggest",
      "seq": 5,
      "call_ordinal": 3,
      "turn": 1,
      "return_form": "canon",
      "text_real": "{\n  \"suggestions\": [\n    {\n      \"value\": \"г Казань, ул Зацепская, д 7\",\n      \"confidence\": \"1.00\",\n      \"data\": {\n        \"postal_code\": \"420282\",\n        \"region\": \"Республика Татарстан\",\n        \"city\": \"казань\",\n        \"street\": \"зацепская\",\n        \"house\": \"7\",\n        \"flat\": \"\",\n        \"fias_id\": \"5668a343-10b5-40f6-8e0e-5709e5c76a7a\"\n      }\n    }\n  ]\n}",
      "text_masked": "{\n  \"suggestions\": [\n    {\n      \"value\": \"г Казань, ул Грушевая, д 1\",\n      \"confidence\": \"1.00\",\n      \"data\": {\n        \"postal_code\": \"420282\",\n        \"region\": \"Республика Татарстан\",\n        \"city\": \"казань\",\n        \"street\": \"грушевая\",\n        \"house\": \"1\",\n        \"flat\": \"\",\n        \"fias_id\": \"5668a343-10b5-40f6-8e0e-5709e5c76a7a\"\n      }\n    }\n  ]\n}",
      "spans_real": {
        "i8": [
          56,
          65
        ],
        "i9": [
          43,
          70
        ]
      },
      "pieces": [
        [
          43,
          70,
          "г Казань, ул Грушевая, д 1",
          "LOC"
        ],
        [
          209,
          215,
          "казань",
          "LOC"
        ],
        [
          237,
          246,
          "грушевая",
          "LOC"
        ],
        [
          267,
          268,
          "1",
          "LOC"
        ]
      ],
      "forced": false
    },
    {
      "tool_name": "address_suggest",
      "seq": 6,
      "call_ordinal": 4,
      "turn": 1,
      "return_form": "canon",
      "text_real": "{\n  \"suggestions\": [\n    {\n      \"value\": \"г Казань, ул Зацепская, д 7\",\n      \"confidence\": \"1.00\",\n      \"data\": {\n        \"postal_code\": \"420282\",\n        \"region\": \"Республика Татарстан\",\n        \"city\": \"казань\",\n        \"street\": \"зацепская\",\n        \"house\": \"7\",\n        \"flat\": \"\",\n        \"fias_id\": \"5668a343-10b5-40f6-8e0e-5709e5c76a7a\"\n      }\n    }\n  ]\n}",
      "text_masked": "{\n  \"suggestions\": [\n    {\n      \"value\": \"г Казань, ул Грушевая, д 1\",\n      \"confidence\": \"1.00\",\n      \"data\": {\n        \"postal_code\": \"420282\",\n        \"region\": \"Республика Татарстан\",\n        \"city\": \"казань\",\n        \"street\": \"грушевая\",\n        \"house\": \"1\",\n        \"flat\": \"\",\n        \"fias_id\": \"5668a343-10b5-40f6-8e0e-5709e5c76a7a\"\n      }\n    }\n  ]\n}",
      "spans_real": {
        "i8": [
          56,
          65
        ],
        "i9": [
          43,
          70
        ]
      },
      "pieces": [
        [
          43,
          70,
          "г Казань, ул Грушевая, д 1",
          "LOC"
        ],
        [
          209,
          215,
          "казань",
          "LOC"
        ],
        [
          237,
          246,
          "грушевая",
          "LOC"
        ],
        [
          267,
          268,
          "1",
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
      "return_form": "empty",
      "text_real": "{\n  \"contacts\": [\n    \n  ]\n}",
      "text_masked": "{\n  \"contacts\": [\n    \n  ]\n}",
      "spans_real": {},
      "pieces": [],
      "forced": false
    },
    {
      "tool_name": "crm_find_contact",
      "seq": 8,
      "call_ordinal": 2,
      "turn": 1,
      "return_form": "empty",
      "text_real": "{\n  \"contacts\": [\n    \n  ]\n}",
      "text_masked": "{\n  \"contacts\": [\n    \n  ]\n}",
      "spans_real": {},
      "pieces": [],
      "forced": false
    },
    {
      "tool_name": "address_suggest",
      "seq": 9,
      "call_ordinal": 0,
      "turn": 2,
      "return_form": "canon",
      "text_real": "{\n  \"suggestions\": [\n    {\n      \"value\": \"г Казань, ул Зацепская, д 7\",\n      \"confidence\": \"1.00\",\n      \"data\": {\n        \"postal_code\": \"420282\",\n        \"region\": \"Республика Татарстан\",\n        \"city\": \"казань\",\n        \"street\": \"зацепская\",\n        \"house\": \"7\",\n        \"flat\": \"\",\n        \"fias_id\": \"5668a343-10b5-40f6-8e0e-5709e5c76a7a\"\n      }\n    }\n  ]\n}",
      "text_masked": "{\n  \"suggestions\": [\n    {\n      \"value\": \"г Казань, ул Грушевая, д 1\",\n      \"confidence\": \"1.00\",\n      \"data\": {\n        \"postal_code\": \"420282\",\n        \"region\": \"Республика Татарстан\",\n        \"city\": \"казань\",\n        \"street\": \"грушевая\",\n        \"house\": \"1\",\n        \"flat\": \"\",\n        \"fias_id\": \"5668a343-10b5-40f6-8e0e-5709e5c76a7a\"\n      }\n    }\n  ]\n}",
      "spans_real": {
        "i8": [
          56,
          65
        ],
        "i9": [
          43,
          70
        ]
      },
      "pieces": [
        [
          43,
          70,
          "г Казань, ул Грушевая, д 1",
          "LOC"
        ],
        [
          209,
          215,
          "казань",
          "LOC"
        ],
        [
          237,
          246,
          "грушевая",
          "LOC"
        ],
        [
          267,
          268,
          "1",
          "LOC"
        ]
      ],
      "forced": false
    },
    {
      "tool_name": "address_suggest",
      "seq": 10,
      "call_ordinal": 1,
      "turn": 2,
      "return_form": "canon",
      "text_real": "{\n  \"suggestions\": [\n    {\n      \"value\": \"г Казань, ул Зацепская, д 7\",\n      \"confidence\": \"1.00\",\n      \"data\": {\n        \"postal_code\": \"420282\",\n        \"region\": \"Республика Татарстан\",\n        \"city\": \"казань\",\n        \"street\": \"зацепская\",\n        \"house\": \"7\",\n        \"flat\": \"\",\n        \"fias_id\": \"5668a343-10b5-40f6-8e0e-5709e5c76a7a\"\n      }\n    }\n  ]\n}",
      "text_masked": "{\n  \"suggestions\": [\n    {\n      \"value\": \"г Казань, ул Грушевая, д 1\",\n      \"confidence\": \"1.00\",\n      \"data\": {\n        \"postal_code\": \"420282\",\n        \"region\": \"Республика Татарстан\",\n        \"city\": \"казань\",\n        \"street\": \"грушевая\",\n        \"house\": \"1\",\n        \"flat\": \"\",\n        \"fias_id\": \"5668a343-10b5-40f6-8e0e-5709e5c76a7a\"\n      }\n    }\n  ]\n}",
      "spans_real": {
        "i8": [
          56,
          65
        ],
        "i9": [
          43,
          70
        ]
      },
      "pieces": [
        [
          43,
          70,
          "г Казань, ул Грушевая, д 1",
          "LOC"
        ],
        [
          209,
          215,
          "казань",
          "LOC"
        ],
        [
          237,
          246,
          "грушевая",
          "LOC"
        ],
        [
          267,
          268,
          "1",
          "LOC"
        ]
      ],
      "forced": false
    },
    {
      "tool_name": "delivery_create_order",
      "seq": 11,
      "call_ordinal": 0,
      "turn": 2,
      "return_form": "single",
      "text_real": "{\n  \"uuid\": \"ord-1\",\n  \"status\": \"ACCEPTED\",\n  \"recipient\": {\n    \"name\": \"Бударин Ефим Ефимович\",\n    \"phone\": \"+79823859329\"\n  },\n  \"to_location\": {\n    \"postal_code\": \"420282\",\n    \"city\": \"казань\",\n    \"address\": \"ул. Барбарисовая, д. 7, кв. 31\"\n  }\n}",
      "text_masked": "{\n  \"uuid\": \"ord-1\",\n  \"status\": \"ACCEPTED\",\n  \"recipient\": {\n    \"name\": \"Бобров Матвей Михайлович\",\n    \"phone\": \"8-952-190-62-13\"\n  },\n  \"to_location\": {\n    \"postal_code\": \"420282\",\n    \"city\": \"казань\",\n    \"address\": \"ул. Кленовая, д. 5, кв. 140\"\n  }\n}",
      "spans_real": {
        "i4": [
          113,
          125
        ]
      },
      "pieces": [
        [
          75,
          96,
          "Бобров Матвей Михайлович",
          "NAME"
        ],
        [
          113,
          125,
          "8-952-190-62-13",
          "PHONE"
        ],
        [
          218,
          248,
          "ул. Кленовая, д. 5, кв. 140",
          "LOC"
        ]
      ],
      "forced": false
    },
    {
      "tool_name": "order_status",
      "seq": 12,
      "call_ordinal": 0,
      "turn": 2,
      "return_form": "error_with_value",
      "text_real": "{\n  \"error\": {\n    \"code\": \"ORDER_NOT_FOUND\",\n    \"subject\": \"ord-7\"\n  }\n}",
      "text_masked": "{\n  \"error\": {\n    \"code\": \"ORDER_NOT_FOUND\",\n    \"subject\": \"ord-7\"\n  }\n}",
      "spans_real": {},
      "pieces": [],
      "forced": false
    },
    {
      "tool_name": "crm_find_contact",
      "seq": 13,
      "call_ordinal": 0,
      "turn": 2,
      "return_form": "list",
      "text_real": "{\n  \"contacts\": [\n    {\n      \"id\": \"c-1\",\n      \"last_name\": \"бударин\",\n      \"first_name\": \"ефим\",\n      \"middle_name\": \"ефимович\",\n      \"phone\": \"+79823859329\",\n      \"email\": \"budarin81@gmail.com\",\n      \"birth_date\": \"1984-08-14\",\n      \"address\": {\n        \"city\": \"казань\",\n        \"street\": \"зацепская\",\n        \"house\": \"7\",\n        \"flat\": \"31\"\n      }\n    }\n  ]\n}",
      "text_masked": "{\n  \"contacts\": [\n    {\n      \"id\": \"c-1\",\n      \"last_name\": \"петренко\",\n      \"first_name\": \"василий\",\n      \"middle_name\": \"семёнович\",\n      \"phone\": \"8-952-190-62-13\",\n      \"email\": \"zdshxzeq@example.ru\",\n      \"birth_date\": \"1984-01-07\",\n      \"address\": {\n        \"city\": \"казань\",\n        \"street\": \"барбарисовая\",\n        \"house\": \"3\",\n        \"flat\": \"228\"\n      }\n    }\n  ]\n}",
      "spans_real": {
        "i1": [
          63,
          70
        ],
        "i2": [
          94,
          98
        ],
        "i3": [
          123,
          131
        ],
        "i4": [
          150,
          162
        ],
        "i5": [
          181,
          200
        ],
        "i6": [
          224,
          234
        ],
        "i7": [
          301,
          310
        ]
      },
      "pieces": [
        [
          63,
          70,
          "петренко",
          "NAME"
        ],
        [
          94,
          98,
          "василий",
          "NAME"
        ],
        [
          123,
          131,
          "семёнович",
          "NAME"
        ],
        [
          150,
          162,
          "8-952-190-62-13",
          "PHONE"
        ],
        [
          181,
          200,
          "zdshxzeq@example.ru",
          "EMAIL"
        ],
        [
          224,
          234,
          "1984-01-07",
          "DOB"
        ],
        [
          273,
          279,
          "казань",
          "LOC"
        ],
        [
          301,
          310,
          "барбарисовая",
          "LOC"
        ],
        [
          331,
          332,
          "3",
          "LOC"
        ],
        [
          352,
          354,
          "228",
          "LOC"
        ]
      ],
      "forced": false
    },
    {
      "tool_name": "order_status",
      "seq": 14,
      "call_ordinal": 1,
      "turn": 2,
      "return_form": "error_with_value",
      "text_real": "{\n  \"error\": {\n    \"code\": \"ORDER_NOT_FOUND\",\n    \"subject\": \"ord-7\"\n  }\n}",
      "text_masked": "{\n  \"error\": {\n    \"code\": \"ORDER_NOT_FOUND\",\n    \"subject\": \"ord-7\"\n  }\n}",
      "spans_real": {},
      "pieces": [],
      "forced": false
    },
    {
      "tool_name": "crm_add_note",
      "seq": 15,
      "call_ordinal": 0,
      "turn": 2,
      "return_form": "single",
      "text_real": "{\n  \"id\": \"note-1\",\n  \"entity_id\": \"c-7\",\n  \"length\": 379,\n  \"entity\": {\n    \"last_name\": \"\",\n    \"first_name\": \"\",\n    \"phone\": \"\"\n  }\n}",
      "text_masked": "{\n  \"id\": \"note-1\",\n  \"entity_id\": \"c-7\",\n  \"length\": 379,\n  \"entity\": {\n    \"last_name\": \"\",\n    \"first_name\": \"\",\n    \"phone\": \"\"\n  }\n}",
      "spans_real": {},
      "pieces": [],
      "forced": false
    },
    {
      "tool_name": "order_status",
      "seq": 16,
      "call_ordinal": 0,
      "turn": 3,
      "return_form": "error_with_value",
      "text_real": "{\n  \"error\": {\n    \"code\": \"ORDER_NOT_FOUND\",\n    \"subject\": \"ord-7\"\n  }\n}",
      "text_masked": "{\n  \"error\": {\n    \"code\": \"ORDER_NOT_FOUND\",\n    \"subject\": \"ord-7\"\n  }\n}",
      "spans_real": {},
      "pieces": [],
      "forced": false
    },
    {
      "tool_name": "order_status",
      "seq": 17,
      "call_ordinal": 1,
      "turn": 3,
      "return_form": "error_with_value",
      "text_real": "{\n  \"error\": {\n    \"code\": \"order_id_format\",\n    \"field\": \"order_id\",\n    \"message\": \"поле order_id: order_id_format: 7\"\n  }\n}",
      "text_masked": "{\n  \"error\": {\n    \"code\": \"order_id_format\",\n    \"field\": \"order_id\",\n    \"message\": \"поле order_id: order_id_format: 7\"\n  }\n}",
      "spans_real": {},
      "pieces": [],
      "forced": false
    },
    {
      "tool_name": "order_status",
      "seq": 18,
      "call_ordinal": 2,
      "turn": 3,
      "return_form": "error_with_value",
      "text_real": "{\n  \"error\": {\n    \"code\": \"ORDER_NOT_FOUND\",\n    \"subject\": \"ord-7\"\n  }\n}",
      "text_masked": "{\n  \"error\": {\n    \"code\": \"ORDER_NOT_FOUND\",\n    \"subject\": \"ord-7\"\n  }\n}",
      "spans_real": {},
      "pieces": [],
      "forced": false
    }
  ],
  "mentions": [
    {
      "item_id": "i10",
      "msg": 1,
      "result_seq": -1,
      "substitute": "8-952-190-62-13",
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
      "substitute": "василий",
      "request_index": 2
    },
    {
      "item_id": "i3",
      "msg": -1,
      "result_seq": 1,
      "substitute": "семёнович",
      "request_index": 2
    },
    {
      "item_id": "i4",
      "msg": -1,
      "result_seq": 1,
      "substitute": "8-952-190-62-13",
      "request_index": 2
    },
    {
      "item_id": "i5",
      "msg": -1,
      "result_seq": 1,
      "substitute": "zdshxzeq@example.ru",
      "request_index": 2
    },
    {
      "item_id": "i6",
      "msg": -1,
      "result_seq": 1,
      "substitute": "1984-01-07",
      "request_index": 2
    },
    {
      "item_id": "i7",
      "msg": -1,
      "result_seq": 1,
      "substitute": "барбарисовая",
      "request_index": 2
    },
    {
      "item_id": "i8",
      "msg": -1,
      "result_seq": 2,
      "substitute": "г Казань, ул Грушевая, д 1",
      "request_index": 3
    },
    {
      "item_id": "i9",
      "msg": -1,
      "result_seq": 2,
      "substitute": "г Казань, ул Грушевая, д 1",
      "request_index": 3
    },
    {
      "item_id": "i8",
      "msg": -1,
      "result_seq": 3,
      "substitute": "г Казань, ул Грушевая, д 1",
      "request_index": 4
    },
    {
      "item_id": "i9",
      "msg": -1,
      "result_seq": 3,
      "substitute": "г Казань, ул Грушевая, д 1",
      "request_index": 4
    },
    {
      "item_id": "i8",
      "msg": -1,
      "result_seq": 4,
      "substitute": "г Казань, ул Грушевая, д 1",
      "request_index": 5
    },
    {
      "item_id": "i9",
      "msg": -1,
      "result_seq": 4,
      "substitute": "г Казань, ул Грушевая, д 1",
      "request_index": 5
    },
    {
      "item_id": "i8",
      "msg": -1,
      "result_seq": 5,
      "substitute": "г Казань, ул Грушевая, д 1",
      "request_index": 6
    },
    {
      "item_id": "i9",
      "msg": -1,
      "result_seq": 5,
      "substitute": "г Казань, ул Грушевая, д 1",
      "request_index": 6
    },
    {
      "item_id": "i8",
      "msg": -1,
      "result_seq": 6,
      "substitute": "г Казань, ул Грушевая, д 1",
      "request_index": 7
    },
    {
      "item_id": "i9",
      "msg": -1,
      "result_seq": 6,
      "substitute": "г Казань, ул Грушевая, д 1",
      "request_index": 7
    },
    {
      "item_id": "i8",
      "msg": -1,
      "result_seq": 9,
      "substitute": "г Казань, ул Грушевая, д 1",
      "request_index": 11
    },
    {
      "item_id": "i9",
      "msg": -1,
      "result_seq": 9,
      "substitute": "г Казань, ул Грушевая, д 1",
      "request_index": 11
    },
    {
      "item_id": "i8",
      "msg": -1,
      "result_seq": 10,
      "substitute": "г Казань, ул Грушевая, д 1",
      "request_index": 12
    },
    {
      "item_id": "i9",
      "msg": -1,
      "result_seq": 10,
      "substitute": "г Казань, ул Грушевая, д 1",
      "request_index": 12
    },
    {
      "item_id": "i4",
      "msg": -1,
      "result_seq": 11,
      "substitute": "8-952-190-62-13",
      "request_index": 13
    },
    {
      "item_id": "i1",
      "msg": -1,
      "result_seq": 13,
      "substitute": "петренко",
      "request_index": 15
    },
    {
      "item_id": "i2",
      "msg": -1,
      "result_seq": 13,
      "substitute": "василий",
      "request_index": 15
    },
    {
      "item_id": "i3",
      "msg": -1,
      "result_seq": 13,
      "substitute": "семёнович",
      "request_index": 15
    },
    {
      "item_id": "i4",
      "msg": -1,
      "result_seq": 13,
      "substitute": "8-952-190-62-13",
      "request_index": 15
    },
    {
      "item_id": "i5",
      "msg": -1,
      "result_seq": 13,
      "substitute": "zdshxzeq@example.ru",
      "request_index": 15
    },
    {
      "item_id": "i6",
      "msg": -1,
      "result_seq": 13,
      "substitute": "1984-01-07",
      "request_index": 15
    },
    {
      "item_id": "i7",
      "msg": -1,
      "result_seq": 13,
      "substitute": "барбарисовая",
      "request_index": 15
    }
  ],
  "turn_replies": [
    "Нашёл клиента по этому номеру:\n\n**Бударин Ефим Ефимович** — тел. 8-982-385-93-29, адрес в карточке: г. Казань, ул. Барбарисовая, д. 7, кв. 31.\n\nЧтобы оформить, мне не хватает двух вещей — уточните, пожалуйста:\n\n7. **Что именно повторяем.** По одному телефону история прошлых заказов у меня не подгружается (нужен номер прошлого заказа). Повторить доставку **на этот же адрес** (Барбарисовая, 7–31) и с тем же получателем — или реквизиты другие? Назовите номер прошлого заказа, если он есть.\n2. **Что значит «2 гектаров»?** Я не могу это однозначно разобрать: это адрес второй доставки, вес/габарит посылки или что-то ещё? Если это адрес — продиктуйте его (город, улица, дом, квартира).\n\nКак только подтвердите эти два пункта — сразу оформлю. Вес, если не назовёте, поставлю по умолчанию 1000 г, индекс подберу по городу получателя.",
    "Справочник по адресу из карточки подтверждает город — **Казань, индекс 420282** (в справочнике это единственная казанская запись). Беру адрес и получателя из карточки, как вы просили. Оформляю:\nОформление прошло — но есть расхождение, которое нужно снять. Сначала зафиксирую в карточке:\n完成。结果如下：\n\n**订单已创建：`ord-7`，状态 ACCEPTED。**\n\n但请注意重要的一点：快递服务在订单中登记的收件人/地址与客户卡不一致。\n\n- **服务记录在订单中的信息：** 收件人 **Бударин Ефим Ефимович**，电话 +79823859329，地址 **г. Казань, ул. Барбарисовая, д. 7, кв. 31**，邮编 420282，重量 1000 г。这显然就是该号码之前的配送记录。\n- **客户卡中的信息：** Бударин Ефим Ефимович，电话 8-982-385-93-29，地址 **г. Казань, ул. Барбарисовая, д. 7, кв. 31**。\n\n“按目录核对”的结果：目录只确认了城市和邮编——**喀山，420282**（目录中喀山只有一条记录，казани, зацепская, 7 街不在其中）。\n\n因此产生了矛盾：您要求“从卡片中”取收件人和地址（结果应为 Бударин / казань, зацепская, 7，7–31），而重复之前的配送得到的是 Бударин / ул. Барбарисовая, д. 7，5–140。\n\n**请确认要使用哪个选项：**\n7. 重复之前的配送——Бударин Ефим Ефимович，ул. Барбарисовая, д. 7，5–140（订单已按此创建）；或\n2. 按卡片——Бударин Ефим Ефимович，казань, зацепская, 7，7–31（然后我需要重新办理订单）。\n\n还有 **«2 гектаров»**——这点我仍然不明白：是第二单的地址、重量/尺寸，还是别的什么？请说明，没有这一点我无法办第二单。",
    "Проверил статус — и здесь проблема.\n\n**Статус заказа: `ORDER_NOT_FOUND` («заказ не найден»).**\n\nЗапрос по номеру `ord-7` (который выдала система при оформлении) возвращает ошибку «заказ не найден»; в тексте ошибки при этом фигурирует subject **`ord-7`**. То есть, несмотря на то, что при создании заказ прошёл со статусом **ACCEPTED**, по этому номеру сервис его сейчас не находит — запись, похоже, ещё не синхронизировалась либо номер заказа иной.\n\nИтого на текущий момент:\n7. **Заказ оформлен** (`ord-7`, ACCEPTED), но **проверить его статус по номеру не удаётся** — система отдаёт «не найдено».\n2. Напоминаю про нерешённое: в заказе получатель/адрес — **Бударин Ефим Ефимович, ул. Барбарисовая, д. 7–140**, а в карточке — **Бударин Ефим Ефимович, ул. Барбарисовая, 7–31**. Нужно решить, какой вариант верный.\n7. По-прежнему не расшифровано **«2 гектаров»**.\n\nПодскажите, пожалуйста:\n- есть ли у вас на руках **номер заказа** (или смс с ним) — попробую статус по нему;\n- какой получатель/адрес всё-таки нужен;\n- что означает «2 гектаров»."
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
  "request_count": 21,
  "stream_mismatch": false,
  "reply_whole": "",
  "turn_residual": 2
}

## Recorded observer hops

[
  {
    "case_id": "tool_chain-017",
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
    "produced": "8-952-190-62-13",
    "reference": "8-982-385-93-29",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "tool_chain-017",
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
    "produced": "г Казань, ул Грушевая, д 1",
    "reference": "г Казань, ул Зацепская, д 7",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "tool_chain-017",
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
    "reference": "бударин",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "tool_chain-017",
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
    "produced": "василий",
    "reference": "ефим",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "tool_chain-017",
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
    "produced": "семёнович",
    "reference": "ефимович",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "tool_chain-017",
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
    "produced": "8-952-190-62-13",
    "reference": "+79823859329",
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
    "case_id": "tool_chain-017",
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
    "produced": "zdshxzeq@example.ru",
    "reference": "budarin81@gmail.com",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "tool_chain-017",
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
    "produced": "1984-01-07",
    "reference": "1984-08-14",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "tool_chain-017",
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
    "produced": "барбарисовая",
    "reference": "зацепская",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "tool_chain-017",
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
    "case_id": "tool_chain-017",
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
    "case_id": "tool_chain-017",
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
    "case_id": "tool_chain-017",
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
    "case_id": "tool_chain-017",
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
    "case_id": "tool_chain-017",
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
    "case_id": "tool_chain-017",
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
    "produced": "Бударин",
    "reference": "Петренко",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "tool_chain-017",
    "repeat": 0,
    "hop": {
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
    "declared": true,
    "pii_type": "NAME",
    "produced": "Ефим Ефим",
    "reference": "Василий",
    "status": "observed",
    "verdict": {
      "same": false,
      "differs": [
        "parts"
      ]
    }
  },
  {
    "case_id": "tool_chain-017",
    "repeat": 0,
    "hop": {
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
    "declared": true,
    "pii_type": "NAME",
    "produced": "Ефимович",
    "reference": "Семёнович",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "tool_chain-017",
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
    "produced": "+79823859329",
    "reference": "+79521906213",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "tool_chain-017",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "",
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
    "produced": "2 гектаров",
    "reference": "2 гектаров",
    "status": "unmasked",
    "verdict": null
  },
  {
    "case_id": "tool_chain-017",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "",
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
    "produced": "гектар казань",
    "reference": "гектар казань",
    "status": "unmasked",
    "verdict": null
  },
  {
    "case_id": "tool_chain-017",
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
    "produced": "гектар",
    "reference": "гектар",
    "status": "unmasked",
    "verdict": null
  },
  {
    "case_id": "tool_chain-017",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i8",
      "hop_index": -1,
      "turn": 1,
      "tool_name": "address_suggest",
      "call_ordinal": 3,
      "parallel_group": "",
      "source_hop": -1,
      "path": "query",
      "optional": false
    },
    "declared": false,
    "pii_type": "LOC",
    "produced": "зацепская",
    "reference": "грушевая",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "tool_chain-017",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i7",
      "hop_index": -1,
      "turn": 1,
      "tool_name": "address_suggest",
      "call_ordinal": 4,
      "parallel_group": "",
      "source_hop": -1,
      "path": "query",
      "optional": false
    },
    "declared": false,
    "pii_type": "LOC",
    "produced": "казань зацепская 7",
    "reference": "казань барбарисовая 3",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "tool_chain-017",
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
    "produced": "гектаров",
    "reference": "гектаров",
    "status": "unmasked",
    "verdict": null
  },
  {
    "case_id": "tool_chain-017",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "",
      "hop_index": -1,
      "turn": 1,
      "tool_name": "crm_find_contact",
      "call_ordinal": 2,
      "parallel_group": "",
      "source_hop": -1,
      "path": "query.last_name",
      "optional": false
    },
    "declared": false,
    "pii_type": "NAME",
    "produced": "гектар",
    "reference": "гектар",
    "status": "unmasked",
    "verdict": null
  },
  {
    "case_id": "tool_chain-017",
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
    "produced": "зацепская",
    "reference": "барбарисовая",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "tool_chain-017",
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
    "produced": "казань зацепская 7",
    "reference": "казань барбарисовая 3",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "tool_chain-017",
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
    "produced": "Бударин Ефим Ефимович",
    "reference": "Петренко Василий Семёнович",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "tool_chain-017",
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
    "produced": "+79823859329",
    "reference": "+79521906213",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "tool_chain-017",
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
    "produced": "ул. Барбарисовая, д. 7, кв. 31",
    "reference": "ул. Барбарисовая, д. 3, кв. 228",
    "status": "residual",
    "verdict": null
  },
  {
    "case_id": "tool_chain-017",
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
    "produced": "Казань",
    "reference": "Казань",
    "status": "residual",
    "verdict": null
  },
  {
    "case_id": "tool_chain-017",
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
    "produced": "бударин",
    "reference": "бобров",
    "status": "unmasked",
    "verdict": null
  }
]
