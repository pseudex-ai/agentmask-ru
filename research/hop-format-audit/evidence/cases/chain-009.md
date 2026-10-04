# chain-009 | source C | repeat 0

Synthetic benchmark evidence. Verbatim serialized fields; no inferred verdicts.

## Case specification

{
  "base": {
    "id": "chain-009",
    "kind": "chain",
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
    "cluster": "PHONE:9607464897",
    "conversation_id": "",
    "now": "2026-09-02",
    "messages": [
      {
        "role": "system",
        "content": "Ты оператор CRM. Находи и обновляй карточки клиентов инструментами; инициалы и латинское написание имени заполняй сам по ФИО. Сегодня 2026-09-02.",
        "source": null,
        "name": ""
      },
      {
        "role": "user",
        "content": "здрасте это захаров владислав юрьевич хочу поменять адрес доставки телефон 8 960 746 48 97 да и проезд подорожал",
        "source": null,
        "name": ""
      },
      {
        "role": "user",
        "content": "теперь казань вишнёвая 8 кв 176",
        "source": null,
        "name": ""
      },
      {
        "role": "user",
        "content": "и пришлите смс с подтверждением",
        "source": null,
        "name": ""
      }
    ],
    "tools": [
      "crm_find_contact",
      "crm_upsert_contact",
      "notify_sms",
      "callback_schedule"
    ],
    "seed_records": [
      {
        "id": "c-1",
        "table": "contacts",
        "fields": {
          "last_name": "захаров",
          "first_name": "владислав",
          "middle_name": "юрьевич",
          "phone": "+79607464897",
          "email": "zaharov70@list.ru",
          "birth_date": "1984-05-22",
          "address": {
            "city": "казань",
            "street": "дзержинского",
            "house": "19",
            "flat": "50"
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
        "identity": "p9",
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
        "identity": "p9",
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
        "identity": "p9",
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
        "identity": "p9",
        "value": "+79607464897",
        "canonical": "+79607464897",
        "parts": {
          "digits": "9607464897"
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
        "identity": "p9",
        "value": "zaharov70@list.ru",
        "canonical": "zaharov70@list.ru",
        "parts": {
          "local": "zaharov70",
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
        "identity": "p9",
        "value": "1984-05-22",
        "canonical": "1984-05-22",
        "parts": {
          "iso": "1984-05-22"
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
        "identity": "p9.home",
        "value": "дзержинского",
        "canonical": "дзержинского",
        "parts": {
          "street": "дзержинского",
          "street_type": "улица",
          "house": "19",
          "flat": "50",
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
        "type": "NAME",
        "identity": "p9",
        "value": "захаров владислав юрьевич",
        "canonical": "захаров владислав юрьевич",
        "parts": {
          "surname": "захаров",
          "given": "владислав",
          "patronymic": "юрьевич",
          "gender": "m"
        },
        "where": {
          "kind": "message",
          "msg": 1,
          "start": 12,
          "end": 37,
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
        "identity": "p9",
        "value": "8 960 746 48 97",
        "canonical": "+79607464897",
        "parts": {
          "digits": "9607464897"
        },
        "where": {
          "kind": "message",
          "msg": 1,
          "start": 75,
          "end": 90,
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
        "identity": "p9.new",
        "value": "казань вишнёвая 8 кв 176",
        "canonical": "казань вишнёвая 8 кв 176",
        "parts": {
          "street": "вишнёвая",
          "house": "8",
          "flat": "176",
          "city": "казань"
        },
        "where": {
          "kind": "message",
          "msg": 2,
          "start": 7,
          "end": 31,
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
        "value": "проезд",
        "start": 96,
        "end": 102,
        "msg": 1,
        "family": "fare",
        "why": "«проезд» как плата, а не как тип улицы"
      }
    ],
    "expects": {
      "reachable_tools": [
        "crm_find_contact",
        "crm_upsert_contact",
        "notify_sms"
      ],
      "primary_identity": "p9",
      "must_contain": [],
      "must_not_contain": [],
      "validate_types": []
    },
    "trace": [
      {
        "msg": 1,
        "key": "",
        "start": 0,
        "end": 7,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 1,
        "key": "",
        "start": 7,
        "end": 8,
        "origin": "literal"
      },
      {
        "msg": 1,
        "key": "",
        "start": 8,
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
        "key": "n1",
        "start": 12,
        "end": 37,
        "origin": "value:n1"
      },
      {
        "msg": 1,
        "key": "",
        "start": 37,
        "end": 38,
        "origin": "literal"
      },
      {
        "msg": 1,
        "key": "",
        "start": 38,
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
        "end": 51,
        "origin": "chunk:noisy_word"
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
        "key": "ph1",
        "start": 75,
        "end": 90,
        "origin": "value:ph1"
      },
      {
        "msg": 1,
        "key": "",
        "start": 90,
        "end": 91,
        "origin": "literal"
      },
      {
        "msg": 1,
        "key": "",
        "start": 91,
        "end": 93,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 1,
        "key": "",
        "start": 93,
        "end": 94,
        "origin": "literal"
      },
      {
        "msg": 1,
        "key": "",
        "start": 94,
        "end": 95,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 1,
        "key": "",
        "start": 95,
        "end": 96,
        "origin": "literal"
      },
      {
        "msg": 1,
        "key": "neg1",
        "start": 96,
        "end": 102,
        "origin": "negative:neg1"
      },
      {
        "msg": 1,
        "key": "",
        "start": 102,
        "end": 103,
        "origin": "literal"
      },
      {
        "msg": 1,
        "key": "",
        "start": 103,
        "end": 112,
        "origin": "chunk:noisy_word"
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
        "key": "a1",
        "start": 7,
        "end": 31,
        "origin": "value:a1"
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
        "end": 14,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 3,
        "key": "",
        "start": 14,
        "end": 15,
        "origin": "literal"
      },
      {
        "msg": 3,
        "key": "",
        "start": 15,
        "end": 16,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 3,
        "key": "",
        "start": 16,
        "end": 17,
        "origin": "literal"
      },
      {
        "msg": 3,
        "key": "",
        "start": 17,
        "end": 31,
        "origin": "chunk:noisy_word"
      }
    ],
    "note": "поиск по телефону, адрес из карточки, новый адрес по полям, смс"
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
      "owner": "tool",
      "item_id": "i1",
      "hop_index": 3,
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
      "hop_index": 4,
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
      "hop_index": 5,
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
      "hop_index": 6,
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
      "hop_index": 7,
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
      "hop_index": 8,
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
      "hop_index": 9,
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
      "hop_index": 10,
      "turn": 3,
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
      "hop_index": 11,
      "turn": 3,
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
      "hop_index": 12,
      "turn": 3,
      "tool_name": "crm_upsert_contact",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": 0,
      "path": "contact.last_name",
      "optional": true
    },
    {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i8",
      "hop_index": 13,
      "turn": 3,
      "tool_name": "crm_upsert_contact",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": 0,
      "path": "contact.first_name",
      "optional": true
    },
    {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i8",
      "hop_index": 14,
      "turn": 3,
      "tool_name": "crm_upsert_contact",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": 0,
      "path": "contact.middle_name",
      "optional": true
    },
    {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i9",
      "hop_index": 15,
      "turn": 3,
      "tool_name": "crm_upsert_contact",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": 1,
      "path": "contact.phone",
      "optional": true
    },
    {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i5",
      "hop_index": 16,
      "turn": 3,
      "tool_name": "crm_upsert_contact",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": 7,
      "path": "contact.email",
      "optional": true
    },
    {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i6",
      "hop_index": 17,
      "turn": 3,
      "tool_name": "crm_upsert_contact",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": 8,
      "path": "contact.birth_date",
      "optional": true
    },
    {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i10",
      "hop_index": 18,
      "turn": 3,
      "tool_name": "crm_upsert_contact",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": 2,
      "path": "contact.address.city",
      "optional": true
    },
    {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i10",
      "hop_index": 19,
      "turn": 3,
      "tool_name": "crm_upsert_contact",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": 2,
      "path": "contact.address.street",
      "optional": true
    },
    {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i10",
      "hop_index": 20,
      "turn": 3,
      "tool_name": "crm_upsert_contact",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": 2,
      "path": "contact.address.house",
      "optional": true
    },
    {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i10",
      "hop_index": 21,
      "turn": 3,
      "tool_name": "crm_upsert_contact",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": 2,
      "path": "contact.address.flat",
      "optional": true
    },
    {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i9",
      "hop_index": 22,
      "turn": 3,
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
      "hop_index": 23,
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
      "item_id": "i2",
      "hop_index": 24,
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
      "item_id": "i3",
      "hop_index": 25,
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
      "item_id": "i4",
      "hop_index": 26,
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
      "item_id": "i5",
      "hop_index": 27,
      "turn": 3,
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
      "item_id": "i6",
      "hop_index": 28,
      "turn": 3,
      "tool_name": "",
      "call_ordinal": -1,
      "parallel_group": "",
      "source_hop": 8,
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
    "case_id": "chain-009",
    "arm": "I",
    "repeat": 0,
    "calls": [
      {
        "name": "crm_find_contact",
        "written": {
          "query": {
            "phone": "+79429252802"
          }
        },
        "restored": {
          "query": {
            "phone": "+79607464897"
          }
        },
        "residual": {},
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "query": {
            "phone": "+79607464897"
          }
        },
        "seq": 1
      },
      {
        "name": "crm_upsert_contact",
        "written": {
          "contact": {
            "address": {
              "city": "Казань",
              "flat": "40",
              "house": "5",
              "street": "Грушевая"
            },
            "birth_date": "1984-02-06",
            "email": "ukdftkxh@example.ru",
            "first_name": "Ярослав",
            "gender": "M",
            "initials": "Я. Г.",
            "last_name": "Рыбаков",
            "middle_name": "Геннадьевич",
            "name_latin": "Rybakov Yaroslav",
            "phone": "+79429252802"
          },
          "id": "c-1"
        },
        "restored": {
          "contact": {
            "address": {
              "city": "Казань",
              "flat": "176",
              "house": "8",
              "street": "Вишнёвая"
            },
            "birth_date": "1984-05-22",
            "email": "zaharov70@list.ru",
            "first_name": "Владислав",
            "gender": "M",
            "initials": "В. Ю.",
            "last_name": "Захаров",
            "middle_name": "Юрьевич",
            "name_latin": "Zakharov Vladislav",
            "phone": "+79607464897"
          },
          "id": "c-1"
        },
        "residual": {},
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "contact": {
            "address": {
              "city": "казань",
              "flat": "176",
              "house": "8",
              "street": "вишнёвая"
            },
            "birth_date": "1984-05-22",
            "email": "zaharov70@list.ru",
            "first_name": "владислав",
            "gender": "M",
            "initials": "ВЮ",
            "last_name": "захаров",
            "middle_name": "юрьевич",
            "name_latin": "ZAKHAROV VLADISLAV",
            "phone": "+79607464897"
          },
          "id": "c-1"
        },
        "seq": 2
      },
      {
        "name": "notify_sms",
        "written": {
          "number": "+79429252802",
          "sign": "Dostavka",
          "text": "Ярослав Геннадьевич, адрес доставки обновлён: Казань, ул. Грушевая, д. 5, кв. 40."
        },
        "restored": {
          "number": "+79607464897",
          "sign": "Dostavka",
          "text": "Владислав Юрьевич, адрес доставки обновлён: Казань, вишнёвая, д. 8, кв. 176."
        },
        "residual": {},
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "number": "+79607464897",
          "sign": "Dostavka",
          "text": "Владислав Юрьевич, адрес доставки обновлён: Казань, вишнёвая, д. 8, кв. 176."
        },
        "seq": 3
      }
    ],
    "state": [
      {
        "fields": {
          "address": {
            "city": "казань",
            "flat": "176",
            "house": "8",
            "street": "вишнёвая"
          },
          "birth_date": "1984-05-22",
          "email": "zaharov70@list.ru",
          "first_name": "владислав",
          "gender": "M",
          "initials": "ВЮ",
          "last_name": "захаров",
          "middle_name": "юрьевич",
          "name_latin": "ZAKHAROV VLADISLAV",
          "phone": "+79607464897"
        },
        "id": "c-1",
        "seq": 2,
        "table": "contacts",
        "tool": "crm_upsert_contact"
      },
      {
        "fields": {
          "number": "+79607464897",
          "sign": "Dostavka",
          "text": "Владислав Юрьевич, адрес доставки обновлён: Казань, вишнёвая, д. 8, кв. 176."
        },
        "id": "sms-1",
        "seq": 3,
        "table": "sms",
        "tool": "notify_sms"
      }
    ],
    "reply": "СМС-подтверждение отправлено на номер +79607464897: «Владислав Юрьевич, адрес доставки обновлён: казань вишнёвая 8 кв 176».",
    "termination": "done",
    "cost_usd": 0.001773,
    "substitutes": {
      "i1": [
        "рыбаков",
        {
          "surname": "рыбаков"
        }
      ],
      "i10": [
        "казань грушевая 5 кв 40",
        {
          "flat": "40",
          "house": "5",
          "street": "грушевая казань"
        }
      ],
      "i2": [
        "ярослав",
        {
          "given": "ярослав"
        }
      ],
      "i3": [
        "геннадьевич",
        {
          "patronymic": "геннадьевич"
        }
      ],
      "i4": [
        "8 942 925 28 02",
        {
          "digits": "9429252802"
        }
      ],
      "i5": [
        "ukdftkxh@example.ru",
        {
          "domain": "example.ru",
          "local": "ukdftkxh"
        }
      ],
      "i6": [
        "1984-02-06",
        {
          "iso": "1984-02-06"
        }
      ],
      "i7": [
        "мятная",
        {
          "street": "мятная"
        }
      ],
      "i8": [
        "рыбаков ярослав геннадьевич",
        {
          "given": "ярослав",
          "patronymic": "геннадьевич",
          "surname": "рыбаков"
        }
      ],
      "i9": [
        "8 942 925 28 02",
        {
          "digits": "9429252802"
        }
      ]
    },
    "masked_spans": {
      "0": [],
      "1": [
        [
          12,
          37
        ],
        [
          75,
          90
        ]
      ],
      "2": [
        [
          7,
          31
        ]
      ],
      "3": []
    }
  },
  "reply_raw": "СМС-подтверждение отправлено на номер 8 942 925 28 02: «Ярослав Геннадьевич, адрес доставки обновлён: Казань, ул. Грушевая, д. 5, кв. 40».",
  "control_reply": "Отправляю СМС с подтверждением.\nСМС с подтверждением отправлена на номер +7 960 746-48-97 — новый адрес: г. Казань, ул. Вишнёвая, д. 8, кв. 176.\n\nЧто-то ещё нужно?",
  "tool_results": [
    {
      "tool_name": "crm_find_contact",
      "seq": 1,
      "call_ordinal": 0,
      "turn": 1,
      "return_form": "list",
      "text_real": "{\n  \"contacts\": [\n    {\n      \"id\": \"c-1\",\n      \"last_name\": \"захаров\",\n      \"first_name\": \"владислав\",\n      \"middle_name\": \"юрьевич\",\n      \"phone\": \"+79607464897\",\n      \"email\": \"zaharov70@list.ru\",\n      \"birth_date\": \"1984-05-22\",\n      \"address\": {\n        \"city\": \"казань\",\n        \"street\": \"дзержинского\",\n        \"house\": \"19\",\n        \"flat\": \"50\"\n      }\n    }\n  ]\n}",
      "text_masked": "{\n  \"contacts\": [\n    {\n      \"id\": \"c-1\",\n      \"last_name\": \"рыбаков\",\n      \"first_name\": \"ярослав\",\n      \"middle_name\": \"геннадьевич\",\n      \"phone\": \"8 942 925 28 02\",\n      \"email\": \"ukdftkxh@example.ru\",\n      \"birth_date\": \"1984-02-06\",\n      \"address\": {\n        \"city\": \"казань\",\n        \"street\": \"мятная\",\n        \"house\": \"12\",\n        \"flat\": \"118\"\n      }\n    }\n  ]\n}",
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
          303,
          315
        ]
      },
      "pieces": [
        [
          63,
          70,
          "рыбаков",
          "NAME"
        ],
        [
          94,
          103,
          "ярослав",
          "NAME"
        ],
        [
          128,
          135,
          "геннадьевич",
          "NAME"
        ],
        [
          154,
          166,
          "8 942 925 28 02",
          "PHONE"
        ],
        [
          185,
          202,
          "ukdftkxh@example.ru",
          "EMAIL"
        ],
        [
          226,
          236,
          "1984-02-06",
          "DOB"
        ],
        [
          275,
          281,
          "казань",
          "LOC"
        ],
        [
          303,
          315,
          "мятная",
          "LOC"
        ],
        [
          336,
          338,
          "12",
          "LOC"
        ],
        [
          358,
          360,
          "118",
          "LOC"
        ]
      ],
      "forced": false
    },
    {
      "tool_name": "crm_upsert_contact",
      "seq": 2,
      "call_ordinal": 0,
      "turn": 2,
      "return_form": "single",
      "text_real": "{\n  \"id\": \"c-1\",\n  \"updated_fields\": [\n    \"last_name\",\n    \"first_name\",\n    \"middle_name\",\n    \"initials\",\n    \"name_latin\",\n    \"phone\",\n    \"email\",\n    \"birth_date\",\n    \"gender\",\n    \"address\"\n  ],\n  \"contact\": {\n    \"last_name\": \"захаров\",\n    \"first_name\": \"владислав\",\n    \"phone\": \"+79607464897\"\n  }\n}",
      "text_masked": "{\n  \"id\": \"c-1\",\n  \"updated_fields\": [\n    \"last_name\",\n    \"first_name\",\n    \"middle_name\",\n    \"initials\",\n    \"name_latin\",\n    \"phone\",\n    \"email\",\n    \"birth_date\",\n    \"gender\",\n    \"address\"\n  ],\n  \"contact\": {\n    \"last_name\": \"рыбаков\",\n    \"first_name\": \"ярослав\",\n    \"phone\": \"8 942 925 28 02\"\n  }\n}",
      "spans_real": {
        "i1": [
          237,
          244
        ],
        "i2": [
          266,
          275
        ],
        "i4": [
          292,
          304
        ]
      },
      "pieces": [
        [
          237,
          244,
          "рыбаков",
          "NAME"
        ],
        [
          266,
          275,
          "ярослав",
          "NAME"
        ],
        [
          292,
          304,
          "8 942 925 28 02",
          "PHONE"
        ]
      ],
      "forced": false
    },
    {
      "tool_name": "notify_sms",
      "seq": 3,
      "call_ordinal": 0,
      "turn": 3,
      "return_form": "single",
      "text_real": "{\n  \"id\": \"sms-1\",\n  \"status\": \"queued\",\n  \"number\": \"+79607464897\"\n}",
      "text_masked": "{\n  \"id\": \"sms-1\",\n  \"status\": \"queued\",\n  \"number\": \"8 942 925 28 02\"\n}",
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
          "8 942 925 28 02",
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
      "substitute": "рыбаков ярослав геннадьевич",
      "request_index": 1
    },
    {
      "item_id": "i9",
      "msg": 1,
      "result_seq": -1,
      "substitute": "8 942 925 28 02",
      "request_index": 1
    },
    {
      "item_id": "i1",
      "msg": -1,
      "result_seq": 1,
      "substitute": "рыбаков",
      "request_index": 2
    },
    {
      "item_id": "i2",
      "msg": -1,
      "result_seq": 1,
      "substitute": "ярослав",
      "request_index": 2
    },
    {
      "item_id": "i3",
      "msg": -1,
      "result_seq": 1,
      "substitute": "геннадьевич",
      "request_index": 2
    },
    {
      "item_id": "i4",
      "msg": -1,
      "result_seq": 1,
      "substitute": "8 942 925 28 02",
      "request_index": 2
    },
    {
      "item_id": "i5",
      "msg": -1,
      "result_seq": 1,
      "substitute": "ukdftkxh@example.ru",
      "request_index": 2
    },
    {
      "item_id": "i6",
      "msg": -1,
      "result_seq": 1,
      "substitute": "1984-02-06",
      "request_index": 2
    },
    {
      "item_id": "i7",
      "msg": -1,
      "result_seq": 1,
      "substitute": "мятная",
      "request_index": 2
    },
    {
      "item_id": "i10",
      "msg": 2,
      "result_seq": -1,
      "substitute": "казань грушевая 5 кв 40",
      "request_index": 3
    },
    {
      "item_id": "i1",
      "msg": -1,
      "result_seq": 2,
      "substitute": "рыбаков",
      "request_index": 4
    },
    {
      "item_id": "i2",
      "msg": -1,
      "result_seq": 2,
      "substitute": "ярослав",
      "request_index": 4
    },
    {
      "item_id": "i4",
      "msg": -1,
      "result_seq": 2,
      "substitute": "8 942 925 28 02",
      "request_index": 4
    },
    {
      "item_id": "i4",
      "msg": -1,
      "result_seq": 3,
      "substitute": "8 942 925 28 02",
      "request_index": 6
    }
  ],
  "turn_replies": [
    "Здравствуйте, Владислав Юрьевич! Карточку нашёл. Чтобы поменять адрес доставки, подскажите, пожалуйста, новый адрес: город, улицу, дом и квартиру.\n\nНасчёт подорожания проезда — уточните, что именно нужно учесть (стоимость доставки/самовывоза?), я помогу.",
    "Готово, Владислав Юрьевич! Адрес доставки обновлён:\n\n**казань вишнёвая 8 кв 176**\n\nОстальное в карточке в порядке. Если нужно что-то уточнить по стоимости проезда/доставки или запланировать звонок — скажите, сделаю.",
    "СМС-подтверждение отправлено на номер +79607464897: «Владислав Юрьевич, адрес доставки обновлён: казань вишнёвая 8 кв 176»."
  ],
  "call_turns": [
    1,
    2,
    3
  ],
  "request_count": 6,
  "stream_mismatch": false,
  "reply_whole": "",
  "turn_residual": 1
}

## Recorded observer hops

[
  {
    "case_id": "chain-009",
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
    "produced": "рыбаков ярослав геннадьевич",
    "reference": "захаров владислав юрьевич",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "chain-009",
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
    "produced": "8 942 925 28 02",
    "reference": "8 960 746 48 97",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "chain-009",
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
    "produced": "казань грушевая 5 кв 40",
    "reference": "казань вишнёвая 8 кв 176",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "chain-009",
    "repeat": 0,
    "hop": {
      "kind": "IN",
      "owner": "tool",
      "item_id": "i1",
      "hop_index": 3,
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
    "produced": "рыбаков",
    "reference": "захаров",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "chain-009",
    "repeat": 0,
    "hop": {
      "kind": "IN",
      "owner": "tool",
      "item_id": "i2",
      "hop_index": 4,
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
    "produced": "ярослав",
    "reference": "владислав",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "chain-009",
    "repeat": 0,
    "hop": {
      "kind": "IN",
      "owner": "tool",
      "item_id": "i3",
      "hop_index": 5,
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
    "produced": "геннадьевич",
    "reference": "юрьевич",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "chain-009",
    "repeat": 0,
    "hop": {
      "kind": "IN",
      "owner": "tool",
      "item_id": "i4",
      "hop_index": 6,
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
    "produced": "8 942 925 28 02",
    "reference": "+79607464897",
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
    "case_id": "chain-009",
    "repeat": 0,
    "hop": {
      "kind": "IN",
      "owner": "tool",
      "item_id": "i5",
      "hop_index": 7,
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
    "produced": "ukdftkxh@example.ru",
    "reference": "zaharov70@list.ru",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "chain-009",
    "repeat": 0,
    "hop": {
      "kind": "IN",
      "owner": "tool",
      "item_id": "i6",
      "hop_index": 8,
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
    "produced": "1984-02-06",
    "reference": "1984-05-22",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "chain-009",
    "repeat": 0,
    "hop": {
      "kind": "IN",
      "owner": "tool",
      "item_id": "i7",
      "hop_index": 9,
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
    "produced": "мятная",
    "reference": "дзержинского",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "chain-009",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i9",
      "hop_index": 22,
      "turn": 3,
      "tool_name": "notify_sms",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": 1,
      "path": "number",
      "optional": false
    },
    "declared": true,
    "pii_type": "PHONE",
    "produced": "+79607464897",
    "reference": "+79429252802",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "chain-009",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "answer",
      "item_id": "i2",
      "hop_index": 24,
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
    "produced": "Владислав",
    "reference": "Ярослав",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "chain-009",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "answer",
      "item_id": "i3",
      "hop_index": 25,
      "turn": 3,
      "tool_name": "",
      "call_ordinal": -1,
      "parallel_group": "",
      "source_hop": 5,
      "path": "",
      "optional": true
    },
    "declared": true,
    "pii_type": "NAME",
    "produced": "Юрьевич",
    "reference": "Геннадьевич",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "chain-009",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "answer",
      "item_id": "i4",
      "hop_index": 26,
      "turn": 3,
      "tool_name": "",
      "call_ordinal": -1,
      "parallel_group": "",
      "source_hop": 6,
      "path": "",
      "optional": true
    },
    "declared": true,
    "pii_type": "PHONE",
    "produced": "+79607464897",
    "reference": "8 942 925 28 02",
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
    "case_id": "chain-009",
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
    "produced": "+79607464897",
    "reference": "+79429252802",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "chain-009",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "",
      "hop_index": -1,
      "turn": 2,
      "tool_name": "crm_upsert_contact",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": -1,
      "path": "contact.address.city",
      "optional": false
    },
    "declared": false,
    "pii_type": "LOC",
    "produced": "Казань",
    "reference": "Казань",
    "status": "unmasked",
    "verdict": null
  },
  {
    "case_id": "chain-009",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i6",
      "hop_index": -1,
      "turn": 2,
      "tool_name": "crm_upsert_contact",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": -1,
      "path": "contact.address.flat",
      "optional": false
    },
    "declared": false,
    "pii_type": "LOC",
    "produced": "176",
    "reference": "40",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "chain-009",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i10",
      "hop_index": -1,
      "turn": 2,
      "tool_name": "crm_upsert_contact",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": -1,
      "path": "contact.address.house",
      "optional": false
    },
    "declared": false,
    "pii_type": "LOC",
    "produced": "8",
    "reference": "5",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "chain-009",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i10",
      "hop_index": -1,
      "turn": 2,
      "tool_name": "crm_upsert_contact",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": -1,
      "path": "contact.address.street",
      "optional": false
    },
    "declared": false,
    "pii_type": "LOC",
    "produced": "Вишнёвая",
    "reference": "Грушевая",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "chain-009",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i6",
      "hop_index": -1,
      "turn": 2,
      "tool_name": "crm_upsert_contact",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": -1,
      "path": "contact.birth_date",
      "optional": false
    },
    "declared": false,
    "pii_type": "DOB",
    "produced": "1984-05-22",
    "reference": "1984-02-06",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "chain-009",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i5",
      "hop_index": -1,
      "turn": 2,
      "tool_name": "crm_upsert_contact",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": -1,
      "path": "contact.email",
      "optional": false
    },
    "declared": false,
    "pii_type": "EMAIL",
    "produced": "zaharov70@list.ru",
    "reference": "ukdftkxh@example.ru",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "chain-009",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i2",
      "hop_index": -1,
      "turn": 2,
      "tool_name": "crm_upsert_contact",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": -1,
      "path": "contact.first_name",
      "optional": false
    },
    "declared": false,
    "pii_type": "NAME",
    "produced": "Владислав",
    "reference": "Ярослав",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "chain-009",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i1",
      "hop_index": -1,
      "turn": 2,
      "tool_name": "crm_upsert_contact",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": -1,
      "path": "contact.last_name",
      "optional": false
    },
    "declared": false,
    "pii_type": "NAME",
    "produced": "Захаров",
    "reference": "Рыбаков",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "chain-009",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i3",
      "hop_index": -1,
      "turn": 2,
      "tool_name": "crm_upsert_contact",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": -1,
      "path": "contact.middle_name",
      "optional": false
    },
    "declared": false,
    "pii_type": "NAME",
    "produced": "Юрьевич",
    "reference": "Геннадьевич",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "chain-009",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i4",
      "hop_index": -1,
      "turn": 2,
      "tool_name": "crm_upsert_contact",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": -1,
      "path": "contact.phone",
      "optional": false
    },
    "declared": false,
    "pii_type": "PHONE",
    "produced": "+79607464897",
    "reference": "+79429252802",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "chain-009",
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
    "produced": "+79607464897: «Владислав",
    "reference": "8 942 925 28 02: «Ярослав",
    "status": "observed",
    "verdict": {
      "same": false,
      "differs": [
        "parts"
      ]
    }
  },
  {
    "case_id": "chain-009",
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
    "produced": "+79607464897",
    "reference": "8 942 925 28 02",
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
    "case_id": "chain-009",
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
    "produced": "Юрьевич",
    "reference": "Геннадьевич",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "chain-009",
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
    "produced": "казань",
    "reference": "Казань",
    "status": "observed",
    "verdict": {
      "same": false,
      "differs": [
        "case_class"
      ]
    }
  },
  {
    "case_id": "chain-009",
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
    "produced": " вишнёвая 8 кв 176».",
    "reference": ", ул. Грушевая, д. 5, кв. 40».",
    "status": "observed",
    "verdict": {
      "same": false,
      "differs": [
        "case_class",
        "commas",
        "flat_marker",
        "generic",
        "house_marker"
      ]
    }
  }
]
