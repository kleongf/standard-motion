import { describe, expect, it } from "vitest";

import { nextStep, stepNotes } from "./flow";

const done = { episodes: 8, labelled: 8, version: 2, shown: 8, waiting: 0, auditLeft: 0 };

describe("nextStep", () => {
  it("follows the work order: ingest, label, run, review, audit", () => {
    expect(nextStep({ ...done, episodes: 0 })).toBe("prepare");
    expect(nextStep({ ...done, labelled: 0 })).toBe("reference");
    expect(nextStep({ ...done, version: null })).toBe("describe");
    expect(nextStep({ ...done, waiting: 3 })).toBe("review");
    expect(nextStep({ ...done, auditLeft: null })).toBe("audit");
    expect(nextStep({ ...done, auditLeft: 2 })).toBe("audit");
    expect(nextStep(done)).toBeNull();
  });

  it("picks nothing past a step still loading", () => {
    expect(nextStep({})).toBeNull();
    expect(nextStep({ episodes: 8 })).toBeNull();
    expect(nextStep({ episodes: 8, labelled: 3, version: 1 })).toBeNull();
  });

  it("an earlier step wins over a later one", () => {
    expect(nextStep({ ...done, labelled: 0, waiting: 3 })).toBe("reference");
  });
});

describe("stepNotes", () => {
  it("says where each step stands", () => {
    expect(
      stepNotes({ episodes: 1, labelled: 0, version: null, waiting: 0, auditLeft: null }),
    ).toEqual({
      prepare: "1 Episode",
      reference: "0 of 1",
      describe: "no Rubric",
      episodes: undefined,
      review: undefined,
      audit: "not drawn",
    });
    expect(stepNotes(done).review).toBe("done");
    expect(stepNotes({ ...done, waiting: 2, auditLeft: 5 })).toMatchObject({
      describe: "v2",
      episodes: "8 decided",
      review: "2 waiting",
      audit: "5 left",
    });
  });
});
