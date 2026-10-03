"""Pure artifact contracts. Paths are relative to their immutable commit directory."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath
import re
from typing import Any, Mapping

from .messages import ContractError

CONTRACT_SET = "qcl-negf.results.v1"
COMMIT_SCHEMA = "qcl-negf.artifact-commit.v2"
POINTER_SCHEMA = "qcl-negf.artifact-pointer.v2"
EXPORT_SCHEMA = "qcl-negf.science-export.v3"
EXPORT_TRANSPORT_SCHEMA = "qcl-negf.export-archive.v1"
DIAGNOSTIC_EXPORT_SCHEMA = "qcl-negf.operational-evidence.v2"
NATIVE_SCHEMA_VERSION = "4.0"
MODEL_SCHEMA = "qcl-negf-resolved-configuration-v3"
RECOVERY_SCHEMA = "qcl-negf-recovery-reference-v1"
PROGRESS_SCHEMA = "qcl-negf-execution-progress-v1"
PERFORMANCE_SCHEMA = "qcl-negf.performance.v2"
# Scientific payload versions are independent of their immutable JSON containers.
# An explicit declaration prevents old native files from passing an index-only read.
ARTIFACT_SCHEMA_CONTRACTS = {
    ("model", "application/json"): frozenset({MODEL_SCHEMA}),
    ("recovery", "application/x-hdf5"): frozenset({"qcl-negf-checkpoint-v4"}),
    ("recovery", "application/json"): frozenset({RECOVERY_SCHEMA}),
    ("execution.progress", "application/json"): frozenset({PROGRESS_SCHEMA}),
    ("physics.full", "application/x-hdf5"): frozenset({"qcl-negf-physics-v4"}),
    ("physics.analysis", "application/x-hdf5"): frozenset({
        "qcl-negf-physics-analysis-v4", "qcl-negf-optical-v4"}),
    ("science.history", "application/x-hdf5"): frozenset({"qcl-negf-scientific-history-v4"}),
    ("science.comparison", "application/json"): frozenset({
        "qcl-negf-operator-diagnostics-v4"}),
}
SCHEMA_BOUND_ROLES = frozenset(role for role, _ in ARTIFACT_SCHEMA_CONTRACTS)
# Legacy multipart read/verification only. New exports have no archive byte cap.
EXPORT_PART_MAX_BYTES = 200_000_000
SCIENCE_MAX_BYTES = EXPORT_PART_MAX_BYTES
SCIENCE_ROLES = frozenset({"physics.analysis", "science.history", "performance.summary",
                           "performance.window", "model", "plan", "science.comparison"})
FULL_ROLES = SCIENCE_ROLES | {"physics.full", "recovery", "performance.full", "control.state", "execution.progress"}
MEDIA_TYPES = frozenset({"application/x-hdf5", "application/vnd.apache.parquet",
                         "application/json", "text/plain", "text/markdown"})


def require_contract_set(value: Mapping[str, Any]) -> None:
    """Reject incompatible result contracts before touching their payloads."""
    if value.get("contract_set") != CONTRACT_SET:
        raise ContractError(f"unsupported result contract set: requires {CONTRACT_SET}",
                            "incompatible_contract")


def relative_path(value: object) -> str:
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        raise ContractError("artifact path must be a nonempty POSIX relative path", "corrupt_result")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in value.split("/")):
        raise ContractError("artifact path escapes its commit", "corrupt_result")
    return value


def digest_value(value: object) -> str:
    if not isinstance(value, str) or not re.fullmatch("[0-9a-f]{64}", value):
        raise ContractError("artifact SHA256 is invalid", "corrupt_result")
    return value


def validate_export_receipt(value: Mapping[str, Any]) -> Mapping[str, Any]:
    """Validate the identity of one finalized archive, without a size ceiling.

    The receipt establishes transport identity, never scientific acceptance.
    Legacy multipart receipts are consumed by their independent legacy reader.
    """
    require_contract_set(value)
    if value.get("schema") not in {EXPORT_SCHEMA, DIAGNOSTIC_EXPORT_SCHEMA}:
        raise ContractError("unsupported export receipt schema", "incompatible_contract")
    if value.get("transport_schema") != EXPORT_TRANSPORT_SCHEMA:
        raise ContractError("unsupported export transport schema", "incompatible_contract")
    profile = value.get("profile")
    if profile not in {"science", "full-state", "diagnostic"} or (
        (value["schema"] == DIAGNOSTIC_EXPORT_SCHEMA) != (profile == "diagnostic")
    ):
        raise ContractError("export receipt profile is invalid", "corrupt_result")
    digest_value(value.get("sha256"))
    digest_value(value.get("snapshot_identity"))
    size = value.get("bytes")
    if not isinstance(size, int) or isinstance(size, bool) or size < 0:
        raise ContractError("export archive byte length is invalid", "corrupt_result")
    for key in ("filename", "archive"):
        name = relative_path(value.get(key))
        if "/" in name or not name.endswith(".tar.xz") or any(ord(char) < 32 or ord(char) == 127 for char in name):
            raise ContractError("export archive filename is invalid", "corrupt_result")
    if any(key in value for key in ("parts", "multipart", "part_count", "maximum_part_bytes")):
        raise ContractError("single archive receipt cannot describe multipart output", "corrupt_result")
    return value


@dataclass(frozen=True)
class Artifact:
    path: str
    role: str
    size: int
    sha256: str
    media_type: str
    profile: str
    dependencies: tuple[str, ...] = ()
    schema: str | None = None

    @classmethod
    def parse(cls, value: Mapping[str, Any]) -> "Artifact":
        size = value.get("bytes")
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            raise ContractError("artifact byte length is invalid", "corrupt_result")
        role, media, profile = value.get("role"), value.get("media_type"), value.get("profile")
        if not isinstance(role, str) or not role:
            raise ContractError("artifact role is missing", "corrupt_result")
        if not isinstance(media, str) or not media:
            raise ContractError("artifact media type is missing", "corrupt_result")
        if profile not in {"science", "full-state", "both", "local"}:
            raise ContractError("artifact export profile is invalid", "corrupt_result")
        if profile != "local" and role not in FULL_ROLES:
            raise ContractError(f"unknown export artifact role: {role}", "incompatible_contract")
        if profile != "local" and media not in MEDIA_TYPES:
            raise ContractError(f"unknown export artifact media type: {media}", "incompatible_contract")
        schema = value.get("schema")
        if schema is not None and not isinstance(schema, str):
            raise ContractError("artifact schema must be a string", "corrupt_result")
        if role in SCHEMA_BOUND_ROLES and schema not in ARTIFACT_SCHEMA_CONTRACTS.get((role, media), ()):
            raise ContractError(
                f"unsupported or missing native artifact schema for {role}: {schema!r}",
                "incompatible_contract",
            )
        deps = value.get("dependencies", [])
        if not isinstance(deps, list):
            raise ContractError("artifact dependencies must be a list", "corrupt_result")
        return cls(relative_path(value.get("path")), role, size, digest_value(value.get("sha256")),
                   media, profile, tuple(relative_path(item) for item in deps), schema)

    def included(self, profile: str) -> bool:
        roles = SCIENCE_ROLES if profile == "science" else FULL_ROLES
        return self.role in roles and self.profile != "local" and (
            profile == "full-state" or self.profile in {"science", "both"})


def validate_commit(value: Mapping[str, Any]) -> tuple[Artifact, ...]:
    require_contract_set(value)
    if value.get("schema") != COMMIT_SCHEMA:
        raise ContractError("unsupported artifact commit schema", "incompatible_contract")
    if not isinstance(value.get("identity"), dict):
        raise ContractError("artifact identity is missing", "corrupt_result")
    if "state_id" in value or "state_sequence" in value:
        state_id, sequence = value.get("state_id"), value.get("state_sequence")
        if (not isinstance(state_id, str) or not state_id or type(sequence) is not int
                or sequence < 1 or value["identity"].get("state_id") != state_id
                or value["identity"].get("state_sequence") != sequence):
            raise ContractError("commit state identity is invalid or conflicting", "corrupt_result")
    generation = value.get("generation")
    if not isinstance(generation, (int, str)) or isinstance(generation, bool):
        raise ContractError("artifact generation is missing", "corrupt_result")
    rows = value.get("artifacts")
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise ContractError("artifact inventory must be objects", "corrupt_result")
    artifacts = tuple(Artifact.parse(row) for row in rows)
    for row in rows:
        if "identity" in row and row["identity"] != value["identity"]:
            raise ContractError("artifact state identity differs from its commit", "corrupt_result")
    paths = {item.path for item in artifacts}
    if len(paths) != len(artifacts):
        raise ContractError("duplicate artifact paths", "corrupt_result")
    for artifact in artifacts:
        if any(dependency not in paths for dependency in artifact.dependencies):
            raise ContractError("artifact dependency is absent from commit", "corrupt_result")
    return artifacts


def validate_execution_progress(value: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    """Validate portable prior-final references; callers verify referenced bytes."""
    require_contract_set(value)
    if value.get("schema") != PROGRESS_SCHEMA:
        raise ContractError("unsupported execution progress schema", "incompatible_contract")
    identity = value.get("identity")
    if (not isinstance(identity, dict) or not value.get("execution_id")
            or identity.get("execution_id") != value["execution_id"]
            or identity.get("point_id") != value.get("active_point_id")):
        raise ContractError("execution progress identity differs", "corrupt_result")
    digest_value(value.get("plan_fingerprint"))
    rows = value.get("completed_points")
    if not isinstance(rows, list):
        raise ContractError("execution progress requires completed point inventory", "corrupt_result")
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("point"), dict):
            raise ContractError("invalid completed point record", "corrupt_result")
        path = relative_path(row.get("final_commit"))
        if not path.endswith("/commit.json") or path in seen:
            raise ContractError("invalid or duplicated prior final commit", "corrupt_result")
        seen.add(path)
        receipt = row.get("receipt")
        if (not isinstance(receipt, dict) or not isinstance(receipt.get("identity"), dict)
                or receipt["identity"].get("execution_id") != value["execution_id"]
                or not isinstance(receipt.get("state_id"), str) or not receipt["state_id"]
                or type(receipt.get("state_sequence")) is not int or receipt["state_sequence"] < 1):
            raise ContractError("invalid prior final receipt identity", "corrupt_result")
        digest_value(receipt.get("commit_sha256"))
        prior_identity = receipt["identity"]
        point_id = prior_identity.get("point_id")
        if (not isinstance(point_id, str) or not point_id or point_id == value["active_point_id"]
                or path != f"{value['execution_id']}/{point_id}/final/commit.json"
                or ("plan_fingerprint" in prior_identity and
                    prior_identity["plan_fingerprint"] != value["plan_fingerprint"])):
            raise ContractError("prior final ownership differs from progress", "corrupt_result")
        for field in ("state_id", "state_sequence"):
            if field in prior_identity and prior_identity[field] != receipt[field]:
                raise ContractError("prior final state coordinates differ", "corrupt_result")
        files = row.get("files")
        if not isinstance(files, list) or not files:
            raise ContractError("prior final dependencies are absent", "corrupt_result")
        paths: set[str] = set()
        for item in files:
            if not isinstance(item, dict):
                raise ContractError("invalid prior final dependency", "corrupt_result")
            name = relative_path(item.get("path"))
            if name in paths or type(item.get("bytes")) is not int or item["bytes"] < 0:
                raise ContractError("invalid prior final dependency size or ownership", "corrupt_result")
            paths.add(name)
            digest_value(item.get("sha256"))
    return tuple(rows)
