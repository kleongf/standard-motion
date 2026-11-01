// A Rubric-level setting (the gripper-closed level, the grasp rule's rise), amber while it is an
// assumption nobody confirmed. On the draft it is edited in place; saving a value confirms it.
import { AlertTriangle } from "lucide-react";
import { useState } from "react";

import { cn } from "@/lib/utils";

import { ASSUMED } from "./phraseTones";
import type { Setting } from "./useDraft";

export interface SettingEditor {
  min: number;
  max: number;
  step: number;
  onSave: (shown: number) => void; // in the units shown
}

function SettingInput(props: { label: string; shown: number; editor: SettingEditor }) {
  const [typed, setTyped] = useState<string | null>(null);
  const save = () => {
    const value = Number(typed);
    if (typed !== null && typed.trim() !== "" && Number.isFinite(value) && value !== props.shown) {
      props.editor.onSave(value);
    }
    setTyped(null);
  };
  return (
    <input
      type="number"
      aria-label={props.label}
      className="w-20 rounded border bg-background px-1.5 py-0.5 text-sm font-semibold tabular-nums"
      min={props.editor.min}
      max={props.editor.max}
      step={props.editor.step}
      value={typed ?? String(props.shown)}
      onChange={(e) => {
        setTyped(e.target.value);
      }}
      onBlur={save}
      onKeyDown={(e) => {
        if (e.key === "Enter") save();
      }}
    />
  );
}

export function SettingCard(props: {
  label: string;
  shown: number;
  unit?: string;
  setting: Setting;
  editor?: SettingEditor; // none on a frozen Rubric version
}) {
  const assumption = props.setting.assumption;
  return (
    <div
      className={cn("rounded-lg border bg-card p-3", assumption && ASSUMED)}
      data-testid="rubric-setting"
    >
      <div className="flex items-center gap-1 text-[11px] text-muted-foreground">
        Rubric setting
        {assumption && (
          <span className="ml-auto flex items-center gap-1 text-amber-800 dark:text-amber-300">
            <AlertTriangle className="size-3" /> assumed
          </span>
        )}
      </div>
      <p className="mt-0.5 flex items-center gap-1.5 text-sm">
        {props.label}{" "}
        {props.editor ? (
          <SettingInput label={props.label} shown={props.shown} editor={props.editor} />
        ) : (
          <span className="font-semibold tabular-nums">{props.shown}</span>
        )}
        {props.unit}
      </p>
      {assumption && <p className="mt-1 text-xs">{assumption}</p>}
    </div>
  );
}

export function cm(metres: number): number {
  return Math.round(metres * 1000) / 10;
}
