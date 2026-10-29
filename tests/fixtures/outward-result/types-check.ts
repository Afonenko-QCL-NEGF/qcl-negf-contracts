import type { OutwardResult, OutwardNativePointSource, OutwardPhaseLocator,
  OutwardScientificSeriesResultV4, OutwardConfiguredPointResultV2, OutwardData,
  OutwardPortableValue, Core_Int64 } from "../../../src/qcl_negf_contracts/generated/contracts.js";
declare const source: OutwardNativePointSource;
declare const series: OutwardScientificSeriesResultV4;
declare const configured: OutwardConfiguredPointResultV2;
const pending: OutwardNativePointSource = {schema:"qcl-negf.native-point-source.v1",
  kind:"absent",artifact_root:".",relation:null,selected_state:null,
  diagnostics:null,observations:null,reason:"solver_not_run"};
const busy: OutwardPhaseLocator = {status:"unavailable",session_id:null,current_path:null,reason:"writer_busy"};
const roots: ReadonlyArray<OutwardResult> = [source,series,configured,pending];
// Scalar extensions coexist with closed named objects in this DTO.
const data: OutwardData = {native_source:pending,phase_source:busy,optical_attachment:null,literal_extension:"kept"};
function immutable(s: OutwardScientificSeriesResultV4): void {
  // @ts-expect-error outward sources and refs are recursively readonly
  s.points[0].data.native_source.artifact_root="rebound";
  // @ts-expect-error canonical StateRef attempt is string, never transport int
  if(s.points[0].data.native_source.selected_state) s.points[0].data.native_source.selected_state.identity.attempt=2;
  // @ts-expect-error chronological point inventory is readonly
  s.points.push(s.points[0]);
}
// @ts-expect-error phase disabled/unavailable never has a session id
const wrongPhase: OutwardPhaseLocator = {status:"disabled",session_id:"fake",current_path:null,reason:"disabled"};
// @ts-expect-error absent source never carries a StateRef or partial analysis
const wrongAbsent: OutwardNativePointSource = {schema:"qcl-negf.native-point-source.v1",kind:"absent",artifact_root:".",relation:null,selected_state:series.points[0].data.native_source.selected_state,diagnostics:null,observations:null,reason:"missing"};
// @ts-expect-error unknown arbitrary object is not a scalar extension or named carrier
const wrongData: OutwardData = {native_source:pending,phase_source:busy,optical_attachment:null,extra:{guessed:true}};
// The index union cannot exclude a valid named carrier under an unknown key;
// runtime JSON Schema rejects this literal (test_both_point_collections...).
const runtimeOnly: OutwardData = {native_source:pending,phase_source:busy,optical_attachment:null,unknown_extension:pending};
const portable: OutwardPortableValue = {nested:[null,false,0,"",{literal:"kept"}]};
// @ts-expect-error equivalent recursive portable metadata has a readonly index
portable.nested=[];
const portableArray: OutwardPortableValue = [null,false,0,"kept"];
// @ts-expect-error equivalent recursive portable arrays are readonly
portableArray.push("changed");
function oldAtomMutable(value: Core_Int64): void { value.decimal="1"; }
void [roots,data,immutable,wrongPhase,wrongAbsent,wrongData,runtimeOnly,portable,portableArray,oldAtomMutable];
