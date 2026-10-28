# QCL-NEGF contracts

Versioned, dependency-free Python contracts and JSON Schema resources shared by the QCL-NEGF
scientific runner, AiiDA integration and result tools. This package owns scientific data formats;
scheduling and machine configuration belong to their respective services.

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

`decode` rejects nonfinite numbers, duplicate keys, excessive nesting and payloads above the
caller's byte budget. `scientific_plan` checks the envelope, identifiers and point count. It does
not replace complete JSON Schema validation or numerical validation.

## Contract ownership

| Resource                                       | Purpose                                                                                                                                                 |
| ---------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `schemas/run.schema.json`                      | Fully resolved solver configuration                                                                                                                     |
| `schemas/scientific-definition.schema.json`    | Declarative study and meta definitions                                                                                                                  |
| `schemas/scientific-plan.schema.json`          | Frozen scientific plan                                                                                                                                  |
| `schemas/output-policy.schema.json`            | Canonical archive/recovery/telemetry settings                                                                                                           |
| `schemas/scientific-worker-result.schema.json` | Solver execution results                                                                                                                                |
| `schemas/results-contract-set.json`            | Native and serialized artifact versions                                                                                                                 |
| `schemas/final-fixed-point-audit.schema.json`  | Bounded final raw measurement record; pure `final_audit.py` helpers validate status, identity and native/commit equality, without scientific acceptance |
| `artifacts.py`                                 | Artifact roles, paths, checksums and immutable commit validation                                                                                        |
| `telemetry.py`                                 | Typed fields and units for performance tables                                                                                                           |

Schemas are distributed inside the wheel under `qcl_negf_contracts/schemas`; `load_schema(name)` is
the supported resource accessor. Install `qcl-negf-contracts[validation]` and call
`schema_validator(name).validate(document)` for full offline validation. The adapter registers all
bundled schemas for relative `$ref` resolution and performs no network retrieval. Schemas follow
JSON Schema 2020-12. `results-contract-set.json` is a registry, not a validation schema.

The single supported result contract is `qcl-negf.results.v2`, with native HDF5 layout `5.0`. The
supported result APIs reject old v1/native4 data with `unsupported_format`; no migration or fallback
is provided. Current single-archive export receipts have no fixed byte ceiling. A successful
transport or valid format does not establish scientific acceptance.

The [scientific runner](https://github.com/Afonenko-QCL-NEGF/QCLNEGFRunner.jl) vendors the
configuration schema and registry with a checksum manifest so Julia does not need a Python runtime.
Changes to a vendored schema require a coordinated runner update.

## Development

Tests check schema validity, reference closure, artifact boundaries and hostile JSON inputs. Public
format changes require compatible producer and consumer releases with matching contract
declarations. MIT licensed; see [LICENSE](LICENSE).

## Integrated environment

The [qcl-negf](https://github.com/Afonenko-QCL-NEGF/qcl-negf) superproject owns the shared
dependency lock. From its root, run `uv sync --locked --all-packages --all-extras --group test`. The
package remains independently buildable and testable from its native metadata.

## Result v2 boundaries

```python
from qcl_negf_contracts.messages import decode
from qcl_negf_contracts.results import validate_manifest, validate_scientific_record

manifest = validate_manifest(decode(manifest_bytes, maximum=caller_byte_budget))
# The parent reference comes from this child's verified lineage.
record = validate_scientific_record(
    decoded_record,
    parent_checkpoint=parent_declaration,
    parent_state=child_manifest["lineage"]["parent_state"],
    parent_manifest_ref=verified_parent_manifest_ref,
)
```

These new public validators require the existing `[validation]` extra. They return detached JSON
objects, perform offline schema and envelope checks, and never read referenced artifacts or run
numerics. `validate_pointer(value)`,
`validate_catalog_page(value, *, previous=None, previous_page=None, previous_ref=None)`,
`validate_cursor(value, *, manifest, manifest_ref, catalog_page=None)`, and
`validate_checkpoint_declaration(value, *, manifest=None)` complete the API. A supplied previous pin
and parent/manifest context must come from the caller's verified immutable source. A hash string,
dataset shape or format declaration is not byte verification. `validate_commit` now accepts the
strict new manifest and returns internal `Artifact` objects; its explicit decimal byte-count adapter
preserves `Artifact.size` as a Python integer.

A catalog page with a nonnull previous pin requires its one preceding page document and verified
FileRef. The validator checks exact pin/ref/counters, owner/epoch and strictly increasing
generation; it does not request that page's ancestors. A cursor requires the supplied manifest's
verified FileRef. A nonnull cursor leaf also requires exactly
`catalog_page={"reference": verified_page_ref, "document": containing_page}`: the validator checks
page owner/epoch/generation/cutoff, exact leaf membership and cursor ordinal coverage. An empty
cursor has no containing page context. Parent-scoped updates require the actual child lineage parent
StateRef and verified parent manifest FileRef, and compare them to the anchor before checking
retained original locators. Caller-verified handles still establish actual bytes/hashes and
reachability of a supplied containing page from the pinned head. The wrappers do not traverse the
catalog prefix or infer physical row offsets from stream ordinals.

Catalog artifacts are only new immutable leaves; `entries` remains their cumulative count. New
artifact paths must be distinct within the page and disjoint from the supplied preceding page,
whether a repeated path declares the same hash or a different one. Global immutable path uniqueness
against earlier pages not supplied here remains a publisher/verified-reader gate. This local check
does not prove whole-prefix uniqueness or maintain a lifetime path index.

The manifest, pointer, scientific catalog, cursor, checkpoint declaration and scientific record
schemas are closed: unknown fields and versions fail, required nullable members remain present.
Counts in these new envelopes are canonical UInt64 decimal strings. Native floating values use
`{kind:"ieee",type:"f64",bits:"..."}` (or reflected f32); signed zero, NaN payloads and infinities
retain their bits. Complex components, integer widths, symbols, units, array eltypes/ranks and
column-major order remain explicit. Raw JSON NaN/Infinity remain invalid. Numerical arrays are HDF5
dataset declarations; Runner/Results verify their actual bytes, values and dimensions. Generic
public Core symbols include the empty symbol; its explicit symbol tag distinguishes it from an empty
String and null. Transport does not invent scientific enum constraints.

Core owns the mandatory state fields. `tools/reflect_core_layout.jl` reflects the public payload
closure into `core_layout.json`; `tools/generate_types.py` derives `core-state.schema.json` and
`generated/contracts.ts`. No hand-maintained copy of the Core field map exists. The layout hash
covers only the normalized type graph. Producer revision/runtime metadata remains separately
auditable. New unknown types fail generation. The sole scoped `Any` island is the existing
`SCBAResult.restart_contract` value grammar; it does not permit arbitrary objects or callbacks.

`ScientificHistorySnapshot` supplies the actual domain/grid and iteration key. Runner adds a
separate contiguous scientific stream ordinal; Core's delivery sequence also covers technical
callbacks, so its gaps do not prove lost science rows. Witness updates carry an explicit original
append locator. Same-leaf references use an earlier local offset without a self hash; sealed
references use exact leaf/hash/offset. Cross-attempt references bind the immediate parent state and
history pin plus its direct original-append dependency, including source epoch. Checkpoints retain
exactly the update-eligible worst/last anchors from the public Core continuation receipt, not an
index of all past rows. They also retain the complete required exact histories. An original append
from the checkpoint's own identity/epoch must lie inside its nonempty committed history pin. A
carried ancestor locator keeps its original epoch and ordinal, which can exceed the new attempt's
local cutoff.

Publication order is payload close/sync, immutable leaf, incremental catalog, checkpoint after its
dependencies, immutable manifest, then the small current pointer. Runner implements these I/O
barriers. Orphans are invisible until an explicit validated salvage. A checkpoint's history pin has
constant size; no append/checkpoint needs to reread old payloads. Full consolidated export is an
explicit streaming operation. Results owns verified handles and bounded reads.

Source composition is the existing Git-derived source graph. Scientific model/plan, exact Core
problem/policy/runtime, source provenance and execution lineage have separate scopes. An unrelated
Root/Portal/docs revision does not silently change scientific identity. Status records separate
process execution from convergence, physics, discretization and experiment: `recorded` means an
owning evidence reference exists, never scientific pass. Original, fresh revalidation and
independent-oracle receipts remain distinct.

The wheel includes `qcl_negf_contracts/generated/contracts.ts`, with generated DTO types and the
offline schema bundle. Counts/IEEE bits are strings in TypeScript. This is a schema/type export, not
a second runtime physics validator. In an already prepared development environment:

```console
python tools/generate_types.py --check
python -m pytest
python -m build --wheel --no-isolation
```

Core reflection is a separate development command using the selected, already prepared Julia
project/depot. `--check` verifies artifacts without writing. Its fixture invokes constructors only,
never SCBA/Poisson; numerical array references are declaration-only manufactured data, and the
fixture is explicitly not a validated exact restart. These checks do not install dependencies.
`tests/fixtures/results-v2/any-scope-probe.jl` explicitly checks the exporter qualification gate
before and after caching the permitted island, including a reused dictionary container. Run it with
the same prepared Julia project/depot as reflection; it performs no solve or installation. Changing
this package does not make old Runner/Results/AiiDA/Portal consumers ready: their owning format and
bridge integration must follow the selected published component composition.

## Export transport

The canonical scientific key is `output`, with `archive`, `recovery` and `telemetry` sections.
`archive.full_final` must be true in this release. Operational retention never certifies scientific
quality. New manifests bind `state_id`/`state_sequence` to their publication; progress artifacts
declare prior final receipts and file hashes for portable multi-point recovery.
`validate_execution_progress` checks reference structure, while consumers must also verify
referenced archive bytes.

`qcl-negf.science-export.v3` and `qcl-negf.operational-evidence.v2` receipts bind the v2 result set
and describe one `.tar.xz` using `qcl-negf.export-archive.v1`. `validate_export_receipt` and the
bundled schema check filename confinement, bytes, SHA256, profile and snapshot identity. These
subresources keep their own payload versions and types; bytes have no fixed upper bound. Successful
transport does not assert convergence or scientific acceptance. Multipart export constants and
registry entries are retired; old transport declarations are unsupported.

## Bound branch warnings

```python
from qcl_negf_contracts.messages import branch_reason, ContractError

# All inputs come from the same pinned, decoded publication and frozen plan.
owner = snapshot['points'][0]  # or a row in snapshot['attempt_history']
execution = next(e for e in plan['executions'] if e['id'] == owner['execution_id'])
cause = branch_reason(owner['warnings'][0], plan=plan, owner_point=owner,
                      owner_execution=execution, source_points=snapshot)
```

`branch_reason(record, *, plan, owner_point, owner_execution, source_points)` is a dependency-free,
pure semantic helper returning a detached seven-field object or `None`. It does not modify inputs or
read files. The typed record has exactly `code`, `scope`, `reason_kind`, `source_execution_id`,
`source_point_id`, `source_attempt`, and `message`. `code` is `BRANCH_STOPPED` or
`DEPENDENCY_UNAVAILABLE`; `scope` is `branch`. The supported reasons are `process_failure`,
`iteration_not_converged`, `physical_gate_failed`, `interrupted`, `data_unavailable`,
`assessment_unavailable`, and `metadata_invalid`. Source IDs use the existing portable ASCII pattern
(1–128 characters); attempt is a positive integer excluding Boolean. Message is nonempty valid
UTF-8, limited to 2048 encoded bytes.

The caller supplies a fully validated/trusted frozen scientific plan v2 and the complete immutable
series result v3 snapshot with contract set `qcl-negf.results.v2`, both `points` and
`attempt_history` lists, and matching header identity. The full owner execution must equal the
frozen plan entry; the snapshot uses the existing nine-field execution projection. Owner row and
warning must be present by whole-record canonical equality. Every indexed row must have its exact
frozen coordinates. Equal duplicate rows are accepted; conflicting rows with the same
`(execution_id, id, attempt)` are rejected. The exact source tuple must exist, including history
when necessary. A source is the same attempt of the owner itself or a declared transitive ancestor
in the same execution, branch and temperature with source attempt no greater than owner attempt. The
complete bounded predecessor path is checked. Latest attempts, immediate initialization predecessors
and `data.checkpoint_source_attempt` do not substitute for the causal locator.

Readers must keep one pinned snapshot through the call. Producers must supply the complete
prospective snapshot for that atomic publication, including the new owner warning and actual
source/history rows, then bind before publishing. The caller guarantees immutability during the
call; this helper does not provide concurrent mutation safety, full schema validation or artifact
availability.

A `BRANCH_STOPPED` code, any `reason_kind`, or `DEPENDENCY_UNAVAILABLE` with any source locator
field recognizes a typed claim. Partial or invalid claims raise `ContractError`; they cannot become
legacy warnings. Other finite JSON warning objects, including the existing three-field
`DEPENDENCY_UNAVAILABLE`, return `None` without consulting owner context or interpreting message
text. `None` means reason unavailable. Unsupported typed plan/result versions, model revision or
contract set raise `incompatible_contract`; malformed or missing provenance, identity mismatch and
invalid graph raise `corrupt_result`.

Successful binding proves identity and graph consistency only. It does not confirm the truth of
`reason_kind`, classify Core assessments, or establish scientific acceptance. In particular,
`physical_gate_failed` requires actual measured failing evidence from the producer;
missing/error/not-measured summaries do not prove a physical failure. Additional causes use separate
warning records. Existing warning schemas remain extensible, and existing plan/outcome APIs retain
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

`validate_agent_report(raw: bytes) -> dict` validates a separate `agent-report.json` file with
schema `qcl-negf-agent-report-v1`. The exact seven fields are `schema`, `anchor`,
`question_snapshot`, `used_runs`, `conclusion`, `reasoning`, and `limitations`. The four prose
fields are nonempty UTF-8 text with no lone surrogates; text and whitespace are not normalized. The
raw file is limited to 262144 bytes and must be strict UTF-8 JSON. UTF-8 BOMs, UTF-16/32 (including
BOM-less forms), malformed JSON, unknown or duplicate keys, and nonfinite JSON numbers are rejected
with `ContractError`. The decoded UTF-8 string is syntax-checked before the existing duplicate-key
decoder; general message decoding is unchanged.

`anchor` has exactly `run_uuid`, `root_definition_id`, `root_kind`, and `plan_fingerprint`. Kind is
`study` or `meta`. `used_runs` contains zero to 16 objects, each with exactly `run_uuid`,
`plan_fingerprint`, `execution_id`, `definition_id`, `variant_id`, `attempt`, and `calcjob_uuid`.
UUIDs use their full canonical lowercase form; fingerprints are 64 lowercase hexadecimal digits. All
IDs start with an ASCII letter or digit and contain only ASCII letters, digits, `.`, `_`, or `-`,
with a maximum length of 128 characters. Attempts are integers at least one, excluding Boolean
values. Duplicate complete seven-field used tuples are rejected; distinct tuples are allowed. An
empty `used_runs` explicitly means no attempts were referenced.

This pure format API does not access files, ORM, plans, results or scientific assessments. Consumers
must separately check frozen plan identity and exact run/variant/attempt/CalcJob membership before
storing the original bytes. `question_snapshot` is author text, not proof of the canonical research
question. The anchor identifies a run view, not a stable research card; full R12 acceptance still
depends on the R01 card/catalog relation. A valid report, including its conclusion, does not
establish scientific acceptance.

## Research card file format

```python
from qcl_negf_contracts.research_cards import validate_research_card

card = validate_research_card(raw_card_bytes)
# Store raw_card_bytes unchanged; do not re-encode card.
```

`validate_research_card(raw: bytes) -> dict` validates `research-card.json` with exactly `schema`,
`title`, `goal`, and `question`. Schema is `qcl-negf-research-card-v1`. Title is limited to 128
Unicode code points; goal and question are each limited to 16384 code points. Each text value must
contain a non-whitespace character according to Python `str.strip()` and encode as strict UTF-8
without lone surrogates. Validation preserves text, leading/trailing whitespace and combining
characters without normalization. The raw file limit is 65536 bytes, including JSON syntax, escapes
and whitespace; the encoded-byte limit also applies to multibyte text.

Input must be bytes containing strict UTF-8 JSON. UTF-8 BOMs, UTF-16/32 with or without BOMs,
invalid UTF-8, malformed JSON, missing/surplus fields, duplicate keys and nonfinite numbers raise
`ContractError`. UTF-8 string syntax is checked before the existing duplicate-key/finite-number
decoder; general message and agent-report decoding remain unchanged.

The native card UUID is assigned by the owning storage service and is absent from this raw format,
as is a self-hash. Equal title/goal/question values do not prescribe merging cards. Consumers retain
original bytes and separately bind their digest, native UUID and immutable frozen-plan ownership.
This pure format API performs no storage, ORM access, process execution, plan lookup or
ScientificAssessment construction. A valid card does not establish scientific acceptance;
agent-report `question_snapshot` remains separate author text.
