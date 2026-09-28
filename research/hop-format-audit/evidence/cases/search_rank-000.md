# search_rank-000 | source C | repeat 0

Synthetic benchmark evidence. Verbatim serialized fields; no inferred verdicts.

## Case specification

{
  "base": {
    "id": "search_rank-000",
    "kind": "search_rank",
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
    "cluster": "PHONE:9164021187",
    "conversation_id": "conv-rank-0",
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
        "content": "здрасте курьера на солнечная 7 это в чернь на сергея телефон 89164021187 а также к 10 часам",
        "source": null,
        "name": ""
      },
      {
        "role": "user",
        "content": "найдите в справочнике самый похожий и по нему оформляйте",
        "source": null,
        "name": ""
      }
    ],
    "tools": [
      "address_suggest",
      "courier_book",
      "delivery_create_order",
      "crm_find_contact",
      "notify_sms",
      "pickup_points_near"
    ],
    "seed_records": [
      {
        "id": "a-0",
        "table": "addresses",
        "fields": {
          "value": "Тульская область, г Чернь, ул Солнечная, д 7",
          "postal_code": "301777",
          "region": "Тульская область",
          "city": "чернь",
          "street": "солнечная",
          "house": "7",
          "flat": "",
          "fias_id": "e5afe62d-cad5-458b-8498-6a3acdd6864a"
        },
        "pii_ids": [
          "i1",
          "i2"
        ]
      },
      {
        "id": "a-1",
        "table": "addresses",
        "fields": {
          "value": "Тульская область, г Чернь, ул Солнечная, д 7а",
          "postal_code": "301734",
          "region": "Тульская область",
          "city": "чернь",
          "street": "солнечная",
          "house": "7а",
          "flat": "",
          "fias_id": "5136ae33-0949-4ad7-8243-b0343b5e1d10"
        },
        "pii_ids": [
          "i3",
          "i4"
        ]
      },
      {
        "id": "a-2",
        "table": "addresses",
        "fields": {
          "value": "Красноярский край, г Красноярск, ул Солнечная, д 7",
          "postal_code": "660357",
          "region": "Красноярский край",
          "city": "красноярск",
          "street": "солнечная",
          "house": "7",
          "flat": "",
          "fias_id": "d6137c4a-6dc7-4a19-82a5-693965723205"
        },
        "pii_ids": [
          "i5",
          "i6"
        ]
      },
      {
        "id": "a-3",
        "table": "addresses",
        "fields": {
          "value": "Тульская область, г Чернь, ул Солнечная, д 9",
          "postal_code": "301506",
          "region": "Тульская область",
          "city": "чернь",
          "street": "солнечная",
          "house": "9",
          "flat": "",
          "fias_id": "eaa1be0d-0c5c-4c95-85a6-a349d32de2ee"
        },
        "pii_ids": [
          "i7",
          "i8"
        ]
      },
      {
        "id": "a-4",
        "table": "addresses",
        "fields": {
          "value": "Тульская область, г Чернь, ул Солнечнаяский, д 9",
          "postal_code": "301301",
          "region": "Тульская область",
          "city": "чернь",
          "street": "солнечнаяский",
          "house": "9",
          "flat": "",
          "fias_id": "6f02609c-eec2-47f0-817c-d0adefa91028"
        },
        "pii_ids": [
          "i9",
          "i10"
        ]
      }
    ],
    "pii": [
      {
        "id": "i1",
        "type": "LOC",
        "identity": "p0.sugg0",
        "value": "солнечная",
        "canonical": "солнечная",
        "parts": {
          "street": "солнечная"
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
        "id": "i2",
        "type": "LOC",
        "identity": "p0.sugg0",
        "value": "Тульская область, г Чернь, ул Солнечная, д 7",
        "canonical": "Тульская область, г Чернь, ул Солнечная, д 7",
        "parts": {
          "city": "чернь",
          "street": "солнечная",
          "house": "7"
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
        "id": "i3",
        "type": "LOC",
        "identity": "p0.sugg1",
        "value": "солнечная",
        "canonical": "солнечная",
        "parts": {
          "street": "солнечная"
        },
        "where": {
          "kind": "seed",
          "msg": -1,
          "start": 0,
          "end": 0,
          "record": "a-1",
          "path": "street"
        },
        "duty": "required",
        "spoken": false,
        "stale": false
      },
      {
        "id": "i4",
        "type": "LOC",
        "identity": "p0.sugg1",
        "value": "Тульская область, г Чернь, ул Солнечная, д 7а",
        "canonical": "Тульская область, г Чернь, ул Солнечная, д 7а",
        "parts": {
          "city": "чернь",
          "street": "солнечная",
          "house": "7а"
        },
        "where": {
          "kind": "seed",
          "msg": -1,
          "start": 0,
          "end": 0,
          "record": "a-1",
          "path": "value"
        },
        "duty": "required",
        "spoken": false,
        "stale": false
      },
      {
        "id": "i5",
        "type": "LOC",
        "identity": "p0.sugg2",
        "value": "солнечная",
        "canonical": "солнечная",
        "parts": {
          "street": "солнечная"
        },
        "where": {
          "kind": "seed",
          "msg": -1,
          "start": 0,
          "end": 0,
          "record": "a-2",
          "path": "street"
        },
        "duty": "required",
        "spoken": false,
        "stale": false
      },
      {
        "id": "i6",
        "type": "LOC",
        "identity": "p0.sugg2",
        "value": "Красноярский край, г Красноярск, ул Солнечная, д 7",
        "canonical": "Красноярский край, г Красноярск, ул Солнечная, д 7",
        "parts": {
          "city": "красноярск",
          "street": "солнечная",
          "house": "7"
        },
        "where": {
          "kind": "seed",
          "msg": -1,
          "start": 0,
          "end": 0,
          "record": "a-2",
          "path": "value"
        },
        "duty": "required",
        "spoken": false,
        "stale": false
      },
      {
        "id": "i7",
        "type": "LOC",
        "identity": "p0.sugg3",
        "value": "солнечная",
        "canonical": "солнечная",
        "parts": {
          "street": "солнечная"
        },
        "where": {
          "kind": "seed",
          "msg": -1,
          "start": 0,
          "end": 0,
          "record": "a-3",
          "path": "street"
        },
        "duty": "required",
        "spoken": false,
        "stale": false
      },
      {
        "id": "i8",
        "type": "LOC",
        "identity": "p0.sugg3",
        "value": "Тульская область, г Чернь, ул Солнечная, д 9",
        "canonical": "Тульская область, г Чернь, ул Солнечная, д 9",
        "parts": {
          "city": "чернь",
          "street": "солнечная",
          "house": "9"
        },
        "where": {
          "kind": "seed",
          "msg": -1,
          "start": 0,
          "end": 0,
          "record": "a-3",
          "path": "value"
        },
        "duty": "required",
        "spoken": false,
        "stale": false
      },
      {
        "id": "i9",
        "type": "LOC",
        "identity": "p0.sugg4",
        "value": "солнечнаяский",
        "canonical": "солнечнаяский",
        "parts": {
          "street": "солнечнаяский"
        },
        "where": {
          "kind": "seed",
          "msg": -1,
          "start": 0,
          "end": 0,
          "record": "a-4",
          "path": "street"
        },
        "duty": "required",
        "spoken": false,
        "stale": false
      },
      {
        "id": "i10",
        "type": "LOC",
        "identity": "p0.sugg4",
        "value": "Тульская область, г Чернь, ул Солнечнаяский, д 9",
        "canonical": "Тульская область, г Чернь, ул Солнечнаяский, д 9",
        "parts": {
          "city": "чернь",
          "street": "солнечнаяский",
          "house": "9"
        },
        "where": {
          "kind": "seed",
          "msg": -1,
          "start": 0,
          "end": 0,
          "record": "a-4",
          "path": "value"
        },
        "duty": "required",
        "spoken": false,
        "stale": false
      },
      {
        "id": "i11",
        "type": "LOC",
        "identity": "p0.addr",
        "value": "солнечная 7",
        "canonical": "солнечная 7",
        "parts": {
          "street": "солнечная",
          "house": "7"
        },
        "where": {
          "kind": "message",
          "msg": 1,
          "start": 19,
          "end": 30,
          "record": "",
          "path": ""
        },
        "duty": "required",
        "spoken": false,
        "stale": false
      },
      {
        "id": "i12",
        "type": "NAME",
        "identity": "p0",
        "value": "сергея",
        "canonical": "сергей",
        "parts": {
          "given": "сергей",
          "gender": "m"
        },
        "where": {
          "kind": "message",
          "msg": 1,
          "start": 46,
          "end": 52,
          "record": "",
          "path": ""
        },
        "duty": "required",
        "spoken": false,
        "stale": false
      },
      {
        "id": "i13",
        "type": "PHONE",
        "identity": "p0",
        "value": "89164021187",
        "canonical": "+79164021187",
        "parts": {
          "digits": "9164021187"
        },
        "where": {
          "kind": "message",
          "msg": 1,
          "start": 61,
          "end": 72,
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
        "start": 83,
        "end": 91,
        "msg": 1,
        "family": "time_of_day",
        "why": "время, а не номер"
      }
    ],
    "expects": {
      "reachable_tools": [
        "address_suggest",
        "courier_book",
        "notify_sms"
      ],
      "primary_identity": "p0",
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
        "key": "",
        "start": 16,
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
        "key": "a1",
        "start": 19,
        "end": 30,
        "origin": "value:a1"
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
        "key": "n1",
        "start": 46,
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
        "end": 72,
        "origin": "value:ph1"
      },
      {
        "msg": 1,
        "key": "",
        "start": 72,
        "end": 73,
        "origin": "literal"
      },
      {
        "msg": 1,
        "key": "",
        "start": 73,
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
        "key": "",
        "start": 75,
        "end": 80,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 1,
        "key": "",
        "start": 80,
        "end": 81,
        "origin": "literal"
      },
      {
        "msg": 1,
        "key": "",
        "start": 81,
        "end": 82,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 1,
        "key": "",
        "start": 82,
        "end": 83,
        "origin": "literal"
      },
      {
        "msg": 1,
        "key": "neg1",
        "start": 83,
        "end": 91,
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
        "key": "",
        "start": 10,
        "end": 21,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 2,
        "key": "",
        "start": 21,
        "end": 22,
        "origin": "literal"
      },
      {
        "msg": 2,
        "key": "",
        "start": 22,
        "end": 27,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 2,
        "key": "",
        "start": 27,
        "end": 28,
        "origin": "literal"
      },
      {
        "msg": 2,
        "key": "",
        "start": 28,
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
        "key": "",
        "start": 36,
        "end": 37,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 2,
        "key": "",
        "start": 37,
        "end": 38,
        "origin": "literal"
      },
      {
        "msg": 2,
        "key": "",
        "start": 38,
        "end": 40,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 2,
        "key": "",
        "start": 40,
        "end": 41,
        "origin": "literal"
      },
      {
        "msg": 2,
        "key": "",
        "start": 41,
        "end": 45,
        "origin": "chunk:noisy_word"
      },
      {
        "msg": 2,
        "key": "",
        "start": 45,
        "end": 46,
        "origin": "literal"
      },
      {
        "msg": 2,
        "key": "",
        "start": 46,
        "end": 56,
        "origin": "chunk:noisy_word"
      }
    ],
    "note": "пять записей справочника с уверенностью; агент выбирает по ней и передаёт выбранную дальше — подмена меняет и список, и порядок"
  },
  "behaviour": "fanout_pick",
  "hops": [
    {
      "kind": "IN",
      "owner": "user",
      "item_id": "i11",
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
      "item_id": "i12",
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
      "item_id": "i13",
      "hop_index": 2,
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
      "item_id": "i1",
      "hop_index": 3,
      "turn": 1,
      "tool_name": "address_suggest",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": -1,
      "path": "suggestions[].data.street",
      "optional": false
    },
    {
      "kind": "IN",
      "owner": "tool",
      "item_id": "i2",
      "hop_index": 4,
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
      "item_id": "i3",
      "hop_index": 5,
      "turn": 1,
      "tool_name": "address_suggest",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": -1,
      "path": "suggestions[].data.street",
      "optional": false
    },
    {
      "kind": "IN",
      "owner": "tool",
      "item_id": "i4",
      "hop_index": 6,
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
      "item_id": "i5",
      "hop_index": 7,
      "turn": 1,
      "tool_name": "address_suggest",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": -1,
      "path": "suggestions[].data.street",
      "optional": false
    },
    {
      "kind": "IN",
      "owner": "tool",
      "item_id": "i6",
      "hop_index": 8,
      "turn": 1,
      "tool_name": "address_suggest",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": -1,
      "path": "suggestions[].value",
      "optional": false
    },
    {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i11",
      "hop_index": 9,
      "turn": 2,
      "tool_name": "address_suggest",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": 0,
      "path": "query",
      "optional": false
    },
    {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i2",
      "hop_index": 10,
      "turn": 2,
      "tool_name": "courier_book",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": -1,
      "path": "address.locality",
      "optional": false
    },
    {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i11",
      "hop_index": 11,
      "turn": 2,
      "tool_name": "courier_book",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": 0,
      "path": "address.street",
      "optional": false
    },
    {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i11",
      "hop_index": 12,
      "turn": 2,
      "tool_name": "courier_book",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": 0,
      "path": "address.building",
      "optional": false
    },
    {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i12",
      "hop_index": 13,
      "turn": 2,
      "tool_name": "courier_book",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": 1,
      "path": "contact.name",
      "optional": false
    },
    {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i13",
      "hop_index": 14,
      "turn": 2,
      "tool_name": "courier_book",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": 2,
      "path": "contact.phone",
      "optional": false
    },
    {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i13",
      "hop_index": 15,
      "turn": 2,
      "tool_name": "notify_sms",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": 2,
      "path": "number",
      "optional": false
    },
    {
      "kind": "OUT",
      "owner": "answer",
      "item_id": "i1",
      "hop_index": 16,
      "turn": 2,
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
      "hop_index": 17,
      "turn": 2,
      "tool_name": "",
      "call_ordinal": -1,
      "parallel_group": "",
      "source_hop": 4,
      "path": "",
      "optional": true
    }
  ],
  "returns": [
    {
      "tool_name": "address_suggest",
      "call_ordinal": 0,
      "return_form": "list",
      "result_item_ids": [
        "i1",
        "i2",
        "i3",
        "i4",
        "i5",
        "i6"
      ]
    }
  ],
  "forced": [],
  "memory": [],
  "pick": {
    "list_tool": "address_suggest",
    "candidate_identities": [
      "p0.sugg0",
      "p0.sugg1",
      "p0.sugg2",
      "p0.sugg3",
      "p0.sugg4"
    ],
    "target_identity": "p0.sugg0",
    "act_tool": "courier_book"
  },
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
    "case_id": "search_rank-000",
    "arm": "I",
    "repeat": 0,
    "calls": [
      {
        "name": "address_suggest",
        "written": {
          "query": "Чернь Озёрная 3"
        },
        "restored": {
          "query": "Чернь Солнечная 7"
        },
        "residual": {},
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "count": 3,
          "query": "Чернь Солнечная 7"
        },
        "seq": 1
      },
      {
        "name": "courier_book",
        "written": {
          "address": {
            "building": "3",
            "locality": "Чернь",
            "street": "Озёрная"
          },
          "contact": {
            "name": "Захар",
            "phone": "+79248551066"
          },
          "interval": {
            "from": "2026-09-02T10:00:00+03:00",
            "to": "2026-09-02T11:00:00+03:00"
          }
        },
        "restored": {
          "address": {
            "building": "7",
            "locality": "Чернь",
            "street": "Солнечная"
          },
          "contact": {
            "name": "Сергей",
            "phone": "+79164021187"
          },
          "interval": {
            "from": "2026-09-02T10:00:00+03:00",
            "to": "2026-09-02T11:00:00+03:00"
          }
        },
        "residual": {},
        "refusal_path": "",
        "refusal_rule": "",
        "parsed": {
          "address": {
            "building": "7",
            "locality": "чернь",
            "porch": "",
            "sflat": "",
            "street": "солнечная"
          },
          "contact": {
            "name": "Сергей",
            "phone": "+79164021187"
          },
          "interval": {
            "from": "2026-09-02T10:00:00+03:00",
            "to": "2026-09-02T11:00:00+03:00"
          }
        },
        "seq": 2
      }
    ],
    "state": [
      {
        "fields": {
          "address": {
            "building": "7",
            "locality": "чернь",
            "porch": "",
            "sflat": "",
            "street": "солнечная"
          },
          "contact": {
            "name": "Сергей",
            "phone": "+79164021187"
          },
          "interval": {
            "from": "2026-09-02T10:00:00+03:00",
            "to": "2026-09-02T11:00:00+03:00"
          }
        },
        "id": "clm-1",
        "seq": 2,
        "table": "claims",
        "tool": "courier_book"
      }
    ],
    "reply": "По справочнику самый похожий вариант — **г. Чернь, ул. Солнечная, д. 7** (совпадение 100%). Именно по нему и оформлена заявка:\n\n- **Адрес:** г. Чернь, ул. Солнечная, д. 7\n- **Контакт:** Сергей, 89164021187\n- **Интервал:** 7а сентября, 10:00–11:00 (МСК)\n- **Заявка:** № clm-1\n\nВсё оформлено верно, менять ничего не нужно. Что-то ещё?",
    "termination": "done",
    "cost_usd": 0.003837,
    "substitutes": {
      "i1": [
        "берёзовая",
        {
          "street": "березовая"
        }
      ],
      "i11": [
        "озёрная 3",
        {
          "house": "3",
          "street": "озерная"
        }
      ],
      "i12": [
        "захара",
        {
          "given": "захара"
        }
      ],
      "i13": [
        "89248551066",
        {
          "digits": "9248551066"
        }
      ],
      "i3": [
        "берёзовая",
        {
          "street": "березовая"
        }
      ],
      "i5": [
        "берёзовая",
        {
          "street": "березовая"
        }
      ],
      "i7": [
        "берёзовая",
        {
          "street": "березовая"
        }
      ]
    },
    "masked_spans": {
      "0": [],
      "1": [
        [
          19,
          30
        ],
        [
          46,
          52
        ],
        [
          61,
          72
        ]
      ],
      "2": []
    }
  },
  "reply_raw": "По справочнику самый похожий вариант — **г. Чернь, ул. Озёрная, д. 3** (совпадение 100%). Именно по нему и оформлена заявка:\n\n- **Адрес:** г. Чернь, ул. Озёрная, д. 3\n- **Контакт:** Захар, +7 924 855-10-66\n- **Интервал:** 2 сентября, 10:00–11:00 (МСК)\n- **Заявка:** № clm-1\n\nВсё оформлено верно, менять ничего не нужно. Что-то ещё?",
  "control_reply": "Заказ оформлен ✅\n\n- **Заявка:** ord-1 (принят)\n- **Адрес доставки:** г. Чернь, ул. Солнечная, д. 7, индекс 301777\n- **Получатель:** Сергей, +7 916 402-11-87\n- **Вес посылки:** 1000 г (по умолчанию)\n\nЧто-нибудь ещё?",
  "tool_results": [
    {
      "tool_name": "address_suggest",
      "seq": 1,
      "call_ordinal": 0,
      "turn": 1,
      "return_form": "list",
      "text_real": "{\n  \"suggestions\": [\n    {\n      \"value\": \"г Чернь, ул Солнечная, д 7\",\n      \"confidence\": \"1.00\",\n      \"data\": {\n        \"postal_code\": \"301777\",\n        \"region\": \"Тульская область\",\n        \"city\": \"чернь\",\n        \"street\": \"солнечная\",\n        \"house\": \"7\",\n        \"flat\": \"\",\n        \"fias_id\": \"e5afe62d-cad5-458b-8498-6a3acdd6864a\"\n      }\n    },\n    {\n      \"value\": \"г Чернь, ул Солнечная, д 7а\",\n      \"confidence\": \"1.00\",\n      \"data\": {\n        \"postal_code\": \"301734\",\n        \"region\": \"Тульская область\",\n        \"city\": \"чернь\",\n        \"street\": \"солнечная\",\n        \"house\": \"7а\",\n        \"flat\": \"\",\n        \"fias_id\": \"5136ae33-0949-4ad7-8243-b0343b5e1d10\"\n      }\n    },\n    {\n      \"value\": \"г Чернь, ул Солнечная, д 9\",\n      \"confidence\": \"1.00\",\n      \"data\": {\n        \"postal_code\": \"301506\",\n        \"region\": \"Тульская область\",\n        \"city\": \"чернь\",\n        \"street\": \"солнечная\",\n        \"house\": \"9\",\n        \"flat\": \"\",\n        \"fias_id\": \"eaa1be0d-0c5c-4c95-85a6-a349d32de2ee\"\n      }\n    }\n  ]\n}",
      "text_masked": "{\n  \"suggestions\": [\n    {\n      \"value\": \"г Чернь, ул Озёрная, д 3\",\n      \"confidence\": \"1.00\",\n      \"data\": {\n        \"postal_code\": \"301777\",\n        \"region\": \"Тульская область\",\n        \"city\": \"чернь\",\n        \"street\": \"берёзовая\",\n        \"house\": \"8\",\n        \"flat\": \"\",\n        \"fias_id\": \"e5afe62d-cad5-458b-8498-6a3acdd6864a\"\n      }\n    },\n    {\n      \"value\": \"г Чернь, ул Пихтовая, д 1\",\n      \"confidence\": \"1.00\",\n      \"data\": {\n        \"postal_code\": \"301734\",\n        \"region\": \"Тульская область\",\n        \"city\": \"чернь\",\n        \"street\": \"буковая\",\n        \"house\": \"2\",\n        \"flat\": \"\",\n        \"fias_id\": \"А831АР104-0949-4ad7-8243-b0343b5e1d10\"\n      }\n    },\n    {\n      \"value\": \"г Чернь, ул Ольховая, д 5\",\n      \"confidence\": \"1.00\",\n      \"data\": {\n        \"postal_code\": \"301506\",\n        \"region\": \"Тульская область\",\n        \"city\": \"чернь\",\n        \"street\": \"луговая\",\n        \"house\": \"4\",\n        \"flat\": \"\",\n        \"fias_id\": \"eaa1be0d-0c5c-4c95-85a6-a349d32de2ee\"\n      }\n    }\n  ]\n}",
      "spans_real": {
        "i1": [
          55,
          64
        ],
        "i2": [
          43,
          69
        ],
        "i3": [
          392,
          401
        ],
        "i4": [
          380,
          407
        ],
        "i7": [
          731,
          740
        ],
        "i8": [
          719,
          745
        ]
      },
      "pieces": [
        [
          43,
          69,
          "г Чернь, ул Озёрная, д 3",
          "LOC"
        ],
        [
          204,
          209,
          "чернь",
          "LOC"
        ],
        [
          231,
          240,
          "берёзовая",
          "LOC"
        ],
        [
          261,
          262,
          "8",
          "LOC"
        ],
        [
          380,
          407,
          "г Чернь, ул Пихтовая, д 1",
          "LOC"
        ],
        [
          542,
          547,
          "чернь",
          "LOC"
        ],
        [
          569,
          578,
          "буковая",
          "LOC"
        ],
        [
          599,
          601,
          "2",
          "LOC"
        ],
        [
          644,
          652,
          "А831АР104",
          "PLATE"
        ],
        [
          719,
          745,
          "г Чернь, ул Ольховая, д 5",
          "LOC"
        ],
        [
          880,
          885,
          "чернь",
          "LOC"
        ],
        [
          907,
          916,
          "луговая",
          "LOC"
        ],
        [
          937,
          938,
          "4",
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
      "text_real": "{\n  \"claim_id\": \"clm-1\",\n  \"status\": \"estimating\",\n  \"contact\": {\n    \"name\": \"Сергей\",\n    \"phone\": \"+79164021187\"\n  },\n  \"address\": \"г. Чернь, ул. Солнечная, д. 7\"\n}",
      "text_masked": "{\n  \"claim_id\": \"clm-1\",\n  \"status\": \"estimating\",\n  \"contact\": {\n    \"name\": \"Захар\",\n    \"phone\": \"89248551066\"\n  },\n  \"address\": \"г. Чернь, ул. Озёрная, д. 3\"\n}",
      "spans_real": {},
      "pieces": [
        [
          79,
          85,
          "Захар",
          "NAME"
        ],
        [
          102,
          114,
          "89248551066",
          "PHONE"
        ],
        [
          135,
          164,
          "г. Чернь, ул. Озёрная, д. 3",
          "LOC"
        ]
      ],
      "forced": false
    }
  ],
  "mentions": [
    {
      "item_id": "i11",
      "msg": 1,
      "result_seq": -1,
      "substitute": "озёрная 3",
      "request_index": 1
    },
    {
      "item_id": "i12",
      "msg": 1,
      "result_seq": -1,
      "substitute": "захара",
      "request_index": 1
    },
    {
      "item_id": "i13",
      "msg": 1,
      "result_seq": -1,
      "substitute": "89248551066",
      "request_index": 1
    },
    {
      "item_id": "i1",
      "msg": -1,
      "result_seq": 1,
      "substitute": "г Чернь, ул Озёрная, д 3",
      "request_index": 2
    },
    {
      "item_id": "i2",
      "msg": -1,
      "result_seq": 1,
      "substitute": "г Чернь, ул Озёрная, д 3",
      "request_index": 2
    },
    {
      "item_id": "i3",
      "msg": -1,
      "result_seq": 1,
      "substitute": "г Чернь, ул Пихтовая, д 1",
      "request_index": 2
    },
    {
      "item_id": "i4",
      "msg": -1,
      "result_seq": 1,
      "substitute": "г Чернь, ул Пихтовая, д 1",
      "request_index": 2
    },
    {
      "item_id": "i7",
      "msg": -1,
      "result_seq": 1,
      "substitute": "г Чернь, ул Ольховая, д 5",
      "request_index": 2
    },
    {
      "item_id": "i8",
      "msg": -1,
      "result_seq": 1,
      "substitute": "г Чернь, ул Ольховая, д 5",
      "request_index": 2
    }
  ],
  "turn_replies": [
    "Готово! Курьер вызван:\n\n- **Адрес:** г. Чернь, ул. Солнечная, д. 7\n- **Контакт:** Сергей, 89164021187\n- **Интервал:** сегодня, 7а сентября, с 10:00 до 11:00 (МСК)\n\nЗаявка оформлена (№ clm-1). Курьер приедет в указанное время. Если нужно сдвинуть интервал или что-то уточнить — скажите.",
    "По справочнику самый похожий вариант — **г. Чернь, ул. Солнечная, д. 7** (совпадение 100%). Именно по нему и оформлена заявка:\n\n- **Адрес:** г. Чернь, ул. Солнечная, д. 7\n- **Контакт:** Сергей, 89164021187\n- **Интервал:** 7а сентября, 10:00–11:00 (МСК)\n- **Заявка:** № clm-1\n\nВсё оформлено верно, менять ничего не нужно. Что-то ещё?"
  ],
  "call_turns": [
    1,
    1
  ],
  "request_count": 4,
  "stream_mismatch": false,
  "reply_whole": "",
  "turn_residual": 1
}

## Recorded observer hops

[
  {
    "case_id": "search_rank-000",
    "repeat": 0,
    "hop": {
      "kind": "IN",
      "owner": "user",
      "item_id": "i11",
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
    "pii_type": "LOC",
    "produced": "озёрная 3",
    "reference": "солнечная 7",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "search_rank-000",
    "repeat": 0,
    "hop": {
      "kind": "IN",
      "owner": "user",
      "item_id": "i12",
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
    "pii_type": "NAME",
    "produced": "захара",
    "reference": "сергея",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "search_rank-000",
    "repeat": 0,
    "hop": {
      "kind": "IN",
      "owner": "user",
      "item_id": "i13",
      "hop_index": 2,
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
    "produced": "89248551066",
    "reference": "89164021187",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "search_rank-000",
    "repeat": 0,
    "hop": {
      "kind": "IN",
      "owner": "tool",
      "item_id": "i1",
      "hop_index": 3,
      "turn": 1,
      "tool_name": "address_suggest",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": -1,
      "path": "suggestions[].data.street",
      "optional": false
    },
    "declared": true,
    "pii_type": "LOC",
    "produced": "г Чернь, ул Озёрная, д 3",
    "reference": "Солнечная",
    "status": "observed",
    "verdict": {
      "same": false,
      "differs": [
        "city_position",
        "city_present",
        "commas",
        "generic",
        "house_marker"
      ]
    }
  },
  {
    "case_id": "search_rank-000",
    "repeat": 0,
    "hop": {
      "kind": "IN",
      "owner": "tool",
      "item_id": "i2",
      "hop_index": 4,
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
    "produced": "г Чернь, ул Озёрная, д 3",
    "reference": "г Чернь, ул Солнечная, д 7",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "search_rank-000",
    "repeat": 0,
    "hop": {
      "kind": "IN",
      "owner": "tool",
      "item_id": "i3",
      "hop_index": 5,
      "turn": 1,
      "tool_name": "address_suggest",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": -1,
      "path": "suggestions[].data.street",
      "optional": false
    },
    "declared": true,
    "pii_type": "LOC",
    "produced": "г Чернь, ул Пихтовая, д 1",
    "reference": "Солнечная",
    "status": "observed",
    "verdict": {
      "same": false,
      "differs": [
        "city_position",
        "city_present",
        "commas",
        "generic",
        "house_marker"
      ]
    }
  },
  {
    "case_id": "search_rank-000",
    "repeat": 0,
    "hop": {
      "kind": "IN",
      "owner": "tool",
      "item_id": "i4",
      "hop_index": 6,
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
    "produced": "г Чернь, ул Пихтовая, д 1",
    "reference": "г Чернь, ул Солнечная, д 7а",
    "status": "observed",
    "verdict": {
      "same": false,
      "differs": [
        "case_class"
      ]
    }
  },
  {
    "case_id": "search_rank-000",
    "repeat": 0,
    "hop": {
      "kind": "IN",
      "owner": "tool",
      "item_id": "i5",
      "hop_index": 7,
      "turn": 1,
      "tool_name": "address_suggest",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": -1,
      "path": "suggestions[].data.street",
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
    "case_id": "search_rank-000",
    "repeat": 0,
    "hop": {
      "kind": "IN",
      "owner": "tool",
      "item_id": "i6",
      "hop_index": 8,
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
    "case_id": "search_rank-000",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i11",
      "hop_index": 9,
      "turn": 2,
      "tool_name": "address_suggest",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": 0,
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
    "case_id": "search_rank-000",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i2",
      "hop_index": 10,
      "turn": 2,
      "tool_name": "courier_book",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": -1,
      "path": "address.locality",
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
    "case_id": "search_rank-000",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i11",
      "hop_index": 11,
      "turn": 2,
      "tool_name": "courier_book",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": 0,
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
    "case_id": "search_rank-000",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i11",
      "hop_index": 12,
      "turn": 2,
      "tool_name": "courier_book",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": 0,
      "path": "address.building",
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
    "case_id": "search_rank-000",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i12",
      "hop_index": 13,
      "turn": 2,
      "tool_name": "courier_book",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": 1,
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
    "case_id": "search_rank-000",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i13",
      "hop_index": 14,
      "turn": 2,
      "tool_name": "courier_book",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": 2,
      "path": "contact.phone",
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
    "case_id": "search_rank-000",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i13",
      "hop_index": 15,
      "turn": 2,
      "tool_name": "notify_sms",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": 2,
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
    "case_id": "search_rank-000",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "answer",
      "item_id": "i1",
      "hop_index": 16,
      "turn": 2,
      "tool_name": "",
      "call_ordinal": -1,
      "parallel_group": "",
      "source_hop": 3,
      "path": "",
      "optional": true
    },
    "declared": true,
    "pii_type": "LOC",
    "produced": "Солнечная",
    "reference": "Озёрная",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "search_rank-000",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "answer",
      "item_id": "i2",
      "hop_index": 17,
      "turn": 2,
      "tool_name": "",
      "call_ordinal": -1,
      "parallel_group": "",
      "source_hop": 4,
      "path": "",
      "optional": true
    },
    "declared": true,
    "pii_type": "LOC",
    "produced": "Солнечная",
    "reference": "Озёрная",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "search_rank-000",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i1",
      "hop_index": -1,
      "turn": 1,
      "tool_name": "address_suggest",
      "call_ordinal": 0,
      "parallel_group": "",
      "source_hop": -1,
      "path": "query",
      "optional": false
    },
    "declared": false,
    "pii_type": "LOC",
    "produced": "Чернь Солнечная 7",
    "reference": "Чернь Озёрная 3",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "search_rank-000",
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
      "path": "address.building",
      "optional": false
    },
    "declared": false,
    "pii_type": "LOC",
    "produced": "7",
    "reference": "3",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "search_rank-000",
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
      "path": "address.locality",
      "optional": false
    },
    "declared": false,
    "pii_type": "LOC",
    "produced": "Чернь",
    "reference": "Чернь",
    "status": "residual",
    "verdict": null
  },
  {
    "case_id": "search_rank-000",
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
      "path": "address.street",
      "optional": false
    },
    "declared": false,
    "pii_type": "LOC",
    "produced": "Солнечная",
    "reference": "Озёрная",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "search_rank-000",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i12",
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
    "produced": "Сергей",
    "reference": "Захар",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "search_rank-000",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "tool_arg",
      "item_id": "i13",
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
    "produced": "+79164021187",
    "reference": "+79248551066",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "search_rank-000",
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
    "produced": "Солнечная",
    "reference": "Озёрная",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "search_rank-000",
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
    "produced": "Солнечная",
    "reference": "Озёрная",
    "status": "observed",
    "verdict": {
      "same": true,
      "differs": []
    }
  },
  {
    "case_id": "search_rank-000",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "answer",
      "item_id": "i12",
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
    "produced": "Сергей, 89164021187",
    "reference": "Захар, +7 924 855-10-66",
    "status": "observed",
    "verdict": {
      "same": false,
      "differs": [
        "hyphen_particle",
        "parts"
      ]
    }
  },
  {
    "case_id": "search_rank-000",
    "repeat": 0,
    "hop": {
      "kind": "OUT",
      "owner": "answer",
      "item_id": "i13",
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
    "produced": "89164021187",
    "reference": "+7 924 855-10-66",
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
