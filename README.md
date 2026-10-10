# QCL-NEGF contracts

Versioned, dependency-free Python contracts and JSON Schema resources shared by the QCL-NEGF scientific runner, AiiDA integration and result tools. This package owns scientific data formats; scheduling and machine configuration belong to their respective services.

## Installation

Python 3.14 is supported. From this repository:

```console
uv venv --python 3.14.7
uv pip install '.[test]'
.venv/bin/python -m pytest
uv build
```

The distribution is `qcl-negf-contracts`; its import name is `qcl_negf_contracts`.

```python
from qcl_negf_contracts import load_schema, schema_names
from qcl_negf_contracts.artifacts import CONTRACT_SET, validate_commit
from qcl_negf_contracts.messages import decode, scientific_plan

schema = load_schema("scientific-worker-result.schema.json")
plan = scientific_plan(decode(plan_bytes))
```

`decode` rejects nonfinite numbers, duplicate keys, excessive nesting and payloads above the caller's byte budget. `scientific_plan` checks the envelope, identifiers and point count. It does not replace complete JSON Schema validation or numerical validation.

## Contract ownership

| Resource | Purpose |
| --- | --- |
| `schemas/run.schema.json` | Fully resolved solver configuration |
| `schemas/scientific-definition.schema.json` | Declarative study and meta definitions |
| `schemas/scientific-plan.schema.json` | Frozen scientific plan |
| `schemas/output-policy.schema.json` | Canonical archive/recovery/telemetry settings |
| `schemas/scientific-worker-result.schema.json` | Solver execution results |
| `schemas/results-contract-set.json` | Native and serialized artifact versions |
| `artifacts.py` | Artifact roles, paths, checksums and immutable commit validation |
| `telemetry.py` | Typed fields and units for performance tables |

Schemas are distributed inside the wheel under `qcl_negf_contracts/schemas`; `load_schema(name)` is the supported resource accessor. Install `qcl-negf-contracts[validation]` and call `schema_validator(name).validate(document)` for full offline validation. The adapter registers all bundled schemas for relative `$ref` resolution and performs no network retrieval. Schemas follow JSON Schema 2020-12. `results-contract-set.json` is a registry, not a validation schema.

The result contract is `qcl-negf.results.v1`, native HDF5 layout is `4.0`, and the maximum independently readable export part is 200,000,000 decimal bytes. Readers reject missing or different contract sets. A successful transport or export does not establish scientific acceptance.

The [scientific runner](https://github.com/Afonenko-QCL-NEGF/QCLNEGFRunner.jl) vendors the configuration schema and registry with a checksum manifest so Julia does not need a Python runtime. Changes to a vendored schema require a coordinated runner update.

## Development

Tests check schema validity, reference closure, artifact boundaries and hostile JSON inputs. Public format changes require compatible producer and consumer releases with matching contract declarations. MIT licensed; see [LICENSE](LICENSE).

## Integrated environment

The [qcl-negf](https://github.com/Afonenko-QCL-NEGF/qcl-negf) superproject owns the shared dependency lock. From its root, run `uv sync --locked --all-packages --all-extras --group test`. The package remains independently buildable and testable from its native metadata.

## Export transport

The canonical scientific key is `output`, with `archive`, `recovery` and
`telemetry` sections. `archive.full_final` must be true in this release.
Legacy `outputs` is accepted only as explicit runner migration; specifying both
keys is rejected. Operational retention never certifies scientific quality.
New commits bind `state_id`/`state_sequence` to their identity; progress artifacts
declare prior final receipts and file hashes for portable multi-point recovery.
`validate_execution_progress` checks reference structure, while consumers must
also verify referenced archive bytes.

New `qcl-negf.science-export.v3` and `qcl-negf.operational-evidence.v2` receipts describe one `.tar.xz` using `qcl-negf.export-archive.v1`. `validate_export_receipt` and the bundled `export-receipt.schema.json` check filename confinement, bytes, SHA256, profile and snapshot identity. Bytes have no fixed upper bound. Successful transport does not assert convergence or scientific acceptance. The legacy 200,000,000-byte constants and registry entries apply only to reading archived `qcl-negf.export-parts.v1` sets; new exporters do not generate them.

## Bound branch warnings

```python
from qcl_negf_contracts.messages import branch_reason, ContractError

# All inputs come from the same pinned, decoded publication and frozen plan.
owner = snapshot['points'][0]  # or a row in snapshot['attempt_history']
execution = next(e for e in plan['executions'] if e['id'] == owner['execution_id'])
cause = branch_reason(owner['warnings'][0], plan=plan, owner_point=owner,
                      owner_execution=execution, source_points=snapshot)
```

`branch_reason(record, *, plan, owner_point, owner_execution, source_points)`
is a dependency-free, pure semantic helper returning a detached seven-field
object or `None`. It does not modify inputs or read files. The typed record has
exactly `code`, `scope`, `reason_kind`, `source_execution_id`, `source_point_id`,
`source_attempt`, and `message`. `code` is `BRANCH_STOPPED` or
`DEPENDENCY_UNAVAILABLE`; `scope` is `branch`. The supported reasons are
`process_failure`, `iteration_not_converged`, `physical_gate_failed`,
`interrupted`, `data_unavailable`, `assessment_unavailable`, and `metadata_invalid`.
Source IDs use the existing portable ASCII pattern (1–128 characters); attempt
is a positive integer excluding Boolean. Message is nonempty valid UTF-8,
limited to 2048 encoded bytes.

The caller supplies a fully validated/trusted frozen scientific plan v2 and the
complete immutable series result v3 snapshot with contract set
`qcl-negf.results.v1`, both `points` and `attempt_history` lists, and matching
header identity. The full owner execution must equal the frozen plan entry;
the snapshot uses the existing nine-field execution projection. Owner row and
warning must be present by whole-record canonical equality. Every indexed row
must have its exact frozen coordinates. Equal duplicate rows are accepted;
conflicting rows with the same `(execution_id, id, attempt)` are rejected.
The exact source tuple must exist, including history when necessary. A source
is the same attempt of the owner itself or a declared transitive ancestor in
the same execution, branch and temperature with source attempt no greater than
owner attempt. The complete bounded predecessor path is checked. Latest attempts,
immediate initialization predecessors and `data.checkpoint_source_attempt` do
not substitute for the causal locator.

Readers must keep one pinned snapshot through the call. Producers must supply
the complete prospective snapshot for that atomic publication, including the
new owner warning and actual source/history rows, then bind before publishing.
The caller guarantees immutability during the call; this helper does not provide
concurrent mutation safety, full schema validation or artifact availability.

A `BRANCH_STOPPED` code, any `reason_kind`, or `DEPENDENCY_UNAVAILABLE` with any
source locator field recognizes a typed claim. Partial or invalid claims raise
`ContractError`; they cannot become legacy warnings. Other finite JSON warning
objects, including the existing three-field `DEPENDENCY_UNAVAILABLE`, return
`None` without consulting owner context or interpreting message text. `None`
means reason unavailable. Unsupported typed plan/result versions, model revision
or contract set raise `incompatible_contract`; malformed or missing provenance,
identity mismatch and invalid graph raise `corrupt_result`.

Successful binding proves identity and graph consistency only. It does not
confirm the truth of `reason_kind`, classify Core assessments, or establish
scientific acceptance. In particular, `physical_gate_failed` requires actual
measured failing evidence from the producer; missing/error/not-measured summaries
do not prove a physical failure. Additional causes use separate warning records.
Existing warning schemas remain extensible, and existing plan/outcome APIs retain
their behavior. This API is imported from `messages`, not the top-level package.

Targeted metadata checks with the already available Python/test runtime:

```console
PYTHONPATH=src python3.14 -m pytest -q tests/test_branch_reasons.py
```

## Agent report file format

```python
from qcl_negf_contracts.agent_reports import validate_agent_report

report = validate_agent_report(raw_report_bytes)
# Retain raw_report_bytes when storing the file; do not re-encode report.
```

`validate_agent_report(raw: bytes) -> dict` validates a separate
`agent-report.json` file with schema `qcl-negf-agent-report-v1`. The exact
seven fields are `schema`, `anchor`, `question_snapshot`, `used_runs`,
`conclusion`, `reasoning`, and `limitations`. The four prose fields are
nonempty UTF-8 text with no lone surrogates; text and whitespace are not
normalized. The raw file is limited to 262144 bytes and must be strict UTF-8
JSON. UTF-8 BOMs, UTF-16/32 (including BOM-less forms), malformed JSON,
unknown or duplicate keys, and nonfinite JSON numbers are rejected with
`ContractError`. The decoded UTF-8 string is syntax-checked before the
existing duplicate-key decoder; general message decoding is unchanged.

`anchor` has exactly `run_uuid`, `root_definition_id`, `root_kind`, and
`plan_fingerprint`. Kind is `study` or `meta`. `used_runs` contains zero to
16 objects, each with exactly `run_uuid`, `plan_fingerprint`, `execution_id`,
`definition_id`, `variant_id`, `attempt`, and `calcjob_uuid`. UUIDs use their
full canonical lowercase form; fingerprints are 64 lowercase hexadecimal
digits. All IDs start with an ASCII letter or digit and contain only ASCII
letters, digits, `.`, `_`, or `-`, with a maximum length of 128 characters.
Attempts are integers at least one, excluding Boolean values. Duplicate
complete seven-field used tuples are rejected; distinct tuples are allowed.
An empty `used_runs` explicitly means no attempts were referenced.

This pure format API does not access files, ORM, plans, results or scientific
assessments. Consumers must separately check frozen plan identity and exact
run/variant/attempt/CalcJob membership before storing the original bytes.
`question_snapshot` is author text, not proof of the canonical research
question. The anchor identifies a run view, not a stable research card;
full R12 acceptance still depends on the R01 card/catalog relation. A valid
report, including its conclusion, does not establish scientific acceptance.

## Research card file format

```python
from qcl_negf_contracts.research_cards import validate_research_card

card = validate_research_card(raw_card_bytes)
# Store raw_card_bytes unchanged; do not re-encode card.
```

`validate_research_card(raw: bytes) -> dict` validates `research-card.json`
with exactly `schema`, `title`, `goal`, and `question`. Schema is
`qcl-negf-research-card-v1`. Title is limited to 128 Unicode code points;
goal and question are each limited to 16384 code points. Each text value
must contain a non-whitespace character according to Python `str.strip()`
and encode as strict UTF-8 without lone surrogates. Validation preserves
text, leading/trailing whitespace and combining characters without
normalization. The raw file limit is 65536 bytes, including JSON syntax,
escapes and whitespace; the encoded-byte limit also applies to multibyte text.

Input must be bytes containing strict UTF-8 JSON. UTF-8 BOMs, UTF-16/32
with or without BOMs, invalid UTF-8, malformed JSON, missing/surplus fields,
duplicate keys and nonfinite numbers raise `ContractError`. UTF-8 string
syntax is checked before the existing duplicate-key/finite-number decoder;
general message and agent-report decoding remain unchanged.

The native card UUID is assigned by the owning storage service and is absent
from this raw format, as is a self-hash. Equal title/goal/question values do
not prescribe merging cards. Consumers retain original bytes and separately
bind their digest, native UUID and immutable frozen-plan ownership. This pure
format API performs no storage, ORM access, process execution, plan lookup or
ScientificAssessment construction. A valid card does not establish scientific
acceptance; agent-report `question_snapshot` remains separate author text.
