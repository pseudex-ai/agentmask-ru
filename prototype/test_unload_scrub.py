"""H3: leased-data caches are scrubbed when the bundle is unloaded.

Assets.unload() drops `self._current`, but several module-level `lru_cache`s hold a
SECOND copy of the leased vocabulary/pools as plain str tuples, keyed on the bundle
version and invisible to unload — up to `maxsize` versions of the gazetteer survived
a revocation (pentest H3: `address._street_index`/`names._misspelling_index` ->
`fuzzy.DeletionIndex._words`). unload() now clears every leased-data cache, so no
leased vocabulary outlives the lease.

The vault fake-pool caches (`_first_names_by_gender`, `_usable_streets`, ...) read the
binary `_FAKE_*` pools TODAY, but those move into the lease in WS-2; clearing them here
is forward-compatible and harmless now.

Run:  python3 test_unload_scrub.py
"""
import sys
import pathlib

_HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

from pseudex import address, names, morph_places, vault  # noqa: E402
from pseudex.assets import ASSETS  # noqa: E402
from testkit import load_dev_bundle  # noqa: E402


def main() -> None:
    load_dev_bundle()
    v = ASSETS.version

    # Populate every leased-data cache.
    address._street_index(v)
    address._street_stems(v)
    address._spoken_house_after_for(v)
    names._misspelling_index(v)
    morph_places._word_number_for(v)
    vault._first_names_by_gender(v)
    vault._usable_streets(v)
    vault._invariant_last_names(v)
    vault._round_trip_last_names(v, "masc")
    vault._token_re(v)

    caches = {
        "address._street_index": address._street_index,
        "address._street_stems": address._street_stems,
        "address._spoken_house_after_for": address._spoken_house_after_for,
        "names._misspelling_index": names._misspelling_index,
        "morph_places._word_number_for": morph_places._word_number_for,
        "vault._first_names_by_gender": vault._first_names_by_gender,
        "vault._usable_streets": vault._usable_streets,
        "vault._invariant_last_names": vault._invariant_last_names,
        "vault._round_trip_last_names": vault._round_trip_last_names,
        "vault._token_re": vault._token_re,
    }
    populated = [n for n, c in caches.items() if c.cache_info().currsize > 0]
    assert len(populated) == len(caches), (
        f"test bug: only {len(populated)}/{len(caches)} caches populated: {populated}")
    print(f"before unload: {len(populated)}/{len(caches)} leased-data caches hold a copy")

    ASSETS.unload()

    leftover = [n for n, c in caches.items() if c.cache_info().currsize > 0]
    assert not leftover, f"leased-data cache survived unload(): {leftover}"
    print(f"OK — all {len(caches)} leased-data caches cleared on unload()")
    print("H3: no leased vocabulary copy survives revocation")


if __name__ == "__main__":
    main()
