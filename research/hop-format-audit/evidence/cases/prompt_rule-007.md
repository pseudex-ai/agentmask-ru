# prompt_rule-007 | source C | repeat 0

Synthetic benchmark evidence. Verbatim serialized fields; no inferred verdicts.

## Case specification

{
  "base": {
    "id": "prompt_rule-007",
    "kind": "prompt_rule",
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
    "cluster": "PHONE:9226866114",
    "conversation_id": "",
    "now": "2026-09-02",
    "messages": [
      {
        "role": "system",
        "content": "Ты оператор службы доставки. Оформляй заказы и вызовы курьера инструментами, переспрашивай только то, чего не хватает для вызова. Вес посылки, если не назван, — 1000 г; почтовый индекс подбери сам по городу получателя. Сегодня 2026-09-02. Заказы с номером дома больше 100 не оформляем — это промзона, туда курьер не ездит.",
        "source": null,
        "name": ""
      },
      {
        "role": "user",
        "content": "оформите доставкуу на тарасова алла телефон восем девятьсот двадцать два шестьсот восемьдесят шесть шестьсот одиннадцать четыре и ещё закааз семьсот девяносто пять",
        "source": null,
        "name": ""
      },
      {
        "role": "user",
        "content": "адрес ростов-на-дону проспект добролюбова сто тридцать четыыре квартира один",
        "source": null,
        "name": ""
      },
      {
        "role": "user",
        "content": "всё оформляйте и смс на этот номер",
        "source": null,
        "name": ""
      }
    ],
    "tools": [
      "delivery_create_order",
      "courier_book",
      "crm_find_contact",
      "notify_sms",
      "delivery_quote",
      "crm_add_note"
    ],
    "seed_records": [
      {
        "id": "c-1",
        "table": "contacts",
        "fields": {
          "last_name": "тарасова",
          "first_name": "алла",
          "middle_name": "анатольевна",
          "phone": "+79226866114",
          "email": "tarasova73@yandex.ru",
          "birth_date": "1997-04-08",
          "address": {
            "city": "ростов-на-дону",
            "street": "добролюбова",
            "house": "134",
            "flat": "1"
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
        "identity": "p7",
        "value": "тарасова",
        "canonical": "тарасова",
        "parts": {
          "surname": "тарасова",
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
        "identity": "p7",
        "value": "алла",
        "canonical": "алла",
        "parts": {
          "given": "алла",
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
        "identity": "p7",
        "value": "анатольевна",
        "canonical": "анатольевна",
        "parts": {
          "patronymic": "анатольевна",
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
        "identity": "p7",
        "value": "+79226866114",
        "canonical": "+79226866114",
        "parts": {
          "digits": "9226866114"
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
        "identity": "p7",
        "value": "tarasova73@yandex.ru",
        "canonical": "tarasova73@yandex.ru",
        "parts": {
          "local": "tarasova73",
          "domain": "yandex.ru"
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
        "identity": "p7",
        "value": "1997-04-08",
        "canonical": "1997-04-08",
        "parts": {
          "iso": "1997-04-08"
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
        "identity": "p7.home",
        "value": "добролюбова",
        "canonical": "добролюбова",
        "parts": {
          "street": "добролюбова",
          "street_type": "проспект",
          "house": "134",
          "flat": "1",
          "city": "ростов-на-дону"
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
        "identity": "p7",
        "value": "тарасова алла",
        "canonical": "тарасова алла",
        "parts": {
          "surname": "тарасова",
          "given": "алла",
          "gender": "f"
        },
        "where": {
          "kind": "message",
          "msg": 1,
          "start": 22,
          "end": 35,
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
        "identity": "p7",
        "value": "восем девятьсот двадцать два шестьсот восемьдесят шесть шестьсот одиннадцать четыре",
        "canonical": "+79226866114",
        "parts": {
          "digits": "9226866114"
        },
        "where": {
          "kind": "message",
          "msg": 1,
          "start": 44,
          "end": 127,
          "record": "",
          "path": ""
        },
        "duty": "required",
        "spoken": true,
        "stale": false
      },
      {
        "id": "i10",
        "type": "LOC",
        "identity": "p7.home",
        "value": "ростов-на-дону проспект добролюбова сто тридцать четыыре квартира один",
        "canonical": "ростов-на-дону проспект добролюбова сто тридцать четыыре квартира один",
        "parts": {
          "street": "добролюбова",
          "street_type": "проспект",
          "house": "134",
          "flat": "1",
          "city": "ростов-на-дону"
        },
        "where": {
          "kind": "message",
          "msg": 2,
          "start": 6,
          "end": 76,
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
        "value": "семьсот девяносто пять",
        "start": 141,
        "end": 163,
        "msg": 1,
        "family": "order_number",
        "why": "номер заказа — не персональные данные; продиктованный вслух он маскировался целиком, и это уже отгружалось"
      }
    ],
    "expects": {
      "reachable_tools": [
        "crm_find_contact",
        "delivery_quote",
        "delivery_create_order",
        "notify_sms"
      ],
      "primary_identity": "p7",
      "must_contain": [],
      "must_not_contain": [],
      "validate_types": []
    },
    "trace": [
      {
        "msg": 1,
        "key": "",
        "start": 0,
        "end": 8,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 1,
        "key": "",
        "start": 8,
        "end": 9,
        "origin": "literal"
      },
      {
        "msg": 1,
        "key": "",
        "start": 9,
        "end": 18,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 1,
        "key": "",
        "start": 18,
        "end": 19,
        "origin": "literal"
      },
      {
        "msg": 1,
        "key": "",
        "start": 19,
        "end": 21,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 1,
        "key": "",
        "start": 21,
        "end": 22,
        "origin": "literal"
      },
      {
        "msg": 1,
        "key": "n1",
        "start": 22,
        "end": 35,
        "origin": "value:n1"
      },
      {
        "msg": 1,
        "key": "",
        "start": 35,
        "end": 36,
        "origin": "literal"
      },
      {
        "msg": 1,
        "key": "",
        "start": 36,
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
        "end": 127,
        "origin": "value:ph1"
      },
      {
        "msg": 1,
        "key": "",
        "start": 127,
        "end": 128,
        "origin": "literal"
      },
      {
        "msg": 1,
        "key": "",
        "start": 128,
        "end": 129,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 1,
        "key": "",
        "start": 129,
        "end": 130,
        "origin": "literal"
      },
      {
        "msg": 1,
        "key": "",
        "start": 130,
        "end": 133,
        "origin": "chunk:noisy_word"
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
        "end": 140,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 1,
        "key": "",
        "start": 140,
        "end": 141,
        "origin": "literal"
      },
      {
        "msg": 1,
        "key": "neg1",
        "start": 141,
        "end": 163,
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
        "key": "a1",
        "start": 6,
        "end": 76,
        "origin": "value:a1"
      },
      {
        "msg": 3,
        "key": "",
        "start": 0,
        "end": 3,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 3,
        "key": "",
        "start": 3,
        "end": 4,
        "origin": "literal"
      },
      {
        "msg": 3,
        "key": "",
        "start": 4,
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
        "msg": 3,
        "key": "",
        "start": 28,
        "end": 29,
        "origin": "literal"
      },
      {
        "msg": 3,
        "key": "",
        "start": 29,
        "end": 34,
        "origin": "chunk:noisy_word"
      }
    ],
    "note": "правило доставки в системном промпте; подмена может его нарушить и агент откажет там, где отказывать не следовало"
  },
  "behaviour": "branching",
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
      "tool_name": "delivery_create_order",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": 0,
      "path": "recipient.name",
      "optional": false
    },
    {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i9",
      "hop_index": 13,
      "turn": 3,
      "tool_name": "delivery_create_order",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": 1,
      "path": "recipient.phones[].number",
      "optional": false
    },
    {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i10",
      "hop_index": 14,
      "turn": 3,
      "tool_name": "delivery_create_order",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": 2,
      "path": "to_location.city",
      "optional": false
    },
    {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i10",
      "hop_index": 15,
      "turn": 3,
      "tool_name": "delivery_create_order",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": 2,
      "path": "to_location.address",
      "optional": false
    },
    {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i9",
      "hop_index": 16,
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
      "item_id": "i2",
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
      "item_id": "i3",
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
      "item_id": "i4",
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
      "item_id": "i5",
      "hop_index": 21,
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
      "hop_index": 22,
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
  "branch": {
    "probe_tool": "crm_find_contact",
    "seed_present": true,
    "then_tool": "delivery_create_order",
    "else_tool": "courier_book"
  },
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
    "case_id": "prompt_rule-007",
    "arm": "I",
    "repeat": 0,
    "calls": [
      {
        "name": "crm_find_contact",
        "written": {
          "query": {
            "phone": "+79842990029"
          }
        },
        "restored": {
          "query": {
            "phone": "восем девятьсот двадцать два шестьсот восемьдесят шесть шестьсот одиннадцать четыре"
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
            "last_name": "Уваров"
          }
        },
        "restored": {
          "query": {
            "last_name": "Тарасов"
          }
        },
        "residual": {},
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "query": {
            "last_name": "тарасов"
          }
        },
        "seq": 2
      },
      {
        "name": "crm_find_contact",
        "written": {
          "query": {
            "phone": "+79226866114"
          }
        },
        "restored": {
          "query": {
            "phone": "+79226866114"
          }
        },
        "residual": {},
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "query": {
            "phone": "+79226866114"
          }
        },
        "seq": 3
      },
      {
        "name": "crm_find_contact",
        "written": {
          "query": {
            "last_name": "павлюк"
          }
        },
        "restored": {
          "query": {
            "last_name": "тарасова"
          }
        },
        "residual": {},
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "query": {
            "last_name": "тарасова"
          }
        },
        "seq": 4
      },
      {
        "name": "crm_find_contact",
        "written": {
          "query": {
            "last_name": "уваров"
          }
        },
        "restored": {
          "query": {
            "last_name": "тарасов"
          }
        },
        "residual": {},
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "query": {
            "last_name": "тарасов"
          }
        },
        "seq": 5
      },
      {
        "name": "crm_find_contact",
        "written": {
          "query": {
            "phone": "+79842990029"
          }
        },
        "restored": {
          "query": {
            "phone": "+79226866114"
          }
        },
        "residual": {},
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "query": {
            "phone": "+79226866114"
          }
        },
        "seq": 6
      },
      {
        "name": "crm_find_contact",
        "written": {
          "query": {
            "phone": "+79001112233"
          }
        },
        "restored": {
          "query": {
            "phone": "+79001112233"
          }
        },
        "residual": {},
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "query": {
            "phone": "+79001112233"
          }
        },
        "seq": 7
      },
      {
        "name": "crm_find_contact",
        "written": {
          "query": {
            "last_name": "иванов"
          }
        },
        "restored": {
          "query": {
            "last_name": "иванов"
          }
        },
        "residual": {},
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "query": {
            "last_name": "иванов"
          }
        },
        "seq": 8
      },
      {
        "name": "notify_sms",
        "written": {
          "number": "+79842990029",
          "sign": "Dostavka",
          "text": "Здравствуйте! Оформить доставку на адрес: Ростов-на-Дону, Черёмуховый проспект, 104 не удалось — номер дома больше 100, это промзона, курьер туда не выезжает. Пожалуйста, укажите другой адрес (дом до 100 включительно), и мы оформим заказ."
        },
        "restored": {
          "number": "+79226866114",
          "sign": "Dostavka",
          "text": "Здравствуйте! Оформить доставку на адрес: Ростов-на-Дону, Добролюбова, 134 не удалось — номер дома больше 100, это промзона, курьер туда не выезжает. Пожалуйста, укажите другой адрес (дом до 100 включительно), и мы оформим заказ."
        },
        "residual": {},
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "number": "+79226866114",
          "sign": "Dostavka",
          "text": "Здравствуйте! Оформить доставку на адрес: Ростов-на-Дону, Добролюбова, 134 не удалось — номер дома больше 100, это промзона, курьер туда не выезжает. Пожалуйста, укажите другой адрес (дом до 100 включительно), и мы оформим заказ."
        },
        "seq": 9
      }
    ],
    "state": [
      {
        "fields": {
          "number": "+79226866114",
          "sign": "Dostavka",
          "text": "Здравствуйте! Оформить доставку на адрес: Ростов-на-Дону, Добролюбова, 134 не удалось — номер дома больше 100, это промзона, курьер туда не выезжает. Пожалуйста, укажите другой адрес (дом до 100 включительно), и мы оформим заказ."
        },
        "id": "sms-1",
        "seq": 9,
        "table": "sms",
        "tool": "notify_sms"
      }
    ],
    "reply": "Оформить заказ не получилось — и не получится, к сожалению: адрес **Ростов-на-Дону, ростов-на-дону проспект добролюбова сто тридцать четыыре** не подходит для доставки. Номер дома **134 больше 100**, это промзона, курьер туда не выезжает — такие заказы мы не оформляем.\n\nСМС на номер **+79226866114** я отправил: там указано, что оформить по этому адресу нельзя, и просьба прислать другой адрес (дом до 100 включительно).\n\nКак только дадите пригодный адрес — оформлю доставку сразу. Также напомню: номер +79226866114 в базе привязан к **Тарасова Алле Анатольевне**, а вы называете получателя **Тарасова Алла** — подтвердите, пожалуйста, верные ФИО и телефон, чтобы заказ ушёл правильно.",
    "termination": "done",
    "cost_usd": 0.01472,
    "substitutes": {
      "i1": [
        "павлюк",
        {
          "surname": "павлюк"
        }
      ],
      "i10": [
        "Ростов-На-Дону, Черёмуховый проспект 104, кв. 100",
        {
          "flat": "100",
          "house": "104",
          "street": "дону на ростов черемуховый"
        }
      ],
      "i2": [
        "иоланта",
        {
          "given": "иоланта"
        }
      ],
      "i3": [
        "олеговна",
        {
          "patronymic": "олеговна"
        }
      ],
      "i4": [
        "+79842990029",
        {
          "digits": "9842990029"
        }
      ],
      "i5": [
        "gyyinzef@example.ru",
        {
          "domain": "example.ru",
          "local": "gyyinzef"
        }
      ],
      "i6": [
        "1997-02-19",
        {
          "iso": "1997-02-19"
        }
      ],
      "i7": [
        "осиновая",
        {
          "street": "осиновая"
        }
      ],
      "i8": [
        "уварова тимура",
        {
          "given": "тимура",
          "surname": "уварова"
        }
      ],
      "i9": [
        "+79842990029",
        {
          "digits": "9842990029"
        }
      ]
    },
    "masked_spans": {
      "0": [],
      "1": [
        [
          22,
          35
        ],
        [
          44,
          127
        ]
      ],
      "2": [
        [
          6,
          76
        ]
      ],
      "3": []
    }
  },
  "reply_raw": "Оформить заказ не получилось — и не получится, к сожалению: адрес **Ростов-на-Дону, Черёмуховый проспект, 104** не подходит для доставки. Номер дома **104 больше 100**, это промзона, курьер туда не выезжает — такие заказы мы не оформляем.\n\nСМС на номер **+79842990029** я отправил: там указано, что оформить по этому адресу нельзя, и просьба прислать другой адрес (дом до 100 включительно).\n\nКак только дадите пригодный адрес — оформлю доставку сразу. Также напомню: номер +79842990029 в базе привязан к **Павлюк Иоланте Олеговне**, а вы называете получателя **Уварова Тимура** — подтвердите, пожалуйста, верные ФИО и телефон, чтобы заказ ушёл правильно.",
  "control_reply": "Не смогу этого сделать: дом 134 в промзоне, а заказы по адресам с номером дома больше 100 мы не оформляем — курьер туда не поедет. Это ограничение я обойти не могу, поэтому ни заказ, ни подтверждающую СМС отправить не получится.\n\nЧто можно сделать:\n1. Дать **другой адрес** с номером дома до 100 — оформлю доставку сразу и отправлю СМС на +7 922 686-61-14.\n2. Если подходящего адреса нет — заказ, к сожалению, оформить нельзя.\n\nЖду корректный адрес.",
  "tool_results": [
    {
      "tool_name": "crm_find_contact",
      "seq": 1,
      "call_ordinal": 0,
      "turn": 1,
      "return_form": "error_with_value",
      "text_real": "{\n  \"error\": {\n    \"code\": \"phone_not_e164\",\n    \"field\": \"query.phone\",\n    \"message\": \"поле query.phone: phone_not_e164: восем девятьсот двадцать два шестьсот восемьдесят шесть шестьсот одиннадцать чет\"\n  }\n}",
      "text_masked": "{\n  \"error\": {\n    \"code\": \"phone_not_e164\",\n    \"field\": \"query.phone\",\n    \"message\": \"поле query.phone: phone_not_e164: восем девятьсот двадцать два шестьсот восемьдесят шесть шестьсот одиннадцать чет\"\n  }\n}",
      "spans_real": {},
      "pieces": [],
      "forced": false
    },
    {
      "tool_name": "crm_find_contact",
      "seq": 2,
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
      "seq": 3,
      "call_ordinal": 2,
      "turn": 1,
      "return_form": "list",
      "text_real": "{\n  \"contacts\": [\n    {\n      \"id\": \"c-1\",\n      \"last_name\": \"тарасова\",\n      \"first_name\": \"алла\",\n      \"middle_name\": \"анатольевна\",\n      \"phone\": \"+79226866114\",\n      \"email\": \"tarasova73@yandex.ru\",\n      \"birth_date\": \"1997-04-08\",\n      \"address\": {\n        \"city\": \"ростов-на-дону\",\n        \"street\": \"добролюбова\",\n        \"house\": \"134\",\n        \"flat\": \"1\"\n      }\n    }\n  ]\n}",
      "text_masked": "{\n  \"contacts\": [\n    {\n      \"id\": \"c-1\",\n      \"last_name\": \"павлюк\",\n      \"first_name\": \"иоланта\",\n      \"middle_name\": \"олеговна\",\n      \"phone\": \"+79842990029\",\n      \"email\": \"gyyinzef@example.ru\",\n      \"birth_date\": \"1997-02-19\",\n      \"address\": {\n        \"city\": \"ростов-на-дону\",\n        \"street\": \"осиновая\",\n        \"house\": \"118\",\n        \"flat\": \"78\"\n      }\n    }\n  ]\n}",
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
          135
        ],
        "i4": [
          154,
          166
        ],
        "i5": [
          185,
          205
        ],
        "i6": [
          229,
          239
        ],
        "i7": [
          314,
          325
        ]
      },
      "pieces": [
        [
          63,
          71,
          "павлюк",
          "NAME"
        ],
        [
          95,
          99,
          "иоланта",
          "NAME"
        ],
        [
          124,
          135,
          "олеговна",
          "NAME"
        ],
        [
          154,
          166,
          "+79842990029",
          "PHONE"
        ],
        [
          185,
          205,
          "gyyinzef@example.ru",
          "EMAIL"
        ],
        [
          229,
          239,
          "1997-02-19",
          "DOB"
        ],
        [
          278,
          292,
          "ростов-на-дону",
          "LOC"
        ],
        [
          314,
          325,
          "осиновая",
          "LOC"
        ],
        [
          346,
          349,
          "118",
          "LOC"
        ],
        [
          369,
          370,
          "78",
          "LOC"
        ]
      ],
      "forced": false
    },
    {
      "tool_name": "crm_find_contact",
      "seq": 4,
      "call_ordinal": 3,
      "turn": 1,
      "return_form": "list",
      "text_real": "{\n  \"contacts\": [\n    {\n      \"id\": \"c-1\",\n      \"last_name\": \"тарасова\",\n      \"first_name\": \"алла\",\n      \"middle_name\": \"анатольевна\",\n      \"phone\": \"+79226866114\",\n      \"email\": \"tarasova73@yandex.ru\",\n      \"birth_date\": \"1997-04-08\",\n      \"address\": {\n        \"city\": \"ростов-на-дону\",\n        \"street\": \"добролюбова\",\n        \"house\": \"134\",\n        \"flat\": \"1\"\n      }\n    }\n  ]\n}",
      "text_masked": "{\n  \"contacts\": [\n    {\n      \"id\": \"c-1\",\n      \"last_name\": \"павлюк\",\n      \"first_name\": \"иоланта\",\n      \"middle_name\": \"олеговна\",\n      \"phone\": \"+79842990029\",\n      \"email\": \"gyyinzef@example.ru\",\n      \"birth_date\": \"1997-02-19\",\n      \"address\": {\n        \"city\": \"ростов-на-дону\",\n        \"street\": \"осиновая\",\n        \"house\": \"118\",\n        \"flat\": \"78\"\n      }\n    }\n  ]\n}",
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
          135
        ],
        "i4": [
          154,
          166
        ],
        "i5": [
          185,
          205
        ],
        "i6": [
          229,
          239
        ],
        "i7": [
          314,
          325
        ]
      },
      "pieces": [
        [
          63,
          71,
          "павлюк",
          "NAME"
        ],
        [
          95,
          99,
          "иоланта",
          "NAME"
        ],
        [
          124,
          135,
          "олеговна",
          "NAME"
        ],
        [
          154,
          166,
          "+79842990029",
          "PHONE"
        ],
        [
          185,
          205,
          "gyyinzef@example.ru",
          "EMAIL"
        ],
        [
          229,
          239,
          "1997-02-19",
          "DOB"
        ],
        [
          278,
          292,
          "ростов-на-дону",
          "LOC"
        ],
        [
          314,
          325,
          "осиновая",
          "LOC"
        ],
        [
          346,
          349,
          "118",
          "LOC"
        ],
        [
          369,
          370,
          "78",
          "LOC"
        ]
      ],
      "forced": false
    },
    {
      "tool_name": "crm_find_contact",
      "seq": 5,
      "call_ordinal": 4,
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
      "seq": 6,
      "call_ordinal": 5,
      "turn": 1,
      "return_form": "list",
      "text_real": "{\n  \"contacts\": [\n    {\n      \"id\": \"c-1\",\n      \"last_name\": \"тарасова\",\n      \"first_name\": \"алла\",\n      \"middle_name\": \"анатольевна\",\n      \"phone\": \"+79226866114\",\n      \"email\": \"tarasova73@yandex.ru\",\n      \"birth_date\": \"1997-04-08\",\n      \"address\": {\n        \"city\": \"ростов-на-дону\",\n        \"street\": \"добролюбова\",\n        \"house\": \"134\",\n        \"flat\": \"1\"\n      }\n    }\n  ]\n}",
      "text_masked": "{\n  \"contacts\": [\n    {\n      \"id\": \"c-1\",\n      \"last_name\": \"павлюк\",\n      \"first_name\": \"иоланта\",\n      \"middle_name\": \"олеговна\",\n      \"phone\": \"+79842990029\",\n      \"email\": \"gyyinzef@example.ru\",\n      \"birth_date\": \"1997-02-19\",\n      \"address\": {\n        \"city\": \"ростов-на-дону\",\n        \"street\": \"осиновая\",\n        \"house\": \"118\",\n        \"flat\": \"78\"\n      }\n    }\n  ]\n}",
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
          135
        ],
        "i4": [
          154,
          166
        ],
        "i5": [
          185,
          205
        ],
        "i6": [
          229,
          239
        ],
        "i7": [
          314,
          325
        ]
      },
      "pieces": [
        [
          63,
          71,
          "павлюк",
          "NAME"
        ],
        [
          95,
          99,
          "иоланта",
          "NAME"
        ],
        [
          124,
          135,
          "олеговна",
          "NAME"
        ],
        [
          154,
          166,
          "+79842990029",
          "PHONE"
        ],
        [
          185,
          205,
          "gyyinzef@example.ru",
          "EMAIL"
        ],
        [
          229,
          239,
          "1997-02-19",
          "DOB"
        ],
        [
          278,
          292,
          "ростов-на-дону",
          "LOC"
        ],
        [
          314,
          325,
          "осиновая",
          "LOC"
        ],
        [
          346,
          349,
          "118",
          "LOC"
        ],
        [
          369,
          370,
          "78",
          "LOC"
        ]
      ],
      "forced": false
    },
    {
      "tool_name": "crm_find_contact",
      "seq": 7,
      "call_ordinal": 6,
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
      "call_ordinal": 7,
      "turn": 1,
      "return_form": "empty",
      "text_real": "{\n  \"contacts\": [\n    \n  ]\n}",
      "text_masked": "{\n  \"contacts\": [\n    \n  ]\n}",
      "spans_real": {},
      "pieces": [],
      "forced": false
    },
    {
      "tool_name": "notify_sms",
      "seq": 9,
      "call_ordinal": 0,
      "turn": 3,
      "return_form": "single",
      "text_real": "{\n  \"id\": \"sms-1\",\n  \"status\": \"queued\",\n  \"number\": \"+79226866114\"\n}",
      "text_masked": "{\n  \"id\": \"sms-1\",\n  \"status\": \"queued\",\n  \"number\": \"+79842990029\"\n}",
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
          "+79842990029",
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
      "substitute": "уварова тимура",
      "request_index": 1
    },
    {
      "item_id": "i9",
      "msg": 1,
      "result_seq": -1,
      "substitute": "+79842990029",
      "request_index": 1
    },
    {
      "item_id": "i1",
      "msg": -1,
      "result_seq": 3,
      "substitute": "павлюк",
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
      "item_id": "i3",
      "msg": -1,
      "result_seq": 3,
      "substitute": "олеговна",
      "request_index": 4
    },
    {
      "item_id": "i4",
      "msg": -1,
      "result_seq": 3,
      "substitute": "+79842990029",
      "request_index": 4
    },
    {
      "item_id": "i5",
      "msg": -1,
      "result_seq": 3,
      "substitute": "gyyinzef@example.ru",
      "request_index": 4
    },
    {
      "item_id": "i6",
      "msg": -1,
      "result_seq": 3,
      "substitute": "1997-02-19",
      "request_index": 4
    },
    {
      "item_id": "i7",
      "msg": -1,
      "result_seq": 3,
      "substitute": "осиновая",
      "request_index": 4
    },
    {
      "item_id": "i1",
      "msg": -1,
      "result_seq": 4,
      "substitute": "павлюк",
      "request_index": 5
    },
    {
      "item_id": "i2",
      "msg": -1,
      "result_seq": 4,
      "substitute": "иоланта",
      "request_index": 5
    },
    {
      "item_id": "i3",
      "msg": -1,
      "result_seq": 4,
      "substitute": "олеговна",
      "request_index": 5
    },
    {
      "item_id": "i4",
      "msg": -1,
      "result_seq": 4,
      "substitute": "+79842990029",
      "request_index": 5
    },
    {
      "item_id": "i5",
      "msg": -1,
      "result_seq": 4,
      "substitute": "gyyinzef@example.ru",
      "request_index": 5
    },
    {
      "item_id": "i6",
      "msg": -1,
      "result_seq": 4,
      "substitute": "1997-02-19",
      "request_index": 5
    },
    {
      "item_id": "i7",
      "msg": -1,
      "result_seq": 4,
      "substitute": "осиновая",
      "request_index": 5
    },
    {
      "item_id": "i1",
      "msg": -1,
      "result_seq": 6,
      "substitute": "павлюк",
      "request_index": 7
    },
    {
      "item_id": "i2",
      "msg": -1,
      "result_seq": 6,
      "substitute": "иоланта",
      "request_index": 7
    },
    {
      "item_id": "i3",
      "msg": -1,
      "result_seq": 6,
      "substitute": "олеговна",
      "request_index": 7
    },
    {
      "item_id": "i4",
      "msg": -1,
      "result_seq": 6,
      "substitute": "+79842990029",
      "request_index": 7
    },
    {
      "item_id": "i5",
      "msg": -1,
      "result_seq": 6,
      "substitute": "gyyinzef@example.ru",
      "request_index": 7
    },
    {
      "item_id": "i6",
      "msg": -1,
      "result_seq": 6,
      "substitute": "1997-02-19",
      "request_index": 7
    },
    {
      "item_id": "i7",
      "msg": -1,
      "result_seq": 6,
      "substitute": "осиновая",
      "request_index": 7
    },
    {
      "item_id": "i10",
      "msg": 2,
      "result_seq": -1,
      "substitute": "Ростов-На-Дону, Черёмуховый проспект 104, кв. 100",
      "request_index": 10
    },
    {
      "item_id": "i4",
      "msg": -1,
      "result_seq": 9,
      "substitute": "+79842990029",
      "request_index": 12
    }
  ],
  "turn_replies": [
    "Проверил номер по нашей базе — есть пара моментов, которые нужно прояснить, прежде чем оформлять.\n\n1. **Получатель.** Номер **+79226866114** в CRM привязан к клиенту **Тарасова Алла Анатольевна**, а не к Тарасову Аллу. Подтвердите, пожалуйста, верные ФИО и телефон получателя.\n\n2. **Адрес доставки.** Его не хватает для оформления — нужен город и улица с номером дома (и квартира). Если ориентироваться на адрес из карточки — **Ростов-на-Дону, ул. Осиновая, д. 134** — то оформить не получится: дом №134 больше 100, это промзона, курьер туда не выезжает. Если получатель по другому адресу — пришлите его.\n\n3. **«Заказ 795».** Уточните, что это — номер существующего заказа, который надо учесть, или отдельная посылка?\n\nВес, если не назовёте, поставлю по умолчанию 1000 г, индекс подберу по городу получателя.",
    "К сожалению, по этому адресу оформить доставку не получится: **ростов-на-дону проспект добролюбова сто тридцать четыыре** — номер дома больше 100, а это промзона, куда курьер не выезжает. Такие заказы мы не оформляем.\n\nЕсли у получателя есть другой адрес (жилой дом с номером до 100 включительно) — пришлите его, и я сразу оформлю доставку. Также напомню про уточнение по получателю: номер **+79226866114** в базе записан на **Тарасова Аллу Анатольевну** — подтвердите, пожалуйста, ФИО и телефон, чтобы я всё оформил верно.",
    "Оформить заказ не получилось — и не получится, к сожалению: адрес **Ростов-на-Дону, ростов-на-дону проспект добролюбова сто тридцать четыыре** не подходит для доставки. Номер дома **134 больше 100**, это промзона, курьер туда не выезжает — такие заказы мы не оформляем.\n\nСМС на номер **+79226866114** я отправил: там указано, что оформить по этому адресу нельзя, и просьба прислать другой адрес (дом до 100 включительно).\n\nКак только дадите пригодный адрес — оформлю доставку сразу. Также напомню: номер +79226866114 в базе привязан к **Тарасова Алле Анатольевне**, а вы называете получателя **Тарасова Алла** — подтвердите, пожалуйста, верные ФИО и телефон, чтобы заказ ушёл правильно."
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
    3
  ],
  "request_count": 12,
  "stream_mismatch": false,
  "reply_whole": "",
  "turn_residual": 2
}

## Recorded observer hops

[
  {
    "case_id": "prompt_rule-007",
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
    "produced": "уварова тимура",
    "reference": "тарасова алла",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "prompt_rule-007",
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
    "produced": "+79842990029",
    "reference": "восем девятьсот двадцать два шестьсот восемьдесят шесть шестьсот одиннадцать четыре",
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
    "case_id": "prompt_rule-007",
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
    "produced": "Ростов-На-Дону, Черёмуховый проспект 104, кв. 100",
    "reference": "ростов-на-дону проспект добролюбова сто тридцать четыыре квартира один",
    "status": "observed",
    "verdict": {
      "same": false,
      "differs": [
        "case_class",
        "city_position",
        "city_present",
        "commas",
        "flat_marker"
      ]
    }
  },
  {
    "case_id": "prompt_rule-007",
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
    "produced": "",
    "reference": "",
    "status": "absent",
    "verdict": null
  },
  {
    "case_id": "prompt_rule-007",
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
    "produced": "",
    "reference": "",
    "status": "absent",
    "verdict": null
  },
  {
    "case_id": "prompt_rule-007",
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
    "produced": "",
    "reference": "",
    "status": "absent",
    "verdict": null
  },
  {
    "case_id": "prompt_rule-007",
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
    "produced": "",
    "reference": "",
    "status": "absent",
    "verdict": null
  },
  {
    "case_id": "prompt_rule-007",
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
    "produced": "",
    "reference": "",
    "status": "absent",
    "verdict": null
  },
  {
    "case_id": "prompt_rule-007",
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
    "produced": "",
    "reference": "",
    "status": "absent",
    "verdict": null
  },
  {
    "case_id": "prompt_rule-007",
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
    "produced": "",
    "reference": "",
    "status": "absent",
    "verdict": null
  },
  {
    "case_id": "prompt_rule-007",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i8",
      "hop_index": 12,
      "turn": 3,
      "tool_name": "delivery_create_order",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": 0,
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
    "case_id": "prompt_rule-007",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i9",
      "hop_index": 13,
      "turn": 3,
      "tool_name": "delivery_create_order",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": 1,
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
    "case_id": "prompt_rule-007",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i10",
      "hop_index": 14,
      "turn": 3,
      "tool_name": "delivery_create_order",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": 2,
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
    "case_id": "prompt_rule-007",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i10",
      "hop_index": 15,
      "turn": 3,
      "tool_name": "delivery_create_order",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": 2,
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
    "case_id": "prompt_rule-007",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i9",
      "hop_index": 16,
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
    "produced": "+79226866114",
    "reference": "+79842990029",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "prompt_rule-007",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "answer",
      "item_id": "i1",
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
    "produced": "Тарасова",
    "reference": "Павлюк",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "prompt_rule-007",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "answer",
      "item_id": "i2",
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
    "produced": "Тарасова Алле Анатольевне",
    "reference": "Павлюк Иоланте Олеговне",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "prompt_rule-007",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "answer",
      "item_id": "i3",
      "hop_index": 19,
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
    "produced": "Тарасова Алле Анатольевне",
    "reference": "Павлюк Иоланте Олеговне",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "prompt_rule-007",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "answer",
      "item_id": "i4",
      "hop_index": 20,
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
    "produced": "+79226866114",
    "reference": "+79842990029",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "prompt_rule-007",
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
    "produced": "восем девятьсот двадцать два шестьсот восемьдесят шесть шестьсот одиннадцать четыре",
    "reference": "+79842990029",
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
    "case_id": "prompt_rule-007",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i8",
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
    "produced": "Тарасов",
    "reference": "Уваров",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "prompt_rule-007",
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
      "path": "query.phone",
      "optional": false
    },
    "declared": false,
    "pii_type": "PHONE",
    "produced": "+79226866114",
    "reference": "+79226866114",
    "status": "unmasked",
    "verdict": null
  },
  {
    "case_id": "prompt_rule-007",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i1",
      "hop_index": -1,
      "turn": 1,
      "tool_name": "crm_find_contact",
      "call_ordinal": 3,
      "parallel_group": "",
      "source_hop": -1,
      "path": "query.last_name",
      "optional": false
    },
    "declared": false,
    "pii_type": "NAME",
    "produced": "тарасова",
    "reference": "павлюк",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "prompt_rule-007",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i8",
      "hop_index": -1,
      "turn": 1,
      "tool_name": "crm_find_contact",
      "call_ordinal": 4,
      "parallel_group": "",
      "source_hop": -1,
      "path": "query.last_name",
      "optional": false
    },
    "declared": false,
    "pii_type": "NAME",
    "produced": "тарасов",
    "reference": "уваров",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "prompt_rule-007",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i4",
      "hop_index": -1,
      "turn": 1,
      "tool_name": "crm_find_contact",
      "call_ordinal": 5,
      "parallel_group": "",
      "source_hop": -1,
      "path": "query.phone",
      "optional": false
    },
    "declared": false,
    "pii_type": "PHONE",
    "produced": "+79226866114",
    "reference": "+79842990029",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "prompt_rule-007",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "",
      "hop_index": -1,
      "turn": 1,
      "tool_name": "crm_find_contact",
      "call_ordinal": 6,
      "parallel_group": "",
      "source_hop": -1,
      "path": "query.phone",
      "optional": false
    },
    "declared": false,
    "pii_type": "PHONE",
    "produced": "+79001112233",
    "reference": "+79001112233",
    "status": "unmasked",
    "verdict": null
  },
  {
    "case_id": "prompt_rule-007",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "",
      "hop_index": -1,
      "turn": 1,
      "tool_name": "crm_find_contact",
      "call_ordinal": 7,
      "parallel_group": "",
      "source_hop": -1,
      "path": "query.last_name",
      "optional": false
    },
    "declared": false,
    "pii_type": "NAME",
    "produced": "иванов",
    "reference": "иванов",
    "status": "unmasked",
    "verdict": null
  },
  {
    "case_id": "prompt_rule-007",
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
    "produced": "ростов-на-дону",
    "reference": "Черёмуховый",
    "status": "observed",
    "verdict": {
      "same": false,
      "differs": [
        "case_class"
      ]
    }
  },
  {
    "case_id": "prompt_rule-007",
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
    "produced": "+79226866114",
    "reference": "+79842990029",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "prompt_rule-007",
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
    "produced": "+79226866114",
    "reference": "+79842990029",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "prompt_rule-007",
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
    "produced": "Тарасова Алла",
    "reference": "Уварова Тимура",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  }
]
