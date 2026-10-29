import type { TelemetryEnvelope, TelemetryCommit, TelemetryPointer, TelemetrySummary,
  TelemetryBinding, TelemetrySourceBinding, Telemetry_SourceCursor, Common_Count,
  Core_Int64 } from "../../../src/qcl_negf_contracts/generated/contracts.js";
declare const commit: TelemetryCommit;
declare const summary: TelemetrySummary;
declare const proof: TelemetrySourceBinding;
declare const binding: TelemetryBinding;
const pointer: TelemetryPointer = {schema:"qcl-negf.telemetry-pointer.v1",contract_set:"qcl-negf.results.v2",commit:binding.commit.ref};
const roots: ReadonlyArray<TelemetryEnvelope> = [commit,summary,proof,binding,pointer];
function counter(c: TelemetryCommit): Common_Count { return c.generation; }
function original(b: TelemetryBinding): number { return b.transport.selection.attempt; }
function noMutation(c: TelemetryCommit, s: TelemetrySummary, r: Telemetry_SourceCursor): void {
  // @ts-expect-error new technical DTOs are recursively readonly
  c.summary.sha256="changed";
  // @ts-expect-error canonical source attempt is a decimal string, not transport int
  r.identity.attempt=3;
  // @ts-expect-error transport int remains explicit and readonly
  c.transport!.selection.attempt=3;
  // @ts-expect-error cumulative totals are readonly
  s.totals.rows.resources="7";
  // @ts-expect-error measured interval evidence cannot mutate in place
  s.cpu_coverage.allocations.push(s.cpu_coverage.allocations[0]);
  // @ts-expect-error exact producer clock source is readonly
  r.source.clock_domain_id="rebound";
}
function oldAtomMutable(value: Core_Int64): void { value.decimal="1"; }
void [roots,counter,original,noMutation,oldAtomMutable];
