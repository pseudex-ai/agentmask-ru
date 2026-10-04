# memory_anaphora-045 | source B | repeat 0

Synthetic benchmark evidence. Verbatim serialized fields; no inferred verdicts.

## Case specification

{
  "base": {
    "id": "memory_anaphora-045",
    "kind": "long_support",
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
    "cluster": "PHONE:9261234567",
    "conversation_id": "conv-memory_anaphora-45",
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
        "content": "здравствуйте это битюкова зинаида мой телефон 8-926-123-45-67 да и к 10 часам",
        "source": null,
        "name": ""
      },
      {
        "role": "user",
        "content": "посылку примет громова марина адрес казань улица нижняя 10 квартира 151",
        "source": null,
        "name": ""
      },
      {
        "role": "user",
        "content": "продублируйте мне на тот же телефон",
        "source": null,
        "name": ""
      },
      {
        "role": "user",
        "content": "курьера к нему отправьте на тот адрес",
        "source": null,
        "name": ""
      },
      {
        "role": "user",
        "content": "и передайте оператору всё по первому клиенту",
        "source": null,
        "name": ""
      }
    ],
    "tools": [
      "crm_find_contact",
      "notify_sms",
      "courier_book",
      "escalate_to_human"
    ],
    "seed_records": [
      {
        "id": "c-caller",
        "table": "contacts",
        "fields": {
          "last_name": "битюкова",
          "first_name": "зинаида",
          "middle_name": "николаевна",
          "phone": "+79261234567",
          "email": "bityukova80@gmail.com",
          "birth_date": "1975-11-02",
          "address": {
            "city": "казань",
            "street": "кирова",
            "house": "22",
            "flat": "227"
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
        "identity": "p45",
        "value": "битюкова",
        "canonical": "битюкова",
        "parts": {
          "surname": "битюкова",
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
        "identity": "p45",
        "value": "зинаида",
        "canonical": "зинаида",
        "parts": {
          "given": "зинаида",
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
        "identity": "p45",
        "value": "николаевна",
        "canonical": "николаевна",
        "parts": {
          "patronymic": "николаевна",
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
        "identity": "p45",
        "value": "+79261234567",
        "canonical": "+79261234567",
        "parts": {
          "digits": "9261234567"
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
        "identity": "p45",
        "value": "bityukova80@gmail.com",
        "canonical": "bityukova80@gmail.com",
        "parts": {
          "local": "bityukova80",
          "domain": "gmail.com"
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
        "identity": "p45",
        "value": "1975-11-02",
        "canonical": "1975-11-02",
        "parts": {
          "iso": "1975-11-02"
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
        "identity": "p45.home",
        "value": "кирова",
        "canonical": "кирова",
        "parts": {
          "street": "кирова",
          "street_type": "бульвар",
          "house": "22",
          "flat": "227",
          "city": "казань"
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
        "identity": "p45",
        "value": "битюкова зинаида",
        "canonical": "битюкова зинаида",
        "parts": {
          "surname": "битюкова",
          "given": "зинаида",
          "gender": "f"
        },
        "where": {
          "kind": "message",
          "msg": 1,
          "start": 17,
          "end": 33,
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
        "identity": "p45",
        "value": "8-926-123-45-67",
        "canonical": "+79261234567",
        "parts": {
          "digits": "9261234567"
        },
        "where": {
          "kind": "message",
          "msg": 1,
          "start": 46,
          "end": 61,
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
        "identity": "p45b",
        "value": "громова марина",
        "canonical": "громова марина",
        "parts": {
          "surname": "громова",
          "given": "марина",
          "gender": "f"
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
        "identity": "p45b.home",
        "value": "казань улица нижняя 10 квартира 151",
        "canonical": "казань улица нижняя 10 квартира 151",
        "parts": {
          "street": "нижняя",
          "street_type": "улица",
          "house": "10",
          "flat": "151",
          "city": "казань"
        },
        "where": {
          "kind": "message",
          "msg": 2,
          "start": 36,
          "end": 71,
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
        "value": "10 часам",
        "start": 69,
        "end": 77,
        "msg": 1,
        "family": "time_of_day",
        "why": "время, а не номер"
      }
    ],
    "expects": {
      "reachable_tools": [
        "crm_find_contact",
        "notify_sms",
        "courier_book"
      ],
      "primary_identity": "p45",
      "must_contain": [
        "битюкова"
      ],
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
        "key": "name",
        "start": 17,
        "end": 33,
        "origin": "value:name"
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
        "key": "",
        "start": 38,
        "end": 45,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 1,
        "key": "",
        "start": 45,
        "end": 46,
        "origin": "literal"
      },
      {
        "msg": 1,
        "key": "ph",
        "start": 46,
        "end": 61,
        "origin": "value:ph"
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
        "end": 64,
        "origin": "chunk:noisy_word"
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
        "end": 68,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 1,
        "key": "",
        "start": 68,
        "end": 69,
        "origin": "literal"
      },
      {
        "msg": 1,
        "key": "neg1",
        "start": 69,
        "end": 77,
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
        "end": 71,
        "origin": "value:addr2"
      },
      {
        "msg": 3,
        "key": "",
        "start": 0,
        "end": 13,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 3,
        "key": "",
        "start": 13,
        "end": 14,
        "origin": "literal"
      },
      {
        "msg": 3,
        "key": "",
        "start": 14,
        "end": 17,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 3,
        "key": "",
        "start": 17,
        "end": 18,
        "origin": "literal"
      },
      {
        "msg": 3,
        "key": "",
        "start": 18,
        "end": 20,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 3,
        "key": "",
        "start": 20,
        "end": 21,
        "origin": "literal"
      },
      {
        "msg": 3,
        "key": "",
        "start": 21,
        "end": 24,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 3,
        "key": "",
        "start": 24,
        "end": 25,
        "origin": "literal"
      },
      {
        "msg": 3,
        "key": "",
        "start": 25,
        "end": 27,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 3,
        "key": "",
        "start": 27,
        "end": 28,
        "origin": "literal"
      },
      {
        "msg": 3,
        "key": "",
        "start": 28,
        "end": 35,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 4,
        "key": "",
        "start": 0,
        "end": 7,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 4,
        "key": "",
        "start": 7,
        "end": 8,
        "origin": "literal"
      },
      {
        "msg": 4,
        "key": "",
        "start": 8,
        "end": 9,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 4,
        "key": "",
        "start": 9,
        "end": 10,
        "origin": "literal"
      },
      {
        "msg": 4,
        "key": "",
        "start": 10,
        "end": 14,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 4,
        "key": "",
        "start": 14,
        "end": 15,
        "origin": "literal"
      },
      {
        "msg": 4,
        "key": "",
        "start": 15,
        "end": 24,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 4,
        "key": "",
        "start": 24,
        "end": 25,
        "origin": "literal"
      },
      {
        "msg": 4,
        "key": "",
        "start": 25,
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
        "end": 31,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 4,
        "key": "",
        "start": 31,
        "end": 32,
        "origin": "literal"
      },
      {
        "msg": 4,
        "key": "",
        "start": 32,
        "end": 37,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 5,
        "key": "",
        "start": 0,
        "end": 1,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 5,
        "key": "",
        "start": 1,
        "end": 2,
        "origin": "literal"
      },
      {
        "msg": 5,
        "key": "",
        "start": 2,
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
        "end": 21,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 5,
        "key": "",
        "start": 21,
        "end": 22,
        "origin": "literal"
      },
      {
        "msg": 5,
        "key": "",
        "start": 22,
        "end": 25,
        "origin": "chunk:noisy_word"
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
        "end": 28,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 5,
        "key": "",
        "start": 28,
        "end": 29,
        "origin": "literal"
      },
      {
        "msg": 5,
        "key": "",
        "start": 29,
        "end": 36,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 5,
        "key": "",
        "start": 36,
        "end": 37,
        "origin": "literal"
      },
      {
        "msg": 5,
        "key": "",
        "start": 37,
        "end": 44,
        "origin": "chunk:noisy_word"
      }
    ],
    "note": "пять реплик, два человека, четыре отсылки без значения: телефон в смс, адрес и получатель в курьера, первый клиент — в сводку"
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
      "kind": "OUT",
      "owner": "template",
      "item_id": "i1",
      "hop_index": 10,
      "turn": 3,
      "tool_name": "notify_sms",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": 3,
      "path": "text",
      "optional": false
    },
    {
      "kind": "IN",
      "owner": "memory",
      "item_id": "i11",
      "hop_index": 11,
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
      "hop_index": 12,
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
      "hop_index": 13,
      "turn": 4,
      "tool_name": "courier_book",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": 11,
      "path": "address.street",
      "optional": false
    },
    {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i10",
      "hop_index": 14,
      "turn": 4,
      "tool_name": "courier_book",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": 12,
      "path": "contact.name",
      "optional": false
    },
    {
      "kind": "IN",
      "owner": "memory",
      "item_id": "i8",
      "hop_index": 15,
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
      "hop_index": 16,
      "turn": 5,
      "tool_name": "escalate_to_human",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": 15,
      "path": "summary",
      "optional": false
    },
    {
      "kind": "OUT",
      "owner": "summary",
      "item_id": "i9",
      "hop_index": 17,
      "turn": 5,
      "tool_name": "escalate_to_human",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": 1,
      "path": "summary",
      "optional": false
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
    "case_id": "memory_anaphora-045",
    "arm": "I",
    "repeat": 0,
    "calls": [
      {
        "name": "crm_find_contact",
        "written": {
          "query": {
            "last_name": "Осипова"
          }
        },
        "restored": {
          "query": {
            "last_name": "Битюкова"
          }
        },
        "residual": {},
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "query": {
            "last_name": "битюкова"
          }
        },
        "seq": 1
      },
      {
        "name": "courier_book",
        "written": {
          "address": {
            "building": "95",
            "locality": "Казань",
            "sflat": "211",
            "street": "Родниковая"
          },
          "contact": {
            "name": "Осипова Прасковья",
            "phone": "+79664177354"
          },
          "interval": {
            "from": "2026-09-02T09:00:00+03:00",
            "to": "2026-09-02T10:00:00+03:00"
          }
        },
        "restored": {
          "address": {
            "building": "22",
            "locality": "Казань",
            "sflat": "227",
            "street": "Кирова"
          },
          "contact": {
            "name": "Битюкова Зинаида",
            "phone": "+79261234567"
          },
          "interval": {
            "from": "2026-09-02T09:00:00+03:00",
            "to": "2026-09-02T10:00:00+03:00"
          }
        },
        "residual": {},
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "address": {
            "building": "22",
            "locality": "казань",
            "porch": "",
            "sflat": "227",
            "street": "кирова"
          },
          "contact": {
            "name": "Битюкова Зинаида",
            "phone": "+79261234567"
          },
          "interval": {
            "from": "2026-09-02T09:00:00+03:00",
            "to": "2026-09-02T10:00:00+03:00"
          }
        },
        "seq": 2
      },
      {
        "name": "courier_book",
        "written": {
          "address": {
            "building": "22",
            "locality": "Казань",
            "sflat": "21",
            "street": "Липовая"
          },
          "contact": {
            "name": "Мухин Степан",
            "phone": "+79664177354"
          },
          "interval": {
            "from": "2026-09-02T09:00:00+03:00",
            "to": "2026-09-02T10:00:00+03:00"
          }
        },
        "restored": {
          "address": {
            "building": "10",
            "locality": "Казань",
            "sflat": "151",
            "street": "Нижняя"
          },
          "contact": {
            "name": "Громов Марин",
            "phone": "+79261234567"
          },
          "interval": {
            "from": "2026-09-02T09:00:00+03:00",
            "to": "2026-09-02T10:00:00+03:00"
          }
        },
        "residual": {},
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "address": {
            "building": "10",
            "locality": "казань",
            "porch": "",
            "sflat": "151",
            "street": "нижняя"
          },
          "contact": {
            "name": "Громов Марин",
            "phone": "+79261234567"
          },
          "interval": {
            "from": "2026-09-02T09:00:00+03:00",
            "to": "2026-09-02T10:00:00+03:00"
          }
        },
        "seq": 3
      },
      {
        "name": "notify_sms",
        "written": {
          "number": "+79664177354",
          "sign": "Dostavka",
          "text": "Заявка clm-2 оформлена. Курьер: г. Казань, ул. Липовая, д. 22, кв. 21. Получатель: Мухин Степан. Интервал: 02.09.2026, 09:00-10:00 (прибудет к 10:00). Телефон: 8-966-417-73-54."
        },
        "restored": {
          "number": "+79261234567",
          "sign": "Dostavka",
          "text": "Заявка clm-2 оформлена. Курьер: г. Казань, ул. Нижняя, д. 10, кв. 151. Получатель: Громов Марин. Интервал: 02.09.2026, 09:00-10:00 (прибудет к 10:00). Телефон: +79261234567."
        },
        "residual": {},
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "number": "+79261234567",
          "sign": "Dostavka",
          "text": "Заявка clm-2 оформлена. Курьер: г. Казань, ул. Нижняя, д. 10, кв. 151. Получатель: Громов Марин. Интервал: 02.09.2026, 09:00-10:00 (прибудет к 10:00). Телефон: +79261234567."
        },
        "seq": 4
      },
      {
        "name": "escalate_to_human",
        "written": {
          "queue": "general",
          "summary": "Клиент: Осипова Прасковья Александровна, тел. 8-966-417-73-54 (карточка в CRM найдена). Ситуация: изначально я оформил вызов курьера clm-1 на её адрес из карточки (г. Казань, ул. Родниковая, д. 95, кв. 211) на 02.09.2026, 09:00–10:00, так как адрес в первом сообщении не был назван. Затем клиент уточнил, что посылку примет Мухин Степан, адрес доставки: г. Казань, ул. Липовая, д. 22, кв. 21 — оформлен вызов clm-2 на тот же интервал (09:00–10:00), получатель Мухин Степан, тел. 8-966-417-73-54. Клиенту отправлено СМС с деталями заявки clm-2. Просьба: разобраться с лишним вызовом clm-1 (Родниковая, 95) — вероятно, его нужно отменить, посылка едет только на адрес Липовая, 22, кв. 21. Что уже сделано: заявки clm-1 и clm-2 оформлены, СМС отправлено."
        },
        "restored": {
          "queue": "general",
          "summary": "Клиент: Битюкова Зинаида Николаевна, тел. +79261234567 (карточка в CRM найдена). Ситуация: изначально я оформил вызов курьера clm-1 на её адрес из карточки (г. Казань, ул. Кирова, д. 22, кв. 227) на 02.09.2026, 09:00–10:00, так как адрес в первом сообщении не был назван. Затем клиент уточнил, что посылку примет Громов Марин, адрес доставки: г. Казань, ул. Нижняя, д. 10, кв. 151 — оформлен вызов clm-2 на тот же интервал (09:00–10:00), получатель Громов Марин, тел. +79261234567. Клиенту отправлено СМС с деталями заявки clm-2. Просьба: разобраться с лишним вызовом clm-1 (Родниковая, 22) — вероятно, его нужно отменить, посылка едет только на адрес Нижняя, 10, кв. 151. Что уже сделано: заявки clm-1 и clm-2 оформлены, СМС отправлено."
        },
        "residual": {
          "summary": [
            "родниковая"
          ]
        },
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "queue": "general",
          "summary": "Клиент: Битюкова Зинаида Николаевна, тел. +79261234567 (карточка в CRM найдена). Ситуация: изначально я оформил вызов курьера clm-1 на её адрес из карточки (г. Казань, ул. Кирова, д. 22, кв. 227) на 02.09.2026, 09:00–10:00, так как адрес в первом сообщении не был назван. Затем клиент уточнил, что посылку примет Громов Марин, адрес доставки: г. Казань, ул. Нижняя, д. 10, кв. 151 — оформлен вызов clm-2 на тот же интервал (09:00–10:00), получатель Громов Марин, тел. +79261234567. Клиенту отправлено СМС с деталями заявки clm-2. Просьба: разобраться с лишним вызовом clm-1 (Родниковая, 22) — вероятно, его нужно отменить, посылка едет только на адрес Нижняя, 10, кв. 151. Что уже сделано: заявки clm-1 и clm-2 оформлены, СМС отправлено."
        },
        "seq": 5
      }
    ],
    "state": [
      {
        "fields": {
          "address": {
            "building": "22",
            "locality": "казань",
            "porch": "",
            "sflat": "227",
            "street": "кирова"
          },
          "contact": {
            "name": "Битюкова Зинаида",
            "phone": "+79261234567"
          },
          "interval": {
            "from": "2026-09-02T09:00:00+03:00",
            "to": "2026-09-02T10:00:00+03:00"
          }
        },
        "id": "clm-1",
        "seq": 2,
        "table": "claims",
        "tool": "courier_book"
      },
      {
        "fields": {
          "address": {
            "building": "10",
            "locality": "казань",
            "porch": "",
            "sflat": "151",
            "street": "нижняя"
          },
          "contact": {
            "name": "Громов Марин",
            "phone": "+79261234567"
          },
          "interval": {
            "from": "2026-09-02T09:00:00+03:00",
            "to": "2026-09-02T10:00:00+03:00"
          }
        },
        "id": "clm-2",
        "seq": 3,
        "table": "claims",
        "tool": "courier_book"
      },
      {
        "fields": {
          "number": "+79261234567",
          "sign": "Dostavka",
          "text": "Заявка clm-2 оформлена. Курьер: г. Казань, ул. Нижняя, д. 10, кв. 151. Получатель: Громов Марин. Интервал: 02.09.2026, 09:00-10:00 (прибудет к 10:00). Телефон: +79261234567."
        },
        "id": "sms-1",
        "seq": 4,
        "table": "sms",
        "tool": "notify_sms"
      },
      {
        "fields": {
          "queue": "general",
          "summary": "Клиент: Битюкова Зинаида Николаевна, тел. +79261234567 (карточка в CRM найдена). Ситуация: изначально я оформил вызов курьера clm-1 на её адрес из карточки (г. Казань, ул. Кирова, д. 22, кв. 227) на 02.09.2026, 09:00–10:00, так как адрес в первом сообщении не был назван. Затем клиент уточнил, что посылку примет Громов Марин, адрес доставки: г. Казань, ул. Нижняя, д. 10, кв. 151 — оформлен вызов clm-2 на тот же интервал (09:00–10:00), получатель Громов Марин, тел. +79261234567. Клиенту отправлено СМС с деталями заявки clm-2. Просьба: разобраться с лишним вызовом clm-1 (Родниковая, 22) — вероятно, его нужно отменить, посылка едет только на адрес Нижняя, 10, кв. 151. Что уже сделано: заявки clm-1 и clm-2 оформлены, СМС отправлено."
        },
        "id": "esc-1",
        "seq": 5,
        "table": "escalations",
        "tool": "escalate_to_human"
      }
    ],
    "reply": "Передал оператору (Соколов Андрей) всю информацию по первому клиенту:\n\n- **Клиент:** Битюкова Зинаида Николаевна, +79261234567\n- **Что случилось:** сначала оформили вызов clm-1 на домашний адрес из карточки (ул. Родниковая, д. 22, кв. 227), затем клиент уточнил, что посылка идёт Громов Марин на казань улица нижняя 10 квартира 151 (clm-2).\n- **Что сделано:** оформлены вызовы clm-1 и clm-2, отправлено СМС с деталями clm-2.\n- **Запрос:** разобраться с лишним вызовом clm-1 (вероятно, его нужно отменить).\n\nНомер обращения — esc-1. Оператор свяжется с вами при необходимости.",
    "termination": "done",
    "cost_usd": 0.009792,
    "substitutes": {
      "i1": [
        "осипова",
        {
          "surname": "осипова"
        }
      ],
      "i10": [
        "мухина степана",
        {
          "given": "степана",
          "surname": "мухина"
        }
      ],
      "i11": [
        "казань улица липовая 22 квартира 21",
        {
          "flat": "21",
          "house": "22",
          "street": "казань липовая"
        }
      ],
      "i2": [
        "прасковья",
        {
          "given": "прасковья"
        }
      ],
      "i3": [
        "александровна",
        {
          "patronymic": "александровна"
        }
      ],
      "i4": [
        "8-966-417-73-54",
        {
          "digits": "9664177354"
        }
      ],
      "i5": [
        "pmwguojr@example.ru",
        {
          "domain": "example.ru",
          "local": "pmwguojr"
        }
      ],
      "i6": [
        "1975-11-11",
        {
          "iso": "1975-11-11"
        }
      ],
      "i7": [
        "родниковая",
        {
          "street": "родниковая"
        }
      ],
      "i8": [
        "осипова прасковья",
        {
          "given": "прасковья",
          "surname": "осипова"
        }
      ],
      "i9": [
        "8-966-417-73-54",
        {
          "digits": "9664177354"
        }
      ]
    },
    "masked_spans": {
      "0": [],
      "1": [
        [
          17,
          33
        ],
        [
          46,
          61
        ]
      ],
      "2": [
        [
          15,
          29
        ],
        [
          36,
          71
        ]
      ],
      "3": [],
      "4": [],
      "5": []
    }
  },
  "reply_raw": "Передал оператору (Сорокин Михаил) всю информацию по первому клиенту:\n\n- **Клиент:** Осипова Прасковья Александровна, 8-966-417-73-54\n- **Что случилось:** сначала оформили вызов clm-1 на домашний адрес из карточки (ул. Родниковая, д. 95, кв. 211), затем клиент уточнил, что посылка идёт Мухину Степану на ул. Липовую, 22, кв. 21 (clm-2).\n- **Что сделано:** оформлены вызовы clm-1 и clm-2, отправлено СМС с деталями clm-2.\n- **Запрос:** разобраться с лишним вызовом clm-1 (вероятно, его нужно отменить).\n\nНомер обращения — esc-1. Оператор свяжется с вами при необходимости.",
  "control_reply": "Передал оператору. ✅\n\n**Обращение:** esc-1\n**Оператор:** Соколов Андрей\n**Очередь:** общие вопросы\n\nОператору направлена полная сводка по первому клиенту — Битюковой Зинаиде Николаевне:\n- заявка на забор **clm-1** (г. Казань, ул. Кирова, д. 22, кв. 227, 02.09.2026, 10:00–11:00);\n- заявка на доставку **clm-2** получателю Громовой Марине (г. Казань, ул. Нижняя, д. 10, кв. 151, тот же интервал);\n- отправленное СМС-подтверждение (sms-1).\n\nЕсли понадобится что-то ещё — я рядом.",
  "tool_results": [
    {
      "tool_name": "crm_find_contact",
      "seq": 1,
      "call_ordinal": 0,
      "turn": 1,
      "return_form": "list",
      "text_real": "{\n  \"contacts\": [\n    {\n      \"id\": \"c-caller\",\n      \"last_name\": \"битюкова\",\n      \"first_name\": \"зинаида\",\n      \"middle_name\": \"николаевна\",\n      \"phone\": \"+79261234567\",\n      \"email\": \"bityukova80@gmail.com\",\n      \"birth_date\": \"1975-11-02\",\n      \"address\": {\n        \"city\": \"казань\",\n        \"street\": \"кирова\",\n        \"house\": \"22\",\n        \"flat\": \"227\"\n      }\n    }\n  ]\n}",
      "text_masked": "{\n  \"contacts\": [\n    {\n      \"id\": \"c-caller\",\n      \"last_name\": \"осипова\",\n      \"first_name\": \"прасковья\",\n      \"middle_name\": \"александровна\",\n      \"phone\": \"8-966-417-73-54\",\n      \"email\": \"pmwguojr@example.ru\",\n      \"birth_date\": \"1975-11-11\",\n      \"address\": {\n        \"city\": \"казань\",\n        \"street\": \"родниковая\",\n        \"house\": \"95\",\n        \"flat\": \"211\"\n      }\n    }\n  ]\n}",
      "spans_real": {
        "i1": [
          68,
          76
        ],
        "i2": [
          100,
          107
        ],
        "i3": [
          132,
          142
        ],
        "i4": [
          161,
          173
        ],
        "i5": [
          192,
          213
        ],
        "i6": [
          237,
          247
        ],
        "i7": [
          314,
          320
        ]
      },
      "pieces": [
        [
          68,
          76,
          "осипова",
          "NAME"
        ],
        [
          100,
          107,
          "прасковья",
          "NAME"
        ],
        [
          132,
          142,
          "александровна",
          "NAME"
        ],
        [
          161,
          173,
          "8-966-417-73-54",
          "PHONE"
        ],
        [
          192,
          213,
          "pmwguojr@example.ru",
          "EMAIL"
        ],
        [
          237,
          247,
          "1975-11-11",
          "DOB"
        ],
        [
          286,
          292,
          "казань",
          "LOC"
        ],
        [
          314,
          320,
          "родниковая",
          "LOC"
        ],
        [
          341,
          343,
          "95",
          "LOC"
        ],
        [
          363,
          366,
          "211",
          "LOC"
        ]
      ],
      "forced": false
    },
    {
      "tool_name": "courier_book",
      "seq": 2,
      "call_ordinal": 0,
      "turn": 1,
      "return_form": "nested",
      "text_real": "{\n  \"claim_id\": \"clm-1\",\n  \"status\": \"estimating\",\n  \"contact\": {\n    \"name\": \"Битюкова Зинаида\",\n    \"phone\": \"+79261234567\"\n  },\n  \"address\": \"г. Казань, ул. Кирова, д. 22, кв. 227\"\n}",
      "text_masked": "{\n  \"claim_id\": \"clm-1\",\n  \"status\": \"estimating\",\n  \"contact\": {\n    \"name\": \"Осипова Прасковья\",\n    \"phone\": \"8-966-417-73-54\"\n  },\n  \"address\": \"г. Казань, ул. Родниковая, д. 95, кв. 211\"\n}",
      "spans_real": {
        "i4": [
          112,
          124
        ],
        "i7": [
          160,
          166
        ]
      },
      "pieces": [
        [
          79,
          95,
          "Осипова Прасковья",
          "NAME"
        ],
        [
          112,
          124,
          "8-966-417-73-54",
          "PHONE"
        ],
        [
          145,
          182,
          "г. Казань, ул. Родниковая, д. 95, кв. 211",
          "LOC"
        ]
      ],
      "forced": false
    },
    {
      "tool_name": "courier_book",
      "seq": 3,
      "call_ordinal": 0,
      "turn": 2,
      "return_form": "nested",
      "text_real": "{\n  \"claim_id\": \"clm-2\",\n  \"status\": \"estimating\",\n  \"contact\": {\n    \"name\": \"Громов Марин\",\n    \"phone\": \"+79261234567\"\n  },\n  \"address\": \"г. Казань, ул. Нижняя, д. 10, кв. 151\"\n}",
      "text_masked": "{\n  \"claim_id\": \"clm-2\",\n  \"status\": \"estimating\",\n  \"contact\": {\n    \"name\": \"Мухин Степан\",\n    \"phone\": \"8-966-417-73-54\"\n  },\n  \"address\": \"г. Казань, ул. Липовая, д. 22, кв. 21\"\n}",
      "spans_real": {
        "i4": [
          108,
          120
        ]
      },
      "pieces": [
        [
          79,
          91,
          "Мухин Степан",
          "NAME"
        ],
        [
          108,
          120,
          "8-966-417-73-54",
          "PHONE"
        ],
        [
          141,
          178,
          "г. Казань, ул. Липовая, д. 22, кв. 21",
          "LOC"
        ]
      ],
      "forced": false
    },
    {
      "tool_name": "notify_sms",
      "seq": 4,
      "call_ordinal": 0,
      "turn": 3,
      "return_form": "single",
      "text_real": "{\n  \"id\": \"sms-1\",\n  \"status\": \"queued\",\n  \"number\": \"+79261234567\"\n}",
      "text_masked": "{\n  \"id\": \"sms-1\",\n  \"status\": \"queued\",\n  \"number\": \"8-966-417-73-54\"\n}",
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
          "8-966-417-73-54",
          "PHONE"
        ]
      ],
      "forced": false
    },
    {
      "tool_name": "escalate_to_human",
      "seq": 5,
      "call_ordinal": 0,
      "turn": 5,
      "return_form": "single",
      "text_real": "{\n  \"escalation_id\": \"esc-1\",\n  \"queue\": \"general\",\n  \"status\": \"queued\",\n  \"assignee\": {\n    \"name\": \"Соколов Андрей\",\n    \"phone\": \"+79261234567\"\n  }\n}",
      "text_masked": "{\n  \"escalation_id\": \"esc-1\",\n  \"queue\": \"general\",\n  \"status\": \"queued\",\n  \"assignee\": {\n    \"name\": \"Сорокин Михаил\",\n    \"phone\": \"8-966-417-73-54\"\n  }\n}",
      "spans_real": {
        "i4": [
          134,
          146
        ]
      },
      "pieces": [
        [
          103,
          117,
          "Сорокин Михаил",
          "NAME"
        ],
        [
          134,
          146,
          "8-966-417-73-54",
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
      "substitute": "осипова прасковья",
      "request_index": 1
    },
    {
      "item_id": "i9",
      "msg": 1,
      "result_seq": -1,
      "substitute": "8-966-417-73-54",
      "request_index": 1
    },
    {
      "item_id": "i1",
      "msg": -1,
      "result_seq": 1,
      "substitute": "осипова",
      "request_index": 2
    },
    {
      "item_id": "i2",
      "msg": -1,
      "result_seq": 1,
      "substitute": "прасковья",
      "request_index": 2
    },
    {
      "item_id": "i3",
      "msg": -1,
      "result_seq": 1,
      "substitute": "александровна",
      "request_index": 2
    },
    {
      "item_id": "i4",
      "msg": -1,
      "result_seq": 1,
      "substitute": "8-966-417-73-54",
      "request_index": 2
    },
    {
      "item_id": "i5",
      "msg": -1,
      "result_seq": 1,
      "substitute": "pmwguojr@example.ru",
      "request_index": 2
    },
    {
      "item_id": "i6",
      "msg": -1,
      "result_seq": 1,
      "substitute": "1975-11-11",
      "request_index": 2
    },
    {
      "item_id": "i7",
      "msg": -1,
      "result_seq": 1,
      "substitute": "родниковая",
      "request_index": 2
    },
    {
      "item_id": "i4",
      "msg": -1,
      "result_seq": 2,
      "substitute": "8-966-417-73-54",
      "request_index": 3
    },
    {
      "item_id": "i7",
      "msg": -1,
      "result_seq": 2,
      "substitute": "г. Казань, ул. Родниковая, д. 95, кв. 211",
      "request_index": 3
    },
    {
      "item_id": "i10",
      "msg": 2,
      "result_seq": -1,
      "substitute": "мухина степана",
      "request_index": 4
    },
    {
      "item_id": "i11",
      "msg": 2,
      "result_seq": -1,
      "substitute": "казань улица липовая 22 квартира 21",
      "request_index": 4
    },
    {
      "item_id": "i4",
      "msg": -1,
      "result_seq": 3,
      "substitute": "8-966-417-73-54",
      "request_index": 5
    },
    {
      "item_id": "i4",
      "msg": -1,
      "result_seq": 4,
      "substitute": "8-966-417-73-54",
      "request_index": 7
    },
    {
      "item_id": "i4",
      "msg": -1,
      "result_seq": 5,
      "substitute": "8-966-417-73-54",
      "request_index": 10
    }
  ],
  "turn_replies": [
    "Готово, Зинаида Николаевна! Курьер вызван.\n\n- **Адрес:** г. Казань, ул. Кирова, д. 22, кв. 227\n- **Контакт:** Битюкова Зинаида, +79261234567\n- **Интервал:** сегодня, 02.09.2026, с 09:00 до 10:00 (курьер прибудет к 10 часам)\n- **Заявка:** clm-1\n\nЕсли нужно что-то уточнить или изменить — напишите.",
    "Записал получателя и адрес доставки:\n\n- **Адрес:** г. Казань, ул. Нижняя, д. 10, кв. 151\n- **Получатель:** Громов Марин\n- **Телефон:** +79261234567\n- **Интервал:** сегодня, 02.09.2026, с 09:00 до 10:00 (курьер прибудет к 10 часам)\n- **Заявка:** clm-2\n\nОбратите внимание: ранее я оформил вызов на адрес из вашей карточки (ул. Родниковая, д. 22, кв. 227) — заявка clm-1. Если посылка должна ехать только на казань улицу нижнюю 10, скажите, и я передам оператору, чтобы отменил лишний вызов.",
    "Отправил СМС с деталями заявки на ваш номер +79261234567:\n\n«Заявка clm-2 оформлена. Курьер: г. Казань, ул. Нижняя, д. 10, кв. 151. Получатель: Громов Марин. Интервал: 02.09.2026, 09:00–10:00 (прибудет к 10:00).»\n\nЕсли нужно что-то поправить — напишите.",
    "Курьер к Громов Марин по адресу г. Казань, ул. Нижняя, д. 10, кв. 151 уже оформлен — это заявка **clm-2** на сегодня, 02.09.2026, интервал 09:00–10:00 (прибудет к 10 часам). Дублировать вызов не нужно.\n\nЕсли имелось в виду, что первый вызов (clm-1, ул. Родниковая, д. 22, кв. 227) лишний — скажите, я передам оператору на отмену.",
    "Передал оператору (Соколов Андрей) всю информацию по первому клиенту:\n\n- **Клиент:** Битюкова Зинаида Николаевна, +79261234567\n- **Что случилось:** сначала оформили вызов clm-1 на домашний адрес из карточки (ул. Родниковая, д. 22, кв. 227), затем клиент уточнил, что посылка идёт Громов Марин на казань улица нижняя 10 квартира 151 (clm-2).\n- **Что сделано:** оформлены вызовы clm-1 и clm-2, отправлено СМС с деталями clm-2.\n- **Запрос:** разобраться с лишним вызовом clm-1 (вероятно, его нужно отменить).\n\nНомер обращения — esc-1. Оператор свяжется с вами при необходимости."
  ],
  "call_turns": [
    1,
    1,
    2,
    3,
    5
  ],
  "request_count": 10,
  "stream_mismatch": false,
  "reply_whole": "",
  "turn_residual": 4
}

## Recorded observer hops

[
  {
    "case_id": "memory_anaphora-045",
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
    "produced": "осипова прасковья",
    "reference": "битюкова зинаида",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "memory_anaphora-045",
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
    "produced": "8-966-417-73-54",
    "reference": "8-926-123-45-67",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "memory_anaphora-045",
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
    "produced": "",
    "reference": "",
    "status": "unmasked",
    "verdict": null
  },
  {
    "case_id": "memory_anaphora-045",
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
    "produced": "осипова",
    "reference": "битюкова",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "memory_anaphora-045",
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
    "produced": "1975-11-11",
    "reference": "1975-11-02",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "memory_anaphora-045",
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
    "produced": "мухина степана",
    "reference": "громова марина",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "memory_anaphora-045",
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
    "produced": "казань улица липовая 22 квартира 21",
    "reference": "казань улица нижняя 10 квартира 151",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "memory_anaphora-045",
    "repeat": 0,
    "hop": {
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
    "declared": true,
    "pii_type": "NAME",
    "produced": "Битюкова",
    "reference": "Осипова",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "memory_anaphora-045",
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
    "produced": "8-966-417-73-54",
    "reference": "8-926-123-45-67",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "memory_anaphora-045",
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
    "produced": "+79261234567",
    "reference": "+79664177354",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "memory_anaphora-045",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "template",
      "item_id": "i1",
      "hop_index": 10,
      "turn": 3,
      "tool_name": "notify_sms",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": 3,
      "path": "text",
      "optional": false
    },
    "declared": true,
    "pii_type": "NAME",
    "produced": "Заявка clm-2 оформлена. Курьер: г. Казань, ул. Нижняя, д. 10, кв. 151. Получатель: Громов Марин. Интервал: 02.09.2026, 09:00-10:00 (прибудет к 10:00). Телефон: +79261234567.",
    "reference": "Заявка clm-2 оформлена. Курьер: г. Казань, ул. Липовая, д. 22, кв. 21. Получатель: Мухин Степан. Интервал: 02.09.2026, 09:00-10:00 (прибудет к 10:00). Телефон: 8-966-417-73-54.",
    "status": "unmasked",
    "verdict": null
  },
  {
    "case_id": "memory_anaphora-045",
    "repeat": 0,
    "hop": {
      "kind": "IN",
      "owner": "memory",
      "item_id": "i11",
      "hop_index": 11,
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
    "produced": "казань улица липовая 22 квартира 21",
    "reference": "казань улица нижняя 10 квартира 151",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "memory_anaphora-045",
    "repeat": 0,
    "hop": {
      "kind": "IN",
      "owner": "memory",
      "item_id": "i10",
      "hop_index": 12,
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
    "produced": "мухина степана",
    "reference": "громова марина",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "memory_anaphora-045",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i11",
      "hop_index": 13,
      "turn": 4,
      "tool_name": "courier_book",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": 11,
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
    "case_id": "memory_anaphora-045",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i10",
      "hop_index": 14,
      "turn": 4,
      "tool_name": "courier_book",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": 12,
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
    "case_id": "memory_anaphora-045",
    "repeat": 0,
    "hop": {
      "kind": "IN",
      "owner": "memory",
      "item_id": "i8",
      "hop_index": 15,
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
    "produced": "осипова прасковья",
    "reference": "битюкова зинаида",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "memory_anaphora-045",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "summary",
      "item_id": "i8",
      "hop_index": 16,
      "turn": 5,
      "tool_name": "escalate_to_human",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": 15,
      "path": "summary",
      "optional": false
    },
    "declared": true,
    "pii_type": "NAME",
    "produced": "Битюкова Зинаида",
    "reference": "Осипова Прасковья",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "memory_anaphora-045",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "summary",
      "item_id": "i9",
      "hop_index": 17,
      "turn": 5,
      "tool_name": "escalate_to_human",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": 1,
      "path": "summary",
      "optional": false
    },
    "declared": true,
    "pii_type": "PHONE",
    "produced": "+79261234567 (карточка в CRM найдена). Ситуация: изначально я оформил вызов курьера clm-1 на её адрес из карточки (г. Казань, ул. Кирова, д. 22, кв. 227) на 02.09.2026, 09:00–10:00, так как адрес в первом сообщении не был назван. Затем клиент уточнил, что посылку примет Громов Марин, адрес доставки: г. Казань, ул. Нижняя, д. 10, кв. 151 — оформлен вызов clm-2 на тот же интервал (09:00–10:00), получатель Громов Марин, тел. +79261234567",
    "reference": "8-966-417-73-54 (карточка в CRM найдена). Ситуация: изначально я оформил вызов курьера clm-1 на её адрес из карточки (г. Казань, ул. Родниковая, д. 95, кв. 211) на 02.09.2026, 09:00–10:00, так как адрес в первом сообщении не был назван. Затем клиент уточнил, что посылку примет Мухин Степан, адрес доставки: г. Казань, ул. Липовая, д. 22, кв. 21 — оформлен вызов clm-2 на тот же интервал (09:00–10:00), получатель Мухин Степан, тел. 8-966-417-73-54",
    "status": "observed",
    "verdict": {
      "same": false,
      "differs": [
        "prefix"
      ]
    }
  },
  {
    "case_id": "memory_anaphora-045",
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
    "produced": "Битюкова",
    "reference": "Осипова",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "memory_anaphora-045",
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
      "path": "address.building",
      "optional": false
    },
    "declared": false,
    "pii_type": "LOC",
    "produced": "22",
    "reference": "95",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "memory_anaphora-045",
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
      "path": "address.locality",
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
    "case_id": "memory_anaphora-045",
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
      "path": "address.sflat",
      "optional": false
    },
    "declared": false,
    "pii_type": "LOC",
    "produced": "227",
    "reference": "211",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "memory_anaphora-045",
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
    "produced": "Кирова",
    "reference": "Родниковая",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "memory_anaphora-045",
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
    "produced": "Битюкова Зинаида",
    "reference": "Осипова Прасковья",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "memory_anaphora-045",
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
    "produced": "+79261234567",
    "reference": "+79664177354",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "memory_anaphora-045",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i11",
      "hop_index": -1,
      "turn": 2,
      "tool_name": "courier_book",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": -1,
      "path": "address.building",
      "optional": false
    },
    "declared": false,
    "pii_type": "LOC",
    "produced": "10",
    "reference": "22",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "memory_anaphora-045",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "",
      "hop_index": -1,
      "turn": 2,
      "tool_name": "courier_book",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": -1,
      "path": "address.locality",
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
    "case_id": "memory_anaphora-045",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i7",
      "hop_index": -1,
      "turn": 2,
      "tool_name": "courier_book",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": -1,
      "path": "address.sflat",
      "optional": false
    },
    "declared": false,
    "pii_type": "LOC",
    "produced": "151",
    "reference": "21",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "memory_anaphora-045",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i11",
      "hop_index": -1,
      "turn": 2,
      "tool_name": "courier_book",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": -1,
      "path": "address.street",
      "optional": false
    },
    "declared": false,
    "pii_type": "LOC",
    "produced": "Нижняя",
    "reference": "Липовая",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "memory_anaphora-045",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i10",
      "hop_index": -1,
      "turn": 2,
      "tool_name": "courier_book",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": -1,
      "path": "contact.name",
      "optional": false
    },
    "declared": false,
    "pii_type": "NAME",
    "produced": "Громов Марин",
    "reference": "Мухин Степан",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "memory_anaphora-045",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i4",
      "hop_index": -1,
      "turn": 2,
      "tool_name": "courier_book",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": -1,
      "path": "contact.phone",
      "optional": false
    },
    "declared": false,
    "pii_type": "PHONE",
    "produced": "+79261234567",
    "reference": "+79664177354",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "memory_anaphora-045",
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
    "produced": "Битюкова Зинаида",
    "reference": "Осипова Прасковья",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "memory_anaphora-045",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "answer",
      "item_id": "i2",
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
    "produced": "Зинаида",
    "reference": "Прасковья",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "memory_anaphora-045",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "answer",
      "item_id": "i3",
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
    "produced": "Николаевна",
    "reference": "Александровна",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "memory_anaphora-045",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "answer",
      "item_id": "i4",
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
    "produced": "+79261234567",
    "reference": "8-966-417-73-54",
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
    "case_id": "memory_anaphora-045",
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
    "produced": "+79261234567",
    "reference": "8-966-417-73-54",
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
    "case_id": "memory_anaphora-045",
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
    "produced": "Громов Марин",
    "reference": "Мухину Степану",
    "status": "observed",
    "verdict": {
      "same": false,
      "differs": [
        "gram_case"
      ]
    }
  },
  {
    "case_id": "memory_anaphora-045",
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
    "produced": "казань улица нижняя 10 квартира 15",
    "reference": "ул. Липовую, 22, кв. 2",
    "status": "observed",
    "verdict": {
      "same": false,
      "differs": [
        "case_class",
        "commas",
        "flat_marker",
        "generic",
        "generic_position"
      ]
    }
  }
]
