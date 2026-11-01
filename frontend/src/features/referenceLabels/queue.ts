// What's left to label: a set's Episodes without a first-pass label, or, for the relabel pass,
// the Dev set's labelled Episodes not yet relabelled (about 15 are enough to measure the slack).
import type { EpisodeSet } from "../sets/useSets";
import { labelledIds, type ReferenceLabel } from "./useReferenceLabels";

export type LabelQueue = "test" | "dev" | "relabel";

export const QUEUE_LABELS: Record<LabelQueue, string> = {
  test: "Test set",
  dev: "Dev set",
  relabel: "Relabel (Dev set)",
};

export function queueMembers(queue: LabelQueue, sets: EpisodeSet[] | undefined): string[] {
  const name = queue === "relabel" ? "dev" : queue;
  return sets?.find((s) => s.name === name)?.episode_ids ?? [];
}

export function labelQueue(
  queue: LabelQueue,
  sets: EpisodeSet[] | undefined,
  labels: ReferenceLabel[] | undefined,
): string[] {
  const first = labelledIds(labels, false);
  const members = queueMembers(queue, sets);
  if (queue !== "relabel") return members.filter((id) => !first.has(id));
  const relabelled = labelledIds(labels, true);
  return members.filter((id) => first.has(id) && !relabelled.has(id));
}

/** The Episode to open after `id`: the next one left in the queue, or null when none is. */
export function nextInQueue(queue: string[], id: string): string | null {
  const rest = queue.filter((other) => other !== id);
  if (rest.length === 0) return null;
  const after = queue.indexOf(id);
  return queue.slice(after + 1).find((other) => other !== id) ?? rest[0] ?? null;
}
