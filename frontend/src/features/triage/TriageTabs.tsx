// The Episodes table's Triage tabs, each with its count; the chosen one lives in `?triage=`.
import { Tabs } from "../core/Tabs";
import { DECISION_LABELS, type TriageDecision } from "./useTriage";

export type TriageTab = "all" | TriageDecision;

const TABS: TriageTab[] = ["all", "keep", "reject", "needs_review"];

export function parseTriageTab(value: string | null): TriageTab {
  return TABS.find((tab) => tab === value) ?? "all";
}

export function countDecisions(decisions: TriageDecision[]): Record<TriageTab, number> {
  const counts: Record<TriageTab, number> = { all: 0, keep: 0, reject: 0, needs_review: 0 };
  for (const decision of decisions) {
    counts.all += 1;
    counts[decision] += 1;
  }
  return counts;
}

export function TriageTabs(props: {
  tab: TriageTab;
  counts: Record<TriageTab, number>;
  onTab: (tab: TriageTab) => void;
}) {
  return (
    <Tabs
      label="Triage decision"
      items={TABS.map((tab) => ({
        value: tab,
        label: tab === "all" ? "All" : DECISION_LABELS[tab],
        count: props.counts[tab],
      }))}
      value={props.tab}
      onChange={props.onTab}
    />
  );
}
