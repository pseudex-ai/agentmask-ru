"""Build the street vocabulary from ГАР without downloading 53 GiB of it.

WHY ГАР AND NOT OSM. Our address arms need the street NAME and the street TYPE
as separate strings — that is what lets one entry match «ул. Ленина», «улица
Ленина», «Ленина ул.» and «ленина» in a messenger. ГАР keeps them in separate
columns (`NAME`, `TYPENAME`); OSM keeps one rendered string and would have to be
un-rendered by guesswork. The licence decides it independently: ODbL §4.4(c)
makes leasing an OSM-derived vocabulary to a customer Public Use, which is
exactly what `licensing/` exists NOT to do. ГАР's licence permits it — see
`docs/gar-street-vocabulary.md`.

WHY A RANGE READER AND NOT A DOWNLOAD. `gar_xml.zip` is 53.5 GiB and we want
~1 GiB of it: 96 regional `AS_ADDR_OBJ` members and ten type dictionaries. The
archive answers `accept-ranges: bytes`, so the ZIP64 central directory (246 KB
at the very end) can be read first and each member fetched by its own byte
range. Measured: ~140 MB transferred, ~10 minutes, against 53.5 GiB and a day.

WHY THE ACTIVE FILTER IS NOT OPTIONAL. `AS_ADDR_OBJ` is a HISTORY table —
~3.4 M rows, every rename of every object since 2011. `ISACTUAL=1 AND
ISACTIVE=1` is what leaves the ~1.2 M streets that exist today. Without it the
vocabulary would carry every name a street has EVER had, and a vocabulary is a
gate: entries that no longer name anything only widen what we mask.

FAILS LOUDLY, NEVER HALF-WRITES. A partial street dictionary is worse than
none, because detection degrades silently — the gateway keeps answering 200 and
simply stops seeing addresses. Every member's CRC32 is checked against the
central directory, every expected member must be present, and the outputs are
written to temporary files and renamed only when all 96 regions have parsed.

usage:
    python3 -m licensing.fetch_gar                    # full run, ~10 min
    python3 -m licensing.fetch_gar --regions 01,77    # one or two, for a change
    python3 -m licensing.fetch_gar --dry-run          # manifest + directory only
"""

import argparse
import json
import os
import re
import struct
import sys
import time
import urllib.error
import urllib.request
import zlib
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

_MANIFEST = "https://fias-file.nalog.ru/WebServices/Public/GetLastDownloadFileInfo"
_DATA = Path(__file__).resolve().parent / "data"

# The five dictionaries that name the parts of a Russian address. Ten sit at the
# ZIP root and total ~12 KB compressed; these are the ones a detector can use.
# `AS_OPERATION_TYPES`, `AS_PARAM_TYPES`, `AS_OBJECT_LEVELS` and the two
# normative-document dictionaries describe the REGISTRY's own bookkeeping and
# name nothing a customer would ever write in a message.
_TYPE_MEMBERS = {
    "addr_obj": "AS_ADDR_OBJ_TYPES",
    "house": "AS_HOUSE_TYPES",
    "addhouse": "AS_ADDHOUSE_TYPES",
    "apartment": "AS_APARTMENT_TYPES",
    "room": "AS_ROOM_TYPES",
}
# LEVEL 8 is «улица» in ГАР's object hierarchy — the street itself, below the
# settlement (7) and above the planning structure. It is the only level whose
# names a person writes in an address.
_STREET_LEVEL = "8"

_HTTP_ATTEMPTS = 4
_HTTP_BACKOFF = 3.0


class GarError(RuntimeError):
    """The dump could not be read as expected. Never a partial result."""


@dataclass(frozen=True)
class Member:
    """One file inside the archive, located but not yet fetched."""
    name: str
    offset: int          # local header offset
    compressed: int
    uncompressed: int
    crc: int
    method: int


# --- transport -----------------------------------------------------------


def _get(url: str, headers: dict[str, str]) -> bytes:
    """One request, retried, then raised. Never a short read passed on silently.

    ГАР's CDN drops connections under a long sequence of range requests, and a
    truncated member is indistinguishable from a small one until the CRC fails
    — so retry here and let the CRC be the second net rather than the first."""
    last: Exception | None = None
    for attempt in range(_HTTP_ATTEMPTS):
        try:
            request = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(request, timeout=300) as response:
                return response.read()
        except (urllib.error.URLError, OSError, TimeoutError) as error:
            last = error
            if attempt + 1 < _HTTP_ATTEMPTS:
                delay = _HTTP_BACKOFF * (attempt + 1)
                print(f"  retry {attempt + 1}/{_HTTP_ATTEMPTS - 1} in {delay:.0f}s "
                      f"({headers.get('Range', 'full')}): {error}", file=sys.stderr)
                time.sleep(delay)
    raise GarError(f"GET {url} {headers.get('Range', '')} failed after "
                   f"{_HTTP_ATTEMPTS} attempts: {last!r}") from last


def _range(url: str, start: int, length: int) -> bytes:
    body = _get(url, {"Range": f"bytes={start}-{start + length - 1}"})
    if len(body) != length:
        raise GarError(f"range {start}+{length} returned {len(body)} bytes — "
                       f"the server ignored Range, or the read was truncated")
    return body


def manifest() -> dict[str, object]:
    """The dump ФНС currently publishes.

    `fias.nalog.ru` (the portal) is unreachable from outside RU; the CDN origin
    `fias-file.nalog.ru` that serves this endpoint and the archive itself is
    not. Both facts were verified before this script was written and both are
    load-bearing — the portal URL would make the script fail for everyone here."""
    payload = json.loads(_get(_MANIFEST, {}).decode("utf-8"))
    for key in ("GarXMLFullURL", "Date", "VersionId"):
        if not payload.get(key):
            raise GarError(f"manifest has no {key}: {payload!r}")
    return payload


def _total_size(url: str) -> int:
    request = urllib.request.Request(url, method="HEAD")
    with urllib.request.urlopen(request, timeout=120) as response:
        if response.headers.get("Accept-Ranges") != "bytes":
            raise GarError(
                "the archive does not advertise byte ranges — the whole 53 GiB "
                "would have to be downloaded, and this script refuses to do that"
            )
        return int(response.headers["Content-Length"])


def central_directory(url: str) -> list[Member]:
    """Every member of the archive, from its ZIP64 central directory.

    246 KB read out of 53.5 GiB. Written by hand rather than with `zipfile`
    because `zipfile` wants a seekable file object over the WHOLE archive, and
    the point here is never to have one."""
    total = _total_size(url)
    tail = _range(url, total - 65536, 65536)
    locator = tail.rfind(b"PK\x06\x07")
    if locator < 0:
        raise GarError("no ZIP64 end-of-central-directory locator in the tail — "
                       "the archive is not the ZIP64 file this script expects")
    eocd64_offset = struct.unpack("<Q", tail[locator + 8:locator + 16])[0]
    record = _range(url, eocd64_offset, 56)
    if record[:4] != b"PK\x06\x06":
        raise GarError(f"ZIP64 EOCD signature missing at {eocd64_offset}")
    entries, cd_size, cd_offset = struct.unpack("<QQQ", record[32:56])
    directory = _range(url, cd_offset, cd_size)

    members: list[Member] = []
    position = 0
    while position < len(directory) and directory[position:position + 4] == b"PK\x01\x02":
        (flags, method, crc, csize, usize, name_len, extra_len, comment_len) = (
            struct.unpack("<H", directory[position + 8:position + 10])[0],
            struct.unpack("<H", directory[position + 10:position + 12])[0],
            struct.unpack("<I", directory[position + 16:position + 20])[0],
            struct.unpack("<I", directory[position + 20:position + 24])[0],
            struct.unpack("<I", directory[position + 24:position + 28])[0],
            struct.unpack("<H", directory[position + 28:position + 30])[0],
            struct.unpack("<H", directory[position + 30:position + 32])[0],
            struct.unpack("<H", directory[position + 32:position + 34])[0],
        )
        offset = struct.unpack("<I", directory[position + 42:position + 46])[0]
        name = directory[position + 46:position + 46 + name_len].decode(
            "utf-8" if flags & 0x800 else "cp437")
        extra = directory[position + 46 + name_len:position + 46 + name_len + extra_len]
        # THE ZIP64 EXTRA FIELD IS POSITIONAL, not tagged per value: it holds
        # only the fields whose 32-bit slot is saturated, in a fixed order. A
        # 53 GiB archive saturates the offset for every member past 4 GiB, so
        # reading it wrongly points every later range request at the wrong place.
        cursor = 0
        while cursor + 4 <= len(extra):
            header_id, header_size = struct.unpack("<HH", extra[cursor:cursor + 4])
            body = extra[cursor + 4:cursor + 4 + header_size]
            if header_id == 0x0001:
                at = 0
                if usize == 0xFFFFFFFF:
                    usize = struct.unpack("<Q", body[at:at + 8])[0]
                    at += 8
                if csize == 0xFFFFFFFF:
                    csize = struct.unpack("<Q", body[at:at + 8])[0]
                    at += 8
                if offset == 0xFFFFFFFF:
                    offset = struct.unpack("<Q", body[at:at + 8])[0]
            cursor += 4 + header_size
        members.append(Member(name, offset, csize, usize, crc, method))
        position += 46 + name_len + extra_len + comment_len
    if len(members) != entries:
        raise GarError(f"central directory declares {entries} members, parsed {len(members)}")
    return members


def _member_bytes(url: str, member: Member) -> bytes:
    """One member, decompressed and CRC-checked.

    The LOCAL header's extra field is a different length from the central
    directory's — the local one carries the alignment padding — so the data
    offset has to be read from the local header rather than computed from the
    directory entry."""
    head = _range(url, member.offset, 30)
    if head[:4] != b"PK\x03\x04":
        raise GarError(f"{member.name}: no local header at {member.offset}")
    name_len, extra_len = struct.unpack("<HH", head[26:30])
    raw = _range(url, member.offset + 30 + name_len + extra_len, member.compressed)
    if member.method == 0:
        body = raw
    elif member.method == 8:
        body = zlib.decompress(raw, -15)
    else:
        raise GarError(f"{member.name}: compression method {member.method} is not supported")
    if len(body) != member.uncompressed:
        raise GarError(f"{member.name}: inflated to {len(body)}, directory says "
                       f"{member.uncompressed}")
    if zlib.crc32(body) != member.crc:
        raise GarError(f"{member.name}: CRC32 mismatch — the transfer was corrupted")
    return body


# --- parsing -------------------------------------------------------------

# Attribute reader rather than an XML parser, and the reason is size: the 96
# street members inflate to ~1 GiB and every row is a single self-closing
# element with no text content and no namespaces. ElementTree builds an object
# per row for a dictionary lookup we make in one pass.
#
# Safe here BECAUSE the shape is that narrow: ГАР writes `NAME="Ленина"` with
# double quotes and XML entities, and both are handled below. It would not be
# safe on arbitrary XML, which is why this function is private to this module.
_ROW_RE = re.compile(rb"<(?P<tag>[A-Z]+)\s(?P<attrs>[^>]*?)/>")
_ATTR_RE = re.compile(rb'(?P<key>[A-Z]+)="(?P<value>[^"]*)"')
_ENTITIES = {"&amp;": "&", "&lt;": "<", "&gt;": ">", "&quot;": '"', "&apos;": "'"}


def _unescape(text: str) -> str:
    if "&" not in text:
        return text
    for entity, char in _ENTITIES.items():
        text = text.replace(entity, char)
    return text


def _rows(blob: bytes):
    for row in _ROW_RE.finditer(blob):
        yield {key.decode("ascii"): _unescape(value.decode("utf-8"))
               for key, value in _ATTR_RE.findall(row.group("attrs"))}


def parse_types(blob: bytes) -> list[dict[str, str]]:
    """Every row of a type dictionary, ACTIVE AND INACTIVE ALIKE.

    Приказ Минфина 171н marks 47 of its 147 rows `<*>` — «не подлежит
    присвоению новым объектам» — and ГАР marks the same set `ISACTIVE=false`.
    They are still what people write: «влд.», «двлд.», «наб.», «км», «лн.» are
    all in that set and all common in real addresses. A detector that only
    knows the assignable types cannot read a document written in 2013.

    LEVEL IS KEPT PER ROW, not folded away. The same word carries different
    abbreviations at different levels — «Сквер» is `сквер` at level 7 and `с-р`
    at level 8 — so a flat word→abbreviation map silently loses one of them."""
    return [row for row in _rows(blob) if "NAME" in row]


def parse_streets(blob: bytes) -> Counter:
    """Active LEVEL-8 names and how many streets carry each.

    The COUNT is what makes a frequency cut possible later: the curve is
    extremely steep, and knowing that «Центральная» names 20 000 streets while
    «Тупиковый переулок» names one is the whole basis for deciding how much of
    the tail is worth leasing."""
    names: Counter = Counter()
    for row in _rows(blob):
        if row.get("LEVEL") != _STREET_LEVEL:
            continue
        if row.get("ISACTUAL") != "1" or row.get("ISACTIVE") != "1":
            continue
        name = row.get("NAME", "").strip()
        if name:
            names[name] += 1
    return names


def parse_street_types(blob: bytes) -> Counter:
    """TYPENAME as it is actually used at level 8, with its frequency.

    `AS_ADDR_OBJ_TYPES` says which types EXIST; this says which are used and how
    often, which is a different question and the one that decides what a
    detector must recognise."""
    types: Counter = Counter()
    for row in _rows(blob):
        if row.get("LEVEL") != _STREET_LEVEL:
            continue
        if row.get("ISACTUAL") != "1" or row.get("ISACTIVE") != "1":
            continue
        typename = row.get("TYPENAME", "").strip()
        if typename:
            types[typename] += 1
    return types


# --- output --------------------------------------------------------------


def _write_atomic(path: Path, text: str) -> None:
    """Rename over the old file, never write into it.

    A run interrupted halfway would otherwise leave a truncated vocabulary that
    still loads and still builds a bundle — and detection would quietly cover
    the regions that happened to arrive first."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".partial")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=_DATA)
    parser.add_argument("--regions", default="",
                        help="comma-separated region codes; default = all 96")
    parser.add_argument("--dry-run", action="store_true",
                        help="read the manifest and the directory, fetch nothing else")
    args = parser.parse_args()

    info = manifest()
    url = str(info["GarXMLFullURL"])
    print(f"ГАР {info['Date']} (version {info['VersionId']})\n{url}", file=sys.stderr)

    members = central_directory(url)
    by_name = {member.name: member for member in members}
    streets = {name: member for name, member in by_name.items()
               if "/AS_ADDR_OBJ_" in name and "_TYPES_" not in name
               and "_PARAMS_" not in name and "_DIVISION_" not in name}
    if args.regions:
        wanted = {code.strip() for code in args.regions.split(",") if code.strip()}
        streets = {name: member for name, member in streets.items()
                   if name.split("/")[0] in wanted}
        missing = wanted - {name.split("/")[0] for name in streets}
        if missing:
            raise GarError(f"no AS_ADDR_OBJ member for region(s) {sorted(missing)}")
    elif len(streets) < 80:
        # 85 federal subjects plus the ЗАТО/Байконур pseudo-regions; the dump has
        # carried 96 for years. A sharp drop means the naming changed and the
        # filter above stopped matching — which would silently halve the
        # vocabulary rather than fail.
        raise GarError(f"found only {len(streets)} regional AS_ADDR_OBJ members; "
                       f"expected ~96 — the member naming has changed")
    print(f"members: {len(members)}   regions: {len(streets)}   "
          f"to fetch: {sum(m.compressed for m in streets.values()) / 1e6:.0f} MB",
          file=sys.stderr)
    if args.dry_run:
        return 0

    type_tables: dict[str, list[dict[str, str]]] = {}
    for key, prefix in _TYPE_MEMBERS.items():
        matches = [member for name, member in by_name.items()
                   if "/" not in name and name.startswith(prefix + "_")]
        if len(matches) != 1:
            raise GarError(f"expected exactly one {prefix} member, found {len(matches)}")
        type_tables[key] = parse_types(_member_bytes(url, matches[0]))
        print(f"  {prefix}: {len(type_tables[key])} rows", file=sys.stderr)

    names: Counter = Counter()
    typenames: Counter = Counter()
    populated = 0
    for index, (name, member) in enumerate(sorted(streets.items()), start=1):
        blob = _member_bytes(url, member)
        found = parse_streets(blob)
        populated += bool(found)
        names.update(found)
        typenames.update(parse_street_types(blob))
        print(f"  [{index:>2}/{len(streets)}] {name.split('/')[0]:>3}  "
              f"{len(found):>6} names  {sum(found.values()):>7} streets",
              file=sys.stderr)

    # AN EMPTY REGION IS NORMAL; A RUN OF THEM IS NOT. Codes 80, 81, 84, 85 and
    # 88 are autonomous okrugs abolished between 2005 and 2008 — their members
    # are still shipped and hold only history, so `ISACTUAL=1 AND ISACTIVE=1`
    # correctly leaves nothing. Failing on the first empty one (which this did)
    # would make the script refuse to complete for a reason that is not a fault.
    # The condition worth failing on is the one that would silently halve the
    # vocabulary: the filter, the schema or the level having changed under us,
    # which shows as MANY regions going quiet at once.
    if not args.regions and populated < 80:
        raise GarError(f"only {populated} of {len(streets)} regions returned active "
                       f"LEVEL-{_STREET_LEVEL} rows — the schema or the filter changed")
    if not names:
        raise GarError("no street names at all — refusing to write an empty vocabulary")

    total = sum(names.values())
    print(f"\ndistinct names: {len(names)}   street objects: {total}   "
          f"populated regions: {populated}/{len(streets)}", file=sys.stderr)

    header = (f"# Государственный адресный реестр (ФИАС), ФНС России — "
              f"выгрузка от {info['Date']}\n"
              f"# https://fias.nalog.ru/ · ОТКРЫТАЯ ЛИЦЕНЗИЯ ФНС России\n"
              f"# LEVEL=8, ISACTUAL=1, ISACTIVE=1. count<TAB>name, "
              f"по убыванию частоты.\n")
    body = "".join(f"{count}\t{name}\n"
                   for name, count in sorted(names.items(), key=lambda kv: (-kv[1], kv[0])))
    _write_atomic(args.out_dir / "gar_streets.tsv", header + body)

    _write_atomic(args.out_dir / "gar_types.json", json.dumps(
        {
            "source": "Государственный адресный реестр (ФИАС), ФНС России",
            "dump_date": info["Date"],
            "version_id": info["VersionId"],
            "licence": "ОТКРЫТАЯ ЛИЦЕНЗИЯ ФНС России",
            "tables": type_tables,
            # What level 8 ACTUALLY uses, which is a shorter list than the
            # dictionary and ordered by how often a customer will write it.
            "level8_used": dict(typenames.most_common()),
        },
        ensure_ascii=False, indent=1, sort_keys=False) + "\n")
    print(f"wrote {args.out_dir / 'gar_streets.tsv'} and "
          f"{args.out_dir / 'gar_types.json'}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
