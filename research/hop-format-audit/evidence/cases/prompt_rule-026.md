# prompt_rule-026 | source C | repeat 0

Synthetic benchmark evidence. Verbatim serialized fields; no inferred verdicts.

## Case specification

{
  "base": {
    "id": "prompt_rule-026",
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
    "cluster": "PHONE:9525074654",
    "conversation_id": "conv-rule-26",
    "now": "2026-09-02",
    "messages": [
      {
        "role": "system",
        "content": "Ты оператор службы доставки. Оформляй заказы и вызовы курьера инструментами, переспрашивай только то, чего не хватает для вызова. Вес посылки, если не назван, — 1000 г; почтовый индекс подбери сам по городу получателя. Сегодня 2026-09-02. Доставляем только по городу Кинешма; в другие города заказы не оформляем.",
        "source": null,
        "name": ""
      },
      {
        "role": "user",
        "content": "аа здравствуйтее оформите доставку на миллер валерий телефон восемь девятьсот пейсят два пятьсот семь сорок шесть пятьдесят четыре и ещё заказ пятьсот восемьдесят семь",
        "source": null,
        "name": ""
      },
      {
        "role": "user",
        "content": "адреес кинешма переулок комиссарова шесят четыре квартира сто восемьдесят три",
        "source": null,
        "name": ""
      },
      {
        "role": "user",
        "content": "давайте оформим и подтверждение смс",
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
          "last_name": "миллер",
          "first_name": "валерий",
          "middle_name": "леонидович",
          "phone": "+79525074654",
          "email": "miller92@list.ru",
          "birth_date": "1979-08-25",
          "address": {
            "city": "кинешма",
            "street": "комиссарова",
            "house": "64",
            "flat": "183"
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
        "identity": "p26",
        "value": "миллер",
        "canonical": "миллер",
        "parts": {
          "surname": "миллер",
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
        "identity": "p26",
        "value": "валерий",
        "canonical": "валерий",
        "parts": {
          "given": "валерий",
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
        "identity": "p26",
        "value": "леонидович",
        "canonical": "леонидович",
        "parts": {
          "patronymic": "леонидович",
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
        "identity": "p26",
        "value": "+79525074654",
        "canonical": "+79525074654",
        "parts": {
          "digits": "9525074654"
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
        "identity": "p26",
        "value": "miller92@list.ru",
        "canonical": "miller92@list.ru",
        "parts": {
          "local": "miller92",
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
        "identity": "p26",
        "value": "1979-08-25",
        "canonical": "1979-08-25",
        "parts": {
          "iso": "1979-08-25"
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
        "identity": "p26.home",
        "value": "комиссарова",
        "canonical": "комиссарова",
        "parts": {
          "street": "комиссарова",
          "street_type": "переулок",
          "house": "64",
          "flat": "183",
          "city": "кинешма"
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
        "identity": "p26",
        "value": "миллер валерий",
        "canonical": "миллер валерий",
        "parts": {
          "surname": "миллер",
          "given": "валерий",
          "gender": "m"
        },
        "where": {
          "kind": "message",
          "msg": 1,
          "start": 38,
          "end": 52,
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
        "identity": "p26",
        "value": "восемь девятьсот пейсят два пятьсот семь сорок шесть пятьдесят четыре",
        "canonical": "+79525074654",
        "parts": {
          "digits": "9525074654"
        },
        "where": {
          "kind": "message",
          "msg": 1,
          "start": 61,
          "end": 130,
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
        "identity": "p26.home",
        "value": "кинешма переулок комиссарова шесят четыре квартира сто восемьдесят три",
        "canonical": "кинешма переулок комиссарова шесят четыре квартира сто восемьдесят три",
        "parts": {
          "street": "комиссарова",
          "street_type": "переулок",
          "house": "64",
          "flat": "183",
          "city": "кинешма"
        },
        "where": {
          "kind": "message",
          "msg": 2,
          "start": 7,
          "end": 77,
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
        "value": "пятьсот восемьдесят семь",
        "start": 143,
        "end": 167,
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
      "primary_identity": "p26",
      "must_contain": [],
      "must_not_contain": [],
      "validate_types": []
    },
    "trace": [
      {
        "msg": 1,
        "key": "",
        "start": 0,
        "end": 2,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 1,
        "key": "",
        "start": 2,
        "end": 3,
        "origin": "literal"
      },
      {
        "msg": 1,
        "key": "",
        "start": 3,
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
        "key": "",
        "start": 17,
        "end": 25,
        "origin": "chunk:noisy_word"
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
        "end": 34,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 1,
        "key": "",
        "start": 34,
        "end": 35,
        "origin": "literal"
      },
      {
        "msg": 1,
        "key": "",
        "start": 35,
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
        "key": "n1",
        "start": 38,
        "end": 52,
        "origin": "value:n1"
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
        "key": "ph1",
        "start": 61,
        "end": 130,
        "origin": "value:ph1"
      },
      {
        "msg": 1,
        "key": "",
        "start": 130,
        "end": 131,
        "origin": "literal"
      },
      {
        "msg": 1,
        "key": "",
        "start": 131,
        "end": 132,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 1,
        "key": "",
        "start": 132,
        "end": 133,
        "origin": "literal"
      },
      {
        "msg": 1,
        "key": "",
        "start": 133,
        "end": 136,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 1,
        "key": "",
        "start": 136,
        "end": 137,
        "origin": "literal"
      },
      {
        "msg": 1,
        "key": "",
        "start": 137,
        "end": 142,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 1,
        "key": "",
        "start": 142,
        "end": 143,
        "origin": "literal"
      },
      {
        "msg": 1,
        "key": "neg1",
        "start": 143,
        "end": 167,
        "origin": "negative:neg1"
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
        "end": 77,
        "origin": "value:a1"
      },
      {
        "msg": 3,
        "key": "",
        "start": 0,
        "end": 7,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 3,
        "key": "",
        "start": 7,
        "end": 8,
        "origin": "literal"
      },
      {
        "msg": 3,
        "key": "",
        "start": 8,
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
        "end": 31,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 3,
        "key": "",
        "start": 31,
        "end": 32,
        "origin": "literal"
      },
      {
        "msg": 3,
        "key": "",
        "start": 32,
        "end": 35,
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
    "case_id": "prompt_rule-026",
    "arm": "I",
    "repeat": 0,
    "calls": [
      {
        "name": "crm_find_contact",
        "written": {
          "query": {
            "phone": "+79729706081"
          }
        },
        "restored": {
          "query": {
            "phone": "восемь девятьсот пейсят два пятьсот семь сорок шесть пятьдесят четыре"
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
            "last_name": "Панов"
          }
        },
        "restored": {
          "query": {
            "last_name": "Миллер"
          }
        },
        "residual": {},
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "query": {
            "last_name": "миллер"
          }
        },
        "seq": 2
      },
      {
        "name": "delivery_quote",
        "written": {
          "city": "Кинешма",
          "weight": 1000
        },
        "restored": {
          "city": "Кинешма",
          "weight": 1000
        },
        "residual": {},
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "city": "кинешма",
          "weight": 1000
        },
        "seq": 3
      },
      {
        "name": "delivery_create_order",
        "written": {
          "comment": "Заказ №587",
          "packages": [
            {
              "weight": 1000
            }
          ],
          "recipient": {
            "name": "Панов Лев Константинович",
            "phones": [
              {
                "number": "+79729706081"
              }
            ]
          },
          "to_location": {
            "address": "улица Мятная, д. 34, кв. 186",
            "city": "Кинешма",
            "postal_code": "155800"
          }
        },
        "restored": {
          "comment": "Заказ №587",
          "packages": [
            {
              "weight": 1000
            }
          ],
          "recipient": {
            "name": "Миллер Валерий Леонидович",
            "phones": [
              {
                "number": "+79525074654"
              }
            ]
          },
          "to_location": {
            "address": "улица Мятная, д. 64, кв. 183",
            "city": "Кинешма",
            "postal_code": "155800"
          }
        },
        "residual": {
          "to_location.address": [
            "мятная"
          ]
        },
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "comment": "Заказ №587",
          "packages": [
            {
              "weight": 1000
            }
          ],
          "recipient": {
            "name": "Миллер Валерий Леонидович",
            "phones": [
              "+79525074654"
            ]
          },
          "to_location": {
            "address": "улица Мятная, д. 64, кв. 183",
            "city": "кинешма",
            "postal_code": "155800"
          }
        },
        "seq": 4
      }
    ],
    "state": [
      {
        "fields": {
          "comment": "Заказ №587",
          "packages": [
            {
              "weight": 1000
            }
          ],
          "recipient": {
            "name": "Миллер Валерий Леонидович",
            "phones": [
              "+79525074654"
            ]
          },
          "to_location": {
            "address": "улица Мятная, д. 64, кв. 183",
            "city": "кинешма",
            "postal_code": "155800"
          }
        },
        "id": "ord-1",
        "seq": 4,
        "table": "orders",
        "tool": "delivery_create_order"
      }
    ],
    "reply": "Для вызова курьера мне нужен интервал времени — на какую дату и время его оформить (например, 03.09.2026 с 10:00 до 13:00)? Как только вызов создам, сразу отправлю СМС с подтверждением на +79525074654.",
    "termination": "done",
    "cost_usd": 0.008385,
    "substitutes": {
      "i1": [
        "панов",
        {
          "surname": "панов"
        }
      ],
      "i10": [
        "Кинешма, улица Мятная 34, кв. 186",
        {
          "city": "кинешма",
          "flat": "186",
          "house": "34",
          "street": "мятная"
        }
      ],
      "i2": [
        "лев",
        {
          "given": "лев"
        }
      ],
      "i3": [
        "константинович",
        {
          "patronymic": "константинович"
        }
      ],
      "i4": [
        "+79729706081",
        {
          "digits": "9729706081"
        }
      ],
      "i5": [
        "lssvtwhz@example.ru",
        {
          "domain": "example.ru",
          "local": "lssvtwhz"
        }
      ],
      "i6": [
        "1979-03-25",
        {
          "iso": "1979-03-25"
        }
      ],
      "i7": [
        "мятная",
        {
          "street": "мятная"
        }
      ],
      "i8": [
        "панов лев",
        {
          "given": "лев",
          "surname": "панов"
        }
      ],
      "i9": [
        "+79729706081",
        {
          "digits": "9729706081"
        }
      ]
    },
    "masked_spans": {
      "0": [],
      "1": [
        [
          38,
          52
        ],
        [
          61,
          130
        ]
      ],
      "2": [
        [
          7,
          77
        ]
      ],
      "3": []
    }
  },
  "reply_raw": "Для вызова курьера мне нужен интервал времени — на какую дату и время его оформить (например, 03.09.2026 с 10:00 до 13:00)? Как только вызов создам, сразу отправлю СМС с подтверждением на +79729706081.",
  "control_reply": "Оформляю заказ по адресу, который вы назвали.\nГотово! Заказ оформлен и подтверждение отправлено.\n\n- **Получатель:** Миллер Валерий Леонидович, +7 952 507‑46‑54\n- **Адрес:** г. Кинешма, пер. Комиссарова, д. 64, кв. 183 (индекс 155800)\n- **Вес:** 1000 г\n- **Номер заказа:** ord-2, статус «принят»\n- **СМС:** подтверждение отправлено на номер получателя\n\nОбратите внимание: ранее был оформлен заказ **ord-1** с адресом «ул. Комиссарова, д. 64, кв. 183». Если он больше не нужен, скажите — учту в работе.\n\nНапоминаю: по «заказу 587» уточнений так и не поступило. Если это отдельная доставка — продиктуйте, пожалуйста, данные, и я её оформлю.",
  "tool_results": [
    {
      "tool_name": "crm_find_contact",
      "seq": 1,
      "call_ordinal": 0,
      "turn": 1,
      "return_form": "error_with_value",
      "text_real": "{\n  \"error\": {\n    \"code\": \"phone_not_e164\",\n    \"field\": \"query.phone\",\n    \"message\": \"поле query.phone: phone_not_e164: восемь девятьсот пейсят два пятьсот семь сорок шесть пятьдесят четыре\"\n  }\n}",
      "text_masked": "{\n  \"error\": {\n    \"code\": \"phone_not_e164\",\n    \"field\": \"query.phone\",\n    \"message\": \"поле query.phone: phone_not_e164: +79729706081\"\n  }\n}",
      "spans_real": {},
      "pieces": [
        [
          123,
          192,
          "+79729706081",
          "PHONE"
        ]
      ],
      "forced": false
    },
    {
      "tool_name": "crm_find_contact",
      "seq": 2,
      "call_ordinal": 1,
      "turn": 1,
      "return_form": "list",
      "text_real": "{\n  \"contacts\": [\n    {\n      \"id\": \"c-1\",\n      \"last_name\": \"миллер\",\n      \"first_name\": \"валерий\",\n      \"middle_name\": \"леонидович\",\n      \"phone\": \"+79525074654\",\n      \"email\": \"miller92@list.ru\",\n      \"birth_date\": \"1979-08-25\",\n      \"address\": {\n        \"city\": \"кинешма\",\n        \"street\": \"комиссарова\",\n        \"house\": \"64\",\n        \"flat\": \"183\"\n      }\n    }\n  ]\n}",
      "text_masked": "{\n  \"contacts\": [\n    {\n      \"id\": \"c-1\",\n      \"last_name\": \"панов\",\n      \"first_name\": \"лев\",\n      \"middle_name\": \"константинович\",\n      \"phone\": \"+79729706081\",\n      \"email\": \"lssvtwhz@example.ru\",\n      \"birth_date\": \"1979-03-25\",\n      \"address\": {\n        \"city\": \"кинешма\",\n        \"street\": \"мятная\",\n        \"house\": \"34\",\n        \"flat\": \"186\"\n      }\n    }\n  ]\n}",
      "spans_real": {
        "i1": [
          63,
          69
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
          303,
          314
        ]
      },
      "pieces": [
        [
          63,
          69,
          "панов",
          "NAME"
        ],
        [
          93,
          100,
          "лев",
          "NAME"
        ],
        [
          125,
          135,
          "константинович",
          "NAME"
        ],
        [
          154,
          166,
          "+79729706081",
          "PHONE"
        ],
        [
          185,
          201,
          "lssvtwhz@example.ru",
          "EMAIL"
        ],
        [
          225,
          235,
          "1979-03-25",
          "DOB"
        ],
        [
          274,
          281,
          "кинешма",
          "LOC"
        ],
        [
          303,
          314,
          "мятная",
          "LOC"
        ],
        [
          335,
          337,
          "34",
          "LOC"
        ],
        [
          357,
          360,
          "186",
          "LOC"
        ]
      ],
      "forced": false
    },
    {
      "tool_name": "delivery_quote",
      "seq": 3,
      "call_ordinal": 0,
      "turn": 1,
      "return_form": "single",
      "text_real": "{\n  \"city\": \"кинешма\",\n  \"weight\": \"1000\",\n  \"price\": \"370.00\",\n  \"currency\": \"RUB\",\n  \"days\": \"2\",\n  \"pickup_point\": {\n    \"address\": \"\"\n  }\n}",
      "text_masked": "{\n  \"city\": \"кинешма\",\n  \"weight\": \"1000\",\n  \"price\": \"370.00\",\n  \"currency\": \"RUB\",\n  \"days\": \"2\",\n  \"pickup_point\": {\n    \"address\": \"\"\n  }\n}",
      "spans_real": {},
      "pieces": [],
      "forced": false
    },
    {
      "tool_name": "delivery_create_order",
      "seq": 4,
      "call_ordinal": 0,
      "turn": 2,
      "return_form": "single",
      "text_real": "{\n  \"uuid\": \"ord-1\",\n  \"status\": \"ACCEPTED\",\n  \"recipient\": {\n    \"name\": \"Миллер Валерий Леонидович\",\n    \"phone\": \"+79525074654\"\n  },\n  \"to_location\": {\n    \"postal_code\": \"155800\",\n    \"city\": \"кинешма\",\n    \"address\": \"улица Мятная, д. 64, кв. 183\"\n  }\n}",
      "text_masked": "{\n  \"uuid\": \"ord-1\",\n  \"status\": \"ACCEPTED\",\n  \"recipient\": {\n    \"name\": \"Панов Лев Романович\",\n    \"phone\": \"+79729706081\"\n  },\n  \"to_location\": {\n    \"postal_code\": \"155800\",\n    \"city\": \"кинешма\",\n    \"address\": \"улица Кедровая, д. 62, кв. 130\"\n  }\n}",
      "spans_real": {
        "i4": [
          117,
          129
        ]
      },
      "pieces": [
        [
          75,
          100,
          "Панов Лев Романович",
          "NAME"
        ],
        [
          117,
          129,
          "+79729706081",
          "PHONE"
        ],
        [
          223,
          251,
          "улица Кедровая, д. 62, кв. 130",
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
      "substitute": "панов лев",
      "request_index": 1
    },
    {
      "item_id": "i9",
      "msg": 1,
      "result_seq": -1,
      "substitute": "+79729706081",
      "request_index": 1
    },
    {
      "item_id": "i1",
      "msg": -1,
      "result_seq": 2,
      "substitute": "панов",
      "request_index": 3
    },
    {
      "item_id": "i2",
      "msg": -1,
      "result_seq": 2,
      "substitute": "лев",
      "request_index": 3
    },
    {
      "item_id": "i3",
      "msg": -1,
      "result_seq": 2,
      "substitute": "константинович",
      "request_index": 3
    },
    {
      "item_id": "i4",
      "msg": -1,
      "result_seq": 2,
      "substitute": "+79729706081",
      "request_index": 3
    },
    {
      "item_id": "i5",
      "msg": -1,
      "result_seq": 2,
      "substitute": "lssvtwhz@example.ru",
      "request_index": 3
    },
    {
      "item_id": "i6",
      "msg": -1,
      "result_seq": 2,
      "substitute": "1979-03-25",
      "request_index": 3
    },
    {
      "item_id": "i7",
      "msg": -1,
      "result_seq": 2,
      "substitute": "мятная",
      "request_index": 3
    },
    {
      "item_id": "i10",
      "msg": 2,
      "result_seq": -1,
      "substitute": "Кинешма, улица Мятная 34, кв. 186",
      "request_index": 5
    },
    {
      "item_id": "i4",
      "msg": -1,
      "result_seq": 4,
      "substitute": "+79729706081",
      "request_index": 6
    }
  ],
  "turn_replies": [
    "Подскажите, пожалуйста, пару моментов, чтобы всё оформить:\n\n1. Нашёл в CRM получателя: **Миллер Валерий Леонидович**, тел. +79525074654, адрес: Кинешма, ул. Мятная, д. 64, кв. 183. Верно? Вес не указали — ставлю 1000 г (стоимость 370 ₽, срок 2 дня).\n2. Что значит «заказ 587» — это номер заказа для комментария курьеру или отдельный заказ? Если отдельный, нужны получатель и адрес.\n3. По какому адресу вызывать курьера за посылкой (откуда забирать)?",
    "Заказ оформлен: № **ord-1** (принят в систему).\n- Получатель: Миллер Валерий Леонидович, +79525074654\n- Адрес: Кинешма, ул. Мятная, д. 64, кв. 183 (индекс 155800)\n- Вес: 1000 г\n- Стоимость: 370 ₽, срок 2 дня\n- Комментарий курьеру: Заказ №587\n\nОсталось вызвать курьера. На какой интервал времени его оформить (дата и время, например 03.09.2026 с 10:00 до 13:00)? Забрать нужно по адресу Кинешма, ул. Мятная, 64, кв. 183 — верно?",
    "Для вызова курьера мне нужен интервал времени — на какую дату и время его оформить (например, 03.09.2026 с 10:00 до 13:00)? Как только вызов создам, сразу отправлю СМС с подтверждением на +79525074654."
  ],
  "call_turns": [
    1,
    1,
    1,
    2
  ],
  "request_count": 7,
  "stream_mismatch": false,
  "reply_whole": "",
  "turn_residual": 2
}

## Recorded observer hops

[
  {
    "case_id": "prompt_rule-026",
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
    "produced": "панов лев",
    "reference": "миллер валерий",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "prompt_rule-026",
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
    "produced": "+79729706081",
    "reference": "восемь девятьсот пейсят два пятьсот семь сорок шесть пятьдесят четыре",
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
    "case_id": "prompt_rule-026",
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
    "produced": "Кинешма, улица Мятная 34, кв. 186",
    "reference": "кинешма переулок комиссарова шесят четыре квартира сто восемьдесят три",
    "status": "observed",
    "verdict": {
      "same": false,
      "differs": [
        "case_class",
        "city_position",
        "city_present",
        "commas",
        "flat_marker",
        "generic",
        "generic_position"
      ]
    }
  },
  {
    "case_id": "prompt_rule-026",
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
    "case_id": "prompt_rule-026",
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
    "case_id": "prompt_rule-026",
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
    "case_id": "prompt_rule-026",
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
    "case_id": "prompt_rule-026",
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
    "case_id": "prompt_rule-026",
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
    "case_id": "prompt_rule-026",
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
    "case_id": "prompt_rule-026",
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
    "case_id": "prompt_rule-026",
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
    "case_id": "prompt_rule-026",
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
    "case_id": "prompt_rule-026",
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
    "case_id": "prompt_rule-026",
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
    "produced": "",
    "reference": "",
    "status": "absent",
    "verdict": null
  },
  {
    "case_id": "prompt_rule-026",
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
    "produced": "+79525074654",
    "reference": "+79729706081",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "prompt_rule-026",
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
    "produced": "восемь девятьсот пейсят два пятьсот семь сорок шесть пятьдесят четыре",
    "reference": "+79729706081",
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
    "case_id": "prompt_rule-026",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i1",
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
    "produced": "Миллер",
    "reference": "Панов",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "prompt_rule-026",
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
    "produced": "Миллер Валерий Леонидович",
    "reference": "Панов Лев Константинович",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "prompt_rule-026",
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
    "produced": "+79525074654",
    "reference": "+79729706081",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "prompt_rule-026",
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
    "produced": "улица Мятная, д. 64, кв. 183",
    "reference": "улица Мятная, д. 34, кв. 186",
    "status": "residual",
    "verdict": null
  },
  {
    "case_id": "prompt_rule-026",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "",
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
    "produced": "Кинешма",
    "reference": "Кинешма",
    "status": "unmasked",
    "verdict": null
  },
  {
    "case_id": "prompt_rule-026",
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
    "produced": "+79525074654",
    "reference": "+79729706081",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  }
]
