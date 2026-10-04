# memory_anaphora-012 | source A | repeat 0

Synthetic benchmark evidence. Verbatim serialized fields; no inferred verdicts.

## Case specification

{
  "base": {
    "id": "memory_anaphora-012",
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
    "cluster": "PHONE:9273011996",
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
        "content": "добрый день это заболотный руслан мой телефон 89273011996 и ещё 6 отделение",
        "source": null,
        "name": ""
      },
      {
        "role": "user",
        "content": "посылку примет тарасова алла адрес краснодар бульвар светлый 20 квартира 31",
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
          "last_name": "заболотный",
          "first_name": "руслан",
          "middle_name": "фёдорович",
          "phone": "+79273011996",
          "email": "zabolotnyy81@bk.ru",
          "birth_date": "1969-05-23",
          "address": {
            "city": "краснодар",
            "street": "октябрьский",
            "house": "67",
            "flat": "207"
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
        "identity": "p12",
        "value": "заболотный",
        "canonical": "заболотный",
        "parts": {
          "surname": "заболотный",
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
        "identity": "p12",
        "value": "руслан",
        "canonical": "руслан",
        "parts": {
          "given": "руслан",
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
        "identity": "p12",
        "value": "фёдорович",
        "canonical": "фёдорович",
        "parts": {
          "patronymic": "фёдорович",
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
        "identity": "p12",
        "value": "+79273011996",
        "canonical": "+79273011996",
        "parts": {
          "digits": "9273011996"
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
        "identity": "p12",
        "value": "zabolotnyy81@bk.ru",
        "canonical": "zabolotnyy81@bk.ru",
        "parts": {
          "local": "zabolotnyy81",
          "domain": "bk.ru"
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
        "identity": "p12",
        "value": "1969-05-23",
        "canonical": "1969-05-23",
        "parts": {
          "iso": "1969-05-23"
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
        "identity": "p12.home",
        "value": "октябрьский",
        "canonical": "октябрьский",
        "parts": {
          "street": "октябрьский",
          "street_type": "бульвар",
          "house": "67",
          "flat": "207",
          "city": "краснодар"
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
        "identity": "p12",
        "value": "заболотный руслан",
        "canonical": "заболотный руслан",
        "parts": {
          "surname": "заболотный",
          "given": "руслан",
          "gender": "m"
        },
        "where": {
          "kind": "message",
          "msg": 1,
          "start": 16,
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
        "identity": "p12",
        "value": "89273011996",
        "canonical": "+79273011996",
        "parts": {
          "digits": "9273011996"
        },
        "where": {
          "kind": "message",
          "msg": 1,
          "start": 46,
          "end": 57,
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
        "identity": "p12b",
        "value": "тарасова алла",
        "canonical": "тарасова алла",
        "parts": {
          "surname": "тарасова",
          "given": "алла",
          "gender": "f"
        },
        "where": {
          "kind": "message",
          "msg": 2,
          "start": 15,
          "end": 28,
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
        "identity": "p12b.home",
        "value": "краснодар бульвар светлый 20 квартира 31",
        "canonical": "краснодар бульвар светлый 20 квартира 31",
        "parts": {
          "street": "светлый",
          "street_type": "бульвар",
          "house": "20",
          "flat": "31",
          "city": "краснодар"
        },
        "where": {
          "kind": "message",
          "msg": 2,
          "start": 35,
          "end": 75,
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
        "value": "6 отделение",
        "start": 64,
        "end": 75,
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
      "primary_identity": "p12",
      "must_contain": [
        "заболотный"
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
        "end": 57,
        "origin": "value:ph"
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
        "end": 59,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 1,
        "key": "",
        "start": 59,
        "end": 60,
        "origin": "literal"
      },
      {
        "msg": 1,
        "key": "",
        "start": 60,
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
        "end": 75,
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
        "end": 28,
        "origin": "value:name2"
      },
      {
        "msg": 2,
        "key": "",
        "start": 28,
        "end": 29,
        "origin": "literal"
      },
      {
        "msg": 2,
        "key": "",
        "start": 29,
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
        "key": "addr2",
        "start": 35,
        "end": 75,
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
    "case_id": "memory_anaphora-012",
    "arm": "I",
    "repeat": 0,
    "calls": [
      {
        "name": "crm_find_contact",
        "written": {
          "query": {
            "phone": "+79289855496"
          }
        },
        "restored": {
          "query": {
            "phone": "+79273011996"
          }
        },
        "residual": {},
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "query": {
            "phone": "+79273011996"
          }
        },
        "seq": 1
      },
      {
        "name": "courier_book",
        "written": {
          "address": {
            "building": "11",
            "locality": "Краснодар",
            "sflat": "46",
            "street": "Тополиный бульвар"
          },
          "contact": {
            "name": "Чижов Глеб",
            "phone": "+79289855496"
          },
          "interval": {
            "from": "2026-09-02T15:00:00+03:00",
            "to": "2026-09-02T18:00:00+03:00"
          }
        },
        "restored": {
          "address": {
            "building": "20",
            "locality": "Краснодар",
            "sflat": "31",
            "street": "Светлый"
          },
          "contact": {
            "name": "Тарасов Алл",
            "phone": "+79273011996"
          },
          "interval": {
            "from": "2026-09-02T15:00:00+03:00",
            "to": "2026-09-02T18:00:00+03:00"
          }
        },
        "residual": {},
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "address": {
            "building": "20",
            "locality": "краснодар",
            "porch": "",
            "sflat": "31",
            "street": "светлый"
          },
          "contact": {
            "name": "Тарасов Алл",
            "phone": "+79273011996"
          },
          "interval": {
            "from": "2026-09-02T15:00:00+03:00",
            "to": "2026-09-02T18:00:00+03:00"
          }
        },
        "seq": 2
      },
      {
        "name": "notify_sms",
        "written": {
          "number": "+79289855496",
          "sign": "Dostavka",
          "text": "Курьер вызван. Заявка clm-1: Краснодар, Тополиный бульвар, 11, кв. 46, получатель Чижов Глеб. Интервал: 02.09.2026 с 15:00 до 18:00. Связь: +7 928 985-54-96."
        },
        "restored": {
          "number": "+79273011996",
          "sign": "Dostavka",
          "text": "Курьер вызван. Заявка clm-1: Краснодар, Светлый, 20, кв. 31, получатель Тарасов Алл. Интервал: 02.09.2026 с 15:00 до 18:00. Связь: +7 927 301-19-96."
        },
        "residual": {},
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "number": "+79273011996",
          "sign": "Dostavka",
          "text": "Курьер вызван. Заявка clm-1: Краснодар, Светлый, 20, кв. 31, получатель Тарасов Алл. Интервал: 02.09.2026 с 15:00 до 18:00. Связь: +7 927 301-19-96."
        },
        "seq": 3
      },
      {
        "name": "escalate_to_human",
        "written": {
          "queue": "general",
          "summary": "Клиент: Мухин Савва Игоревич, тел. +7 928 985-54-96 (карточка c-caller; адрес по CRM: Краснодар, Родниковая 93, кв. 125). Обратился за вызовом курьера для доставки посылки. Получатель: Чижов Глеб, адрес доставки: Краснодар, Тополиный бульвар, 11, кв. 46. Интервал: 02.09.2026, 15:00–18:00 (+03:00). Сделано: создана заявка на курьера clm-1 (статус estimating), на телефон клиента отправлено СМС-подтверждение (sms-1). Дополнительно: клиент упомянул «6 отделение», смысл не уточнён — просил передать всё по этому (первому) клиенту оператору."
        },
        "restored": {
          "queue": "general",
          "summary": "Клиент: Заболотный Руслан Фёдорович, тел. +7 927 301-19-96 (карточка c-caller; адрес по CRM: Краснодар, Родниковая 67, кв. 207). Обратился за вызовом курьера для доставки посылки. Получатель: Тарасов Алл, адрес доставки: Краснодар, Светлый, 20, кв. 31. Интервал: 02.09.2026, 15:00–18:00 (+03:00). Сделано: создана заявка на курьера clm-1 (статус estimating), на телефон клиента отправлено СМС-подтверждение (sms-1). Дополнительно: клиент упомянул «6 отделение», смысл не уточнён — просил передать всё по этому (первому) клиенту оператору."
        },
        "residual": {
          "summary": [
            "Фёдорович"
          ]
        },
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "queue": "general",
          "summary": "Клиент: Заболотный Руслан Фёдорович, тел. +7 927 301-19-96 (карточка c-caller; адрес по CRM: Краснодар, Родниковая 67, кв. 207). Обратился за вызовом курьера для доставки посылки. Получатель: Тарасов Алл, адрес доставки: Краснодар, Светлый, 20, кв. 31. Интервал: 02.09.2026, 15:00–18:00 (+03:00). Сделано: создана заявка на курьера clm-1 (статус estimating), на телефон клиента отправлено СМС-подтверждение (sms-1). Дополнительно: клиент упомянул «6 отделение», смысл не уточнён — просил передать всё по этому (первому) клиенту оператору."
        },
        "seq": 4
      }
    ],
    "state": [
      {
        "fields": {
          "address": {
            "building": "20",
            "locality": "краснодар",
            "porch": "",
            "sflat": "31",
            "street": "светлый"
          },
          "contact": {
            "name": "Тарасов Алл",
            "phone": "+79273011996"
          },
          "interval": {
            "from": "2026-09-02T15:00:00+03:00",
            "to": "2026-09-02T18:00:00+03:00"
          }
        },
        "id": "clm-1",
        "seq": 2,
        "table": "claims",
        "tool": "courier_book"
      },
      {
        "fields": {
          "number": "+79273011996",
          "sign": "Dostavka",
          "text": "Курьер вызван. Заявка clm-1: Краснодар, Светлый, 20, кв. 31, получатель Тарасов Алл. Интервал: 02.09.2026 с 15:00 до 18:00. Связь: +7 927 301-19-96."
        },
        "id": "sms-1",
        "seq": 3,
        "table": "sms",
        "tool": "notify_sms"
      },
      {
        "fields": {
          "queue": "general",
          "summary": "Клиент: Заболотный Руслан Фёдорович, тел. +7 927 301-19-96 (карточка c-caller; адрес по CRM: Краснодар, Родниковая 67, кв. 207). Обратился за вызовом курьера для доставки посылки. Получатель: Тарасов Алл, адрес доставки: Краснодар, Светлый, 20, кв. 31. Интервал: 02.09.2026, 15:00–18:00 (+03:00). Сделано: создана заявка на курьера clm-1 (статус estimating), на телефон клиента отправлено СМС-подтверждение (sms-1). Дополнительно: клиент упомянул «6 отделение», смысл не уточнён — просил передать всё по этому (первому) клиенту оператору."
        },
        "id": "esc-1",
        "seq": 4,
        "table": "escalations",
        "tool": "escalate_to_human"
      }
    ],
    "reply": "Передал оператору 📋\n\n- Очередь: general\n- Оператор: Соколов Андрей (+79261234567)\n- Номер обращения: esc-1\n\nВ сводку включил всё по первому клиенту: Заболотный Руслан Фёдорович, 89273011996; заявку на курьера clm-1 (г. Краснодар, ул. Светлый, д. 20, кв. 31, получатель Тарасов Алл, интервал 02.09.2026 с 15:00 до 18:00); отправленное СМС sms-1; и нерешённый вопрос с «6 отделением».",
    "termination": "done",
    "cost_usd": 0.010475,
    "substitutes": {
      "i1": [
        "мухин",
        {
          "surname": "мухин"
        }
      ],
      "i10": [
        "чижова глеба",
        {
          "given": "глеба",
          "surname": "чижова"
        }
      ],
      "i11": [
        "краснодар бульвар тополиный 11 квартира 46",
        {
          "flat": "46",
          "house": "11",
          "street": "краснодар тополиный"
        }
      ],
      "i2": [
        "савва",
        {
          "given": "савва"
        }
      ],
      "i3": [
        "игоревич",
        {
          "patronymic": "игоревич"
        }
      ],
      "i4": [
        "89289855496",
        {
          "digits": "9289855496"
        }
      ],
      "i5": [
        "bvatkjyl@example.ru",
        {
          "domain": "example.ru",
          "local": "bvatkjyl"
        }
      ],
      "i6": [
        "1969-08-26",
        {
          "iso": "1969-08-26"
        }
      ],
      "i7": [
        "родниковая",
        {
          "street": "родниковая"
        }
      ],
      "i8": [
        "мухин савва",
        {
          "given": "савва",
          "surname": "мухин"
        }
      ],
      "i9": [
        "89289855496",
        {
          "digits": "9289855496"
        }
      ]
    },
    "masked_spans": {
      "0": [],
      "1": [
        [
          16,
          33
        ],
        [
          46,
          57
        ]
      ],
      "2": [
        [
          15,
          28
        ],
        [
          35,
          75
        ]
      ],
      "3": [],
      "4": [],
      "5": []
    }
  },
  "reply_raw": "Передал оператору 📋\n\n- Очередь: general\n- Оператор: Котов Ярослав (+7 975 494-79-35)\n- Номер обращения: esc-1\n\nВ сводку включил всё по первому клиенту: Мухин Савва Игоревич, +7 928 985-54-96; заявку на курьера clm-1 (Краснодар, Тополиный бульвар, 11, кв. 46, получатель Чижов Глеб, интервал 02.09.2026 с 15:00 до 18:00); отправленное СМС sms-1; и нерешённый вопрос с «6 отделением».",
  "control_reply": "Передал обращение живому оператору.\n\nКратко, что передано:\n- Клиент: Заболотный Руслан Фёдорович, +79273011996 (карточка в CRM: Краснодар, Октябрьский, 67, кв. 207).\n- Задача: отправить посылку получателю Тарасовой Алле, Краснодар, бульвар Светлый, 20, кв. 31; курьера — на адрес получателя.\n- Уже сделано: SMS с деталями заказа на ваш номер +79273011996.\n- Не хватает для вызова: время (дата и интервал) и телефон для связи курьера; также осталось невыясненным, что означает «6 отделение».\n\nОператор: Соколов Андрей, тел. +79261234567 (очередь general). Номер обращения — esc-1.\n\nЕсли сможете подсказать удобное время курьера и телефон для связи, я тут же оформлю вызов.",
  "tool_results": [
    {
      "tool_name": "crm_find_contact",
      "seq": 1,
      "call_ordinal": 0,
      "turn": 1,
      "return_form": "list",
      "text_real": "{\n  \"contacts\": [\n    {\n      \"id\": \"c-caller\",\n      \"last_name\": \"заболотный\",\n      \"first_name\": \"руслан\",\n      \"middle_name\": \"фёдорович\",\n      \"phone\": \"+79273011996\",\n      \"email\": \"zabolotnyy81@bk.ru\",\n      \"birth_date\": \"1969-05-23\",\n      \"address\": {\n        \"city\": \"краснодар\",\n        \"street\": \"октябрьский\",\n        \"house\": \"67\",\n        \"flat\": \"207\"\n      }\n    }\n  ]\n}",
      "text_masked": "{\n  \"contacts\": [\n    {\n      \"id\": \"c-caller\",\n      \"last_name\": \"мухин\",\n      \"first_name\": \"савва\",\n      \"middle_name\": \"игоревич\",\n      \"phone\": \"89289855496\",\n      \"email\": \"bvatkjyl@example.ru\",\n      \"birth_date\": \"1969-08-26\",\n      \"address\": {\n        \"city\": \"краснодар\",\n        \"street\": \"родниковая\",\n        \"house\": \"93\",\n        \"flat\": \"125\"\n      }\n    }\n  ]\n}",
      "spans_real": {
        "i1": [
          68,
          78
        ],
        "i2": [
          102,
          108
        ],
        "i3": [
          133,
          142
        ],
        "i4": [
          161,
          173
        ],
        "i5": [
          192,
          210
        ],
        "i6": [
          234,
          244
        ],
        "i7": [
          314,
          325
        ]
      },
      "pieces": [
        [
          68,
          78,
          "мухин",
          "NAME"
        ],
        [
          102,
          108,
          "савва",
          "NAME"
        ],
        [
          133,
          142,
          "игоревич",
          "NAME"
        ],
        [
          161,
          173,
          "89289855496",
          "PHONE"
        ],
        [
          192,
          210,
          "bvatkjyl@example.ru",
          "EMAIL"
        ],
        [
          234,
          244,
          "1969-08-26",
          "DOB"
        ],
        [
          283,
          292,
          "краснодар",
          "LOC"
        ],
        [
          314,
          325,
          "родниковая",
          "LOC"
        ],
        [
          346,
          348,
          "93",
          "LOC"
        ],
        [
          368,
          371,
          "125",
          "LOC"
        ]
      ],
      "forced": false
    },
    {
      "tool_name": "courier_book",
      "seq": 2,
      "call_ordinal": 0,
      "turn": 4,
      "return_form": "nested",
      "text_real": "{\n  \"claim_id\": \"clm-1\",\n  \"status\": \"estimating\",\n  \"contact\": {\n    \"name\": \"Тарасов Алл\",\n    \"phone\": \"+79273011996\"\n  },\n  \"address\": \"г. Краснодар, ул. Светлый, д. 20, кв. 31\"\n}",
      "text_masked": "{\n  \"claim_id\": \"clm-1\",\n  \"status\": \"estimating\",\n  \"contact\": {\n    \"name\": \"Чижов Глеб\",\n    \"phone\": \"89289855496\"\n  },\n  \"address\": \"г. Краснодар, ул. Тополиный, д. 11, кв. 46\"\n}",
      "spans_real": {
        "i4": [
          107,
          119
        ]
      },
      "pieces": [
        [
          79,
          90,
          "Чижов Глеб",
          "NAME"
        ],
        [
          107,
          119,
          "89289855496",
          "PHONE"
        ],
        [
          140,
          180,
          "г. Краснодар, ул. Тополиный, д. 11, кв. 46",
          "LOC"
        ]
      ],
      "forced": false
    },
    {
      "tool_name": "notify_sms",
      "seq": 3,
      "call_ordinal": 0,
      "turn": 4,
      "return_form": "single",
      "text_real": "{\n  \"id\": \"sms-1\",\n  \"status\": \"queued\",\n  \"number\": \"+79273011996\"\n}",
      "text_masked": "{\n  \"id\": \"sms-1\",\n  \"status\": \"queued\",\n  \"number\": \"89289855496\"\n}",
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
          "89289855496",
          "PHONE"
        ]
      ],
      "forced": false
    },
    {
      "tool_name": "escalate_to_human",
      "seq": 4,
      "call_ordinal": 0,
      "turn": 5,
      "return_form": "single",
      "text_real": "{\n  \"escalation_id\": \"esc-1\",\n  \"queue\": \"general\",\n  \"status\": \"queued\",\n  \"assignee\": {\n    \"name\": \"Соколов Андрей\",\n    \"phone\": \"+79261234567\"\n  }\n}",
      "text_masked": "{\n  \"escalation_id\": \"esc-1\",\n  \"queue\": \"general\",\n  \"status\": \"queued\",\n  \"assignee\": {\n    \"name\": \"Котов Ярослав\",\n    \"phone\": \"+79754947935\"\n  }\n}",
      "spans_real": {},
      "pieces": [
        [
          103,
          117,
          "Котов Ярослав",
          "NAME"
        ],
        [
          134,
          146,
          "+79754947935",
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
      "substitute": "мухин савва",
      "request_index": 1
    },
    {
      "item_id": "i9",
      "msg": 1,
      "result_seq": -1,
      "substitute": "89289855496",
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
      "substitute": "савва",
      "request_index": 2
    },
    {
      "item_id": "i3",
      "msg": -1,
      "result_seq": 1,
      "substitute": "игоревич",
      "request_index": 2
    },
    {
      "item_id": "i4",
      "msg": -1,
      "result_seq": 1,
      "substitute": "89289855496",
      "request_index": 2
    },
    {
      "item_id": "i5",
      "msg": -1,
      "result_seq": 1,
      "substitute": "bvatkjyl@example.ru",
      "request_index": 2
    },
    {
      "item_id": "i6",
      "msg": -1,
      "result_seq": 1,
      "substitute": "1969-08-26",
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
      "item_id": "i10",
      "msg": 2,
      "result_seq": -1,
      "substitute": "чижова глеба",
      "request_index": 3
    },
    {
      "item_id": "i11",
      "msg": 2,
      "result_seq": -1,
      "substitute": "краснодар бульвар тополиный 11 квартира 46",
      "request_index": 3
    },
    {
      "item_id": "i4",
      "msg": -1,
      "result_seq": 2,
      "substitute": "89289855496",
      "request_index": 6
    },
    {
      "item_id": "i4",
      "msg": -1,
      "result_seq": 3,
      "substitute": "89289855496",
      "request_index": 7
    }
  ],
  "turn_replies": [
    "Добрый день, Руслан Фёдорович! Вас вижу в базе. Уточните, пожалуйста, что нужно оформить — вызов курьера? И что вы имеете в виду под «6 отделение»: это адрес, куда нужно доставить, или что-то другое?",
    "Понял: посылку получает Тарасов Алл, адрес — г. Краснодар, ул. Светлый, д. 20, кв. 31.\n\nЧтобы вызвать курьера, мне не хватает двух вещей:\n1. На какой интервал времени вызвать курьера (например, сегодня с 14:00 до 18:00)?\n2. По какому телефону с ним связаться — на ваш номер 89273011996 или нужен телефон получателя?",
    "Хорошо, телефон для связи оставляю ваш — 89273011996, и подтверждение продублирую вам СМС на него.\n\nОстался последний вопрос: на какой интервал времени вызвать курьера к адресу г. Краснодар, ул. Светлый, д. 20, кв. 31? Например, сегодня с 14:00 до 18:00 — или назовите удобное время.",
    "Готово, Руслан Фёдорович!\n\nКурьер вызван:\n- Адрес: г. Краснодар, ул. Светлый, д. 20, кв. 31\n- Получатель: Тарасов Алл\n- Интервал: сегодня, 02.09.2026, с 15:00 до 18:00\n- Заявка: clm-1\n\nПодтверждение продублировано вам СМС на 89273011996. Позвонить вам сможет и получатель, если что-то уточнит.\n\nЕсли по «6 отделению» было что-то важное (например, конкретный пункт приёма/выдачи) — уточните, я внесу в заявку.",
    "Передал оператору 📋\n\n- Очередь: general\n- Оператор: Соколов Андрей (+79261234567)\n- Номер обращения: esc-1\n\nВ сводку включил всё по первому клиенту: Заболотный Руслан Фёдорович, 89273011996; заявку на курьера clm-1 (г. Краснодар, ул. Светлый, д. 20, кв. 31, получатель Тарасов Алл, интервал 02.09.2026 с 15:00 до 18:00); отправленное СМС sms-1; и нерешённый вопрос с «6 отделением»."
  ],
  "call_turns": [
    1,
    4,
    4,
    5
  ],
  "request_count": 9,
  "stream_mismatch": false,
  "reply_whole": "",
  "turn_residual": 3
}

## Recorded observer hops

[
  {
    "case_id": "memory_anaphora-012",
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
    "produced": "мухин савва",
    "reference": "заболотный руслан",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "memory_anaphora-012",
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
    "produced": "89289855496",
    "reference": "89273011996",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "memory_anaphora-012",
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
    "produced": "+79273011996",
    "reference": "+79289855496",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "memory_anaphora-012",
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
    "reference": "заболотный",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "memory_anaphora-012",
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
    "produced": "1969-08-26",
    "reference": "1969-05-23",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "memory_anaphora-012",
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
    "produced": "чижова глеба",
    "reference": "тарасова алла",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "memory_anaphora-012",
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
    "produced": "краснодар бульвар тополиный 11 квартира 46",
    "reference": "краснодар бульвар светлый 20 квартира 31",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "memory_anaphora-012",
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
    "produced": "Заболотный",
    "reference": "Мухин",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "memory_anaphora-012",
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
    "produced": "89289855496",
    "reference": "89273011996",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "memory_anaphora-012",
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
    "case_id": "memory_anaphora-012",
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
    "case_id": "memory_anaphora-012",
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
    "produced": "краснодар бульвар тополиный 11 квартира 46",
    "reference": "краснодар бульвар светлый 20 квартира 31",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "memory_anaphora-012",
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
    "produced": "чижова глеба",
    "reference": "тарасова алла",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "memory_anaphora-012",
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
    "produced": "Светлый",
    "reference": "Тополиный бульвар",
    "status": "observed",
    "verdict": {
      "same": false,
      "differs": [
        "generic"
      ]
    }
  },
  {
    "case_id": "memory_anaphora-012",
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
    "produced": "Тарасов Алл",
    "reference": "Чижов Глеб",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "memory_anaphora-012",
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
    "produced": "мухин савва",
    "reference": "заболотный руслан",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "memory_anaphora-012",
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
    "produced": "Заболотный Руслан",
    "reference": "Мухин Савва",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "memory_anaphora-012",
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
    "produced": "+7 927 301-19-96",
    "reference": "+7 928 985-54-96",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "memory_anaphora-012",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i11",
      "hop_index": -1,
      "turn": 4,
      "tool_name": "courier_book",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": -1,
      "path": "address.building",
      "optional": false
    },
    "declared": false,
    "pii_type": "LOC",
    "produced": "20",
    "reference": "11",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "memory_anaphora-012",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "",
      "hop_index": -1,
      "turn": 4,
      "tool_name": "courier_book",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": -1,
      "path": "address.locality",
      "optional": false
    },
    "declared": false,
    "pii_type": "LOC",
    "produced": "Краснодар",
    "reference": "Краснодар",
    "status": "unmasked",
    "verdict": null
  },
  {
    "case_id": "memory_anaphora-012",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i11",
      "hop_index": -1,
      "turn": 4,
      "tool_name": "courier_book",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": -1,
      "path": "address.sflat",
      "optional": false
    },
    "declared": false,
    "pii_type": "LOC",
    "produced": "31",
    "reference": "46",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "memory_anaphora-012",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i4",
      "hop_index": -1,
      "turn": 4,
      "tool_name": "courier_book",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": -1,
      "path": "contact.phone",
      "optional": false
    },
    "declared": false,
    "pii_type": "PHONE",
    "produced": "+79273011996",
    "reference": "+79289855496",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "memory_anaphora-012",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i4",
      "hop_index": -1,
      "turn": 4,
      "tool_name": "notify_sms",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": -1,
      "path": "number",
      "optional": false
    },
    "declared": false,
    "pii_type": "PHONE",
    "produced": "+79273011996",
    "reference": "+79289855496",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "memory_anaphora-012",
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
    "produced": "Руслан",
    "reference": "Савва",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "memory_anaphora-012",
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
    "produced": "Фёдорович",
    "reference": "Игоревич",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "memory_anaphora-012",
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
    "produced": "Заболотный Руслан",
    "reference": "Мухин Савва",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "memory_anaphora-012",
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
    "produced": "89273011996",
    "reference": "+7 928 985-54-96",
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
    "case_id": "memory_anaphora-012",
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
    "produced": "89273011996",
    "reference": "+7 928 985-54-96",
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
    "case_id": "memory_anaphora-012",
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
    "produced": "ул. Светлый, д. 20",
    "reference": "Тополиный бульвар, 11",
    "status": "observed",
    "verdict": {
      "same": false,
      "differs": [
        "generic",
        "generic_position",
        "house_marker"
      ]
    }
  },
  {
    "case_id": "memory_anaphora-012",
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
    "produced": "Тарасов Алл",
    "reference": "Чижов Глеб",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  }
]
