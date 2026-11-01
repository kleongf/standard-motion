// Filters above the Episodes table: a Phrase that didn't pass, an Uncertainty signal, and a set.
// Each lives in the URL, so a filtered view survives reloads and links.
import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";

import { navigate } from "../core/url";
import { SET_LABELS } from "../sets/useSets";
import type { EpisodeFilters } from "./episodeFilters";

function Filter(props: {
  label: string;
  param: string;
  value: string | null;
  children: ReactNode;
}) {
  return (
    <label className="flex items-center gap-1.5 text-xs text-muted-foreground">
      {props.label}
      <select
        aria-label={props.label}
        value={props.value ?? ""}
        onChange={(event) => {
          navigate({ [props.param]: event.target.value || null });
        }}
        className="h-7 max-w-64 truncate rounded-md border bg-background px-1.5 text-xs text-foreground"
      >
        {props.children}
      </select>
    </label>
  );
}

export function EpisodeFilterBar(props: {
  filters: EpisodeFilters;
  phrases: string[];
  signals: string[];
}) {
  const { filters } = props;
  const active = filters.phrase !== null || filters.signal !== null || filters.set !== null;
  return (
    <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2" aria-label="Filters">
      <Filter label="Phrase" param="phrase" value={filters.phrase}>
        <option value="">Any Phrase</option>
        {props.phrases.map((p) => (
          <option key={p} value={p}>
            Didn’t pass: {p}
          </option>
        ))}
      </Filter>
      <Filter label="Uncertainty signal" param="signal" value={filters.signal}>
        <option value="">Any signal</option>
        {props.signals.map((s) => (
          <option key={s} value={s}>
            {s}
          </option>
        ))}
      </Filter>
      <Filter label="Set" param="set" value={filters.set}>
        <option value="">Any set</option>
        <option value="dev">{SET_LABELS.dev}</option>
        <option value="test">{SET_LABELS.test}</option>
        <option value="none">Neither set</option>
      </Filter>
      {active && (
        <Button
          size="xs"
          variant="ghost"
          onClick={() => {
            navigate({ phrase: null, signal: null, set: null });
          }}
        >
          Clear filters
        </Button>
      )}
    </div>
  );
}
