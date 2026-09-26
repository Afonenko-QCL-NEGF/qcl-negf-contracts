"""Shared scientific contracts for the QCL-NEGF project family."""
from importlib.resources import files
import json

__version__ = "0.2.0"


def schema_names() -> tuple[str, ...]:
    """Return bundled schema and registry resource names."""
    return tuple(sorted(item.name for item in files(__package__).joinpath("schemas").iterdir()
                        if item.name.endswith(".json")))


def load_schema(name: str) -> dict:
    """Load a bundled JSON schema or result contract registry by its basename."""
    if name not in schema_names():
        raise ValueError(f"unknown schema resource: {name}")
    return json.loads(files(__package__).joinpath("schemas", name).read_text(encoding="utf-8"))


def schema_validator(name: str):
    """Create an offline Draft 2020-12 validator with bundled references.

    Install ``qcl-negf-contracts[validation]`` to enable this adapter. The pure
    JSON/artifact contracts and schema resource loading have no dependencies.
    """
    from jsonschema import Draft202012Validator
    from referencing import Registry, Resource

    base = "https://qcl-negf.invalid/schema/"
    registry = Registry()
    documents = {}
    for resource_name in schema_names():
        if resource_name == "results-contract-set.json":
            continue
        document = load_schema(resource_name)
        document.setdefault("$id", base + resource_name)
        documents[resource_name] = document
        registry = registry.with_resource(base + resource_name, Resource.from_contents(document))
    if name not in documents:
        raise ValueError(f"not a validation schema: {name}")
    return Draft202012Validator(documents[name], registry=registry)
