import type {
  Common_Count,
  Core_Int64,
  Phase_Aggregate,
  Phase_AggregateTimeBounds,
  Phase_Event,
  Phase_ScalarMetric,
  Phase_SegmentHeader,
  ProducerPhaseSegment,
  ProducerPhaseSource,
} from "../../../src/qcl_negf_contracts/generated/contracts.js";

declare const header: Phase_SegmentHeader;
declare const aggregate: Phase_Aggregate;
declare const event: Phase_Event;
const normal: ProducerPhaseSegment = { ...header, mode: "normal", rows: [aggregate] };
const diagnostic: ProducerPhaseSegment = { ...header, mode: "diagnostic", rows: [event] };
// @ts-expect-error normal represents aggregates only
const normalEvent: ProducerPhaseSegment = { ...header, mode: "normal", rows: [event] };
// @ts-expect-error diagnostic retains events only
const diagnosticAggregate: ProducerPhaseSegment = {
  ...header,
  mode: "diagnostic",
  rows: [aggregate],
};
const exactCount: Common_Count = "9007199254740993";
// @ts-expect-error source ordinals must not become rounded JS Numbers
const roundedCount: Common_Count = 9007199254740993;
const exactInteger: Core_Int64 = { kind: "integer", type: "Int64", decimal: "9007199254740993" };
// @ts-expect-error native Int64 metrics use the shared tagged decimal atom
const rawBigInt: Core_Int64 = 9007199254740993n;
const metric: Phase_ScalarMetric = {
  name: "cpu_seconds",
  value: 3,
  unit: "s",
  measurement_status: "measured",
  reason: "process_inclusive_delta_on_end",
};
// @ts-expect-error nullable reason remains mandatory
const missingReason: Phase_ScalarMetric = {
  name: "x",
  value: null,
  unit: "1",
  measurement_status: "error",
};
function progress(value: ProducerPhaseSource): Common_Count | null {
  if (value.schema === "qcl-negf.producer-phase-cursor.v1") return value.next_row;
  if (value.schema === "qcl-negf.producer-phase-publication.v1") return value.generation;
  return null;
}
void [
  normal,
  diagnostic,
  normalEvent,
  diagnosticAggregate,
  exactCount,
  roundedCount,
  exactInteger,
  rawBigInt,
  metric,
  missingReason,
  progress,
];

// Immutability is scoped to the new DTOs, including nested shared references.
function forbiddenMutation(
  segment: ProducerPhaseSegment,
  row: Phase_Aggregate,
  event: Phase_Event,
): void {
  // @ts-expect-error readonly discriminator cannot retag aggregate rows as diagnostic
  segment.mode = "diagnostic";
  // @ts-expect-error represented bounds cannot change independently of header/cursor
  row.last_sequence = "1";
  // @ts-expect-error readonly Source fields prevent clock rebinding
  segment.source.clock_domain_id = "rebound";
  // @ts-expect-error nested common Identity is readonly in the phase DTO
  segment.identity.run_id = "rebound";
  // @ts-expect-error readonly fields cannot be replaced with another valid Source
  segment.source = { ...segment.source };
  // @ts-expect-error nested scalar metric status/reason evidence is immutable
  event.metrics[0].reason = "rewritten";
  const value = event.metrics[0].value;
  if (value !== null && typeof value === "object") {
    // @ts-expect-error nested shared Core Int64 atom is readonly in the phase DTO
    value.decimal = "1";
  }
  // @ts-expect-error aggregate per-metric counts are immutable too
  row.metrics[0].measured_calls = "0";
}
function forbiddenSourceMutation(value: ProducerPhaseSource): void {
  if (value.schema === "qcl-negf.producer-phase-publication.v1") {
    // @ts-expect-error publication ordinal is readonly
    value.generation = "1";
    // @ts-expect-error common FileRef path is readonly through the DTO
    value.segment.path = "rebound.json";
    // @ts-expect-error nested cumulative Health counters are readonly
    value.health.dropped.capacity = "0";
  } else if (value.schema === "qcl-negf.producer-phase-current.v1") {
    if (value.current_phase !== null) {
      // @ts-expect-error inline nested object fields are readonly
      value.current_phase.span_id = "rebound:1";
    }
  } else {
    // @ts-expect-error cursor progress cannot be mutated after construction
    value.next_row = "0";
  }
}
// Healthy callers construct a successor value; source DTOs stay unchanged.
function withNewBound(row: Phase_Aggregate): Phase_Aggregate {
  return { ...row, last_sequence: "10" };
}
// Existing aliases retain their published mutability outside the new DTO graph.
function existingAtomStillMutable(value: Core_Int64): void {
  value.decimal = "1";
}
void [forbiddenMutation, forbiddenSourceMutation, withNewBound, existingAtomStillMutable];

const clockBounds: Phase_AggregateTimeBounds = {
  min_start_monotonic_ns: "9007199254741000",
  max_end_monotonic_ns: "9007204754741000",
  measured_calls: "2",
  unavailable_calls: "0",
  reasons: [],
};
declare const withoutClock: Omit<Phase_Aggregate, "time_bounds">;
// @ts-expect-error an old aggregate without required time_bounds is unsupported
const missingClock: Phase_Aggregate = withoutClock;
function forbidClockMutation(row: Phase_Aggregate): void {
  // @ts-expect-error recursive readonly protects clock envelope bounds
  row.time_bounds.min_start_monotonic_ns = "1";
  // @ts-expect-error clock coverage counts are readonly
  row.time_bounds.measured_calls = "0";
  // @ts-expect-error clock reasons remain a readonly array
  row.time_bounds.reasons.push("rewritten");
}
void [clockBounds, missingClock, forbidClockMutation];
