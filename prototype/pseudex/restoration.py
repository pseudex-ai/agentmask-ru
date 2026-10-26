"""OUT receipts: request-local coordinates, never restored literals or lookups.

Prose records accepted, rendered, changed splices. JSON records actual changed-
leaf writes in the walker and joins; structural lexical maps bind those writes
across serialization. Whole leaf lexemes include quotes. Semantic completeness
is NOT a claim that json.dumps preserved whitespace/escaping. Nothing here is
cached, persisted, audited, or used for provider streaming.
"""

import hashlib
import json
import uuid

from pseudex.inspection import pointer
from pseudex.json_fields import scalar_map


def _same_scalar(left: str, right: str) -> bool:
    if left == right:
        return True  # includes Python's accepted NaN/Infinity JSON extensions
    before, after = json.loads(left), json.loads(right)
    return type(before) is type(after) and before == after


class RestorationField:
    def __init__(self, path: str) -> None:
        self.path = path
        self.replacements: list[dict[str, object]] = []
        self.writes: set[tuple[str | int, ...]] = set()
        self.semantic_complete = True
        self.lexical_complete = True
        self.limitations: list[str] = []

    def limit(self, reason: str, semantic: bool = True) -> None:
        if reason not in self.limitations:
            self.limitations.append(reason)
        if semantic:
            self.semantic_complete = False
        self.lexical_complete = False

    def splice(self, start: int, end: int, output_start: int, output_end: int) -> None:
        self.replacements.append({
            "source_start": start, "source_end": end,
            "output_start": output_start, "output_end": output_end,
            "type": "RESTORATION", "kind": "restoration", "granularity": "span"})

    def write(self, path: tuple[str | int, ...], before: object, after: object) -> None:
        # Called at the assignment, never inferred by comparing the final trees.
        if type(before) is not type(after) or before != after:
            self.writes.add(path)

    def json(self, source: str, output: str, include_splices: bool = False) -> None:
        """Bind recorded writes to independently parsed source/output lexemes.

        Parsing the serialized output is a structural map, NOT searching for a
        decoded value in json.dumps output (which cannot align escapes). Prior
        flat splices on JSON-shaped assistant content are promoted to owning
        whole leaves only when an unambiguous source leaf contains the splice.
        """
        source_map, source_error = scalar_map(source)
        output_map, output_error = scalar_map(output)
        if include_splices:
            for one in self.replacements:
                owners = [path for path, (lo, hi) in source_map.items()
                          if lo <= one["source_start"] < one["source_end"] <= hi]
                if len(owners) == 1:
                    self.writes.add(owners[0])
                else:
                    self.limit("json_splice_outside_scalar_leaf")
        self.replacements = []
        if source_error or output_error:
            self.limit(source_error or output_error)
            return
        if source_map.keys() != output_map.keys():
            self.limit("json_structure_changed")
        for path in source_map.keys() & output_map.keys():
            lo, hi = source_map[path]
            start, end = output_map[path]
            if path not in self.writes and not _same_scalar(source[lo:hi], output[start:end]):
                # A future/unsupported branch must fail the coverage claim. This
                # structural check NEVER invents a replacement for that branch.
                self.limit("untracked_json_leaf_change")
        for path in sorted(self.writes, key=lambda item: tuple(str(x) for x in item)):
            if path not in source_map or path not in output_map:
                self.limit("json_write_without_lexical_leaf")
                continue
            lo, hi = source_map[path]
            start, end = output_map[path]
            # A write that returned to the original semantic value is not a
            # restoration, nor is a different escaping of an unchanged leaf.
            if _same_scalar(source[lo:hi], output[start:end]):
                continue
            leaf_path = ""
            for component in path:
                leaf_path = pointer(leaf_path, component)
            self.replacements.append({
                "source_start": lo, "source_end": hi,
                "output_start": start, "output_end": end,
                "type": "RESTORATION", "kind": "restoration",
                "granularity": "json_leaf", "leaf_path": leaf_path})
        # Compose only recorded operations. This is a lexical coverage check,
        # never a diff that invents new transformations or PII substrings.
        pieces = []
        cursor = 0
        for one in sorted(self.replacements, key=lambda item: item["source_start"]):
            pieces.extend((source[cursor:one["source_start"]],
                           output[one["output_start"]:one["output_end"]]))
            cursor = one["source_end"]
        pieces.append(source[cursor:])
        if "".join(pieces) != output:
            self.limit("json_serialization_normalized" if self.semantic_complete
                       else "json_lexical_changes_unaccounted", semantic=False)


class RestorationInspection:
    """One opt-in execution request. Metadata contains no restored raw values."""
    def __init__(self, request_id: str) -> None:
        self.request_id = request_id
        self.receipt_id = uuid.uuid4().hex
        self.fields: list[RestorationField] = []

    def field(self, path: str) -> RestorationField:
        field = RestorationField(path)
        self.fields.append(field)
        return field

    def payload(self, conversation_id: str, pseudonym_scope: str) -> dict[str, object]:
        replacements = []
        for field in self.fields:
            for index, one in enumerate(field.replacements):
                identity = f"{self.receipt_id}\x00{field.path}\x00{index}"
                replacements.append({
                    "occurrence_id": hashlib.sha256(identity.encode()).hexdigest()[:32],
                    "path": field.path, **one})
        return {
            "version": 2, "operation": "restore", "request_id": self.request_id,
            "receipt_id": self.receipt_id, "conversation_id": conversation_id,
            "pseudonym_scope": pseudonym_scope, "offset_unit": "unicode_codepoint",
            "coverage": "semantic_transformations",
            "semantic_complete": all(one.semantic_complete for one in self.fields),
            "lexical_complete": all(one.lexical_complete for one in self.fields),
            "limitations": [{"path": one.path, "reason": reason}
                            for one in self.fields for reason in one.limitations],
            "replacements": replacements}
