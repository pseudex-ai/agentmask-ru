"""Bundle wire format: sealed to one process, signed by us.

Shared by the licensing server (which seals) and the engine (which opens), so the
two can never disagree about the format.

WHY BOTH ENCRYPTION AND A SIGNATURE — they answer different questions:

  * **age (X25519) encryption** answers "who may open this". The recipient is a
    keypair the WORKER PROCESS generated in memory at startup and never wrote
    down. A captured lease response is therefore useless anywhere else, and there
    is no portable form of the bundle to copy off the machine.

  * **Ed25519 signature** answers "who made this". age in x25519 mode does not
    authenticate the sender: anyone holding the process's public key can seal a
    bundle to it. For a product whose entire value is detection quality, a
    swapped bundle is a silent PII leak — so the engine verifies the plaintext
    hash against a signature made with a key that only we hold, and whose public
    half is compiled into the binary.

The signature covers the plaintext hash rather than the ciphertext: age
ciphertext is randomized per seal, so signing it would force a re-sign per lease
and would still say nothing about what is inside.
"""

import base64
import hashlib
import hmac
import json
from dataclasses import dataclass

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.serialization import (Encoding,
                                                          PublicFormat)
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes
from pyrage import decrypt, encrypt, x25519


class BundleError(RuntimeError):
    """The bundle could not be opened, or is not ours."""


@dataclass(frozen=True)
class ProcessKey:
    """An X25519 identity that exists only in this process's memory.

    `identity` is a `pyrage.x25519.Identity` — a Rust object with no importable
    Python type to annotate, which is why this field is the one loose type in the
    module. It is never serialized, never logged and never leaves the process."""

    identity: x25519.Identity
    public: str


def generate_process_key() -> ProcessKey:
    identity = x25519.Identity.generate()
    return ProcessKey(identity=identity, public=str(identity.to_public()))


def is_recipient(encoded: str) -> bool:
    """Разбирается ли строка как получатель age — БЕЗ шифрования.

    Нужна серверу, чтобы отказать 400 на битом `pubkey`, а не упасть внутри
    `seal` в 500. Пятисотка у клиента grace-worthy, то есть чужой мусор в теле
    запроса покупал сорок восемь часов работы в долг — ровно тот же примитив,
    что и отчёт с нечисловым счётчиком, только другой дверью.
    """
    try:
        x25519.Recipient.from_str(encoded)
    except Exception:  # noqa: BLE001 — pyrage бросает свой тип, см. `seal`
        return False
    return True


def seal(plaintext: bytes, recipient_public: str) -> str:
    """Encrypt the bundle to one process. Returns base64 for JSON transport."""
    try:
        recipient = x25519.Recipient.from_str(recipient_public)
    except Exception as error:  # pyrage raises its own type on a malformed key
        raise BundleError(f"bad recipient public key: {recipient_public!r}") from error
    return base64.b64encode(encrypt(plaintext, [recipient])).decode("ascii")


def open_sealed(sealed_b64: str, process_key: ProcessKey) -> bytes:
    try:
        return decrypt(base64.b64decode(sealed_b64), [process_key.identity])
    except Exception as error:
        raise BundleError(
            "bundle did not decrypt with this process's key — it was sealed to "
            "someone else, or the payload is corrupt"
        ) from error


# ВНЕШНИЙ СЛОЙ БАНДЛА, КЛЮЧ КОТОРОГО = СВЕЖИЙ НОНС КЛИЕНТА.
#
# Зачем поверх age-печати. Проверка «эхо нонса совпало» — булева ветка, и на
# машине атакующего её снимают одним NOP: тогда снятый из памяти реальный
# бандл можно предъявлять пропатченному клиенту вечно (§3.4-остаток). Если же
# КЛЮЧ расшифровки выводится из нонса, который клиент сгенерировал ДЛЯ ЭТОГО
# запроса, то повтор старой аренды даёт нерасшифровываемый бандл — ветку
# снимать бесполезно, надо перенаправить сам вход KDF на старый нонс, а это уже
# не «инвертировать переход», а понять и переписать поток данных.
#
# Не закрывает остаток полностью (полный патч клиента + снятие нонса из
# захваченной аренды всё ещё возможны) — но поднимает планку ровно так, как
# сформулирована цель: с «инвертировать один переход» до «разобрать и
# перенаправить KDF». Ломается ГРОМКО: ошибка здесь = бандл не расшифровался =
# 503, а не тихое ослабление.
#
# Аддитивно к age: per-process-привязка (захваченная аренда бесполезна на
# другой машине) сохраняется внешним age-слоем, этот — внутренний.
_BUNDLE_INFO = b"pseudex-bundle-nonce-v1"


def _bundle_key(nonce: str) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=None,
               info=_BUNDLE_INFO).derive(nonce.encode("utf-8"))


def nonce_wrap(plaintext: bytes, nonce: str) -> bytes:
    """AEAD-обёртка бандла ключом из нонса. 12 байт AEAD-нонса впереди."""
    aead_nonce = hashlib.sha256(nonce.encode("utf-8") + b"aead").digest()[:12]
    ct = ChaCha20Poly1305(_bundle_key(nonce)).encrypt(aead_nonce, plaintext, None)
    return aead_nonce + ct


def nonce_unwrap(wrapped: bytes, nonce: str) -> bytes:
    """Снять обёртку ключом из нонса, который сгенерировал ЭТОТ процесс.

    Неверный нонс (повтор чужой/старой аренды) → провал аутентификации AEAD →
    `BundleError`. Ветки, которую можно инвертировать, здесь нет: нонс — это
    ключ."""
    if len(wrapped) < 12:
        raise BundleError("nonce-wrapped bundle is too short")
    aead_nonce, ct = wrapped[:12], wrapped[12:]
    try:
        return ChaCha20Poly1305(_bundle_key(nonce)).decrypt(aead_nonce, ct, None)
    except Exception as error:
        raise BundleError(
            "bundle does not decrypt under this request's nonce — a replayed or "
            "foreign lease, or a tampered nonce source"
        ) from error


def plaintext_hash(plaintext: bytes) -> str:
    return hashlib.sha256(plaintext).hexdigest()


def signing_payload(lease: dict[str, object]) -> bytes:
    """Canonical bytes covered by the LEASE signature: every field except the
    ciphertext and the signature itself. `bundle_sha256` is in there, which is
    what binds the signature to the contents.

    БЕЗ ДОМЕННОГО ТЕГА, И ЭТО НЕ НЕДОСМОТР. Добавить его к подписи лизы —
    изменение НЕ аддитивное: новый сервер плюс старый движок дают несходящуюся
    подпись у ВСЕХ развёрнутых контейнеров, то есть ровно то направление, которое
    `docs/operations.md` §2bis объявляет запрещённым. Разделение типов сделано
    иначе и внутри тела: квант несёт `kind: "capacity"` ПОД подписью, и клиент
    его сверяет, поэтому предъявить лизу как квант или наоборот нельзя.
    """
    covered = {key: value for key, value in lease.items()
               if key not in ("bundle", "signature")}
    return json.dumps(covered, sort_keys=True, separators=(",", ":")).encode("utf-8")


# Доменный тег отчёта. Один канонический вид на два типа сообщений — это
# приглашение спутать их; здесь тег можно добавить безопасно, потому что MAC
# отчёта проверяем МЫ и можем принимать обе формы, пока в парке есть старые
# движки.
_REPORT_DOMAIN = b"pseudex-report-v1\x00"


def report_payload(report: dict[str, object]) -> bytes:
    """Канонические байты отчёта. Исключается ТОЛЬКО подпись.

    `signing_payload` исключает ещё и `bundle` — у лизы это шифротекст, а у
    отчёта поля с таким именем не бывает, и привилегированное имя в чужом
    сообщении означало, что поле `bundle` в отчёте оказалось бы ВНЕ MAC.
    """
    covered = {key: value for key, value in report.items() if key != "signature"}
    return _REPORT_DOMAIN + json.dumps(
        covered, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sign_lease(lease: dict[str, object], private_key: Ed25519PrivateKey) -> str:
    return base64.b64encode(private_key.sign(signing_payload(lease))).decode("ascii")


def mac_report(report: dict[str, object], secret: bytes) -> str:
    """HMAC отчёта секретом, который пришёл ЗАПЕЧАТАННЫМ на этот процесс.

    ЧТО ЭТОТ MAC ДОКАЗЫВАЕТ, И ЧЕГО НЕ ДОКАЗЫВАЕТ — ЕДИНСТВЕННОЕ МЕСТО, ГДЕ ЭТО
    НАПИСАНО ПОЛНОСТЬЮ. Остальные комментарии про подпись отчёта ссылаются сюда.

    Доказывает три вещи:
      * отчёт не переписан В КАНАЛЕ — перехватчик на хосте клиента не может ни
        подделать его, ни изменить. Подпись ключом, который контейнер объявляет
        сам, этого не давала: такой ключ подменяется в первом же обращении, и
        подпись начинает удостоверять перехватчика;
      * отчёт принадлежит ТОЙ ЖЕ ЦЕПИ, что предыдущие от этого процесса —
        пропуск, перестановка и повтор видны как разрыв;
      * мера исполняемой сборки лежит ВНУТРИ подписанного тела, поэтому ложь о
        ней становится датированной записью, а не разговором по памяти.

    НЕ ДОКАЗЫВАЕТ, ЧТО ЧИСЛА ПРАВДИВЫ. Получателя секрета называет сам клиент:
    он присылает свой открытый ключ, мы запечатываем секрет ему, и владелец
    ключа открывает его и подписывает что угодно. Проверено — клиент,
    написанный за тридцать строк на одном лишь ключе лицензии, отдаёт отчёты,
    которые проходят как `trust=signed`.

    Поэтому счёт строится НЕ НА ЭТОМ. Он строится на выданной ёмкости — числе,
    которое пишем мы сами и которое клиент может только не попросить, перестав
    обслуживать, — а подтверждённый отчёт лишь УМЕНЬШАЕТ начисление до
    фактического расхода. Так у клиента появляется собственный интерес
    отчитываться честно, и механизм принуждения не нужен вовсе.
    """
    return hmac.new(secret, report_payload(report), hashlib.sha256).hexdigest()


def verify_report(report: dict[str, object], secret: bytes) -> None:
    """ФОРМА ПРОВЕРЯЕТСЯ ДО СРАВНЕНИЯ, И СРАВНИВАЮТСЯ БАЙТЫ.

    `hmac.compare_digest` на строках бросает `TypeError`, если в них есть
    что-то вне ASCII, — а `signature` приходит из тела запроса. Незнакомый
    `TypeError` летел мимо `except (BundleError, ValueError)` и превращался в
    500, который клиент читает как НАШ сбой и уходит в grace. Проверка биллинга
    не имеет права падать в ту сторону.
    """
    given = report.get("signature")
    if not isinstance(given, str) or len(given) != 64:
        raise BundleError("report MAC has the wrong shape")
    try:
        given_bytes = bytes.fromhex(given)
    except ValueError as error:
        raise BundleError("report MAC is not hex") from error
    # ОБЕ ФОРМЫ, ПОКА В ПАРКЕ ЕСТЬ СТАРЫЕ ДВИЖКИ. Новая — с доменным тегом;
    # старая — общий с лизой канонический вид. Проверяем мы, поэтому переход
    # обходится без единовременной поломки, а откат совместимости — отдельный
    # коммит, когда старых образов не останется.
    unsigned = {k: v for k, v in report.items() if k != "signature"}
    for candidate in (report_payload(report), signing_payload(unsigned)):
        if hmac.compare_digest(given_bytes,
                               hmac.new(secret, candidate, hashlib.sha256).digest()):
            return
    raise BundleError("report MAC does not verify")


def decode_public_key(encoded: str) -> Ed25519PublicKey:
    """Parse our verification key from its base64 raw form.

    Lives here, not in `licensing/`, because the ENGINE needs it and the licensing
    package never ships to a customer — importing it from the engine would drag
    the asset source into the image and defeat the whole lease."""
    try:
        return Ed25519PublicKey.from_public_bytes(base64.b64decode(encoded))
    except Exception as error:
        raise BundleError(f"malformed verification key: {encoded[:16]!r}") from error


def verify_lease(lease: dict[str, object], public_key: Ed25519PublicKey) -> None:
    signature = lease.get("signature")
    if not isinstance(signature, str):
        raise BundleError("lease carries no signature")
    try:
        public_key.verify(base64.b64decode(signature), signing_payload(lease))
    except InvalidSignature as error:
        raise BundleError(
            "lease signature is not ours — refusing to load the bundle"
        ) from error
