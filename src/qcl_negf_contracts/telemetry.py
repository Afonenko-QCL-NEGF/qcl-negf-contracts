"""Telemetry field contracts, independent of Arrow and filesystem adapters."""
from __future__ import annotations

from .artifacts import CONTRACT_SET
from .messages import ContractError, Object, encode, object_value
from .results import _context_definition, _file, _require, _validator, _walk

TELEMETRY_SCHEMA = "qcl-negf.performance.v2"
# Types map to Arrow types at the adapter boundary; units remain explicit in names.
COMMON_FIELDS = (("session_id", "string"), ("worker_id", "string"),
                 ("execution_id", "string"), ("point_id", "string"),
                 ("allocation_id", "string"), ("monotonic_ns", "int64"),
                 ("sample_sequence", "int64"), ("clock_domain_id", "string"),
                 ("utc_anchor_ns", "int64"), ("monotonic_anchor_ns", "int64"))
SPAN_FIELDS = COMMON_FIELDS + (("span_id", "string"), ("parent_span_id", "string"),
    ("phase", "string"), ("duration_seconds", "float64"), ("call_count", "int64"),
    ("iteration", "int64"), ("timing_kind", "string"), ("warmup", "bool"),
    ("measurement_kind", "string"), ("timestamp_kind", "string"),
    ("source_session_id", "string"), ("source_sequence", "int64"),
    ("source_path", "string"), ("source_offset", "int64"),
    ("stage_path", "string"), ("attempt", "int64"),
    ("may_include_compilation", "bool"), ("payload_bytes", "int64"),
    ("event_kind", "string"), ("begin_monotonic_ns", "int64"),
    ("end_monotonic_ns", "int64"), ("process_cpu_seconds", "float64"),
    ("allocated_bytes", "int64"), ("gc_seconds", "float64"), ("gc_count", "int64"),
    ("counter_scope", "string"), ("process_cpu_total_seconds", "float64"),
    ("allocated_total_bytes", "int64"), ("gc_total_seconds", "float64"),
    ("gc_total_count", "int64"), ("task_width", "int64"),
    ("work_units", "int64"), ("workspace_bytes", "int64"),
    ("memory_burst_bytes", "int64"), ("parallel_kind", "string"),
    ("phase_wait_reason", "string"), ("capability_reasons", "string"),
    ("memory_admission_mode", "string"), ("memory_current_before_bytes", "int64"),
    ("memory_limit_bytes", "int64"), ("memory_granted_additional_bytes", "int64"),
    ("memory_current_after_gc_bytes", "int64"), ("memory_effective_current_bytes", "int64"),
    ("memory_clean_cache_credit_bytes", "int64"), ("memory_full_gc_seconds", "float64"),
    ("memory_stat_before", "string"), ("memory_stat_after_gc", "string"))
RESOURCE_FIELDS = COMMON_FIELDS + (("cpu_time_seconds", "float64"),
    ("wall_seconds", "float64"), ("rss_bytes", "int64"), ("peak_rss_bytes", "int64"),
    ("cpu_count", "int64"), ("read_bytes", "int64"), ("write_bytes", "int64"),
    ("gc_seconds", "float64"), ("throttled_seconds", "float64"),
    ("cpu_pressure_seconds", "float64"), ("sample_interval_seconds", "float64"),
    ("missing_reason", "string"), ("capability_reasons", "string"),
    ("pid", "int64"), ("process_start_ticks", "int64"),
    ("cgroup_path", "string"), ("cgroup_scope", "string"),
    ("cgroup_cpu_seconds", "float64"), ("cpu_quota_cores", "float64"),
    ("cpu_period_seconds", "float64"), ("throttled_periods", "int64"),
    ("memory_current_bytes", "int64"), ("memory_peak_bytes", "int64"),
    ("memory_high_bytes", "int64"), ("memory_max_bytes", "int64"),
    ("memory_anon_bytes", "int64"), ("memory_file_bytes", "int64"),
    ("memory_kernel_bytes", "int64"), ("memory_swap_bytes", "int64"),
    ("memory_inactive_file_bytes", "int64"), ("memory_file_dirty_bytes", "int64"),
    ("memory_file_writeback_bytes", "int64"), ("memory_shmem_bytes", "int64"),
    ("memory_file_mapped_bytes", "int64"),
    ("memory_event_high", "int64"), ("memory_event_max", "int64"),
    ("memory_event_oom", "int64"), ("memory_event_oom_kill", "int64"),
    ("memory_event_oom_group_kill", "int64"),
    ("memory_pressure_seconds", "float64"), ("io_pressure_seconds", "float64"),
    ("cpu_full_pressure_seconds", "float64"),
    ("memory_full_pressure_seconds", "float64"), ("io_full_pressure_seconds", "float64"),
    ("minor_faults", "int64"), ("major_faults", "int64"),
    ("voluntary_context_switches", "int64"), ("involuntary_context_switches", "int64"),
    ("thread_count", "int64"), ("thread_cpu_seconds", "string"),
    ("thread_counter_scope", "string"), ("thread_counter_details", "string"),
    ("thread_listed_count", "int64"), ("thread_sample_count", "int64"),
    ("thread_sampling_complete", "bool"), ("thread_delta_complete", "bool"),
    ("matched_thread_count", "int64"), ("new_thread_count", "int64"),
    ("vanished_thread_count", "int64"), ("thread_counter_interval_seconds", "float64"),
    ("voluntary_context_switches_delta", "int64"), ("involuntary_context_switches_delta", "int64"),
    ("thread_runtime_seconds", "float64"), ("thread_runtime_delta_seconds", "float64"),
    ("thread_runqueue_wait_seconds", "float64"), ("thread_runqueue_wait_delta_seconds", "float64"),
    ("thread_schedstat_enabled", "bool"),
    ("profile_window_id", "string"), ("sampling_mode", "string"),
    ("active_task_width", "int64"), ("phase", "string"))
CONTROL_FIELDS = COMMON_FIELDS + (("event", "string"), ("reason", "string"),
    ("attempt", "int64"), ("reference", "string"), ("samples_dropped", "int64"))
TABLE_FIELDS = {"spans": SPAN_FIELDS, "resources": RESOURCE_FIELDS, "control_events": CONTROL_FIELDS}


# The producer source protocol is separate from the Parquet table contracts above.
# Pure validators below inspect only caller-supplied bounded contents and declarations.
_PHASE_SCHEMAS = {kind: 'qcl-negf.producer-phase-'+kind+'.v1'
                  for kind in ('segment', 'publication', 'current', 'cursor')}
_CUMULATIVE = ('events_seen', 'enqueued', 'sealed_events', 'coalesced_events', 'peak_buffered_bytes')


def _phase_reference(value, kind, path):
    checked = _context_definition('FileRef', value, path)
    _file(checked, _PHASE_SCHEMAS[kind], path)
    _require(checked['media_type'] == 'application/json', path+'.media_type', 'phase reference requires application/json')
    return checked


def _phase_checked(kind, value):
    from jsonschema import ValidationError
    checked = object_value(value)
    if checked.get('schema') != _PHASE_SCHEMAS[kind] or checked.get('contract_set') != CONTRACT_SET:
        raise ContractError(f'$: unsupported producer phase {kind} format', 'unsupported_format')
    # Classify a declared unknown referenced format before the closed schema rejects it.
    for field, target in (('segment', 'segment'), ('previous', 'publication'), ('publication', 'publication')):
        reference = checked.get(field)
        if isinstance(reference, dict) and isinstance(reference.get('schema'), str):
            if reference['schema'] != _PHASE_SCHEMAS[target]:
                raise ContractError(f'$.{field}.schema: unsupported producer phase reference', 'unsupported_format')
    filename = 'producer-phase-'+('segment' if kind == 'segment' else 'source')+'.schema.json'
    try:
        encode(checked)
        _validator(filename).validate(checked)
    except ValidationError as error:
        path = '$'+''.join(f'[{item}]' if isinstance(item, int) else '.'+item for item in error.absolute_path)
        raise ContractError(f'{path}: {error.message}', 'invalid_input') from error
    except UnicodeError as error:
        raise ContractError('$: invalid UTF-8 phase metadata', 'invalid_input') from error
    _walk(checked)
    _require(len(checked['source']['clock_domain_id'].encode('utf-8')) <= 512,
             '$.source.clock_domain_id', 'clock domain exceeds 512 UTF-8 bytes')
    if kind != 'cursor':
        _phase_health(checked['health'], '$.health')
    return checked


def _span(value, path):
    if value is not None:
        _require(len(value.encode('utf-8')) <= 256, path, 'span id exceeds 256 UTF-8 bytes')


def _unique_metrics(metrics, path, *, scalar=False):
    keys = [(metric['name'], metric['unit']) for metric in metrics]
    _require(len(set(keys)) == len(keys), path, 'duplicate metric name/unit')
    if scalar:
        for index, metric in enumerate(metrics):
            here = f'{path}[{index}]'
            if metric['measurement_status'] == 'measured':
                _require(metric['value'] is not None, here+'.value', 'measured metric requires a value')
            else:
                _require(bool(metric['reason']), here+'.reason', 'unavailable/error metric requires a reason')


def _phase_health(value, path):
    _require(int(value['buffered_bytes']) <= int(value['peak_buffered_bytes']), path, 'buffered bytes exceed peak')
    reasons = value['incomplete_reasons']
    _require(bool(reasons) == value['incomplete'], path+'.incomplete_reasons', 'incomplete status and reasons differ')
    if any(int(count) > 0 for count in value['dropped'].values()):
        _require(value['incomplete'], path+'.incomplete', 'drops require explicit incomplete health')
    _unique_metrics(value['self_cost'], path+'.self_cost', scalar=True)


def _health_after(before, after, path='$.health'):
    for key in _CUMULATIVE:
        _require(int(after[key]) >= int(before[key]), path+'.'+key, 'cumulative counter decreased')
    for key in before['dropped']:
        _require(int(after['dropped'][key]) >= int(before['dropped'][key]), path+'.dropped.'+key, 'cumulative drops decreased')
    _require(not before['incomplete'] or after['incomplete'], path+'.incomplete', 'incomplete health must remain sticky')
    _require(set(before['incomplete_reasons']) <= set(after['incomplete_reasons']), path+'.incomplete_reasons', 'cumulative reasons decreased')


def _same_owner(value, other, path):
    for key in ('identity', 'source'):
        _require(value[key] == other[key], path+'.'+key, 'phase owner/source binding differs')


def _row_bounds(row):
    if row['kind'] == 'event':
        return int(row['sequence']), int(row['sequence'])
    return int(row['first_sequence']), int(row['last_sequence'])


def _aggregate_time_bounds(value, call_count, path):
    """Declared envelope only; actual paired Core event admission belongs to the producer."""
    measured, unavailable = int(value['measured_calls']), int(value['unavailable_calls'])
    start, end = value['min_start_monotonic_ns'], value['max_end_monotonic_ns']
    _require(measured+unavailable == int(call_count), path, 'clock call counts differ from aggregate')
    _require((start is None) == (end is None), path, 'clock bounds must be null together')
    if measured == 0:
        _require(start is None and end is None, path, 'zero measured clock calls require null bounds')
    else:
        _require(start is not None and end is not None, path, 'measured clock calls require bounds')
        _require(int(start) <= int(end), path, 'clock bounds reversed')
    if unavailable:
        _require(bool(value['reasons']), path+'.reasons', 'unavailable clock calls require reasons')
    else:
        _require(not value['reasons'], path+'.reasons', 'fully measured clocks require empty reasons')


def validate_phase_segment(value: object) -> Object:
    """Validate one sealed metadata batch; never infer measurement or science acceptance."""
    value = _phase_checked('segment', value)
    rows = value['rows']; health = value['health']
    observed, coalesced = int(value['observed_events']), int(value['coalesced_events'])
    _require(coalesced <= observed, '$.coalesced_events', 'batch coalescing exceeds observed inputs')
    _require(observed >= len(rows), '$.observed_events', 'fewer batch inputs than represented rows')
    if value['mode'] == 'diagnostic':
        _require(coalesced == 0, '$.coalesced_events', 'diagnostic events cannot be coalesced')
        previous = None
        for index, row in enumerate(rows):
            path = f'$.rows[{index}]'; sequence = int(row['sequence'])
            if previous is not None:
                _require(sequence > previous, path+'.sequence', 'diagnostic sequences must strictly increase')
                _require(sequence == previous+1 or health['incomplete'], path+'.sequence', 'diagnostic gap requires incomplete health')
            previous = sequence
            _span(row['span_id'], path+'.span_id'); _span(row['parent_span_id'], path+'.parent_span_id')
            _require(row['span_id'] is None or row['span_id'] != row['parent_span_id'], path+'.parent_span_id', 'span cannot parent itself')
            if row['context_status'] == 'complete':
                _require(row['span_id'] is not None, path+'.span_id', 'complete context requires span id')
            else:
                _require(health['incomplete'], path+'.context_status', 'incomplete context requires incomplete health')
            _unique_metrics(row['metrics'], path+'.metrics', scalar=True)
    else:
        keys = [(row['stage'], row['phase'], row['status'], row['task_width'], row['counter_scope']) for row in rows]
        _require(len(set(keys)) == len(keys), '$.rows', 'duplicate aggregate key')
        for index, row in enumerate(rows):
            path = f'$.rows[{index}]'
            first, last = _row_bounds(row)
            _require(first <= last, path, 'aggregate technical bounds reversed')
            first_core, last_core = row['first_core_sequence'], row['last_core_sequence']
            _require((first_core is None) == (last_core is None), path, 'Core sequence bounds must be null together')
            if first_core is not None:
                _require(int(first_core) <= int(last_core), path, 'Core sequence bounds reversed')
            _aggregate_time_bounds(row['time_bounds'], row['call_count'], path+'.time_bounds')
            _unique_metrics(row['metrics'], path+'.metrics')
            for mindex, metric in enumerate(row['metrics']):
                here = f'{path}.metrics[{mindex}]'
                measured, unavailable = int(metric['measured_calls']), int(metric['unavailable_calls'])
                _require(measured+unavailable == int(row['call_count']), here, 'metric call counts differ from aggregate')
                if measured == 0:
                    _require(metric['sum'] is None, here+'.sum', 'zero measured calls require null sum')
                elif metric['sum'] is None:
                    _require(bool(metric['reasons']), here+'.reasons', 'failed aggregation requires explicit reason')
                if unavailable:
                    _require(bool(metric['reasons']), here+'.reasons', 'unavailable calls require reasons')
    bounds = [_row_bounds(row) for row in rows]
    _require(int(value['first_sequence']) == min(first for first, _ in bounds)
             and int(value['last_sequence']) == max(last for _, last in bounds), '$', 'segment bounds differ from represented rows')
    return value


def _publication_content(value):
    """Only this Publication's local header; no Segment or ancestor traversal."""
    value = _phase_checked('publication', value)
    _phase_reference(value['segment'], 'segment', '$.segment')
    if value['previous'] is not None:
        _phase_reference(value['previous'], 'publication', '$.previous')
        _require(value['previous']['path'] != value['segment']['path'], '$.segment.path', 'segment rebinds previous publication path')
    _require(int(value['first_sequence']) <= int(value['last_sequence']), '$', 'publication bounds reversed')
    _require(int(value['rows']) > 0, '$.rows', 'publication requires nonempty segment rows')
    return value


def _publication_segment(value, segment, segment_ref):
    checked = validate_phase_segment(segment)
    reference = _phase_reference(segment_ref, 'segment', '$.segment_ref')
    _require(reference == value['segment'], '$.segment', 'exact verified segment reference required')
    _same_owner(value, checked, '$.segment')
    for key in ('first_sequence', 'last_sequence'):
        _require(value[key] == checked[key], '$.'+key, 'publication/segment bounds differ')
    _require(int(value['rows']) == len(checked['rows']), '$.rows', 'publication/segment row count differs')
    _require(value['generation'] == checked['segment_ordinal'], '$.generation', 'publication generation differs from segment ordinal')
    _health_after(checked['health'], value['health'])
    return checked


def _publication_self(value, reference, path):
    reference = _phase_reference(reference, 'publication', path)
    forbidden = [value['segment']['path']]
    if value['previous'] is not None:
        forbidden.append(value['previous']['path'])
    _require(reference['path'] not in forbidden, path+'.path', 'publication path rebinds its segment or predecessor')
    return reference


def validate_phase_publication(value: object, *, segment: object, segment_ref: object,
                               previous: object | None = None,
                               previous_ref: object | None = None) -> Object:
    """Bind one sealed Segment and at most one supplied, caller-verified predecessor."""
    value = _publication_content(value)
    checked_segment = _publication_segment(value, segment, segment_ref)
    if value['previous'] is None:
        _require(previous is None and previous_ref is None, '$.previous', 'initial publication has extraneous previous context')
    else:
        _require(previous is not None and previous_ref is not None, '$.previous', 'previous publication content and verified reference required')
        prior = _publication_content(previous)
        reference = _publication_self(prior, previous_ref, '$.previous_ref')
        _require(reference == value['previous'], '$.previous', 'exact verified previous publication reference required')
        _same_owner(value, prior, '$.previous')
        _require(int(value['generation']) > int(prior['generation']), '$.generation', 'publication generation must strictly increase')
        _require(int(value['first_sequence']) > int(prior['last_sequence']), '$.first_sequence', 'publication ranges overlap or reverse')
        _require(value['segment']['path'] != prior['segment']['path'], '$.segment.path', 'adjacent publication reuses segment path')
        _health_after(prior['health'], value['health'])
        if int(value['first_sequence']) > int(prior['last_sequence'])+1:
            normal_coalescing = checked_segment['mode'] == 'normal' and (
                int(checked_segment['coalesced_events']) > 0 or int(value['health']['coalesced_events']) > 0)
            _require(value['health']['incomplete'] or normal_coalescing, '$.first_sequence', 'publication gap requires incomplete or normal coalescing evidence')
    return value


def validate_phase_current(value: object, *, publication: object | None = None,
                           publication_ref: object | None = None) -> Object:
    """Validate live/closed source progress with its one explicit Publication context."""
    value = _phase_checked('current', value)
    if value['publication'] is None:
        _require(publication is None and publication_ref is None, '$.publication', 'empty current has extraneous publication context')
    else:
        _require(publication is not None and publication_ref is not None, '$.publication', 'publication content and verified reference required')
        content = _publication_content(publication)
        reference = _publication_self(content, publication_ref, '$.publication_ref')
        _require(value['publication'] == reference, '$.publication', 'exact verified publication reference required')
        _same_owner(value, content, '$.publication')
        _health_after(content['health'], value['health'])
    phase = value['current_phase']
    if phase is not None:
        _span(phase['span_id'], '$.current_phase.span_id')
    if value['closed'] and (phase is not None or any(int(value['health'][key]) > 0 for key in
            ('queued_events', 'unsealed_events', 'buffered_bytes', 'inflight_bytes'))):
        _require(value['health']['incomplete'], '$.health.incomplete', 'closed source has open phase or unsealed tail')
    return value


def validate_phase_cursor(value: object, *, publication: object, publication_ref: object,
                          segment: object, segment_ref: object) -> Object:
    """Check progress in immutable file order; caller verifies observed head/output commit."""
    value = _phase_checked('cursor', value)
    content = _publication_content(publication)
    reference = _publication_self(content, publication_ref, '$.publication_ref')
    _require(value['publication'] == reference, '$.publication', 'exact verified publication reference required')
    _same_owner(value, content, '$.publication')
    checked = _publication_segment(content, segment, segment_ref)
    _require(value['segment'] == content['segment'], '$.segment', 'cursor segment reference differs from publication')
    next_row, sequence = int(value['next_row']), int(value['last_sequence'])
    rows = checked['rows']
    _require(next_row <= len(rows), '$.next_row', 'cursor is beyond segment rows')
    if next_row == 0:
        _require(sequence < int(content['first_sequence']), '$.last_sequence', 'zero progress must precede publication range')
    else:
        maximum = max(_row_bounds(row)[1] for row in rows[:next_row])
        _require(sequence == maximum, '$.last_sequence', 'cursor differs from maximum represented prefix ordinal')
    if value['complete_at_observation']:
        _require(next_row == len(rows) and sequence == int(content['last_sequence']), '$.complete_at_observation', 'observed prefix completion requires all rows')
    return value


# Optional technical metadata is deliberately independent of scientific manifests.
TELEMETRY_COMMIT_SCHEMA = 'qcl-negf.telemetry-commit.v1'
TELEMETRY_POINTER_SCHEMA = 'qcl-negf.telemetry-pointer.v1'
TELEMETRY_SUMMARY_SCHEMA = 'qcl-negf.telemetry-summary.v1'
TELEMETRY_BINDING_SCHEMA = 'qcl-negf.telemetry-binding.v1'
TELEMETRY_SOURCE_BINDING_SCHEMA = 'qcl-negf.telemetry-source-binding.v1'
_TELEMETRY_ROOTS = dict(commit='TelemetryCommit', pointer='TelemetryPointer',
    summary='TelemetrySummary', binding='TelemetryBinding', source_binding='TelemetrySourceBinding')
_TELEMETRY_IDS = dict(commit=TELEMETRY_COMMIT_SCHEMA, pointer=TELEMETRY_POINTER_SCHEMA,
    summary=TELEMETRY_SUMMARY_SCHEMA, binding=TELEMETRY_BINDING_SCHEMA,
    source_binding=TELEMETRY_SOURCE_BINDING_SCHEMA)
_UNITS = dict(duration_seconds='s', process_cpu_seconds='s', allocated_bytes='B', gc_seconds='s', gc_count='1')


def _technical_definition(name, value, path='$'):
    from jsonschema import ValidationError
    checked = object_value(value)
    validator = _validator('telemetry-envelope.schema.json')
    try:
        encode(checked)
        target = 'model-help.schema.json#/$defs/SourceGraph' if name == 'SourceGraph' else '#/$defs/'+name
        validator.evolve(schema={'$ref': target, '$defs': validator.schema['$defs']}).validate(checked)
    except ValidationError as error:
        suffix = ''.join(f'[{item}]' if isinstance(item, int) else '.'+item for item in error.absolute_path)
        code = 'unsupported_format' if error.absolute_path and error.absolute_path[-1] in ('schema','contract_set') else 'invalid_input'
        raise ContractError(f'{path}{suffix}: {error.message}', code) from error
    except UnicodeError as error:
        raise ContractError(f'{path}: invalid UTF-8', 'invalid_input') from error
    _walk(checked, path)
    _technical_bounds(checked, path)
    return checked


def _technical_bounds(value, path='$'):
    if isinstance(value, dict):
        for key, item in value.items():
            here = path+'.'+key
            if isinstance(item, str) and key != 'raw_utf8':
                limit = 4096 if key == 'path' else 256 if key in ('stage','phase','label','event','name','unit') else 512
                _require(len(item.encode('utf-8')) <= limit, here, 'technical string exceeds UTF-8 byte bound')
            if key in ('metrics', 'self_cost', 'reasons', 'incomplete_reasons') and isinstance(item, list):
                _require(len(item) <= 32, here, 'technical metric/reason list exceeds page bound')
            if key in ('reasons', 'incomplete_reasons') and isinstance(item, list):
                _require(len(item) == len(set(item)), here, 'duplicate reason')
            _technical_bounds(item, here)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _technical_bounds(item, f'{path}[{index}]')


def _technical_checked(kind, value):
    checked = object_value(value)
    if checked.get('schema') != _TELEMETRY_IDS[kind] or checked.get('contract_set') != CONTRACT_SET:
        raise ContractError('$: unsupported technical telemetry envelope', 'unsupported_format')
    return _technical_definition(_TELEMETRY_ROOTS[kind], checked)


def _technical_ref(value, kind, path):
    checked = _context_definition('FileRef', value, path)
    _file(checked, _TELEMETRY_IDS[kind], path)
    _require(checked['media_type'] == 'application/json', path, 'technical reference requires application/json')
    return checked


def _source_key(identity, source):
    import hashlib
    return hashlib.sha256(encode(dict(identity=identity, source=source))).hexdigest()


def _unique(rows, key, path):
    keys = [key(row) for row in rows]
    _require(len(keys) == len(set(keys)), path, 'duplicate technical key')


def _measurement(value, path, *, forecast=False):
    measured = value['status'] == ('forecast' if forecast else 'measured')
    _require((value['value'] is not None) == measured, path+'.value', 'status and value availability differ')
    _require(measured or bool(value['reason']), path+'.reason', 'unavailable measurement requires reason')


def _source_cursor(value, path):
    _require(value['source_key'] == _source_key(value['identity'], value['source']), path+'.source_key', 'source digest differs from exact tuple')
    _same_owner(value, value['cursor'], path+'.cursor')
    binding = value['binding']
    if binding['status'] == 'bound':
        _require(all(binding[k] is not None for k in ('state','invocation','evidence')) and binding['reason'] is None,
                 path+'.binding', 'bound source requires exact state/invocation/evidence')
        _require(binding['state']['identity'] == value['identity'], path+'.binding.state', 'source state identity differs')
        _file(binding['state']['manifest'], 'qcl-negf.result-manifest.v1', path+'.binding.state.manifest')
    else:
        _require(all(binding[k] is None for k in ('state','invocation','evidence')) and bool(binding['reason']),
                 path+'.binding', 'unbound source must preserve unknown state with reason')
    if value['producer_health'] is None:
        _require(bool(value['health_reason']), path+'.health_reason', 'unknown producer health requires reason')
    else:
        _phase_health(value['producer_health'], path+'.producer_health')


def _aggregate(value, path):
    _require(int(value['first_sequence']) <= int(value['last_sequence']), path, 'aggregate bounds reversed')
    first, last = value['first_core_sequence'], value['last_core_sequence']
    _require((first is None) == (last is None) and (first is None or int(first) <= int(last)), path, 'Core bounds differ or reverse')
    _aggregate_time_bounds(value['time_bounds'], value['call_count'], path+'.time_bounds')
    _unique_metrics(value['metrics'], path+'.metrics')
    for i, metric in enumerate(value['metrics']):
        here = f'{path}.metrics[{i}]'
        measured, unavailable = int(metric['measured_calls']), int(metric['unavailable_calls'])
        _require(measured+unavailable == int(value['call_count']), here, 'metric call coverage differs')
        _require(measured != 0 or metric['sum'] is None, here+'.sum', 'zero measured calls require null sum')
        if unavailable or (measured and metric['sum'] is None):
            _require(bool(metric['reasons']), here+'.reasons', 'unavailable/overflow sum requires reason')


def _cpu_allocation(value, path):
    valid, wall = int(value['valid_intervals']), value['covered_wall_seconds']
    _require(valid <= max(0, int(value['samples'])-1), path, 'more intervals than endpoints')
    _require(int(value['coarse_intervals']) <= valid, path+'.coarse_intervals', 'coarse intervals exceed valid')
    _require(value['coarse_wall_seconds']+value['fine_resolution_wall_seconds'] == wall, path, 'resolution wall totals differ')
    if valid == 0:
        _require(all(value[k] is None for k in ('cpu_seconds','allocated_cpu_seconds','observed_capacity_cpu_seconds')) and bool(value['cpu_unavailable_reason']), path, 'no measured CPU interval requires null and reason')
        _require(wall == 0, path+'.covered_wall_seconds', 'zero stable intervals cannot cover measured wall')
    else:
        _require(wall > 0 and value['cpu_seconds'] is not None, path, 'stable interval requires measured CPU and positive wall')
    if value['allocated_cpu_seconds'] is None or value['observed_capacity_cpu_seconds'] is None:
        _require(bool(value['capacity_unavailable_reason']) or valid == 0, path, 'unknown capacity requires reason')
    first, last = value['first_sample_monotonic_ns'], value['last_sample_monotonic_ns']
    observed = (int(last)-int(first))/1e9 if first is not None and last is not None else None
    _require(observed is None or observed >= 0, path, 'sample clocks reversed')
    _require(value['observed_window_seconds'] == observed, path+'.observed_window_seconds', 'observed clock window differs')
    for field, numerator, denominator in (
        ('fraction_of_observed_window_covered', wall, observed),
        ('mean_busy_logical_cpus', value['cpu_seconds'], wall),
        ('fraction_of_allocated_cpu', value['cpu_seconds'], value['allocated_cpu_seconds']),
        ('fraction_of_observed_capacity', value['cpu_seconds'], value['observed_capacity_cpu_seconds'])):
        expected = numerator/denominator if numerator is not None and denominator is not None and denominator > 0 else None
        _require(value[field] == expected, path+'.'+field, 'ratio differs from known numerator/positive denominator')


_CPU_ROLLUP_COUNTS = ('valid_intervals', 'missing_samples', 'discontinuous_intervals')
_CPU_ROLLUP_VALUES = ('cpu_seconds', 'allocated_cpu_seconds', 'observed_capacity_cpu_seconds')


def _cpu_finite_sum(values):
    """One finite Float64 metadata sum; overflow remains unavailable, never zero."""
    import math
    try:
        # Negative terms first avoid a gratuitous intermediate overflow in a
        # same-session cumulative-minus-local delta with large finite counters.
        total = math.fsum(sorted(values))
        return total if math.isfinite(total) else None
    except OverflowError:
        return None


def _cpu_local_rollup(coverage):
    rows = coverage['allocations']
    local = {key: sum(int(row[key]) for row in rows) for key in _CPU_ROLLUP_COUNTS}
    local['covered_wall_seconds'] = _cpu_finite_sum([row['covered_wall_seconds'] for row in rows])
    _require(local['covered_wall_seconds'] is not None, '$.cpu_coverage', 'local covered wall sum overflows finite representation')
    contributing = [row for row in rows if int(row['valid_intervals']) > 0]
    overflow = set()
    for key in _CPU_ROLLUP_VALUES:
        # No stable interval is no measurement, not a measured zero interval.
        if not contributing or any(row[key] is None for row in contributing):
            local[key] = None
        else:
            local[key] = _cpu_finite_sum([row[key] for row in contributing])
            if local[key] is None:
                overflow.add(key)
    return local, overflow


def _cpu_rollup_relation(totals, expected, overflow, *, exact):
    for key in _CPU_ROLLUP_COUNTS:
        actual = int(totals[key])
        _require(actual == expected[key] if exact else actual >= expected[key],
                 '$.cpu_totals.'+key, 'cumulative count differs from supplied allocation/baseline totals')
    wall = totals['covered_wall_seconds']
    _require(wall == expected['covered_wall_seconds'] if exact else wall >= expected['covered_wall_seconds'],
             '$.cpu_totals.covered_wall_seconds', 'covered wall differs from supplied allocation/baseline totals')
    for key in _CPU_ROLLUP_VALUES:
        measurement = totals[key]
        actual, wanted = measurement['value'], expected[key]
        if exact or (wanted is None and expected['valid_intervals'] > 0):
            _require(actual == wanted, '$.cpu_totals.'+key, 'cumulative measurement differs from supplied allocation/baseline totals')
        elif wanted is not None and actual is not None:
            _require(actual >= wanted, '$.cpu_totals.'+key, 'cumulative measurement is below supplied local coverage')
        if key in overflow:
            _require(measurement['status']=='error' and 'overflow' in measurement['reason'],
                     '$.cpu_totals.'+key, 'aggregation overflow requires explicit error/null/reason')


def _cpu_commit_rollup(summary, previous_summary, same_session):
    local, overflow = _cpu_local_rollup(summary['cpu_coverage'])
    if previous_summary is None:
        _cpu_rollup_relation(summary['cpu_totals'], local, overflow, exact=True)
        return
    prior = previous_summary['cpu_totals']
    prior_local, _ = _cpu_local_rollup(previous_summary['cpu_coverage'])
    expected = {}
    for key in (*_CPU_ROLLUP_COUNTS, 'covered_wall_seconds'):
        if same_session:
            _require(local[key]>=prior_local[key], '$.cpu_coverage.'+key, 'same-session local cumulative coverage decreased')
        if key == 'covered_wall_seconds':
            terms = [prior[key], local[key]]
            if same_session:
                terms.append(-prior_local[key])
            expected[key] = _cpu_finite_sum(terms)
            _require(expected[key] is not None, '$.cpu_totals.'+key, 'covered wall rollup overflows finite representation')
        else:
            expected[key] = int(prior[key])+local[key]-(prior_local[key] if same_session else 0)
    for key in _CPU_ROLLUP_VALUES:
        before, after = prior[key]['value'], summary['cpu_totals'][key]['value']
        _require(before is None or after is None or after >= before,
                 '$.cpu_totals.'+key, 'cumulative measured CPU/capacity decreased')
        if same_session:
            before_local, after_local = prior_local[key], local[key]
            _require(before_local is None or after_local is None or after_local >= before_local,
                     '$.cpu_coverage.'+key, 'same-session local measured CPU/capacity delta is negative')
        pieces = []
        unknown = False
        if int(prior['valid_intervals']) > 0:
            if prior[key]['value'] is None:
                unknown = True
                if prior[key]['status']=='error' and 'overflow' in prior[key]['reason']:
                    overflow.add(key)
            else:
                pieces.append(prior[key]['value'])
        if local['valid_intervals'] > 0:
            if local[key] is None:
                unknown = True
            else:
                pieces.append(local[key])
        if same_session and prior_local['valid_intervals'] > 0:
            if prior_local[key] is None:
                unknown = True
            else:
                pieces.append(-prior_local[key])
        if unknown or not pieces:
            expected[key] = None
        else:
            expected[key] = _cpu_finite_sum(pieces)
            if expected[key] is None:
                overflow.add(key)
    _cpu_rollup_relation(summary['cpu_totals'], expected, overflow, exact=True)


def _phase_aggregate_key(row):
    a = row['aggregate']
    return (row['source_key'], row['representation'], a['stage'], a['phase'], a['status'], a['task_width'], a['counter_scope'])


def validate_telemetry_summary(value: object) -> Object:
    """Dispatch only by declared technical version; never infer version from fields."""
    if isinstance(value, dict) and value.get('schema') == _RETAINED_IDS['summary']:
        return _validate_telemetry_summary2(value)
    return _validate_telemetry_summary1(value)


def _validate_telemetry_summary1(value: object) -> Object:
    """Validate bounded technical declarations; no acceptance or file access."""
    value = _technical_checked('summary', value)
    _unique(value['source_cursors'], lambda r: r['source_key'], '$.source_cursors')
    for i, row in enumerate(value['source_cursors']):
        _source_cursor(row, f'$.source_cursors[{i}]')
    _unique(value['producer_phase_aggregates'], _phase_aggregate_key, '$.producer_phase_aggregates')
    for i, row in enumerate(value['producer_phase_aggregates']):
        _require(row['source_key'] == _source_key(row['identity'], row['source']), '$.producer_phase_aggregates', 'phase aggregate owner differs')
        _aggregate(row['aggregate'], f'$.producer_phase_aggregates[{i}].aggregate')
    _unique(value['span_aggregates'], lambda r: (r['phase'],r['timing_kind'],r['measurement_kind']), '$.span_aggregates')
    for row in value['span_aggregates']:
        _require(int(row['warmup_calls']) <= int(row['call_count']), '$.span_aggregates', 'warmup calls exceed calls')
        for key in ('duration_seconds','warmup_seconds'):
            _measurement(row[key], '$.span_aggregates.'+key)
    _unique(value['control_events'], lambda r:r['event'], '$.control_events')
    _unique(value['cpu_coverage']['allocations'], lambda r:r['allocation_id'], '$.cpu_coverage.allocations')
    _require(value['cpu_coverage']['temporal_resolution_target_seconds'] > 0, '$.cpu_coverage', 'positive resolution target required')
    for i, row in enumerate(value['cpu_coverage']['allocations']):
        _cpu_allocation(row, f'$.cpu_coverage.allocations[{i}]')
    for key in ('cpu_seconds','allocated_cpu_seconds','observed_capacity_cpu_seconds'):
        _measurement(value['cpu_totals'][key], '$.cpu_totals.'+key)
    local, overflow = _cpu_local_rollup(value['cpu_coverage'])
    _cpu_rollup_relation(value['cpu_totals'], local, overflow, exact=value['baseline'] is None)
    if int(value['cpu_totals']['valid_intervals']) == 0:
        _require(all(value['cpu_totals'][key]['value'] is None for key in _CPU_ROLLUP_VALUES),
                 '$.cpu_totals', 'zero intervals cannot imply measured zero CPU or capacity')
    for name, measurement in value['observer_self_cost'].items():
        if name != 'scope':
            _measurement(measurement, '$.observer_self_cost.'+name, forecast=name=='arrow_io_forecast_bytes')
    for key in ('coverage','retention','cpu_totals'):
        _require(not value[key]['incomplete'] or bool(value[key]['reasons']), '$.'+key+'.reasons', 'incomplete requires reason')
    if int(value['totals']['collector_dropped_rows']):
        _require(value['coverage']['incomplete'], '$.coverage', 'collector drops require incomplete coverage')
    if any(int(value['retention'][k]) for k in ('omitted_source_rows','omitted_resource_rows','omitted_span_rows')) or value['retention']['pinned_retention_refused']:
        _require(value['retention']['incomplete'], '$.retention', 'omission/pin refusal requires retention reason')
    for gap in value['coverage']['gaps']:
        first, last = gap['first_monotonic_ns'], gap['last_monotonic_ns']
        _require((first is None)==(last is None), '$.coverage.gaps', 'gap clock endpoints must be paired')
        if first is not None:
            _require(gap['clock_domain_id'] is not None and int(first)<=int(last), '$.coverage.gaps', 'gap clock domain missing or reversed')
        if gap['kind'] in ('collector_restart','detail_page_rotation'):
            _require(value['coverage']['incomplete'], '$.coverage', 'uncovered endpoint reset requires incomplete coverage')
    for omission in value['retention']['omissions']:
        _require(int(omission['first_row'])<int(omission['stop_row']), '$.retention.omissions', 'empty/reversed omission')
    d = value['durability']
    _require(0 < d['maximum_buffer_seconds'] <= 60, '$.durability.maximum_buffer_seconds', 'buffer cadence outside (0,60]')
    _require(int(d['maximum_synchronous_flush_rows']) == 2*int(d['maximum_staged_batch_rows']), '$.durability', 'synchronous row bound differs')
    _require(d['uncommitted_resource_batch_at_risk'] == (not value['closed']), '$.durability', 'closed/resource tail declaration differs')
    _require(value['science_window_policy']['period_seconds'] > 0, '$.science_window_policy.period_seconds', 'positive window period required')
    return value


def validate_telemetry_source_binding(value: object, *, expected_state: object,
        expected_transport: object, manifest: object, manifest_ref: object,
        source_transport: object, canonical_plan_ref: object,
        expected_producer_provenance: object) -> Object:
    """Match independently trusted producer contexts; never infer canonical aliases."""
    from .results import validate_manifest
    value = _technical_checked('source_binding', value)
    state = _context_definition('StateRef', expected_state, '$.expected_state')
    source = validate_manifest(manifest)
    reference = _context_definition('FileRef', manifest_ref, '$.manifest_ref')
    _file(reference, 'qcl-negf.result-manifest.v1', '$.manifest_ref')
    _require(reference['media_type']=='application/json', '$.manifest_ref', 'scientific manifest reference requires application/json')
    actual = dict(identity=source['identity'],state_id=source['state_id'],state_sequence=source['state_sequence'],manifest=reference)
    _require(value['selected_state']==state==actual, '$.selected_state', 'exact selected original scientific state required')
    _require(value['invocation']==source['invocation'], '$.invocation', 'actual original invocation differs')
    enclosing = _technical_definition('Transport', expected_transport, '$.expected_transport')
    original = _technical_definition('Transport', source_transport, '$.source_transport')
    _require(value['enclosing_transport']==enclosing and value['source_transport']==original, '$.source_transport', 'independent actual transports differ')
    plan = _technical_definition('PlanRef', canonical_plan_ref, '$.canonical_plan_ref')
    _require(enclosing['frozen_plan'] is not None and original['frozen_plan'] is not None, '$.canonical_plan', 'original frozen plan pins required')
    _require(value['canonical_plan']==plan==original['frozen_plan'] and plan['sha256']==state['identity']['plan_sha256'], '$.canonical_plan', 'direct original canonical frozen-plan bytes not proven')
    graph = _technical_definition('SourceGraph', expected_producer_provenance, '$.expected_producer_provenance')
    _require(value['producer_provenance']==graph, '$.producer_provenance', 'qualified producer source differs')
    if value['relation']=='produced':
        _require(enclosing==original, '$.relation', 'produced relation requires same actual transports')
    else:
        _require(enclosing['selection']!=original['selection'], '$.relation', 'borrowed relation requires original distinct transport')
    return value


def _commit_summary(commit, summary, reference):
    summary = _validate_telemetry_summary1(summary)
    reference = _technical_ref(reference, 'summary', '$.summary_ref')
    _require(commit['summary']==reference, '$.summary', 'exact verified summary reference required')
    for key in ('session','transport','generation','closed','baseline','source_cursors'):
        _require(commit[key]==summary[key], '$.'+key, 'commit/summary transaction differs')
    return summary


def _cursor_after(before, after):
    _same_owner(before, after, '$.source_cursors')
    _require(int(after['route_epoch'])>=int(before['route_epoch']), '$.source_cursors.route_epoch', 'route epoch reversed')
    if before['producer_health'] is not None and after['producer_health'] is not None:
        _health_after(before['producer_health'], after['producer_health'], '$.source_cursors.producer_health')


def _numeric_metric(value):
    return int(value['decimal']) if isinstance(value,dict) else value


def _merge_aggregate(left, right):
    """Combine only accepted source-scoped rows; input metrics remain explicit."""
    import math
    merged = object_value(left)
    merged['call_count'] = str(int(left['call_count'])+int(right['call_count']))
    for first, last in (('first_sequence','last_sequence'),('first_core_sequence','last_core_sequence')):
        starts = [int(r[first]) for r in (left,right) if r[first] is not None]
        stops = [int(r[last]) for r in (left,right) if r[last] is not None]
        merged[first] = str(min(starts)) if starts else None
        merged[last] = str(max(stops)) if stops else None
    a, b = left['time_bounds'],right['time_bounds']
    clocks = object_value(a)
    for k in ('measured_calls','unavailable_calls'):
        clocks[k] = str(int(a[k])+int(b[k]))
    for name, op in (('min_start_monotonic_ns',min),('max_end_monotonic_ns',max)):
        vals = [int(r[name]) for r in (a,b) if r[name] is not None]
        clocks[name] = str(op(vals)) if vals else None
    clocks['reasons'] = sorted(set(a['reasons']+b['reasons']))
    merged['time_bounds'] = clocks
    left_metrics = {(m['name'],m['unit']):m for m in left['metrics']}
    right_metrics = {(m['name'],m['unit']):m for m in right['metrics']}
    _require(set(left_metrics)==set(right_metrics), '$.producer_phase_aggregates.metrics',
             'unlike metric profiles require separate detail pages; no unit conversion/default')
    metrics = []
    for (name, unit), a in left_metrics.items():
        b = right_metrics[(name,unit)]
        parts = [a,b]
        if a['sum'] is not None and b['sum'] is not None:
            _require(isinstance(a['sum'],dict)==isinstance(b['sum'],dict),
                     '$.producer_phase_aggregates.metrics.sum', 'native integer and Float64 metric profiles differ')
        metric = dict(name=name,unit=a['unit'],sum=None,
            measured_calls=str(int(a['measured_calls'])+int(b['measured_calls'])),
            unavailable_calls=str(int(a['unavailable_calls'])+int(b['unavailable_calls'])),
            reasons=sorted(set(a['reasons']+b['reasons'])))
        measured = [r for r in parts if int(r['measured_calls'])]
        if measured and all(r['sum'] is not None for r in measured):
            vals = [r['sum'] for r in measured]
            if len(vals)==1:
                metric['sum'] = vals[0]
            elif all(isinstance(v,dict) for v in vals):
                total = sum(_numeric_metric(v) for v in vals)
                if -(2**63)<=total<2**63:
                    metric['sum'] = dict(kind='integer',type='Int64',decimal=str(total))
                else:
                    metric['reasons'] = sorted(set(metric['reasons']+['counter_overflow']))
            else:
                try:
                    total = _numeric_metric(vals[0])+_numeric_metric(vals[1])
                    finite = math.isfinite(total)
                except OverflowError:
                    finite = False
                if finite:
                    metric['sum'] = total
                else:
                    metric['reasons'] = sorted(set(metric['reasons']+['counter_overflow']))
        metrics.append(metric)
    merged['metrics'] = metrics
    return merged


def _diagnostic_aggregate(row):
    """Only actual end metrics, with unavailable clocks never reconstructed."""
    metrics=[]
    for m in row['metrics']:
        name = 'process_cpu_seconds' if m['name']=='cpu_seconds' else m['name']
        if name not in _UNITS:continue
        v=m['value']
        numeric = type(v) in (int,float) or isinstance(v,dict) and v.get('kind')=='integer'
        allowed_units = ('B','bytes') if name=='allocated_bytes' else ('1','') if name=='gc_count' else ('s',)
        measured = m['measurement_status']=='measured' and numeric and m['unit'] in allowed_units
        metrics.append(dict(name=name,unit=m['unit'],sum=v if measured else None,
            measured_calls='1' if measured else '0',unavailable_calls='0' if measured else '1',
            reasons=[] if measured else [m['reason'] or ('metric_type_or_unit_invalid' if m['measurement_status']=='measured' else 'producer_metric_unavailable')]))
    def clock(name):
        metric = next((m for m in row['metrics'] if m['name']==name),None)
        if metric and metric['measurement_status']=='measured' and isinstance(metric['value'],dict) and metric['value'].get('type')=='Int64' and metric['unit']=='ns':
            n=int(metric['value']['decimal'])
            if n>=0:return n
        return None
    start,end=clock('start_monotonic_ns'),clock('end_monotonic_ns')
    valid=start is not None and end is not None and start<=end
    producer=next((m for m in row['metrics'] if m['name']=='producer_monotonic_ns'),None)
    mismatch=producer is not None and producer['measurement_status']=='measured' and clock('producer_monotonic_ns')!=end
    valid=valid and not mismatch
    reason='producer_clock_mismatch' if mismatch else 'producer_clock_missing' if start is None or end is None else 'producer_clock_reversed'
    return dict(kind='aggregate',stage=row['stage'],phase=row['label'],status=row['status'],
        task_width=None,counter_scope='process_inclusive_delta_on_end',first_sequence=row['sequence'],last_sequence=row['sequence'],
        first_core_sequence=row['core_sequence'],last_core_sequence=row['core_sequence'],call_count='1',metrics=metrics,
        time_bounds=dict(min_start_monotonic_ns=str(start) if valid else None,max_end_monotonic_ns=str(end) if valid else None,
        measured_calls='1' if valid else '0',unavailable_calls='0' if valid else '1',
        reasons=[] if valid else [reason]))


def validate_telemetry_commit(value: object, *, summary: object, summary_ref: object,
        previous: object | None = None, previous_ref: object | None = None,
        previous_summary: object | None = None, previous_summary_ref: object | None = None,
        phase_contexts: object = (), resume_contexts: object = (),
        catalog: object | None = None, previous_catalog: object | None = None) -> Object:
    """One bounded accepted delta with explicit predecessor/context refs, no traversal."""
    if isinstance(value, dict) and value.get('schema') == _RETAINED_IDS['commit']:
        return _validate_telemetry_commit2(value, summary=summary, summary_ref=summary_ref,
            previous=previous, previous_ref=previous_ref, previous_summary=previous_summary,
            previous_summary_ref=previous_summary_ref, phase_contexts=phase_contexts,
            resume_contexts=resume_contexts, catalog=catalog, previous_catalog=previous_catalog)
    _require(catalog is None and previous_catalog is None, '$.catalog', 'v1 rejects retained-v2 catalog contexts')
    value = _technical_checked('commit', value)
    checked_summary = _commit_summary(value, summary, summary_ref)
    prior_summary = None
    prior_cursors = {}
    same_session = False
    if value['previous'] is None:
        _require(previous is None and previous_ref is None and previous_summary is None and previous_summary_ref is None,
                 '$.previous', 'genesis cannot have predecessor contexts')
        _require(value['generation']=='1' and value['baseline'] is None, '$.generation', 'genesis requires generation1/no baseline')
    else:
        _require(all(x is not None for x in (previous,previous_ref,previous_summary,previous_summary_ref)), '$.previous', 'all predecessor content/reference contexts required')
        prior = _technical_checked('commit', previous)
        pref = _technical_ref(previous_ref,'commit','$.previous_ref')
        prior_summary = _commit_summary(prior,previous_summary,previous_summary_ref)
        _require(value['previous']==pref and int(value['generation'])==int(prior['generation'])+1, '$.previous', 'predecessor/ref/generation differs')
        same_session = value['session']['source']['session_id']==prior['session']['source']['session_id']
        if same_session:
            _require(not prior['closed'], '$.closed', 'closed collector session cannot append')
            for key in ('session','transport','baseline'):
                _require(value[key]==prior[key], '$.'+key, 'session binding changed')
        else:
            _require(prior['closed'], '$.previous.closed', 'rotation requires closed prior page')
            _require(value['transport']==prior['transport'], '$.transport', 'rotation changed enclosing transport')
            _require(value['baseline']==dict(commit=pref,summary=previous_summary_ref), '$.baseline', 'rotation baseline differs')
        prior_cursors = {r['source_key']:r for r in prior['source_cursors']}
    _require(isinstance(resume_contexts,(tuple,list)) and len(resume_contexts)<=16, '$.resume_contexts', 'bounded resume contexts required')
    for context in resume_contexts:
        _require(isinstance(context,dict) and set(context)=={'commit','commit_ref','summary','summary_ref'}, '$.resume_contexts', 'closed resume context required')
        c = _technical_checked('commit',context['commit'])
        _technical_ref(context['commit_ref'],'commit','$.resume_contexts.commit_ref')
        _commit_summary(c,context['summary'],context['summary_ref'])
        _require(value['baseline'] is not None and int(c['generation'])<int(value['generation']), '$.resume_contexts', 'resume needs older retained baseline evidence')
        matches = [r for r in c['source_cursors'] if r['source_key'] not in prior_cursors and any(r['source_key']==a['source_key'] for a in value['source_cursors'])]
        _require(bool(matches), '$.resume_contexts', 'unmatched/duplicate resume context')
        for row in matches:
            prior_cursors[row['source_key']] = row
    _require(isinstance(phase_contexts,(tuple,list)) and len(phase_contexts)<=128, '$.phase_contexts', 'bounded phase contexts required')
    contexts = {}
    for context in phase_contexts:
        _require(isinstance(context,dict) and set(context)=={'publication','publication_ref','segment','segment_ref'}, '$.phase_contexts', 'closed phase context required')
        k = encode(context['publication_ref'])
        _require(k not in contexts, '$.phase_contexts', 'duplicate publication context')
        contexts[k] = context
    used = set(); progress = {k:r['cursor'] for k,r in prior_cursors.items()}
    delta = dict(accepted_source_rows=0,accepted_aggregate_calls=0,accepted_diagnostic_events=0,coalesced_source_events=0)
    sources = {r['source_key']:r for r in value['source_cursors']}
    projected_rows = []
    for index, ar in enumerate(value['accepted_ranges']):
        path = f'$.accepted_ranges[{index}]'
        context = contexts.get(encode(ar['publication']))
        _require(context is not None, path, 'exact original phase context required')
        used.add(encode(ar['publication']))
        cursor = validate_phase_cursor(ar['cursor'],**context)
        segment = context['segment']; source_key = _source_key(segment['identity'],segment['source'])
        _require(source_key==ar['source_key'] and ar['segment']==context['segment_ref'] and ar['mode']==segment['mode'], path, 'accepted range source/segment/mode differs')
        _require(source_key in sources, path, 'range has no transaction source cursor')
        _same_owner(sources[source_key],cursor,path)
        first, stop = int(ar['first_row']),int(ar['stop_row'])
        _require(0<=first<stop<=len(segment['rows']) and int(cursor['next_row'])==stop, path, 'accepted physical row range differs')
        old = progress.get(source_key)
        if old is not None and old['segment']==ar['segment']:
            _require(first==int(old['next_row']) and old['publication']==ar['publication'], path, 'range overlaps/skips durable physical prefix')
        else:
            _require(first==0, path, 'new segment must start at physical row0')
            if old is not None:
                proof = contexts.get(encode(old['publication']))
                _require(proof is not None, path, 'old segment physical completion proof required')
                validate_phase_cursor(old, **proof)
                _require(int(old['next_row'])==len(proof['segment']['rows']), path, 'old physical segment tail not accepted')
                used.add(encode(old['publication']))
                _same_owner(proof['publication'],context['publication'],path)
                _require(context['publication']['previous']==old['publication'] and int(old['last_sequence'])<int(context['publication']['first_sequence']), path, 'new publication not adjacent to accepted cursor')
        rp, rs = ar['retained_publication'],ar['retained_segment']
        _require((rp is None)==(rs is None), path, 'raw retained refs must be paired')
        if rp is not None:
            for local, original in ((rp,ar['publication']),(rs,ar['segment'])):
                _require(all(local[k]==original[k] for k in ('bytes','sha256','media_type','schema')), path, 'retained raw bytes differ')
        else:
            _require(any(o['source_key']==source_key and o['segment']==ar['segment'] and o['first_row']==ar['first_row'] and o['stop_row']==ar['stop_row'] for o in checked_summary['retention']['omissions']), path, 'omitted raw range needs explicit exact omission')
        delta['accepted_source_rows'] += stop-first
        rows = segment['rows'][first:stop]
        if ar['mode']=='normal':
            delta['accepted_aggregate_calls'] += sum(int(r['call_count']) for r in rows)
            projected_rows.extend((source_key,segment,'normal_aggregate',r) for r in rows)
        else:
            delta['accepted_diagnostic_events'] += len(rows)
            projected_rows.extend((source_key,segment,'diagnostic_end_projection',_diagnostic_aggregate(r)) for r in rows if r['action']=='phase_end')
        if stop==len(segment['rows']):
            delta['coalesced_source_events'] += int(segment['coalesced_events'])
        progress[source_key] = cursor
    _require(used==set(contexts), '$.phase_contexts', 'extraneous original context')
    for key, row in sources.items():
        _require(key in progress and row['cursor']==progress[key], '$.source_cursors', 'cursor not justified by accepted range or explicit baseline')
        if key in prior_cursors:
            _cursor_after(prior_cursors[key],row)
    for key, amount in delta.items():
        before = int(prior_summary['totals'][key]) if prior_summary else 0
        _require(int(checked_summary['totals'][key])==before+amount, '$.totals.'+key, 'accepted delta differs from cumulative totals')
    for table in ('spans','resources','control_events'):
        total = int(checked_summary['totals']['rows'][table]); local = int(checked_summary['rows'][table])
        prior_total = int(prior_summary['totals']['rows'][table]) if prior_summary else 0
        prior_local = int(prior_summary['rows'][table]) if prior_summary and same_session else 0
        _require(total==prior_total+local-prior_local and local>=prior_local, '$.totals.rows.'+table, 'table row totals/baseline counted incorrectly')
    _cpu_commit_rollup(checked_summary, prior_summary, same_session)
    expected = {}
    if same_session:
        for phase in prior_summary['producer_phase_aggregates']:
            expected[_phase_aggregate_key(phase)] = object_value(phase)
    for key, segment, representation, row in projected_rows:
        phase = dict(source_key=key,identity=segment['identity'],source=segment['source'],
                     representation=representation,aggregate=row)
        phase_key = _phase_aggregate_key(phase)
        if phase_key in expected:
            phase = dict(phase,aggregate=_merge_aggregate(expected[phase_key]['aggregate'],row))
        expected[phase_key] = phase
    actual = {_phase_aggregate_key(row):row for row in checked_summary['producer_phase_aggregates']}
    _require(set(actual)==set(expected), '$.producer_phase_aggregates', 'accepted cumulative phase keys differ')
    for key in expected:
        _require(encode(actual[key])==encode(expected[key]), '$.producer_phase_aggregates', 'summary differs from accepted cumulative phase projection')
    return value


def validate_telemetry_pointer(value: object, *, commit: object, commit_ref: object) -> Object:
    """Select exactly the supplied immutable commit; never consult index/latest."""
    if isinstance(value, dict) and value.get('schema') == _RETAINED_IDS['pointer']:
        value = _retained_checked('pointer', value)
        content = _retained_checked('commit', commit)
        reference = _retained_ref(commit_ref, 'commit', '$.commit_ref')
        _require(value['commit'] == reference, '$.commit', 'pointer differs from supplied exact v2 commit reference')
        paths = [content['summary']['path'], content['catalog']['path']]
        paths.extend(row['ref']['path'] for k in ('introduced', 'removed') for row in content['window_delta'][k])
        paths.extend(ref['path'] for ref in content['window_delta']['pending_unlink'])
        if content['previous'] is not None: paths.extend(r['path'] for r in content['previous'].values())
        _require(reference['path'] not in paths, '$.commit.path', 'commit aliases required transaction metadata')
        return value
    value = _technical_checked('pointer',value)
    content = _technical_checked('commit',commit)
    reference = _technical_ref(commit_ref,'commit','$.commit_ref')
    _require(value['commit']==reference,'$.commit','pointer differs from supplied exact commit reference')
    _require(reference['path']!=content['summary']['path'] and (content['previous'] is None or reference['path']!=content['previous']['path']), '$.commit.path', 'commit rebinds itself or its summary path')
    return value


def _embedded_technical(row, kind, expected, reference):
    import hashlib
    from .messages import decode
    raw = row['raw_utf8'].encode('utf-8')
    _require(row['ref']==reference, '$.'+kind+'.ref', 'embedded full reference differs')
    _require(len(raw)==int(reference['bytes']) and hashlib.sha256(raw).hexdigest()==reference['sha256'], '$.'+kind+'.raw_utf8', 'original embedded bytes differ from exact pin')
    parsed = decode(raw, maximum=1024*1024)
    _require(encode(parsed)==encode(object_value(expected)), '$.'+kind, 'supplied decoded context differs from original raw bytes')
    return parsed, len(raw)


def validate_telemetry_binding(value: object, *, expected_state: object,
        expected_transport: object, commit: object, commit_ref: object,
        summary: object, summary_ref: object, source_binding: object,
        source_binding_ref: object, manifest: object, manifest_ref: object,
        source_transport: object, canonical_plan_ref: object,
        expected_producer_provenance: object) -> Object:
    """Verify exact retained close bytes and independently proven scientific source."""
    if isinstance(value, dict) and value.get('schema') == _RETAINED_IDS['binding']:
        return _validate_telemetry_binding2(value, expected_state=expected_state,
            expected_transport=expected_transport, commit=commit, commit_ref=commit_ref,
            summary=summary, summary_ref=summary_ref, source_binding=source_binding,
            source_binding_ref=source_binding_ref, manifest=manifest, manifest_ref=manifest_ref,
            source_transport=source_transport, canonical_plan_ref=canonical_plan_ref,
            expected_producer_provenance=expected_producer_provenance)
    value = _technical_checked('binding',value)
    _require(len(encode(value))<=1024*1024, '$', 'retained binding exceeds metadata cap')
    cref = _technical_ref(commit_ref,'commit','$.commit_ref')
    sref = _technical_ref(summary_ref,'summary','$.summary_ref')
    bref = _technical_ref(source_binding_ref,'source_binding','$.source_binding_ref')
    roots=[];size=0
    for key,ref in (('commit',cref),('summary',sref),('source_binding',bref)):
        parsed,count = _embedded_technical(value[key],key,locals()[key],ref)
        roots.append(parsed);size+=count
    _require(size<=1024*1024, '$', 'aggregate embedded raw bytes exceed cap')
    pending=[value,*roots];count=0
    while pending:
        item=pending.pop();count+=1
        _require(count<=4096, '$', 'aggregate retained metadata object cap exceeded')
        if isinstance(item,dict):pending.extend(item.values())
        elif isinstance(item,list):pending.extend(item)
    c = _technical_checked('commit',commit)
    validate_telemetry_pointer(dict(schema=TELEMETRY_POINTER_SCHEMA,contract_set=CONTRACT_SET,commit=cref),commit=c,commit_ref=cref)
    s = _commit_summary(c,summary,sref)
    _require(c['closed'] and s['closed'], '$.commit.closed', 'fixed binding requires returned closed session')
    proof = validate_telemetry_source_binding(source_binding,expected_state=expected_state,
        expected_transport=expected_transport,manifest=manifest,manifest_ref=manifest_ref,
        source_transport=source_transport,canonical_plan_ref=canonical_plan_ref,
        expected_producer_provenance=expected_producer_provenance)
    _require(value['selected_state']==proof['selected_state'] and value['transport']==c['transport']==proof['enclosing_transport'], '$.selected_state', 'retained selection/transport differs')
    for row in c['source_cursors']:
        binding=row['binding']
        if binding['state']==value['selected_state']:
            _require(binding['evidence']==bref and binding['invocation']==proof['invocation'], '$.source_cursors.binding', 'selected phase source evidence differs')
    status=value['capture_status']
    _require(status['performance_status']=='available' or bool(status['reason']), '$.capture_status.reason', 'unavailable capture requires reason')
    _require(status['scalar_live_route']!='unavailable' or bool(status['scalar_live_reason']), '$.capture_status.scalar_live_reason', 'unavailable scalar route requires reason')
    return value


# Explicit retained-technical v2. Legacy definitions and branches above remain v1.
_RETAINED_IDS = {kind: 'qcl-negf.telemetry-'+kind+'.v2'
                 for kind in ('commit', 'summary', 'pointer', 'binding')}
_RETAINED_IDS.update(catalog='qcl-negf.telemetry-catalog.v3', index='qcl-negf.performance-index.v3')
_RETAINED_ROOTS = dict(commit='TelemetryCommit2', summary='TelemetrySummary2',
    pointer='TelemetryPointer2', binding='TelemetryBinding2', catalog='RetainedCatalog3', index='PerformanceIndex3')
_COST_FLOATS = ('probe_seconds', 'read_seconds', 'hash_seconds', 'parse_validate_seconds',
    'serialize_seconds', 'parquet_seconds', 'flush_sync_seconds', 'process_cpu_seconds')
_PHASE_COUNTS = ('allocated_bytes', 'gc_count')
_UINT64_MAX = (1 << 64)-1


def _retained_budget(*values):
    """Bound supplied decoded metadata; actual original byte admission is caller-owned."""
    pending = list(values); nodes = 0
    while pending:
        item = pending.pop(); nodes += 1
        _require(nodes <= 16384, '$', 'retained metadata object cap exceeded')
        if isinstance(item, dict): pending.extend(item.values())
        elif isinstance(item, (tuple, list)): pending.extend(item)
    _require(sum(len(encode(v)) for v in values) <= 1024*1024, '$', 'combined retained metadata byte cap exceeded')


def _retained_checked(kind, value):
    checked = object_value(value)
    if checked.get('schema') != _RETAINED_IDS[kind] or checked.get('contract_set') != CONTRACT_SET:
        raise ContractError('$: unsupported retained technical envelope', 'unsupported_format')
    _retained_budget(checked)
    return _technical_definition(_RETAINED_ROOTS[kind], checked)


def _retained_ref(value, kind, path):
    checked = _context_definition('FileRef', value, path)
    _file(checked, _RETAINED_IDS[kind], path)
    _require(checked['media_type'] == 'application/json', path, 'retained reference requires application/json')
    return checked


def _count_sum(values, path):
    total = sum(values)
    _require(0 <= total <= _UINT64_MAX, path, 'UInt64 accumulation overflow before update')
    return total


def _classified(value):
    return sum(int(value[k]) for k in ('covered', 'unavailable', 'overflow'))


def _accumulation(value, path, *, contributions=None):
    counts = [int(value[k]) for k in ('covered', 'unavailable', 'overflow')]
    total = _count_sum(counts, path)
    _require((value['known'] is None) == (counts[0] == 0), path+'.known', 'known subtotal requires covered contributions only')
    if counts[1] or counts[2]:
        _require(bool(value['reasons']), path+'.reasons', 'unknown/overflow contributions require reason')
    _require('no_observations' not in value['reasons'] or total == 0, path+'.reasons', 'no_observations requires zero contributions')
    if contributions is not None:
        _require(total == contributions, path, 'classified contribution count differs from interval/calls')
    return total


def _accumulated(left, right, *, count, path):
    """Known subtotal and classifications are separate; missing work never disappears."""
    counts = {k: str(_count_sum((int(left[k]), int(right[k])), path+'.'+k))
              for k in ('covered', 'unavailable', 'overflow')}
    parts = [v['known'] for v in (left, right) if v['known'] is not None]
    if not parts:
        known = None
    elif count:
        known = str(_count_sum([int(v) for v in parts], path+'.known'))
    else:
        known = _cpu_finite_sum(parts)
        _require(known is not None, path+'.known', 'finite subtotal overflows before update')
    reasons = set(left['reasons']) | set(right['reasons'])
    if any(int(v) for v in counts.values()): reasons.discard('no_observations')
    return dict(known=known, **counts, reasons=sorted(reasons))


def _equal_accumulation(actual, expected, path):
    _require(all(actual[k] == expected[k] for k in ('known', 'covered', 'unavailable', 'overflow'))
             and set(actual['reasons']) == set(expected['reasons']), path, 'accumulation differs from exact disjoint merge')


def _empty_accumulation():
    return dict(known=None, covered='0', unavailable='0', overflow='0', reasons=[])


def _phase_key2(key):
    return encode(key)


def _phase_rollup2(value, path):
    keys = [_phase_key2(row['key']) for row in value['entries']]
    _require(keys == sorted(set(keys)), path+'.entries', 'phase keys must be unique canonical keys')
    for row in value['entries']:
        for label in ('stage', 'phase', 'status'):
            _require(len(row['key'][label].encode('utf-8')) <= 256, path+'.key.'+label, 'phase label exceeds UTF-8 byte bound')
    missing = set()
    for i, row in enumerate([*value['entries'], value['overflow']]):
        calls = int(row['call_count'])
        for key, metric in row['metrics'].items():
            _accumulation(metric, f'{path}[{i}].metrics.{key}', contributions=calls)
            if int(metric['unavailable']) or int(metric['overflow']): missing.update(metric['reasons'])
    _require(not missing or value['incomplete'] and missing <= set(value['reasons']), path, 'phase metric gaps require incomplete normalized reasons')
    if int(value['overflow']['call_count']):
        _require(value['incomplete'] and 'phase_key_limit' in value['reasons'], path+'.overflow', 'unclassified calls require explicit breakdown gap')
    _require(not value['incomplete'] or bool(value['reasons']), path+'.reasons', 'incomplete phase rollup requires reasons')


def _summary_cumulative2(value):
    cumulative = value['cumulative']; cost = cumulative['cost']; coverage = cumulative['coverage']
    totals = {_accumulation(v, '$.cumulative.cost.metrics.'+k) for k, v in cost['metrics'].items()}
    _require(len(totals) == 1, '$.cumulative.cost.metrics', 'metrics classify different completed operation counts')
    completed = next(iter(totals))
    _require(completed >= int(cost['position']['stop_operation']), '$.cumulative.cost.position', 'position exceeds cumulative completed operations')
    _phase_rollup2(cumulative['phases'], '$.cumulative.phases')
    _measurement(cumulative['max_observed_rss_bytes'], '$.cumulative.max_observed_rss_bytes')
    local = value['max_observed_rss_bytes']; observed = cumulative['max_observed_rss_bytes']['value']
    _require(local is None or observed is not None and int(observed) >= int(local), '$.cumulative.max_observed_rss_bytes', 'observed RSS maximum below local observation')
    _require(not coverage['incomplete'] or bool(coverage['reasons']), '$.cumulative.coverage', 'incomplete requires normalized reasons')
    _require('no_observations' not in coverage['reasons'] or completed == 0 and not any(int(row['call_count']) for row in cumulative['phases']['entries']) and int(cumulative['phases']['overflow']['call_count']) == 0,
             '$.cumulative.coverage.reasons', 'no_observations cannot erase real contributions')
    required = set()
    if cumulative['prior_capture'] == 'unimported': required.add('unimported_capture')
    if int(cost['uncovered_restarts']): required.add('collector_restart')
    if int(value['coverage']['capture_error_events']): required.add('capture_error')
    if int(value['totals']['collector_dropped_rows']): required.add('missing_observation')
    if value['coverage']['incomplete'] or value['coverage']['gaps']:
        evidence = set(coverage['reasons'])-{'no_observations', 'publication_tail', 'unimported_capture'}
        _require(coverage['incomplete'] and bool(evidence), '$.cumulative.coverage', 'local uncovered gap requires cumulative incomplete evidence')
    for metric in cost['metrics'].values():
        if int(metric['unavailable']) or int(metric['overflow']): required.update(metric['reasons'])
    if cumulative['phases']['incomplete']: required.update(cumulative['phases']['reasons'])
    if any(int(value['retention'][k]) for k in ('omitted_source_rows', 'omitted_resource_rows', 'omitted_span_rows')): required.add('retention_omission')
    if value['retention']['pinned_retention_refused']: required.add('pin_refused')
    _require(required <= set(coverage['reasons']) and (not required or coverage['incomplete']), '$.cumulative.coverage', 'cumulative unknown/gap evidence missing')
    _require(int(coverage['gap_events']) >= len(value['coverage']['gaps']), '$.cumulative.coverage.gap_events', 'cumulative gap count below local gaps')


def _commit_summary2(commit, summary, reference):
    summary = _validate_telemetry_summary2(summary)
    reference = _retained_ref(reference, 'summary', '$.summary_ref')
    _require(commit['summary'] == reference, '$.summary', 'exact supplied v2 summary reference required')
    for key in ('session', 'transport', 'generation', 'closed', 'source_cursors'):
        _require(commit[key] == summary[key], '$.'+key, 'commit/summary retained transaction differs')
    return summary


def _artifact_extent_key(extent):
    return (extent['source_key'], encode(extent['segment']), int(extent['first_row']), int(extent['stop_row']))


def _catalog_artifacts2(rows, path):
    keys = [(r['ref']['path'], r['ref']['sha256']) for r in rows]
    _require(keys == sorted(keys) and len({k[0] for k in keys}) == len(keys), path, 'artifact paths must be unique canonical order')
    intervals = {}
    for i, row in enumerate(rows):
        ref = row['ref']; here = f'{path}[{i}]'
        parquet = ref['media_type'] == 'application/vnd.apache.parquet'
        if parquet:
            _require(ref['schema'] == TELEMETRY_SCHEMA and row['table'] is not None and row['rows'] is not None and not row['accepted'], here, 'Parquet requires exact table/footer rows and no raw extents')
        else:
            _require(ref['media_type'] == 'application/json' and row['rows'] is None and row['table'] is None, here, 'metadata requires JSON and null table/rows')
            allowed = set(_RETAINED_IDS.values()) | {TELEMETRY_SOURCE_BINDING_SCHEMA, 'qcl-negf.producer-phase-segment.v1', 'qcl-negf.producer-phase-publication.v1'}
            _require(ref['schema'] in allowed, here+'.ref.schema', 'nontechnical artifact outside retained pruning inventory')
        _require(not row['accepted'] or ref['schema'] == _PHASE_SCHEMAS['segment'], here, 'only original retained phase segments carry extents')
        extent_keys = [_artifact_extent_key(e) for e in row['accepted']]
        _require(extent_keys == sorted(extent_keys), here+'.accepted', 'extent order is not canonical')
        for extent in row['accepted']:
            first, stop = int(extent['first_row']), int(extent['stop_row'])
            _require(first < stop, here+'.accepted', 'empty/reversed source extent')
            _require(all(ref[k] == extent['segment'][k] for k in ('bytes', 'sha256', 'media_type', 'schema')), here+'.accepted', 'retained segment bytes differ from original source')
            k = (extent['source_key'], extent['segment']['sha256'], extent['segment']['bytes'],
                 extent['segment']['schema'], extent['segment']['media_type'])
            for left, right in intervals.setdefault(k, []):
                _require(stop <= left or first >= right, here+'.accepted', 'source extent overlaps retained alias')
            intervals[k].append((first, stop))


def validate_telemetry_catalog(value: object, *, expected_transport: object) -> Object:
    """Validate v3 retained inventory declarations, never physical files or origin."""
    value = _retained_checked('catalog', value)
    expected = _technical_definition('Transport', expected_transport, '$.expected_transport')
    _require(value['transport'] == expected, '$.transport', 'catalog transport differs')
    _require(len(encode(value)) <= 65536, '$', 'catalog exceeds 64 KiB metadata ceiling')
    _catalog_artifacts2(value['artifacts'], '$.artifacts')
    return value


def validate_telemetry_index(value: object, *, expected_transport: object) -> Object:
    """Bounded v3 discovery membership; a supplied transaction pair is no lease."""
    value = _retained_checked('index', value)
    expected = _technical_definition('Transport', expected_transport, '$.expected_transport')
    _require(value['transport'] == expected, '$.transport', 'index transport differs')
    rows = value['retained']; keys = [encode(row) for row in rows]
    _require(keys == sorted(set(keys)), '$.retained', 'retained transaction references must be unique canonical pairs')
    paths = {}; pairs = {}
    for row in [value['current'], *rows]:
        token = encode(row['commit'])
        _require(token not in pairs or pairs[token] == row['summary'], '$.retained', 'one commit cannot select different summaries')
        pairs[token] = row['summary']
        _require(row['commit']['path'] != row['summary']['path'], '$.retained', 'transaction paths alias')
        for ref in row.values():
            _require(ref['path'] not in paths or paths[ref['path']] == ref, '$.retained', 'index path rebinds whole reference')
            paths[ref['path']] = ref
    return value


def _cost_merge2(value, summary, prior, prior_summary):
    delta = value['cost_delta']; roll = summary['cumulative']['cost']
    first, stop = int(delta['first_operation']), int(delta['stop_operation'])
    _require(first <= stop, '$.cost_delta', 'operation interval reversed')
    width = stop-first
    for k, metric in delta['metrics'].items():
        _accumulation(metric, '$.cost_delta.metrics.'+k, contributions=width)
    _require(width > 0 or int(delta['arrow_io_forecast_bytes']) == 0, '$.cost_delta.arrow_io_forecast_bytes', 'empty delta cannot carry forecast work')
    position = dict(observer_id=delta['observer_id'], stop_operation=delta['stop_operation'])
    _require(roll['position'] == position, '$.cumulative.cost.position', 'rollup position differs from completed operation delta')
    prior_roll = prior_summary['cumulative']['cost'] if prior_summary else None
    if prior_roll is None:
        _require(first == 0 and not delta['restart_gap'], '$.cost_delta', 'v2 genesis starts operation0 without imported restart')
        restarts = 0
    elif delta['observer_id'] == prior_roll['position']['observer_id']:
        _require(first == int(prior_roll['position']['stop_operation']) and not delta['restart_gap'], '$.cost_delta', 'same observer interval overlaps/skips or claims restart')
        _require(int(delta['as_of_monotonic_ns']) >= int(prior['cost_delta']['as_of_monotonic_ns']), '$.cost_delta.as_of_monotonic_ns', 'same observer clock reversed')
        restarts = int(prior_roll['uncovered_restarts'])
    else:
        _require(first == 0 and delta['restart_gap'], '$.cost_delta', 'new observer requires operation0 and explicit restart gap')
        restarts = _count_sum((int(prior_roll['uncovered_restarts']), 1), '$.cumulative.cost.uncovered_restarts')
    _require(int(roll['uncovered_restarts']) == restarts, '$.cumulative.cost.uncovered_restarts', 'restart coverage count differs')
    for k, current in delta['metrics'].items():
        before = prior_roll['metrics'][k] if prior_roll else _empty_accumulation()
        expected = _accumulated(before, current, count=k not in _COST_FLOATS, path='$.cumulative.cost.metrics.'+k)
        _equal_accumulation(roll['metrics'][k], expected, '$.cumulative.cost.metrics.'+k)
    expected_forecast = _count_sum((int(prior_roll['arrow_io_forecast_bytes']) if prior_roll else 0,
                                    int(delta['arrow_io_forecast_bytes'])), '$.cumulative.cost.arrow_io_forecast_bytes')
    _require(int(roll['arrow_io_forecast_bytes']) == expected_forecast, '$.cumulative.cost.arrow_io_forecast_bytes', 'forecast disjoint merge differs')


def _phase_contribution2(row):
    """Project one validated accepted normal/end row, including absent metric profiles."""
    calls = int(row['call_count']); metrics = {}
    for name, unit in _UNITS.items():
        candidates = [m for m in row['metrics'] if m['name'] == name]
        allowed = ('B', 'bytes') if name == 'allocated_bytes' else ('1', '') if name == 'gc_count' else ('s',)
        match = candidates[0] if len(candidates) == 1 and candidates[0]['unit'] in allowed else None
        if match is None:
            metrics[name] = dict(known=None, covered='0', unavailable=str(calls), overflow='0', reasons=['missing_observation'] if calls else [])
            continue
        measured, unavailable = int(match['measured_calls']), int(match['unavailable_calls'])
        known = _numeric_metric(match['sum']) if match['sum'] is not None else None
        overflow = measured if measured and known is None else 0
        covered = measured-overflow
        # The rollup fixes integer metrics to UInt64; negative/unrepresentable source
        # values remain explicit unavailable observations, never coerced measurements.
        invalid = known is not None and name in _PHASE_COUNTS and (type(known) is not int or not 0 <= known <= _UINT64_MAX)
        if invalid:
            unavailable += covered; covered = 0; known = None
        reasons = []
        if unavailable: reasons.append('missing_observation')
        if overflow: reasons.append('counter_overflow')
        metrics[name] = dict(known=str(known) if known is not None and name in _PHASE_COUNTS else known,
                             covered=str(covered), unavailable=str(unavailable), overflow=str(overflow), reasons=reasons)
    return dict(call_count=str(calls), metrics=metrics)


def _phase_merge2(summary, prior_summary, projected_rows):
    value = summary['cumulative']['phases']
    previous = prior_summary['cumulative']['phases'] if prior_summary else None
    expected = { _phase_key2(r['key']): object_value(r) for r in previous['entries']} if previous else {}
    actual = {_phase_key2(r['key']): r for r in value['entries']}
    overflow = object_value(previous['overflow']) if previous else dict(call_count='0', metrics={k:_empty_accumulation() for k in _UNITS})
    for _, _, representation, row in projected_rows:
        key = {k:row[k] for k in ('stage', 'phase', 'status', 'task_width', 'counter_scope')}
        key['representation'] = representation
        token = _phase_key2(key); contribution = _phase_contribution2(row)
        if token in expected or token in actual:
            target = expected.setdefault(token, dict(key=key, call_count='0', metrics={k:_empty_accumulation() for k in _UNITS}))
        else:
            target = overflow
        target['call_count'] = str(_count_sum((int(target['call_count']), int(contribution['call_count'])), '$.cumulative.phases.call_count'))
        for k in _UNITS:
            target['metrics'][k] = _accumulated(target['metrics'][k], contribution['metrics'][k], count=k in _PHASE_COUNTS, path='$.cumulative.phases.metrics.'+k)
    _require(set(actual) == set(expected), '$.cumulative.phases.entries', 'phase key evicted/relabelled or unaccepted key introduced')
    for token, wanted in expected.items():
        row = actual[token]
        _require(row['call_count'] == wanted['call_count'], '$.cumulative.phases.call_count', 'accepted phase calls differ')
        for k in _UNITS: _equal_accumulation(row['metrics'][k], wanted['metrics'][k], '$.cumulative.phases.metrics.'+k)
    _require(value['overflow']['call_count'] == overflow['call_count'], '$.cumulative.phases.overflow', 'unclassified accepted call count differs')
    for k in _UNITS: _equal_accumulation(value['overflow']['metrics'][k], overflow['metrics'][k], '$.cumulative.phases.overflow.metrics.'+k)
    if previous:
        _require(not previous['incomplete'] or value['incomplete'], '$.cumulative.phases.incomplete', 'phase gap must remain sticky')
        _require(set(previous['reasons'])-{'no_observations'} <= set(value['reasons']), '$.cumulative.phases.reasons', 'phase reasons lost')


def _extent_union2(extents):
    result = {}
    for extent in extents:
        segment = extent['segment']
        # Aliased locators never create a new physical source contribution.
        key = (extent['source_key'], segment['sha256'], segment['bytes'], segment['schema'], segment['media_type'])
        result.setdefault(key, []).append((int(extent['first_row']), int(extent['stop_row'])))
    for key, intervals in result.items():
        merged = []
        for first, stop in sorted(intervals):
            if merged and first <= merged[-1][1]: merged[-1] = (merged[-1][0], max(stop, merged[-1][1]))
            else: merged.append((first, stop))
        result[key] = merged
    return result


def _extent_size2(extents):
    return sum(stop-first for intervals in _extent_union2(extents).values() for first, stop in intervals)


def _catalog_window2(value, summary, catalog, prior, prior_summary, previous_catalog, summary_ref, previous_ref, previous_summary_ref):
    window = value['window_delta']; before = previous_catalog['artifacts'] if previous_catalog else []
    after = catalog['artifacts']
    old = {r['ref']['path']: r for r in before}; current = {r['ref']['path']: r for r in after}
    for field in ('introduced', 'removed'):
        _catalog_artifacts2(window[field], '$.window_delta.'+field)
    removed = {r['ref']['path']: r for r in window['removed']}
    introduced = {r['ref']['path']: r for r in window['introduced']}
    protected = [summary_ref, value['catalog']]
    new_paths = [summary_ref['path'], value['catalog']['path']]
    _require(len(set(new_paths)) == 2, '$.catalog', 'current summary and catalog paths alias')
    if prior:
        old_paths = {previous_ref['path'], previous_summary_ref['path'], prior['catalog']['path']}
        _require(not old_paths.intersection(new_paths), '$.summary', 'successor metadata reuses predecessor immutable path')
    protected.extend(ref for ar in value['accepted_ranges'] for ref in (ar['retained_publication'], ar['retained_segment']) if ref is not None)
    if value['transport']['frozen_plan'] is not None: protected.append(value['transport']['frozen_plan'])
    for row in value['contexts']['phase_context_refs']:
        for name in ('retained_publication_ref', 'retained_segment_ref'):
            ref = row[name]
            _require(ref['path'] in current and current[ref['path']]['ref'] == ref, '$.contexts', 'required raw context absent from exact retained catalog inventory')
            protected.append(ref)
    for pair in value['contexts']['resume_context_refs']: protected.extend(pair.values())
    if prior:
        protected.extend((previous_ref, previous_summary_ref, prior['catalog']))
        leaf = dict(ref=prior['catalog'], role='performance.provenance', table=None, rows=None, accepted=[])
        _require(current.get(prior['catalog']['path']) == leaf, '$.artifacts', 'successor must inventory exact previous catalog metadata leaf')
    protected_paths = {r['path'] for r in protected}
    # The current commit's reference is supplied only to pointer/binding. It cannot
    # already occur in the predecessor inventory; immutable no-reuse is caller-owned.
    _require(value['catalog']['path'] not in current, '$.catalog', 'catalog cannot contain self reference')
    expected = dict(old); gained = []; retired = []
    for path, row in removed.items():
        _require(old.get(path) == row and path not in protected_paths, '$.window_delta.removed', 'removal is not exact unprotected predecessor inventory')
        expected.pop(path); retired.extend(row['accepted'])
    for path, row in introduced.items():
        if path in old:
            prior_row = old[path]
            _require(path not in removed and row != prior_row and row['ref'] == prior_row['ref']
                and all(row[k] == prior_row[k] for k in ('role', 'table', 'rows')), '$.window_delta.introduced', 'introduced path rebinds immutable identity or duplicates before')
            old_extents = prior_row['accepted']; new_extents = row['accepted']
            _require(bool(new_extents), '$.window_delta.introduced', 'only accepted extents may update existing descriptor')
            union = _extent_union2([*old_extents, *new_extents])
            _require(union == _extent_union2(new_extents), '$.window_delta.introduced', 'accepted descriptor lost old physical extents')
            # Difference is represented by new accepted delta below; compare unions
            # and cardinalities without allocating rows proportional to row counters.
            gained.extend(new_extents)
        else:
            gained.extend(row['accepted'])
        expected[path] = row
    _require(expected == current, '$.artifacts', 'after differs from before minus removed plus introduced')
    retained_delta = [dict(source_key=a['source_key'], segment=a['segment'], first_row=a['first_row'], stop_row=a['stop_row'])
                      for a in value['accepted_ranges'] if a['retained_segment'] is not None]
    old_updated = [e for path in introduced if path in old for e in old[path]['accepted']]
    _require(_extent_union2(gained) == _extent_union2([*old_updated, *retained_delta])
        and _extent_size2(gained) == _extent_size2(old_updated)+_extent_size2(retained_delta),
        '$.window_delta.introduced', 'introduced extents are not exactly new accepted physical delta')
    extents = [e for row in after for e in row['accepted']]
    retained_rows = _extent_size2(extents)
    retention = summary['retention']; previous_retention = prior_summary['retention'] if prior_summary else None
    omitted_delta = sum(int(a['stop_row'])-int(a['first_row']) for a in value['accepted_ranges'] if a['retained_segment'] is None)
    omitted = (int(previous_retention['omitted_source_rows']) if previous_retention else 0)+_extent_size2(retired)+omitted_delta
    _require(int(retention['omitted_source_rows']) == omitted and int(retention['retained_source_rows']) == retained_rows,
             '$.retention', 'retained/omitted physical source counts differ')
    _require(retained_rows+omitted == int(summary['totals']['accepted_source_rows']), '$.retention', 'accepted rows lost or counted twice across retained window')
    for table, key in (('resources', 'omitted_resource_rows'), ('spans', 'omitted_span_rows')):
        increment = sum(int(r['rows']) for r in removed.values() if r['table'] == table)
        wanted = (int(previous_retention[key]) if previous_retention else 0)+increment
        _require(int(retention[key]) == wanted, '$.retention.'+key, 'removed Parquet rows not accounted exactly once')
        kept = sum(int(r['rows']) for r in after if r['table'] == table)
        _require(kept+wanted == int(summary['totals']['rows'][table]), '$.retention.'+key, 'Parquet retained/omitted rows differ from accepted table totals')
    _require(int(retention['retained_bytes']) == sum(int(r['ref']['bytes']) for r in after), '$.retention.retained_bytes', 'retained bytes differ from deduplicated whole inventory')
    eligible = [r['ref'] for r in removed.values()]
    if prior:
        eligible.extend(prior['window_delta']['pending_unlink'])
        if prior['previous'] is not None: eligible.extend(prior['previous'].values())
        eligible.extend(ref for row in prior['contexts']['phase_context_refs'] for k, ref in row.items() if k.startswith('retained_'))
        eligible.extend(ref for pair in prior['contexts']['resume_context_refs'] for ref in pair.values())
    pending = window['pending_unlink']; _unique(pending, lambda ref: ref['path'], '$.window_delta.pending_unlink')
    for ref in pending:
        allowed = set(_RETAINED_IDS.values()) | {TELEMETRY_SOURCE_BINDING_SCHEMA, *_PHASE_SCHEMAS.values(), TELEMETRY_SCHEMA}
        _require(ref['schema'] in allowed, '$.window_delta.pending_unlink', 'scientific/source artifact is outside technical retirement domain')
        _require(ref in eligible and ref['path'] not in protected_paths and ref['path'] not in current,
                 '$.window_delta.pending_unlink', 'debt is not authenticated retired unprotected metadata/artifact')


def _coverage_merge2(value, summary, prior, prior_summary, same_session):
    current = summary['cumulative']; coverage = current['coverage']
    previous = prior_summary['cumulative'] if prior_summary else None
    if previous:
        _require(current['prior_capture'] == previous['prior_capture'], '$.cumulative.prior_capture', 'prior capture scope changed')
        old = previous['coverage']
        _require(not old['incomplete'] or coverage['incomplete'], '$.cumulative.coverage.incomplete', 'cumulative gap became complete')
        _require(set(old['reasons'])-{'no_observations'} <= set(coverage['reasons']), '$.cumulative.coverage.reasons', 'cumulative reasons lost')
        prior_local = {encode(g) for g in prior_summary['coverage']['gaps']} if same_session else set()
        new_gaps = len({encode(g) for g in summary['coverage']['gaps']}-prior_local)
        if value['cost_delta']['restart_gap']: new_gaps = max(new_gaps, 1)
        _require(int(coverage['gap_events']) >= int(old['gap_events'])+new_gaps, '$.cumulative.coverage.gap_events', 'cumulative gap evidence decreased/reset')
    local = summary['max_observed_rss_bytes']
    old_rss = previous['max_observed_rss_bytes']['value'] if previous else None
    known = [int(v) for v in (old_rss, local) if v is not None]
    actual = current['max_observed_rss_bytes']['value']
    _require(actual == (str(max(known)) if known else None), '$.cumulative.max_observed_rss_bytes', 'maximum differs from carried observed RSS/HWM')


def _validate_telemetry_summary2(value: object) -> Object:
    """Validate bounded technical declarations; no acceptance or file access."""
    value = _retained_checked('summary', value)
    _unique(value['source_cursors'], lambda r: r['source_key'], '$.source_cursors')
    for i, row in enumerate(value['source_cursors']):
        _source_cursor(row, f'$.source_cursors[{i}]')
    _unique(value['producer_phase_aggregates'], _phase_aggregate_key, '$.producer_phase_aggregates')
    for i, row in enumerate(value['producer_phase_aggregates']):
        _require(row['source_key'] == _source_key(row['identity'], row['source']), '$.producer_phase_aggregates', 'phase aggregate owner differs')
        _aggregate(row['aggregate'], f'$.producer_phase_aggregates[{i}].aggregate')
    _unique(value['span_aggregates'], lambda r: (r['phase'],r['timing_kind'],r['measurement_kind']), '$.span_aggregates')
    for row in value['span_aggregates']:
        _require(int(row['warmup_calls']) <= int(row['call_count']), '$.span_aggregates', 'warmup calls exceed calls')
        for key in ('duration_seconds','warmup_seconds'):
            _measurement(row[key], '$.span_aggregates.'+key)
    _unique(value['control_events'], lambda r:r['event'], '$.control_events')
    _unique(value['cpu_coverage']['allocations'], lambda r:r['allocation_id'], '$.cpu_coverage.allocations')
    _require(value['cpu_coverage']['temporal_resolution_target_seconds'] > 0, '$.cpu_coverage', 'positive resolution target required')
    for i, row in enumerate(value['cpu_coverage']['allocations']):
        _cpu_allocation(row, f'$.cpu_coverage.allocations[{i}]')
    for key in ('cpu_seconds','allocated_cpu_seconds','observed_capacity_cpu_seconds'):
        _measurement(value['cpu_totals'][key], '$.cpu_totals.'+key)
    local, overflow = _cpu_local_rollup(value['cpu_coverage'])
    _cpu_rollup_relation(value['cpu_totals'], local, overflow, exact=value['generation'] == '1')
    if int(value['cpu_totals']['valid_intervals']) == 0:
        _require(all(value['cpu_totals'][key]['value'] is None for key in _CPU_ROLLUP_VALUES),
                 '$.cpu_totals', 'zero intervals cannot imply measured zero CPU or capacity')
    for name, measurement in value['observer_self_cost'].items():
        if name != 'scope':
            _measurement(measurement, '$.observer_self_cost.'+name, forecast=name=='arrow_io_forecast_bytes')
    for key in ('coverage','retention','cpu_totals'):
        _require(not value[key]['incomplete'] or bool(value[key]['reasons']), '$.'+key+'.reasons', 'incomplete requires reason')
    if int(value['totals']['collector_dropped_rows']):
        _require(value['coverage']['incomplete'], '$.coverage', 'collector drops require incomplete coverage')
    if any(int(value['retention'][k]) for k in ('omitted_source_rows','omitted_resource_rows','omitted_span_rows')) or value['retention']['pinned_retention_refused']:
        _require(value['retention']['incomplete'], '$.retention', 'omission/pin refusal requires retention reason')
    for gap in value['coverage']['gaps']:
        first, last = gap['first_monotonic_ns'], gap['last_monotonic_ns']
        _require((first is None)==(last is None), '$.coverage.gaps', 'gap clock endpoints must be paired')
        if first is not None:
            _require(gap['clock_domain_id'] is not None and int(first)<=int(last), '$.coverage.gaps', 'gap clock domain missing or reversed')
        if gap['kind'] in ('collector_restart','detail_page_rotation'):
            _require(value['coverage']['incomplete'], '$.coverage', 'uncovered endpoint reset requires incomplete coverage')
    for omission in value['retention']['omissions']:
        _require(int(omission['first_row'])<int(omission['stop_row']), '$.retention.omissions', 'empty/reversed omission')
    d = value['durability']
    _require(0 < d['maximum_buffer_seconds'] <= 60, '$.durability.maximum_buffer_seconds', 'buffer cadence outside (0,60]')
    _require(int(d['maximum_synchronous_flush_rows']) == 2*int(d['maximum_staged_batch_rows']), '$.durability', 'synchronous row bound differs')
    _require(d['uncommitted_resource_batch_at_risk'] == (not value['closed']), '$.durability', 'closed/resource tail declaration differs')
    _require(value['science_window_policy']['period_seconds'] > 0, '$.science_window_policy.period_seconds', 'positive window period required')
    _summary_cumulative2(value)
    return value


def _validate_telemetry_commit2(value, *, summary, summary_ref, previous=None, previous_ref=None,
        previous_summary=None, previous_summary_ref=None, phase_contexts=(), resume_contexts=(),
        catalog=None, previous_catalog=None):
    value = _retained_checked('commit', value)
    checked_summary = _commit_summary2(value, summary, summary_ref)
    _require(catalog is not None, '$.catalog', 'current decoded retained catalog required')
    current_catalog = validate_telemetry_catalog(catalog, expected_transport=value['transport'])
    _require(current_catalog['generation'] == value['generation'] and int(value['catalog']['bytes']) <= 65536,
             '$.catalog', 'catalog generation/declared byte ceiling differs')
    prior_summary = None; prior = None; same_session = False; prior_cursors = {}; before_catalog = None
    if value['previous'] is None:
        _require(all(v is None for v in (previous, previous_ref, previous_summary, previous_summary_ref, previous_catalog)),
                 '$.previous', 'genesis cannot carry predecessor contexts')
        _require(value['generation'] == '1', '$.generation', 'v2 genesis requires generation1')
    else:
        _require(all(v is not None for v in (previous, previous_ref, previous_summary, previous_summary_ref, previous_catalog)),
                 '$.previous', 'immediate previous pair and catalog contents required')
        prior = _retained_checked('commit', previous)
        pref = _retained_ref(previous_ref, 'commit', '$.previous_ref')
        prior_summary = _commit_summary2(prior, previous_summary, previous_summary_ref)
        _require(value['previous'] == dict(commit=pref, summary=previous_summary_ref)
                 and int(value['generation']) == int(prior['generation'])+1,
                 '$.previous', 'exact previous transaction pair/generation differs')
        _require(value['transport'] == prior['transport'], '$.transport', 'enclosing transport changed')
        before_catalog = validate_telemetry_catalog(previous_catalog, expected_transport=value['transport'])
        _require(before_catalog['generation'] == prior['generation'], '$.previous_catalog', 'previous catalog generation differs')
        same_session = value['session']['source']['session_id'] == prior['session']['source']['session_id']
        if same_session:
            _require(not prior['closed'] and value['session'] == prior['session'], '$.session', 'closed or rebound collector session cannot append')
        else:
            _require(prior['closed'] or value['cost_delta']['restart_gap'], '$.previous.closed', 'rotation needs closed prior or explicit crash recovery')
            _require(value['session']['source']['clock_domain_id'] != prior['session']['source']['clock_domain_id'], '$.session', 'new collector session reused clock binding')
        prior_cursors = {r['source_key']:r for r in prior['source_cursors']}
    _require(isinstance(resume_contexts, (tuple, list)) and len(resume_contexts) <= 16,
             '$.resume_contexts', 'bounded resume contexts required')
    resume_refs = []
    for context in resume_contexts:
        _require(isinstance(context, dict) and set(context) == {'commit', 'commit_ref', 'summary', 'summary_ref'},
                 '$.resume_contexts', 'closed resume context required')
        c = _retained_checked('commit', context['commit'])
        ref = _retained_ref(context['commit_ref'], 'commit', '$.resume_contexts.commit_ref')
        _commit_summary2(c, context['summary'], context['summary_ref'])
        _require(value['previous'] is not None and int(c['generation']) < int(value['generation']) and c['transport'] == value['transport'],
                 '$.resume_contexts', 'resume requires older matching retained transport evidence')
        matches = [r for r in c['source_cursors'] if r['source_key'] not in prior_cursors
                   and any(r['source_key'] == a['source_key'] for a in value['source_cursors'])]
        _require(bool(matches), '$.resume_contexts', 'unmatched/duplicate resume context')
        prior_cursors.update((r['source_key'], r) for r in matches)
        resume_refs.append(dict(commit=ref, summary=context['summary_ref']))
    _require(resume_refs == value['contexts']['resume_context_refs'], '$.contexts.resume_context_refs', 'committed resume pairs differ from supplied contexts')
    _require(isinstance(phase_contexts, (tuple, list)) and len(phase_contexts) <= 128, '$.phase_contexts', 'bounded phase contexts required')
    declared = value['contexts']['phase_context_refs']
    _unique(declared, lambda r: encode(r['publication_ref']), '$.contexts.phase_context_refs')
    _require(len(declared) == len(phase_contexts), '$.contexts.phase_context_refs', 'exact committed phase context inventory required')
    for row, context in zip(declared, phase_contexts):
        _require(isinstance(context, dict) and set(context) == {'publication', 'publication_ref', 'segment', 'segment_ref'}, '$.phase_contexts', 'closed phase context required')
        _require(all(row[k] == context[k] for k in ('publication_ref', 'segment_ref')), '$.contexts.phase_context_refs', 'original phase context references differ')
        for original, retained in (('publication_ref', 'retained_publication_ref'), ('segment_ref', 'retained_segment_ref')):
            _require(all(row[original][k] == row[retained][k] for k in ('bytes', 'sha256', 'media_type', 'schema')),
                     '$.contexts.phase_context_refs', 'retained context bytes differ from original')
    _retained_budget(value, checked_summary, current_catalog, *([prior, prior_summary, before_catalog] if prior else []),
                     *phase_contexts, *resume_contexts)
    _require(isinstance(phase_contexts,(tuple,list)) and len(phase_contexts)<=128, '$.phase_contexts', 'bounded phase contexts required')
    contexts = {}
    for context in phase_contexts:
        _require(isinstance(context,dict) and set(context)=={'publication','publication_ref','segment','segment_ref'}, '$.phase_contexts', 'closed phase context required')
        k = encode(context['publication_ref'])
        _require(k not in contexts, '$.phase_contexts', 'duplicate publication context')
        contexts[k] = context
    used = set(); progress = {k:r['cursor'] for k,r in prior_cursors.items()}
    delta = dict(accepted_source_rows=0,accepted_aggregate_calls=0,accepted_diagnostic_events=0,coalesced_source_events=0)
    sources = {r['source_key']:r for r in value['source_cursors']}
    projected_rows = []
    for index, ar in enumerate(value['accepted_ranges']):
        path = f'$.accepted_ranges[{index}]'
        context = contexts.get(encode(ar['publication']))
        _require(context is not None, path, 'exact original phase context required')
        used.add(encode(ar['publication']))
        cursor = validate_phase_cursor(ar['cursor'],**context)
        segment = context['segment']; source_key = _source_key(segment['identity'],segment['source'])
        _require(source_key==ar['source_key'] and ar['segment']==context['segment_ref'] and ar['mode']==segment['mode'], path, 'accepted range source/segment/mode differs')
        _require(source_key in sources, path, 'range has no transaction source cursor')
        _same_owner(sources[source_key],cursor,path)
        first, stop = int(ar['first_row']),int(ar['stop_row'])
        _require(0<=first<stop<=len(segment['rows']) and int(cursor['next_row'])==stop, path, 'accepted physical row range differs')
        old = progress.get(source_key)
        if old is not None and old['segment']==ar['segment']:
            _require(first==int(old['next_row']) and old['publication']==ar['publication'], path, 'range overlaps/skips durable physical prefix')
        else:
            _require(first==0, path, 'new segment must start at physical row0')
            if old is not None:
                proof = contexts.get(encode(old['publication']))
                _require(proof is not None, path, 'old segment physical completion proof required')
                validate_phase_cursor(old, **proof)
                _require(int(old['next_row'])==len(proof['segment']['rows']), path, 'old physical segment tail not accepted')
                used.add(encode(old['publication']))
                _same_owner(proof['publication'],context['publication'],path)
                _require(context['publication']['previous']==old['publication'] and int(old['last_sequence'])<int(context['publication']['first_sequence']), path, 'new publication not adjacent to accepted cursor')
        rp, rs = ar['retained_publication'],ar['retained_segment']
        _require((rp is None)==(rs is None), path, 'raw retained refs must be paired')
        if rp is not None:
            for local, original in ((rp,ar['publication']),(rs,ar['segment'])):
                _require(all(local[k]==original[k] for k in ('bytes','sha256','media_type','schema')), path, 'retained raw bytes differ')
        else:
            _require(any(o['source_key']==source_key and o['segment']==ar['segment'] and o['first_row']==ar['first_row'] and o['stop_row']==ar['stop_row'] for o in checked_summary['retention']['omissions']), path, 'omitted raw range needs explicit exact omission')
        delta['accepted_source_rows'] += stop-first
        rows = segment['rows'][first:stop]
        if ar['mode']=='normal':
            delta['accepted_aggregate_calls'] += sum(int(r['call_count']) for r in rows)
            projected_rows.extend((source_key,segment,'normal_aggregate',r) for r in rows)
        else:
            delta['accepted_diagnostic_events'] += len(rows)
            projected_rows.extend((source_key,segment,'diagnostic_end_projection',_diagnostic_aggregate(r)) for r in rows if r['action']=='phase_end')
        if stop==len(segment['rows']):
            delta['coalesced_source_events'] += int(segment['coalesced_events'])
        progress[source_key] = cursor
    _require(used==set(contexts), '$.phase_contexts', 'extraneous original context')
    for key, row in sources.items():
        _require(key in progress and row['cursor']==progress[key], '$.source_cursors', 'cursor not justified by accepted range or explicit baseline')
        if key in prior_cursors:
            _cursor_after(prior_cursors[key],row)
    for key, amount in delta.items():
        before = int(prior_summary['totals'][key]) if prior_summary else 0
        _require(int(checked_summary['totals'][key])==before+amount, '$.totals.'+key, 'accepted delta differs from cumulative totals')
    for table in ('spans','resources','control_events'):
        total = int(checked_summary['totals']['rows'][table]); local = int(checked_summary['rows'][table])
        prior_total = int(prior_summary['totals']['rows'][table]) if prior_summary else 0
        prior_local = int(prior_summary['rows'][table]) if prior_summary and same_session else 0
        _require(total==prior_total+local-prior_local and local>=prior_local, '$.totals.rows.'+table, 'table row totals/baseline counted incorrectly')
    _cpu_commit_rollup(checked_summary, prior_summary, same_session)
    expected = {}
    if same_session:
        for phase in prior_summary['producer_phase_aggregates']:
            expected[_phase_aggregate_key(phase)] = object_value(phase)
    for key, segment, representation, row in projected_rows:
        phase = dict(source_key=key,identity=segment['identity'],source=segment['source'],
                     representation=representation,aggregate=row)
        phase_key = _phase_aggregate_key(phase)
        if phase_key in expected:
            phase = dict(phase,aggregate=_merge_aggregate(expected[phase_key]['aggregate'],row))
        expected[phase_key] = phase
    actual = {_phase_aggregate_key(row):row for row in checked_summary['producer_phase_aggregates']}
    _require(set(actual)==set(expected), '$.producer_phase_aggregates', 'accepted cumulative phase keys differ')
    for key in expected:
        _require(encode(actual[key])==encode(expected[key]), '$.producer_phase_aggregates', 'summary differs from accepted cumulative phase projection')
    for ar in value['accepted_ranges']:
        row = next(r for r in declared if r['publication_ref'] == ar['publication'])
        if ar['retained_publication'] is not None:
            _require(ar['retained_publication'] == row['retained_publication_ref'] and ar['retained_segment'] == row['retained_segment_ref'],
                     '$.accepted_ranges', 'retained range locator differs from committed raw context')
    _cost_merge2(value, checked_summary, prior, prior_summary)
    _phase_merge2(checked_summary, prior_summary, projected_rows)
    _coverage_merge2(value, checked_summary, prior, prior_summary, same_session)
    _catalog_window2(value, checked_summary, current_catalog, prior, prior_summary, before_catalog,
                     summary_ref, previous_ref, previous_summary_ref)
    return value


def _validate_telemetry_binding2(value: object, *, expected_state: object,
        expected_transport: object, commit: object, commit_ref: object,
        summary: object, summary_ref: object, source_binding: object,
        source_binding_ref: object, manifest: object, manifest_ref: object,
        source_transport: object, canonical_plan_ref: object,
        expected_producer_provenance: object) -> Object:
    """Verify exact retained close bytes and independently proven scientific source."""
    value = _retained_checked('binding',value)
    _require(len(encode(value))<=1024*1024, '$', 'retained binding exceeds metadata cap')
    cref = _retained_ref(commit_ref,'commit','$.commit_ref')
    sref = _retained_ref(summary_ref,'summary','$.summary_ref')
    bref = _technical_ref(source_binding_ref,'source_binding','$.source_binding_ref')
    roots=[];size=0
    for key,ref in (('commit',cref),('summary',sref),('source_binding',bref)):
        parsed,count = _embedded_technical(value[key],key,locals()[key],ref)
        roots.append(parsed);size+=count
    _require(size<=1024*1024, '$', 'aggregate embedded raw bytes exceed cap')
    pending=[value,*roots];count=0
    while pending:
        item=pending.pop();count+=1
        _require(count<=16384, '$', 'aggregate retained metadata object cap exceeded')
        if isinstance(item,dict):pending.extend(item.values())
        elif isinstance(item,list):pending.extend(item)
    c = _retained_checked('commit',commit)
    validate_telemetry_pointer(dict(schema=_RETAINED_IDS['pointer'],contract_set=CONTRACT_SET,commit=cref),commit=c,commit_ref=cref)
    s = _commit_summary2(c,summary,sref)
    _require(c['closed'] and s['closed'], '$.commit.closed', 'fixed binding requires returned closed session')
    proof = validate_telemetry_source_binding(source_binding,expected_state=expected_state,
        expected_transport=expected_transport,manifest=manifest,manifest_ref=manifest_ref,
        source_transport=source_transport,canonical_plan_ref=canonical_plan_ref,
        expected_producer_provenance=expected_producer_provenance)
    _require(value['selected_state']==proof['selected_state'] and value['transport']==c['transport']==proof['enclosing_transport'], '$.selected_state', 'retained selection/transport differs')
    for row in c['source_cursors']:
        binding=row['binding']
        if binding['state']==value['selected_state']:
            _require(binding['evidence']==bref and binding['invocation']==proof['invocation'], '$.source_cursors.binding', 'selected phase source evidence differs')
    status=value['capture_status']
    _require(status['performance_status']=='available' or bool(status['reason']), '$.capture_status.reason', 'unavailable capture requires reason')
    _require(status['scalar_live_route']!='unavailable' or bool(status['scalar_live_reason']), '$.capture_status.scalar_live_reason', 'unavailable scalar route requires reason')
    return value
