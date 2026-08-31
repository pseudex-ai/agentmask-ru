"""What the two speech corpora actually contain -- and, more usefully, what they
CANNOT contain, which is the list v3 has to generate from templates.

Nothing here consults `pseudex/`. Asking the detector to profile the corpus can
only return what the detector already knows; the first voice set was built that
way and reported 100% where the truth was 38.6%.

Licensing is enforced in code, not in a comment: OpenSTT asr_calls_2_val is
CC BY-NC 4.0, so only its hashes and labels may be written to disk. SOVA
RuDevices is CC BY 4.0 and its text may be quoted verbatim.
"""

import collections
import hashlib
import json
import os
import re
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import probes as P

CACHE = "/Users/igor/.cache/pseudex-bench"
CALLS = os.path.join(CACHE, "speech_calls.jsonl")
RUDEV = os.path.join(CACHE, "speech_rudevices.jsonl")
VOICE_LABELS = os.path.join(CACHE, "voice_addresses.json")
RUDEV_LABELS = os.path.join(CACHE, "rudevices_addresses.json")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mined",
                   "reference_distribution.json")

COMMON_RANK = 400  # how many of the corpus's own top words disqualify a name shape


def load_jsonl(path):
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line)["text"] for line in fh]


def key_of(text):
    return hashlib.blake2b(text.encode("utf-8"), digest_size=6).hexdigest()


def quote(text, source):
    """Verbatim only where the licence allows it."""
    if source == "rudevices":
        return {"source": source, "text": text}
    return {"source": source, "key": key_of(text),
            "text_withheld": "CC BY-NC 4.0 -- hashes and labels only"}


# --- register ---------------------------------------------------------------

def register_stats(replicas):
    n = len(replicas)
    words = [len(t.split()) for t in replicas]
    chars = [len(t) for t in replicas]
    runs = [P.longest_run(t.split()) for t in replicas]
    run_hist = collections.Counter(runs)
    return {
        "replicas": n,
        "share_with_any_digit": sum(1 for t in replicas if re.search(r"[0-9]", t)) / n,
        "share_starting_capital": sum(1 for t in replicas if t[:1].isupper()) / n,
        "share_ending_period": sum(1 for t in replicas if t.rstrip().endswith(".")) / n,
        "share_any_sentence_punctuation": sum(
            1 for t in replicas if re.search(r"[,.!?;:]", t)) / n,
        "share_with_hyphen": sum(1 for t in replicas if "-" in t) / n,
        "share_with_latin": sum(1 for t in replicas if re.search(r"[A-Za-z]", t)) / n,
        "share_single_word": sum(1 for w in words if w == 1) / n,
        "words_mean": round(statistics.mean(words), 2),
        "words_median": statistics.median(words),
        "words_p90": sorted(words)[int(0.9 * n)],
        "words_max": max(words),
        "chars_mean": round(statistics.mean(chars), 2),
        "chars_median": statistics.median(chars),
        "chars_p90": sorted(chars)[int(0.9 * n)],
        "chars_max": max(chars),
        "share_numeral_run_ge1": sum(1 for r in runs if r >= 1) / n,
        "share_numeral_run_ge3": sum(1 for r in runs if r >= 3) / n,
        "share_numeral_run_ge5": sum(1 for r in runs if r >= 5) / n,
        "share_numeral_run_ge7": sum(1 for r in runs if r >= 7) / n,
        "numeral_run_histogram": {str(k): run_hist[k] for k in sorted(run_hist)},
    }


# --- PII presence -----------------------------------------------------------

def pii_counts(replicas, source):
    """One dict per type. Counts are over DISTINCT replicas: one address said by
    seven callers is one value and seven occurrences, and an interval computed
    on occurrences flatters us."""
    hits = collections.defaultdict(list)
    for text in replicas:
        tokens = text.split()
        strong, loose, cue, _ = P.name_probe(text, tokens)
        if strong:
            hits["name_strong"].append(text)
        if loose and not strong:
            hits["name_loose_only"].append(text)
        if cue and not strong:
            hits["name_cue_without_value"].append(text)
        ok, _ = P.address_probe(tokens, text)
        if ok:
            hits["address_marker_visible"].append(text)
        ok, _ = P.phone_probe(tokens, text)
        if ok:
            hits["phone"].append(text)
        if P.email_probe(text)[0]:
            hits["email"].append(text)
        if P.dob_probe(tokens, text)[0]:
            hits["dob"].append(text)
        if P.SNILS_CUE.search(text):
            hits["snils_word"].append(text)
        if P.INN_CUE.search(text):
            hits["inn_word"].append(text)
        if P.CARD_STRICT.search(text):
            hits["card_word"].append(text)
        if P.PASSPORT_CUE.search(text):
            hits["passport_word"].append(text)
        if P.plate_probe(tokens, text)[0]:
            hits["plate"].append(text)
    return hits


def with_value(texts, min_run):
    """A document word is not a document number. Splitting the two is the whole
    finding for СНИЛС, ИНН, карта and паспорт in speech."""
    return [t for t in texts if P.longest_run(t.split()) >= min_run]


# --- address truth from the human labels ------------------------------------

def address_truth():
    """The probe above shares its signals with the street-type vocabulary, so its
    own number is biased upward exactly where the annotation says it is blind.
    The share below comes from the hand labels instead, stratum-weighted."""
    rud = json.load(open(RUDEV_LABELS, encoding="utf-8"))
    voice = json.load(open(VOICE_LABELS, encoding="utf-8"))

    def split(rows, flt):
        rows = [r for r in rows if r.get("filter") == flt]
        gold = [r for r in rows if r["label"] == "адрес с номером"]
        values = sum(len(r.get("spans") or []) for r in gold)
        return rows, gold, values

    m_rows, m_gold, m_val = split(rud, "marker")
    n_rows, n_gold, n_val = split(rud, "number-sample")
    weight = 4805 / 250.0
    est_number_layer = len(n_gold) * weight

    v_marker, v_m_gold, _ = split(voice, "marker")
    v_number, v_n_gold, _ = split(voice, "number")

    return {
        "method": "hand labels, never the detector; two strata counted apart "
                  "because the marker stratum is a census and the number "
                  "stratum is a 250/4805 random sample (weight 19.22)",
        "rudevices": {
            "marker_stratum": {"annotated": len(m_rows), "is_census": True,
                               "address_replicas": len(m_gold),
                               "address_values": m_val},
            "number_stratum": {"annotated": len(n_rows), "stratum_size": 4805,
                               "sample_weight": round(weight, 2),
                               "address_replicas_in_sample": len(n_gold),
                               "address_values_in_sample": n_val,
                               "estimated_address_replicas": round(est_number_layer, 1)},
            "estimated_address_replicas_total": round(len(m_gold) + est_number_layer, 1),
            "unique_replicas": None,  # filled by caller
        },
        "calls": {
            "marker_stratum": {"annotated": len(v_marker), "address_replicas": len(v_m_gold)},
            "number_stratum": {"annotated": len(v_number), "address_replicas": len(v_n_gold),
                               "is_near_census": True},
            "address_replicas_total": len(v_m_gold) + len(v_n_gold),
        },
        "marker_free_share_of_addresses": round(
            est_number_layer / (len(m_gold) + est_number_layer), 3),
        "why_it_matters": "a majority of real spoken addresses carry NO street "
                          "type word and NO house marker -- «ленина пятьдесят», "
                          "«гусева семь». A generator that writes «улица X дом N» "
                          "reproduces the minority shape.",
    }


def distinct_address_values():
    """A value said by seven callers is one value and seven occurrences. Both
    numbers are printed because an interval computed on occurrences flatters us."""
    out = {}
    for name, path in (("rudevices", RUDEV_LABELS), ("calls", VOICE_LABELS)):
        rows = json.load(open(path, encoding="utf-8"))
        occ, vals = 0, set()
        for r in rows:
            if r["label"] != "адрес с номером":
                continue
            for span in (r.get("spans") or []):
                occ += 1
                vals.add(span.strip())
        out[name] = {"occurrences": occ, "distinct_values": len(vals),
                     "repeat_factor": round(occ / len(vals), 2) if vals else None}
    return out


def probe_vs_labels():
    """How blind is the marker-shaped probe, measured against the hand labels.
    Printed so the number above is never mistaken for the probe's own."""
    out = {}
    for name, path, strata in (("rudevices", RUDEV_LABELS, ("marker", "number-sample")),
                               ("calls", VOICE_LABELS, ("marker", "number"))):
        rows = json.load(open(path, encoding="utf-8"))
        per = {}
        for flt in strata:
            sub = [r for r in rows if r.get("filter") == flt]
            gold = [r for r in sub if r["label"] == "адрес с номером"]
            tp = sum(1 for r in gold if P.address_probe(r["text"].split(), r["text"])[0])
            fp = sum(1 for r in sub if r["label"] == "не адрес"
                     and P.address_probe(r["text"].split(), r["text"])[0])
            per[flt] = {"gold": len(gold), "probe_found": tp,
                        "recall": round(tp / len(gold), 3) if gold else None,
                        "false_positives_on_non_address": fp}
        out[name] = per
    return out


# --- lexicon ----------------------------------------------------------------

OPENERS = ("алло", "здравствуйте", "здрасте", "здрасьте", "привет", "приветик",
           "добрый день", "добрый вечер", "доброе утро", "слушаю", "да слушаю",
           "девушка", "молодой человек", "мужчина", "женщина", "уважаемый",
           "простите", "извините", "подскажите", "скажите пожалуйста", "будьте добры")
FILLERS = ("ну", "вот", "короче", "типа", "как бы", "значит", "в общем", "это самое",
           "так сказать", "блин", "слушай", "слушайте", "понимаешь", "понимаете",
           "эээ", "ээ", "ммм", "мм", "аа", "ага", "угу", "да ладно", "то есть",
           "просто", "вообще", "кстати", "по-моему", "наверное", "получается")
INTENTS = ("вызовите", "вызови", "вызвать", "запишите", "запиши", "записать",
           "отправьте", "отправить", "приезжайте", "приедет", "подъедет", "подать",
           "подайте", "заберите", "забрать", "перезвоните", "перезвони", "позвоните",
           "позвони", "оформите", "оформить", "доставьте", "доставить", "закажите",
           "заказать", "нужно", "надо", "хочу", "можно", "дайте", "скажите",
           "подскажите", "найдите", "посмотрите", "проверьте", "уточните", "поеду",
           "поедем", "поехали", "жду", "ждём", "ждем")


def phrase_counts(replicas, phrases):
    joined = [" %s " % t for t in replicas]
    out = {}
    for ph in phrases:
        pat = " %s " % ph
        c = sum(1 for t in joined if pat in t)
        if c:
            out[ph] = c
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))


GLUED_TO = re.compile(r"^(что|кто|как|где|куда|когда|какой|какая|какие|чей|чего|кому)"
                      r"(то|нибудь|либо)$")
DOUBLED = re.compile(r"([аеёиоуыэюя])\1")


def error_lexicon(replicas):
    """ASR artifacts, mined mechanically rather than imagined: a corpus we write
    ourselves has none of these, and the register is defined by them."""
    tok = collections.Counter()
    for t in replicas:
        tok.update(t.split())
    glued = {w: c for w, c in tok.items() if GLUED_TO.match(w)}
    # A doubled vowel is only a stretch when collapsing it yields a word the
    # corpus uses MORE often. Counting every doubled vowel called "вообще",
    # "более" and "россии" transcription errors -- they are ordinary spelling.
    stretched = {}
    for w, c in tok.items():
        if not DOUBLED.search(w) or c < 3:
            continue
        collapsed = re.sub(r"([аеёиоуыэюя])\1+", r"\1", w)
        if collapsed != w and tok.get(collapsed, 0) > c:
            stretched[w] = c
    colloquial = {w: tok[w] for w in
                  ("щас", "ща", "чё", "че", "чо", "тя", "шо", "тока", "токо",
                   "нету", "чото", "щя", "прям", "ниче", "ничё")
                  if tok.get(w)}
    return {
        "glued_indefinite": dict(sorted(glued.items(), key=lambda kv: -kv[1])[:20]),
        "stretched_vowel": dict(sorted(stretched.items(), key=lambda kv: -kv[1])[:20]),
        "colloquial_reduction": dict(sorted(colloquial.items(), key=lambda kv: -kv[1])),
    }


# --- shapes -----------------------------------------------------------------

def find_shapes(pool):
    """pool: list of (text, source). Returns shape rows with a verbatim example."""
    shapes = []

    def add(pattern, matcher, carries, prefer="rudevices"):
        hits = [(t, s) for t, s in pool if matcher(t, t.split())]
        # the shortest quotable hit shows the shape; the first one alphabetically
        # showed whatever happened to start with "а"
        quotable = sorted((t for t, s in hits if s == prefer), key=len)
        mid = [t for t in quotable if 3 <= len(t.split()) <= 12]
        example = None
        if mid:
            example = quote(mid[0], prefer)
        elif quotable:
            example = quote(quotable[0], prefer)
        elif hits:
            example = quote(*hits[0])
        shapes.append({"pattern": pattern, "count": len(hits),
                       "carries": carries, "example": example})

    def fio(text, tk):
        for i in range(len(tk) - 2):
            a, b, c = tk[i], tk[i + 1], tk[i + 2]
            if P.PATRONYMIC.match(c) and P.is_given_name(b) and P._is_surname_shape(a):
                return True
            if P.PATRONYMIC.match(c) and P._is_surname_shape(b) and P.is_given_name(a):
                return True
        return False

    def name_patronymic(text, tk):
        return any(P.is_given_name(tk[i]) and P.PATRONYMIC.match(tk[i + 1])
                   for i in range(len(tk) - 1))

    def bare_given(text, tk):
        strong, loose, _, _ = P.name_probe(text, tk)
        return loose and not strong

    def marked_street(text, tk):
        for i, w in enumerate(tk):
            if P.STREET_TYPE.match(w) and any(P.is_numeral(x) for x in tk[i + 1:i + 5]):
                return True
        return False

    STREET_WORD = re.compile(r"^[а-яё]{5,}(ская|ский|ской|ского|цкая|цкий|овая|евая"
                             r"|ова|ева|ина|ыня|ного|ного|ая|ий|ое)$")

    def markerless_street(text, tk):
        if any(P.STREET_TYPE.match(w) or P.HOUSE_MARK.match(w) for w in tk):
            return False
        for i in range(len(tk) - 1):
            if STREET_WORD.match(tk[i]) and P.is_numeral(tk[i + 1]):
                return True
        return False

    def house_marker(text, tk):
        return any(P.HOUSE_MARK.match(w) and (
            (i + 1 < len(tk) and P.is_numeral(tk[i + 1])) or
            (i and P.is_numeral(tk[i - 1]))) for i, w in enumerate(tk))

    def dictated_number(text, tk):
        return P.longest_run(tk) >= 7 and not P._is_counting(text)

    def counting(text, tk):
        return P.longest_run(tk) >= 4 and P._is_counting(text)

    def year_in_words(text, tk):
        return bool(re.search(r"\b(тысяч[аи]|две тысячи|тысяча девятьсот)\b", text)) \
            and any(P.ORDINAL.match(w) for w in tk)

    def doc_word_no_value(text, tk):
        has_word = bool(P.PASSPORT_CUE.search(text) or P.SNILS_CUE.search(text)
                        or P.INN_CUE.search(text) or P.CARD_STRICT.search(text))
        return has_word and P.longest_run(tk) < 4

    def opener_only(text, tk):
        return len(tk) <= 4 and tk and tk[0] in ("алло", "здравствуйте", "привет", "слушаю")

    add("<фамилия> <имя> <отчество>", fio, ["NAME"])
    add("<имя> <отчество>", name_patronymic, ["NAME"])
    add("<имя> в косвенном падеже без фамилии", bare_given, ["NAME"])
    add("<тип улицы> <название> <число прописью>", marked_street, ["LOC", "ADDR"])
    add("<название улицы> <число прописью> — без типа и без маркера дома",
        markerless_street, ["LOC", "ADDR"])
    add("<маркер дома/квартиры/подъезда> <число прописью>", house_marker, ["ADDR"])
    add("<пробег числительных ≥7> — продиктованный номер", dictated_number, ["PHONE"])
    add("<счётная последовательность раз-два-три> — приманка, не номер",
        counting, [])
    add("<год прописью: две тысячи + порядковое>", year_in_words, ["DATE"])
    add("<слово-документ без значения>", doc_word_no_value, [])
    def intent_plus_address(text, tk):
        return bool(re.search(r"\b(поеду|поедем|подать|подайте|приезжайте|приедет"
                              r"|заберите|адрес|нахожусь|находимся|жду)\b", text)) \
            and (markerless_street(text, tk) or marked_street(text, tk)
                 or house_marker(text, tk))

    def vocative_name(text, tk):
        strong, loose, _, _ = P.name_probe(text, tk)
        return loose and bool(tk) and (P.is_given_name(tk[0])
                                       or (len(tk) > 1 and P.is_given_name(tk[-1])))

    add("<обращение> — реплика из 1-4 слов", opener_only, [])
    add("<намерение> + <адрес> — реплика, из которой строится вызов инструмента",
        intent_plus_address, ["ADDR", "LOC"])
    add("<имя> в позиции обращения — первое или последнее слово реплики",
        vocative_name, ["NAME"])
    return shapes


def main():
    calls = load_jsonl(CALLS)
    rudev = load_jsonl(RUDEV)
    freq = collections.Counter()
    for t in calls + rudev:
        freq.update(t.split())
    P.set_common([w for w, _ in freq.most_common(COMMON_RANK)])

    uc = sorted(set(calls))
    ur = sorted(set(rudev))
    pool = [(t, "calls") for t in uc] + [(t, "rudevices") for t in ur]

    reg = {
        "calls": register_stats(uc),
        "rudevices": register_stats(ur),
        "combined": register_stats(uc + ur),
    }
    reg["calls"]["raw_lines"] = len(calls)
    reg["rudevices"]["raw_lines"] = len(rudev)

    hc, hr = pii_counts(uc, "calls"), pii_counts(ur, "rudevices")

    def entry(key, min_run=None, note=None):
        row = {}
        for name, hits, total, src in (("calls", hc, len(uc), "calls"),
                                       ("rudevices", hr, len(ur), "rudevices")):
            texts = hits.get(key, [])
            valued = with_value(texts, min_run) if min_run else None
            row[name] = {
                "replicas": len(texts),
                "share": round(len(texts) / total, 5),
                "examples": [quote(t, src) for t in texts[:3]],
            }
            if min_run:
                row[name]["replicas_carrying_a_number"] = len(valued)
        row["combined_replicas"] = row["calls"]["replicas"] + row["rudevices"]["replicas"]
        row["combined_share"] = round(row["combined_replicas"] / (len(uc) + len(ur)), 5)
        if note:
            row["note"] = note
        return row

    pii = {
        "name": entry("name_strong", note=(
            "strong shapes only: patronymic, given+surname pair, or a value right "
            "after «меня зовут». A hand check of 30 sampled hits found 30 real people.")),
        "name_first_only": entry("name_loose_only", note=(
            "a bare given name with nothing beside it -- «марина у меня машина», "
            "«позвоните татьянке». Noisier by construction and reported apart: "
            "this is the shape a written corpus never produces. Hand-checked on "
            "40 sampled hits: 37 real people, two were «жена» read as «Женя» "
            "(the stem was removed, so the shipped number no longer has them) "
            "and one was the city Владимир, which no surface form can separate "
            "from the given name.")),
        "name_cue_without_value": entry("name_cue_without_value", note=(
            "«как вас зовут», «фамилия» with no name following -- the cue word "
            "without the value it licenses.")),
        "address": entry("address_marker_visible", note=(
            "MARKER-VISIBLE ONLY and therefore biased upward; see address_truth "
            "for the number that does not share signals with the probe.")),
        "phone": entry("phone", note=(
            "numeral run >= 7 with the counting sequence vetoed, or run >= 4 next "
            "to a telephone cue.")),
        "email": entry("email", note="zero. Speech has no «@» and no spelled-out address."),
        "dob": entry("dob", note=(
            "a birth cue with a number near it. None is a full д-м-г date; the "
            "commonest real form is «семьдесят пятого года рождения».")),
        "snils": entry("snils_word", min_run=8, note="the WORD; no value follows any of them."),
        "inn": entry("inn_word", min_run=8, note="zero -- the word itself never occurs."),
        "card": entry("card_word", min_run=8, note="the WORD; no 16-numeral run exists."),
        "passport": entry("passport_word", min_run=6, note="the WORD; no series/number follows."),
        "plate": entry("plate", note=(
            "no dictated plate exists. Every hit is a cue word next to an unrelated "
            "number; single-letter plate names («а», «о», «у») had to be dropped "
            "from the alphabet because they are ordinary Russian words.")),
    }

    any_pii = {}
    for name, hits, total in (("calls", hc, len(uc)), ("rudevices", hr, len(ur))):
        carrying = set()
        for key in ("name_strong", "name_first_only", "address_marker_visible",
                    "phone", "dob"):
            carrying |= set(hits.get(key, []))
        any_pii[name] = {"replicas_with_any_pii": len(carrying),
                         "share": round(len(carrying) / total, 5)}
    any_pii["note"] = ("counted on the probes that actually fire -- name, address "
                       "(marker-visible), phone, DOB. It is a FLOOR: the "
                       "marker-free address class is invisible to it, so the real "
                       "share is roughly a third higher. What it settles is the "
                       "order of magnitude: nine replicas in ten carry no personal "
                       "data at all, and a generated set where every line carries "
                       "some is not this register.")

    truth = address_truth()
    truth["distinct_values"] = distinct_address_values()
    truth["rudevices"]["unique_replicas"] = len(ur)
    truth["rudevices"]["estimated_share"] = round(
        truth["rudevices"]["estimated_address_replicas_total"] / len(ur), 5)
    truth["calls"]["unique_replicas"] = len(uc)
    truth["calls"]["share"] = round(truth["calls"]["address_replicas_total"] / len(uc), 5)

    lexicon = {
        "openers": {"calls": phrase_counts(uc, OPENERS),
                    "rudevices": phrase_counts(ur, OPENERS)},
        "fillers": {"calls": phrase_counts(uc, FILLERS),
                    "rudevices": phrase_counts(ur, FILLERS)},
        "intents": {"calls": phrase_counts(uc, INTENTS),
                    "rudevices": phrase_counts(ur, INTENTS)},
        "asr_errors": {"calls": error_lexicon(uc), "rudevices": error_lexicon(ur)},
        "hyphenation": {
            "note": "the two corpora were transcribed by different pipelines: "
                    "calls writes «что то», rudevices writes «что-то». A v3 "
                    "register that fixes one spelling models one pipeline.",
            "calls_share_with_hyphen": reg["calls"]["share_with_hyphen"],
            "rudevices_share_with_hyphen": reg["rudevices"]["share_with_hyphen"],
        },
    }

    doc = {
        "meta": {
            "purpose": "reference distribution for AgentPII-RU v3: what live "
                       "Russian speech contains, so the generated corpus "
                       "reproduces it instead of our imagination",
            "generated": "2026-08-30",
            "corpora": {
                "calls": {"path": CALLS, "raw": len(calls), "unique": len(uc),
                          "licence": "CC BY-NC 4.0", "text_may_ship": False,
                          "source": "OpenSTT asr_calls_2_val"},
                "rudevices": {"path": RUDEV, "raw": len(rudev), "unique": len(ur),
                              "licence": "CC BY 4.0", "text_may_ship": True,
                              "source": "SOVA RuDevices"},
            },
            "counting_unit": "DISTINCT replica. The raw files repeat 968 and 1610 "
                             "lines respectively; a repeat is an occurrence, not "
                             "an observation, and shares computed on occurrences "
                             "lean our way.",
            "method": "surface form only. The detector is never called: a corpus "
                      "profiled with the engine can only report what the engine "
                      "already knows.",
            "name_gazetteer": "written by hand in probes.py for this measurement, "
                              "NOT the leased 197k list -- otherwise the count "
                              "measures the dictionary, not the corpus.",
        },
        "register": reg,
        "share_of_replicas_carrying_any_pii": any_pii,
        "pii_presence": pii,
        "address_truth": truth,
        "probe_blindness": {
            "note": "the marker-shaped address probe measured against the hand "
                    "labels. It recalls almost everything in the stratum selected "
                    "by the same words it looks for and nothing outside it -- the "
                    "same defect the first voice set had, reproduced here on "
                    "purpose so the number above is read correctly.",
            "by_stratum": probe_vs_labels(),
        },
        "lexicon": lexicon,
        "shapes": find_shapes(pool),
    }

    doc["v3_targets"] = {
        "note": "v3 has to reproduce this, not our imagination. Every share is "
                "over DISTINCT replicas of the two corpora combined.",
        "digits_in_text": 0.0,
        "starts_with_capital": round(reg["combined"]["share_starting_capital"], 5),
        "ends_with_period": 0.0,
        "any_sentence_punctuation": 0.0,
        "numeral_run_ge1": round(reg["combined"]["share_numeral_run_ge1"], 4),
        "numeral_run_ge3": round(reg["combined"]["share_numeral_run_ge3"], 4),
        "words_median": reg["combined"]["words_median"],
        "words_mean": reg["combined"]["words_mean"],
        "chars_median": reg["combined"]["chars_median"],
        "single_word_replicas": round(reg["combined"]["share_single_word"], 4),
        "hyphenation": "split across the two pipelines -- v3 must carry both "
                       "«что то» and «что-то», not one of them",
        "address_shape_split": {
            "marker_free": truth["marker_free_share_of_addresses"],
            "meaning": "the majority shape is «ленина пятьдесят», not «улица "
                       "Ленина дом 50». A generator that writes the marked form "
                       "measures the easy half.",
        },
    }

    absent = [k for k, v in pii.items() if v["combined_replicas"] == 0]
    thin = [k for k, v in pii.items()
            if 0 < v["combined_replicas"] <= 30]
    doc["absent_from_both_corpora"] = absent
    doc["present_but_too_thin_to_measure_on"] = thin
    doc["must_be_generated_from_templates"] = {
        "reason": "these types either never occur in speech or occur as a bare "
                  "word with no value behind it, so no amount of mining produces "
                  "a test case for them",
        "types": sorted(set(absent) | set(thin)),
        "but_the_register_must_be_borrowed": "generate the VALUE from a template "
                                             "and the SENTENCE from the "
                                             "distribution above: no digits, no "
                                             "capital, no final period, numbers "
                                             "spelled out, median length short.",
    }

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=2)
    print("wrote", OUT)
    for k, v in pii.items():
        print("  %-24s %5d replicas  %.4f%%" % (k, v["combined_replicas"],
                                                100 * v["combined_share"]))


if __name__ == "__main__":
    main()
