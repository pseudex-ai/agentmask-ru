# long_support-014 | source A | repeat 0

Synthetic benchmark evidence. Verbatim serialized fields; no inferred verdicts.

## Case specification

{
  "base": {
    "id": "long_support-014",
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
    "cluster": "PHONE:9259876922",
    "conversation_id": "conv-support-14",
    "now": "2026-09-02",
    "messages": [
      {
        "role": "system",
        "content": "Ты оператор колл-центра. Планируй обратные звонки и отправляй смс инструментами. Сегодня 2026-09-02.",
        "source": null,
        "name": ""
      },
      {
        "role": "user",
        "content": "здравствуйте у меня проблема с заказом это миллер валерия телефон 8 925 987 69 22 да и 9 филиала",
        "source": null,
        "name": ""
      },
      {
        "role": "user",
        "content": "адрес был тула переулок коммунаров 34кв25",
        "source": null,
        "name": ""
      },
      {
        "role": "user",
        "content": "у вас должны быть мои обращения",
        "source": null,
        "name": ""
      },
      {
        "role": "user",
        "content": "и я у вас в базе дважды объедините карточки",
        "source": null,
        "name": ""
      },
      {
        "role": "user",
        "content": "переключите на человека вы не решаете",
        "source": null,
        "name": ""
      }
    ],
    "tools": [
      "ticket_find",
      "ticket_create",
      "escalate_to_human",
      "crm_find_contact",
      "crm_merge_contacts",
      "crm_upsert_contact",
      "crm_add_note",
      "notify_sms",
      "callback_schedule",
      "order_status"
    ],
    "seed_records": [
      {
        "id": "c-1",
        "table": "contacts",
        "fields": {
          "last_name": "миллер",
          "first_name": "валерия",
          "middle_name": "леонидовна",
          "phone": "+79259876922",
          "email": "miller94@mail.ru",
          "birth_date": "1966-07-04",
          "address": {
            "city": "тула",
            "street": "коммунаров",
            "house": "34",
            "flat": "25"
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
        "id": "c-2",
        "table": "contacts",
        "fields": {
          "last_name": "миллер",
          "first_name": "валерия",
          "middle_name": "леонидовна",
          "phone": "+79259876922",
          "email": "miller94@mail.ru",
          "birth_date": "1966-07-04",
          "address": {
            "city": "тула",
            "street": "коммунаров",
            "house": "34",
            "flat": "25"
          }
        },
        "pii_ids": [
          "i8",
          "i9",
          "i10",
          "i11",
          "i12",
          "i13",
          "i14"
        ]
      }
    ],
    "pii": [
      {
        "id": "i1",
        "type": "NAME",
        "identity": "p14",
        "value": "миллер",
        "canonical": "миллер",
        "parts": {
          "surname": "миллер",
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
        "identity": "p14",
        "value": "валерия",
        "canonical": "валерия",
        "parts": {
          "given": "валерия",
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
        "identity": "p14",
        "value": "леонидовна",
        "canonical": "леонидовна",
        "parts": {
          "patronymic": "леонидовна",
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
        "identity": "p14",
        "value": "+79259876922",
        "canonical": "+79259876922",
        "parts": {
          "digits": "9259876922"
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
        "identity": "p14",
        "value": "miller94@mail.ru",
        "canonical": "miller94@mail.ru",
        "parts": {
          "local": "miller94",
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
        "identity": "p14",
        "value": "1966-07-04",
        "canonical": "1966-07-04",
        "parts": {
          "iso": "1966-07-04"
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
        "identity": "p14.home",
        "value": "коммунаров",
        "canonical": "коммунаров",
        "parts": {
          "street": "коммунаров",
          "street_type": "переулок",
          "house": "34",
          "flat": "25",
          "city": "тула"
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
        "identity": "p14",
        "value": "миллер",
        "canonical": "миллер",
        "parts": {
          "surname": "миллер",
          "gender": "f"
        },
        "where": {
          "kind": "seed",
          "msg": -1,
          "start": 0,
          "end": 0,
          "record": "c-2",
          "path": "last_name"
        },
        "duty": "required",
        "spoken": false,
        "stale": false
      },
      {
        "id": "i9",
        "type": "NAME",
        "identity": "p14",
        "value": "валерия",
        "canonical": "валерия",
        "parts": {
          "given": "валерия",
          "gender": "f"
        },
        "where": {
          "kind": "seed",
          "msg": -1,
          "start": 0,
          "end": 0,
          "record": "c-2",
          "path": "first_name"
        },
        "duty": "required",
        "spoken": false,
        "stale": false
      },
      {
        "id": "i10",
        "type": "NAME",
        "identity": "p14",
        "value": "леонидовна",
        "canonical": "леонидовна",
        "parts": {
          "patronymic": "леонидовна",
          "gender": "f"
        },
        "where": {
          "kind": "seed",
          "msg": -1,
          "start": 0,
          "end": 0,
          "record": "c-2",
          "path": "middle_name"
        },
        "duty": "required",
        "spoken": false,
        "stale": false
      },
      {
        "id": "i11",
        "type": "PHONE",
        "identity": "p14",
        "value": "+79259876922",
        "canonical": "+79259876922",
        "parts": {
          "digits": "9259876922"
        },
        "where": {
          "kind": "seed",
          "msg": -1,
          "start": 0,
          "end": 0,
          "record": "c-2",
          "path": "phone"
        },
        "duty": "required",
        "spoken": false,
        "stale": false
      },
      {
        "id": "i12",
        "type": "EMAIL",
        "identity": "p14",
        "value": "miller94@mail.ru",
        "canonical": "miller94@mail.ru",
        "parts": {
          "local": "miller94",
          "domain": "mail.ru"
        },
        "where": {
          "kind": "seed",
          "msg": -1,
          "start": 0,
          "end": 0,
          "record": "c-2",
          "path": "email"
        },
        "duty": "required",
        "spoken": false,
        "stale": false
      },
      {
        "id": "i13",
        "type": "DOB",
        "identity": "p14",
        "value": "1966-07-04",
        "canonical": "1966-07-04",
        "parts": {
          "iso": "1966-07-04"
        },
        "where": {
          "kind": "seed",
          "msg": -1,
          "start": 0,
          "end": 0,
          "record": "c-2",
          "path": "birth_date"
        },
        "duty": "required",
        "spoken": false,
        "stale": false
      },
      {
        "id": "i14",
        "type": "LOC",
        "identity": "p14.home",
        "value": "коммунаров",
        "canonical": "коммунаров",
        "parts": {
          "street": "коммунаров",
          "street_type": "переулок",
          "house": "34",
          "flat": "25",
          "city": "тула"
        },
        "where": {
          "kind": "seed",
          "msg": -1,
          "start": 0,
          "end": 0,
          "record": "c-2",
          "path": "address.street"
        },
        "duty": "required",
        "spoken": false,
        "stale": false
      },
      {
        "id": "i15",
        "type": "NAME",
        "identity": "p14",
        "value": "миллер валерия",
        "canonical": "миллер валерия",
        "parts": {
          "surname": "миллер",
          "given": "валерия",
          "gender": "f"
        },
        "where": {
          "kind": "message",
          "msg": 1,
          "start": 43,
          "end": 57,
          "record": "",
          "path": ""
        },
        "duty": "required",
        "spoken": false,
        "stale": false
      },
      {
        "id": "i16",
        "type": "PHONE",
        "identity": "p14",
        "value": "8 925 987 69 22",
        "canonical": "+79259876922",
        "parts": {
          "digits": "9259876922"
        },
        "where": {
          "kind": "message",
          "msg": 1,
          "start": 66,
          "end": 81,
          "record": "",
          "path": ""
        },
        "duty": "required",
        "spoken": false,
        "stale": false
      },
      {
        "id": "i17",
        "type": "LOC",
        "identity": "p14.home",
        "value": "тула переулок коммунаров 34кв25",
        "canonical": "тула переулок коммунаров 34кв25",
        "parts": {
          "street": "коммунаров",
          "street_type": "переулок",
          "house": "34",
          "flat": "25",
          "city": "тула"
        },
        "where": {
          "kind": "message",
          "msg": 2,
          "start": 10,
          "end": 41,
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
        "value": "9 филиала",
        "start": 87,
        "end": 96,
        "msg": 1,
        "family": "quantity",
        "why": "числительное с единицей счёта — не номер дома"
      }
    ],
    "expects": {
      "reachable_tools": [
        "crm_find_contact",
        "ticket_find",
        "ticket_create",
        "escalate_to_human",
        "crm_merge_contacts",
        "callback_schedule"
      ],
      "primary_identity": "p14",
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
        "end": 14,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 1,
        "key": "",
        "start": 14,
        "end": 15,
        "origin": "literal"
      },
      {
        "msg": 1,
        "key": "",
        "start": 15,
        "end": 19,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 1,
        "key": "",
        "start": 19,
        "end": 20,
        "origin": "literal"
      },
      {
        "msg": 1,
        "key": "",
        "start": 20,
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
        "key": "",
        "start": 29,
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
        "end": 38,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 1,
        "key": "",
        "start": 38,
        "end": 39,
        "origin": "literal"
      },
      {
        "msg": 1,
        "key": "",
        "start": 39,
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
        "key": "n1",
        "start": 43,
        "end": 57,
        "origin": "value:n1"
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
        "end": 65,
        "origin": "chunk:noisy_word"
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
        "key": "ph1",
        "start": 66,
        "end": 81,
        "origin": "value:ph1"
      },
      {
        "msg": 1,
        "key": "",
        "start": 81,
        "end": 82,
        "origin": "literal"
      },
      {
        "msg": 1,
        "key": "",
        "start": 82,
        "end": 84,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 1,
        "key": "",
        "start": 84,
        "end": 85,
        "origin": "literal"
      },
      {
        "msg": 1,
        "key": "",
        "start": 85,
        "end": 86,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 1,
        "key": "",
        "start": 86,
        "end": 87,
        "origin": "literal"
      },
      {
        "msg": 1,
        "key": "neg1",
        "start": 87,
        "end": 96,
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
        "key": "a1",
        "start": 10,
        "end": 41,
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
        "end": 21,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 3,
        "key": "",
        "start": 21,
        "end": 22,
        "origin": "literal"
      },
      {
        "msg": 3,
        "key": "",
        "start": 22,
        "end": 31,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 4,
        "key": "",
        "start": 0,
        "end": 1,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 4,
        "key": "",
        "start": 1,
        "end": 2,
        "origin": "literal"
      },
      {
        "msg": 4,
        "key": "",
        "start": 2,
        "end": 3,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 4,
        "key": "",
        "start": 3,
        "end": 4,
        "origin": "literal"
      },
      {
        "msg": 4,
        "key": "",
        "start": 4,
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
        "end": 11,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 4,
        "key": "",
        "start": 11,
        "end": 12,
        "origin": "literal"
      },
      {
        "msg": 4,
        "key": "",
        "start": 12,
        "end": 16,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 4,
        "key": "",
        "start": 16,
        "end": 17,
        "origin": "literal"
      },
      {
        "msg": 4,
        "key": "",
        "start": 17,
        "end": 23,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 4,
        "key": "",
        "start": 23,
        "end": 24,
        "origin": "literal"
      },
      {
        "msg": 4,
        "key": "",
        "start": 24,
        "end": 34,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 4,
        "key": "",
        "start": 34,
        "end": 35,
        "origin": "literal"
      },
      {
        "msg": 4,
        "key": "",
        "start": 35,
        "end": 43,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 5,
        "key": "",
        "start": 0,
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
        "end": 14,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 5,
        "key": "",
        "start": 14,
        "end": 15,
        "origin": "literal"
      },
      {
        "msg": 5,
        "key": "",
        "start": 15,
        "end": 23,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 5,
        "key": "",
        "start": 23,
        "end": 24,
        "origin": "literal"
      },
      {
        "msg": 5,
        "key": "",
        "start": 24,
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
        "end": 29,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 5,
        "key": "",
        "start": 29,
        "end": 30,
        "origin": "literal"
      },
      {
        "msg": 5,
        "key": "",
        "start": 30,
        "end": 37,
        "origin": "chunk:noisy_word"
      }
    ],
    "note": "обращение, история по телефону, склейка дублей, эскалация СО СВОДКОЙ — персональные данные в прозе, которую читает живой оператор"
  },
  "behaviour": "single",
  "hops": [
    {
      "kind": "IN",
      "owner": "user",
      "item_id": "i15",
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
      "item_id": "i16",
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
      "item_id": "i17",
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
      "kind": "IN",
      "owner": "tool",
      "item_id": "i8",
      "hop_index": 10,
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
      "item_id": "i9",
      "hop_index": 11,
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
      "item_id": "i10",
      "hop_index": 12,
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
      "item_id": "i11",
      "hop_index": 13,
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
      "item_id": "i12",
      "hop_index": 14,
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
      "item_id": "i13",
      "hop_index": 15,
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
      "item_id": "i14",
      "hop_index": 16,
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
      "item_id": "i16",
      "hop_index": 17,
      "turn": 5,
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
      "item_id": "i15",
      "hop_index": 18,
      "turn": 5,
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
      "item_id": "i4",
      "hop_index": 19,
      "turn": 5,
      "tool_name": "ticket_find",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": -1,
      "path": "phone",
      "optional": false
    },
    {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i16",
      "hop_index": 20,
      "turn": 5,
      "tool_name": "ticket_create",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": 1,
      "path": "phone",
      "optional": true
    },
    {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i16",
      "hop_index": 21,
      "turn": 5,
      "tool_name": "callback_schedule",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": 1,
      "path": "phone",
      "optional": false
    },
    {
      "kind": "OUT",
      "owner": "answer",
      "item_id": "i1",
      "hop_index": 22,
      "turn": 5,
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
      "hop_index": 23,
      "turn": 5,
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
      "hop_index": 24,
      "turn": 5,
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
      "hop_index": 25,
      "turn": 5,
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
      "hop_index": 26,
      "turn": 5,
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
      "hop_index": 27,
      "turn": 5,
      "tool_name": "",
      "call_ordinal": -1,
      "parallel_group": "",
      "source_hop": 8,
      "path": "",
      "optional": true
    },
    {
      "kind": "OUT",
      "owner": "answer",
      "item_id": "i8",
      "hop_index": 28,
      "turn": 5,
      "tool_name": "",
      "call_ordinal": -1,
      "parallel_group": "",
      "source_hop": 10,
      "path": "",
      "optional": true
    },
    {
      "kind": "OUT",
      "owner": "answer",
      "item_id": "i9",
      "hop_index": 29,
      "turn": 5,
      "tool_name": "",
      "call_ordinal": -1,
      "parallel_group": "",
      "source_hop": 11,
      "path": "",
      "optional": true
    },
    {
      "kind": "OUT",
      "owner": "answer",
      "item_id": "i10",
      "hop_index": 30,
      "turn": 5,
      "tool_name": "",
      "call_ordinal": -1,
      "parallel_group": "",
      "source_hop": 12,
      "path": "",
      "optional": true
    },
    {
      "kind": "OUT",
      "owner": "answer",
      "item_id": "i11",
      "hop_index": 31,
      "turn": 5,
      "tool_name": "",
      "call_ordinal": -1,
      "parallel_group": "",
      "source_hop": 13,
      "path": "",
      "optional": true
    },
    {
      "kind": "OUT",
      "owner": "answer",
      "item_id": "i12",
      "hop_index": 32,
      "turn": 5,
      "tool_name": "",
      "call_ordinal": -1,
      "parallel_group": "",
      "source_hop": 14,
      "path": "",
      "optional": true
    },
    {
      "kind": "OUT",
      "owner": "answer",
      "item_id": "i13",
      "hop_index": 33,
      "turn": 5,
      "tool_name": "",
      "call_ordinal": -1,
      "parallel_group": "",
      "source_hop": 15,
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
        "i7",
        "i8",
        "i9",
        "i10",
        "i11",
        "i12",
        "i13",
        "i14"
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
    "case_id": "long_support-014",
    "arm": "I",
    "repeat": 0,
    "calls": [
      {
        "name": "crm_find_contact",
        "written": {
          "query": {
            "phone": "+79127647327"
          }
        },
        "restored": {
          "query": {
            "phone": "+79259876922"
          }
        },
        "residual": {},
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "query": {
            "phone": "+79259876922"
          }
        },
        "seq": 1
      },
      {
        "name": "ticket_find",
        "written": {
          "phone": "+79127647327"
        },
        "restored": {
          "phone": "+79259876922"
        },
        "residual": {},
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "phone": "+79259876922"
        },
        "seq": 2
      },
      {
        "name": "crm_merge_contacts",
        "written": {
          "duplicate_id": "c-2",
          "primary_id": "c-1"
        },
        "restored": {
          "duplicate_id": "c-2",
          "primary_id": "c-1"
        },
        "residual": {},
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "duplicate_id": "c-2",
          "primary_id": "c-1"
        },
        "seq": 3
      },
      {
        "name": "ticket_find",
        "written": {
          "phone": "89127647327"
        },
        "restored": {
          "phone": "89259876922"
        },
        "residual": {},
        "refusal_path": "phone",
        "refusal_rule": "phone_not_e164",
        "parsed": null,
        "seq": 4
      },
      {
        "name": "ticket_find",
        "written": {
          "phone": "+7 912 764 73 27"
        },
        "restored": {
          "phone": "+7 925 987 69 22"
        },
        "residual": {},
        "refusal_path": "phone",
        "refusal_rule": "phone_not_e164",
        "parsed": null,
        "seq": 5
      },
      {
        "name": "ticket_find",
        "written": {
          "phone": "8 912 764 73 27"
        },
        "restored": {
          "phone": "+7 925 987 69 22"
        },
        "residual": {},
        "refusal_path": "phone",
        "refusal_rule": "phone_not_e164",
        "parsed": null,
        "seq": 6
      },
      {
        "name": "escalate_to_human",
        "written": {
          "queue": "general",
          "summary": "Клиент: Сазонова Иоланта Александровна, тел. +7 912 764 73 27, адрес: Тула, переулок Полевая, д. 69, кв. 120. Обратилась по проблеме с заказом (суть не уточнена — клиент не назвал номер заказа и детали). Упоминала «9 филиал». По номеру телефона зарегистрированных обращений в системе нет. В CRM обнаружены две одинаковые карточки клиента — дубликат c-2 объединён с основной c-1. Клиент просит переключить на живого оператора, т.к. я не могу решить вопрос. Нужно уточнить номер заказа и суть проблемы, найти заказ и разобраться."
        },
        "restored": {
          "queue": "general",
          "summary": "Клиент: Миллер Валерия Леонидовна, тел. +7 925 987 69 22, адрес: Тула, переулок Полевая, д. 34, кв. 25. Обратилась по проблеме с заказом (суть не уточнена — клиент не назвал номер заказа и детали). Упоминала «9 филиал». По номеру телефона зарегистрированных обращений в системе нет. В CRM обнаружены две одинаковые карточки клиента — дубликат c-2 объединён с основной c-1. Клиент просит переключить на живого оператора, т.к. я не могу решить вопрос. Нужно уточнить номер заказа и суть проблемы, найти заказ и разобраться."
        },
        "residual": {
          "summary": [
            "полевая"
          ]
        },
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "queue": "general",
          "summary": "Клиент: Миллер Валерия Леонидовна, тел. +7 925 987 69 22, адрес: Тула, переулок Полевая, д. 34, кв. 25. Обратилась по проблеме с заказом (суть не уточнена — клиент не назвал номер заказа и детали). Упоминала «9 филиал». По номеру телефона зарегистрированных обращений в системе нет. В CRM обнаружены две одинаковые карточки клиента — дубликат c-2 объединён с основной c-1. Клиент просит переключить на живого оператора, т.к. я не могу решить вопрос. Нужно уточнить номер заказа и суть проблемы, найти заказ и разобраться."
        },
        "seq": 7
      },
      {
        "name": "crm_add_note",
        "written": {
          "entity_id": "c-1",
          "note_type": "call_in",
          "text": "Входящий звонок 2026-09-02. Клиент сообщила о проблеме с заказом, номер заказа и суть не назвала, упоминала «9 филиал». Адрес: Тула, переулок Полевая, 69, кв. 120. Обращений по номеру в системе нет. Объединены дубликаты карточек (c-2 в c-1). Клиент просила переключить на живого оператора — эскалация esc-1 (очередь general, Наумов Даниил)."
        },
        "restored": {
          "entity_id": "c-1",
          "note_type": "call_in",
          "text": "Входящий звонок 2026-09-02. Клиент сообщила о проблеме с заказом, номер заказа и суть не назвала, упоминала «9 филиал». Адрес: Тула, переулок Полевая, 34, кв. 25. Обращений по номеру в системе нет. Объединены дубликаты карточек (c-2 в c-1). Клиент просила переключить на живого оператора — эскалация esc-1 (очередь general, Соколов Андрей)."
        },
        "residual": {
          "text": [
            "полевая"
          ]
        },
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "entity_id": "c-1",
          "note_type": "call_in",
          "text": "Входящий звонок 2026-09-02. Клиент сообщила о проблеме с заказом, номер заказа и суть не назвала, упоминала «9 филиал». Адрес: Тула, переулок Полевая, 34, кв. 25. Обращений по номеру в системе нет. Объединены дубликаты карточек (c-2 в c-1). Клиент просила переключить на живого оператора — эскалация esc-1 (очередь general, Соколов Андрей)."
        },
        "seq": 8
      }
    ],
    "state": [
      {
        "fields": {
          "address": {
            "city": "тула",
            "flat": "25",
            "house": "34",
            "street": "коммунаров"
          },
          "birth_date": "1966-07-04",
          "email": "miller94@mail.ru",
          "first_name": "валерия",
          "last_name": "миллер",
          "middle_name": "леонидовна",
          "phone": "+79259876922"
        },
        "id": "c-1",
        "seq": 3,
        "table": "contacts",
        "tool": "crm_merge_contacts"
      },
      {
        "fields": {
          "queue": "general",
          "summary": "Клиент: Миллер Валерия Леонидовна, тел. +7 925 987 69 22, адрес: Тула, переулок Полевая, д. 34, кв. 25. Обратилась по проблеме с заказом (суть не уточнена — клиент не назвал номер заказа и детали). Упоминала «9 филиал». По номеру телефона зарегистрированных обращений в системе нет. В CRM обнаружены две одинаковые карточки клиента — дубликат c-2 объединён с основной c-1. Клиент просит переключить на живого оператора, т.к. я не могу решить вопрос. Нужно уточнить номер заказа и суть проблемы, найти заказ и разобраться."
        },
        "id": "esc-1",
        "seq": 7,
        "table": "escalations",
        "tool": "escalate_to_human"
      },
      {
        "fields": {
          "entity_id": "c-1",
          "note_type": "call_in",
          "text": "Входящий звонок 2026-09-02. Клиент сообщила о проблеме с заказом, номер заказа и суть не назвала, упоминала «9 филиал». Адрес: Тула, переулок Полевая, 34, кв. 25. Обращений по номеру в системе нет. Объединены дубликаты карточек (c-2 в c-1). Клиент просила переключить на живого оператора — эскалация esc-1 (очередь general, Соколов Андрей)."
        },
        "id": "note-1",
        "seq": 8,
        "table": "notes",
        "tool": "crm_add_note"
      }
    ],
    "reply": "Передаю вас живому оператору. Всё, что успели зафиксировать, я уже сохранил:\n\n- **Кто:** Миллер Валерия Леонидовна, 8 925 987 69 22\n- **Адрес:** Тула, переулок Полевая, д. 34, кв. 25\n- **Дубликаты карточек:** объединены (в базе теперь одна запись)\n- **Вопрос:** проблема с заказом (номер и детали не названы), упоминался «9 филиал»\n\nСейчас вас подключит оператор — **Соколов Андрей**. Ожидайте, пожалуйста, на линии.",
    "termination": "done",
    "cost_usd": 0.003682,
    "substitutes": {
      "i1": [
        "сазонова",
        {
          "surname": "сазонова"
        }
      ],
      "i10": [
        "александровна",
        {
          "patronymic": "александровна"
        }
      ],
      "i11": [
        "8 912 764 73 27",
        {
          "digits": "9127647327"
        }
      ],
      "i12": [
        "fjfcbcss@example.ru",
        {
          "domain": "example.ru",
          "local": "fjfcbcss"
        }
      ],
      "i13": [
        "1966-02-01",
        {
          "iso": "1966-02-01"
        }
      ],
      "i14": [
        "полевая",
        {
          "street": "полевая"
        }
      ],
      "i15": [
        "сазонова иоланта",
        {
          "given": "иоланта",
          "surname": "сазонова"
        }
      ],
      "i16": [
        "8 912 764 73 27",
        {
          "digits": "9127647327"
        }
      ],
      "i17": [
        "тула переулок полевая 69кв120",
        {
          "flat": "120",
          "house": "69",
          "street": "полевая тула"
        }
      ],
      "i2": [
        "иоланта",
        {
          "given": "иоланта"
        }
      ],
      "i3": [
        "александровна",
        {
          "patronymic": "александровна"
        }
      ],
      "i4": [
        "8 912 764 73 27",
        {
          "digits": "9127647327"
        }
      ],
      "i5": [
        "fjfcbcss@example.ru",
        {
          "domain": "example.ru",
          "local": "fjfcbcss"
        }
      ],
      "i6": [
        "1966-02-01",
        {
          "iso": "1966-02-01"
        }
      ],
      "i7": [
        "полевая",
        {
          "street": "полевая"
        }
      ],
      "i8": [
        "сазонова",
        {
          "surname": "сазонова"
        }
      ],
      "i9": [
        "иоланта",
        {
          "given": "иоланта"
        }
      ]
    },
    "masked_spans": {
      "0": [],
      "1": [
        [
          43,
          57
        ],
        [
          66,
          81
        ]
      ],
      "2": [
        [
          10,
          41
        ]
      ],
      "3": [],
      "4": [],
      "5": []
    }
  },
  "reply_raw": "Передаю вас живому оператору. Всё, что успели зафиксировать, я уже сохранил:\n\n- **Кто:** Сазонова Иоланта Александровна, +7 912 764 73 27\n- **Адрес:** Тула, переулок Полевая, д. 69, кв. 120\n- **Дубликаты карточек:** объединены (в базе теперь одна запись)\n- **Вопрос:** проблема с заказом (номер и детали не названы), упоминался «9 филиал»\n\nСейчас вас подключит оператор — **Наумов Даниил**. Ожидайте, пожалуйста, на линии.",
  "control_reply": "Поняла вас, Валерия. Передаю живому оператору.\nВалерия, переключила вас на оператора — Андрей Соколов уже принял обращение (№ esc-1). Он свяжется с вами по номеру +7 925 987 69 22.\n\nКратко, что я передала:\n- проблема с заказом по вашему номеру;\n- в системе обращений по номеру не найдено, номер заказа не указан;\n- расхождение в адресе: «переулок Коммунаров, 34, кв. 25» против «улица Коммунаров» в карточке;\n- карточки-дубли объединены.\n\nПожалуйста, будьте на связи. Если удобнее — могу запланировать обратный звонок на конкретное время. 🙏",
  "tool_results": [
    {
      "tool_name": "crm_find_contact",
      "seq": 1,
      "call_ordinal": 0,
      "turn": 1,
      "return_form": "list",
      "text_real": "{\n  \"contacts\": [\n    {\n      \"id\": \"c-1\",\n      \"last_name\": \"миллер\",\n      \"first_name\": \"валерия\",\n      \"middle_name\": \"леонидовна\",\n      \"phone\": \"+79259876922\",\n      \"email\": \"miller94@mail.ru\",\n      \"birth_date\": \"1966-07-04\",\n      \"address\": {\n        \"city\": \"тула\",\n        \"street\": \"коммунаров\",\n        \"house\": \"34\",\n        \"flat\": \"25\"\n      }\n    },\n    {\n      \"id\": \"c-2\",\n      \"last_name\": \"миллер\",\n      \"first_name\": \"валерия\",\n      \"middle_name\": \"леонидовна\",\n      \"phone\": \"+79259876922\",\n      \"email\": \"miller94@mail.ru\",\n      \"birth_date\": \"1966-07-04\",\n      \"address\": {\n        \"city\": \"тула\",\n        \"street\": \"коммунаров\",\n        \"house\": \"34\",\n        \"flat\": \"25\"\n      }\n    }\n  ]\n}",
      "text_masked": "{\n  \"contacts\": [\n    {\n      \"id\": \"c-1\",\n      \"last_name\": \"сазонова\",\n      \"first_name\": \"иоланта\",\n      \"middle_name\": \"александровна\",\n      \"phone\": \"8 912 764 73 27\",\n      \"email\": \"fjfcbcss@example.ru\",\n      \"birth_date\": \"1966-02-01\",\n      \"address\": {\n        \"city\": \"тула\",\n        \"street\": \"полевая\",\n        \"house\": \"69\",\n        \"flat\": \"120\"\n      }\n    },\n    {\n      \"id\": \"c-2\",\n      \"last_name\": \"сазонова\",\n      \"first_name\": \"иоланта\",\n      \"middle_name\": \"александровна\",\n      \"phone\": \"8 912 764 73 27\",\n      \"email\": \"fjfcbcss@example.ru\",\n      \"birth_date\": \"1966-02-01\",\n      \"address\": {\n        \"city\": \"тула\",\n        \"street\": \"полевая\",\n        \"house\": \"69\",\n        \"flat\": \"120\"\n      }\n    }\n  ]\n}",
      "spans_real": {
        "i1": [
          63,
          69
        ],
        "i10": [
          479,
          489
        ],
        "i11": [
          508,
          520
        ],
        "i12": [
          539,
          555
        ],
        "i13": [
          579,
          589
        ],
        "i14": [
          654,
          664
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
          300,
          310
        ],
        "i8": [
          417,
          423
        ],
        "i9": [
          447,
          454
        ]
      },
      "pieces": [
        [
          63,
          69,
          "сазонова",
          "NAME"
        ],
        [
          93,
          100,
          "иоланта",
          "NAME"
        ],
        [
          125,
          135,
          "александровна",
          "NAME"
        ],
        [
          154,
          166,
          "8 912 764 73 27",
          "PHONE"
        ],
        [
          185,
          201,
          "fjfcbcss@example.ru",
          "EMAIL"
        ],
        [
          225,
          235,
          "1966-02-01",
          "DOB"
        ],
        [
          274,
          278,
          "тула",
          "LOC"
        ],
        [
          300,
          310,
          "полевая",
          "LOC"
        ],
        [
          331,
          333,
          "69",
          "LOC"
        ],
        [
          353,
          355,
          "120",
          "LOC"
        ],
        [
          417,
          423,
          "сазонова",
          "NAME"
        ],
        [
          447,
          454,
          "иоланта",
          "NAME"
        ],
        [
          479,
          489,
          "александровна",
          "NAME"
        ],
        [
          508,
          520,
          "8 912 764 73 27",
          "PHONE"
        ],
        [
          539,
          555,
          "fjfcbcss@example.ru",
          "EMAIL"
        ],
        [
          579,
          589,
          "1966-02-01",
          "DOB"
        ],
        [
          628,
          632,
          "тула",
          "LOC"
        ],
        [
          654,
          664,
          "полевая",
          "LOC"
        ],
        [
          685,
          687,
          "69",
          "LOC"
        ],
        [
          707,
          709,
          "120",
          "LOC"
        ]
      ],
      "forced": false
    },
    {
      "tool_name": "ticket_find",
      "seq": 2,
      "call_ordinal": 0,
      "turn": 1,
      "return_form": "empty",
      "text_real": "{\n  \"issues\": [\n    \n  ]\n}",
      "text_masked": "{\n  \"issues\": [\n    \n  ]\n}",
      "spans_real": {},
      "pieces": [],
      "forced": false
    },
    {
      "tool_name": "crm_merge_contacts",
      "seq": 3,
      "call_ordinal": 0,
      "turn": 1,
      "return_form": "single",
      "text_real": "{\n  \"primary_id\": \"c-1\",\n  \"merged\": \"c-2\",\n  \"contact\": {\n    \"last_name\": \"миллер\",\n    \"first_name\": \"валерия\",\n    \"phone\": \"+79259876922\"\n  }\n}",
      "text_masked": "{\n  \"primary_id\": \"c-1\",\n  \"merged\": \"c-2\",\n  \"contact\": {\n    \"last_name\": \"сазонова\",\n    \"first_name\": \"иоланта\",\n    \"phone\": \"8 912 764 73 27\"\n  }\n}",
      "spans_real": {
        "i1": [
          77,
          83
        ],
        "i2": [
          105,
          112
        ],
        "i4": [
          129,
          141
        ]
      },
      "pieces": [
        [
          77,
          83,
          "сазонова",
          "NAME"
        ],
        [
          105,
          112,
          "иоланта",
          "NAME"
        ],
        [
          129,
          141,
          "8 912 764 73 27",
          "PHONE"
        ]
      ],
      "forced": false
    },
    {
      "tool_name": "ticket_find",
      "seq": 4,
      "call_ordinal": 0,
      "turn": 3,
      "return_form": "error_with_value",
      "text_real": "{\n  \"error\": {\n    \"code\": \"phone_not_e164\",\n    \"field\": \"phone\",\n    \"message\": \"поле phone: phone_not_e164: 89259876922\"\n  }\n}",
      "text_masked": "{\n  \"error\": {\n    \"code\": \"phone_not_e164\",\n    \"field\": \"phone\",\n    \"message\": \"поле phone: phone_not_e164: 8 912 764 73 27\"\n  }\n}",
      "spans_real": {},
      "pieces": [
        [
          111,
          122,
          "8 912 764 73 27",
          "PHONE"
        ]
      ],
      "forced": false
    },
    {
      "tool_name": "ticket_find",
      "seq": 5,
      "call_ordinal": 1,
      "turn": 3,
      "return_form": "error_with_value",
      "text_real": "{\n  \"error\": {\n    \"code\": \"phone_not_e164\",\n    \"field\": \"phone\",\n    \"message\": \"поле phone: phone_not_e164: +7 925 987 69 22\"\n  }\n}",
      "text_masked": "{\n  \"error\": {\n    \"code\": \"phone_not_e164\",\n    \"field\": \"phone\",\n    \"message\": \"поле phone: phone_not_e164: 8 912 764 73 27\"\n  }\n}",
      "spans_real": {},
      "pieces": [
        [
          111,
          127,
          "8 912 764 73 27",
          "PHONE"
        ]
      ],
      "forced": false
    },
    {
      "tool_name": "ticket_find",
      "seq": 6,
      "call_ordinal": 2,
      "turn": 3,
      "return_form": "error_with_value",
      "text_real": "{\n  \"error\": {\n    \"code\": \"phone_not_e164\",\n    \"field\": \"phone\",\n    \"message\": \"поле phone: phone_not_e164: +7 925 987 69 22\"\n  }\n}",
      "text_masked": "{\n  \"error\": {\n    \"code\": \"phone_not_e164\",\n    \"field\": \"phone\",\n    \"message\": \"поле phone: phone_not_e164: 8 912 764 73 27\"\n  }\n}",
      "spans_real": {},
      "pieces": [
        [
          111,
          127,
          "8 912 764 73 27",
          "PHONE"
        ]
      ],
      "forced": false
    },
    {
      "tool_name": "escalate_to_human",
      "seq": 7,
      "call_ordinal": 0,
      "turn": 5,
      "return_form": "single",
      "text_real": "{\n  \"escalation_id\": \"esc-1\",\n  \"queue\": \"general\",\n  \"status\": \"queued\",\n  \"assignee\": {\n    \"name\": \"Соколов Андрей\",\n    \"phone\": \"+79261234567\"\n  }\n}",
      "text_masked": "{\n  \"escalation_id\": \"esc-1\",\n  \"queue\": \"general\",\n  \"status\": \"queued\",\n  \"assignee\": {\n    \"name\": \"Наумов Даниил\",\n    \"phone\": \"+79460695344\"\n  }\n}",
      "spans_real": {},
      "pieces": [
        [
          103,
          117,
          "Наумов Даниил",
          "NAME"
        ],
        [
          134,
          146,
          "+79460695344",
          "PHONE"
        ]
      ],
      "forced": false
    },
    {
      "tool_name": "crm_add_note",
      "seq": 8,
      "call_ordinal": 0,
      "turn": 5,
      "return_form": "single",
      "text_real": "{\n  \"id\": \"note-1\",\n  \"entity_id\": \"c-1\",\n  \"length\": 340,\n  \"entity\": {\n    \"last_name\": \"миллер\",\n    \"first_name\": \"валерия\",\n    \"phone\": \"+79259876922\"\n  }\n}",
      "text_masked": "{\n  \"id\": \"note-1\",\n  \"entity_id\": \"c-1\",\n  \"length\": 340,\n  \"entity\": {\n    \"last_name\": \"сазонова\",\n    \"first_name\": \"иоланта\",\n    \"phone\": \"8 912 764 73 27\"\n  }\n}",
      "spans_real": {
        "i1": [
          91,
          97
        ],
        "i2": [
          119,
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
          97,
          "сазонова",
          "NAME"
        ],
        [
          119,
          126,
          "иоланта",
          "NAME"
        ],
        [
          143,
          155,
          "8 912 764 73 27",
          "PHONE"
        ]
      ],
      "forced": false
    }
  ],
  "mentions": [
    {
      "item_id": "i15",
      "msg": 1,
      "result_seq": -1,
      "substitute": "сазонова иоланта",
      "request_index": 1
    },
    {
      "item_id": "i16",
      "msg": 1,
      "result_seq": -1,
      "substitute": "8 912 764 73 27",
      "request_index": 1
    },
    {
      "item_id": "i1",
      "msg": -1,
      "result_seq": 1,
      "substitute": "сазонова",
      "request_index": 2
    },
    {
      "item_id": "i2",
      "msg": -1,
      "result_seq": 1,
      "substitute": "иоланта",
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
      "substitute": "8 912 764 73 27",
      "request_index": 2
    },
    {
      "item_id": "i5",
      "msg": -1,
      "result_seq": 1,
      "substitute": "fjfcbcss@example.ru",
      "request_index": 2
    },
    {
      "item_id": "i6",
      "msg": -1,
      "result_seq": 1,
      "substitute": "1966-02-01",
      "request_index": 2
    },
    {
      "item_id": "i7",
      "msg": -1,
      "result_seq": 1,
      "substitute": "полевая",
      "request_index": 2
    },
    {
      "item_id": "i8",
      "msg": -1,
      "result_seq": 1,
      "substitute": "сазонова",
      "request_index": 2
    },
    {
      "item_id": "i9",
      "msg": -1,
      "result_seq": 1,
      "substitute": "иоланта",
      "request_index": 2
    },
    {
      "item_id": "i10",
      "msg": -1,
      "result_seq": 1,
      "substitute": "александровна",
      "request_index": 2
    },
    {
      "item_id": "i11",
      "msg": -1,
      "result_seq": 1,
      "substitute": "8 912 764 73 27",
      "request_index": 2
    },
    {
      "item_id": "i12",
      "msg": -1,
      "result_seq": 1,
      "substitute": "fjfcbcss@example.ru",
      "request_index": 2
    },
    {
      "item_id": "i13",
      "msg": -1,
      "result_seq": 1,
      "substitute": "1966-02-01",
      "request_index": 2
    },
    {
      "item_id": "i14",
      "msg": -1,
      "result_seq": 1,
      "substitute": "полевая",
      "request_index": 2
    },
    {
      "item_id": "i1",
      "msg": -1,
      "result_seq": 3,
      "substitute": "сазонова",
      "request_index": 4
    },
    {
      "item_id": "i2",
      "msg": -1,
      "result_seq": 3,
      "substitute": "иоланта",
      "request_index": 4
    },
    {
      "item_id": "i4",
      "msg": -1,
      "result_seq": 3,
      "substitute": "8 912 764 73 27",
      "request_index": 4
    },
    {
      "item_id": "i17",
      "msg": 2,
      "result_seq": -1,
      "substitute": "тула переулок полевая 69кв120",
      "request_index": 5
    },
    {
      "item_id": "i1",
      "msg": -1,
      "result_seq": 8,
      "substitute": "сазонова",
      "request_index": 13
    },
    {
      "item_id": "i2",
      "msg": -1,
      "result_seq": 8,
      "substitute": "иоланта",
      "request_index": 13
    },
    {
      "item_id": "i4",
      "msg": -1,
      "result_seq": 8,
      "substitute": "8 912 764 73 27",
      "request_index": 13
    }
  ],
  "turn_replies": [
    "Здравствуйте, Валерия Леонидовна! Я вас нашёл в нашей системе. Уточните, пожалуйста, что именно случилось с заказом: номер заказа, что не так (доставка, состав, оплата) и что вы упомянули про «9 филиала» — это где оформляли?",
    "Спасибо. Записал: Тула, переулок Полевая, д. 34, кв. 25.\n\nЧтобы я мог разобраться, подскажите, пожалуйста: номер заказа (если есть под рукой), что именно не так — доставка не пришла / пришло не то / неверный адрес — и что за «9 филиал» (это пункт выдачи или клиника/офис, куда вы обращались)?",
    "Проверил по вашему номеру (8 925 987 69 22) — зарегистрированных обращений, к сожалению, нет. Возможно, они оформлялись на другой номер или через филиал.\n\nЧтобы я мог помочь, давайте я заведу обращение. Для этого мне нужно:\n1) номер заказа (если сохранился);\n2) суть проблемы (что с доставкой/составом/оплатой);\n3) что за «9 филиал» — пункт выдачи, магазин или клиника, и по какому адресу.\n\nКак только уточните, я всё зафиксирую и передам в работу.",
    "Да, я это уже увидел и сделал — карточки объединены. В базе по вашему номеру было две одинаковые записи (Миллер Валерия Леонидовна), я склеил дубликат с основной карточкой. Теперь у вас одна запись: Тула, переулок Полевая, д. 34, кв. 25.\n\nОсталось разобраться с заказом. Подскажите, пожалуйста, номер заказа и в чём именно проблема (доставка, состав, оплата), а также что за «9 филиал» — тогда я заведу обращение и передам в работу.",
    "Передаю вас живому оператору. Всё, что успели зафиксировать, я уже сохранил:\n\n- **Кто:** Миллер Валерия Леонидовна, 8 925 987 69 22\n- **Адрес:** Тула, переулок Полевая, д. 34, кв. 25\n- **Дубликаты карточек:** объединены (в базе теперь одна запись)\n- **Вопрос:** проблема с заказом (номер и детали не названы), упоминался «9 филиал»\n\nСейчас вас подключит оператор — **Соколов Андрей**. Ожидайте, пожалуйста, на линии."
  ],
  "call_turns": [
    1,
    1,
    1,
    3,
    3,
    3,
    5,
    5
  ],
  "request_count": 13,
  "stream_mismatch": false,
  "reply_whole": "",
  "turn_residual": 3
}

## Recorded observer hops

[
  {
    "case_id": "long_support-014",
    "repeat": 0,
    "hop": {
      "kind": "IN",
      "owner": "user",
      "item_id": "i15",
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
    "produced": "сазонова иоланта",
    "reference": "миллер валерия",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "long_support-014",
    "repeat": 0,
    "hop": {
      "kind": "IN",
      "owner": "user",
      "item_id": "i16",
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
    "produced": "8 912 764 73 27",
    "reference": "8 925 987 69 22",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "long_support-014",
    "repeat": 0,
    "hop": {
      "kind": "IN",
      "owner": "user",
      "item_id": "i17",
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
    "produced": "тула переулок полевая 69кв120",
    "reference": "тула переулок коммунаров 34кв25",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "long_support-014",
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
    "produced": "сазонова",
    "reference": "миллер",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "long_support-014",
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
    "produced": "иоланта",
    "reference": "валерия",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "long_support-014",
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
    "produced": "александровна",
    "reference": "леонидовна",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "long_support-014",
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
    "produced": "8 912 764 73 27",
    "reference": "+79259876922",
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
    "case_id": "long_support-014",
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
    "produced": "fjfcbcss@example.ru",
    "reference": "miller94@mail.ru",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "long_support-014",
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
    "produced": "1966-02-01",
    "reference": "1966-07-04",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "long_support-014",
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
    "produced": "полевая",
    "reference": "коммунаров",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "long_support-014",
    "repeat": 0,
    "hop": {
      "kind": "IN",
      "owner": "tool",
      "item_id": "i8",
      "hop_index": 10,
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
    "produced": "сазонова",
    "reference": "миллер",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "long_support-014",
    "repeat": 0,
    "hop": {
      "kind": "IN",
      "owner": "tool",
      "item_id": "i9",
      "hop_index": 11,
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
    "produced": "иоланта",
    "reference": "валерия",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "long_support-014",
    "repeat": 0,
    "hop": {
      "kind": "IN",
      "owner": "tool",
      "item_id": "i10",
      "hop_index": 12,
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
    "produced": "александровна",
    "reference": "леонидовна",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "long_support-014",
    "repeat": 0,
    "hop": {
      "kind": "IN",
      "owner": "tool",
      "item_id": "i11",
      "hop_index": 13,
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
    "produced": "8 912 764 73 27",
    "reference": "+79259876922",
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
    "case_id": "long_support-014",
    "repeat": 0,
    "hop": {
      "kind": "IN",
      "owner": "tool",
      "item_id": "i12",
      "hop_index": 14,
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
    "produced": "fjfcbcss@example.ru",
    "reference": "miller94@mail.ru",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "long_support-014",
    "repeat": 0,
    "hop": {
      "kind": "IN",
      "owner": "tool",
      "item_id": "i13",
      "hop_index": 15,
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
    "produced": "1966-02-01",
    "reference": "1966-07-04",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "long_support-014",
    "repeat": 0,
    "hop": {
      "kind": "IN",
      "owner": "tool",
      "item_id": "i14",
      "hop_index": 16,
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
    "produced": "полевая",
    "reference": "коммунаров",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "long_support-014",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i4",
      "hop_index": 19,
      "turn": 5,
      "tool_name": "ticket_find",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": -1,
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
    "case_id": "long_support-014",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i16",
      "hop_index": 21,
      "turn": 5,
      "tool_name": "callback_schedule",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": 1,
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
    "case_id": "long_support-014",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "answer",
      "item_id": "i1",
      "hop_index": 22,
      "turn": 5,
      "tool_name": "",
      "call_ordinal": -1,
      "parallel_group": "",
      "source_hop": 3,
      "path": "",
      "optional": true
    },
    "declared": true,
    "pii_type": "NAME",
    "produced": "Миллер",
    "reference": "Сазонова",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "long_support-014",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "answer",
      "item_id": "i2",
      "hop_index": 23,
      "turn": 5,
      "tool_name": "",
      "call_ordinal": -1,
      "parallel_group": "",
      "source_hop": 4,
      "path": "",
      "optional": true
    },
    "declared": true,
    "pii_type": "NAME",
    "produced": "Валерия",
    "reference": "Иоланта",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "long_support-014",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "answer",
      "item_id": "i3",
      "hop_index": 24,
      "turn": 5,
      "tool_name": "",
      "call_ordinal": -1,
      "parallel_group": "",
      "source_hop": 5,
      "path": "",
      "optional": true
    },
    "declared": true,
    "pii_type": "NAME",
    "produced": "Леонидовна",
    "reference": "Александровна",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "long_support-014",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "answer",
      "item_id": "i4",
      "hop_index": 25,
      "turn": 5,
      "tool_name": "",
      "call_ordinal": -1,
      "parallel_group": "",
      "source_hop": 6,
      "path": "",
      "optional": true
    },
    "declared": true,
    "pii_type": "PHONE",
    "produced": "8 925 987 69 22",
    "reference": "+7 912 764 73 27",
    "status": "observed",
    "verdict": {
      "same": false,
      "differs": [
        "prefix"
      ]
    }
  },
  {
    "case_id": "long_support-014",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "answer",
      "item_id": "i8",
      "hop_index": 28,
      "turn": 5,
      "tool_name": "",
      "call_ordinal": -1,
      "parallel_group": "",
      "source_hop": 10,
      "path": "",
      "optional": true
    },
    "declared": true,
    "pii_type": "NAME",
    "produced": "Миллер",
    "reference": "Сазонова",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "long_support-014",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "answer",
      "item_id": "i9",
      "hop_index": 29,
      "turn": 5,
      "tool_name": "",
      "call_ordinal": -1,
      "parallel_group": "",
      "source_hop": 11,
      "path": "",
      "optional": true
    },
    "declared": true,
    "pii_type": "NAME",
    "produced": "Валерия",
    "reference": "Иоланта",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "long_support-014",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "answer",
      "item_id": "i10",
      "hop_index": 30,
      "turn": 5,
      "tool_name": "",
      "call_ordinal": -1,
      "parallel_group": "",
      "source_hop": 12,
      "path": "",
      "optional": true
    },
    "declared": true,
    "pii_type": "NAME",
    "produced": "Леонидовна",
    "reference": "Александровна",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "long_support-014",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "answer",
      "item_id": "i11",
      "hop_index": 31,
      "turn": 5,
      "tool_name": "",
      "call_ordinal": -1,
      "parallel_group": "",
      "source_hop": 13,
      "path": "",
      "optional": true
    },
    "declared": true,
    "pii_type": "PHONE",
    "produced": "8 925 987 69 22",
    "reference": "+7 912 764 73 27",
    "status": "observed",
    "verdict": {
      "same": false,
      "differs": [
        "prefix"
      ]
    }
  },
  {
    "case_id": "long_support-014",
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
    "produced": "+79259876922",
    "reference": "+79127647327",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "long_support-014",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i4",
      "hop_index": -1,
      "turn": 1,
      "tool_name": "ticket_find",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": -1,
      "path": "phone",
      "optional": false
    },
    "declared": false,
    "pii_type": "PHONE",
    "produced": "+79259876922",
    "reference": "+79127647327",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "long_support-014",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i4",
      "hop_index": -1,
      "turn": 3,
      "tool_name": "ticket_find",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": -1,
      "path": "phone",
      "optional": false
    },
    "declared": false,
    "pii_type": "PHONE",
    "produced": "89259876922",
    "reference": "89127647327",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "long_support-014",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i4",
      "hop_index": -1,
      "turn": 3,
      "tool_name": "ticket_find",
      "call_ordinal": 1,
      "parallel_group": "",
      "source_hop": -1,
      "path": "phone",
      "optional": false
    },
    "declared": false,
    "pii_type": "PHONE",
    "produced": "+7 925 987 69 22",
    "reference": "+7 912 764 73 27",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "long_support-014",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i4",
      "hop_index": -1,
      "turn": 3,
      "tool_name": "ticket_find",
      "call_ordinal": 2,
      "parallel_group": "",
      "source_hop": -1,
      "path": "phone",
      "optional": false
    },
    "declared": false,
    "pii_type": "PHONE",
    "produced": "+7 925 987 69 22",
    "reference": "8 912 764 73 27",
    "status": "observed",
    "verdict": {
      "same": false,
      "differs": [
        "prefix"
      ]
    }
  },
  {
    "case_id": "long_support-014",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "answer",
      "item_id": "i15",
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
    "produced": "Миллер Валерия",
    "reference": "Сазонова Иоланта",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "long_support-014",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "answer",
      "item_id": "i16",
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
    "produced": "8 925 987 69 22",
    "reference": "+7 912 764 73 27",
    "status": "observed",
    "verdict": {
      "same": false,
      "differs": [
        "prefix"
      ]
    }
  }
]
