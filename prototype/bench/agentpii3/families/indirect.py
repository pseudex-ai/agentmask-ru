"""AgentPII-RU v3 — `indirect`: the datum the customer never says out loud.

«привезите туда же куда в прошлый раз», «позвоните мне на тот номер что в
заказе», «оформите на того же человека», «адрес возьмите из моей карточки», «на
ленина дом не помню». Nobody dictates a value. The agent fetches it with a tool,
the customer's own CRM answers with real personal data, and that answer has to be
masked ON THE WAY TO THE MODEL. The model then puts the substitute into the
second call and the REAL value has to arrive at the tool.

WHY THIS IS A FAMILY. Every other family in this corpus — and every earlier set
of ours — puts the gold value in the customer's text, so the round trip only ever
walks `user -> model -> tool`. Here it walks `tool -> model -> tool`, and the two
paths share no code but the vault. The value never passed through `normalize`, so
the fold that repairs a Cyrillic О inside a phone has not run on it; it never
passed the morphology gate, so nothing decided its case; it arrived as a JSON
string, where a substitute containing a bare quote breaks the parse rather than
the meaning. A gateway can be perfect on the user leg and lose every case here.

WHAT THE SPEECH CORPORA SAY ABOUT THIS FORM, and it is a finding rather than an
excuse. The indirect-reference stratum of SOVA RuDevices was read IN FULL: 42 952
utterances scanned, 47 match `_INDIRECT_PROBE`, 36 survive the profanity and
digit filter, and FIVE are usable as a customer asking a service to reuse
something it already stores (`VERBATIM_TRIGGERS`). That is not a sampling
failure. Phone and dispatch speech of that period has no stored profile to refer
back to, because there was no profile; the form is real and it is MODERN — an app
support chat, an authenticated widget — which is exactly the traffic this product
sits in. So the family is honest about its provenance in the only way available:
the five real utterances are carried `verbatim` with their source and their
digest, and everything else is `recombined` — the DISCOURSE ENVELOPE is a mined
shape (opener, filler, glued particle, self-correction, dictation cue, attention
word) and the referring clause is composed from the mined intent lexicon, with
`Provenance.shape` naming the envelope rather than pretending a corpus holds the
sentence. Nothing here is labelled `verbatim` that is not, and nothing is
labelled `recombined` whose envelope cannot be pointed at in
`mined/calls_grammar.json`.

FOUR RULES THIS MODULE HOLDS TO, each of which the alternative gets wrong:

  * **The lookup key is never personal data.** The customer is identified by a
    session or by an order number, never by their own phone. Keying the lookup on
    a value the customer stated would put a user-leg value back into the case and
    turn half the family into `transfer` under another name.
  * **The CRM does not speak the customer's register.** `voice_raw` is how the
    CALLER reaches us; a support system does not start writing house numbers in
    words because the customer phoned. The register acts on the user's turns —
    which is where the partial mention lives, and the partial mention is where
    linking decides anything — and the tool result stays wire-form JSON in every
    register. `_register_problems` judges `user` messages only, which is what
    makes that representable at all.
  * **Ground truth is built, never searched.** `assemble` records a slot's offset
    AS IT WRITES the slot. A `str.find` over the finished record would return the
    first occurrence, and `order_and_card` deliberately writes one address twice.
  * **The engine is never consulted about what to label.** Every span here comes
    from what this generator placed. The only mechanical reader involved is the
    schema's own shape audit, which knows nothing about our recognizers.

WHAT THE PARTIAL MENTION IS FOR. «на ленина дом не помню» carries a street and no
house number: under 152-ФЗ ст. 3 п. 1 it identifies nobody — hundreds of
buildings stand on it — so its `duty` is `optional` and it may claim no
`tool_param`. What it CAN claim is a `LinkExpectation`: the gateway must resolve
it against the fuller address that came back from the tool, inside this one
conversation. That is `place_parts` exercised from a TOOL RESULT, which nothing
but a unit test has ever done.

WHY MOST CASES DO NOT JUDGE THE LOOKUP CALL. The schema refuses a call with no
judged argument, and it is right to: «a call whose personal data nobody named is
scored on nothing». A lookup keyed on a session id carries nothing of ours, so it
is not listed as an expected call at all — the tool message is still there and
the live harness still serves it by name. It IS listed, and judged, in the two
places where its argument is a real claim: the partial street (which the gateway
may legitimately mask and must then give back) and the customer id in the system
prompt (which the gateway must not mask, and a false mask there breaks the fetch
before any personal data is reached).
"""

import json
import random
import re
import sys
from dataclasses import dataclass
from pathlib import Path

# The repo runs its benchmarks as `python3 -m bench.agentpii3.families.indirect`
# from `prototype/`; the insert is what lets the same file also run by path,
# which is how it gets iterated on. Same shape as `mine_reference.py`.
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from bench.agentpii3.schema import (  # noqa: E402
    Case,
    ExpectedCall,
    FinalAnswer,
    LinkExpectation,
    Message,
    Negative,
    PiiItem,
    Provenance,
    Source,
    ToolSchema,
    case_characters,
    distinct_values,
    type_denominators,
    validate,
)

FAMILY = "indirect"

# The owner's size for this family in the v3 plan. `build` takes the count, so a
# smaller run is a subset of the same schedule rather than a different corpus.
TARGET = 250


# --- the census behind the verbatim cases ---------------------------------
#
# Published so a third party can rebuild the stratum: this is the ONLY reason
# `selection` is `census` rather than `marker` on those cases. None of these cues
# is a cue the detector reads — there is no personal data in any of them — so the
# stratum cannot be biased towards what we already find, which is the failure
# mode `SELECTIONS` exists to name. What it IS biased towards is the phrasing of
# an indirect reference, which is the family's subject.
_INDIRECT_PROBE = re.compile(
    r"(туда же|туда куда|как в прошлый раз|в прошлом заказе|в заказе|"
    r"по этому же номеру|на тот номер|тот же номер|этому номеру|"
    r"мой адрес|моего адреса|тот же адрес|этот адрес|адрес мой|"
    r"как обычно|как всегда|на того же|на ту же|та же карта|той же карте|"
    r"в карточке|в анкете|в договоре|у вас записан|у вас есть мой|"
    r"вы знаете где|знаешь где я|туда откуда)")

# (text, blake2b-6 key, 1-based line in speech_rudevices.jsonl, sha256 of text).
# SOVA RuDevices is CC BY 4.0, so the text ships and `Message.content` is filled;
# the digest is still carried, because a re-downloaded corpus whose lines shifted
# would move every offset in the case while the numbers went on looking like
# numbers.
_Verbatim = tuple[str, str, int, str]

VERBATIM_TRIGGERS: dict[str, _Verbatim] = {
    "same_number_v": (
        "получить по этому же номеру",
        "176cd08e520c", 40541,
        "3c7110e7af3f26c5781a0723d63bff621dffcf3038fb14c3f119df8d7db00cc2"),
    "callback_v": (
        "с утра наберёте на этот же номер я вас соединю",
        "0527d5a380c5", 32986,
        "89dc73bd893f49055ac4f22432d74b1bed969a2bbd3315a6e070bf99fc4c06f0"),
    "names_in_base_v": (
        "но фамилии уже есть в базе а имена там телефон",
        "970e6e6529f5", 36544,
        "21b759cc0965f716498b1f5c1cdfadd15cbe1295c7bae660983cd8fa814b9a78"),
    "as_last_time_v": (
        "что осматривает моё разрешение будешь как по стандарту как в прошлый раз",
        "83bf9dca3ecc", 18881,
        "988ea378c85e1f5c3be0ca7936d0591c269f428db199ef850d198c286525efc9"),
    "as_in_order_v": (
        "ээ сейчас сто семьдесят как у него в заказе есть так и останется",
        "14e6a985b4aa", 28274,
        "f7a0d603d63509a38281b79f840eb680d93a87e435fb9ebc0768c91a08349de5"),
}

# Filler for the `long` and `deep` rungs, and it is REAL SPEECH on purpose. The
# measured floor is that nine utterances in ten carry no personal data at all
# (1.995% of the call corpus, 0.939% of the dispatch corpus); a long context
# authored by a generator carries a value in every second line, which inflates
# recall and precision at once. Selected from SOVA RuDevices (CC BY 4.0) by a
# filter that is mechanical and stated: 55-150 characters, no digit, no numeral
# word, no address vocabulary, no patronymic tail, no common given name, and a
# profanity block-list — the corpus is casual speech and a benchmark a customer
# will read is not the place for it.
#
# The filter is deliberately BLIND to our recognizers. A residual name in filler
# would be scored by nothing (it is neither gold nor negative), so the cost of a
# miss here is a missing measurement, never a false one.
_FILLER: tuple[_Verbatim, ...] = (
    ('он всегда в чате вообще запрещают такое писать потому что', '50a67a1bbc65', 225, 'c20b753688e8272d0a26ac1581dc1b556421adf7b37c5f4a80a1fa717fe935ca'),
    ('если тебе скину от этого пользы никакой не будет ты какую-то фигню начнёшь делать', 'fe0deea70080', 934, 'a982e3c6126dcacf793f78b2cbe624515b819a2817b5f13850852f485aadb612'),
    ('есть ли кто-то играл скажите какой из них сложнее потому что у меня сейчас выбор что начать учить', '4994c582fa9b', 970, '1b3d1c74f6e6510ba2043c50c2985cc6ef31478ba4a12571592deac34e339950'),
    ('пожалуйста уважаемые слушатели определите какой у меня акцент и из какого гипотетического региона я могу быть', 'a8836f31f0b3', 2715, '36129aa5e6bd96126b58de259cf79ad99de6950cb3d4a596a4719138745340f2'),
    ('а вы знаете что в физике есть понятие виртуальные частицы', 'f75037dda23d', 2961, '22ee80e4b40da60d4cf0e57dc16ebe7db6d77c8f1607e0f722778bf98b0fb3e9'),
    ('получается всё равно съедать определённое количество ну короче там считать надо', 'f107191986a0', 3893, '54dbe15290273944e93463dad56ad533c9e7ffef50582880fda2c9c3fb99d290'),
    ('ну в принципе они похожи вы можете их в режиме одного плейлиста по кругу все крутить', '85507536bc4e', 4245, '4c1b0d35effe9b81ce3a38e6d2e56dfe739e4bb788df9b81a1d03cabf844ccb0'),
    ('тогда точно нету студийной банды и просто банально не может быть', '253fbb2cc30b', 5808, 'dd607e9e8c2831cf036d2de81cbda7a74101cbdf863380de6c9cefb865aaff50'),
    ('она не может делать бэкап ээ той же памяти ээ куда и сам файл ложиться бэкапа', '6920edd9f8f5', 5943, '7faab5e11c6151efd623220823111df66c26baa781d3e6a946acdd2d66627bba'),
    ('да это тот редкий случай когда сделали и исекай и сделали сэйнэн', '00734e2bcf5b', 6692, '759b345b71306df7fffa6a79781b83dd063dda3b3defb7b8224274becb105257'),
    ('в основном радуга образуется на кучево-дождевых облаках связанных с ливневыми осадками из-под которых вот падает дождь', '85c5e88a0962', 7368, '7668d5bf6ed523e849bfff47633d55a57996b11f98f469baeb19e3d4b2ca7134'),
    ('ну у меня до конца не получаются блин больше половины задач', '0b0afbd56e85', 7735, 'f12209160eeb4a07c854f973966ac336728b2c921e787ee2ba9798aeee5fd1e0'),
    ('то есть у нас есть пространство и время а есть то что за пространством и временем', 'd068ad5714b7', 9995, 'adb1191fa7278ea01ad9ce0f047635dae2309243d58ac829cccb5f2cc8130e3f'),
    ('интересней было бы на мой взгляд читать чем вот такие сложные и неинтересные предложения', '69f4293eb393', 10784, '8d782f113e920aa5eda74bbc1b071afe8fc03357b5bd534f6f5b677acbdac837'),
    ('отношение администрации потому что я к администрации нормально отношусь вы же оба причём неадекватно реагируете на мои на моё обращение', '767e68c2f4ad', 11033, 'a5d6e1b158a220104d5ff3d1db2b044cdd37dd4b57d39d73a2c2af9b29a5b240'),
    ('заранее будем планировать вот конкретно сейчас например', '409b80b65572', 11193, '3f1e7a7626ab716cef22d7c6bdd6001826ebf01b4f8ddd8bdda36ff6a357e665'),
    ('будут ли проблемы и насколько большие или вообще не будет проблем', '943a77e4beb5', 11420, 'de4b56808a71386f313b469b8ef59f6671db1626c2eb594334b47a31784c628a'),
    ('ой так смешно высказался так какая смешная манера речи интересно люди так говорят или нет', 'd2ded1179ede', 11951, 'd7ee29519d6606df4b01982e228d5b8dfec20996a03df2e2acdb47751b2428c5'),
    ('ничем не обоснованные мне даже спросить не у кого будет', 'f3dab5ad0bac', 13316, '2edc1bd51e16386664f0c77377f4c02a6800364e66c118ea2e3552c54bdfc834'),
    ('негативные комменты а если нет откройте другую там и они будут', 'c1e96b65b4e7', 13702, 'cd3bb030677f777cf8c545c3a1eeb63e66ad7c4364e452d564eba9b4e8b9c7be'),
    ('в общем там всё очень запутанно ещё поэтому они даже сами не знают где это всё будет если в зале то тогда', '84612043f3a9', 13894, '3f08ba07da756516097f8622ea5f80422c6bf0770553b8b32ef879e1171b0854'),
    ('ну пока ещё нет но они говорят о том что скоро наступит', '15b96fcfc679', 14481, 'd5e1e8b6381b66b17db730eace68151311e44c4ab23f8e187d00146fd4de2eb6'),
    ('так оно пойдёт с осложнением или по лёгкому сценарию никто не знает', 'faa95f793392', 15026, 'b9b02b6da9244dd26fd60a6bdd8fade06a12e2358f094987cd2b1575a48a0c7e'),
    ('и мы туда вкладываем какой-то вот предмет какую-то шестерёнку или какую-то палку', 'd01dae309a59', 15945, '7a8757f564fd73b65d52d11ba6ec3b3123ecb64ab02ba43fa699d28fe19173cb'),
    ('даже сейчас иду под дождём он утром то начнётся то закончится', '926a0ef5854b', 16871, 'c2727bd359969a91032e3047b69df506d1ab6b1023a6e92ccfe682ff8b3d68e1'),
    ('вот либо придётся тогда ставить ещё впереди стулья чтоб все', 'd292fdaf5129', 17936, '4f845e9ec9c7b457c1da6e659ae46d885f780dfe591b368b2b22db65d98e1f03'),
    ('ну ребят давайте вот на чистоту почему вы стали пробовать', 'b5a86e3913f1', 19609, 'efc6fa47aa62f3385aa123321abfe741d0f99b872394051c1be4024407391792'),
    ('у нас даже есть опыт текущий опыт там к цене или да к прибыли может привязываться но это мы можем делать только ну с некоторыми но', '7d27c3fdf549', 20389, 'a0d4ad605189b4a8be78a9fd1d60e15fa2c2b16d053d113eb2a1c2b258f03978'),
    ('я так делаю всё у меня такой принцип жизни не нравится не общайтесь со мной вот так', '0ad7d2abd9aa', 22027, '505b4d77e472bc7b873fcbde8a9e30b695a6e80e56a851efa3f29406bff2c724'),
    ('натягивается лента сигнальная или что-то ещё там шнурка это ориентир для ну для выемки грунта', '80d78933ab46', 23630, 'c6dfa35af97c8b6d7300d4fb9b64ce3b4850bf9a04afaebcf21e1e77c62a3ea3'),
    ('вот когда будут дети тогда да а так я сама и мне скучно плюс', '0991362dfa33', 23896, '85d64aa356e3e4ec79bc2c407d7d7f976ac716cdf65d30cc07ba81316f0c4534'),
    ('я русский то учу с самого рождения и до сих пор неграмотный так что нормально', '44bf47ac423b', 24354, '5bcc5d9e4ae315df7fc3a1a44ac56284d4f713c0d532f0f292da80b9ca885fdb'),
    ('так я же не предлагаю вам что-то менять я предлагаю зарабатывать', '727725d4ac6f', 24783, '9c6d586f5108e44e6cc53b4314ad0445c9a69a5022437f7ac2795c8aec42f951'),
    ('я даже удивляюсь после вот этих его слов как он вообще песни свои пишет', '4d417cbe019c', 24829, '65701f8ab57a448f6b20c9834324dc1ffd1fb9a81e0661680ca16182d4b5174c'),
    ('когда я прочитал аа вот эти вот отрывки по сути сами по себе', 'f68226b52c15', 25630, '1c4f3ed99cf3dcfd8cc30c1d397f668e89d94f7bbf77233c3bf19eb36ff55f20'),
    ('строй это система как можно двигаться и к чему всё приводит', 'ed71f2b27196', 31197, '139daf9b9feade5d9ff58b1bfd331e8f82264143a6513e31aac546d2c21a8710'),
    ('а как ты можешь чтобы набить себе подписчиков поучаствовать в гиве допустим', 'b7917fabdefa', 31580, '5850ea365a3fdeab0f90cd9611dfae0b3a09fbfceea87729a27d528cde795d07'),
    ('и я буду показывать именно все нюансы опять же повторюсь сняли очень классно я не', '93e3da9d4fcb', 33589, '4491ceaad57630ff71f6a9c5a86f1a45a20a12ed88c8dcd767047e174a893b7d'),
    ('объясните кто-нибудь тупо мне почему вот тут должен быть дать ну типо', '5f6bdcf36eff', 34673, 'd5edcefceb1242a9e897e26e4eb3dab17b0c9e61dbf77a759751353c65d6a264'),
    ('в итоге по результату года заплатит больше чем клиент платящий', '7e46f3b62275', 36773, 'b9c4957b0ddddd6a2c7d958d4eceed7f038240d9790602e78f2505087899a822'),
    ('ну типа вот сегодня я не могу давай завтра вот завтра точно', '350286dbdbab', 37034, '7692a1410eba692a40e8e4eb88abd589a366aacd1584ab689e0744fb83cc8cfa'),
    ('ну можно также без модов поиграть если тебе не понравится но типа', '50b1d8e7046e', 39636, 'd233c9a64ce6434e9942c0164250f7daed86a42ab79d46c370ab9e116fadb8e7'),
    ('ну таких вот моментов да и тщательных каких-то действий которые допустим мене были бы не в радость и было всё классно атмосфера очень дружественная', 'e667d72d4377', 41537, 'e2bf0a6ab9d13ccf6a6f6a67142a0ffacc2f91ffe4979f718424f86ae25f4ff6'),
    ('а скажите честно вам какой интерес вот в этой всей истории', 'efa936fc6358', 42218, 'b44180433b2eae26b3096a6acde96bab2a1fb02e44838d91ab89cd04555029aa'),
    ('могу ему пожаловаться он меня поймёт и поддержит ну как бы', 'd181492effc8', 42720, '39bf95d93750d1cc221063ec549edc6eba379a193b768153ace62dd637a80da9'),
)

# The agent's side of the filler. Authored, lower case and unpunctuated so a
# `voice_raw` transcript reads as one conversation — assistant turns are not
# register-gated, but a case that mixes a literary agent with a spoken customer
# is a case nobody would recognise as their own traffic. Long enough that the
# `deep` rung reaches MIN_DEEP_CHARS on thirty-odd messages rather than on two
# hundred, which is what the character floor is there to force.
_AGENT_FILLER: tuple[str, ...] = (
    "понял вас записал сейчас посмотрю по системе и вернусь с ответом",
    "да конечно я на связи уточню и сразу скажу что получилось",
    "хорошо приняла минутку пожалуйста я поднимаю историю обращений",
    "спасибо что дождались я почти закончил проверять что у нас есть",
    "поняла вас давайте так и сделаем я оформлю и подтвержу отдельно",
    "тут надо посмотреть внимательнее сейчас найду и напишу как только будет",
    "ага записал я всё вижу продолжайте пожалуйста я слушаю",
    "хорошо тогда двигаемся дальше по порядку я пока держу заявку открытой",
    "принято сейчас сверю с тем что у нас сохранено и отвечу",
    "конечно я никуда не пропал просто данные подтягиваются небыстро",
    "да я вас понял давайте я уточню детали чтобы ничего не перепутать",
    "спасибо понял вас сейчас соберу всё вместе и подтвержу заявку",
)


# --- value pools ----------------------------------------------------------
#
# Authored from the domain. Overlap with the leased gazetteer is unavoidable
# (Russian names are Russian names) but nothing is here BECAUSE we detect it.
# Foreign surnames are drawn at a flat rate rather than kept in a corner: a
# Russian shop with foreign customers is Tuesday, and hiding them in one corner
# lets a summary number look healthy over the population it fails on.

# Drawn in PARTS, not as fixed triples. Twenty-eight frozen people would have
# given 43 distinct names over 223 gold items, and a rate whose denominator is
# the same four dozen strings repeated is the «повтор — не наблюдение» trap the
# schema prints `distinct_values` to expose. The parts recombine within a gender,
# which is the constraint that keeps «Иванов Мария Петрович» out of ground truth.
_SURNAMES_M: tuple[tuple[str, str], ...] = (
    ("Смирнов", "smirnov"), ("Кузнецов", "kuznetsov"), ("Морозов", "morozov"),
    ("Волков", "volkov"), ("Лебедев", "lebedev"), ("Новиков", "novikov"),
    ("Фёдоров", "fedorov"), ("Соколов", "sokolov"), ("Захаров", "zaharov"),
    ("Григорьев", "grigoriev"), ("Панкратов", "pankratov"),
    ("Ерохин", "erohin"), ("Бирюков", "biryukov"), ("Селезнёв", "seleznev"),
)
_SURNAMES_F: tuple[tuple[str, str], ...] = (
    ("Смирнова", "smirnova"), ("Кузнецова", "kuznetsova"),
    ("Морозова", "morozova"), ("Волкова", "volkova"), ("Лебедева", "lebedeva"),
    ("Новикова", "novikova"), ("Фёдорова", "fedorova"),
    ("Соколова", "sokolova"), ("Панкратова", "pankratova"),
    ("Селезнёва", "selezneva"),
)
_GIVEN_M: tuple[str, ...] = (
    "Артём", "Дмитрий", "Алексей", "Сергей", "Максим", "Пётр", "Кирилл",
    "Игорь", "Никита", "Владислав", "Роман", "Валерий", "Леонид", "Аркадий",
)
_GIVEN_F: tuple[str, ...] = (
    "Мария", "Ольга", "Екатерина", "Татьяна", "Ирина", "Светлана", "Юлия",
    "Анна", "Валентина", "Зинаида",
)
_PATR_M: tuple[str, ...] = (
    "Игоревич", "Сергеевич", "Андреевич", "Николаевич", "Павлович",
    "Олегович", "Витальевич", "Романович", "Львович", "Валентинович",
)
_PATR_F: tuple[str, ...] = (
    "Игоревна", "Сергеевна", "Андреевна", "Николаевна", "Павловна",
    "Олеговна", "Витальевна", "Романовна", "Львовна", "Валентиновна",
)
# Hostile to suffix rules on purpose: no -ов/-ев/-ин on most, several
# non-Slavic, one indeclinable given name. NEREL says nearly every name we miss
# is foreign, so a corpus without them measures the easy half — and they are
# drawn at a flat rate rather than kept in a corner, because a Russian shop with
# foreign customers is Tuesday.
_FOREIGN: tuple[tuple[str, str, str, str], ...] = (
    ("Ким", "Виктор", "kim", "m"),
    ("Тагиев", "Рустам", "tagiev", "m"),
    ("Мкртчян", "Ашот", "mkrtchyan", "m"),
    ("Гулиев", "Эльдар", "guliev", "m"),
    ("Абдуллаев", "Тимур", "abdullaev", "m"),
    ("Саркисян", "Карен", "sarkisyan", "m"),
    ("Нгуен", "Ань", "nguyen", "f"),
    ("Мамедова", "Лейла", "mamedova", "f"),
    ("Валиахметов", "Ильдар", "valiahmetov", "m"),
    ("Джонсон", "Майкл", "johnson", "m"),
    ("Ли", "Чен", "li", "m"),
)
_FOREIGN_SHARE = 0.3

# Street names as the dispatch corpus actually produces them, and in the ratio it
# produces them: a surname in the genitive twice as often as an adjective (28
# against 14 in `mined/dispatch_grammar.json`). A generator that only writes
# «улица Ленина» measures the half that carries a type word — two thirds of real
# address values carry none.
_STREETS_GENITIVE: tuple[str, ...] = (
    "Ленина", "Лермонтова", "Грибоедова", "Комиссарова", "Чапаева",
    "Миронова", "Добролюбова", "Дзержинского", "Энгельса", "Калашникова",
    "Челюскинцев", "Гагарина",
)
_STREETS_ADJECTIVE: tuple[str, ...] = (
    "Школьная", "Зеленоградская", "Вольная", "Кирочная", "Мончегорская",
    "Ферганская", "Заречная", "Центральная",
)
_CITIES: tuple[str, ...] = (
    "Ижевск", "Казань", "Пермь", "Самара", "Воронеж",
    "Екатеринбург", "Новосибирск", "Краснодар", "Уфа", "Тюмень",
)
# Real Russian mobile prefixes: a phone libphonenumber refuses is a phone our own
# ground truth invented, and the miss would be the corpus's, not the gateway's.
_MOBILE: tuple[str, ...] = ("912", "916", "926", "903", "905", "917", "919",
                            "950", "951", "987", "999", "982")
_MAIL_DOMAINS: tuple[str, ...] = ("mail.ru", "yandex.ru", "gmail.com", "bk.ru",
                                  "list.ru", "inbox.ru")
# ГИБДД uses the twelve Cyrillic letters that look like Latin ones. Written in
# Cyrillic here because that is what a real plate and a real CRM hold; a Latin
# spelling would be a look-alike defect we invented ourselves.
_PLATE_LETTERS: str = "АВЕКМНОРСТУХ"
_PLATE_REGIONS: tuple[str, ...] = ("18", "16", "59", "63", "36", "66", "54",
                                   "23", "02", "72")
# Published Russian BIN prefixes. A card is Luhn-VALID here: the record is a real
# customer's card as a CRM holds it, and a checksum-invalid one would let a
# gateway that only checks Luhn look better than it is.
_CARD_BINS: tuple[str, ...] = ("220070", "427644", "546901", "553691", "415482")


# --- numerals, for the register that has no digits ------------------------

_ONES: tuple[str, ...] = (
    "ноль", "один", "два", "три", "четыре",
    "пять", "шесть", "семь", "восемь", "девять",
)
_TEENS: tuple[str, ...] = (
    "десять", "одиннадцать", "двенадцать", "тринадцать", "четырнадцать",
    "пятнадцать", "шестнадцать", "семнадцать", "восемнадцать", "девятнадцать",
)
_TENS: tuple[str, ...] = (
    "", "", "двадцать", "тридцать", "сорок", "пятьдесят",
    "шестьдесят", "семьдесят", "восемьдесят", "девяносто",
)
_HUNDREDS: tuple[str, ...] = (
    "", "сто", "двести", "триста", "четыреста",
    "пятьсот", "шестьсот", "семьсот", "восемьсот", "девятьсот",
)
_ORDINALS: tuple[str, ...] = (
    "", "первый", "второй", "третий", "четвёртый", "пятый",
    "шестой", "седьмой", "восьмой", "девятый", "десятый",
    "одиннадцатый", "двенадцатый", "тринадцатый", "четырнадцатый",
)


# The dative of the hours a dispatcher names, written out rather than derived:
# «к восемь ноль ноль» is not a sentence anybody says, and a rule that produced
# it would put the error in ground truth where it is scored as if it were real.
_HOUR_DATIVE: dict[int, str] = {
    7: "семи", 8: "восьми", 9: "девяти", 10: "десяти", 11: "одиннадцати",
}


def _pieces(count: int) -> str:
    """«две штуки» / «пять штук». Agreement, because 2-4 takes the paucal."""
    return "штуки" if 2 <= count % 10 <= 4 and not 11 <= count % 100 <= 14 \
        else "штук"


def _spell(value: int) -> str:
    """A number as a caller says it. Masculine, which is the house-number form.

    Hundreds are here because flats run past ninety-nine in a panel block and a
    generator that stopped at two digits would quietly restrict the corpus to
    small buildings — and to numeral runs one word shorter than the register's.
    """
    if value < 10:
        return _ONES[value]
    if value < 20:
        return _TEENS[value - 10]
    if value < 100:
        tens, ones = divmod(value, 10)
        return _TENS[tens] if not ones else f"{_TENS[tens]} {_ONES[ones]}"
    hundreds, rest = divmod(value, 100)
    return (_HUNDREDS[hundreds] if not rest
            else f"{_HUNDREDS[hundreds]} {_spell(rest)}")


# --- checksums ------------------------------------------------------------
#
# Published algorithms, implemented here rather than imported: `bench/` may not
# reach into `pseudex/`, and a benchmark that borrowed the engine's checksum
# would be testing the engine against itself. A CRM row holds a VALID identifier,
# so these produce valid ones — the deliberately invalid form belongs to the
# substitute the gateway mints, not to the customer's record.

def _snils(rng: random.Random) -> str:
    while True:
        digits = [rng.randrange(10) for _ in range(9)]
        if len(set(digits)) < 4:
            continue
        total = sum(digit * (9 - index) for index, digit in enumerate(digits))
        control = 0 if total in (100, 101) else total % 101
        if control == 100 or control == 101:
            control = 0
        if control > 99:
            continue
        body = "".join(str(digit) for digit in digits)
        return f"{body[:3]}-{body[3:6]}-{body[6:9]} {control:02d}"


def _inn12(rng: random.Random) -> str:
    """ИНН физического лица. Twelve digits, two check digits.

    An individual's ИНН, never a company's: a legal entity's identifiers are out
    of scope by Recital 14 and by 152-ФЗ's definition of the subject, and putting
    one in the gold would demand masking of something that is not personal data.
    """
    base = [1, 8] + [rng.randrange(10) for _ in range(8)]
    weights_11 = (7, 2, 4, 10, 3, 5, 9, 4, 6, 8)
    weights_12 = (3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8)
    eleventh = sum(d * w for d, w in zip(base, weights_11)) % 11 % 10
    twelfth = sum(d * w for d, w in zip(base + [eleventh], weights_12)) % 11 % 10
    return "".join(str(d) for d in base + [eleventh, twelfth])


def _card(rng: random.Random) -> str:
    bin_prefix = rng.choice(_CARD_BINS)
    body = bin_prefix + "".join(str(rng.randrange(10)) for _ in range(9))
    total = 0
    for index, char in enumerate(reversed(body)):
        digit = int(char)
        if index % 2 == 0:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    check = (10 - total % 10) % 10
    full = body + str(check)
    return f"{full[:4]} {full[4:8]} {full[8:12]} {full[12:]}"


# --- one customer ---------------------------------------------------------

@dataclass(frozen=True)
class Party:
    """Everything one person's record could hold. A frame uses what it needs.

    Built once per case and never re-drawn, so the same human keeps one phone
    across the two rows of `order_and_card` — which is the whole point of the
    `same` link that case carries.
    """

    full: str
    short: str
    phone: str
    phone_flat: str
    email: str
    city: str
    street: str
    flat: int
    address: str
    dob: str
    passport: str
    snils: str
    inn: str
    card: str
    plate: str


def _party(rng: random.Random) -> Party:
    if rng.random() < _FOREIGN_SHARE:
        # The gender column of the foreign pool is documentation, not a choice:
        # those names carry no patronymic, so nothing in the case has to agree
        # with it.
        surname, given, latin, _ = rng.choice(_FOREIGN)
        patronymic = ""
    elif rng.random() < 0.5:
        surname, latin = rng.choice(_SURNAMES_M)
        given, patronymic = rng.choice(_GIVEN_M), rng.choice(_PATR_M)
    else:
        surname, latin = rng.choice(_SURNAMES_F)
        given, patronymic = rng.choice(_GIVEN_F), rng.choice(_PATR_F)
    full = " ".join(part for part in (surname, given, patronymic) if part)
    street = (rng.choice(_STREETS_GENITIVE) if rng.random() < 0.66
              else rng.choice(_STREETS_ADJECTIVE))
    city = rng.choice(_CITIES)
    house = rng.randrange(1, 99)
    flat = rng.randrange(1, 199)
    tail = "".join(str(rng.randrange(10)) for _ in range(7))
    prefix = rng.choice(_MOBILE)
    plate = (f"{rng.choice(_PLATE_LETTERS)}{rng.randrange(100, 999)}"
             f"{rng.choice(_PLATE_LETTERS)}{rng.choice(_PLATE_LETTERS)}"
             f"{rng.choice(_PLATE_REGIONS)}")
    return Party(
        full=full,
        short=f"{surname} {given}",
        phone=f"+7 {prefix} {tail[:3]}-{tail[3:5]}-{tail[5:]}",
        phone_flat=f"+7{prefix}{tail}",
        email=f"{latin}.{rng.randrange(10, 99)}@{rng.choice(_MAIL_DOMAINS)}",
        city=city,
        street=street,
        flat=flat,
        address=f"{city}, ул. {street}, д. {house}, кв. {flat}",
        dob=f"{rng.randrange(1, 29):02d}.{rng.randrange(1, 13):02d}."
            f"{rng.randrange(1955, 2001)}",
        passport=f"{rng.randrange(10, 91)} {rng.randrange(10, 91)} "
                 f"{rng.randrange(100000, 999999)}",
        snils=_snils(rng),
        inn=_inn12(rng),
        card=_card(rng),
        plate=plate,
    )


# --- assembly -------------------------------------------------------------
#
# A message and the offsets of its tracked slots, in ONE pass. A `str` is
# literal; a `(slot, value)` pair is tracked. Offsets are recorded as the slot is
# written and never by searching the finished string — `order_and_card` writes
# one address twice on purpose, and `str.find` would point both items at the
# first copy.

Part = str | tuple[str, str]
Spans = dict[str, tuple[int, int]]


def assemble(parts: list[Part]) -> tuple[str, Spans]:
    out: list[str] = []
    spans: Spans = {}
    cursor = 0
    for part in parts:
        if isinstance(part, tuple):
            slot, value = part
            if slot in spans:
                raise ValueError(f"slot {slot!r} assembled twice")
            spans[slot] = (cursor, cursor + len(value))
            out.append(value)
            cursor += len(value)
        else:
            out.append(part)
            cursor += len(part)
    return "".join(out), spans


# (json key, slot or "", value). A slot names a row in `Record.roles`.
Field = tuple[str, str, str]


def _object_parts(fields: tuple[Field, ...]) -> list[Part]:
    """Wire-form JSON as assembly parts.

    Serialised HERE and not by `json.dumps` at score time, because the envelope's
    `content` is a string and masking runs over it flat: a scorer choosing its own
    separators would move every offset in the family. A value needing an escape is
    REFUSED rather than escaped — an escaped value no longer appears literally in
    the text, so its span would be a lie, and no real Russian address or name in
    these pools needs one.
    """
    parts: list[Part] = ["{"]
    for index, (key, slot, value) in enumerate(fields):
        if json.dumps(value, ensure_ascii=False) != f'"{value}"':
            raise ValueError(f"value {value!r} would need JSON escaping")
        parts.append(", " if index else "")
        parts.append(f'"{key}": "')
        parts.append((slot, value) if slot else value)
        parts.append('"')
    parts.append("}")
    return parts


def _array_parts(objects: tuple[tuple[Field, ...], ...]) -> list[Part]:
    parts: list[Part] = ["["]
    for index, fields in enumerate(objects):
        if index:
            parts.append(", ")
        parts.extend(_object_parts(fields))
    parts.append("]")
    return parts


# --- records --------------------------------------------------------------
#
# What the customer's own system hands back. `roles` says what each slot IS: a
# gold item with its type, or a negative with its family. The record is the only
# place personal data enters an `indirect` case, which is what makes the family
# the inbound half of the contract.

@dataclass(frozen=True)
class Role:
    kind: str        # "pii" | "neg"
    tag: str         # a schema TYPE, or a NEGATIVE_FAMILIES name
    value: str
    canonical: str
    identity: str
    why: str


@dataclass(frozen=True)
class Record:
    parts: list[Part]
    roles: dict[str, Role]


def _pii(tag: str, value: str, canonical: str, identity: str) -> Role:
    return Role(kind="pii", tag=tag, value=value, canonical=canonical,
                identity=identity, why="")


def _neg(family: str, value: str, why: str) -> Role:
    return Role(kind="neg", tag=family, value=value, canonical=value,
                identity="", why=why)


def _order_id(rng: random.Random) -> str:
    return f"{rng.choice('ABZ')}-{rng.randrange(1000, 9999)}"


def _record(name: str, party: Party, other: Party, customer_id: str,
            rng: random.Random) -> Record:
    """One tool result, chosen by name. Every branch returns wire-form JSON."""
    order_id = _order_id(rng)
    if name == "order":
        roles = {
            "order_id": _neg("order_number", order_id,
                             "номер заказа — не персональные данные"),
            "name": _pii("NAME", party.full, party.full, "self.name"),
            "phone": _pii("PHONE", party.phone, party.phone_flat, "self.phone"),
            "addr": _pii("LOC", party.address, party.address, "self.loc"),
            "count": _neg("quantity", f"{rng.randrange(2, 9)} шт",
                          "количество позиций, а не номер"),
        }
        fields: tuple[Field, ...] = (
            ("order_id", "order_id", roles["order_id"].value),
            ("created", "", "2026-08-12"),
            ("recipient", "name", party.full),
            ("phone", "phone", party.phone),
            ("address", "addr", party.address),
            ("items", "count", roles["count"].value),
            ("status", "", "доставлен"),
        )
        return Record(_object_parts(fields), roles)
    if name == "card":
        roles = {
            "name": _pii("NAME", party.full, party.full, "self.name"),
            "phone": _pii("PHONE", party.phone, party.phone_flat, "self.phone"),
            "addr": _pii("LOC", party.address, party.address, "self.loc"),
            "zone": _neg("city_reference", party.city,
                         "город как зона доставки, а не чей-то адрес"),
        }
        fields = (
            ("customer_id", "", customer_id),
            ("name", "name", party.full),
            ("phone", "phone", party.phone),
            ("address", "addr", party.address),
            ("zone", "zone", party.city),
        )
        return Record(_object_parts(fields), roles)
    if name == "two_orders":
        other_id = _order_id(rng)
        roles = {
            "order_id": _neg("order_number", order_id, "номер заказа"),
            "other_order_id": _neg("order_number", other_id, "номер заказа"),
            "name": _pii("NAME", party.full, party.full, "self.name"),
            "phone": _pii("PHONE", party.phone, party.phone_flat, "self.phone"),
            "addr": _pii("LOC", party.address, party.address, "self.loc"),
            "other_name": _pii("NAME", other.full, other.full, "other.name"),
            "other_phone": _pii("PHONE", other.phone, other.phone_flat,
                                "other.phone"),
            "other_addr": _pii("LOC", other.address, other.address, "other.loc"),
        }
        mine: tuple[Field, ...] = (
            ("order_id", "order_id", order_id),
            ("created", "", "2026-08-14"),
            ("latest", "", "да"),
            ("recipient", "name", party.full),
            ("phone", "phone", party.phone),
            ("address", "addr", party.address),
        )
        theirs: tuple[Field, ...] = (
            ("order_id", "other_order_id", other_id),
            ("created", "", "2025-11-30"),
            ("latest", "", "нет"),
            ("recipient", "other_name", other.full),
            ("phone", "other_phone", other.phone),
            ("address", "other_addr", other.address),
        )
        return Record(_array_parts((mine, theirs)), roles)
    if name == "trip":
        roles = {
            "trip_id": _neg("order_number", f"T-{rng.randrange(1000, 9999)}",
                            "номер поездки"),
            "addr": _pii("LOC", party.address, party.address, "self.loc"),
            "name": _pii("NAME", party.short, party.short, "self.name"),
            "phone": _pii("PHONE", party.phone, party.phone_flat, "self.phone"),
            "fare": _neg("fare", "проезд 340",
                         "«проезд» здесь — плата, а не тип улицы"),
        }
        fields = (
            ("trip_id", "trip_id", roles["trip_id"].value),
            ("pickup", "addr", party.address),
            ("passenger", "name", party.short),
            ("phone", "phone", party.phone),
            ("payment", "fare", roles["fare"].value),
        )
        return Record(_object_parts(fields), roles)
    if name == "contract_addr":
        roles = {
            "name": _pii("NAME", party.full, party.full, "self.name"),
            "addr": _pii("LOC", party.address, party.address, "self.loc"),
            "email": _pii("EMAIL", party.email, party.email, "self.email"),
            "area": _neg("measure", "45 кв м", "площадь помещения, не адрес"),
        }
        fields = (
            ("contract_id", "", "Д-2024/117"),
            ("client", "name", party.full),
            ("delivery_address", "addr", party.address),
            ("email", "email", party.email),
            ("area", "area", roles["area"].value),
        )
        return Record(_object_parts(fields), roles)
    if name == "contract_email":
        roles = {
            "email": _pii("EMAIL", party.email, party.email, "self.email"),
            "inn": _pii("INN", party.inn, party.inn, "self.inn"),
            "amount": _neg("quantity", "18400",
                           "сумма счёта, а не идентификатор"),
        }
        fields = (
            ("contract_id", "", "Д-2024/117"),
            ("billing_email", "email", party.email),
            ("inn", "inn", party.inn),
            ("amount", "amount", roles["amount"].value),
        )
        return Record(_object_parts(fields), roles)
    if name == "profile_doc":
        roles = {
            "dob": _pii("DOB", party.dob, party.dob, "self.dob"),
            "passport": _pii("PASSPORT", party.passport, party.passport,
                             "self.passport"),
            "snils": _pii("SNILS", party.snils, party.snils, "self.snils"),
            "office": _neg("room_number", "314",
                           "номер кабинета — не персональные данные"),
        }
        fields = (
            ("customer_id", "", customer_id),
            ("birth_date", "dob", party.dob),
            ("passport", "passport", party.passport),
            ("snils", "snils", party.snils),
            ("office", "office", roles["office"].value),
        )
        return Record(_object_parts(fields), roles)
    if name == "payment_only":
        roles = {
            "card": _pii("CARD", party.card, party.card, "self.card"),
            "amount": _neg("quantity", "4300", "сумма возврата"),
        }
        fields = (
            ("method", "", "карта"),
            ("card_number", "card", party.card),
            ("expires", "", "09/28"),
            ("last_amount", "amount", roles["amount"].value),
        )
        return Record(_object_parts(fields), roles)
    if name == "visit":
        roles = {
            "visit_id": _neg("order_number", f"V-{rng.randrange(1000, 9999)}",
                             "номер визита"),
            "plate": _pii("PLATE", party.plate, party.plate, "self.plate"),
            "name": _pii("NAME", party.short, party.short, "self.name"),
            "phone": _pii("PHONE", party.phone, party.phone_flat, "self.phone"),
            "bay": _neg("room_number", "12", "номер поста, не квартира"),
        }
        fields = (
            ("visit_id", "visit_id", roles["visit_id"].value),
            ("plate", "plate", party.plate),
            ("owner", "name", party.short),
            ("phone", "phone", party.phone),
            ("bay", "bay", roles["bay"].value),
        )
        return Record(_object_parts(fields), roles)
    if name == "ticket":
        roles = {
            "ticket_id": _neg("order_number", f"ОБР-{rng.randrange(100, 999)}",
                              "номер обращения"),
            "name": _pii("NAME", party.short, party.short, "self.name"),
            "phone": _pii("PHONE", party.phone, party.phone_flat, "self.phone"),
            "slot": _neg("time_of_day", "09:00", "время, а не идентификатор"),
        }
        fields = (
            ("ticket_id", "ticket_id", roles["ticket_id"].value),
            ("contact", "name", party.short),
            ("callback_phone", "phone", party.phone),
            ("slot", "slot", roles["slot"].value),
        )
        return Record(_object_parts(fields), roles)
    if name == "order_and_card":
        # ONE address, written twice. The gateway must give both mentions the
        # same substitute; a scorer sees that through the `same` link, and the
        # offsets only survive because `assemble` never searches.
        roles = {
            "order_id": _neg("order_number", order_id, "номер заказа"),
            "name": _pii("NAME", party.full, party.full, "self.name"),
            "addr": _pii("LOC", party.address, party.address, "self.loc"),
            "addr2": _pii("LOC", party.address, party.address, "self.loc"),
            "phone": _pii("PHONE", party.phone, party.phone_flat, "self.phone"),
        }
        fields = (
            ("order_id", "order_id", order_id),
            ("recipient", "name", party.full),
            ("delivery_address", "addr", party.address),
            ("profile_address", "addr2", party.address),
            ("phone", "phone", party.phone),
            ("note", "", "оставить у консьержа"),
        )
        return Record(_object_parts(fields), roles)
    if name == "empty_address":
        roles = {
            "order_id": _neg("order_number", order_id, "номер заказа"),
            "name": _pii("NAME", party.full, party.full, "self.name"),
            "phone": _pii("PHONE", party.phone, party.phone_flat, "self.phone"),
        }
        fields = (
            ("order_id", "order_id", order_id),
            ("recipient", "name", party.full),
            ("phone", "phone", party.phone),
            ("address", "", ""),
        )
        return Record(_object_parts(fields), roles)
    raise ValueError(f"unknown record {name!r}")


# --- tools ----------------------------------------------------------------
#
# `customer_id` is OPTIONAL in every lookup and its description says the session
# is used when it is absent. That is what makes a `solo` case — two messages, no
# system prompt — a real shape rather than a rigged one: an authenticated widget
# is how this traffic arrives, and demanding an id nobody stated would force the
# family to invent a message that states one.

def _tool(name: str, description: str, params: dict[str, tuple[str, str]],
          required: list[str]) -> ToolSchema:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": {key: {"type": kind, "description": text}
                               for key, (kind, text) in params.items()},
                "required": required,
            },
        },
    }


_SESSION = ("string", "Идентификатор клиента. Если не указан — берётся из "
                      "авторизованной сессии.")

TOOLS: dict[str, ToolSchema] = {
    "find_last_order": _tool(
        "find_last_order", "Найти последний заказ клиента.",
        {"customer_id": _SESSION}, []),
    "list_orders": _tool(
        "list_orders", "Список заказов клиента, свежие первыми.",
        {"customer_id": _SESSION,
         "limit": ("number", "Сколько заказов вернуть")}, []),
    "get_customer_card": _tool(
        "get_customer_card", "Карточка клиента: контакты и адрес доставки.",
        {"customer_id": _SESSION}, []),
    "find_address_by_street": _tool(
        "find_address_by_street",
        "Найти сохранённый адрес клиента по названию улицы.",
        {"street": ("string", "Название улицы так, как назвал клиент"),
         "customer_id": _SESSION}, ["street"]),
    "find_last_trip": _tool(
        "find_last_trip", "Последняя поездка клиента: откуда забирали.",
        {"customer_id": _SESSION}, []),
    "get_contract": _tool(
        "get_contract", "Реквизиты договора клиента.",
        {"contract_id": ("string", "Номер договора, если известен"),
         "customer_id": _SESSION}, []),
    "get_profile": _tool(
        "get_profile", "Анкета клиента: документы и дата рождения.",
        {"customer_id": _SESSION}, []),
    "get_payment_method": _tool(
        "get_payment_method", "Сохранённый способ оплаты клиента.",
        {"customer_id": _SESSION}, []),
    "find_last_visit": _tool(
        "find_last_visit", "Прошлый визит на сервис: машина и владелец.",
        {"customer_id": _SESSION}, []),
    "get_ticket": _tool(
        "get_ticket", "Открытое обращение клиента с контактами для связи.",
        {"customer_id": _SESSION}, []),
    "find_customer": _tool(
        "find_customer", "Найти клиента в базе.",
        {"customer_id": _SESSION,
         "query": ("string", "Что искать, если идентификатора нет")}, []),
    "get_order_note": _tool(
        "get_order_note", "Примечание к заказу вместе с адресом доставки.",
        {"customer_id": _SESSION}, []),
    "get_order_and_profile": _tool(
        "get_order_and_profile",
        "Заказ клиента вместе с адресом из его профиля.",
        {"customer_id": _SESSION}, []),

    "create_order": _tool(
        "create_order", "Оформить заказ и отправить его в доставку.",
        {"recipient_name": ("string", "ФИО получателя"),
         "phone": ("string", "Телефон получателя"),
         "address": ("string", "Адрес доставки с домом и квартирой"),
         "items": ("string", "Позиции заказа")},
        ["address"]),
    "update_delivery_address": _tool(
        "update_delivery_address", "Изменить адрес доставки у заказа.",
        {"order_id": ("string", "Номер заказа"),
         "address": ("string", "Новый адрес доставки")},
        ["order_id", "address"]),
    "call_customer": _tool(
        "call_customer", "Позвонить клиенту по указанному телефону.",
        {"phone": ("string", "Телефон для звонка"),
         "reason": ("string", "Причина звонка")},
        ["phone"]),
    "send_sms": _tool(
        "send_sms", "Отправить клиенту SMS.",
        {"phone": ("string", "Телефон получателя"),
         "text": ("string", "Текст сообщения")},
        ["phone", "text"]),
    "add_contact": _tool(
        "add_contact", "Добавить контакт в CRM.",
        {"name": ("string", "ФИО контакта"),
         "phone": ("string", "Телефон контакта")},
        ["name", "phone"]),
    "assign_driver": _tool(
        "assign_driver", "Назначить водителя на подачу по адресу.",
        {"address": ("string", "Адрес подачи"),
         "phone": ("string", "Телефон пассажира")},
        ["address"]),
    "route_courier": _tool(
        "route_courier", "Отправить курьера по адресу.",
        {"address": ("string", "Адрес доставки"),
         "note": ("string", "Что передать курьеру")},
        ["address"]),
    "issue_refund": _tool(
        "issue_refund", "Вернуть деньги на карту, с которой была оплата.",
        {"card_number": ("string", "Номер карты для возврата"),
         "amount": ("string", "Сумма возврата в рублях")},
        ["card_number", "amount"]),
    "verify_document": _tool(
        "verify_document", "Проверить документы клиента.",
        {"passport": ("string", "Серия и номер паспорта"),
         "snils": ("string", "Номер СНИЛС"),
         "birth_date": ("string", "Дата рождения ДД.ММ.ГГГГ")},
        ["birth_date"]),
    "send_invoice": _tool(
        "send_invoice", "Выставить счёт и отправить его на почту.",
        {"email": ("string", "Почта для отправки счёта"),
         "inn": ("string", "ИНН плательщика"),
         "amount": ("string", "Сумма счёта")},
        ["email", "amount"]),
    "book_service": _tool(
        "book_service", "Записать машину на сервис.",
        {"plate": ("string", "Государственный номер"),
         "phone": ("string", "Телефон владельца")},
        ["plate"]),
}

# Offered beside the pair a case needs. A single-tool prompt lets a model succeed
# by having nowhere else to go, which hides whether an implausible substitute
# damaged its ability to CHOOSE.
_DISTRACTORS: tuple[str, ...] = ("send_sms", "list_orders", "get_ticket",
                                 "call_customer", "route_courier")


# --- frames ---------------------------------------------------------------
#
# A frame is one way of not saying the value, and it is also the CLUSTER: cases
# built from one frame share a template and their failures correlate, so error
# bars must resample frames rather than cases. `shape` names the mined discourse
# envelope in `mined/calls_grammar.json`; the referring clause is composed from
# the mined intent lexicon, and the docstring says so rather than letting the
# field imply a corpus sentence that does not exist.

@dataclass(frozen=True)
class Frame:
    id: str
    asks: tuple[str, ...]        # voice_raw base form: lower case, no digits
    shape: str                   # mined shape id, "" for a verbatim frame
    selection: str
    record: str
    lookup: str
    action: str
    # (tool parameter, record slot). A slot may be a gold item or a negative —
    # an order number the model copies out of the record is judged too, because
    # a gateway that masked it hands the tool an argument no system can resolve.
    action_args: tuple[tuple[str, str], ...]
    judge_lookup: bool
    template_ok: bool
    note: str


FRAMES: tuple[Frame, ...] = (
    Frame("same_place",
          ("привезите туда же куда в прошлый раз",
           "доставьте на тот же адрес что и в прошлый раз",
           "отправьте туда же куда всегда возите"),
          "disc.attention", "census", "order", "find_last_order", "create_order",
          (("address", "addr"), ("recipient_name", "name"), ("phone", "phone")),
          True, False,
          "адрес не назван ни разу: он приходит из заказа и обязан вернуться "
          "настоящим во второй вызов"),
    Frame("address_from_card",
          ("адрес возьмите из моей карточки",
           "адрес у вас в карточке записан оттуда и берите",
           "адрес не диктую он у вас сохранён"),
          "disc.dictation", "census", "card", "get_customer_card",
          "create_order",
          (("address", "addr"), ("recipient_name", "name"), ("phone", "phone")),
          True, False,
          "клиент прямо отказывается диктовать: значение существует только "
          "внутри ответа инструмента"),
    Frame("partial_street",
          ("мы на {street} а дом я не помню",
           "на {street} а номер дома у вас должен быть",
           "{street} дом не помню посмотрите у себя"),
          "addr.street_no_number", "marker", "order",
          "find_address_by_street", "update_delivery_address",
          (("order_id", "order_id"), ("address", "addr")),
          True, False,
          "улица без дома никого не определяет — это optional, и она обязана "
          "разрешиться против полного адреса ВНУТРИ этого разговора"),
    Frame("partial_flat",
          ("квартира {flat_word} а дом вы знаете",
           "{entrance} подъезд а адрес у вас есть",
           "{flat_home} остальное как в прошлый раз"),
          "addr.number_only", "marker", "card", "get_customer_card",
          "create_order",
          (("address", "addr"), ("phone", "phone")),
          False, False,
          "номер квартиры сам по себе не адрес: он негатив, а полный адрес "
          "приходит из карточки"),
    Frame("driver_pickup",
          ("подъезжайте туда откуда вчера забирали",
           "заберите оттуда же откуда в прошлый раз",
           "подача туда же откуда возили"),
          "disc.attention", "census", "trip", "find_last_trip", "assign_driver",
          (("address", "addr"), ("phone", "phone")),
          False, False,
          "точка подачи известна только системе — диспетчерский регистр, где "
          "адрес обычно и не произносят"),
    Frame("two_orders_place",
          ("привезите туда же куда последний раз",
           "адрес как в последнем заказе а не в позапрошлом",
           "везите по свежему заказу тот адрес и нужен"),
          "disc.self_correction", "census", "two_orders", "list_orders",
          "update_delivery_address",
          (("order_id", "order_id"), ("address", "addr")),
          False, False,
          "две строки в ответе: чужой адрес обязан получить ДРУГУЮ подмену и не "
          "попасть ни в вызов, ни в ответ клиенту"),
    Frame("address_from_contract",
          ("как в договоре записано туда и везите",
           "адрес в договоре есть по нему и работайте"),
          "disc.dictation", "census", "contract_addr", "get_contract",
          "route_courier",
          (("address", "addr"),),
          False, False,
          "адрес приходит из договора вместе с почтой — две ПД разных типов в "
          "одной строке ответа инструмента"),
    Frame("order_phone",
          ("позвоните мне на тот номер что в заказе",
           "наберите на телефон который в заказе указан",
           "звоните на номер из заказа я его не диктую"),
          "disc.attention", "census", "order", "find_last_order",
          "call_customer",
          (("phone", "phone"),),
          True, False,
          "телефон не звучал ни разу: libphonenumber отработает по ответу "
          "инструмента или не отработает вовсе"),
    Frame("same_number_v",
          ("получить по этому же номеру",),
          "", "census", "ticket", "get_ticket", "send_sms",
          (("phone", "phone"),),
          False, False,
          "дословная реплика SOVA RuDevices: косвенная ссылка на номер, "
          "которого в разговоре нет"),
    Frame("callback_v",
          ("с утра наберёте на этот же номер я вас соединю",),
          "", "census", "ticket", "get_ticket", "call_customer",
          (("phone", "phone"),),
          False, False,
          "дословная реплика: клиент назначает обратный звонок на номер, "
          "который знает только система"),
    Frame("phone_from_card",
          ("телефон у вас в карточке есть по нему и звоните",
           "номер мой у вас записан не буду диктовать"),
          "disc.dictation", "census", "card", "get_customer_card",
          "call_customer",
          (("phone", "phone"),),
          True, False,
          "карточка вместо диктовки — самый частый способ не назвать телефон"),
    Frame("same_person",
          ("оформите на того же человека",
           "получатель тот же что и в прошлый раз",
           "на того же кто и заказывал оформляйте"),
          "disc.attention", "census", "order", "find_last_order",
          "create_order",
          (("recipient_name", "name"), ("phone", "phone"),
           ("address", "addr")),
          True, False,
          "имя приходит из системы в именительном — склонить его теперь может "
          "только модель, и вернуться оно обязано целым"),
    Frame("names_in_base_v",
          ("но фамилии уже есть в базе а имена там телефон",),
          "", "census", "card", "find_customer", "add_contact",
          (("name", "name"), ("phone", "phone")),
          False, False,
          "дословная реплика: говорящий ссылается на запись в базе вместо того "
          "чтобы назвать людей"),
    Frame("who_ordered",
          ("наберите тому кто вчера заказывал",
           "свяжитесь с тем кто оформлял прошлый заказ"),
          "disc.attention", "census", "order", "find_last_order",
          "call_customer",
          (("phone", "phone"),),
          False, False,
          "адресат описан ролью а не именем: и имя, и телефон существуют только "
          "в ответе CRM"),
    Frame("saved_card",
          ("верните на ту же карту с которой платил",
           "деньги назад на ту же карту она у вас сохранена"),
          "disc.attention", "census", "payment_only", "get_payment_method",
          "issue_refund",
          (("card_number", "card"), ("amount", "amount")),
          False, True,
          "номер карты не звучит: Луна проверяет то, что пришло из системы, а "
          "не то, что сказал клиент"),
    Frame("passport_on_file",
          ("паспорт у вас в анкете есть оттуда и берите",
           "паспортные данные я в прошлый раз давал они у вас"),
          "disc.dictation", "census", "profile_doc", "get_profile",
          "verify_document",
          (("passport", "passport"), ("birth_date", "dob")),
          False, True,
          "документ приходит из анкеты — путь tool → модель → tool для "
          "значения с контрольной суммой"),
    Frame("email_from_contract",
          ("счёт киньте на почту которая в договоре",
           "почта в договоре указана туда и шлите"),
          "disc.dictation", "census", "contract_email", "get_contract",
          "send_invoice",
          (("email", "email"), ("inn", "inn"), ("amount", "amount")),
          False, True,
          "почта и ИНН физлица приходят из договора: латиница внутри "
          "русской строки ответа инструмента"),
    Frame("dob_on_file",
          ("дату рождения вы знаете она у вас записана",
           "год рождения не диктую он в анкете"),
          "disc.attention", "census", "profile_doc", "get_profile",
          "verify_document",
          (("birth_date", "dob"), ("snils", "snils")),
          False, True,
          "дата рождения персональна по ассоциации — здесь ассоциация приходит "
          "из анкеты, а не из фразы клиента"),
    Frame("plate_same_car",
          ("машина та же что и в прошлый раз",
           "номер машины у вас с прошлого визита остался"),
          "disc.attention", "census", "visit", "find_last_visit",
          "book_service",
          (("plate", "plate"), ("phone", "phone")),
          False, False,
          "госномер — буквы и цифры вперемешку: сравнение по цифрам его бы "
          "склеило, поэтому PLATE сверяется целиком"),
    Frame("snils_on_file",
          ("снилс я вам в прошлый раз давал он у вас есть",
           "снилс в анкете смотрите я его наизусть не помню"),
          "disc.dictation", "census", "profile_doc", "get_profile",
          "verify_document",
          (("snils", "snils"), ("birth_date", "dob")),
          False, True,
          "СНИЛС из анкеты: контрольная сумма по модулю сто один считается по "
          "тому, что пришло от клиента системы"),
    Frame("saved_address_q",
          ("а адрес у вас мой сохранён",
           "скажите адрес мой у вас записан или нет"),
          "disc.attention", "census", "card", "get_customer_card",
          "create_order",
          (("address", "addr"), ("phone", "phone")),
          False, False,
          "закрытый вопрос: ответ «да» проверяем отдельно от того, попал ли "
          "настоящий адрес в вызов"),
    Frame("no_saved_address",
          ("пришлите на сохранённый адрес",
           "везите на тот адрес который у вас записан"),
          "disc.attention", "census", "empty_address", "find_last_order",
          "call_customer",
          (("phone", "phone"),),
          False, False,
          "адреса в системе НЕТ: правильный ответ «нет», и телефон всё равно "
          "обязан вернуться настоящим"),
    Frame("as_in_order_v",
          ("ээ сейчас сто семьдесят как у него в заказе есть так и останется",),
          "", "census", "order", "find_last_order", "update_delivery_address",
          (("order_id", "order_id"), ("address", "addr")),
          False, False,
          "дословная реплика: «как в заказе есть так и останется» — ссылка на "
          "сохранённое значение вместо значения"),
    Frame("as_last_time_v",
          ("что осматривает моё разрешение будешь как по стандарту как в прошлый раз",),
          "", "census", "visit", "find_last_visit", "book_service",
          (("plate", "plate"), ("phone", "phone")),
          False, False,
          "дословная реплика с ошибками расшифровки внутри — регистр, в котором "
          "косвенная ссылка и приходит"),
    Frame("same_place_twice",
          ("адрес как в заказе он же и в профиле",
           "везите по тому адресу что и в профиле и в заказе"),
          "disc.word_repeat", "census", "order_and_card",
          "get_order_and_profile", "update_delivery_address",
          (("order_id", "order_id"), ("address", "addr")),
          False, False,
          "один адрес написан в ответе дважды: обе строки обязаны получить одну "
          "подмену, иначе модель видит два разных места"),
    Frame("two_people_phone",
          ("наберите тому кто оформлял свежий заказ",
           "звоните по свежему заказу а не по старому"),
          "disc.self_correction", "census", "two_orders", "list_orders",
          "call_customer",
          (("phone", "phone"),),
          False, False,
          "два телефона в одном ответе: восстановиться обязан тот, о ком шла "
          "речь, — единственный источник other_person без второго разговора"),
    Frame("order_note",
          ("в примечании к заказу адрес есть",
           "адрес в примечании смотрите я его не повторяю"),
          "disc.dictation", "census", "order_and_card", "get_order_note",
          "route_courier",
          (("address", "addr"),),
          False, False,
          "адрес спрятан в примечании к заказу — тот же путь, другая форма "
          "ответа инструмента"),
    Frame("ticket_callback",
          ("в обращении номер записан по нему и наберите",
           "телефон в обращении есть новый я не давал"),
          "disc.attention", "census", "ticket", "get_ticket", "call_customer",
          (("phone", "phone"),),
          True, False,
          "обращение как источник контакта: значение пришло из системы, а не "
          "из речи"),
)

_VERBATIM_FRAMES: frozenset[str] = frozenset(VERBATIM_TRIGGERS)


# --- register rendering ---------------------------------------------------
#
# The trigger carries NO gold value in this family (the partial street is the one
# exception and it is tracked as a slot), so a writing error inside a literal is
# free: there is no ground truth to keep in step with it. That is not true
# anywhere else in the corpus, and it is why this module can afford `sloppy`
# without the `_spoil_pair` machinery the user-leg families need.

_OPENERS: tuple[str, ...] = ("", "", "", "здравствуйте ", "алло здравствуйте ",
                             "а ", "аа ", "добрый день ", "алё ")
_FILLERS: tuple[str, ...] = ("", "", "", "ээ ", "нуу ", "иии ", "это самое ")
_ATTENTION: tuple[str, ...] = ("", "", "слушайте ", "значит ", "короче ",
                               "смотрите ", "вот ")
_TAILS: tuple[str, ...] = ("", "", " спасибо", " если можно", " пожалуйста",
                           " хорошо", " всё")

# Keyboard-shaped, not phonetic: `sloppy` is a messenger and `voice_raw` is ASR,
# and the two break in different ways. A phonetic error here would make the two
# registers the same register with two names.
_LATIN_TWINS: dict[str, str] = {"о": "o", "а": "a", "е": "e", "с": "c",
                                "р": "p", "у": "y", "х": "x"}


def _typo(text: str, rng: random.Random) -> str:
    """One keyboard-shaped error in a literal chunk."""
    roll = rng.random()
    positions = [index for index, char in enumerate(text)
                 if char.isalpha() and index > 0]
    if not positions:
        return text
    index = rng.choice(positions)
    if roll < 0.4:
        return text[:index] + text[index + 1:]
    if roll < 0.7:
        spaces = [i for i, char in enumerate(text) if char == " " and i > 0]
        if not spaces:
            return text[:index] + text[index + 1:]
        cut = rng.choice(spaces)
        return text[:cut] + text[cut + 1:]
    twin = _LATIN_TWINS.get(text[index])
    if twin is None:
        return text[:index] + text[index + 1:]
    return text[:index] + twin + text[index + 1:]


# --- negatives in the customer's own words --------------------------------
#
# The single largest false-positive source in this register: a number standing
# beside «кабинет» or «отделение» occurs 528 times in the call corpus, and «к
# девяти ноль ноль» — a time whose zeros are spoken — 66. Every case carries at
# least one, in the register it is being read in.

def _spoken_negatives(rng: random.Random) -> tuple[tuple[str, str, str, str], ...]:
    """(prefix, value, family, why) for a `voice_raw` turn. No digit anywhere."""
    room = rng.randrange(2, 15)
    hour = rng.randrange(7, 12)
    count = rng.randrange(2, 10)
    return (
        (" в ", f"{_ORDINALS[room]} кабинет", "room_number",
         "номер кабинета рядом с числом — не персональные данные"),
        (" к ", f"{_HOUR_DATIVE[hour]} ноль ноль", "time_of_day",
         "время, ноли проговорены словом"),
        (" ", f"{_ORDINALS[rng.randrange(2, 7)]} подъезд",
         "entrance_no_street", "подъезд без улицы никого не определяет"),
        (" возьмите ", f"{_spell(count)} {_pieces(count)}", "quantity",
         "количество, а не номер"),
        (" на ", "улице дождь", "street_no_name",
         "«улица» без названия — про погоду, не адрес"),
        (" по заказу ", f"{_spell(rng.randrange(11, 99))}", "order_number",
         "номер заказа, продиктованный словами"),
    )


def _digit_negatives(rng: random.Random) -> tuple[tuple[str, str, str, str], ...]:
    """The same traps once inverse text normalisation has put the digits back."""
    return (
        (" в ", f"{rng.randrange(101, 415)} кабинет", "room_number",
         "номер кабинета"),
        # No colon: `[.,;:!?]` is sentence punctuation to the register gate, and
        # ITN on this traffic writes «к 9 00» rather than «к 9:00» anyway.
        (" к ", f"{rng.randrange(8, 12)} 00", "time_of_day", "время"),
        (" ", f"{rng.randrange(2, 7)} подъезд", "entrance_no_street",
         "подъезд без улицы"),
        (" возьмите ", f"{(count := rng.randrange(2, 9))} {_pieces(count)}",
         "quantity", "количество"),
        (" по заказу ", f"{rng.randrange(100, 9999)}", "order_number",
         "номер заказа"),
        (" квартира ", "маленькая", "flat_as_home",
         "«квартира» как жильё, без номера"),
    )


# --- one case -------------------------------------------------------------

_SYSTEM_BASE = ("Ты оператор поддержки. Клиент уже авторизован, его "
                "идентификатор {cid}. Личные данные бери только из системы "
                "через инструменты и не проси клиента диктовать их заново.")
_SYSTEM_ECHO = (" В ответе повтори значение ровно так, как оно записано в "
                "системе.")


def _flat_word(party: Party, register: str) -> str:
    return (_spell(party.flat) if register == "voice_raw"
            else str(party.flat))


# A placeholder the ask carries and the case tracks: (slot, kind, family, why).
# Split off the TEMPLATE before formatting, never located in the finished
# sentence — the whole family's discipline in one place.
#
# «квартира двенадцать» is deliberately NOT in this table. A flat number standing
# with no street identifies nobody («дом пять» / «квартира двенадцать»,
# `addr.number_only`, 15 utterances in the call corpus), so it belongs in the
# negatives — and `NEGATIVE_FAMILIES` has no row for it: `flat_as_home` is
# «квартира» WITHOUT a number and `entrance_no_street` is an ordinal plus
# «подъезд». Filing it under either would make that family's own number wrong,
# so the corpus leaves it unclaimed and says so here rather than mislabelling it.
_PLACEHOLDERS: dict[str, tuple[str, str, str, str]] = {
    "{street}": ("hint", "pii", "", ""),
    "{entrance}": ("negent", "neg", "entrance_no_street",
                   "порядковое с подъездом, но улицы в реплике нет"),
    "{flat_home}": ("negflat", "neg", "flat_as_home",
                    "«квартира» без номера — жильё, а не адрес"),
}


def _trigger_parts(frame: Frame, party: Party, register: str,
                   rng: random.Random) -> tuple[list[Part], list[tuple[str, str, str]]]:
    """The customer's turn as parts, plus (slot, family, why) for its negatives.

    The partial street is written as the slot `hint` — the one place in this
    family where a gold span sits in the user's own text, and it is `optional`
    because a street with no house number identifies nobody.
    """
    template = rng.choice(frame.asks)
    values = {"street": party.street.lower(),
              "flat_word": _flat_word(party, register),
              "entrance": _ORDINALS[rng.randrange(2, 7)] + " подъезд",
              "flat_home": "квартира"}
    parts: list[Part] = []
    claims: list[tuple[str, str, str]] = []

    marker = next((name for name in _PLACEHOLDERS if name in template), "")
    if marker:
        slot, kind, family, why = _PLACEHOLDERS[marker]
        head, _, tail = template.partition(marker)
        parts.extend([head.format(**values), (slot, values[marker[1:-1]]),
                      tail.format(**values)])
        if kind == "neg":
            claims.append((slot, family, why))
    else:
        parts.append(template.format(**values))

    # `clean` takes the spoken pool too: a web form written by a person who was
    # reading a number aloud is not this corpus's business, and the digit-bearing
    # traps are already carried by four registers out of five.
    pool = (_spoken_negatives(rng) if register in ("voice_raw", "clean")
            else _digit_negatives(rng))
    if register == "voice_itn":
        # ITN is DEFINED by the digits being on, and the trigger's only digit is
        # the one a negative brings. A trap with no digit in it would leave a
        # `voice_itn` case that is a `voice_raw` case in disguise — the schema
        # refuses that, and rightly.
        pool = tuple(row for row in pool if any(ch.isdigit() for ch in row[1]))
    chosen = rng.sample(pool, 2 if rng.random() < 0.45 else 1)
    for index, (prefix, value, family, why) in enumerate(chosen):
        slot = f"neg{index}"
        parts.append(f",{prefix}" if register == "clean" else prefix)
        parts.append((slot, value))
        claims.append((slot, family, why))

    parts.append(rng.choice(_TAILS))
    if register == "clean":
        # A written form carries no «алё», no «ээ» and no «слушайте»; those are
        # the discourse of a phone call and `_render_register` supplies the
        # literary opener instead.
        return parts, claims
    prefix_parts: list[Part] = [rng.choice(_OPENERS), rng.choice(_FILLERS),
                                rng.choice(_ATTENTION)]
    return prefix_parts + parts, claims


def _render_register(parts: list[Part], register: str,
                     rng: random.Random) -> list[Part]:
    """Apply the register before assembly, never after.

    A pass over a FINISHED message changes its length and silently invalidates
    every offset already computed against it: the corpus keeps scoring, and
    scores wrongly. `sloppy` therefore edits literal chunks only — a typo inside
    a tracked slot would leave the ground truth claiming a spelling the message
    no longer carries, which is the defect that made 162 of v1's 183 sloppy
    failures the corpus's own rather than the gateway's.

    `clean` is the one branch that touches a slot, capitalising the first content
    part whether it is a literal or a slot, and it is safe for a reason that does
    not generalise: every value in this module is read back OUT of the assembled
    string, so the ground truth follows the edit instead of being contradicted by
    it.
    """
    if register == "sloppy":
        literals = [index for index, part in enumerate(parts)
                    if isinstance(part, str) and len(part.strip()) >= 8]
        if literals:
            index = rng.choice(literals)
            parts = list(parts)
            parts[index] = _typo(str(parts[index]), rng)
        return parts
    if register == "clean":
        # A capital and a full stop are what `clean` IS: the schema refuses a
        # `clean` case without both, because a lower-case one would be a chat
        # case spending the literary budget. The first content part is
        # capitalised whether it is a literal or a SLOT — a form writes «Ленина»
        # — and the slot's ground truth follows it, because every value in this
        # module is read back out of the assembled string.
        rendered: list[Part] = ["Здравствуйте! "]
        capitalised = False
        for part in parts:
            if capitalised or not str(part[1] if isinstance(part, tuple)
                                      else part).strip():
                rendered.append(part)
                continue
            if isinstance(part, tuple):
                slot, value = part
                stripped = value.lstrip()
                pad = value[:len(value) - len(stripped)]
                rendered.append((slot, pad + stripped[0].upper() + stripped[1:]))
            else:
                stripped = part.lstrip()
                pad = part[:len(part) - len(stripped)]
                rendered.append(pad + stripped[0].upper() + stripped[1:])
            capitalised = True
        rendered.append(".")
        return rendered
    return parts


def _party_pair(rng: random.Random) -> tuple[Party, Party]:
    """Two people whose surnames differ, so `other_person` is decidable.

    Two rows carrying the same surname would make a restored value ambiguous
    between them, and `classify_break` would name the wrong outcome — the corpus
    would be reporting a defect it manufactured.
    """
    first = _party(rng)
    for _ in range(64):
        second = _party(rng)
        if (second.full != first.full and second.address != first.address
                and second.phone != first.phone):
            return first, second
    # Bounded rather than `while True`. A pool a caller can exhaust is a hang
    # here for the same reason it is a permanent 5xx in the engine, and the
    # useful form of that failure is a message naming the pool.
    raise ValueError("the party pools no longer yield two distinct people; "
                     "widen _SURNAMES_*, _GIVEN_* or _STREETS_*")


def _messages_for(frame: Frame, context: str, trigger: str,
                  source: Source | None, record_text: str, customer_id: str,
                  echo: bool,
                  rng: random.Random) -> tuple[list[Message], int, int]:
    """Every message, plus the indexes of the trigger and of the tool result."""
    messages: list[Message] = []
    if context != "solo":
        system = _SYSTEM_BASE.format(cid=customer_id)
        if echo:
            system += _SYSTEM_ECHO
        messages.append(Message(role="system", content=system, source=None,
                                name=""))

    if context in ("long", "deep"):
        pairs = rng.randrange(4, 9) if context == "long" else 16
        pool = list(_FILLER)
        rng.shuffle(pool)
        agent = list(_AGENT_FILLER)
        rng.shuffle(agent)
        index = 0
        while True:
            text, key, line, digest = pool[index % len(pool)]
            messages.append(Message(
                role="user", content=text,
                source=Source(corpus="speech_rudevices", key=key, line=line,
                              sha256=digest, licence="CC BY 4.0"),
                name=""))
            messages.append(Message(role="assistant",
                                    content=agent[index % len(agent)],
                                    source=None, name=""))
            index += 1
            if context == "long" and index >= pairs:
                break
            if context == "deep":
                # The character floor, not the message count, is what makes a
                # long context long: thirty two-word replies are not one.
                so_far = sum(len(message.content) for message in messages)
                if index >= pairs and so_far >= 4_400:
                    break
                if index >= 88:
                    break

    trigger_index = len(messages)
    messages.append(Message(role="user", content=trigger, source=source, name=""))
    tool_index = len(messages)
    messages.append(Message(role="tool", content=record_text, source=None,
                            name=frame.lookup))
    return messages, trigger_index, tool_index


def _case(frame: Frame, register: str, context: str, index: int,
          rng: random.Random) -> Case:
    case_id = f"i3-ind-{index:04d}"
    party, other = _party_pair(rng)
    customer_id = f"C-{rng.randrange(1000, 9999)}"
    record = _record(frame.record, party, other, customer_id, rng)
    record_text, record_spans = assemble(record.parts)
    # A hand-built record that does not parse is a bug in this module, and it
    # would reach the customer's gateway as a tool result no real system emits.
    # Raised, never repaired: `_object_parts` refuses a value needing an escape,
    # so a failure here means the assembly is wrong rather than the value.
    json.loads(record_text)
    # `must_contain` is only ever set where the SYSTEM PROMPT asked for the value
    # back, and a `solo` case has no system prompt. Demanding a long address
    # verbatim from a model nobody told to repeat it scores the gateway on a
    # paraphrase.
    echo = rng.random() < 0.3 and context != "solo"

    source: Source | None = None
    if frame.id in _VERBATIM_FRAMES:
        # A real utterance, unchanged, and therefore with NO claims of its own:
        # a negative inside it would need an offset located in a string this
        # module did not build, and locating one is precisely what the family
        # forbids. Its gold lives where every other case's does — in the record.
        trigger_text, key, line, digest = VERBATIM_TRIGGERS[frame.id]
        trigger_spans: Spans = {}
        negative_claims: list[tuple[str, str, str]] = []
        source = Source(corpus="speech_rudevices", key=key, line=line,
                        sha256=digest, licence="CC BY 4.0")
    else:
        trigger_parts, negative_claims = _trigger_parts(frame, party, register,
                                                        rng)
        trigger_text, trigger_spans = assemble(
            _render_register(trigger_parts, register, rng))

    messages, trigger_index, tool_index = _messages_for(
        frame, context, trigger_text, source, record_text, customer_id, echo,
        rng)

    # --- gold and negatives ------------------------------------------------
    items: list[PiiItem] = []
    negatives: list[Negative] = []
    slot_to_item: dict[str, str] = {}
    slot_param = {slot: param for param, slot in frame.action_args}

    for slot, role in record.roles.items():
        start, end = record_spans[slot]
        if role.kind == "neg":
            negatives.append(Negative(value=role.value, start=start, end=end,
                                      msg=tool_index, family=role.tag,
                                      why=role.why))
            continue
        item_id = f"p{len(items) + 1}"
        slot_to_item[slot] = item_id
        items.append(PiiItem(
            id=item_id, type=role.tag, value=role.value,
            canonical=role.canonical, start=start, end=end, msg=tool_index,
            identity=f"{case_id}.{role.identity}", duty="required",
            value_source="template" if role.tag in (
                "PHONE", "EMAIL", "DOB", "SNILS", "INN", "CARD", "PASSPORT",
                "PLATE") else "pool",
            spoken=False,
            tool_param=slot_param.get(slot, "")))

    if "hint" in trigger_spans:
        start, end = trigger_spans["hint"]
        hint_id = f"p{len(items) + 1}"
        items.append(PiiItem(
            id=hint_id, type="LOC", value=trigger_text[start:end],
            canonical=party.address, start=start, end=end, msg=trigger_index,
            identity=f"{case_id}.self.hint", duty="optional",
            value_source="pool", spoken=False, tool_param=""))
    else:
        hint_id = ""

    for slot, family, why in negative_claims:
        start, end = trigger_spans[slot]
        negatives.append(Negative(value=trigger_text[start:end], start=start,
                                  end=end, msg=trigger_index, family=family,
                                  why=why))

    # --- links -------------------------------------------------------------
    links: list[LinkExpectation] = []
    if hint_id and "addr" in slot_to_item:
        links.append(LinkExpectation(
            left=hint_id, right=slot_to_item["addr"], kind="same", case="",
            why="улица без дома обязана разрешиться против полного адреса из "
                "ответа инструмента внутри ЭТОГО разговора"))
    if "addr2" in slot_to_item:
        links.append(LinkExpectation(
            left=slot_to_item["addr"], right=slot_to_item["addr2"], kind="same",
            case="", why="один адрес написан в ответе дважды: одна личность — "
                         "одна подмена"))
    if "other_addr" in slot_to_item:
        links.append(LinkExpectation(
            left=slot_to_item["addr"], right=slot_to_item["other_addr"],
            kind="different", case="",
            why="разные клиенты: слияние отдало бы адрес одного в заказ другого"))
    if "other_phone" in slot_to_item:
        links.append(LinkExpectation(
            left=slot_to_item["phone"], right=slot_to_item["other_phone"],
            kind="different", case="",
            why="два телефона в одном ответе не одна личность"))

    # --- calls -------------------------------------------------------------
    arguments: dict[str, str] = {}
    pii_items: list[str] = []
    for param, slot in frame.action_args:
        role = record.roles[slot]
        arguments[param] = role.value
        if role.kind == "pii":
            pii_items.append(slot_to_item[slot])
    if frame.action == "call_customer":
        arguments["reason"] = "уточнить доставку"
    if frame.action == "send_sms":
        arguments["text"] = "ваш заказ готов"
    if frame.action == "route_courier":
        arguments["note"] = "позвонить за час"

    calls: list[ExpectedCall] = []
    if frame.judge_lookup and context != "solo":
        if frame.lookup == "find_address_by_street" and hint_id:
            calls.append(ExpectedCall(
                name=frame.lookup,
                arguments={"street": trigger_text[trigger_spans["hint"][0]:
                                                  trigger_spans["hint"][1]]},
                judged_args=("street",), pii_items=(), after_msg=trigger_index))
        else:
            calls.append(ExpectedCall(
                name=frame.lookup, arguments={"customer_id": customer_id},
                judged_args=("customer_id",), pii_items=(),
                after_msg=trigger_index))
    calls.append(ExpectedCall(
        name=frame.action, arguments=arguments,
        judged_args=tuple(param for param, _ in frame.action_args),
        pii_items=tuple(pii_items), after_msg=tool_index))

    # --- the final reply ---------------------------------------------------
    must_contain: tuple[str, ...] = ()
    must_not_contain: tuple[str, ...] = ()
    answer = ""
    if frame.id == "saved_address_q":
        answer = "да"
    elif frame.id == "no_saved_address":
        answer = "нет"
    forbidden = [role.value for slot, role in record.roles.items()
                 if slot.startswith("other_") and role.kind == "pii"]
    if forbidden:
        must_not_contain = tuple(forbidden)
    if echo and not must_not_contain:
        # Only where the system prompt ASKED for the value back. Demanding a
        # long address verbatim from a model nobody told to repeat it would
        # score the gateway on a paraphrase.
        echo_slot = next((slot for slot in ("addr", "phone", "email", "plate")
                          if slot in slot_to_item), "")
        if echo_slot:
            must_contain = (record.roles[echo_slot].value,)

    provenance = _provenance(frame, register)
    conversation_id = f"i3-conv-{index:04d}" if index % 2 == 0 else ""
    return Case(
        id=case_id,
        family=FAMILY,
        register=register,
        context=context,
        provenance=provenance,
        cluster=f"i3.{frame.id}",
        conversation_id=conversation_id,
        messages=tuple(messages),
        tools=tuple(TOOLS[name] for name in _offered(frame)),
        pii=tuple(items),
        negatives=tuple(negatives),
        links=tuple(links),
        calls=tuple(calls),
        final=FinalAnswer(must_contain=must_contain,
                          must_not_contain=must_not_contain, answer=answer),
        preceded_by="",
        annotators=0,
        adjudicated=False,
        note=frame.note,
    )


def _offered(frame: Frame) -> tuple[str, ...]:
    names = [frame.lookup, frame.action]
    for candidate in _DISTRACTORS:
        if candidate not in names:
            names.append(candidate)
            break
    return tuple(names)


def _provenance(frame: Frame, register: str) -> Provenance:
    """Where the FORM came from. Three answers and they are not interchangeable.

    A verbatim frame carries a real utterance and names it. A template frame is
    permitted ONLY where the record holds nothing a speech corpus could have
    supplied — no NAME, no LOC — and only in a written register, because a spoken
    envelope IS mined and calling it authored would understate what the case is.
    Everything else is `recombined`, and its `shape` names the mined envelope.
    """
    if frame.id in _VERBATIM_FRAMES:
        _, key, _, _ = VERBATIM_TRIGGERS[frame.id]
        return Provenance(kind="verbatim", corpus="speech_rudevices", key=key,
                          shape="", selection="census", weight=1.0,
                          licence="CC BY 4.0")
    if frame.template_ok and register in ("chat", "sloppy", "clean"):
        return Provenance(kind="template", corpus="authored", key="", shape="",
                          selection="authored", weight=1.0, licence="authored")
    return Provenance(kind="recombined", corpus="speech_calls", key="",
                      shape=frame.shape, selection=frame.selection, weight=1.0,
                      licence="CC BY-NC 4.0")


# --- the schedule ---------------------------------------------------------
#
# Registers and context rungs are laid out on FIXED CYCLES rather than drawn, so
# the mix is a property of the file and not of how many times a builder happened
# to call `rng`. The cycles hold the shares the corpus plan gives this family:
# speech is the base, `clean` is one case in twenty-five, and every rung of
# context is present so the frozen ladder can close on it.

def _interleave(counts: tuple[tuple[str, int], ...]) -> tuple[str, ...]:
    """A cycle where every value is spread evenly, not blocked.

    Item i of a value with n slots sits at fraction (i + 0.5) / n, and the whole
    list is sorted by that fraction — v2's `build.py` uses the same construction
    to interleave families. Blocked cycles would make the first thirty cases
    entirely `voice_raw`, so any prefix of this family — and a ladder builder
    reaching for early ids — would see one register and three frames.
    """
    slots = [((index + 0.5) / count, name)
             for name, count in counts for index in range(count)]
    slots.sort()
    return tuple(name for _, name in slots)


# THE OWNER NAMED FIVE FORMS, and they carry more of the family than the ones
# added around them: «туда же куда в прошлый раз», «на тот номер что в заказе»,
# «на того же человека», «адрес из моей карточки», «на ленина, дом не помню».
# A flat cycle would have given each of the twenty-eight frames nine cases and
# left the partial mention — the only linking claim this family can make, and
# the one the owner spelled out — measured on nine.
_FRAME_WEIGHTS: dict[str, int] = {
    "same_place": 3, "order_phone": 3, "same_person": 3,
    "partial_street": 3, "address_from_card": 2,
}
_BY_ID: dict[str, Frame] = {frame.id: frame for frame in FRAMES}
_FRAME_CYCLE: tuple[str, ...] = ()   # filled below, once `_interleave` exists

_REGISTER_CYCLE: tuple[str, ...] = _interleave(
    (("voice_raw", 24), ("voice_itn", 7), ("chat", 12), ("sloppy", 5),
     ("clean", 2)))
_CONTEXT_CYCLE: tuple[str, ...] = _interleave(
    (("short", 12), ("solo", 4), ("long", 6), ("deep", 3)))
_FRAME_CYCLE = _interleave(
    tuple((frame.id, _FRAME_WEIGHTS.get(frame.id, 1)) for frame in FRAMES))


def _schedule(count: int) -> list[tuple[Frame, str, str]]:
    plan: list[tuple[Frame, str, str]] = []
    for index in range(count):
        frame = _BY_ID[_FRAME_CYCLE[index % len(_FRAME_CYCLE)]]
        register = _REGISTER_CYCLE[index % len(_REGISTER_CYCLE)]
        context = _CONTEXT_CYCLE[index % len(_CONTEXT_CYCLE)]
        # A verbatim trigger IS an ASR transcript: no digit, no punctuation, no
        # capital. Reading it as `chat` would be a claim about the text that the
        # text refutes, and `solo` would leave it with no dialogue to refer back
        # to — «получить по этому же номеру» refers to something.
        if frame.id in _VERBATIM_FRAMES:
            register = "voice_raw"
            if context == "solo":
                context = "short"
        # The literary register has no filler pool here on purpose: a long
        # context of raw ASR under a `clean` trigger is two registers in one
        # case, and the register is the thing being measured.
        if register == "clean" and context in ("long", "deep"):
            context = "short"
        # `voice_itn` is defined by digits being ON. The trigger only carries one
        # through a negative, and `partial_street` has no digit-bearing negative
        # to give it, so the pair is impossible rather than unlucky.
        if register == "voice_itn" and frame.id == "partial_street":
            register = "voice_raw"
        plan.append((frame, register, context))
    return plan


def build(rng: random.Random, count: int) -> list[Case]:
    """`count` cases, in schedule order.

    The caller owns the generator, as in v2's `build.py`: one stream per family,
    seeded from the run seed and the family name, so adding a frame here cannot
    redraw another family's cases.
    """
    return [_case(frame, register, context, index, rng)
            for index, (frame, register, context) in
            enumerate(_schedule(count))]


def main() -> int:
    """Build the family and check it against the schema.

    Returns 1 on any problem. A generator whose spans disagree with its own text
    keeps producing numbers and the numbers are false, so this is a gate and not
    a report.
    """
    cases = build(random.Random("v3:indirect:20260830"), TARGET)
    problems = [problem for case in cases for problem in validate(case)]

    by_register: dict[str, int] = {}
    by_context: dict[str, int] = {}
    by_provenance: dict[str, int] = {}
    for case in cases:
        by_register[case.register] = by_register.get(case.register, 0) + 1
        by_context[case.context] = by_context.get(case.context, 0) + 1
        by_provenance[case.provenance.kind] = (
            by_provenance.get(case.provenance.kind, 0) + 1)
    real_form = sum(count for kind, count in by_provenance.items()
                    if kind in ("verbatim", "recombined"))
    speech = sum(count for register, count in by_register.items()
                 if register in ("voice_raw", "voice_itn"))

    print(f"случаев:        {len(cases)}")
    print(f"кластеров:      {len({case.cluster for case in cases})}")
    print(f"по регистрам:   {by_register}")
    print(f"по контексту:   {by_context}")
    print(f"происхождение:  {by_provenance}")
    print(f"форма из речи:  {real_form}/{len(cases)} = "
          f"{real_form / len(cases):.0%}")
    print(f"речь:           {speech}/{len(cases)} = {speech / len(cases):.0%}")
    print(f"золотых по типам: {type_denominators(cases)}")
    print(f"различных значений: {distinct_values(cases)}")
    print(f"негативов:      {sum(len(case.negatives) for case in cases)}")
    print(f"связей same:    "
          f"{sum(1 for c in cases for l in c.links if l.kind == 'same')}")
    print(f"связей different: "
          f"{sum(1 for c in cases for l in c.links if l.kind == 'different')}")
    print(f"вызовов:        {sum(len(case.calls) for case in cases)}")
    print(f"с закрытым ответом: "
          f"{sum(1 for case in cases if case.final.answer)}")
    print(f"с must_not_contain: "
          f"{sum(1 for case in cases if case.final.must_not_contain)}")
    print(f"длина:          {min(case_characters(c) for c in cases)}-"
          f"{max(case_characters(c) for c in cases)} символов")
    print(f"с id разговора: {sum(1 for c in cases if c.conversation_id)}")

    if problems:
        print(f"НЕВАЛИДНО — {len(problems)} проблем:")
        for problem in problems[:25]:
            print(f"  {problem}")
        return 1
    print("схема: без замечаний")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
