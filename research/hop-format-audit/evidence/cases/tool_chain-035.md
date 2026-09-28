# tool_chain-035 | source C | repeat 0

Synthetic benchmark evidence. Verbatim serialized fields; no inferred verdicts.

## Case specification

{
  "base": {
    "id": "tool_chain-035",
    "kind": "tool_chain",
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
    "cluster": "PHONE:9777778899",
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
        "content": "алло всёё как обычно телефон восемь девятьсот семьдесят семь семьсот семьдесят семь восемьсот восемьдесят девять девять кстати проезд подорожаал",
        "source": null,
        "name": ""
      },
      {
        "role": "user",
        "content": "данные всее в базе сверьте адрес в справочнике и оформляйтее",
        "source": null,
        "name": ""
      },
      {
        "role": "user",
        "content": "ии скажите потом какой статуус уу заказаа",
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
          "last_name": "соколова",
          "first_name": "анна",
          "middle_name": "игоревна",
          "phone": "+79777778899",
          "email": "sokolova91@mail.ru",
          "birth_date": "1971-02-28",
          "address": {
            "city": "брянск",
            "street": "пушкина",
            "house": "145а",
            "flat": "44"
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
          "value": "Брянская область, г Брянск, ул Пушкина, д 145а",
          "postal_code": "241434",
          "region": "Брянская область",
          "city": "брянск",
          "street": "пушкина",
          "house": "145а",
          "flat": "",
          "fias_id": "d9c4a4f1-55d7-4ac6-8efa-a57b711651ed"
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
        "identity": "p35",
        "value": "соколова",
        "canonical": "соколова",
        "parts": {
          "surname": "соколова",
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
        "identity": "p35",
        "value": "анна",
        "canonical": "анна",
        "parts": {
          "given": "анна",
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
        "identity": "p35",
        "value": "игоревна",
        "canonical": "игоревна",
        "parts": {
          "patronymic": "игоревна",
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
        "identity": "p35",
        "value": "+79777778899",
        "canonical": "+79777778899",
        "parts": {
          "digits": "9777778899"
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
        "identity": "p35",
        "value": "sokolova91@mail.ru",
        "canonical": "sokolova91@mail.ru",
        "parts": {
          "local": "sokolova91",
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
        "identity": "p35",
        "value": "1971-02-28",
        "canonical": "1971-02-28",
        "parts": {
          "iso": "1971-02-28"
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
        "identity": "p35.home",
        "value": "пушкина",
        "canonical": "пушкина",
        "parts": {
          "street": "пушкина",
          "street_type": "проспект",
          "house": "145а",
          "flat": "44",
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
        "identity": "p35.dir",
        "value": "пушкина",
        "canonical": "пушкина",
        "parts": {
          "street": "пушкина"
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
        "identity": "p35.dir",
        "value": "Брянская область, г Брянск, ул Пушкина, д 145а",
        "canonical": "Брянская область, г Брянск, ул Пушкина, д 145а",
        "parts": {
          "city": "брянск",
          "street": "пушкина",
          "house": "145а"
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
        "identity": "p35",
        "value": "восемь девятьсот семьдесят семь семьсот семьдесят семь восемьсот восемьдесят девять девять",
        "canonical": "+79777778899",
        "parts": {
          "digits": "9777778899"
        },
        "where": {
          "kind": "message",
          "msg": 1,
          "start": 29,
          "end": 119,
          "record": "",
          "path": ""
        },
        "duty": "required",
        "spoken": true,
        "stale": false
      }
    ],
    "plain": [],
    "negatives": [
      {
        "value": "проезд",
        "start": 127,
        "end": 133,
        "msg": 1,
        "family": "fare",
        "why": "«проезд» как плата, а не как тип улицы"
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
      "primary_identity": "p35",
      "must_contain": [],
      "must_not_contain": [],
      "validate_types": []
    },
    "trace": [
      {
        "msg": 1,
        "key": "",
        "start": 0,
        "end": 4,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 1,
        "key": "",
        "start": 4,
        "end": 5,
        "origin": "literal"
      },
      {
        "msg": 1,
        "key": "",
        "start": 5,
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
        "end": 13,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 1,
        "key": "",
        "start": 13,
        "end": 14,
        "origin": "literal"
      },
      {
        "msg": 1,
        "key": "",
        "start": 14,
        "end": 20,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 1,
        "key": "",
        "start": 20,
        "end": 21,
        "origin": "literal"
      },
      {
        "msg": 1,
        "key": "",
        "start": 21,
        "end": 28,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 1,
        "key": "",
        "start": 28,
        "end": 29,
        "origin": "literal"
      },
      {
        "msg": 1,
        "key": "ph1",
        "start": 29,
        "end": 119,
        "origin": "value:ph1"
      },
      {
        "msg": 1,
        "key": "",
        "start": 119,
        "end": 120,
        "origin": "literal"
      },
      {
        "msg": 1,
        "key": "",
        "start": 120,
        "end": 126,
        "origin": "chunk:noisy_word"
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
        "key": "neg1",
        "start": 127,
        "end": 133,
        "origin": "negative:neg1"
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
        "key": "",
        "start": 134,
        "end": 144,
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
        "key": "",
        "start": 7,
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
        "key": "",
        "start": 12,
        "end": 13,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 2,
        "key": "",
        "start": 13,
        "end": 14,
        "origin": "literal"
      },
      {
        "msg": 2,
        "key": "",
        "start": 14,
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
        "end": 26,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 2,
        "key": "",
        "start": 26,
        "end": 27,
        "origin": "literal"
      },
      {
        "msg": 2,
        "key": "",
        "start": 27,
        "end": 32,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 2,
        "key": "",
        "start": 32,
        "end": 33,
        "origin": "literal"
      },
      {
        "msg": 2,
        "key": "",
        "start": 33,
        "end": 34,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 2,
        "key": "",
        "start": 34,
        "end": 35,
        "origin": "literal"
      },
      {
        "msg": 2,
        "key": "",
        "start": 35,
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
        "end": 48,
        "origin": "chunk:noisy_word"
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
        "end": 60,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 3,
        "key": "",
        "start": 0,
        "end": 2,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 3,
        "key": "",
        "start": 2,
        "end": 3,
        "origin": "literal"
      },
      {
        "msg": 3,
        "key": "",
        "start": 3,
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
        "end": 30,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 3,
        "key": "",
        "start": 30,
        "end": 31,
        "origin": "literal"
      },
      {
        "msg": 3,
        "key": "",
        "start": 31,
        "end": 33,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 3,
        "key": "",
        "start": 33,
        "end": 34,
        "origin": "literal"
      },
      {
        "msg": 3,
        "key": "",
        "start": 34,
        "end": 41,
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
    "case_id": "tool_chain-035",
    "arm": "I",
    "repeat": 0,
    "calls": [
      {
        "name": "crm_find_contact",
        "written": {
          "query": {
            "phone": "+79316427327"
          }
        },
        "restored": {
          "query": {
            "phone": "восемь девятьсот семьдесят семь семьсот семьдесят семь восемьсот восемьдесят девять девять"
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
            "phone": "+79316427327"
          }
        },
        "restored": {
          "query": {
            "phone": "восемь девятьсот семьдесят семь семьсот семьдесят семь восемьсот восемьдесят девять девять"
          }
        },
        "residual": {},
        "refusal_path": "query.phone",
        "refusal_rule": "phone_not_e164",
        "parsed": null,
        "seq": 2
      },
      {
        "name": "crm_find_contact",
        "written": {
          "query": {
            "phone": "79316427327"
          }
        },
        "restored": {
          "query": {
            "phone": "79777778899"
          }
        },
        "residual": {},
        "refusal_path": "query.phone",
        "refusal_rule": "phone_not_e164",
        "parsed": null,
        "seq": 3
      },
      {
        "name": "crm_find_contact",
        "written": {
          "query": {
            "phone": "89316427327"
          }
        },
        "restored": {
          "query": {
            "phone": "89777778899"
          }
        },
        "residual": {},
        "refusal_path": "query.phone",
        "refusal_rule": "phone_not_e164",
        "parsed": null,
        "seq": 4
      },
      {
        "name": "crm_find_contact",
        "written": {
          "query": {
            "phone": "+79777778899"
          }
        },
        "restored": {
          "query": {
            "phone": "+79777778899"
          }
        },
        "residual": {},
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "query": {
            "phone": "+79777778899"
          }
        },
        "seq": 5
      },
      {
        "name": "address_suggest",
        "written": {
          "count": 5,
          "query": "Брянск, Еловая 162"
        },
        "restored": {
          "count": 5,
          "query": "Брянск, Еловая 145а"
        },
        "residual": {
          "query": [
            "еловая"
          ]
        },
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "count": 5,
          "query": "Брянск, Еловая 145а"
        },
        "seq": 6
      },
      {
        "name": "address_suggest",
        "written": {
          "count": 10,
          "query": "Брянск, улица Еловая, дом 162"
        },
        "restored": {
          "count": 10,
          "query": "Брянск, улица Еловая, дом 145а"
        },
        "residual": {
          "query": [
            "еловая"
          ]
        },
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "count": 10,
          "query": "Брянск, улица Еловая, дом 145а"
        },
        "seq": 7
      },
      {
        "name": "address_suggest",
        "written": {
          "count": 10,
          "query": "Еловая 162"
        },
        "restored": {
          "count": 10,
          "query": "Еловая 145а"
        },
        "residual": {
          "query": [
            "еловая"
          ]
        },
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "count": 10,
          "query": "Еловая 145а"
        },
        "seq": 8
      },
      {
        "name": "address_suggest",
        "written": {
          "count": 10,
          "query": "Брянск Еловая"
        },
        "restored": {
          "count": 10,
          "query": "Брянск Пушкина"
        },
        "residual": {},
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "count": 10,
          "query": "Брянск Пушкина"
        },
        "seq": 9
      },
      {
        "name": "address_suggest",
        "written": {
          "count": 10,
          "query": "Брянск Пихтовая 136"
        },
        "restored": {
          "count": 10,
          "query": "Брянск Пихтовая 145а"
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
          "query": "Брянск Пихтовая 145а"
        },
        "seq": 10
      },
      {
        "name": "delivery_create_order",
        "written": {
          "comment": "Доставка по стандартному адресу, кв. 167",
          "packages": [
            {
              "weight": 1000
            }
          ],
          "recipient": {
            "name": "Бондарчук Ольга Александровна",
            "phones": [
              {
                "number": "+79316427327"
              }
            ]
          },
          "to_location": {
            "address": "ул Пихтовая, д. 136, кв. 167",
            "city": "Брянск",
            "postal_code": "241434"
          }
        },
        "restored": {
          "comment": "Доставка по стандартному адресу, кв. 44",
          "packages": [
            {
              "weight": 1000
            }
          ],
          "recipient": {
            "name": "Соколова Анна Игоревна",
            "phones": [
              {
                "number": "+79777778899"
              }
            ]
          },
          "to_location": {
            "address": "ул Пихтовая, д. 145а, кв. 44",
            "city": "Брянск",
            "postal_code": "241434"
          }
        },
        "residual": {
          "to_location.address": [
            "пихтовая"
          ]
        },
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "comment": "Доставка по стандартному адресу, кв. 44",
          "packages": [
            {
              "weight": 1000
            }
          ],
          "recipient": {
            "name": "Соколова Анна Игоревна",
            "phones": [
              "+79777778899"
            ]
          },
          "to_location": {
            "address": "ул Пихтовая, д. 145а, кв. 44",
            "city": "брянск",
            "postal_code": "241434"
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
      },
      {
        "name": "crm_find_contact",
        "written": {
          "query": {
            "last_name": "Фомина"
          }
        },
        "restored": {
          "query": {
            "last_name": "Соколова"
          }
        },
        "residual": {},
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "query": {
            "last_name": "соколова"
          }
        },
        "seq": 13
      },
      {
        "name": "address_suggest",
        "written": {
          "count": 5,
          "query": "Брянск, Речная 133"
        },
        "restored": {
          "count": 5,
          "query": "Брянск, Пихтовая 145а"
        },
        "residual": {
          "query": [
            "пихтовая"
          ]
        },
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "count": 5,
          "query": "Брянск, Пихтовая 145а"
        },
        "seq": 14
      },
      {
        "name": "crm_find_contact",
        "written": {
          "query": {
            "phone": "+79777778899"
          }
        },
        "restored": {
          "query": {
            "phone": "+79777778899"
          }
        },
        "residual": {},
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "query": {
            "phone": "+79777778899"
          }
        },
        "seq": 15
      },
      {
        "name": "notify_sms",
        "written": {
          "number": "+79316427327",
          "sign": "Dostavka",
          "text": "Заказ на доставку оформлен. Номер ord-1. Получатель: Бондарчук О.А., Брянск, ул Пихтовая, 136, кв. 167, индекс 241434. Курьер свяжется перед доставкой. Спасибо!"
        },
        "restored": {
          "number": "+79777778899",
          "sign": "Dostavka",
          "text": "Заказ на доставку оформлен. Номер ord-1. Получатель: Соколова О.А., Брянск, ул Пихтовая, 145а, кв. 44, индекс 241434. Курьер свяжется перед доставкой. Спасибо!"
        },
        "residual": {
          "text": [
            "пихтовая"
          ]
        },
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "number": "+79777778899",
          "sign": "Dostavka",
          "text": "Заказ на доставку оформлен. Номер ord-1. Получатель: Соколова О.А., Брянск, ул Пихтовая, 145а, кв. 44, индекс 241434. Курьер свяжется перед доставкой. Спасибо!"
        },
        "seq": 16
      },
      {
        "name": "crm_add_note",
        "written": {
          "entity_id": "c-1",
          "note_type": "call_in",
          "text": "02.09.2026, входящий звонок. Клиент просил оформить доставку «как обычно», данные — в карточке. Адрес сверен по справочнику (241434, Брянск, ул Пихтовая, 136), поставлен кв. 167. Оформлен заказ ord-1, вес 1000 г (по умолчанию). Номер клиента в карточке: +79316427327. Отправлено СМС с подтверждением."
        },
        "restored": {
          "entity_id": "c-1",
          "note_type": "call_in",
          "text": "02.09.2026, входящий звонок. Клиент просил оформить доставку «как обычно», данные — в карточке. Адрес сверен по справочнику (241434, Брянск, ул Пихтовая, 145а), поставлен кв. 44. Оформлен заказ ord-1, вес 1000 г (по умолчанию). Номер клиента в карточке: +79777778899. Отправлено СМС с подтверждением."
        },
        "residual": {
          "text": [
            "пихтовая"
          ]
        },
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "entity_id": "c-1",
          "note_type": "call_in",
          "text": "02.09.2026, входящий звонок. Клиент просил оформить доставку «как обычно», данные — в карточке. Адрес сверен по справочнику (241434, Брянск, ул Пихтовая, 145а), поставлен кв. 44. Оформлен заказ ord-1, вес 1000 г (по умолчанию). Номер клиента в карточке: +79777778899. Отправлено СМС с подтверждением."
        },
        "seq": 17
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
        "seq": 18
      }
    ],
    "state": [
      {
        "fields": {
          "comment": "Доставка по стандартному адресу, кв. 44",
          "packages": [
            {
              "weight": 1000
            }
          ],
          "recipient": {
            "name": "Соколова Анна Игоревна",
            "phones": [
              "+79777778899"
            ]
          },
          "to_location": {
            "address": "ул Пихтовая, д. 145а, кв. 44",
            "city": "брянск",
            "postal_code": "241434"
          }
        },
        "id": "ord-1",
        "seq": 11,
        "table": "orders",
        "tool": "delivery_create_order"
      },
      {
        "fields": {
          "number": "+79777778899",
          "sign": "Dostavka",
          "text": "Заказ на доставку оформлен. Номер ord-1. Получатель: Соколова О.А., Брянск, ул Пихтовая, 145а, кв. 44, индекс 241434. Курьер свяжется перед доставкой. Спасибо!"
        },
        "id": "sms-1",
        "seq": 16,
        "table": "sms",
        "tool": "notify_sms"
      },
      {
        "fields": {
          "entity_id": "c-1",
          "note_type": "call_in",
          "text": "02.09.2026, входящий звонок. Клиент просил оформить доставку «как обычно», данные — в карточке. Адрес сверен по справочнику (241434, Брянск, ул Пихтовая, 145а), поставлен кв. 44. Оформлен заказ ord-1, вес 1000 г (по умолчанию). Номер клиента в карточке: +79777778899. Отправлено СМС с подтверждением."
        },
        "id": "note-1",
        "seq": 17,
        "table": "notes",
        "tool": "crm_add_note"
      }
    ],
    "reply": "Конечно! Сейчас по заказу **ord-1** статус — **«Принят»** (ACCEPTED): заказ зарегистрирован в системе, передан в обработку.\n\nКак только он перейдёт на следующий этап (сборка/передача курьеру), я вас уведомлю — сообщение придёт на этот же номер. Если захотите узнать раньше, просто позвоните и назовите номер заказа ord-1, я сразу посмотрю.",
    "termination": "done",
    "cost_usd": 0.022861,
    "substitutes": {
      "i1": [
        "бондарчук",
        {
          "surname": "бондарчук"
        }
      ],
      "i10": [
        "+79316427327",
        {
          "digits": "9316427327"
        }
      ],
      "i2": [
        "ольга",
        {
          "given": "ольга"
        }
      ],
      "i3": [
        "александровна",
        {
          "patronymic": "александровна"
        }
      ],
      "i4": [
        "+79316427327",
        {
          "digits": "9316427327"
        }
      ],
      "i5": [
        "tdbrydrl@example.ru",
        {
          "domain": "example.ru",
          "local": "tdbrydrl"
        }
      ],
      "i6": [
        "1971-01-25",
        {
          "iso": "1971-01-25"
        }
      ],
      "i7": [
        "еловая",
        {
          "street": "еловая"
        }
      ],
      "i8": [
        "еловая",
        {
          "street": "еловая"
        }
      ]
    },
    "masked_spans": {
      "0": [],
      "1": [
        [
          29,
          119
        ]
      ],
      "2": [],
      "3": []
    }
  },
  "reply_raw": "Конечно! Сейчас по заказу **ord-1** статус — **«Принят»** (ACCEPTED): заказ зарегистрирован в системе, передан в обработку.\n\nКак только он перейдёт на следующий этап (сборка/передача курьеру), я вас уведомлю — сообщение придёт на этот же номер. Если захотите узнать раньше, просто позвоните и назовите номер заказа ord-1, я сразу посмотрю.",
  "control_reply": "Сейчас по заказу **ord-1** статус: **принят (ACCEPTED)** — заказ успешно оформлен и передан в обработку.\n\nКак только статус изменится (например, «передан курьеру» или «доставлен»), я вас уведомлю СМС на номер +7 977 777-88-99. Если хотите, могу проверить статус прямо сейчас ещё раз или позже по звонку — просто назовите номер заказа ord-1.",
  "tool_results": [
    {
      "tool_name": "crm_find_contact",
      "seq": 1,
      "call_ordinal": 0,
      "turn": 1,
      "return_form": "error_with_value",
      "text_real": "{\n  \"error\": {\n    \"code\": \"phone_not_e164\",\n    \"field\": \"query.phone\",\n    \"message\": \"поле query.phone: phone_not_e164: восемь девятьсот семьдесят семь семьсот семьдесят семь восемьсот восемьдесят дев\"\n  }\n}",
      "text_masked": "{\n  \"error\": {\n    \"code\": \"phone_not_e164\",\n    \"field\": \"query.phone\",\n    \"message\": \"поле query.phone: phone_not_e164: восемь девятьсот семьдесят семь семьсот семьдесят семь восемьсот восемьдесят дев\"\n  }\n}",
      "spans_real": {},
      "pieces": [],
      "forced": false
    },
    {
      "tool_name": "crm_find_contact",
      "seq": 2,
      "call_ordinal": 1,
      "turn": 1,
      "return_form": "error_with_value",
      "text_real": "{\n  \"error\": {\n    \"code\": \"phone_not_e164\",\n    \"field\": \"query.phone\",\n    \"message\": \"поле query.phone: phone_not_e164: восемь девятьсот семьдесят семь семьсот семьдесят семь восемьсот восемьдесят дев\"\n  }\n}",
      "text_masked": "{\n  \"error\": {\n    \"code\": \"phone_not_e164\",\n    \"field\": \"query.phone\",\n    \"message\": \"поле query.phone: phone_not_e164: восемь девятьсот семьдесят семь семьсот семьдесят семь восемьсот восемьдесят дев\"\n  }\n}",
      "spans_real": {},
      "pieces": [],
      "forced": false
    },
    {
      "tool_name": "crm_find_contact",
      "seq": 3,
      "call_ordinal": 0,
      "turn": 2,
      "return_form": "error_with_value",
      "text_real": "{\n  \"error\": {\n    \"code\": \"phone_not_e164\",\n    \"field\": \"query.phone\",\n    \"message\": \"поле query.phone: phone_not_e164: 79777778899\"\n  }\n}",
      "text_masked": "{\n  \"error\": {\n    \"code\": \"phone_not_e164\",\n    \"field\": \"query.phone\",\n    \"message\": \"поле query.phone: phone_not_e164: +79316427327\"\n  }\n}",
      "spans_real": {},
      "pieces": [
        [
          123,
          134,
          "+79316427327",
          "PHONE"
        ]
      ],
      "forced": false
    },
    {
      "tool_name": "crm_find_contact",
      "seq": 4,
      "call_ordinal": 1,
      "turn": 2,
      "return_form": "error_with_value",
      "text_real": "{\n  \"error\": {\n    \"code\": \"phone_not_e164\",\n    \"field\": \"query.phone\",\n    \"message\": \"поле query.phone: phone_not_e164: 89777778899\"\n  }\n}",
      "text_masked": "{\n  \"error\": {\n    \"code\": \"phone_not_e164\",\n    \"field\": \"query.phone\",\n    \"message\": \"поле query.phone: phone_not_e164: +79316427327\"\n  }\n}",
      "spans_real": {},
      "pieces": [
        [
          123,
          134,
          "+79316427327",
          "PHONE"
        ]
      ],
      "forced": false
    },
    {
      "tool_name": "crm_find_contact",
      "seq": 5,
      "call_ordinal": 2,
      "turn": 2,
      "return_form": "list",
      "text_real": "{\n  \"contacts\": [\n    {\n      \"id\": \"c-1\",\n      \"last_name\": \"соколова\",\n      \"first_name\": \"анна\",\n      \"middle_name\": \"игоревна\",\n      \"phone\": \"+79777778899\",\n      \"email\": \"sokolova91@mail.ru\",\n      \"birth_date\": \"1971-02-28\",\n      \"address\": {\n        \"city\": \"брянск\",\n        \"street\": \"пушкина\",\n        \"house\": \"145а\",\n        \"flat\": \"44\"\n      }\n    }\n  ]\n}",
      "text_masked": "{\n  \"contacts\": [\n    {\n      \"id\": \"c-1\",\n      \"last_name\": \"бондарчук\",\n      \"first_name\": \"ольга\",\n      \"middle_name\": \"александровна\",\n      \"phone\": \"+79316427327\",\n      \"email\": \"tdbrydrl@example.ru\",\n      \"birth_date\": \"1971-01-25\",\n      \"address\": {\n        \"city\": \"брянск\",\n        \"street\": \"еловая\",\n        \"house\": \"162\",\n        \"flat\": \"167\"\n      }\n    }\n  ]\n}",
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
          200
        ],
        "i6": [
          224,
          234
        ],
        "i7": [
          301,
          308
        ]
      },
      "pieces": [
        [
          63,
          71,
          "бондарчук",
          "NAME"
        ],
        [
          95,
          99,
          "ольга",
          "NAME"
        ],
        [
          124,
          132,
          "александровна",
          "NAME"
        ],
        [
          151,
          163,
          "+79316427327",
          "PHONE"
        ],
        [
          182,
          200,
          "tdbrydrl@example.ru",
          "EMAIL"
        ],
        [
          224,
          234,
          "1971-01-25",
          "DOB"
        ],
        [
          273,
          279,
          "брянск",
          "LOC"
        ],
        [
          301,
          308,
          "еловая",
          "LOC"
        ],
        [
          329,
          333,
          "162",
          "LOC"
        ],
        [
          353,
          355,
          "167",
          "LOC"
        ]
      ],
      "forced": false
    },
    {
      "tool_name": "address_suggest",
      "seq": 6,
      "call_ordinal": 0,
      "turn": 2,
      "return_form": "canon",
      "text_real": "{\n  \"suggestions\": [\n    {\n      \"value\": \"г Брянск, ул Пушкина, д 145а\",\n      \"confidence\": \"0.67\",\n      \"data\": {\n        \"postal_code\": \"241434\",\n        \"region\": \"Брянская область\",\n        \"city\": \"брянск\",\n        \"street\": \"пушкина\",\n        \"house\": \"145а\",\n        \"flat\": \"\",\n        \"fias_id\": \"d9c4a4f1-55d7-4ac6-8efa-a57b711651ed\"\n      }\n    }\n  ]\n}",
      "text_masked": "{\n  \"suggestions\": [\n    {\n      \"value\": \"г Брянск, ул Пихтовая, д 136\",\n      \"confidence\": \"0.67\",\n      \"data\": {\n        \"postal_code\": \"241434\",\n        \"region\": \"Брянская область\",\n        \"city\": \"брянск\",\n        \"street\": \"пихтовая\",\n        \"house\": \"136\",\n        \"flat\": \"\",\n        \"fias_id\": \"d9c4a4f1-55d7-4ac6-8efa-a57b711651ed\"\n      }\n    }\n  ]\n}",
      "spans_real": {
        "i8": [
          56,
          63
        ],
        "i9": [
          43,
          71
        ]
      },
      "pieces": [
        [
          43,
          71,
          "г Брянск, ул Пихтовая, д 136",
          "LOC"
        ],
        [
          206,
          212,
          "брянск",
          "LOC"
        ],
        [
          234,
          241,
          "пихтовая",
          "LOC"
        ],
        [
          262,
          266,
          "136",
          "LOC"
        ]
      ],
      "forced": false
    },
    {
      "tool_name": "address_suggest",
      "seq": 7,
      "call_ordinal": 1,
      "turn": 2,
      "return_form": "canon",
      "text_real": "{\n  \"suggestions\": [\n    {\n      \"value\": \"г Брянск, ул Пушкина, д 145а\",\n      \"confidence\": \"0.40\",\n      \"data\": {\n        \"postal_code\": \"241434\",\n        \"region\": \"Брянская область\",\n        \"city\": \"брянск\",\n        \"street\": \"пушкина\",\n        \"house\": \"145а\",\n        \"flat\": \"\",\n        \"fias_id\": \"d9c4a4f1-55d7-4ac6-8efa-a57b711651ed\"\n      }\n    }\n  ]\n}",
      "text_masked": "{\n  \"suggestions\": [\n    {\n      \"value\": \"г Брянск, ул Пихтовая, д 136\",\n      \"confidence\": \"0.40\",\n      \"data\": {\n        \"postal_code\": \"241434\",\n        \"region\": \"Брянская область\",\n        \"city\": \"брянск\",\n        \"street\": \"пихтовая\",\n        \"house\": \"136\",\n        \"flat\": \"\",\n        \"fias_id\": \"d9c4a4f1-55d7-4ac6-8efa-a57b711651ed\"\n      }\n    }\n  ]\n}",
      "spans_real": {
        "i8": [
          56,
          63
        ],
        "i9": [
          43,
          71
        ]
      },
      "pieces": [
        [
          43,
          71,
          "г Брянск, ул Пихтовая, д 136",
          "LOC"
        ],
        [
          206,
          212,
          "брянск",
          "LOC"
        ],
        [
          234,
          241,
          "пихтовая",
          "LOC"
        ],
        [
          262,
          266,
          "136",
          "LOC"
        ]
      ],
      "forced": false
    },
    {
      "tool_name": "address_suggest",
      "seq": 8,
      "call_ordinal": 2,
      "turn": 2,
      "return_form": "canon",
      "text_real": "{\n  \"suggestions\": [\n    {\n      \"value\": \"г Брянск, ул Пушкина, д 145а\",\n      \"confidence\": \"0.50\",\n      \"data\": {\n        \"postal_code\": \"241434\",\n        \"region\": \"Брянская область\",\n        \"city\": \"брянск\",\n        \"street\": \"пушкина\",\n        \"house\": \"145а\",\n        \"flat\": \"\",\n        \"fias_id\": \"d9c4a4f1-55d7-4ac6-8efa-a57b711651ed\"\n      }\n    }\n  ]\n}",
      "text_masked": "{\n  \"suggestions\": [\n    {\n      \"value\": \"г Брянск, ул Пихтовая, д 136\",\n      \"confidence\": \"0.50\",\n      \"data\": {\n        \"postal_code\": \"241434\",\n        \"region\": \"Брянская область\",\n        \"city\": \"брянск\",\n        \"street\": \"пихтовая\",\n        \"house\": \"136\",\n        \"flat\": \"\",\n        \"fias_id\": \"d9c4a4f1-55d7-4ac6-8efa-a57b711651ed\"\n      }\n    }\n  ]\n}",
      "spans_real": {
        "i8": [
          56,
          63
        ],
        "i9": [
          43,
          71
        ]
      },
      "pieces": [
        [
          43,
          71,
          "г Брянск, ул Пихтовая, д 136",
          "LOC"
        ],
        [
          206,
          212,
          "брянск",
          "LOC"
        ],
        [
          234,
          241,
          "пихтовая",
          "LOC"
        ],
        [
          262,
          266,
          "136",
          "LOC"
        ]
      ],
      "forced": false
    },
    {
      "tool_name": "address_suggest",
      "seq": 9,
      "call_ordinal": 3,
      "turn": 2,
      "return_form": "canon",
      "text_real": "{\n  \"suggestions\": [\n    {\n      \"value\": \"г Брянск, ул Пушкина, д 145а\",\n      \"confidence\": \"1.00\",\n      \"data\": {\n        \"postal_code\": \"241434\",\n        \"region\": \"Брянская область\",\n        \"city\": \"брянск\",\n        \"street\": \"пушкина\",\n        \"house\": \"145а\",\n        \"flat\": \"\",\n        \"fias_id\": \"d9c4a4f1-55d7-4ac6-8efa-a57b711651ed\"\n      }\n    }\n  ]\n}",
      "text_masked": "{\n  \"suggestions\": [\n    {\n      \"value\": \"г Брянск, ул Пихтовая, д 136\",\n      \"confidence\": \"1.00\",\n      \"data\": {\n        \"postal_code\": \"241434\",\n        \"region\": \"Брянская область\",\n        \"city\": \"брянск\",\n        \"street\": \"пихтовая\",\n        \"house\": \"136\",\n        \"flat\": \"\",\n        \"fias_id\": \"d9c4a4f1-55d7-4ac6-8efa-a57b711651ed\"\n      }\n    }\n  ]\n}",
      "spans_real": {
        "i8": [
          56,
          63
        ],
        "i9": [
          43,
          71
        ]
      },
      "pieces": [
        [
          43,
          71,
          "г Брянск, ул Пихтовая, д 136",
          "LOC"
        ],
        [
          206,
          212,
          "брянск",
          "LOC"
        ],
        [
          234,
          241,
          "пихтовая",
          "LOC"
        ],
        [
          262,
          266,
          "136",
          "LOC"
        ]
      ],
      "forced": false
    },
    {
      "tool_name": "address_suggest",
      "seq": 10,
      "call_ordinal": 4,
      "turn": 2,
      "return_form": "canon",
      "text_real": "{\n  \"suggestions\": [\n    {\n      \"value\": \"г Брянск, ул Пушкина, д 145а\",\n      \"confidence\": \"0.67\",\n      \"data\": {\n        \"postal_code\": \"241434\",\n        \"region\": \"Брянская область\",\n        \"city\": \"брянск\",\n        \"street\": \"пушкина\",\n        \"house\": \"145а\",\n        \"flat\": \"\",\n        \"fias_id\": \"d9c4a4f1-55d7-4ac6-8efa-a57b711651ed\"\n      }\n    }\n  ]\n}",
      "text_masked": "{\n  \"suggestions\": [\n    {\n      \"value\": \"г Брянск, ул Пихтовая, д 136\",\n      \"confidence\": \"0.67\",\n      \"data\": {\n        \"postal_code\": \"241434\",\n        \"region\": \"Брянская область\",\n        \"city\": \"брянск\",\n        \"street\": \"пихтовая\",\n        \"house\": \"136\",\n        \"flat\": \"\",\n        \"fias_id\": \"d9c4a4f1-55d7-4ac6-8efa-a57b711651ed\"\n      }\n    }\n  ]\n}",
      "spans_real": {
        "i8": [
          56,
          63
        ],
        "i9": [
          43,
          71
        ]
      },
      "pieces": [
        [
          43,
          71,
          "г Брянск, ул Пихтовая, д 136",
          "LOC"
        ],
        [
          206,
          212,
          "брянск",
          "LOC"
        ],
        [
          234,
          241,
          "пихтовая",
          "LOC"
        ],
        [
          262,
          266,
          "136",
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
      "text_real": "{\n  \"uuid\": \"ord-1\",\n  \"status\": \"ACCEPTED\",\n  \"recipient\": {\n    \"name\": \"Соколова Анна Игоревна\",\n    \"phone\": \"+79777778899\"\n  },\n  \"to_location\": {\n    \"postal_code\": \"241434\",\n    \"city\": \"брянск\",\n    \"address\": \"ул Пихтовая, д. 145а, кв. 44\"\n  }\n}",
      "text_masked": "{\n  \"uuid\": \"ord-1\",\n  \"status\": \"ACCEPTED\",\n  \"recipient\": {\n    \"name\": \"Фомина Агата Степановна\",\n    \"phone\": \"+79316427327\"\n  },\n  \"to_location\": {\n    \"postal_code\": \"241434\",\n    \"city\": \"брянск\",\n    \"address\": \"ул Речная, д. 133, кв. 9\"\n  }\n}",
      "spans_real": {
        "i4": [
          114,
          126
        ]
      },
      "pieces": [
        [
          75,
          97,
          "Фомина Агата Степановна",
          "NAME"
        ],
        [
          114,
          126,
          "+79316427327",
          "PHONE"
        ],
        [
          219,
          247,
          "ул Речная, д. 133, кв. 9",
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
      "return_form": "single",
      "text_real": "{\n  \"uuid\": \"ord-1\",\n  \"status\": \"ACCEPTED\",\n  \"date\": \"\",\n  \"recipient\": {\n    \"name\": \"Соколова Анна Игоревна\",\n    \"phone\": \"+79777778899\"\n  },\n  \"to_location\": {\n    \"city\": \"брянск\",\n    \"address\": \"ул Пихтовая, д. 145а, кв. 44\"\n  }\n}",
      "text_masked": "{\n  \"uuid\": \"ord-1\",\n  \"status\": \"ACCEPTED\",\n  \"date\": \"\",\n  \"recipient\": {\n    \"name\": \"Фомина Агата Степановна\",\n    \"phone\": \"+79316427327\"\n  },\n  \"to_location\": {\n    \"city\": \"брянск\",\n    \"address\": \"ул Речная, д. 133, кв. 9\"\n  }\n}",
      "spans_real": {
        "i4": [
          128,
          140
        ]
      },
      "pieces": [
        [
          89,
          111,
          "Фомина Агата Степановна",
          "NAME"
        ],
        [
          128,
          140,
          "+79316427327",
          "PHONE"
        ],
        [
          204,
          232,
          "ул Речная, д. 133, кв. 9",
          "LOC"
        ]
      ],
      "forced": false
    },
    {
      "tool_name": "crm_find_contact",
      "seq": 13,
      "call_ordinal": 3,
      "turn": 2,
      "return_form": "list",
      "text_real": "{\n  \"contacts\": [\n    {\n      \"id\": \"c-1\",\n      \"last_name\": \"соколова\",\n      \"first_name\": \"анна\",\n      \"middle_name\": \"игоревна\",\n      \"phone\": \"+79777778899\",\n      \"email\": \"sokolova91@mail.ru\",\n      \"birth_date\": \"1971-02-28\",\n      \"address\": {\n        \"city\": \"брянск\",\n        \"street\": \"пушкина\",\n        \"house\": \"145а\",\n        \"flat\": \"44\"\n      }\n    }\n  ]\n}",
      "text_masked": "{\n  \"contacts\": [\n    {\n      \"id\": \"c-1\",\n      \"last_name\": \"бондарчук\",\n      \"first_name\": \"ольга\",\n      \"middle_name\": \"александровна\",\n      \"phone\": \"+79316427327\",\n      \"email\": \"tdbrydrl@example.ru\",\n      \"birth_date\": \"1971-01-25\",\n      \"address\": {\n        \"city\": \"брянск\",\n        \"street\": \"еловая\",\n        \"house\": \"162\",\n        \"flat\": \"167\"\n      }\n    }\n  ]\n}",
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
          200
        ],
        "i6": [
          224,
          234
        ],
        "i7": [
          301,
          308
        ]
      },
      "pieces": [
        [
          63,
          71,
          "бондарчук",
          "NAME"
        ],
        [
          95,
          99,
          "ольга",
          "NAME"
        ],
        [
          124,
          132,
          "александровна",
          "NAME"
        ],
        [
          151,
          163,
          "+79316427327",
          "PHONE"
        ],
        [
          182,
          200,
          "tdbrydrl@example.ru",
          "EMAIL"
        ],
        [
          224,
          234,
          "1971-01-25",
          "DOB"
        ],
        [
          273,
          279,
          "брянск",
          "LOC"
        ],
        [
          301,
          308,
          "еловая",
          "LOC"
        ],
        [
          329,
          333,
          "162",
          "LOC"
        ],
        [
          353,
          355,
          "167",
          "LOC"
        ]
      ],
      "forced": false
    },
    {
      "tool_name": "address_suggest",
      "seq": 14,
      "call_ordinal": 5,
      "turn": 2,
      "return_form": "canon",
      "text_real": "{\n  \"suggestions\": [\n    {\n      \"value\": \"г Брянск, ул Пушкина, д 145а\",\n      \"confidence\": \"0.67\",\n      \"data\": {\n        \"postal_code\": \"241434\",\n        \"region\": \"Брянская область\",\n        \"city\": \"брянск\",\n        \"street\": \"пушкина\",\n        \"house\": \"145а\",\n        \"flat\": \"\",\n        \"fias_id\": \"d9c4a4f1-55d7-4ac6-8efa-a57b711651ed\"\n      }\n    }\n  ]\n}",
      "text_masked": "{\n  \"suggestions\": [\n    {\n      \"value\": \"г Брянск, ул Пихтовая, д 136\",\n      \"confidence\": \"0.67\",\n      \"data\": {\n        \"postal_code\": \"241434\",\n        \"region\": \"Брянская область\",\n        \"city\": \"брянск\",\n        \"street\": \"пихтовая\",\n        \"house\": \"136\",\n        \"flat\": \"\",\n        \"fias_id\": \"d9c4a4f1-55d7-4ac6-8efa-a57b711651ed\"\n      }\n    }\n  ]\n}",
      "spans_real": {
        "i8": [
          56,
          63
        ],
        "i9": [
          43,
          71
        ]
      },
      "pieces": [
        [
          43,
          71,
          "г Брянск, ул Пихтовая, д 136",
          "LOC"
        ],
        [
          206,
          212,
          "брянск",
          "LOC"
        ],
        [
          234,
          241,
          "пихтовая",
          "LOC"
        ],
        [
          262,
          266,
          "136",
          "LOC"
        ]
      ],
      "forced": false
    },
    {
      "tool_name": "crm_find_contact",
      "seq": 15,
      "call_ordinal": 4,
      "turn": 2,
      "return_form": "list",
      "text_real": "{\n  \"contacts\": [\n    {\n      \"id\": \"c-1\",\n      \"last_name\": \"соколова\",\n      \"first_name\": \"анна\",\n      \"middle_name\": \"игоревна\",\n      \"phone\": \"+79777778899\",\n      \"email\": \"sokolova91@mail.ru\",\n      \"birth_date\": \"1971-02-28\",\n      \"address\": {\n        \"city\": \"брянск\",\n        \"street\": \"пушкина\",\n        \"house\": \"145а\",\n        \"flat\": \"44\"\n      }\n    }\n  ]\n}",
      "text_masked": "{\n  \"contacts\": [\n    {\n      \"id\": \"c-1\",\n      \"last_name\": \"бондарчук\",\n      \"first_name\": \"ольга\",\n      \"middle_name\": \"александровна\",\n      \"phone\": \"+79316427327\",\n      \"email\": \"tdbrydrl@example.ru\",\n      \"birth_date\": \"1971-01-25\",\n      \"address\": {\n        \"city\": \"брянск\",\n        \"street\": \"еловая\",\n        \"house\": \"162\",\n        \"flat\": \"167\"\n      }\n    }\n  ]\n}",
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
          200
        ],
        "i6": [
          224,
          234
        ],
        "i7": [
          301,
          308
        ]
      },
      "pieces": [
        [
          63,
          71,
          "бондарчук",
          "NAME"
        ],
        [
          95,
          99,
          "ольга",
          "NAME"
        ],
        [
          124,
          132,
          "александровна",
          "NAME"
        ],
        [
          151,
          163,
          "+79316427327",
          "PHONE"
        ],
        [
          182,
          200,
          "tdbrydrl@example.ru",
          "EMAIL"
        ],
        [
          224,
          234,
          "1971-01-25",
          "DOB"
        ],
        [
          273,
          279,
          "брянск",
          "LOC"
        ],
        [
          301,
          308,
          "еловая",
          "LOC"
        ],
        [
          329,
          333,
          "162",
          "LOC"
        ],
        [
          353,
          355,
          "167",
          "LOC"
        ]
      ],
      "forced": false
    },
    {
      "tool_name": "notify_sms",
      "seq": 16,
      "call_ordinal": 0,
      "turn": 2,
      "return_form": "single",
      "text_real": "{\n  \"id\": \"sms-1\",\n  \"status\": \"queued\",\n  \"number\": \"+79777778899\"\n}",
      "text_masked": "{\n  \"id\": \"sms-1\",\n  \"status\": \"queued\",\n  \"number\": \"+79316427327\"\n}",
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
          "+79316427327",
          "PHONE"
        ]
      ],
      "forced": false
    },
    {
      "tool_name": "crm_add_note",
      "seq": 17,
      "call_ordinal": 0,
      "turn": 2,
      "return_form": "single",
      "text_real": "{\n  \"id\": \"note-1\",\n  \"entity_id\": \"c-1\",\n  \"length\": 300,\n  \"entity\": {\n    \"last_name\": \"соколова\",\n    \"first_name\": \"анна\",\n    \"phone\": \"+79777778899\"\n  }\n}",
      "text_masked": "{\n  \"id\": \"note-1\",\n  \"entity_id\": \"c-1\",\n  \"length\": 300,\n  \"entity\": {\n    \"last_name\": \"бондарчук\",\n    \"first_name\": \"ольга\",\n    \"phone\": \"+79316427327\"\n  }\n}",
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
          "бондарчук",
          "NAME"
        ],
        [
          121,
          125,
          "ольга",
          "NAME"
        ],
        [
          142,
          154,
          "+79316427327",
          "PHONE"
        ]
      ],
      "forced": false
    },
    {
      "tool_name": "order_status",
      "seq": 18,
      "call_ordinal": 0,
      "turn": 3,
      "return_form": "single",
      "text_real": "{\n  \"uuid\": \"ord-1\",\n  \"status\": \"ACCEPTED\",\n  \"date\": \"\",\n  \"recipient\": {\n    \"name\": \"Соколова Анна Игоревна\",\n    \"phone\": \"+79777778899\"\n  },\n  \"to_location\": {\n    \"city\": \"брянск\",\n    \"address\": \"ул Пихтовая, д. 145а, кв. 44\"\n  }\n}",
      "text_masked": "{\n  \"uuid\": \"ord-1\",\n  \"status\": \"ACCEPTED\",\n  \"date\": \"\",\n  \"recipient\": {\n    \"name\": \"Фомина Агата Степановна\",\n    \"phone\": \"+79316427327\"\n  },\n  \"to_location\": {\n    \"city\": \"брянск\",\n    \"address\": \"ул Речная, д. 133, кв. 9\"\n  }\n}",
      "spans_real": {
        "i4": [
          128,
          140
        ]
      },
      "pieces": [
        [
          89,
          111,
          "Фомина Агата Степановна",
          "NAME"
        ],
        [
          128,
          140,
          "+79316427327",
          "PHONE"
        ],
        [
          204,
          232,
          "ул Речная, д. 133, кв. 9",
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
      "substitute": "+79316427327",
      "request_index": 1
    },
    {
      "item_id": "i1",
      "msg": -1,
      "result_seq": 5,
      "substitute": "бондарчук",
      "request_index": 7
    },
    {
      "item_id": "i2",
      "msg": -1,
      "result_seq": 5,
      "substitute": "ольга",
      "request_index": 7
    },
    {
      "item_id": "i3",
      "msg": -1,
      "result_seq": 5,
      "substitute": "александровна",
      "request_index": 7
    },
    {
      "item_id": "i4",
      "msg": -1,
      "result_seq": 5,
      "substitute": "+79316427327",
      "request_index": 7
    },
    {
      "item_id": "i5",
      "msg": -1,
      "result_seq": 5,
      "substitute": "tdbrydrl@example.ru",
      "request_index": 7
    },
    {
      "item_id": "i6",
      "msg": -1,
      "result_seq": 5,
      "substitute": "1971-01-25",
      "request_index": 7
    },
    {
      "item_id": "i7",
      "msg": -1,
      "result_seq": 5,
      "substitute": "еловая",
      "request_index": 7
    },
    {
      "item_id": "i8",
      "msg": -1,
      "result_seq": 6,
      "substitute": "г Брянск, ул Пихтовая, д 136",
      "request_index": 8
    },
    {
      "item_id": "i9",
      "msg": -1,
      "result_seq": 6,
      "substitute": "г Брянск, ул Пихтовая, д 136",
      "request_index": 8
    },
    {
      "item_id": "i8",
      "msg": -1,
      "result_seq": 7,
      "substitute": "г Брянск, ул Пихтовая, д 136",
      "request_index": 9
    },
    {
      "item_id": "i9",
      "msg": -1,
      "result_seq": 7,
      "substitute": "г Брянск, ул Пихтовая, д 136",
      "request_index": 9
    },
    {
      "item_id": "i8",
      "msg": -1,
      "result_seq": 8,
      "substitute": "г Брянск, ул Пихтовая, д 136",
      "request_index": 10
    },
    {
      "item_id": "i9",
      "msg": -1,
      "result_seq": 8,
      "substitute": "г Брянск, ул Пихтовая, д 136",
      "request_index": 10
    },
    {
      "item_id": "i8",
      "msg": -1,
      "result_seq": 9,
      "substitute": "г Брянск, ул Пихтовая, д 136",
      "request_index": 11
    },
    {
      "item_id": "i9",
      "msg": -1,
      "result_seq": 9,
      "substitute": "г Брянск, ул Пихтовая, д 136",
      "request_index": 11
    },
    {
      "item_id": "i8",
      "msg": -1,
      "result_seq": 10,
      "substitute": "г Брянск, ул Пихтовая, д 136",
      "request_index": 12
    },
    {
      "item_id": "i9",
      "msg": -1,
      "result_seq": 10,
      "substitute": "г Брянск, ул Пихтовая, д 136",
      "request_index": 12
    },
    {
      "item_id": "i4",
      "msg": -1,
      "result_seq": 11,
      "substitute": "+79316427327",
      "request_index": 13
    },
    {
      "item_id": "i4",
      "msg": -1,
      "result_seq": 12,
      "substitute": "+79316427327",
      "request_index": 14
    },
    {
      "item_id": "i1",
      "msg": -1,
      "result_seq": 13,
      "substitute": "бондарчук",
      "request_index": 15
    },
    {
      "item_id": "i2",
      "msg": -1,
      "result_seq": 13,
      "substitute": "ольга",
      "request_index": 15
    },
    {
      "item_id": "i3",
      "msg": -1,
      "result_seq": 13,
      "substitute": "александровна",
      "request_index": 15
    },
    {
      "item_id": "i4",
      "msg": -1,
      "result_seq": 13,
      "substitute": "+79316427327",
      "request_index": 15
    },
    {
      "item_id": "i5",
      "msg": -1,
      "result_seq": 13,
      "substitute": "tdbrydrl@example.ru",
      "request_index": 15
    },
    {
      "item_id": "i6",
      "msg": -1,
      "result_seq": 13,
      "substitute": "1971-01-25",
      "request_index": 15
    },
    {
      "item_id": "i7",
      "msg": -1,
      "result_seq": 13,
      "substitute": "еловая",
      "request_index": 15
    },
    {
      "item_id": "i8",
      "msg": -1,
      "result_seq": 14,
      "substitute": "г Брянск, ул Пихтовая, д 136",
      "request_index": 16
    },
    {
      "item_id": "i9",
      "msg": -1,
      "result_seq": 14,
      "substitute": "г Брянск, ул Пихтовая, д 136",
      "request_index": 16
    },
    {
      "item_id": "i1",
      "msg": -1,
      "result_seq": 15,
      "substitute": "бондарчук",
      "request_index": 17
    },
    {
      "item_id": "i2",
      "msg": -1,
      "result_seq": 15,
      "substitute": "ольга",
      "request_index": 17
    },
    {
      "item_id": "i3",
      "msg": -1,
      "result_seq": 15,
      "substitute": "александровна",
      "request_index": 17
    },
    {
      "item_id": "i4",
      "msg": -1,
      "result_seq": 15,
      "substitute": "+79316427327",
      "request_index": 17
    },
    {
      "item_id": "i5",
      "msg": -1,
      "result_seq": 15,
      "substitute": "tdbrydrl@example.ru",
      "request_index": 17
    },
    {
      "item_id": "i6",
      "msg": -1,
      "result_seq": 15,
      "substitute": "1971-01-25",
      "request_index": 17
    },
    {
      "item_id": "i7",
      "msg": -1,
      "result_seq": 15,
      "substitute": "еловая",
      "request_index": 17
    },
    {
      "item_id": "i4",
      "msg": -1,
      "result_seq": 16,
      "substitute": "+79316427327",
      "request_index": 18
    },
    {
      "item_id": "i1",
      "msg": -1,
      "result_seq": 17,
      "substitute": "бондарчук",
      "request_index": 19
    },
    {
      "item_id": "i2",
      "msg": -1,
      "result_seq": 17,
      "substitute": "ольга",
      "request_index": 19
    },
    {
      "item_id": "i4",
      "msg": -1,
      "result_seq": 17,
      "substitute": "+79316427327",
      "request_index": 19
    },
    {
      "item_id": "i4",
      "msg": -1,
      "result_seq": 18,
      "substitute": "+79316427327",
      "request_index": 21
    }
  ],
  "turn_replies": [
    "Здравствуйте! Хотел вас найти в базе по номеру +79777778899, но система его не приняла — номер не распознаётся как корректный (похоже, где-то опечатка).\n\nПродиктуйте, пожалуйста, номер ещё раз, цифра за цифрой, — и заодно уточните, что именно сегодня заказываем (адрес, получатель, что и куда везём), а то «как обычно» у меня в системе, к сожалению, ни за чем не закреплено.\n\nПро проезд понял — да, тарифы выросли, но на стоимость доставки это не влияет.",
    "Готово! Нашёл вашу карточку в базе, адрес сверил по справочнику и оформил доставку.\n\n**Заказ ord-1**\n- Получатель: Соколова Анна Игоревна, +79777778899\n- Адрес: г. Брянск, ул. Пихтовая, д. 145а, кв. 44\n- Индекс: 241434 (подобран по городу)\n- Вес: 1000 г (по умолчанию, так как не называли)\n- Статус: принят\n\nПодтверждение отправил вам СМС. Если нужно поменять квартиру, вес или добавить вызов курьера на конкретное время — скажите.\n\nПо проезду: да, тарифы подросли, но на стоимость доставки это не влияет — считаем по весу и направлению.\n\nНебольшое уточнение: в справочнике адрес по «брянска, пушкина, 145а» нормализовался в «Пихтовую, 145а», а в вашей карточке указана «Еловая, 145а». Я оформил по данным справочника — если верна «Еловая, 145а», дайте знать, переоформлю.",
    "Конечно! Сейчас по заказу **ord-1** статус — **«Принят»** (ACCEPTED): заказ зарегистрирован в системе, передан в обработку.\n\nКак только он перейдёт на следующий этап (сборка/передача курьеру), я вас уведомлю — сообщение придёт на этот же номер. Если захотите узнать раньше, просто позвоните и назовите номер заказа ord-1, я сразу посмотрю."
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
    2,
    2,
    2,
    2,
    2,
    2,
    3
  ],
  "request_count": 21,
  "stream_mismatch": false,
  "reply_whole": "",
  "turn_residual": 1
}

## Recorded observer hops

[
  {
    "case_id": "tool_chain-035",
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
    "produced": "+79316427327",
    "reference": "восемь девятьсот семьдесят семь семьсот семьдесят семь восемьсот восемьдесят девять девять",
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
    "case_id": "tool_chain-035",
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
    "case_id": "tool_chain-035",
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
    "produced": "",
    "reference": "",
    "status": "absent",
    "verdict": null
  },
  {
    "case_id": "tool_chain-035",
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
    "produced": "",
    "reference": "",
    "status": "absent",
    "verdict": null
  },
  {
    "case_id": "tool_chain-035",
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
    "produced": "",
    "reference": "",
    "status": "absent",
    "verdict": null
  },
  {
    "case_id": "tool_chain-035",
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
    "produced": "",
    "reference": "",
    "status": "absent",
    "verdict": null
  },
  {
    "case_id": "tool_chain-035",
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
    "produced": "",
    "reference": "",
    "status": "absent",
    "verdict": null
  },
  {
    "case_id": "tool_chain-035",
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
    "produced": "",
    "reference": "",
    "status": "absent",
    "verdict": null
  },
  {
    "case_id": "tool_chain-035",
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
    "produced": "",
    "reference": "",
    "status": "absent",
    "verdict": null
  },
  {
    "case_id": "tool_chain-035",
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
    "case_id": "tool_chain-035",
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
    "case_id": "tool_chain-035",
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
    "case_id": "tool_chain-035",
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
    "case_id": "tool_chain-035",
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
    "case_id": "tool_chain-035",
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
    "case_id": "tool_chain-035",
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
    "produced": "восемь девятьсот семьдесят семь семьсот семьдесят семь восемьсот восемьдесят девять девять",
    "reference": "+79316427327",
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
    "case_id": "tool_chain-035",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i4",
      "hop_index": -1,
      "turn": 1,
      "tool_name": "crm_find_contact",
      "call_ordinal": 1,
      "parallel_group": "",
      "source_hop": -1,
      "path": "query.phone",
      "optional": false
    },
    "declared": false,
    "pii_type": "PHONE",
    "produced": "восемь девятьсот семьдесят семь семьсот семьдесят семь восемьсот восемьдесят девять девять",
    "reference": "+79316427327",
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
    "case_id": "tool_chain-035",
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
    "produced": "79777778899",
    "reference": "79316427327",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "tool_chain-035",
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
    "produced": "89777778899",
    "reference": "89316427327",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "tool_chain-035",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "",
      "hop_index": -1,
      "turn": 2,
      "tool_name": "crm_find_contact",
      "call_ordinal": 2,
      "parallel_group": "",
      "source_hop": -1,
      "path": "query.phone",
      "optional": false
    },
    "declared": false,
    "pii_type": "PHONE",
    "produced": "+79777778899",
    "reference": "+79777778899",
    "status": "unmasked",
    "verdict": null
  },
  {
    "case_id": "tool_chain-035",
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
    "produced": "Брянск, Еловая 145а",
    "reference": "Брянск, Еловая 162",
    "status": "residual",
    "verdict": null
  },
  {
    "case_id": "tool_chain-035",
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
    "produced": "Брянск, улица Еловая, дом 145а",
    "reference": "Брянск, улица Еловая, дом 162",
    "status": "residual",
    "verdict": null
  },
  {
    "case_id": "tool_chain-035",
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
    "produced": "Еловая 145а",
    "reference": "Еловая 162",
    "status": "residual",
    "verdict": null
  },
  {
    "case_id": "tool_chain-035",
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
    "produced": "Брянск Пушкина",
    "reference": "Брянск Еловая",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "tool_chain-035",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i8",
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
    "produced": "Брянск Пихтовая 145а",
    "reference": "Брянск Пихтовая 136",
    "status": "residual",
    "verdict": null
  },
  {
    "case_id": "tool_chain-035",
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
    "produced": "Соколова Анна Игоревна",
    "reference": "Бондарчук Ольга Александровна",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "tool_chain-035",
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
    "produced": "+79777778899",
    "reference": "+79316427327",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "tool_chain-035",
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
      "path": "to_location.address",
      "optional": false
    },
    "declared": false,
    "pii_type": "LOC",
    "produced": "ул Пихтовая, д. 145а, кв. 44",
    "reference": "ул Пихтовая, д. 136, кв. 167",
    "status": "residual",
    "verdict": null
  },
  {
    "case_id": "tool_chain-035",
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
    "case_id": "tool_chain-035",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "",
      "hop_index": -1,
      "turn": 2,
      "tool_name": "crm_find_contact",
      "call_ordinal": 3,
      "parallel_group": "",
      "source_hop": -1,
      "path": "query.last_name",
      "optional": false
    },
    "declared": false,
    "pii_type": "NAME",
    "produced": "Соколова",
    "reference": "Фомина",
    "status": "unmasked",
    "verdict": null
  },
  {
    "case_id": "tool_chain-035",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "",
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
    "produced": "Брянск, Пихтовая 145а",
    "reference": "Брянск, Речная 133",
    "status": "unmasked",
    "verdict": null
  },
  {
    "case_id": "tool_chain-035",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "",
      "hop_index": -1,
      "turn": 2,
      "tool_name": "crm_find_contact",
      "call_ordinal": 4,
      "parallel_group": "",
      "source_hop": -1,
      "path": "query.phone",
      "optional": false
    },
    "declared": false,
    "pii_type": "PHONE",
    "produced": "+79777778899",
    "reference": "+79777778899",
    "status": "unmasked",
    "verdict": null
  },
  {
    "case_id": "tool_chain-035",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i4",
      "hop_index": -1,
      "turn": 2,
      "tool_name": "notify_sms",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": -1,
      "path": "number",
      "optional": false
    },
    "declared": false,
    "pii_type": "PHONE",
    "produced": "+79777778899",
    "reference": "+79316427327",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  }
]
