"""Generated DTO/schema export must refuse drift and unknown schema constructs."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).parents[1]
TOOL = ROOT / 'tools/generate_types.py'


def test_native_generation_tool_exists():
    assert TOOL.is_file(), 'schema/TS generator missing'


def generator():
    spec = importlib.util.spec_from_file_location('qcl_generate_types', TOOL)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def test_generated_exports_are_current_without_bootstrap():
    result = subprocess.run([sys.executable, str(TOOL), '--check'], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_layout_change_changes_required_fields_and_fails_closed():
    module = generator()
    layout = json.loads((ROOT / 'src/qcl_negf_contracts/core_layout.json').read_text())
    original = module.core_schema(layout)
    layout['graph']['nodes']['SolverProgress']['fields'].append({'name':'added_receipt','type':'Int64'})
    updated = module.core_schema(layout)
    assert 'added_receipt' not in original['$defs']['SolverProgress']['properties']['fields']['required']
    assert 'added_receipt' in updated['$defs']['SolverProgress']['properties']['fields']['required']
    layout['graph']['nodes']['Int64']['kind'] = 'arbitrary_function'
    with pytest.raises(ValueError, match='Int64'):
        module.core_schema(layout)


def test_ts_generator_refuses_unknown_schema_keyword():
    module = generator()
    with pytest.raises(ValueError, match='unevaluatedProperties'):
        module.ts_type({'type':'object','unevaluatedProperties':False}, 'test', {})
