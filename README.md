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

Core `$defs` keys and payload type tags remain logical names. Generated `$ref` fragments first
escape JSON Pointer tokens (`~0`, `~1`), then percent-encode UTF-8 URI characters. For example,
`#/$defs/CoreArray%7BInt64%7D` targets the unchanged key `CoreArray{Int64}`. A literal `%7B` in a
logical key becomes `%257B` in its URI fragment. URI decoding happens once before Pointer token
traversal; decoding twice changes the target. The generator uses the same logical target for lookup
and TypeScript aliases, rejects invalid/unprovided targets, and retains standard offline resolution
without disabling optional strict URI format checks. See
[RFC 6901 §6](https://www.rfc-editor.org/rfc/rfc6901.html#section-6).

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

The canonical `scientific-plan.schema.json` retains scientific-plan v2 and transport-contract v2,
and requires the resolved snapshot marker, each execution's resolved snapshot/resource receipt and
each point's model digest. `resolved-configuration.schema.json` defines the closed snapshot metadata
containers; `resource-estimate.schema.json` defines the available analytical estimate and the
not-applicable receipt. Unknown overhead/RSS/admission fields remain required nulls. Receipt counts
are native JSON integers, distinct from decimal result-envelope counts and browser DTO tags.

Use `schema_validator("scientific-plan.schema.json")` for structural plan validation; the existing
`messages.scientific_plan` header/ID helper does not establish a full canonical schema pass. Strict
JSON decode/encode supplies the finite-value boundary. Runner owns typed projection field inventory,
units, raw replay, model/fingerprint recomputation and resource formulas. Snapshot metadata accepts
recursive JSON values without duplicating Core parameter definitions. A schema pass does not prove
scientific acceptance, measured memory, native admission or exact restart identity. Markerless plans
do not satisfy this canonical schema; no legacy fallback or automatic migration is provided.

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

### Полные raw final diagnostics

`final-diagnostics.schema.json` объявляет `qcl-negf.final-diagnostics.v1`: локальный JSON
subresource уже зарегистрированного native5 HDF `qcl-negf-physics-analysis-v5`, role
`physics.analysis`, profile `science`. Declaration хранится как bounded fixed-width UTF-8 scalar
`/final_diagnostics/declaration_json`, representation `final_diagnostics`. Это отдельная admission
ветка native reader; она не расширяет Core-state `array_payload`/`record_leaf` и graph129. Данная
поставка определяет Contracts boundary; producer/reader требуют отдельной квалификации.

```python
from qcl_negf_contracts.results import validate_final_diagnostics

checked = validate_final_diagnostics(
    declaration,
    checkpoint=verified_checkpoint_document,
    manifest=verified_manifest_document,
    artifact_ref=verified_selected_analysis_file_ref,
)
```

Все три keyword contexts обязательны. Caller сначала bounded-decodes JSON и проверяет bytes/hash
выбранных immutable файлов. Pure validator не открывает файлы, не следует по каталогам/dependencies,
не проверяет HDF или подлинность SHA256, не вызывает Core и не вычисляет научную приёмку. Он
связывает все пять FileRef fields выбранного analysis с manifest inventory, точные
identity/epoch/state id и sequence с checkpoint и manifest, а numerical binding — через существующий
checkpoint validator. `checkpoint` FileRef должен полностью совпадать с manifest checkpoint; direct
dependencies analysis ровно `[checkpoint.path]`. Checkpoint dependencies совпадают с его payload
frontier; полные FileRefs payloads также совпадают с inventory и не могут ссылаться на сам
checkpoint или selected analysis. Reachable dependency closure выбранного analysis проверяется на
cycles итеративно, без рекурсии и файлового I/O. Branching, shared leaves и forward/transitive DAG
разрешены; порядок inventory не задаёт topological order. Это scoped gate нового boundary, не
изменение старого manifest validator или проверка unrelated inventory closure. Dependency cycle и
круговая зависимость actual file hashes — разные утверждения; validator не экспериментирует с hash
fixed points. Требуются closed global `final`, non-null original final evidence и terminal process
state, включая failed/cancelled/interrupted. Сам payload не содержит собственного FileRef/manifest
hash: зависимости направлены analysis → checkpoint → state/history, без hash cycle.

Закрытый declaration содержит `schema`, `contract_set`, `identity`, `invocation`, `state_id`,
`state_sequence`, `checkpoint`, `dimensions`, `solution_metrics`, `positivity`. Dimensions — actual
positive Int64-domain decimal counts `energy`, `momentum`, `basis`; они должны совпадать с
`(E,k,a,b)` shapes всех четырёх checkpoint Green arrays. Это не реконструкция problem или новая
discretization.

`solution_metrics` сохраняет все поля Core `SolutionMetricDiagnostics`: `summary_metrics`,
`strict_limits`, `approximate_limits`. Maps — sorted unique `{name,value}` entries; symbol names
сохраняются строками, включая пустое имя; `nothing` optional limits — явный `null`, отличный от
`[]`. Final-over-history precedence вычисляет public Core getter, а encoder сохраняет его выход.

`positivity={status,reason,data}` отделяет successful invocation (`measured`, null reason, полные
данные) от `error`/`not_measured` (непустая причина, null data). Measured scan может содержать
`PositivityWitness.status="error"`: это не измеренный pass. I/O failure принадлежит writer и не
должен публиковаться как выполненный scan. Полные данные включают все восемь полей
`PositivityDiagnostics`: metric version, шесть matrix kinds, шесть witnesses, ratio limit, шесть
absolute limits и threshold flags, scan order и integrals. Full-final вариант требует
`scan_order="momentum_energy"` и non-null integrals от
`positivity_diagnostics(...; integrate=true)`; light scan не удовлетворяет этому контракту.

Каждый witness сохраняет все 13 public fields: status, matrix kind, energy/momentum indices, minimum
eigenvalue, block norm, floor, ratio, absolute/relative defect, backward error, hermiticity defect и
construction scale. Error sentinel `none`/нулевые coordinates и legacy scalar defaults не теряются;
error witness не может объявить measured threshold satisfaction. Scalar evidence и limits не
пересчитываются и не исправляются validator. В частности, IEEE diagnostics failed state сохраняются
независимо от scientific classification.

Float64 — существующий Core IEEE tag `{kind:"ieee",type:"f64",bits:"16 lowercase hex"}`, включая
signed zero, ±Inf и произвольные NaN payloads; JSON float/NaN/null не заменяет этот tag. Integers —
существующий Core Int64 tag с canonical decimal и range check. Counts не переводятся в Float64.
Четыре local array descriptors имеют fixed unique paths `/final_diagnostics/arrays/<field>`, exact
eltype, decimal shape, `order="F"`, axes и units; собственного FileRef внутри них нет:

| Field                             | Shape / axes               | Eltype / units                                                     |
| --------------------------------- | -------------------------- | ------------------------------------------------------------------ |
| `spectral_integral`               | `(Nk,Nb,Nb)` / `k,a,b`     | ComplexF64 / `1`                                                   |
| `spectral_integral_eigenvalues`   | `(Nk,Nb)` / `k,state`      | Float64 / `1`                                                      |
| `spectral_trace_cumulative`       | `(NE,Nk)` / `E,k`          | Float64 / `1`                                                      |
| `negative_energy_integral_scaled` | `(6,Nk)` / `matrix_kind,k` | Float64 / `scaled solver units; broadening carries energy squared` |

Native owner проверяет exact little-endian Float64 / consecutive `r,i` ComplexF64 storage, logical
axis mapping, filters, chunks и allocation/read budgets до чтения. Rank-3 analysis array не является
новой веткой frozen Core graph. Остальные пять integral fields inline: три Int64 count tuples длины
6, `total_blocks_per_kind=NE*Nk`, пять raw IEEE phase-space weights в `m^-2` для kinds
spectral/occupied/unoccupied/raw_occupied/raw_unoccupied; broadening сюда не входит. Проверяются
nonnegative counts, beyond ≤ negative ≤ total−invalid; спектральные данные не исправляются и не
реконструируются.

Порядок шести kinds фиксирован public Core: spectral, occupied, unoccupied, broadening,
raw_occupied, raw_unoccupied. Witness scalars/absolute limits используют scaled solver units
соответствующего matrix kind; physical-unit display projection хранится отдельно и не заменяет raw
source. Четыре integral arrays записываются один раз, без копии Green/Σ/history/witness matrices и
без второго scan для display. Stored observations не являются independent oracle или свидетельством
convergence, physics, discretization либо experiment. Missing analysis означает unavailable
capability; legacy v4 fallback и скрытый derive/selected-map/solve не предусмотрены.

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

## Producer phase source wire

`producer-phase-segment.schema.json` and `producer-phase-source.schema.json` describe the separate
technical producer protocol. Its Segment, Publication, Current and Cursor schemas are
`qcl-negf.producer-phase-{segment,publication,current,cursor}.v1`, with contract set
`qcl-negf.results.v2`. All fields, including nullable fields, are required and objects are closed.
They reuse result Identity/FileRef/decimal Count atoms and the generated Core Int64 atom. They add
no result artifact registry role and do not replace the Results telemetry Parquet catalog.

```python
from qcl_negf_contracts.telemetry import (
    validate_phase_segment, validate_phase_publication,
    validate_phase_current, validate_phase_cursor,
)

segment = validate_phase_segment(decoded_segment)
publication = validate_phase_publication(decoded_publication, segment=segment,
    segment_ref=verified_segment_ref, previous=previous_publication,
    previous_ref=verified_previous_ref)
current = validate_phase_current(decoded_current, publication=publication,
    publication_ref=verified_publication_ref)
cursor = validate_phase_cursor(decoded_cursor, publication=publication,
    publication_ref=verified_publication_ref, segment=segment,
    segment_ref=verified_segment_ref)
```

These pure APIs require the existing `[validation]` extra and return detached objects. Decode bytes
with an explicit caller budget first. FileRefs require application/json and the exact schema, with
canonical decimal bytes and confined relative paths. A digest declaration is not verification:
callers read and verify actual bytes/hash, safe paths/symlinks, owner identity and committed-chain
reachability before supplying immutable contexts. No referenced artifact is opened by these APIs.
Unknown versions/sets raise `unsupported_format`, malformed shapes `invalid_input`, and
contradictory bounded relations `corrupt_result`, using the existing `ContractError` and JSON-path
diagnostics.

Normal Segments contain only aggregates; diagnostic Segments contain only ordered begin/end events.
Normal maps the actual Core metric name `cpu_seconds` to `process_cpu_seconds` by name alone,
preserving value, unit, measurement status/reason at admission. The counter scope remains
`process_inclusive_delta_on_end`: nested timing intervals may overlap or straddle batches, so sums
are not exclusive CPU or a wall-time partition. Aggregate bounds describe contributing current-batch
end ordinals, excluding an older span begin. Aggregate rows may overlap across distinct keys and
need not be chronological. Diagnostic retains `cpu_seconds` and permits Core delivery gaps. Complete
event context requires a span id; incomplete context requires explicit incomplete Health. Spans may
cross Segments; the validator does not demand a locally balanced stack.

Numbers denote finite Float64 (including integral-valued floats). Actual native Int64 metrics use
`{kind:"integer",type:"Int64",decimal:"..."}` without JS Number rounding. Scalars retain explicit
units, statuses and reasons. Measured requires a nonnull value; unavailable/error requires a reason
and can retain an actual finite value. A producer represents a nonfinite source observation as null
with its error/reason, never zero; raw NaN/Infinity is rejected. Each aggregate metric has
`measured_calls + unavailable_calls == call_count`. Zero measured calls requires null sum; positive
measured calls with null sum requires an explicit aggregation-failure reason such as
`counter_overflow`. Summation failure does not relabel measured input calls as unavailable. Finite
partial sums with unavailable-call reasons are valid. Format validation cannot prove the measured
values or the declared aggregation failure.

Every normal Aggregate requires a closed `time_bounds` object with exactly `min_start_monotonic_ns`,
`max_end_monotonic_ns`, `measured_calls`, `unavailable_calls` and `reasons`. Bounds are nullable
decimal Counts in nanoseconds in the enclosing Source.clock_domain_id; all keys remain present.
Clock counts sum to Aggregate.call_count. Zero measured calls requires both bounds null; positive
measured calls requires both nonnull with min_start<=max_end (equality is valid). Unavailable calls
require unique nonempty reasons; fully measured clocks have no reasons. Partial envelopes cover only
the measured contributing calls. Clock availability is independent of CPU/GC/allocation availability
and cumulative Health; missing clocks never become [0,0].

The producer derives each contributing interval from measured, nonnegative native Int64 start/end
metrics in nanoseconds carried by the same actual phase_end event. End carries its token start even
across batches; a second begin copy is unnecessary. A measured producer_monotonic_ns, when present,
must equal end. Missing/invalid/reversed/mismatched pairs become unavailable with their actual
reasons or producer_clock_missing, producer_clock_invalid, producer_clock_reversed or
producer_clock_mismatch. Do not round Float64, parse string clocks, infer endpoints from duration,
or substitute observer/seal time. These are P29 admission rules: the pure validator checks only the
declared bounded envelope, without reading hidden events. An unfinished begin remains Current/Health
tail evidence, not a completed aggregate call.

Envelopes can overlap or begin before a previous seal; technical sequence/header/cursor ordering
still uses current-batch end ordinals. Source anchors correlate an actual endpoint using
UTC_anchor + (producer_monotonic - monotonic_anchor), within that Source/session/clock domain; they
do not reconstruct discarded endpoints or prove cross-host synchronization/drift precision. Envelope
width is not duration sum, busy/exclusive time or continuous coverage. Do not distribute
CPU/GC/allocation sums uniformly across chart bins and present that as measured per-bin utilization.
Normal preserves coarse placement; exact per-call chronology requires explicit diagnostic trace.

Segment `observed_events` counts retained valid inputs consumed by this batch before projection;
`coalesced_events` counts those folded/suppressed intentionally, at most once each. It is at most
observed, and diagnostic coalescing is zero. Nonempty Segments have at least as many inputs as rows;
empty/drop-only tails use Current/Health. Bounds equal min/max represented ordinals, excluding
future queued inputs or dropped-only endpoints. Diagnostic sequence gaps require explicit incomplete
Health. Normal projection can intentionally leave gaps without marking measurement incomplete.

Health `events_seen`, `enqueued`, `sealed_events`, `coalesced_events`, all six `dropped` counters
and `peak_buffered_bytes` are cumulative per Source/session. The queue/buffer/inflight/unsealed
fields are gauges; `self_cost` metrics are independent measurements. Buffered bytes cannot exceed
peak. Actual positive drops require incomplete Health and nonempty reasons; incomplete is sticky and
its reasons/cumulative counters cannot decrease in supplied successive contexts. Gauges can
decrease; no conservation equation is inferred between unlike counters. Publication Health may be
later than Segment Health, with nondecreasing cumulative fields and different gauges/self-cost, so
Segment encode/hash/sync costs are reported later without a self-cost cycle.

Publication binds the exact supplied Segment reference/content, full Identity/Source, bounds, row
count and `generation == segment_ordinal`. Ordinals strictly increase across supplied Publications
but need not be adjacent. A nonnull predecessor requires its exact content and verified reference;
initial publication rejects extra contexts. The local check rejects overlapping/reversed source
ranges and adjacent segment path reuse even if its hash changes. A gap requires incomplete Health or
normal mode plus positive batch/cumulative coalescing evidence. This is not proof of dense trace
coverage. Only one previous Publication is inspected; older global immutable path uniqueness and
chain reachability remain publisher/verified-reader gates.

Current requires its exact Publication content/reference when its pointer is nonnull and rejects
contexts for a null pointer. It checks full Identity/Source and cumulative Health. A live open phase
alone is not a drop. A closed Current with an open phase or positive queue/unsealed/buffer/inflight
tail must explicitly be incomplete; closed never means lossless or durable. When the self
Publication reference is known (Current/Cursor and supplied predecessor), its path must differ from
its Segment and previous Publication paths.

Cursor requires the exact Publication and Segment references/contents, with their local binding; it
does not recursively request ancestors. `next_row` is the zero-based next physical row. At zero,
`last_sequence` precedes this Publication; after positive progress it equals the maximum represented
upper ordinal across the consumed row prefix, including normal rows stored out of chronological
order. `complete_at_observation=true` requires all rows consumed through Publication.last_sequence.
It means committed-prefix read completion, never lossless measurement or future stream completion;
false may also mean that more observed Publications remain. The caller verifies the observed head
and advances a cursor only with its actual accepted output commit.

The existing generator exports `ProducerPhaseSegment`, `ProducerPhaseSource`, shared `Phase_*` types
and the offline schemas in `generated/contracts.ts`. The pure APIs do not establish queue bounds,
crash durability, actual storage reads, reader transactions, native overhead or scientific
acceptance. P29/P30 integration and runtime checks remain separate owning gates.

### Stored final observations and actual physical context

`final-observations.schema.json` defines `qcl-negf.final-observations.v1`, a separate local
subresource of the existing native5 `qcl-negf-physics-analysis-v5` artifact, role `physics.analysis`,
profile `science`. Its representation is `final_observations`; the fixed-width UTF8 scalar
declaration is `/final_observations/declaration_json`. The HDF root contains only `metadata` and
`final_observations`. This does not extend the frozen Core state graph, `array_payload`,
`record_leaf` or the independent `final_diagnostics` representation.

```python
from qcl_negf_contracts.results import (
    validate_final_observations, validate_nested_sweep_plan,
)

checked = validate_final_observations(
    decoded_observations,
    checkpoint=verified_checkpoint_document,
    manifest=verified_manifest_document,
    artifact_ref=verified_selected_observations_file_ref,
    diagnostics=decoded_selected_final_diagnostics,
    plan=decoded_original_plan,
    model=decoded_actual_point_model,
)
```

The keyword contexts are mandatory caller-verified immutable sources. The validator returns a
detached object and checks closed schemas, full FileRefs, actual state bindings, domain dimensions,
request facts, missing-output issues and the selected dependency DAG. It never opens files, verifies
hashes/HDF bytes, resolves Julia inputs, computes canonical model bytes or runs numerical validation.
The existing `[validation]` extra is required. Decode JSON with an explicit caller byte budget;
the existing finite UTF8/depth64 boundary applies. Native readers share one aggregate metadata/read
budget, check fixed scalar strings before reading and verify same-open storage and hashes.

The declaration binds exact identity, invocation, state sequence and Core identity/integrity to a
closed global-final checkpoint. Failed, cancelled and interrupted process outcomes remain valid
carriers of recorded evidence. Exact direct dependencies are ordered checkpoint, diagnostics, plan,
model; these are distinct immutable paths, as is the observations file. Diagnostics still depends
only on the checkpoint; plan and model are leaves. Selected closure cycles fail; forward/shared DAGs
are allowed. Unrelated inventory closure is not silently given a new global validation meaning.

`context` preserves actual postadaptive coordinates, nonuniform quadrature weights, scaled and
physical axes, scales, inputs, ordered scattering families, full physical/algorithm options and
declared basis/boundary/gauge conventions. Five construction/requested flags remain distinct from
actual enabled families; an absent requested zero kernel is not a measured zero. Electron-electron
scattering is a separate actual family. The schema names every context/view field from the published
Core declarations. Twenty-six fixed local array descriptors have exact dataset names, eltypes,
shapes, F order, logical axes, units and context coordinate/weight field references. Existing
checkpoint Green/selfenergy descriptors are copied exactly as bindings without duplicating their
arrays, kernels or retained witnesses.

The stored views retain complete complex wavefunctions and sheet matrices, including coherences;
raw spectral/occupied traces have axes `(E,k)`, spatial-energy density `(E,z)`. Potentials and density
refer to the accepted published state. Six nullable views require explicit issues; the effective
levels/wavefunctions/transform/density-matrix group is all present or all missing. Scalars use
existing IEEE64 tags; native Float64/ComplexF64 bytes preserve NaN payloads, infinities and signed
zero. Missing remains null with an issue. Native owners enforce exact LE storage, consecutive complex
`r/i` components, HDF Boolean enums and the existing non-lossy filter policy.

Raw metrics, optional limits and the one integrated positivity scan remain solely in the linked
`final_diagnostics`. When positivity is unavailable, its status matches the observations issue and
its diagnostic reason is exactly `issue.reason + ': ' + issue.detail`; machine reason/detail remain
separate in observations. An error witness inside measured diagnostics remains an error witness.
`summary` records the owning scientific classification without computing new acceptance criteria.
Its exact Core status text has a transport-profile limit of 256 Unicode codepoints: no truncation
or new Core Symbol restriction. Other current producer conventions/issue vocabularies are closed;
new owning producer values require an explicit format/profile update. The existing lossy display
`assessment` is not part of this wire. Runner retains full point/light presentation; readers must
not claim reconstruction of unseen display fields or treat display as raw evidence.

For completed restoration, pass both `parent_manifest` and `parent_checkpoint`. The child binds the
immediate parent StateRef, exact parent checkpoint/history cutoff and unchanged original Core
binding/evidence. Attempt, branch and epoch may legitimately differ in the envelopes. Original
evidence remains in the child checkpoint; current selected-map and independent-oracle receipts are
stored separately. `measured`, `unsupported`, `not_measured` and `error` remain distinct. These are
structural joins, without a hidden restore, fresh map, solve or numerical acceptance evaluator.

The plan FileRef hash is the exact original byte hash, distinct from a scientific fingerprint.
The model is the existing `qcl-negf-resolved-configuration-v3` envelope containing actual P03
`stationary_transport_inputs_v1` **after point axes are resolved**. Its `configuration_hash` is the
existing canonical preimage digest and equals model identity; its FileRef SHA is a different hash
of JSON file bytes. A template or renamed resolved-snapshot-v1 is not that point model. Results
independently checks canonical model bytes. Request coordinates bind to the frozen point; honest
voltage field/period roundtrip differences retain both IEEE samples as `not_verified` without an
invented tolerance.

`nested-sweep-plan.schema.json` formalizes the existing raw `{name,root}` tree: leaf `{kind,name}`
or level `{kind,name,axes:[{name,values}],child}`. It adds no payload envelope or `schema` key.
`validate_nested_sweep_plan(decoded_tree)` checks finite portable metadata, names, depth and unique
axis/fully-qualified coordinate names. Canonical axis-value uniqueness remains an owner check.
For configured results its FileRef uses `text/plain`, format `qcl-negf.nested-sweep-plan.v1`.
Runner captures an immutable attempt copy of original `execution_plan.yaml` bytes before Core;
the mutable operational file is not an immutable source and reserialization is not byte preservation.
The bounded raw YAML parser must reject anchors/aliases/merges, custom tags, duplicate/non-string
keys and NaN/Infinity before building objects. Validation of an already-decoded dict cannot prove
these properties of unseen YAML. The ordinary scientific route retains its actual canonical
scientific-plan-v2 JSON and full schema check.

Generated exports add `FinalObservations`, `Observation_*`, `NestedSweepPlan` and `Nested_*` while
preserving existing aliases and URI rules. Native Julia producer/readback qualification, mandatory
Results consumers, scientific discretization/oracle evidence and experimental validation remain
separate gates; a format pass does not establish any of them.
