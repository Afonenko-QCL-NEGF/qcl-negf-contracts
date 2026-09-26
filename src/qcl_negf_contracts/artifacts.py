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
EXPORT_SCHEMA = "qcl-negf.science-export.v2"
NATIVE_SCHEMA_VERSION = "4.0"
MODEL_SCHEMA = "qcl-negf-resolved-configuration-v3"
RECOVERY_SCHEMA = "qcl-negf-recovery-reference-v1"
PERFORMANCE_SCHEMA = "qcl-negf.performance.v2"
# Scientific payload versions are independent of their immutable JSON containers.
# An explicit declaration prevents old native files from passing an index-only read.
ARTIFACT_SCHEMA_CONTRACTS = {
    ("model", "application/json"): frozenset({MODEL_SCHEMA}),
    ("recovery", "application/x-hdf5"): frozenset({"qcl-negf-checkpoint-v4"}),
    ("recovery", "application/json"): frozenset({RECOVERY_SCHEMA}),
    ("physics.full", "application/x-hdf5"): frozenset({"qcl-negf-physics-v4"}),
    ("physics.analysis", "application/x-hdf5"): frozenset({
        "qcl-negf-physics-analysis-v4", "qcl-negf-optical-v4"}),
    ("science.history", "application/x-hdf5"): frozenset({"qcl-negf-scientific-history-v4"}),
    ("science.comparison", "application/json"): frozenset({
        "qcl-negf-operator-diagnostics-v4"}),
}
SCHEMA_BOUND_ROLES = frozenset(role for role, _ in ARTIFACT_SCHEMA_CONTRACTS)
# Decimal bytes: applies to every independently readable export part, all profiles.
EXPORT_PART_MAX_BYTES = 200_000_000
SCIENCE_MAX_BYTES = EXPORT_PART_MAX_BYTES
SCIENCE_ROLES = frozenset({"physics.analysis", "science.history", "performance.summary",
                           "performance.window", "model", "plan", "science.comparison"})
FULL_ROLES = SCIENCE_ROLES | {"physics.full", "recovery", "performance.full", "control.state"}
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
    generation = value.get("generation")
    if not isinstance(generation, (int, str)) or isinstance(generation, bool):
        raise ContractError("artifact generation is missing", "corrupt_result")
    rows = value.get("artifacts")
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise ContractError("artifact inventory must be objects", "corrupt_result")
    artifacts = tuple(Artifact.parse(row) for row in rows)
    paths = {item.path for item in artifacts}
    if len(paths) != len(artifacts):
        raise ContractError("duplicate artifact paths", "corrupt_result")
    for artifact in artifacts:
        if any(dependency not in paths for dependency in artifact.dependencies):
            raise ContractError("artifact dependency is absent from commit", "corrupt_result")
    return artifacts
