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
