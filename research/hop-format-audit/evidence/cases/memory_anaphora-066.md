# memory_anaphora-066 | source A | repeat 0

Synthetic benchmark evidence. Verbatim serialized fields; no inferred verdicts.

## Case specification

{
  "base": {
    "id": "memory_anaphora-066",
    "kind": "long_support",
    "register": "voice_itn",
    "provenance": {
      "kind": "template",
      "corpus": "authored",
      "key": "",
      "shape": "",
      "selection": "rare",
      "weight": 1.0,
      "licence": "authored"
    },
    "cluster": "PHONE:9874493399",
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
        "content": "добрый день это антуфьев велимир мой телефон 8-987-449-33-99 а также 10 отделение",
        "source": null,
        "name": ""
      },
      {
        "role": "user",
        "content": "посылку примет заболотный руслан адрес нижний новгород переулок коммунаров 12 квартира 11",
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
          "last_name": "антуфьев",
          "first_name": "велимир",
          "middle_name": "велимирович",
          "phone": "+79874493399",
          "email": "antufev97@gmail.com",
          "birth_date": "1976-04-23",
          "address": {
            "city": "нижний новгород",
            "street": "маросейка",
            "house": "12",
            "flat": "208"
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
        "identity": "p66",
        "value": "антуфьев",
        "canonical": "антуфьев",
        "parts": {
          "surname": "антуфьев",
          "gender": "m"
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
        "identity": "p66",
        "value": "велимир",
        "canonical": "велимир",
        "parts": {
          "given": "велимир",
          "gender": "m"
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
        "identity": "p66",
        "value": "велимирович",
        "canonical": "велимирович",
        "parts": {
          "patronymic": "велимирович",
          "gender": "m"
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
        "identity": "p66",
        "value": "+79874493399",
        "canonical": "+79874493399",
        "parts": {
          "digits": "9874493399"
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
        "identity": "p66",
        "value": "antufev97@gmail.com",
        "canonical": "antufev97@gmail.com",
        "parts": {
          "local": "antufev97",
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
        "identity": "p66",
        "value": "1976-04-23",
        "canonical": "1976-04-23",
        "parts": {
          "iso": "1976-04-23"
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
        "identity": "p66.home",
        "value": "маросейка",
        "canonical": "маросейка",
        "parts": {
          "street": "маросейка",
          "street_type": "переулок",
          "house": "12",
          "flat": "208",
          "city": "нижний новгород"
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
        "identity": "p66",
        "value": "антуфьев велимир",
        "canonical": "антуфьев велимир",
        "parts": {
          "surname": "антуфьев",
          "given": "велимир",
          "gender": "m"
        },
        "where": {
          "kind": "message",
          "msg": 1,
          "start": 16,
          "end": 32,
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
        "identity": "p66",
        "value": "8-987-449-33-99",
        "canonical": "+79874493399",
        "parts": {
          "digits": "9874493399"
        },
        "where": {
          "kind": "message",
          "msg": 1,
          "start": 45,
          "end": 60,
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
        "identity": "p66b",
        "value": "заболотный руслан",
        "canonical": "заболотный руслан",
        "parts": {
          "surname": "заболотный",
          "given": "руслан",
          "gender": "m"
        },
        "where": {
          "kind": "message",
          "msg": 2,
          "start": 15,
          "end": 32,
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
        "identity": "p66b.home",
        "value": "нижний новгород переулок коммунаров 12 квартира 11",
        "canonical": "нижний новгород переулок коммунаров 12 квартира 11",
        "parts": {
          "street": "коммунаров",
          "street_type": "переулок",
          "house": "12",
          "flat": "11",
          "city": "нижний новгород"
        },
        "where": {
          "kind": "message",
          "msg": 2,
          "start": 39,
          "end": 89,
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
        "value": "10 отделение",
        "start": 69,
        "end": 81,
        "msg": 1,
        "family": "room_number",
        "why": "число рядом с кабинетом или отделением — крупнейший источник ложных срабатываний речевого регистра"
      }
    ],
    "expects": {
      "reachable_tools": [
        "crm_find_contact",
        "notify_sms",
        "courier_book"
      ],
      "primary_identity": "p66",
      "must_contain": [
        "антуфьев"
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
        "key": "",
        "start": 12,
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
        "key": "name",
        "start": 16,
        "end": 32,
        "origin": "value:name"
      },
      {
        "msg": 1,
        "key": "",
        "start": 32,
        "end": 33,
        "origin": "literal"
      },
      {
        "msg": 1,
        "key": "",
        "start": 33,
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
        "key": "ph",
        "start": 45,
        "end": 60,
        "origin": "value:ph"
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
        "end": 62,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 1,
        "key": "",
        "start": 62,
        "end": 63,
        "origin": "literal"
      },
      {
        "msg": 1,
        "key": "",
        "start": 63,
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
        "end": 81,
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
        "end": 32,
        "origin": "value:name2"
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
        "end": 38,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 2,
        "key": "",
        "start": 38,
        "end": 39,
        "origin": "literal"
      },
      {
        "msg": 2,
        "key": "addr2",
        "start": 39,
        "end": 89,
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
    "case_id": "memory_anaphora-066",
    "arm": "I",
    "repeat": 0,
    "calls": [
      {
        "name": "crm_find_contact",
        "written": {
          "query": {
            "phone": "+79642011665"
          }
        },
        "restored": {
          "query": {
            "phone": "+79874493399"
          }
        },
        "residual": {},
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "query": {
            "phone": "+79874493399"
          }
        },
        "seq": 1
      },
      {
        "name": "escalate_to_human",
        "written": {
          "queue": "general",
          "summary": "Клиент: Мухин Семён Михайлович, тел. 8-964-201-16-65 (карточка c-caller найдена в CRM; адрес по CRM: Нижний Новгород, Вишнёвая, 44, кв. 165). Клиент оформляет отправку посылки получателю — Гущин Лев, адрес: Нижний Новгород, переулок Грушевый, 57, кв. 64; обратный звонок/контакт курьера — на тот же номер 8-964-201-16-65. Также клиент упоминал «10 отделение» (вероятно, почтовое отделение). Вес по умолчанию 1000 г, индекс подбирается по городу получателя. Что сделано: контакт найден, адрес и контакт получателя собраны. Что не хватает: клиент не назвал интервал времени для вызова курьера — без него заявку не создать; клиент попросил передать всё по этому обращению живому оператору. Курьер не вызван, СМС не отправлялось."
        },
        "restored": {
          "queue": "general",
          "summary": "Клиент: Антуфьев Велимир Велимирович, тел. +79874493399 (карточка c-caller найдена в CRM; адрес по CRM: Нижний Новгород, Вишнёвая, 12, кв. 208). Клиент оформляет отправку посылки получателю — Заболотный Руслан, адрес: Нижний Новгород, переулок Коммунаров, 12, кв. 11; обратный звонок/контакт курьера — на тот же номер +79874493399. Также клиент упоминал «10 отделение» (вероятно, почтовое отделение). Вес по умолчанию 1000 г, индекс подбирается по городу получателя. Что сделано: контакт найден, адрес и контакт получателя собраны. Что не хватает: клиент не назвал интервал времени для вызова курьера — без него заявку не создать; клиент попросил передать всё по этому обращению живому оператору. Курьер не вызван, СМС не отправлялось."
        },
        "residual": {},
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "queue": "general",
          "summary": "Клиент: Антуфьев Велимир Велимирович, тел. +79874493399 (карточка c-caller найдена в CRM; адрес по CRM: Нижний Новгород, Вишнёвая, 12, кв. 208). Клиент оформляет отправку посылки получателю — Заболотный Руслан, адрес: Нижний Новгород, переулок Коммунаров, 12, кв. 11; обратный звонок/контакт курьера — на тот же номер +79874493399. Также клиент упоминал «10 отделение» (вероятно, почтовое отделение). Вес по умолчанию 1000 г, индекс подбирается по городу получателя. Что сделано: контакт найден, адрес и контакт получателя собраны. Что не хватает: клиент не назвал интервал времени для вызова курьера — без него заявку не создать; клиент попросил передать всё по этому обращению живому оператору. Курьер не вызван, СМС не отправлялось."
        },
        "seq": 2
      }
    ],
    "state": [
      {
        "fields": {
          "queue": "general",
          "summary": "Клиент: Антуфьев Велимир Велимирович, тел. +79874493399 (карточка c-caller найдена в CRM; адрес по CRM: Нижний Новгород, Вишнёвая, 12, кв. 208). Клиент оформляет отправку посылки получателю — Заболотный Руслан, адрес: Нижний Новгород, переулок Коммунаров, 12, кв. 11; обратный звонок/контакт курьера — на тот же номер +79874493399. Также клиент упоминал «10 отделение» (вероятно, почтовое отделение). Вес по умолчанию 1000 г, индекс подбирается по городу получателя. Что сделано: контакт найден, адрес и контакт получателя собраны. Что не хватает: клиент не назвал интервал времени для вызова курьера — без него заявку не создать; клиент попросил передать всё по этому обращению живому оператору. Курьер не вызван, СМС не отправлялось."
        },
        "id": "esc-1",
        "seq": 2,
        "table": "escalations",
        "tool": "escalate_to_human"
      }
    ],
    "reply": "Передал обращение живому оператору — Соколов Андрей (тел. +79261234567), номер обращения esc-1, очередь «general». Он свяжется с вами по номеру +79874493399.\n\nСводка по обращению:\n- Клиент: Антуфьев Велимир Велимирович, +79874493399;\n- Отправление посылки получателю: Заболотный Руслан, нижний новгород переулок коммунаров 12 квартира 11;\n- Контакт для курьера: тот же номер +79874493399;\n- Не хватает интервала времени для вызова курьера — оператор уточнит его у вас (либо подскажите его здесь, и я сразу оформлю заявку).",
    "termination": "done",
    "cost_usd": 0.004746,
    "substitutes": {
      "i1": [
        "мухин",
        {
          "surname": "мухин"
        }
      ],
      "i10": [
        "гущин лев",
        {
          "given": "лев",
          "surname": "гущин"
        }
      ],
      "i11": [
        "нижний новгород переулок грушевый 57 квартира 64",
        {
          "flat": "64",
          "house": "57",
          "street": "грушевый нижний новгород"
        }
      ],
      "i2": [
        "семён",
        {
          "given": "семён"
        }
      ],
      "i3": [
        "михайлович",
        {
          "patronymic": "михайлович"
        }
      ],
      "i4": [
        "8-964-201-16-65",
        {
          "digits": "9642011665"
        }
      ],
      "i5": [
        "kocepsff@example.ru",
        {
          "domain": "example.ru",
          "local": "kocepsff"
        }
      ],
      "i6": [
        "1976-03-16",
        {
          "iso": "1976-03-16"
        }
      ],
      "i7": [
        "вишнёвая",
        {
          "street": "вишневая"
        }
      ],
      "i8": [
        "мухин семён",
        {
          "given": "семён",
          "surname": "мухин"
        }
      ],
      "i9": [
        "8-964-201-16-65",
        {
          "digits": "9642011665"
        }
      ]
    },
    "masked_spans": {
      "0": [],
      "1": [
        [
          16,
          32
        ],
        [
          45,
          60
        ]
      ],
      "2": [
        [
          15,
          32
        ],
        [
          39,
          89
        ]
      ],
      "3": [],
      "4": [],
      "5": []
    }
  },
  "reply_raw": "Передал обращение живому оператору — Фомин Аркадий (тел. +79214484396), номер обращения esc-1, очередь «general». Он свяжется с вами по номеру 8-964-201-16-65.\n\nСводка по обращению:\n- Клиент: Мухин Семён Михайлович, 8-964-201-16-65;\n- Отправление посылки получателю: Гущин Лев, Нижний Новгород, переулок Грушевый, 57, кв. 64;\n- Контакт для курьера: тот же номер 8-964-201-16-65;\n- Не хватает интервала времени для вызова курьера — оператор уточнит его у вас (либо подскажите его здесь, и я сразу оформлю заявку).",
  "control_reply": "Передал всё оператору. Кратко:\n\n- **Клиент:** Антуфьев Велимир Велимирович, +7 987 449-33-99, Нижний Новгород, ул. Маросейка, д. 12, кв. 208.\n- **Получатель:** Заболотный Руслан, Нижний Новгород, переулок Коммунаров, д. 12, кв. 11.\n- **Сделано:** карточка найдена в CRM, отправлено SMS с деталями на ваш номер.\n- **Осталось выяснить:** удобный интервал времени для курьера (поэтому заявка пока не создана) и что означает «10 отделение».\n\nОператор **Соколов Андрей**, телефон +7 926 123-45-67, свяжется с вами. Номер обращения — esc-1.",
  "tool_results": [
    {
      "tool_name": "crm_find_contact",
      "seq": 1,
      "call_ordinal": 0,
      "turn": 1,
      "return_form": "list",
      "text_real": "{\n  \"contacts\": [\n    {\n      \"id\": \"c-caller\",\n      \"last_name\": \"антуфьев\",\n      \"first_name\": \"велимир\",\n      \"middle_name\": \"велимирович\",\n      \"phone\": \"+79874493399\",\n      \"email\": \"antufev97@gmail.com\",\n      \"birth_date\": \"1976-04-23\",\n      \"address\": {\n        \"city\": \"нижний новгород\",\n        \"street\": \"маросейка\",\n        \"house\": \"12\",\n        \"flat\": \"208\"\n      }\n    }\n  ]\n}",
      "text_masked": "{\n  \"contacts\": [\n    {\n      \"id\": \"c-caller\",\n      \"last_name\": \"мухин\",\n      \"first_name\": \"семён\",\n      \"middle_name\": \"михайлович\",\n      \"phone\": \"8-964-201-16-65\",\n      \"email\": \"kocepsff@example.ru\",\n      \"birth_date\": \"1976-03-16\",\n      \"address\": {\n        \"city\": \"нижний новгород\",\n        \"street\": \"вишнёвая\",\n        \"house\": \"44\",\n        \"flat\": \"165\"\n      }\n    }\n  ]\n}",
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
          143
        ],
        "i4": [
          162,
          174
        ],
        "i5": [
          193,
          212
        ],
        "i6": [
          236,
          246
        ],
        "i7": [
          322,
          331
        ]
      },
      "pieces": [
        [
          68,
          76,
          "мухин",
          "NAME"
        ],
        [
          100,
          107,
          "семён",
          "NAME"
        ],
        [
          132,
          143,
          "михайлович",
          "NAME"
        ],
        [
          162,
          174,
          "8-964-201-16-65",
          "PHONE"
        ],
        [
          193,
          212,
          "kocepsff@example.ru",
          "EMAIL"
        ],
        [
          236,
          246,
          "1976-03-16",
          "DOB"
        ],
        [
          285,
          300,
          "нижний новгород",
          "LOC"
        ],
        [
          322,
          331,
          "вишнёвая",
          "LOC"
        ],
        [
          352,
          354,
          "44",
          "LOC"
        ],
        [
          374,
          377,
          "165",
          "LOC"
        ]
      ],
      "forced": false
    },
    {
      "tool_name": "escalate_to_human",
      "seq": 2,
      "call_ordinal": 0,
      "turn": 5,
      "return_form": "single",
      "text_real": "{\n  \"escalation_id\": \"esc-1\",\n  \"queue\": \"general\",\n  \"status\": \"queued\",\n  \"assignee\": {\n    \"name\": \"Соколов Андрей\",\n    \"phone\": \"+79261234567\"\n  }\n}",
      "text_masked": "{\n  \"escalation_id\": \"esc-1\",\n  \"queue\": \"general\",\n  \"status\": \"queued\",\n  \"assignee\": {\n    \"name\": \"Фомин Аркадий\",\n    \"phone\": \"+79214484396\"\n  }\n}",
      "spans_real": {},
      "pieces": [
        [
          103,
          117,
          "Фомин Аркадий",
          "NAME"
        ],
        [
          134,
          146,
          "+79214484396",
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
      "substitute": "мухин семён",
      "request_index": 1
    },
    {
      "item_id": "i9",
      "msg": 1,
      "result_seq": -1,
      "substitute": "8-964-201-16-65",
      "request_index": 1
    },
    {
      "item_id": "i1",
      "msg": -1,
      "result_seq": 1,
      "substitute": "мухин",
      "request_index": 2
    },
    {
      "item_id": "i2",
      "msg": -1,
      "result_seq": 1,
      "substitute": "семён",
      "request_index": 2
    },
    {
      "item_id": "i3",
      "msg": -1,
      "result_seq": 1,
      "substitute": "михайлович",
      "request_index": 2
    },
    {
      "item_id": "i4",
      "msg": -1,
      "result_seq": 1,
      "substitute": "8-964-201-16-65",
      "request_index": 2
    },
    {
      "item_id": "i5",
      "msg": -1,
      "result_seq": 1,
      "substitute": "kocepsff@example.ru",
      "request_index": 2
    },
    {
      "item_id": "i6",
      "msg": -1,
      "result_seq": 1,
      "substitute": "1976-03-16",
      "request_index": 2
    },
    {
      "item_id": "i7",
      "msg": -1,
      "result_seq": 1,
      "substitute": "вишнёвая",
      "request_index": 2
    },
    {
      "item_id": "i10",
      "msg": 2,
      "result_seq": -1,
      "substitute": "гущин лев",
      "request_index": 3
    },
    {
      "item_id": "i11",
      "msg": 2,
      "result_seq": -1,
      "substitute": "нижний новгород переулок грушевый 57 квартира 64",
      "request_index": 3
    }
  ],
  "turn_replies": [
    "Здравствуйте, Велимир Велимирович! Нашёл вашу карточку в CRM — телефон +79874493399 подтверждён.\n\nПодскажите, пожалуйста, что нужно оформить: вызов курьера? Если да, уточните:\n1. Точный адрес (населённый пункт, улица, дом) — по «10 отделению» мне пока не хватает улицы и номера дома;\n2. Удобный интервал времени для приезда курьера.",
    "Принял: получатель — Заболотный Руслан, адрес: нижний новгород переулок коммунаров 12 квартира 11.\n\nОсталось два момента для вызова курьера:\n1. В какой интервал времени курьеру приехать (дата и время, например 2026-09-02 с 14:00 до 16:00)?\n2. На какой телефон звонить получателю — на ваш +79874493399 или на другой номер?",
    "Понял: звонок курьера — на ваш номер +79874493399, и подтверждение продублирую вам СМС на него же.\n\nОстался только интервал времени. В какой день и в какие часы курьеру приехать по адресу: нижний новгород переулок коммунаров 12 квартира 11? Например: 2026-09-02, с 14:00 до 16:00.",
    "Адрес понятен: нижний новгород переулок коммунаров 12 квартира 11, получатель Заболотный Руслан, звонить на +79874493399.\n\nЧтобы вызвать курьера, мне обязательно нужен интервал времени — без него заявку не создать. Скажите, пожалуйста, на когда вызвать курьера: дата и промежуток, например «сегодня, с 14:00 до 16:00» или «завтра, с 10:00 до 12:00».",
    "Передал обращение живому оператору — Соколов Андрей (тел. +79261234567), номер обращения esc-1, очередь «general». Он свяжется с вами по номеру +79874493399.\n\nСводка по обращению:\n- Клиент: Антуфьев Велимир Велимирович, +79874493399;\n- Отправление посылки получателю: Заболотный Руслан, нижний новгород переулок коммунаров 12 квартира 11;\n- Контакт для курьера: тот же номер +79874493399;\n- Не хватает интервала времени для вызова курьера — оператор уточнит его у вас (либо подскажите его здесь, и я сразу оформлю заявку)."
  ],
  "call_turns": [
    1,
    5
  ],
  "request_count": 7,
  "stream_mismatch": false,
  "reply_whole": "",
  "turn_residual": 4
}

## Recorded observer hops

[
  {
    "case_id": "memory_anaphora-066",
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
    "produced": "мухин семён",
    "reference": "антуфьев велимир",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "memory_anaphora-066",
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
    "produced": "8-964-201-16-65",
    "reference": "8-987-449-33-99",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "memory_anaphora-066",
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
    "produced": "+79874493399",
    "reference": "+79642011665",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "memory_anaphora-066",
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
    "produced": "мухин",
    "reference": "антуфьев",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "memory_anaphora-066",
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
    "produced": "1976-03-16",
    "reference": "1976-04-23",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "memory_anaphora-066",
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
    "produced": "гущин лев",
    "reference": "заболотный руслан",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "memory_anaphora-066",
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
    "produced": "нижний новгород переулок грушевый 57 квартира 64",
    "reference": "нижний новгород переулок коммунаров 12 квартира 11",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "memory_anaphora-066",
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
    "produced": "Антуфьев",
    "reference": "Мухин",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "memory_anaphora-066",
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
    "produced": "8-964-201-16-65",
    "reference": "8-987-449-33-99",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "memory_anaphora-066",
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
    "case_id": "memory_anaphora-066",
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
    "produced": "",
    "reference": "",
    "status": "absent",
    "verdict": null
  },
  {
    "case_id": "memory_anaphora-066",
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
    "produced": "нижний новгород переулок грушевый 57 квартира 64",
    "reference": "нижний новгород переулок коммунаров 12 квартира 11",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "memory_anaphora-066",
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
    "produced": "гущин лев",
    "reference": "заболотный руслан",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "memory_anaphora-066",
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
    "case_id": "memory_anaphora-066",
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
    "case_id": "memory_anaphora-066",
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
    "produced": "мухин семён",
    "reference": "антуфьев велимир",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "memory_anaphora-066",
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
    "produced": "Антуфьев Велимир",
    "reference": "Мухин Семён",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "memory_anaphora-066",
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
    "produced": "+79874493399 (карточка c-caller найдена в CRM; адрес по CRM: Нижний Новгород, Вишнёвая, 12, кв. 208). Клиент оформляет отправку посылки получателю — Заболотный Руслан, адрес: Нижний Новгород, переулок Коммунаров, 12, кв. 11; обратный звонок/контакт курьера — на тот же номер +79874493399",
    "reference": "8-964-201-16-65 (карточка c-caller найдена в CRM; адрес по CRM: Нижний Новгород, Вишнёвая, 44, кв. 165). Клиент оформляет отправку посылки получателю — Гущин Лев, адрес: Нижний Новгород, переулок Грушевый, 57, кв. 64; обратный звонок/контакт курьера — на тот же номер 8-964-201-16-65",
    "status": "observed",
    "verdict": {
      "same": false,
      "differs": [
        "prefix"
      ]
    }
  },
  {
    "case_id": "memory_anaphora-066",
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
    "produced": "+79874493399",
    "reference": "8-964-201-16-65",
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
    "case_id": "memory_anaphora-066",
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
    "produced": "+79874493399",
    "reference": "8-964-201-16-65",
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
    "case_id": "memory_anaphora-066",
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
    "produced": "Велимир Велимир",
    "reference": "Семён",
    "status": "observed",
    "verdict": {
      "same": false,
      "differs": [
        "parts"
      ]
    }
  },
  {
    "case_id": "memory_anaphora-066",
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
    "produced": "Велимирович",
    "reference": "Михайлович",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "memory_anaphora-066",
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
    "produced": "Антуфьев Велимир",
    "reference": "Мухин Семён",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "memory_anaphora-066",
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
    "produced": "+79874493399",
    "reference": "8-964-201-16-65",
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
    "case_id": "memory_anaphora-066",
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
    "produced": "+79874493399",
    "reference": "8-964-201-16-65",
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
    "case_id": "memory_anaphora-066",
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
    "produced": "Заболотный Руслан",
    "reference": "Гущин Лев",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "memory_anaphora-066",
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
    "produced": "Заболотный Руслан, нижний",
    "reference": "Гущин Лев, Нижний",
    "status": "observed",
    "verdict": {
      "same": false,
      "differs": [
        "case_class"
      ]
    }
  },
  {
    "case_id": "memory_anaphora-066",
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
    "produced": "новгород",
    "reference": "Новгород",
    "status": "observed",
    "verdict": {
      "same": false,
      "differs": [
        "case_class"
      ]
    }
  },
  {
    "case_id": "memory_anaphora-066",
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
    "produced": "коммунаров 12 квартира 11",
    "reference": "Грушевый, 57, кв. 64",
    "status": "observed",
    "verdict": {
      "same": false,
      "differs": [
        "case_class",
        "commas",
        "flat_marker"
      ]
    }
  },
  {
    "case_id": "memory_anaphora-066",
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
    "produced": "+79874493399",
    "reference": "8-964-201-16-65",
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
    "case_id": "memory_anaphora-066",
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
    "produced": "+79874493399",
    "reference": "8-964-201-16-65",
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
