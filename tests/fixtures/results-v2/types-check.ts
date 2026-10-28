import type {
  Common_Count,
  Core_ScientificHistorySnapshot,
  Core_SolverMetric,
} from "../../../src/qcl_negf_contracts/generated/contracts.js";

const count: Common_Count = "9007199254740993";
// @ts-expect-error exact counters are decimal strings, never JS Number
const rounded: Common_Count = 9007199254740993;
const incomplete: Core_ScientificHistorySnapshot = {
  type: "ScientificHistorySnapshot",
  // @ts-expect-error all reflected fields including nullable fields remain mandatory
  fields: {},
};
const metric: Core_SolverMetric = {
  type: "SolverMetric",
  fields: {
    name: { kind: "symbol", value: "residual" },
    value: { kind: "ieee", type: "f64", bits: "7ff8000000000001" },
    unit: "1",
    measurement_status: { kind: "symbol", value: "error" },
    reason: { kind: "symbol", value: "non_finite" },
  },
};
void [count, rounded, incomplete, metric];
