import { describe, expect, it } from "vitest";

import type { SetName } from "../sets/useSets";
import type { TriageRow } from "../triage/useTriage";
import { applyFilters, nextSort, parseFilters, signalsIn } from "./episodeFilters";

const PLACES = "places it on the target";

function row(id: string, confidence: number, extra: Partial<TriageRow> = {}): TriageRow {
  return {
    episode_id: id,
    decision: "needs_review",
    reason: "",
    confidence,
    not_passed: [],
    uncertainty: [],
    quality: null,
    ...extra,
  };
}

const episodes = [{ id: "a" }, { id: "b" }, { id: "c" }, { id: "d" }];
const triageOf = new Map(
  [
    row("a", 0.9, { quality: 0.5 }),
    row("b", 0.6, {
      not_passed: [{ phrase: PLACES, status: "unsure" }],
      uncertainty: ["near threshold"],
      quality: -1.2,
    }),
    row("c", 0.7, {
      not_passed: [{ phrase: PLACES, status: "unsure" }],
      uncertainty: ["unconfirmed fail"],
    }),
  ].map((r) => [r.episode_id, r]),
);
const setOf = new Map<string, SetName>([["a", "dev"]]);

function ids(params: string): string[] {
  return applyFilters(episodes, parseFilters(new URLSearchParams(params)), triageOf, setOf).map(
    (e) => e.id,
  );
}

describe("applyFilters", () => {
  it("keeps the Dataset's order with no filters", () => {
    expect(ids("")).toEqual(["a", "b", "c", "d"]);
  });

  it("filters by a Phrase that didn't pass, an Uncertainty signal, and a set", () => {
    expect(ids(`phrase=${encodeURIComponent(PLACES)}`)).toEqual(["b", "c"]);
    expect(ids("signal=unconfirmed+fail")).toEqual(["c"]);
    expect(ids("set=dev")).toEqual(["a"]);
    expect(ids("set=none")).toEqual(["b", "c", "d"]);
    expect(ids("set=dev&signal=near+threshold")).toEqual([]);
  });

  it("sorts by confidence either way, unscored Episodes last", () => {
    expect(ids("sort=confidence")).toEqual(["b", "c", "a", "d"]);
    expect(ids("sort=-confidence")).toEqual(["a", "c", "b", "d"]);
  });

  it("sorts by quality either way, Episodes with none or unscored last", () => {
    expect(ids("sort=-quality")).toEqual(["a", "b", "c", "d"]);
    expect(ids("sort=quality")).toEqual(["b", "a", "c", "d"]);
  });
});

describe("nextSort", () => {
  it("cycles least confident first, most confident first, then off", () => {
    expect(nextSort(null, "confidence")).toBe("confidence");
    expect(nextSort("confidence", "confidence")).toBe("-confidence");
    expect(nextSort("-confidence", "confidence")).toBeNull();
  });

  it("cycles best quality first, worst first, then off", () => {
    expect(nextSort(null, "quality")).toBe("-quality");
    expect(nextSort("-quality", "quality")).toBe("quality");
    expect(nextSort("quality", "quality")).toBeNull();
  });

  it("starts afresh on a column the table isn't sorted by", () => {
    expect(nextSort("-confidence", "quality")).toBe("-quality");
    expect(nextSort("quality", "confidence")).toBe("confidence");
  });
});

describe("signalsIn", () => {
  it("lists each signal present once", () => {
    expect(signalsIn([...triageOf.values()])).toEqual(["near threshold", "unconfirmed fail"]);
  });
});
