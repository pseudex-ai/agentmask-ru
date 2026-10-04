# memory_anaphora-028 | source C | repeat 0

Synthetic benchmark evidence. Verbatim serialized fields; no inferred verdicts.

## Case specification

{
  "base": {
    "id": "memory_anaphora-028",
    "kind": "long_support",
    "register": "clean",
    "provenance": {
      "kind": "template",
      "corpus": "authored",
      "key": "",
      "shape": "",
      "selection": "authored",
      "weight": 1.0,
      "licence": "authored"
    },
    "cluster": "PHONE:9252387434",
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
        "content": "Здравствуйте. это Лебедев Максим мой телефон +7 925 238-74-34. кстати к 10 часам.",
        "source": null,
        "name": ""
      },
      {
        "role": "user",
        "content": "посылку примет Ерохин Пётр адрес Воткинск, бульвар Лермонтова, 23 кв. 196.",
        "source": null,
        "name": ""
      },
      {
        "role": "user",
        "content": "пришлите на тот же номер.",
        "source": null,
        "name": ""
      },
      {
        "role": "user",
        "content": "заберите у неё по тому же адресу.",
        "source": null,
        "name": ""
      },
      {
        "role": "user",
        "content": "по первому получателю передайте оператору.",
        "source": null,
        "name": ""
      }
    ],
    "tools": [
      "crm_find_contact",
      "callback_schedule",
      "courier_book",
      "crm_add_note"
    ],
    "seed_records": [
      {
        "id": "c-caller",
        "table": "contacts",
        "fields": {
          "last_name": "лебедев",
          "first_name": "максим",
          "middle_name": "константинович",
          "phone": "+79252387434",
          "email": "lebedev77@yandex.ru",
          "birth_date": "2000-06-09",
          "address": {
            "city": "воткинск",
            "street": "маяковского",
            "house": "32",
            "flat": "129"
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
        "identity": "p28",
        "value": "лебедев",
        "canonical": "лебедев",
        "parts": {
          "surname": "лебедев",
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
        "identity": "p28",
        "value": "максим",
        "canonical": "максим",
        "parts": {
          "given": "максим",
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
        "identity": "p28",
        "value": "константинович",
        "canonical": "константинович",
        "parts": {
          "patronymic": "константинович",
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
        "identity": "p28",
        "value": "+79252387434",
        "canonical": "+79252387434",
        "parts": {
          "digits": "9252387434"
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
        "identity": "p28",
        "value": "lebedev77@yandex.ru",
        "canonical": "lebedev77@yandex.ru",
        "parts": {
          "local": "lebedev77",
          "domain": "yandex.ru"
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
        "identity": "p28",
        "value": "2000-06-09",
        "canonical": "2000-06-09",
        "parts": {
          "iso": "2000-06-09"
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
        "identity": "p28.home",
        "value": "маяковского",
        "canonical": "маяковского",
        "parts": {
          "street": "маяковского",
          "street_type": "бульвар",
          "house": "32",
          "flat": "129",
          "city": "воткинск"
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
        "identity": "p28",
        "value": "Лебедев Максим",
        "canonical": "Лебедев Максим",
        "parts": {
          "surname": "Лебедев",
          "given": "Максим",
          "gender": "m"
        },
        "where": {
          "kind": "message",
          "msg": 1,
          "start": 18,
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
        "identity": "p28",
        "value": "+7 925 238-74-34",
        "canonical": "+79252387434",
        "parts": {
          "digits": "9252387434"
        },
        "where": {
          "kind": "message",
          "msg": 1,
          "start": 45,
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
        "identity": "p28b",
        "value": "Ерохин Пётр",
        "canonical": "Ерохин Пётр",
        "parts": {
          "surname": "Ерохин",
          "given": "Пётр",
          "gender": "m"
        },
        "where": {
          "kind": "message",
          "msg": 2,
          "start": 15,
          "end": 26,
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
        "identity": "p28b.home",
        "value": "Воткинск, бульвар Лермонтова, 23 кв. 196",
        "canonical": "Воткинск, бульвар Лермонтова, 23 кв. 196",
        "parts": {
          "street": "лермонтова",
          "street_type": "бульвар",
          "house": "23",
          "flat": "196",
          "city": "воткинск"
        },
        "where": {
          "kind": "message",
          "msg": 2,
          "start": 33,
          "end": 73,
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
        "start": 72,
        "end": 80,
        "msg": 1,
        "family": "time_of_day",
        "why": "время, а не номер"
      }
    ],
    "expects": {
      "reachable_tools": [
        "crm_find_contact",
        "callback_schedule",
        "courier_book"
      ],
      "primary_identity": "p28",
      "must_contain": [
        "лебедев"
      ],
      "must_not_contain": [],
      "validate_types": []
    },
    "trace": [
      {
        "msg": 1,
        "key": "",
        "start": 0,
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
        "key": "name",
        "start": 18,
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
        "end": 63,
        "origin": "literal"
      },
      {
        "msg": 1,
        "key": "",
        "start": 63,
        "end": 69,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 1,
        "key": "",
        "start": 69,
        "end": 70,
        "origin": "literal"
      },
      {
        "msg": 1,
        "key": "",
        "start": 70,
        "end": 71,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 1,
        "key": "",
        "start": 71,
        "end": 72,
        "origin": "literal"
      },
      {
        "msg": 1,
        "key": "neg1",
        "start": 72,
        "end": 80,
        "origin": "negative:neg1"
      },
      {
        "msg": 1,
        "key": "",
        "start": 80,
        "end": 81,
        "origin": "literal"
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
        "end": 26,
        "origin": "value:name2"
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
        "key": "addr2",
        "start": 33,
        "end": 73,
        "origin": "value:addr2"
      },
      {
        "msg": 2,
        "key": "",
        "start": 73,
        "end": 74,
        "origin": "literal"
      },
      {
        "msg": 3,
        "key": "",
        "start": 0,
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
        "end": 11,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 3,
        "key": "",
        "start": 11,
        "end": 12,
        "origin": "literal"
      },
      {
        "msg": 3,
        "key": "",
        "start": 12,
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
        "end": 18,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 3,
        "key": "",
        "start": 18,
        "end": 19,
        "origin": "literal"
      },
      {
        "msg": 3,
        "key": "",
        "start": 19,
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
        "msg": 4,
        "key": "",
        "start": 0,
        "end": 8,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 4,
        "key": "",
        "start": 8,
        "end": 9,
        "origin": "literal"
      },
      {
        "msg": 4,
        "key": "",
        "start": 9,
        "end": 10,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 4,
        "key": "",
        "start": 10,
        "end": 11,
        "origin": "literal"
      },
      {
        "msg": 4,
        "key": "",
        "start": 11,
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
        "end": 17,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 4,
        "key": "",
        "start": 17,
        "end": 18,
        "origin": "literal"
      },
      {
        "msg": 4,
        "key": "",
        "start": 18,
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
        "end": 25,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 4,
        "key": "",
        "start": 25,
        "end": 26,
        "origin": "literal"
      },
      {
        "msg": 4,
        "key": "",
        "start": 26,
        "end": 32,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 4,
        "key": "",
        "start": 32,
        "end": 33,
        "origin": "literal"
      },
      {
        "msg": 5,
        "key": "",
        "start": 0,
        "end": 2,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 5,
        "key": "",
        "start": 2,
        "end": 3,
        "origin": "literal"
      },
      {
        "msg": 5,
        "key": "",
        "start": 3,
        "end": 10,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 5,
        "key": "",
        "start": 10,
        "end": 11,
        "origin": "literal"
      },
      {
        "msg": 5,
        "key": "",
        "start": 11,
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
        "end": 31,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 5,
        "key": "",
        "start": 31,
        "end": 32,
        "origin": "literal"
      },
      {
        "msg": 5,
        "key": "",
        "start": 32,
        "end": 41,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 5,
        "key": "",
        "start": 41,
        "end": 42,
        "origin": "literal"
      }
    ],
    "note": "пять реплик: обратный звонок по «тому же телефону», курьер «по тому адресу», заметка в карточке по «первому клиенту»"
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
      "tool_name": "callback_schedule",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": 8,
      "path": "phone",
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
      "tool_name": "crm_add_note",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": 14,
      "path": "text",
      "optional": false
    },
    {
      "kind": "OUT",
      "owner": "summary",
      "item_id": "i10",
      "hop_index": 16,
      "turn": 5,
      "tool_name": "crm_add_note",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": 5,
      "path": "text",
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
    "case_id": "memory_anaphora-028",
    "arm": "I",
    "repeat": 0,
    "calls": [
      {
        "name": "crm_find_contact",
        "written": {
          "query": {
            "phone": "+79187249467"
          }
        },
        "restored": {
          "query": {
            "phone": "+79252387434"
          }
        },
        "residual": {},
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "query": {
            "phone": "+79252387434"
          }
        },
        "seq": 1
      },
      {
        "name": "courier_book",
        "written": {
          "address": {
            "building": "71",
            "locality": "Воткинск",
            "sflat": "144",
            "street": "Ивовый бульвар"
          },
          "contact": {
            "name": "Лебедев Артур",
            "phone": "+79187249467"
          },
          "interval": {
            "from": "2026-09-02T10:00:00+04:00",
            "to": "2026-09-02T11:00:00+04:00"
          }
        },
        "restored": {
          "address": {
            "building": "23",
            "locality": "Воткинск",
            "sflat": "196",
            "street": "Лермонтова"
          },
          "contact": {
            "name": "Ерохин Пётр",
            "phone": "+79252387434"
          },
          "interval": {
            "from": "2026-09-02T10:00:00+04:00",
            "to": "2026-09-02T11:00:00+04:00"
          }
        },
        "residual": {},
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "address": {
            "building": "23",
            "locality": "воткинск",
            "porch": "",
            "sflat": "196",
            "street": "лермонтова"
          },
          "contact": {
            "name": "Ерохин Пётр",
            "phone": "+79252387434"
          },
          "interval": {
            "from": "2026-09-02T10:00:00+04:00",
            "to": "2026-09-02T11:00:00+04:00"
          }
        },
        "seq": 2
      },
      {
        "name": "crm_add_note",
        "written": {
          "entity_id": "c-caller",
          "note_type": "call_in",
          "text": "Оформил вызов курьера (заявка clm-1). Адрес: г. Воткинск, Ивовый бульвар, 71, кв. 144. Получатель/контакт: Лебедев Артур, тел. +7 918 724-94-67 (тот же номер). Интервал: 02.09.2026, 10:00–11:00 (+04:00, Europe/Samara)."
        },
        "restored": {
          "entity_id": "c-caller",
          "note_type": "call_in",
          "text": "Оформил вызов курьера (заявка clm-1). Адрес: г. Воткинск, Лермонтова, 23, кв. 196. Получатель/контакт: Ерохин Пётр, тел. +79252387434 (тот же номер). Интервал: 02.09.2026, 10:00–11:00 (+04:00, Europe/Samara)."
        },
        "residual": {},
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "entity_id": "c-caller",
          "note_type": "call_in",
          "text": "Оформил вызов курьера (заявка clm-1). Адрес: г. Воткинск, Лермонтова, 23, кв. 196. Получатель/контакт: Ерохин Пётр, тел. +79252387434 (тот же номер). Интервал: 02.09.2026, 10:00–11:00 (+04:00, Europe/Samara)."
        },
        "seq": 3
      }
    ],
    "state": [
      {
        "fields": {
          "address": {
            "building": "23",
            "locality": "воткинск",
            "porch": "",
            "sflat": "196",
            "street": "лермонтова"
          },
          "contact": {
            "name": "Ерохин Пётр",
            "phone": "+79252387434"
          },
          "interval": {
            "from": "2026-09-02T10:00:00+04:00",
            "to": "2026-09-02T11:00:00+04:00"
          }
        },
        "id": "clm-1",
        "seq": 2,
        "table": "claims",
        "tool": "courier_book"
      },
      {
        "fields": {
          "entity_id": "c-caller",
          "note_type": "call_in",
          "text": "Оформил вызов курьера (заявка clm-1). Адрес: г. Воткинск, Лермонтова, 23, кв. 196. Получатель/контакт: Ерохин Пётр, тел. +79252387434 (тот же номер). Интервал: 02.09.2026, 10:00–11:00 (+04:00, Europe/Samara)."
        },
        "id": "note-1",
        "seq": 3,
        "table": "notes",
        "tool": "crm_add_note"
      }
    ],
    "reply": "Понял — по первому получателю (Ерохин Пётр, заявка clm-1) передам оператору.\n\nУточните, пожалуйста, во сколько вам удобно, чтобы оператор перезвонил? Номер для связи тот же — +79252387434 (Воткинск, Europe/Samara).",
    "termination": "done",
    "cost_usd": 0.014717,
    "substitutes": {
      "i1": [
        "устинов",
        {
          "surname": "устинов"
        }
      ],
      "i10": [
        "Лебедев Артур",
        {
          "given": "Артур",
          "surname": "Лебедев"
        }
      ],
      "i11": [
        "Воткинск, бульвар Ивовый, 71 кв. 144",
        {
          "city": "воткинск",
          "flat": "144",
          "house": "71",
          "street": "ивовый"
        }
      ],
      "i2": [
        "назар",
        {
          "given": "назар"
        }
      ],
      "i3": [
        "сергеевич",
        {
          "patronymic": "сергеевич"
        }
      ],
      "i4": [
        "+7 918 724-94-67",
        {
          "digits": "9187249467"
        }
      ],
      "i5": [
        "rfamnvlh@example.ru",
        {
          "domain": "example.ru",
          "local": "rfamnvlh"
        }
      ],
      "i6": [
        "2000-03-22",
        {
          "iso": "2000-03-22"
        }
      ],
      "i7": [
        "каштановая",
        {
          "street": "каштановая"
        }
      ],
      "i8": [
        "Устинов Назар",
        {
          "given": "Назар",
          "surname": "Устинов"
        }
      ],
      "i9": [
        "+7 918 724-94-67",
        {
          "digits": "9187249467"
        }
      ]
    },
    "masked_spans": {
      "0": [],
      "1": [
        [
          18,
          32
        ],
        [
          45,
          61
        ]
      ],
      "2": [
        [
          15,
          26
        ],
        [
          33,
          73
        ]
      ],
      "3": [],
      "4": [],
      "5": []
    }
  },
  "reply_raw": "Понял — по первому получателю (Лебедев Артур, заявка clm-1) передам оператору.\n\nУточните, пожалуйста, во сколько вам удобно, чтобы оператор перезвонил? Номер для связи тот же — +7 918 724-94-67 (Воткинск, Europe/Samara).",
  "control_reply": "Передал оператору данные по первому получателю — Ерохин Пётр, г. Воткинск, бульвар Лермонтова, д. 23, кв. 196, контактный номер +7 925 238-74-34 (заявка clm-1). Оператор займётся этим вопросом.\n\nПо забору посылки («у неё» по тому же адресу) напоминаю: жду от вас **имя и телефон того, у кого забрать**, и **время** вызова курьера — тогда сразу оформлю заявку.",
  "tool_results": [
    {
      "tool_name": "crm_find_contact",
      "seq": 1,
      "call_ordinal": 0,
      "turn": 1,
      "return_form": "list",
      "text_real": "{\n  \"contacts\": [\n    {\n      \"id\": \"c-caller\",\n      \"last_name\": \"лебедев\",\n      \"first_name\": \"максим\",\n      \"middle_name\": \"константинович\",\n      \"phone\": \"+79252387434\",\n      \"email\": \"lebedev77@yandex.ru\",\n      \"birth_date\": \"2000-06-09\",\n      \"address\": {\n        \"city\": \"воткинск\",\n        \"street\": \"маяковского\",\n        \"house\": \"32\",\n        \"flat\": \"129\"\n      }\n    }\n  ]\n}",
      "text_masked": "{\n  \"contacts\": [\n    {\n      \"id\": \"c-caller\",\n      \"last_name\": \"устинов\",\n      \"first_name\": \"назар\",\n      \"middle_name\": \"сергеевич\",\n      \"phone\": \"+7 918 724-94-67\",\n      \"email\": \"rfamnvlh@example.ru\",\n      \"birth_date\": \"2000-03-22\",\n      \"address\": {\n        \"city\": \"воткинск\",\n        \"street\": \"каштановая\",\n        \"house\": \"72\",\n        \"flat\": \"97\"\n      }\n    }\n  ]\n}",
      "spans_real": {
        "i1": [
          68,
          75
        ],
        "i2": [
          99,
          105
        ],
        "i3": [
          130,
          144
        ],
        "i4": [
          163,
          175
        ],
        "i5": [
          194,
          213
        ],
        "i6": [
          237,
          247
        ],
        "i7": [
          316,
          327
        ]
      },
      "pieces": [
        [
          68,
          75,
          "устинов",
          "NAME"
        ],
        [
          99,
          105,
          "назар",
          "NAME"
        ],
        [
          130,
          144,
          "сергеевич",
          "NAME"
        ],
        [
          163,
          175,
          "+7 918 724-94-67",
          "PHONE"
        ],
        [
          194,
          213,
          "rfamnvlh@example.ru",
          "EMAIL"
        ],
        [
          237,
          247,
          "2000-03-22",
          "DOB"
        ],
        [
          286,
          294,
          "воткинск",
          "LOC"
        ],
        [
          316,
          327,
          "каштановая",
          "LOC"
        ],
        [
          348,
          350,
          "72",
          "LOC"
        ],
        [
          370,
          373,
          "97",
          "LOC"
        ]
      ],
      "forced": false
    },
    {
      "tool_name": "courier_book",
      "seq": 2,
      "call_ordinal": 0,
      "turn": 3,
      "return_form": "nested",
      "text_real": "{\n  \"claim_id\": \"clm-1\",\n  \"status\": \"estimating\",\n  \"contact\": {\n    \"name\": \"Ерохин Пётр\",\n    \"phone\": \"+79252387434\"\n  },\n  \"address\": \"г. Воткинск, ул. Лермонтова, д. 23, кв. 196\"\n}",
      "text_masked": "{\n  \"claim_id\": \"clm-1\",\n  \"status\": \"estimating\",\n  \"contact\": {\n    \"name\": \"Лебедев Артур\",\n    \"phone\": \"+7 918 724-94-67\"\n  },\n  \"address\": \"г. Воткинск, ул. Ивовый, д. 71, кв. 144\"\n}",
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
          "Лебедев Артур",
          "NAME"
        ],
        [
          107,
          119,
          "+7 918 724-94-67",
          "PHONE"
        ],
        [
          140,
          183,
          "г. Воткинск, ул. Ивовый, д. 71, кв. 144",
          "LOC"
        ]
      ],
      "forced": false
    },
    {
      "tool_name": "crm_add_note",
      "seq": 3,
      "call_ordinal": 0,
      "turn": 3,
      "return_form": "single",
      "text_real": "{\n  \"id\": \"note-1\",\n  \"entity_id\": \"c-caller\",\n  \"length\": 208,\n  \"entity\": {\n    \"last_name\": \"лебедев\",\n    \"first_name\": \"максим\",\n    \"phone\": \"+79252387434\"\n  }\n}",
      "text_masked": "{\n  \"id\": \"note-1\",\n  \"entity_id\": \"c-caller\",\n  \"length\": 208,\n  \"entity\": {\n    \"last_name\": \"устинов\",\n    \"first_name\": \"назар\",\n    \"phone\": \"+7 918 724-94-67\"\n  }\n}",
      "spans_real": {
        "i1": [
          96,
          103
        ],
        "i2": [
          125,
          131
        ],
        "i4": [
          148,
          160
        ]
      },
      "pieces": [
        [
          96,
          103,
          "устинов",
          "NAME"
        ],
        [
          125,
          131,
          "назар",
          "NAME"
        ],
        [
          148,
          160,
          "+7 918 724-94-67",
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
      "substitute": "Устинов Назар",
      "request_index": 1
    },
    {
      "item_id": "i9",
      "msg": 1,
      "result_seq": -1,
      "substitute": "+7 918 724-94-67",
      "request_index": 1
    },
    {
      "item_id": "i1",
      "msg": -1,
      "result_seq": 1,
      "substitute": "устинов",
      "request_index": 2
    },
    {
      "item_id": "i2",
      "msg": -1,
      "result_seq": 1,
      "substitute": "назар",
      "request_index": 2
    },
    {
      "item_id": "i3",
      "msg": -1,
      "result_seq": 1,
      "substitute": "сергеевич",
      "request_index": 2
    },
    {
      "item_id": "i4",
      "msg": -1,
      "result_seq": 1,
      "substitute": "+7 918 724-94-67",
      "request_index": 2
    },
    {
      "item_id": "i5",
      "msg": -1,
      "result_seq": 1,
      "substitute": "rfamnvlh@example.ru",
      "request_index": 2
    },
    {
      "item_id": "i6",
      "msg": -1,
      "result_seq": 1,
      "substitute": "2000-03-22",
      "request_index": 2
    },
    {
      "item_id": "i7",
      "msg": -1,
      "result_seq": 1,
      "substitute": "каштановая",
      "request_index": 2
    },
    {
      "item_id": "i10",
      "msg": 2,
      "result_seq": -1,
      "substitute": "Лебедев Артур",
      "request_index": 3
    },
    {
      "item_id": "i11",
      "msg": 2,
      "result_seq": -1,
      "substitute": "Воткинск, бульвар Ивовый, 71 кв. 144",
      "request_index": 3
    },
    {
      "item_id": "i4",
      "msg": -1,
      "result_seq": 2,
      "substitute": "+7 918 724-94-67",
      "request_index": 5
    },
    {
      "item_id": "i1",
      "msg": -1,
      "result_seq": 3,
      "substitute": "устинов",
      "request_index": 6
    },
    {
      "item_id": "i2",
      "msg": -1,
      "result_seq": 3,
      "substitute": "назар",
      "request_index": 6
    },
    {
      "item_id": "i4",
      "msg": -1,
      "result_seq": 3,
      "substitute": "+7 918 724-94-67",
      "request_index": 6
    }
  ],
  "turn_replies": [
    "Здравствуйте, Максим Константинович! Нашёл вашу карточку. Уточните, пожалуйста, что именно нужно: вызвать курьера (откуда и куда забрать посылку) или это что-то другое? И «к 10 часам» — на какое число, сегодня 2 сентября или на другой день?",
    "Понял. Тогда для вызова курьера не хватает только телефона Петра — подскажите его номер, пожалуйста.\n\nИ подтвердите время: вам нужно на сегодня, 2 сентября, к 10:00?",
    "Готово, курьер вызван! 🚚\n\n- **Заявка:** clm-1\n- **Адрес:** г. г. Воткинск, ул. Лермонтова, д. 23, кв. 196\n- **Контакт:** Ерохин Пётр, тел. +79252387434\n- **Время:** сегодня, 2 сентября, 10:00–11:00\n\nЕсли что-то нужно поправить — скажите.",
    "Уточните, пожалуйста, пару деталей, чтобы вызвать курьера на забор:\n\n- у кого именно забрать посылку — имя и телефон этого человека (в заявке на забор нужен контакт на месте);\n- на какое время вызывать курьера.\n\nАдрес тот же — г. г. Воткинск, ул. Лермонтова, д. 23, кв. 196, верно?",
    "Понял — по первому получателю (Ерохин Пётр, заявка clm-1) передам оператору.\n\nУточните, пожалуйста, во сколько вам удобно, чтобы оператор перезвонил? Номер для связи тот же — +79252387434 (Воткинск, Europe/Samara)."
  ],
  "call_turns": [
    1,
    3,
    3
  ],
  "request_count": 8,
  "stream_mismatch": false,
  "reply_whole": "",
  "turn_residual": 2
}

## Recorded observer hops

[
  {
    "case_id": "memory_anaphora-028",
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
    "produced": "Устинов Назар",
    "reference": "Лебедев Максим",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "memory_anaphora-028",
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
    "produced": "+7 918 724-94-67",
    "reference": "+7 925 238-74-34",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "memory_anaphora-028",
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
    "produced": "+79252387434",
    "reference": "+79187249467",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "memory_anaphora-028",
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
    "produced": "устинов",
    "reference": "лебедев",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "memory_anaphora-028",
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
    "produced": "2000-03-22",
    "reference": "2000-06-09",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "memory_anaphora-028",
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
    "produced": "Лебедев Артур",
    "reference": "Ерохин Пётр",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "memory_anaphora-028",
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
    "produced": "Воткинск, бульвар Ивовый, 71 кв. 144",
    "reference": "Воткинск, бульвар Лермонтова, 23 кв. 196",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "memory_anaphora-028",
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
    "produced": "",
    "reference": "",
    "status": "unmasked",
    "verdict": null
  },
  {
    "case_id": "memory_anaphora-028",
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
    "produced": "+7 918 724-94-67",
    "reference": "+7 925 238-74-34",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "memory_anaphora-028",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i9",
      "hop_index": 9,
      "turn": 3,
      "tool_name": "callback_schedule",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": 8,
      "path": "phone",
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
    "case_id": "memory_anaphora-028",
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
    "produced": "Воткинск, бульвар Ивовый, 71 кв. 144",
    "reference": "Воткинск, бульвар Лермонтова, 23 кв. 196",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "memory_anaphora-028",
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
    "produced": "Лебедев Артур",
    "reference": "Ерохин Пётр",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "memory_anaphora-028",
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
    "case_id": "memory_anaphora-028",
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
    "case_id": "memory_anaphora-028",
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
    "produced": "Устинов Назар",
    "reference": "Лебедев Максим",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "memory_anaphora-028",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "summary",
      "item_id": "i8",
      "hop_index": 15,
      "turn": 5,
      "tool_name": "crm_add_note",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": 14,
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
    "case_id": "memory_anaphora-028",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "summary",
      "item_id": "i10",
      "hop_index": 16,
      "turn": 5,
      "tool_name": "crm_add_note",
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
    "case_id": "memory_anaphora-028",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i11",
      "hop_index": -1,
      "turn": 3,
      "tool_name": "courier_book",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": -1,
      "path": "address.building",
      "optional": false
    },
    "declared": false,
    "pii_type": "LOC",
    "produced": "23",
    "reference": "71",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "memory_anaphora-028",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "",
      "hop_index": -1,
      "turn": 3,
      "tool_name": "courier_book",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": -1,
      "path": "address.locality",
      "optional": false
    },
    "declared": false,
    "pii_type": "LOC",
    "produced": "Воткинск",
    "reference": "Воткинск",
    "status": "unmasked",
    "verdict": null
  },
  {
    "case_id": "memory_anaphora-028",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i11",
      "hop_index": -1,
      "turn": 3,
      "tool_name": "courier_book",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": -1,
      "path": "address.sflat",
      "optional": false
    },
    "declared": false,
    "pii_type": "LOC",
    "produced": "196",
    "reference": "144",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "memory_anaphora-028",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i11",
      "hop_index": -1,
      "turn": 3,
      "tool_name": "courier_book",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": -1,
      "path": "address.street",
      "optional": false
    },
    "declared": false,
    "pii_type": "LOC",
    "produced": "Лермонтова",
    "reference": "Ивовый бульвар",
    "status": "observed",
    "verdict": {
      "same": false,
      "differs": [
        "generic"
      ]
    }
  },
  {
    "case_id": "memory_anaphora-028",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i10",
      "hop_index": -1,
      "turn": 3,
      "tool_name": "courier_book",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": -1,
      "path": "contact.name",
      "optional": false
    },
    "declared": false,
    "pii_type": "NAME",
    "produced": "Ерохин Пётр",
    "reference": "Лебедев Артур",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "memory_anaphora-028",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i4",
      "hop_index": -1,
      "turn": 3,
      "tool_name": "courier_book",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": -1,
      "path": "contact.phone",
      "optional": false
    },
    "declared": false,
    "pii_type": "PHONE",
    "produced": "+79252387434",
    "reference": "+79187249467",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "memory_anaphora-028",
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
    "produced": "Ерохин Пётр",
    "reference": "Лебедев Артур",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "memory_anaphora-028",
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
    "produced": "+79252387434",
    "reference": "+7 918 724-94-67",
    "status": "observed",
    "verdict": {
      "same": false,
      "differs": [
        "grouping",
        "separators"
      ]
    }
  },
  {
    "case_id": "memory_anaphora-028",
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
    "produced": "+79252387434",
    "reference": "+7 918 724-94-67",
    "status": "observed",
    "verdict": {
      "same": false,
      "differs": [
        "grouping",
        "separators"
      ]
    }
  }
]
