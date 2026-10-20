"""Private DOC07 bindings over finite, schema-valid documents and detached evidence.

The caller owns IO, child selection, finite/C1 validation, and the association of
an opaque review receipt with its reviewed source and recipe. These routines
verify exact bytes and relationships; they never import targets, read files,
fetch locators, convert units, infer scientific origin, or mutate their inputs.
The retained argument is the internal owner layout documented by the DOC07 C2
fixtures, not a public receipt, registry, or capture interface.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
from html.parser import HTMLParser
import re
from urllib.parse import unquote, urlsplit

from .messages import ContractError, MAX_MESSAGE_BYTES, MAX_PLAN_BYTES, decode, encode


_MIB = 1024 * 1024
_LOCAL_FIELDS = ("plan_fingerprint", "scientific_fingerprint", "model_revision",
                 "execution_id", "point_id", "attempt", "configuration_hash")
_FORMATS = {
    "qcl-negf.docs-bundle.v1": "bundle",
    "qcl-negf.model-help-fragment.v1": "fragment",
    "qcl-negf.model-help-view.v1": "view",
    "qcl-negf.model-help-inputs.v1": "snapshot",
    "qcl-negf.model-help-index.v1": "index",
}


class _MissingProof(Exception):
    """Unavailable evidence, distinct from contradictory retained evidence."""


def _require(condition, message):
    if not condition:
        raise ContractError("model help: " + message)


def _equal(left, right):
    """JSON equality with Boolean distinct from numeric, without conversion."""
    if isinstance(left, bool) or isinstance(right, bool):
        return type(left) is type(right) and left == right
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return left == right
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(_equal(left[k], right[k]) for k in left)
    if isinstance(left, list):
        return len(left) == len(right) and all(_equal(a, b) for a, b in zip(left, right))
    return left == right


def _hash(payload):
    return hashlib.sha256(payload).hexdigest()


def _bytes(record, maximum=MAX_MESSAGE_BYTES):
    if record is None:
        raise _MissingProof("missing byte record")
    _require(isinstance(record, dict) and isinstance(record.get("bytes"), bytes),
             "detached evidence must contain exact bytes")
    payload = record["bytes"]
    _require(len(payload) <= maximum, "retained bytes exceed their budget")
    _require(record.get("sha256") == _hash(payload), "retained byte digest mismatch")
    return payload


def _keyed(rows, key, description):
    result = {}
    for row in rows:
        identity = key(row) if callable(key) else row[key]
        _require(identity not in result, "duplicate " + description)
        result[identity] = row
    return result


def _pointer(value, pointer):
    _require(isinstance(pointer, str) and (not pointer or pointer.startswith("/")),
             "invalid evidence pointer")
    if not pointer:
        return value
    for encoded in pointer[1:].split("/"):
        _require(re.search(r"~(?![01])", encoded) is None, "invalid pointer escape")
        part = encoded.replace("~1", "/").replace("~0", "~")
        if isinstance(value, dict):
            _require(part in value, "evidence selector is absent")
            value = value[part]
        elif isinstance(value, list):
            _require(part.isascii() and part.isdecimal() and (part == "0" or not part.startswith("0")),
                     "invalid array pointer")
            index = int(part)
            _require(index < len(value), "evidence array selector is absent")
            value = value[index]
        else:
            raise ContractError("model help: selector traverses a scalar")
    return value


def _escape(value):
    return value.replace("~", "~0").replace("/", "~1")


def _path(value):
    """Reject unsafe spelling; never normalize an unsafe path into a public one."""
    _require(isinstance(value, str) and bool(value), "missing relative path")
    current = value
    while True:
        _require(not current.startswith("/") and "\\" not in current and
                 re.match(r"^[A-Za-z]:/", current) is None,
                 "absolute or backslash path")
        _require(not any(ord(char) < 32 or 127 <= ord(char) <= 159 for char in current),
                 "control character in path")
        parts = current.split("/")
        _require(all(part and not part.startswith(".") for part in parts),
                 "unsafe path component")
        decoded = unquote(current, errors="strict")
        if decoded == current:
            return value
        current = decoded


def _uri(uri):
    _require(isinstance(uri, str) and not any(ord(c) <= 32 or 127 <= ord(c) <= 159 for c in uri),
             "control or space in public locator")
    _require("?" not in uri, "query-bearing public locator")
    decoded = unquote(uri, errors="strict")
    _require(not any(ord(c) < 32 or 127 <= ord(c) <= 159 for c in decoded),
             "encoded control character in public locator")
    try:
        parsed = urlsplit(uri)
        _require(parsed.scheme in {"https", "doi"}, "unsupported public locator scheme")
        _require(parsed.username is None and parsed.password is None, "credentials in public locator")
        if parsed.scheme == "https":
            _require(bool(parsed.netloc) and bool(parsed.hostname), "nonabsolute https locator")
            parsed.port  # Invalid port/bracket spellings are rejected by urllib.
        else:
            _require(bool(parsed.path) and not parsed.netloc, "invalid DOI locator")
    except ValueError as error:
        raise ContractError("model help: malformed public locator") from error


class _Anchors(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.identifiers = set()

    def handle_starttag(self, tag, attrs):
        for key, value in attrs:
            if key == "id" and value is not None:
                self.identifiers.add(value)


def _html_ids(payload):
    try:
        parser = _Anchors()
        parser.feed(payload.decode("utf-8"))
        parser.close()
        return parser.identifiers
    except (UnicodeError, ValueError) as error:
        raise ContractError("model help: invalid retained HTML") from error


class _Evidence:
    def __init__(self, retained):
        _require(isinstance(retained, dict), "detached retained inputs are required")
        self.retained = retained
        self.selection = retained.get("selection", {})
        self.context = self.selection.get("context", {})
        self.cache = {}
        # A corrupt supplied record is not silently reclassified as absent.
        for name, record in retained.get("metadata", {}).items():
            self.metadata(name)

    def record(self, name, maximum):
        record = self.retained.get(name)
        payload = _bytes(record, maximum)
        key = ("document", name)
        if key not in self.cache:
            self.cache[key] = decode(payload, maximum=maximum)
        return self.cache[key]

    def metadata(self, name):
        record = self.retained.get("metadata", {}).get(name)
        if record is None:
            raise _MissingProof("missing " + name)
        maximum = MAX_PLAN_BYTES if name == "frozen_plan" else (
            64 * 1024 if name == "execution_input" else MAX_MESSAGE_BYTES)
        payload = _bytes(record, maximum)
        key = ("metadata", name)
        if key not in self.cache:
            self.cache[key] = decode(payload, maximum=maximum)
        return self.cache[key]

    def graph(self):
        graph = self.selection.get("sources")
        if graph is None:
            raise _MissingProof("selected source graph is missing")
        _require(graph.get("format") == "qcl-negf.git-graph.v1", "unsupported selected graph")
        rows = graph["components"]
        _keyed(rows, "path", "source component")
        _require([row["path"] for row in rows] == sorted(row["path"] for row in rows),
                 "source graph is not sorted")
        for row in rows:
            _path(row["path"])
        return graph

    def source_base(self, reference):
        graph = self.graph()
        revisions = {row["path"]: row["revision"] for row in graph["components"]}
        revisions["root"] = graph["revision"]
        component, path = reference["component"], _path(reference["path"])
        _require(component in revisions, "source owner is outside selected graph")
        _require(reference["revision"] == revisions[component], "source revision mismatch")
        _require((component, path) in self.retained.get("input_allowlist", ()),
                 "source is outside recipe input allowlist")
        record = self.retained.get("sources", {}).get((component, path))
        if record is None:
            raise _MissingProof("public source bytes are missing")
        _require(record.get("revision") == revisions[component], "retained source owner mismatch")
        payload = record.get("bytes")
        _require(isinstance(payload, bytes) and len(payload) <= MAX_MESSAGE_BYTES,
                 "source bytes are not bounded")
        _require(_hash(payload) == reference["sha256"], "public source hash mismatch")
        return payload

    def review(self, reference):
        bundle = self.record("bundle", 2 * _MIB)
        recipes = bundle["generator"]["recipes"]
        source_file = {**reference, "selector": {"kind": "file", "value": ""}}
        for review in self.retained.get("public_reviews", ()):
            if not _equal(review.get("source"), source_file):
                continue
            if not any(_equal(review.get("recipe"), recipe) for recipe in recipes):
                continue
            self.source_base(review["recipe"])
            _bytes(review.get("receipt"))  # Opaque owning review; no invented receipt parser.
            return
        raise _MissingProof("exact owning public-source review association is missing")

    def source(self, reference):
        payload = self.source_base(reference)
        selector = reference["selector"]
        selector_key = (reference["component"], reference["path"], selector["kind"], selector["value"])
        _require(selector_key in self.retained.get("selector_allowlist", ()),
                 "source selector is outside reviewed allowlist")
        self.review(reference)
        if selector["kind"] == "file":
            return payload
        if selector["kind"] == "json_pointer":
            return _pointer(decode(payload), selector["value"])
        try:
            text = payload.decode("utf-8")
        except UnicodeError as error:
            raise ContractError("model help: source text is not UTF-8") from error
        if selector["kind"] == "anchor":
            exists = selector["value"] in _html_ids(payload) or ("{#" + selector["value"] + "}") in text
            _require(exists, "authored source anchor is absent")
        else:
            # The owning extraction allowlist provides the source-verified symbol;
            # this byte-existence guard does not evaluate or import target code.
            _require(selector["value"] in text, "authored source symbol is absent")
        return payload

    def evidence(self, item):
        record = self.retained.get("metadata", {}).get(item["container"])
        if record is None:
            raise _MissingProof("evidence container is missing")
        document = self.metadata(item["container"])
        _require(item["sha256"] == record["sha256"], "evidence digest mismatch")
        return _pointer(document, item["selector"])

    def make_evidence(self, container, selector):
        self.metadata(container)
        return {"container": container,
                "sha256": self.retained["metadata"][container]["sha256"], "selector": selector}

    def point_configuration(self, execution_id=None, point_id=None):
        """Exact frozen passport and pointer, without choosing an endpoint sibling.

        Optional point_passports maps (execution_id, point_id) to Evidence into
        the original frozen plan. It is an in-memory owner projection, not a new
        public format. The key, actual point membership, pointer, and bytes must
        all agree; a sibling's matching numeric value cannot substitute.
        """
        execution_id = self.context.get("execution_id") if execution_id is None else execution_id
        point_id = self.context.get("point_id") if point_id is None else point_id
        plan = self.metadata("frozen_plan")
        points = plan.get("points")
        if points is not None:
            indexed = _keyed(points, lambda row: (row["execution_id"], row["id"]), "frozen point")
            _require((execution_id, point_id) in indexed, "point is not a member of frozen execution")
            position = next(i for i, row in enumerate(points)
                            if row["execution_id"] == execution_id and row["id"] == point_id)
            expected = self.make_evidence("frozen_plan", f"/points/{position}/configuration")
            supplied = self.retained.get("point_passports", {}).get((execution_id, point_id))
            if supplied is None:
                raise _MissingProof("point passport association is missing")
            _require(_equal(supplied, expected), "point passport is associated with another frozen leaf")
            configuration = self.evidence(supplied)
            _require(isinstance(configuration, dict), "point passport is not a configuration object")
            return configuration, expected["selector"]
        _require((execution_id, point_id) == (self.context.get("execution_id"), self.context.get("point_id")),
                 "point is outside the single frozen passport")
        configuration = plan.get("point", {}).get("configuration")
        if configuration is None:
            raise _MissingProof("frozen point passport is missing")
        return configuration, "/point/configuration"

    def local_context(self, context, *, index_point=False):
        fields = tuple(key for key in _LOCAL_FIELDS if not (index_point and key in {"point_id", "configuration_hash"}))
        _require(all(_equal(context.get(key), self.context.get(key)) for key in fields),
                 "local context differs from selected child")
        try:
            plan = self.metadata("frozen_plan")
        except _MissingProof:
            # The owning selected context remains authoritative. Missing plan
            # bytes cannot turn known snapshot data into a guessed mismatch;
            # operations needing declared/last-assignment proof still require it.
            return
        frozen = self.retained["metadata"]["frozen_plan"]
        _require(context["plan_fingerprint"] == plan.get("fingerprint", frozen["sha256"]),
                 "frozen plan fingerprint mismatch")
        try:
            configuration, _ = self.point_configuration(context["execution_id"], context["point_id"])
        except _MissingProof:
            # Unknown declared leaves do not acquire values from absent passport
            # proof; exact selected context remains an owning input.
            return
        _require(context["configuration_hash"] == _hash(encode(configuration)),
                 "declared point passport digest mismatch")

    def snapshot(self):
        snapshot = self.metadata("execution_input")
        _require(snapshot.get("format") == "qcl-negf.model-help-inputs.v1", "unsupported input snapshot")
        self.local_context(snapshot["context"])
        _keyed(snapshot["inputs"], "path", "snapshot input path")
        _keyed(snapshot["origin_bindings"], lambda claim: (claim["reference_id"], claim["phase"]),
               "snapshot origin claim")
        return snapshot

    def scalar(self, path, phase):
        if phase == "declared":
            configuration, pointer = self.point_configuration()
            if path not in configuration:
                return None, None
            return configuration[path], self.make_evidence(
                "frozen_plan", pointer + "/" + _escape(path))
        snapshot = self.snapshot()
        for index, item in enumerate(snapshot["inputs"]):
            if item["path"] == path:
                state = item["used"]
                if state["status"] != "known":
                    return None, None
                return state["atom"], self.make_evidence("execution_input", f"/inputs/{index}/used/atom")
        return None, None

    def publication(self, bundle):
        graph = self.graph()
        manifest = self.record("release_manifest", MAX_MESSAGE_BYTES)
        _require(manifest.get("format") == "qcl-negf.release.v2", "unsupported release manifest")
        _require(_equal(manifest["sources"], graph), "release source graph mismatch")
        receipt = self.metadata("release_receipt")
        _require(_equal(receipt.get("context"), self.context), "release receipt belongs to another child")
        _require(receipt.get("release_id") == self.selection.get("release_id"), "retained release id mismatch")
        _require(receipt.get("release_manifest_sha256") == self.retained["release_manifest"]["sha256"],
                 "release manifest digest mismatch")
        _require(receipt.get("source_revision") == graph["revision"], "publication source revision mismatch")
        _require(receipt.get("bundle_sha256") == self.retained["bundle"]["sha256"],
                 "publication bundle digest mismatch")
        _require(_equal(bundle["sources"], graph), "bundle source graph mismatch")
        return receipt

    def mapping(self):
        """Only retained manifest/fragment/release proof authorizes a public slice.

        Public HTML may be unserved. It is deliberately not needed to retain an
        already verified used scalar under an unavailable documentation status.
        """
        bundle = self.record("bundle", 2 * _MIB)
        fragment = self.record("fragment", 32 * 1024)
        _require(bundle.get("format") == "qcl-negf.docs-bundle.v1", "unsupported retained bundle")
        _require(fragment.get("format") == "qcl-negf.model-help-fragment.v1", "unsupported retained fragment")
        self.publication(bundle)
        _require(fragment["source_revision"] == self.graph()["revision"], "fragment source revision mismatch")
        requested = self.selection.get("fragment_id")
        _require(fragment["id"] == requested, "fragment differs from requested id")
        descriptors = _keyed(bundle["fragments"], "id", "fragment descriptor id")
        _keyed(bundle["fragments"], "file", "fragment descriptor path")
        files = _keyed(bundle["files"], "path", "payload path")
        _require(requested in descriptors, "requested fragment descriptor is missing")
        descriptor = descriptors[requested]
        expected_path = "help/fragments/" + requested + ".json"
        _require(descriptor["file"] == expected_path, "fragment descriptor path mismatch")
        _require(expected_path in files, "fragment is outside payload inventory")
        _require(descriptor["sha256"] == self.retained["fragment"]["sha256"], "fragment descriptor digest mismatch")
        item = files[expected_path]
        _require(item["media_type"] == "application/json", "fragment media type mismatch")
        _require(item["sha256"] == descriptor["sha256"] and
                 item["bytes"] == len(self.retained["fragment"]["bytes"]), "fragment inventory mismatch")
        _require(expected_path in self.retained.get("output_allowlist", ()), "fragment output is not allowlisted")
        # Original fragment bytes can be retained even when their serving tree is absent.
        supplied = self.retained.get("payload", {}).get(expected_path)
        if supplied is not None:
            _require(supplied.get("kind") == "file" and supplied.get("bytes") == self.retained["fragment"]["bytes"],
                     "retained fragment payload mismatch")
        _keyed(fragment["inputs"], "path", "fragment input path")
        _keyed(fragment["inputs"], lambda item: item["reference_value_origin"]["id"], "reference id")
        return fragment

    def candidate_path(self, reference):
        # Candidate data here chooses no public projection and is never enough for
        # bound. Missing graph proof is diagnosed after absent-claim precedence.
        fragment = self.record("fragment", 32 * 1024)
        _keyed(fragment["inputs"], "path", "fragment input path")
        rows = [item for item in fragment["inputs"]
                if item["reference_value_origin"]["id"] == reference["id"]]
        _require(len(rows) <= 1, "ambiguous reference id")
        if not rows:
            raise _MissingProof("reference is outside retained fragment")
        _require(_equal(rows[0]["reference_value_origin"], reference), "reference differs from retained authored bytes")
        return rows[0]["path"]

    def requirements(self, path):
        reference = self.retained.get("effective_requirements")
        if reference is None:
            raise _MissingProof("owning causal step universe is missing")
        rows = self.source(reference)
        _require(isinstance(rows, dict), "owning causal requirements are not a mapping")
        if path not in rows:
            raise _MissingProof("owning causal steps are unspecified for this leaf")
        locations = rows[path]
        _require(isinstance(locations, list), "owning causal steps are not a list")
        keyed = _keyed(locations, lambda item: (item["container"], item["selector"]), "owning causal step")
        for container, selector in keyed:
            self.evidence(self.make_evidence(container, selector))
        return set(keyed)


def _atom_source(atom, value):
    # Producers own normalization. An already normalized Atom can be checked in
    # full; a public scalar leaf is checked without manufacturing a unit/kind.
    if isinstance(value, dict) and {"kind", "value", "unit"} <= value.keys():
        _require(_equal(atom, value), "reference Atom differs from public parameter bytes")
    else:
        _require(_equal(atom["value"], value), "reference scalar differs from public parameter bytes")


def _origin(origin):
    for locator in origin["locators"]:
        _uri(locator["uri"])


def _reference(reference, session):
    _keyed(reference["applicability"]["conditions"], "id", "applicability condition id")
    _origin(reference["origin"])
    _atom_source(reference["atom"], session.source(reference["parameter"]))
    for condition in reference["applicability"]["conditions"]:
        session.source(condition["source"])


def _unknown(reason):
    notes = {
        "value_unavailable": "The selected phase value is unavailable in retained metadata.",
        "override_unbound": "The selected assignment or override lacks the exact last-source binding.",
        "conditions_unbound": "Scientific applicability conditions are not all bound to the selected phase.",
        "origin_not_recorded": "No retained origin claim was supplied for this selected value and phase.",
        "source_unbound": "Selected source bytes, graph, or retained source bindings are unavailable.",
    }
    return {"status": "unknown", "origin": {"status": "unknown", "kind": "unknown",
            "locators": [], "note": notes[reason]}, "binding": None, "reason": reason}


def _claim_preflight(reference, claim, phase, session):
    """Contradiction precedes all missing-proof reasons (D2 R2)."""
    if claim is None:
        return
    _require(claim["reference_id"] == reference["id"], "claim reference id mismatch")
    _require(claim["phase"] == phase, "origin claim belongs to another phase")
    _require(claim["annotation"]["component"] == "components/qcl-negf-research",
             "value-origin annotation is outside its Research owner")
    _require(_equal(claim["parameter"], reference["parameter"]), "claim public parameter mismatch")
    _keyed(claim["conditions"], "id", "claim condition id")
    receipt = claim["assignment_receipt"]
    _require(receipt["source_sha256"] == receipt["source"]["sha256"], "assignment receipt source digest mismatch")
    for key in ("plan_fingerprint", "execution_id", "point_id", "attempt"):
        _require(_equal(receipt[key], session.context.get(key)), "origin claim selected context mismatch")
    for source in (claim["annotation"], claim["parameter"], receipt["source"]):
        try:
            session.source_base(source)
        except _MissingProof:
            pass  # Absence is diagnosed in the specified order below.
    for container, key in (("value_origin_receipt", "claims"), ("execution_input", "origin_bindings")):
        try:
            document = session.metadata(container)
        except _MissingProof:
            continue
        if container == "execution_input":
            session.snapshot()
        rows = document.get(key, [])
        indexed = _keyed(rows, lambda item: (item["reference_id"], item["phase"]), "retained origin claim")
        stored = indexed.get((reference["id"], phase))
        if stored is not None:
            _require(_equal(stored, claim), "supplied claim contradicts retained claim bytes")


def _retained_claim(claim, session):
    if claim is None:
        return None
    try:
        document = session.metadata("value_origin_receipt")
        snapshot = session.snapshot()
    except _MissingProof:
        return None
    if not any(_equal(stored, claim) for stored in snapshot["origin_bindings"]):
        return None
    for index, stored in enumerate(document.get("claims", [])):
        if _equal(stored, claim):
            return index
    return None


def _last_assignment(path, phase, session):
    if phase == "declared":
        return session.metadata("frozen_plan").get("assignment")
    snapshot = session.snapshot()
    for item in snapshot["inputs"]:
        if item["path"] == path:
            return item["assigning"]
    return None


def _explicit_override(path, phase, session):
    if phase != "used" or path is None:
        return False
    try:
        snapshot = session.snapshot()
    except _MissingProof:
        return False
    for item in snapshot["inputs"]:
        if item["path"] != path:
            continue
        if item["assigning"]["status"] != "known":
            return True
        return any(step["kind"] == "checkpoint_restore" and step["source"] is None
                   for step in item["effective_origin"]["steps"])
    return False


def _resolve(reference, claim, phase, session):
    _require(phase in {"declared", "used"}, "unsupported origin phase")
    _keyed(reference["applicability"]["conditions"], "id", "applicability condition id")
    _claim_preflight(reference, claim, phase, session)
    try:
        path = session.candidate_path(reference)
    except _MissingProof:
        path = None

    # Explicit inapplicability is an owning statement, not an inference from
    # missing data. Require its retained authored mapping and public source.
    if reference["origin"]["status"] == "not_applicable":
        try:
            session.mapping()
            _reference(reference, session)
        except _MissingProof:
            return _unknown("source_unbound")
        return {"status": "not_applicable", "origin": deepcopy(reference["origin"]),
                "binding": None, "reason": "not_applicable"}

    value, value_evidence = None, None
    try:
        # A missing phase container is actual unavailable data. A missing source
        # mapping is deferred; it cannot invent a comparison or choose a leaf.
        if phase == "used":
            session.snapshot()
        else:
            session.metadata("frozen_plan")
        if path is not None:
            value, value_evidence = session.scalar(path, phase)
            if value_evidence is None:
                return _unknown("value_unavailable")
    except _MissingProof:
        return _unknown("value_unavailable")
    if _explicit_override(path, phase, session):
        return _unknown("override_unbound")

    # Only available, verified comparison inputs may establish earlier mismatch.
    parameter_available = False
    try:
        _atom_source(reference["atom"], session.source(reference["parameter"]))
        parameter_available = True
    except _MissingProof:
        pass
    if parameter_available and value_evidence is not None and not _equal(value, reference["atom"]):
        return _unknown("override_unbound")

    condition_values = {}
    for condition in reference["applicability"]["conditions"]:
        try:
            session.source(condition["source"])
            observed, proof = session.scalar(condition["path"], phase)
        except _MissingProof:
            continue
        if proof is not None:
            if not _equal(observed, condition["atom"]):
                return _unknown("conditions_unbound")
            condition_values[condition["id"]] = proof

    claim_index = _retained_claim(claim, session)
    if claim_index is None:
        return _unknown("origin_not_recorded")
    try:
        fragment = session.mapping()
        _require(path is not None and any(item["path"] == path for item in fragment["inputs"]),
                 "origin target is outside exact retained mapping")
        annotation = session.source(claim["annotation"])
        _require(_equal(annotation, reference), "annotation differs from reference origin bytes")
        _reference(reference, session)
    except _MissingProof:
        return _unknown("source_unbound")

    # The exact last source/leaf/context is a distinct proof from public reference
    # equality. Missing last-assignment proof stays override_unbound.
    receipt = claim["assignment_receipt"]
    try:
        assigning = _last_assignment(path, phase, session)
        assignment_value = session.source(receipt["source"])
        plan_value = _pointer(session.metadata("frozen_plan"), receipt["leaf_pointer"])
    except _MissingProof:
        return _unknown("override_unbound")
    if (assigning is None or assigning.get("status", "known") != "known" or
            not _equal(assigning.get("source"), receipt["source"])):
        return _unknown("override_unbound")
    expected_declared, declared_evidence = session.scalar(path, "declared")
    if declared_evidence is None or receipt["leaf_pointer"] != declared_evidence["selector"]:
        return _unknown("override_unbound")
    if not _equal(plan_value, expected_declared):
        raise ContractError("model help: receipt leaf differs from frozen point value")
    if isinstance(assignment_value, dict) and {"kind", "value", "unit"} <= assignment_value.keys():
        if not _equal(assignment_value, value):
            return _unknown("override_unbound")
    elif not _equal(assignment_value, value["value"]):
        return _unknown("override_unbound")

    expected_conditions = reference["applicability"]["conditions"]
    conditions = _keyed(claim["conditions"], "id", "claim condition id")
    _require(set(conditions) <= {row["id"] for row in expected_conditions}, "claim has an unrelated condition")
    proofs = []
    for condition in expected_conditions:
        binding = conditions.get(condition["id"])
        if (binding is None or binding["phase"] != phase or binding["input_path"] != condition["path"] or
                condition["id"] not in condition_values):
            return _unknown("conditions_unbound")
        proofs.append(condition_values[condition["id"]])
    if reference["applicability"]["status"] != "specified":
        return _unknown("conditions_unbound")
    if reference["origin"]["status"] != "known":
        return _unknown("source_unbound")
    return {"status": "bound", "origin": deepcopy(reference["origin"]), "binding": {
        "reference_id": reference["id"], "annotation": deepcopy(claim["annotation"]),
        "parameter": deepcopy(claim["parameter"]), "phase": phase, "value": value_evidence,
        "assignment": session.make_evidence("value_origin_receipt", f"/claims/{claim_index}/assignment_receipt"),
        "conditions": proofs,
        "receipt": session.make_evidence("value_origin_receipt", f"/claims/{claim_index}")}, "reason": "ok"}


def _payload(path, session, expected=None):
    _path(path)
    _require(path in session.retained.get("output_allowlist", ()), "payload is outside output allowlist")
    payload = session.retained.get("payload", {}).get(path)
    if payload is None:
        raise _MissingProof("public payload is missing")
    _require(payload.get("kind") == "file", "public payload is not a regular file")
    content = payload.get("bytes")
    _require(isinstance(content, bytes), "public payload bytes are absent")
    if expected is not None:
        _require(expected["bytes"] == len(content) and expected["sha256"] == _hash(content),
                 "public inventory size or digest mismatch")
    return content


def _doc(reference, session):
    path = reference["section"] + "/" + reference["path"]
    content = _payload(path, session)
    bundle = session.record("bundle", 2 * _MIB)
    files = _keyed(bundle["files"], "path", "payload path")
    _require(path in files and files[path]["media_type"] == "text/html", "document is outside HTML inventory")
    _payload(path, session, files[path])
    if reference["anchor"] is not None:
        _require(reference["anchor"] in _html_ids(content), "document anchor is absent")
    return content


def _fragment(document, session, *, payload=None):
    graph = session.graph()
    _require(document["source_revision"] == graph["revision"], "static fragment graph mismatch")
    bundle = session.record("bundle", 2 * _MIB)
    _require(_equal(bundle["sources"], graph), "static fragment bundle graph mismatch")
    if payload is None:
        retained_fragment = session.record("fragment", 32 * 1024)
        _require(_equal(document, retained_fragment), "static fragment differs from retained bytes")
        payload = session.retained["fragment"]["bytes"]
    descriptors = _keyed(bundle["fragments"], "id", "fragment descriptor id")
    descriptor = descriptors.get(document["id"])
    _require(descriptor is not None and descriptor["file"] == "help/fragments/" + document["id"] + ".json" and
             descriptor["sha256"] == _hash(payload),
             "static fragment descriptor binding mismatch")
    _keyed(document["inputs"], "path", "fragment input path")
    _keyed(document["inputs"], lambda item: item["reference_value_origin"]["id"], "reference id")
    _keyed(document["api"], "symbol", "API symbol")
    _keyed(document["equations"], "id", "equation id")
    session.source(document["meaning_source"])
    _doc(document["full"], session)
    for reference in document["related"]:
        _doc(reference, session)
    for equation in document["equations"]:
        content = _doc(equation["doc"], session)
        _require(equation["id"] in _html_ids(content), "equation identifier is absent from document")
    for item in document["inputs"]:
        session.source(item["schema_source"])
        _reference(item["reference_value_origin"], session)
        for fact in item["facts"]:
            for source in fact["sources"]:
                session.source(source)
    for api in document["api"]:
        session.source(api["source"])
        _doc(api["doc"], session)
        for fact in api["facts"]:
            for source in fact["sources"]:
                session.source(source)


def _bundle(document, session):
    _require(_equal(document["sources"], session.graph()), "bundle differs from selected graph")
    _require(_equal(document, session.record("bundle", 2 * _MIB)), "bundle differs from retained manifest bytes")
    session.source(document["schema"])
    _require(document["schema"]["component"] == "components/qcl-negf-contracts" and
             document["schema"]["path"] == "src/qcl_negf_contracts/schemas/model-help.schema.json",
             "bundle schema does not reference the owning Contracts resource")
    for source in document["generator"]["recipes"]:
        session.source(source)
    session.source(document["generator"]["toolchain_lock"])
    descriptors = _keyed(document["fragments"], "id", "fragment id")
    _keyed(document["fragments"], "file", "fragment descriptor path")
    files = _keyed(document["files"], "path", "public payload path")
    _require("bundle.json" not in files, "bundle manifest cannot hash itself")
    _require(set(session.retained.get("payload", {})) == set(files), "payload inventory is not complete")
    for path, item in files.items():
        _path(path)
        _require(not path.lower().endswith((".h5", ".hdf5", ".npy", ".npz")), "scientific arrays are not public help payload")
        _payload(path, session, item)
        if path.endswith(".html"):
            _require(item["media_type"] == "text/html", "HTML media type mismatch")
        if path.endswith(".json"):
            _require(item["media_type"] == "application/json", "JSON media type mismatch")
    for identifier, descriptor in descriptors.items():
        path = "help/fragments/" + identifier + ".json"
        _require(descriptor["file"] == path and path in files, "descriptor does not bind its exact fragment path")
        _require(descriptor["sha256"] == files[path]["sha256"], "descriptor differs from file digest")
        _require(files[path]["bytes"] <= 32 * 1024, "fragment exceeds byte budget")
        content = _payload(path, session, files[path])
        fragment = decode(content, maximum=32 * 1024)
        _require(fragment["id"] == identifier and fragment["source_revision"] == document["sources"]["revision"],
                 "payload fragment identity mismatch")
        _fragment(fragment, session, payload=content)
    for alias in document["aliases"]:
        _doc(alias["from"], session)
        _doc(alias["to"], session)


def _snapshot_contents(document, session, *, index_point=False):
    session.local_context(document["context"], index_point=index_point)
    _keyed(document["inputs"], "path", "snapshot input path")
    _keyed(document["origin_bindings"], lambda item: (item["reference_id"], item["phase"]), "origin claim")
    configuration = None
    for item in document["inputs"]:
        if item["declared"]["status"] == "known":
            if configuration is None:
                configuration, _ = session.point_configuration(
                    document["context"]["execution_id"], document["context"]["point_id"])
            _require(item["path"] in configuration and _equal(item["declared"]["atom"], configuration[item["path"]]),
                     "snapshot declared Atom differs from frozen point passport")
    for claim in document["origin_bindings"]:
        _keyed(claim["conditions"], "id", "claim condition id")
        receipt = claim["assignment_receipt"]
        _require(receipt["source_sha256"] == receipt["source"]["sha256"], "snapshot assignment digest mismatch")
        for key in ("plan_fingerprint", "execution_id", "point_id", "attempt"):
            _require(_equal(receipt[key], document["context"][key]), "snapshot claim context mismatch")


def _snapshot(document, session):
    _snapshot_contents(document, session)
    retained = session.snapshot()
    _require(_equal(document, retained), "snapshot differs from retained selected bytes")


def _index(document, session):
    _require(document["complete"], "incomplete index cannot establish trusted input availability")
    _keyed(document["entries"], "path", "index path")
    context = session.context
    plan = session.metadata("frozen_plan")
    count = len(plan.get("points", [plan.get("point")]))
    _require(len(document["entries"]) <= count, "index exceeds frozen point count")
    total = sum(entry["bytes"] for entry in document["entries"])
    _require(total <= 8 * _MIB, "index exceeds aggregate snapshot budget")
    for entry in document["entries"]:
        _path(entry["path"])
        expected = ("result/executions/" + entry["execution_id"] + "/" + entry["point_id"] +
                    "/attempt-" + str(entry["attempt"]) + "/model-help-inputs.json")
        _require(entry["path"] == expected, "index path identity mismatch")
        _require(all(_equal(entry[key], context.get(key)) for key in ("execution_id", "attempt")),
                 "index entry differs from selected execution and child attempt")
        # Index-wide point membership differs from endpoint point selection.
        session.point_configuration(entry["execution_id"], entry["point_id"])
        files = session.retained.get("snapshot_files")
        if files is not None:
            record = files.get(entry["path"])
            if record is None:
                raise _MissingProof("indexed sibling byte record is missing")
            inventory = record.get("inventory")
            _require(isinstance(inventory, dict) and inventory.get("bytes") == entry["bytes"] and
                     inventory.get("sha256") == entry["sha256"], "indexed file differs from owning inventory")
        else:
            _require(entry["point_id"] == context.get("point_id"),
                     "sibling requires its own retained file and passport")
            record = session.retained.get("metadata", {}).get("execution_input")
            if record is None:
                raise _MissingProof("indexed byte record is missing")
        if entry["status"] == "valid":
            content = _bytes(record, 64 * 1024)
            selected_record = session.retained.get("metadata", {}).get("execution_input")
            if entry["point_id"] == context.get("point_id") and selected_record is not None:
                _require(content == _bytes(selected_record, 64 * 1024),
                         "selected snapshot alias differs from indexed original bytes")
            snapshot = decode(content, maximum=64 * 1024)
            _require(entry["sha256"] == record["sha256"] and entry["bytes"] == len(record["bytes"]),
                     "index payload digest or size mismatch")
            _require(entry["bytes"] <= 64 * 1024, "valid snapshot exceeds file budget")
            _require(all(_equal(snapshot["context"][key], entry[key]) for key in ("execution_id", "point_id", "attempt")),
                     "index payload context mismatch")
            _require(snapshot.get("format") == "qcl-negf.model-help-inputs.v1", "unsupported indexed snapshot")
            _snapshot_contents(snapshot, session, index_point=True)
        elif isinstance(record.get("bytes"), bytes):
            content = _bytes(record, 8 * _MIB)
            _require(entry["sha256"] == record["sha256"] and entry["bytes"] == len(content),
                     "invalid indexed payload differs from retained inventory bytes")


def _effective(item, session):
    effective = item["effective_origin"]
    supplied = set()
    for proof in effective["evidence"]:
        session.evidence(proof)
        supplied.add((proof["container"], proof["selector"]))
    if effective["status"] == "known":
        required = session.requirements(item["path"])
        _require(required == supplied, "known effective origin differs from applicable causal selector scope")
    elif effective["evidence"]:
        # Partial evidence is not complete proof, but its emitted selectors must
        # still be among the source-bound applicable planning/runtime locations.
        try:
            required = session.requirements(item["path"])
        except _MissingProof:
            raise _MissingProof("public causal evidence needs an owning selector scope")
        _require(supplied <= required, "causal evidence is outside owning selector scope")


def _assigning(item, session):
    assigning = item["assigning"]
    if assigning["status"] == "unknown":
        return
    if assigning["source"] is not None:
        session.source(assigning["source"])
    if assigning["evidence"] is not None:
        # Provenance availability is independent of emitted numeric availability.
        # A retained runtime assignment stays authoritative even when View.used
        # is conservatively unknown. Only genuine absence allows plan fallback.
        target, runtime_selector = None, None
        try:
            snapshot = session.snapshot()
            for index, leaf in enumerate(snapshot["inputs"]):
                if leaf["path"] == item["path"]:
                    target = leaf["assigning"]
                    runtime_selector = f"/inputs/{index}/assigning"
                    break
        except _MissingProof:
            pass
        if target is None:
            target = _last_assignment(item["path"], "declared", session)
        _require(isinstance(target, dict) and target.get("status", "known") == assigning["status"],
                 "assigning status differs from target leaf's retained assignment")
        for key in ("kind", "rule"):
            _require(_equal(target.get(key), assigning[key]), "assigning projection is not the target's last assignment")
        if assigning["status"] == "known":
            _require(_equal(target.get("source"), assigning["source"]), "target leaf last source mismatch")
        allowed = set()
        if runtime_selector is not None:
            allowed.add(("execution_input", runtime_selector))
        try:
            frozen = session.metadata("frozen_plan").get("assignment")
            declared, proof = session.scalar(item["path"], "declared")
            if (proof is not None and isinstance(frozen, dict) and
                    frozen.get("status", "known") == target.get("status", "known") and all(
                    _equal(frozen.get(key), target.get(key)) for key in ("kind", "rule", "source"))):
                allowed.add(("frozen_plan", "/assignment"))
        except _MissingProof:
            pass
        _require((assigning["evidence"]["container"], assigning["evidence"]["selector"]) in allowed,
                 "assigning evidence is outside target leaf assignment scope")
        source = session.evidence(assigning["evidence"])
        _require(isinstance(source, dict), "assignment evidence does not address an assignment")
        _require(source.get("status", "known") == assigning["status"],
                 "assignment status differs from exact evidence")
        for key in ("kind", "rule"):
            _require(_equal(source.get(key), assigning[key]), "assignment projection differs from retained evidence")
        if assigning["status"] == "known":
            _require(_equal(source.get("source"), assigning["source"]), "last assigning source projection mismatch")
        if assigning["source"] is not None:
            _require(_equal(source.get("source"), assigning["source"]), "public assigning source mismatch")
        # A producer rule is proved by the selected immutable assignment record;
        # it is never inferred from the presence or numeric value of a scalar.
        if assigning["rule"] is not None:
            _require(source.get("rule") == assigning["rule"], "producer rule is not recorded")


def _view(document, session):
    _require(_equal(document["context"], session.context), "View context differs from selected child")
    session.local_context(document["context"])
    binding = document["binding"]
    known = {"release_id": session.selection.get("release_id")}
    try:
        known["source_revision"] = session.graph()["revision"]
    except _MissingProof:
        known["source_revision"] = None
    try:
        retained_receipt = session.metadata("release_receipt")
    except _MissingProof:
        retained_receipt = None
    if retained_receipt is not None:
        _require(_equal(retained_receipt.get("context"), session.context),
                 "retained identity receipt belongs to another selected child")
        _require(retained_receipt.get("release_id") == known["release_id"],
                 "retained identity receipt release mismatch")
        if known["source_revision"] is not None:
            _require(retained_receipt.get("source_revision") == known["source_revision"],
                     "retained identity receipt source mismatch")
        else:
            known["source_revision"] = retained_receipt.get("source_revision")
        for field in ("bundle_sha256", "release_manifest_sha256"):
            known[field] = retained_receipt.get(field)
    for field, record_name, maximum in (("bundle_sha256", "bundle", 2 * _MIB),
                                       ("release_manifest_sha256", "release_manifest", MAX_MESSAGE_BYTES)):
        record = session.retained.get(record_name)
        if record is not None:
            _bytes(record, maximum)
            if known.get(field) is not None:
                _require(known[field] == record["sha256"], "retained identity receipt digest mismatch")
            known[field] = record["sha256"]
        elif field not in known:
            known[field] = None
    for field, value in known.items():
        _require(_equal(binding[field], value), "View retained identity scalar erasure or mismatch")

    try:
        fragment = session.mapping()
    except _MissingProof:
        fragment = None
    if binding["status"] == "bound":
        _require(fragment is not None, "bound documentation lacks retained mapping proof")
        bundle = session.record("bundle", 2 * _MIB)
        _bundle(bundle, session)
        _fragment(fragment, session)
        expected = {"id": fragment["id"], "sha256": session.retained["fragment"]["sha256"],
                    "url": "/docs/" + fragment["source_revision"] + "/help/fragments/" + fragment["id"] + ".json"}
        _require(_equal(document["fragment"], expected), "View fragment descriptor differs from exact retained source")
    if fragment is None:
        _require(not document["inputs"], "input projection has no exact retained mapping")
        mappings = {}
    else:
        mappings = _keyed(fragment["inputs"], "path", "fragment input path")
    _keyed(document["inputs"], "path", "View input path")

    snapshot = None
    try:
        snapshot = session.snapshot()
    except _MissingProof:
        pass
    if document["input_status"]["status"] == "available":
        _require(snapshot is not None, "available input status lacks selected snapshot")
    for item in document["inputs"]:
        _require(item["path"] in mappings, "View input is outside requested fragment mapping")
        for phase in ("declared", "used"):
            state = item[phase]
            if state["status"] != "known":
                continue
            if phase == "used":
                _require(document["input_status"]["status"] == "available", "unavailable snapshot cannot supply used values")
            actual, proof = session.scalar(item["path"], phase)
            _require(proof is not None and _equal(state["atom"], actual), "projected scalar differs from selected phase")
            _require(_equal(state["evidence"], proof), "scalar evidence does not select its exact phase and leaf")
            _require(_equal(session.evidence(state["evidence"]), actual), "scalar evidence value mismatch")
        _assigning(item, session)
        _effective(item, session)
        reference = mappings[item["path"]]["reference_value_origin"]
        for phase in ("declared", "used"):
            view = item["value_origin"][phase]
            if view["status"] == "unknown":
                continue  # Conservative unknowns are never promoted to bound.
            claim = None
            try:
                receipt = session.metadata("value_origin_receipt")
            except _MissingProof:
                receipt = {}
            candidates = [row for row in receipt.get("claims", [])
                          if row["reference_id"] == reference["id"] and row["phase"] == phase]
            _require(len(candidates) <= 1, "ambiguous origin receipt")
            if candidates:
                claim = candidates[0]
            actual = _resolve(reference, claim, phase, session)
            _require(_equal(view, actual), "attempted origin attribution lacks its exact retained proofs")


def _resolve_value_origin(reference, claim, *, phase, retained):
    """Return one exact ValueOriginView; missing proof never fabricates origin.

    D2 R2 ordering: reject contradictions first; explicit inapplicability, missing
    target, proved override, proved condition mismatch, absent claim, missing
    sources, missing last assignment, missing conditions, then bound/ok.
    """
    try:
        return _resolve(reference, claim, phase, _Evidence(retained))
    except _MissingProof:
        return _unknown("source_unbound")
    except (KeyError, IndexError, TypeError, UnicodeError, OverflowError) as error:
        raise ContractError("model help: malformed detached binding evidence") from error


def _validate_model_help_bindings(document, *, retained):
    """Check cross-document proof relationships and return the same input object.

    The caller has already performed finite JSON and C1 schema validation. No
    schema validator is imported here, and no shape-valid status is proof of its
    source, selected child, last assignment, or complete effective causal chain.
    """
    try:
        session = _Evidence(retained)
        branch = _FORMATS.get(document.get("format"))
        _require(branch is not None, "unsupported help format")
        maximum = {"bundle": 2 * _MIB, "fragment": 32 * 1024,
                   "view": 64 * 1024, "snapshot": 64 * 1024, "index": 2 * _MIB}[branch]
        # Existing finite encoder is only a document budget guard, not a schema.
        _require(len(encode(document)) <= maximum, "help document exceeds byte budget")
        {"bundle": _bundle, "fragment": _fragment, "view": _view,
         "snapshot": _snapshot, "index": _index}[branch](document, session)
        return document
    except _MissingProof as error:
        raise ContractError("model help: required retained binding proof is missing") from error
    except (KeyError, IndexError, TypeError, UnicodeError, OverflowError) as error:
        raise ContractError("model help: malformed detached binding evidence") from error
