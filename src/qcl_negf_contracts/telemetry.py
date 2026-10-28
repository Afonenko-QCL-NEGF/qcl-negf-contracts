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
