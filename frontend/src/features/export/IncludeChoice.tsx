// What an export includes: the Keeps only (the default), or the Needs review Episodes with them.
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";

import { INCLUDE_LABELS } from "./exportText";
import type { Include } from "./useExport";

const CHOICES: Include[] = ["keep", "keep_and_review"];

export function IncludeChoice(props: { value: Include; onChange: (include: Include) => void }) {
  return (
    <RadioGroup
      aria-label="Include"
      value={props.value}
      onValueChange={(value) => {
        const choice = CHOICES.find((c) => c === value);
        if (choice) props.onChange(choice);
      }}
      className="gap-3"
    >
      {CHOICES.map((choice) => (
        <label key={choice} className="flex cursor-pointer items-center gap-2.5 text-sm">
          <RadioGroupItem value={choice} />
          <span className="font-medium">{INCLUDE_LABELS[choice]}</span>
        </label>
      ))}
    </RadioGroup>
  );
}
