# memory_anaphora-119 | source A | repeat 0

Synthetic benchmark evidence. Verbatim serialized fields; no inferred verdicts.

## Case specification

{
  "base": {
    "id": "memory_anaphora-119",
    "kind": "long_support",
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
    "cluster": "PHONE:9506302117",
    "conversation_id": "",
    "now": "2026-09-02",
    "messages": [
      {
        "role": "system",
        "content": "Ты оператор службы доставки. Оформляй заказы и вызовы курьера инструментами, переспрашивай только то, чего не хватает для вызова. Вес посылки, если не назван, — 1000 г; почтовый индекс подбери сам по городу получателя. Сегодня 2026-09-02. Клиент может ссылаться на сказанное раньше («ему», «на тот адрес», «тот же телефон») — восстанавливай значение из разговора, не переспрашивай.",
        "source": null,
        "name": ""
      },
      {
        "role": "user",
        "content": "привет это лебедева ирина мой телефон 8 950 630 21 17 кстати заказ 154",
        "source": null,
        "name": ""
      },
      {
        "role": "user",
        "content": "посылку примет морозов леонид адрес сарапул улица новая 119 кв 176",
        "source": null,
        "name": ""
      },
      {
        "role": "user",
        "content": "и мне на тот же телефон тоже",
        "source": null,
        "name": ""
      },
      {
        "role": "user",
        "content": "пусть курьер приедет к нему по тому адресу",
        "source": null,
        "name": ""
      },
      {
        "role": "user",
        "content": "оператору отдайте карточку первого",
        "source": null,
        "name": ""
      }
    ],
    "tools": [
      "crm_find_contact",
      "notify_sms",
      "courier_book",
      "ticket_create"
    ],
    "seed_records": [
      {
        "id": "c-caller",
        "table": "contacts",
        "fields": {
          "last_name": "лебедева",
          "first_name": "ирина",
          "middle_name": "петровна",
          "phone": "+79506302117",
          "email": "lebedeva96@list.ru",
          "birth_date": "1986-02-14",
          "address": {
            "city": "сарапул",
            "street": "северный",
            "house": "198",
            "flat": "161"
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
        "identity": "p119",
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
          "record": "c-caller",
          "path": "last_name"
        },
        "duty": "required",
        "spoken": false,
        "stale": false
      },
      {
        "id": "i2",
        "type": "NAME",
        "identity": "p119",
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
          "record": "c-caller",
          "path": "first_name"
        },
        "duty": "required",
        "spoken": false,
        "stale": false
      },
      {
        "id": "i3",
        "type": "NAME",
        "identity": "p119",
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
          "record": "c-caller",
          "path": "middle_name"
        },
        "duty": "required",
        "spoken": false,
        "stale": false
      },
      {
        "id": "i4",
        "type": "PHONE",
        "identity": "p119",
        "value": "+79506302117",
        "canonical": "+79506302117",
        "parts": {
          "digits": "9506302117"
        },
        "where": {
          "kind": "seed",
          "msg": -1,
          "start": 0,
          "end": 0,
          "record": "c-caller",
          "path": "phone"
        },
        "duty": "required",
        "spoken": false,
        "stale": false
      },
      {
        "id": "i5",
        "type": "EMAIL",
        "identity": "p119",
        "value": "lebedeva96@list.ru",
        "canonical": "lebedeva96@list.ru",
        "parts": {
          "local": "lebedeva96",
          "domain": "list.ru"
        },
        "where": {
          "kind": "seed",
          "msg": -1,
          "start": 0,
          "end": 0,
          "record": "c-caller",
          "path": "email"
        },
        "duty": "required",
        "spoken": false,
        "stale": false
      },
      {
        "id": "i6",
        "type": "DOB",
        "identity": "p119",
        "value": "1986-02-14",
        "canonical": "1986-02-14",
        "parts": {
          "iso": "1986-02-14"
        },
        "where": {
          "kind": "seed",
          "msg": -1,
          "start": 0,
          "end": 0,
          "record": "c-caller",
          "path": "birth_date"
        },
        "duty": "required",
        "spoken": false,
        "stale": false
      },
      {
        "id": "i7",
        "type": "LOC",
        "identity": "p119.home",
        "value": "северный",
        "canonical": "северный",
        "parts": {
          "street": "северный",
          "street_type": "бульвар",
          "house": "198",
          "flat": "161",
          "city": "сарапул"
        },
        "where": {
          "kind": "seed",
          "msg": -1,
          "start": 0,
          "end": 0,
          "record": "c-caller",
          "path": "address.street"
        },
        "duty": "required",
        "spoken": false,
        "stale": false
      },
      {
        "id": "i8",
        "type": "NAME",
        "identity": "p119",
        "value": "лебедева ирина",
        "canonical": "лебедева ирина",
        "parts": {
          "surname": "лебедева",
          "given": "ирина",
          "gender": "f"
        },
        "where": {
          "kind": "message",
          "msg": 1,
          "start": 11,
          "end": 25,
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
        "identity": "p119",
        "value": "8 950 630 21 17",
        "canonical": "+79506302117",
        "parts": {
          "digits": "9506302117"
        },
        "where": {
          "kind": "message",
          "msg": 1,
          "start": 38,
          "end": 53,
          "record": "",
          "path": ""
        },
        "duty": "required",
        "spoken": false,
        "stale": false
      },
      {
        "id": "i10",
        "type": "NAME",
        "identity": "p119b",
        "value": "морозов леонид",
        "canonical": "морозов леонид",
        "parts": {
          "surname": "морозов",
          "given": "леонид",
          "gender": "m"
        },
        "where": {
          "kind": "message",
          "msg": 2,
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
        "id": "i11",
        "type": "LOC",
        "identity": "p119b.home",
        "value": "сарапул улица новая 119 кв 176",
        "canonical": "сарапул улица новая 119 кв 176",
        "parts": {
          "street": "новая",
          "street_type": "улица",
          "house": "119",
          "flat": "176",
          "city": "сарапул"
        },
        "where": {
          "kind": "message",
          "msg": 2,
          "start": 36,
          "end": 66,
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
        "value": "154",
        "start": 67,
        "end": 70,
        "msg": 1,
        "family": "order_number",
        "why": "номер заказа — не персональные данные; продиктованный вслух он маскировался целиком, и это уже отгружалось"
      }
    ],
    "expects": {
      "reachable_tools": [
        "crm_find_contact",
        "notify_sms",
        "courier_book"
      ],
      "primary_identity": "p119",
      "must_contain": [
        "лебедева"
      ],
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
        "end": 10,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 1,
        "key": "",
        "start": 10,
        "end": 11,
        "origin": "literal"
      },
      {
        "msg": 1,
        "key": "name",
        "start": 11,
        "end": 25,
        "origin": "value:name"
      },
      {
        "msg": 1,
        "key": "",
        "start": 25,
        "end": 26,
        "origin": "literal"
      },
      {
        "msg": 1,
        "key": "",
        "start": 26,
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
        "end": 37,
        "origin": "chunk:noisy_word"
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
        "key": "ph",
        "start": 38,
        "end": 53,
        "origin": "value:ph"
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
        "key": "",
        "start": 61,
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
        "key": "neg1",
        "start": 67,
        "end": 70,
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
        "end": 14,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 2,
        "key": "",
        "start": 14,
        "end": 15,
        "origin": "literal"
      },
      {
        "msg": 2,
        "key": "name2",
        "start": 15,
        "end": 29,
        "origin": "value:name2"
      },
      {
        "msg": 2,
        "key": "",
        "start": 29,
        "end": 30,
        "origin": "literal"
      },
      {
        "msg": 2,
        "key": "",
        "start": 30,
        "end": 35,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 2,
        "key": "",
        "start": 35,
        "end": 36,
        "origin": "literal"
      },
      {
        "msg": 2,
        "key": "addr2",
        "start": 36,
        "end": 66,
        "origin": "value:addr2"
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
        "end": 12,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 3,
        "key": "",
        "start": 12,
        "end": 13,
        "origin": "literal"
      },
      {
        "msg": 3,
        "key": "",
        "start": 13,
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
        "end": 23,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 3,
        "key": "",
        "start": 23,
        "end": 24,
        "origin": "literal"
      },
      {
        "msg": 3,
        "key": "",
        "start": 24,
        "end": 28,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 4,
        "key": "",
        "start": 0,
        "end": 5,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 4,
        "key": "",
        "start": 5,
        "end": 6,
        "origin": "literal"
      },
      {
        "msg": 4,
        "key": "",
        "start": 6,
        "end": 12,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 4,
        "key": "",
        "start": 12,
        "end": 13,
        "origin": "literal"
      },
      {
        "msg": 4,
        "key": "",
        "start": 13,
        "end": 20,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 4,
        "key": "",
        "start": 20,
        "end": 21,
        "origin": "literal"
      },
      {
        "msg": 4,
        "key": "",
        "start": 21,
        "end": 22,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 4,
        "key": "",
        "start": 22,
        "end": 23,
        "origin": "literal"
      },
      {
        "msg": 4,
        "key": "",
        "start": 23,
        "end": 27,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 4,
        "key": "",
        "start": 27,
        "end": 28,
        "origin": "literal"
      },
      {
        "msg": 4,
        "key": "",
        "start": 28,
        "end": 30,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 4,
        "key": "",
        "start": 30,
        "end": 31,
        "origin": "literal"
      },
      {
        "msg": 4,
        "key": "",
        "start": 31,
        "end": 35,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 4,
        "key": "",
        "start": 35,
        "end": 36,
        "origin": "literal"
      },
      {
        "msg": 4,
        "key": "",
        "start": 36,
        "end": 42,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 5,
        "key": "",
        "start": 0,
        "end": 9,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 5,
        "key": "",
        "start": 9,
        "end": 10,
        "origin": "literal"
      },
      {
        "msg": 5,
        "key": "",
        "start": 10,
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
        "key": "",
        "start": 18,
        "end": 26,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 5,
        "key": "",
        "start": 26,
        "end": 27,
        "origin": "literal"
      },
      {
        "msg": 5,
        "key": "",
        "start": 27,
        "end": 34,
        "origin": "chunk:noisy_word"
      }
    ],
    "note": "пять реплик: смс «на тот же телефон», курьер «по тому адресу», обращение по «первому клиенту» с обоими людьми в тексте"
  },
  "behaviour": "memory_anaphora",
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
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i9",
      "hop_index": 2,
      "turn": 1,
      "tool_name": "crm_find_contact",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": 1,
      "path": "query.phone",
      "optional": true
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
      "item_id": "i6",
      "hop_index": 4,
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
      "owner": "user",
      "item_id": "i10",
      "hop_index": 5,
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
      "hop_index": 6,
      "turn": 2,
      "tool_name": "",
      "call_ordinal": -1,
      "parallel_group": "",
      "source_hop": -1,
      "path": "",
      "optional": false
    },
    {
      "kind": "OUT",
      "owner": "answer",
      "item_id": "i1",
      "hop_index": 7,
      "turn": 1,
      "tool_name": "",
      "call_ordinal": -1,
      "parallel_group": "",
      "source_hop": 3,
      "path": "",
      "optional": true
    },
    {
      "kind": "IN",
      "owner": "memory",
      "item_id": "i9",
      "hop_index": 8,
      "turn": 3,
      "tool_name": "",
      "call_ordinal": -1,
      "parallel_group": "",
      "source_hop": 1,
      "path": "",
      "optional": false
    },
    {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i9",
      "hop_index": 9,
      "turn": 3,
      "tool_name": "notify_sms",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": 8,
      "path": "number",
      "optional": false
    },
    {
      "kind": "IN",
      "owner": "memory",
      "item_id": "i11",
      "hop_index": 10,
      "turn": 4,
      "tool_name": "",
      "call_ordinal": -1,
      "parallel_group": "",
      "source_hop": 6,
      "path": "",
      "optional": false
    },
    {
      "kind": "IN",
      "owner": "memory",
      "item_id": "i10",
      "hop_index": 11,
      "turn": 4,
      "tool_name": "",
      "call_ordinal": -1,
      "parallel_group": "",
      "source_hop": 5,
      "path": "",
      "optional": false
    },
    {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i11",
      "hop_index": 12,
      "turn": 4,
      "tool_name": "courier_book",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": 10,
      "path": "address.street",
      "optional": false
    },
    {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i10",
      "hop_index": 13,
      "turn": 4,
      "tool_name": "courier_book",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": 11,
      "path": "contact.name",
      "optional": false
    },
    {
      "kind": "IN",
      "owner": "memory",
      "item_id": "i8",
      "hop_index": 14,
      "turn": 5,
      "tool_name": "",
      "call_ordinal": -1,
      "parallel_group": "",
      "source_hop": 0,
      "path": "",
      "optional": false
    },
    {
      "kind": "OUT",
      "owner": "summary",
      "item_id": "i8",
      "hop_index": 15,
      "turn": 5,
      "tool_name": "ticket_create",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": 14,
      "path": "subject",
      "optional": false
    },
    {
      "kind": "OUT",
      "owner": "summary",
      "item_id": "i10",
      "hop_index": 16,
      "turn": 5,
      "tool_name": "ticket_create",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": 5,
      "path": "text",
      "optional": false
    },
    {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i9",
      "hop_index": 17,
      "turn": 5,
      "tool_name": "ticket_create",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": 1,
      "path": "phone",
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
        "i4",
        "i6",
        "i7"
      ]
    }
  ],
  "forced": [],
  "memory": [
    {
      "item_id": "i9",
      "first_turn": 1,
      "recall_turn": 3,
      "anaphora": "same_phone"
    },
    {
      "item_id": "i11",
      "first_turn": 2,
      "recall_turn": 4,
      "anaphora": "same_address"
    },
    {
      "item_id": "i10",
      "first_turn": 2,
      "recall_turn": 4,
      "anaphora": "pronoun"
    },
    {
      "item_id": "i8",
      "first_turn": 1,
      "recall_turn": 5,
      "anaphora": "same_person"
    }
  ],
  "pick": null,
  "branch": null,
  "loop": null,
  "rag": null,
  "document": null,
  "has_result": true,
  "streaming": false,
  "revised_from_v4": false
}

## Actual gateway arm (written/restored calls, tool results, answers, mentions)

{
  "base": {
    "case_id": "memory_anaphora-119",
    "arm": "I",
    "repeat": 0,
    "calls": [
      {
        "name": "crm_find_contact",
        "written": {
          "query": {
            "phone": "+79504837232"
          }
        },
        "restored": {
          "query": {
            "phone": "+79506302117"
          }
        },
        "residual": {},
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "query": {
            "phone": "+79506302117"
          }
        },
        "seq": 1
      }
    ],
    "state": [],
    "reply": "Извините, не совсем поняла про «карточку первого» — уточните, пожалуйста, что вы имеете в виду?\n\nИ чтобы я могла вызвать курьера, мне всё ещё нужен интервал времени — на какую дату и время он должен приехать к Морозову Леониду по адресу сарапул улица новая 119 кв 176?",
    "termination": "done",
    "cost_usd": 0.00352,
    "substitutes": {
      "i1": [
        "мухина",
        {
          "surname": "мухина"
        }
      ],
      "i10": [
        "юдин геннадий",
        {
          "given": "геннадий",
          "surname": "юдин"
        }
      ],
      "i11": [
        "сарапул улица ивовая 146 кв 68",
        {
          "flat": "68",
          "house": "146",
          "street": "ивовая сарапул"
        }
      ],
      "i2": [
        "инна",
        {
          "given": "инна"
        }
      ],
      "i3": [
        "евгеньевна",
        {
          "patronymic": "евгеньевна"
        }
      ],
      "i4": [
        "8 950 483 72 32",
        {
          "digits": "9504837232"
        }
      ],
      "i5": [
        "xcergtmf@example.ru",
        {
          "domain": "example.ru",
          "local": "xcergtmf"
        }
      ],
      "i6": [
        "1986-05-09",
        {
          "iso": "1986-05-09"
        }
      ],
      "i7": [
        "буковая",
        {
          "street": "буковая"
        }
      ],
      "i8": [
        "мухина инна",
        {
          "given": "инна",
          "surname": "мухина"
        }
      ],
      "i9": [
        "8 950 483 72 32",
        {
          "digits": "9504837232"
        }
      ]
    },
    "masked_spans": {
      "0": [],
      "1": [
        [
          11,
          25
        ],
        [
          38,
          53
        ]
      ],
      "2": [
        [
          15,
          29
        ],
        [
          36,
          66
        ]
      ],
      "3": [],
      "4": [],
      "5": []
    }
  },
  "reply_raw": "Извините, не совсем поняла про «карточку первого» — уточните, пожалуйста, что вы имеете в виду?\n\nИ чтобы я могла вызвать курьера, мне всё ещё нужен интервал времени — на какую дату и время он должен приехать к Юдину Геннадию по адресу Сарапул, ул. Ивовая, д. 146, кв. 68?",
  "control_reply": "Прошу прощения, не совсем поняла, что значит «отдайте карточку первого». Уточните, пожалуйста.\n\nЧтобы оформить вызов курьера к Морозову Леониду (Сарапул, ул. Новая, 119, кв. 176), мне всё ещё нужны:\n\n1. **Интервал времени** — дата и часы.\n2. **Телефон для связи** — Морозова Леонида у меня нет; можно указать ваш +7 950 630-21-17?",
  "tool_results": [
    {
      "tool_name": "crm_find_contact",
      "seq": 1,
      "call_ordinal": 0,
      "turn": 1,
      "return_form": "list",
      "text_real": "{\n  \"contacts\": [\n    {\n      \"id\": \"c-caller\",\n      \"last_name\": \"лебедева\",\n      \"first_name\": \"ирина\",\n      \"middle_name\": \"петровна\",\n      \"phone\": \"+79506302117\",\n      \"email\": \"lebedeva96@list.ru\",\n      \"birth_date\": \"1986-02-14\",\n      \"address\": {\n        \"city\": \"сарапул\",\n        \"street\": \"северный\",\n        \"house\": \"198\",\n        \"flat\": \"161\"\n      }\n    }\n  ]\n}",
      "text_masked": "{\n  \"contacts\": [\n    {\n      \"id\": \"c-caller\",\n      \"last_name\": \"мухина\",\n      \"first_name\": \"инна\",\n      \"middle_name\": \"евгеньевна\",\n      \"phone\": \"8 950 483 72 32\",\n      \"email\": \"xcergtmf@example.ru\",\n      \"birth_date\": \"1986-05-09\",\n      \"address\": {\n        \"city\": \"сарапул\",\n        \"street\": \"буковая\",\n        \"house\": \"102\",\n        \"flat\": \"83\"\n      }\n    }\n  ]\n}",
      "spans_real": {
        "i1": [
          68,
          76
        ],
        "i2": [
          100,
          105
        ],
        "i3": [
          130,
          138
        ],
        "i4": [
          157,
          169
        ],
        "i5": [
          188,
          206
        ],
        "i6": [
          230,
          240
        ],
        "i7": [
          308,
          316
        ]
      },
      "pieces": [
        [
          68,
          76,
          "мухина",
          "NAME"
        ],
        [
          100,
          105,
          "инна",
          "NAME"
        ],
        [
          130,
          138,
          "евгеньевна",
          "NAME"
        ],
        [
          157,
          169,
          "8 950 483 72 32",
          "PHONE"
        ],
        [
          188,
          206,
          "xcergtmf@example.ru",
          "EMAIL"
        ],
        [
          230,
          240,
          "1986-05-09",
          "DOB"
        ],
        [
          279,
          286,
          "сарапул",
          "LOC"
        ],
        [
          308,
          316,
          "буковая",
          "LOC"
        ],
        [
          337,
          340,
          "102",
          "LOC"
        ],
        [
          360,
          363,
          "83",
          "LOC"
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
      "substitute": "мухина инна",
      "request_index": 1
    },
    {
      "item_id": "i9",
      "msg": 1,
      "result_seq": -1,
      "substitute": "8 950 483 72 32",
      "request_index": 1
    },
    {
      "item_id": "i1",
      "msg": -1,
      "result_seq": 1,
      "substitute": "мухина",
      "request_index": 2
    },
    {
      "item_id": "i2",
      "msg": -1,
      "result_seq": 1,
      "substitute": "инна",
      "request_index": 2
    },
    {
      "item_id": "i3",
      "msg": -1,
      "result_seq": 1,
      "substitute": "евгеньевна",
      "request_index": 2
    },
    {
      "item_id": "i4",
      "msg": -1,
      "result_seq": 1,
      "substitute": "8 950 483 72 32",
      "request_index": 2
    },
    {
      "item_id": "i5",
      "msg": -1,
      "result_seq": 1,
      "substitute": "xcergtmf@example.ru",
      "request_index": 2
    },
    {
      "item_id": "i6",
      "msg": -1,
      "result_seq": 1,
      "substitute": "1986-05-09",
      "request_index": 2
    },
    {
      "item_id": "i7",
      "msg": -1,
      "result_seq": 1,
      "substitute": "буковая",
      "request_index": 2
    },
    {
      "item_id": "i10",
      "msg": 2,
      "result_seq": -1,
      "substitute": "юдин геннадий",
      "request_index": 3
    },
    {
      "item_id": "i11",
      "msg": 2,
      "result_seq": -1,
      "substitute": "сарапул улица ивовая 146 кв 68",
      "request_index": 3
    }
  ],
  "turn_replies": [
    "Здравствуйте, Ирина Петровна! Нашла вашу карточку в системе. Чем могу помочь по заказу №154?",
    "Приняла: получатель — Морозов Леонид, адрес: сарапул улица новая 119 кв 176.\n\nУточните, пожалуйста:\n1. На какой интервал времени вызвать курьера (дата и время)?\n2. Телефон получателя для связи с курьером.",
    "Поняла: для связи и уведомлений используем ваш номер 8 950 630 21 17.\n\nОсталось уточнить главное — на какой интервал времени вызвать курьера (дата и время)?",
    "Адрес курьера понятен: сарапул улица новая 119 кв 176.\n\nНо без интервала времени я не смогу оформить вызов — подскажите, на какую дату и в какое время (например, сегодня с 15:00 до 18:00) должен приехать курьер?",
    "Извините, не совсем поняла про «карточку первого» — уточните, пожалуйста, что вы имеете в виду?\n\nИ чтобы я могла вызвать курьера, мне всё ещё нужен интервал времени — на какую дату и время он должен приехать к Морозову Леониду по адресу сарапул улица новая 119 кв 176?"
  ],
  "call_turns": [
    1
  ],
  "request_count": 6,
  "stream_mismatch": false,
  "reply_whole": "",
  "turn_residual": 2
}

## Recorded observer hops

[
  {
    "case_id": "memory_anaphora-119",
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
    "produced": "мухина инна",
    "reference": "лебедева ирина",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "memory_anaphora-119",
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
    "produced": "8 950 483 72 32",
    "reference": "8 950 630 21 17",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "memory_anaphora-119",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i9",
      "hop_index": 2,
      "turn": 1,
      "tool_name": "crm_find_contact",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": 1,
      "path": "query.phone",
      "optional": true
    },
    "declared": true,
    "pii_type": "PHONE",
    "produced": "+79506302117",
    "reference": "+79504837232",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "memory_anaphora-119",
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
    "produced": "мухина",
    "reference": "лебедева",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "memory_anaphora-119",
    "repeat": 0,
    "hop": {
      "kind": "IN",
      "owner": "tool",
      "item_id": "i6",
      "hop_index": 4,
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
    "produced": "1986-05-09",
    "reference": "1986-02-14",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "memory_anaphora-119",
    "repeat": 0,
    "hop": {
      "kind": "IN",
      "owner": "user",
      "item_id": "i10",
      "hop_index": 5,
      "turn": 2,
      "tool_name": "",
      "call_ordinal": -1,
      "parallel_group": "",
      "source_hop": -1,
      "path": "",
      "optional": false
    },
    "declared": true,
    "pii_type": "NAME",
    "produced": "юдин геннадий",
    "reference": "морозов леонид",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "memory_anaphora-119",
    "repeat": 0,
    "hop": {
      "kind": "IN",
      "owner": "user",
      "item_id": "i11",
      "hop_index": 6,
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
    "produced": "сарапул улица ивовая 146 кв 68",
    "reference": "сарапул улица новая 119 кв 176",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "memory_anaphora-119",
    "repeat": 0,
    "hop": {
      "kind": "IN",
      "owner": "memory",
      "item_id": "i9",
      "hop_index": 8,
      "turn": 3,
      "tool_name": "",
      "call_ordinal": -1,
      "parallel_group": "",
      "source_hop": 1,
      "path": "",
      "optional": false
    },
    "declared": true,
    "pii_type": "PHONE",
    "produced": "8 950 483 72 32",
    "reference": "8 950 630 21 17",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "memory_anaphora-119",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i9",
      "hop_index": 9,
      "turn": 3,
      "tool_name": "notify_sms",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": 8,
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
    "case_id": "memory_anaphora-119",
    "repeat": 0,
    "hop": {
      "kind": "IN",
      "owner": "memory",
      "item_id": "i11",
      "hop_index": 10,
      "turn": 4,
      "tool_name": "",
      "call_ordinal": -1,
      "parallel_group": "",
      "source_hop": 6,
      "path": "",
      "optional": false
    },
    "declared": true,
    "pii_type": "LOC",
    "produced": "сарапул улица ивовая 146 кв 68",
    "reference": "сарапул улица новая 119 кв 176",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "memory_anaphora-119",
    "repeat": 0,
    "hop": {
      "kind": "IN",
      "owner": "memory",
      "item_id": "i10",
      "hop_index": 11,
      "turn": 4,
      "tool_name": "",
      "call_ordinal": -1,
      "parallel_group": "",
      "source_hop": 5,
      "path": "",
      "optional": false
    },
    "declared": true,
    "pii_type": "NAME",
    "produced": "юдин геннадий",
    "reference": "морозов леонид",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "memory_anaphora-119",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i11",
      "hop_index": 12,
      "turn": 4,
      "tool_name": "courier_book",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": 10,
      "path": "address.street",
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
    "case_id": "memory_anaphora-119",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i10",
      "hop_index": 13,
      "turn": 4,
      "tool_name": "courier_book",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": 11,
      "path": "contact.name",
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
    "case_id": "memory_anaphora-119",
    "repeat": 0,
    "hop": {
      "kind": "IN",
      "owner": "memory",
      "item_id": "i8",
      "hop_index": 14,
      "turn": 5,
      "tool_name": "",
      "call_ordinal": -1,
      "parallel_group": "",
      "source_hop": 0,
      "path": "",
      "optional": false
    },
    "declared": true,
    "pii_type": "NAME",
    "produced": "мухина инна",
    "reference": "лебедева ирина",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "memory_anaphora-119",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "summary",
      "item_id": "i8",
      "hop_index": 15,
      "turn": 5,
      "tool_name": "ticket_create",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": 14,
      "path": "subject",
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
    "case_id": "memory_anaphora-119",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "summary",
      "item_id": "i10",
      "hop_index": 16,
      "turn": 5,
      "tool_name": "ticket_create",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": 5,
      "path": "text",
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
    "case_id": "memory_anaphora-119",
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
    "pii_type": "NAME",
    "produced": "Морозову Леониду",
    "reference": "Юдину Геннадию",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "memory_anaphora-119",
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
    "pii_type": "LOC",
    "produced": "сарапул",
    "reference": "Сарапул",
    "status": "observed",
    "verdict": {
      "same": false,
      "differs": [
        "case_class"
      ]
    }
  },
  {
    "case_id": "memory_anaphora-119",
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
    "pii_type": "LOC",
    "produced": " улица новая",
    "reference": ", ул. Ивовая",
    "status": "observed",
    "verdict": {
      "same": false,
      "differs": [
        "case_class",
        "commas",
        "generic"
      ]
    }
  }
]
