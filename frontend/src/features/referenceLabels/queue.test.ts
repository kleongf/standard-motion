import { expect, test } from "vitest";

import { labelQueue, nextInQueue } from "./queue";

const sets = [
  { name: "dev" as const, size: 3, frozen_at: null, episode_ids: ["d:0", "d:1", "d:2"] },
  { name: "test" as const, size: 2, frozen_at: null, episode_ids: ["t:0", "t:1"] },
];
const label = (episode_id: string, relabel = false) => ({
  episode_id,
  relabel,
  description: "",
  phrases: [],
  instruction: null,
  elapsed_s: 1,
  labelled_at: "",
});

test("a set's queue is its Episodes without a first-pass label", () => {
  const labels = [label("t:0"), label("d:1")];
  expect(labelQueue("test", sets, labels)).toEqual(["t:1"]);
  expect(labelQueue("dev", sets, labels)).toEqual(["d:0", "d:2"]);
});

test("the relabel queue is the Dev set's labelled Episodes not yet relabelled", () => {
  const labels = [label("d:0"), label("d:1"), label("d:1", true), label("t:0")];
  expect(labelQueue("relabel", sets, labels)).toEqual(["d:0"]);
});

test("after an Episode comes the next in its queue, wrapping round, and none at the end", () => {
  expect(nextInQueue(["a", "b", "c"], "b")).toBe("c");
  expect(nextInQueue(["a", "b", "c"], "c")).toBe("a");
  expect(nextInQueue(["b"], "b")).toBeNull();
});
