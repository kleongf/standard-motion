// A small "i" beside a heading that opens its explanation, so the page itself shows only the
// heading.
import { Info } from "lucide-react";
import type { ReactNode } from "react";

import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";

export function InfoTip(props: { label: string; children: ReactNode }) {
  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          type="button"
          aria-label={`About ${props.label}`}
          className="inline-grid size-5 shrink-0 place-items-center rounded text-muted-foreground hover:text-foreground"
        >
          <Info className="size-3.5" />
        </button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-80 text-xs leading-relaxed">
        {props.children}
      </PopoverContent>
    </Popover>
  );
}
