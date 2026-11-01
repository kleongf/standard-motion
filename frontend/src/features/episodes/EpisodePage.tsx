// The full-page Workstation for one Episode: breadcrumb, prev/next on J/K, Esc back.
import { ChevronLeft, ChevronRight } from "lucide-react";
import { useEffect } from "react";

import { Button } from "@/components/ui/button";

import { Page } from "../core/PageHeader";
import { neighbours } from "./neighbours";
import type { Episode } from "./useEpisodes";
import { Workstation } from "./Workstation";

function typing(target: EventTarget | null): boolean {
  return target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement;
}

export function EpisodePage(props: {
  episode: Episode;
  ids: string[];
  initialT: number;
  onOpen: (id: string | null) => void;
}) {
  const { episode, onOpen } = props;
  const { prev, next } = neighbours(props.ids, episode.id);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (typing(event.target) || event.metaKey || event.ctrlKey) return;
      if (event.key === "Escape") onOpen(null);
      else if (event.key === "j" && next) onOpen(next);
      else if (event.key === "k" && prev) onOpen(prev);
    };
    globalThis.addEventListener("keydown", onKey);
    return () => {
      globalThis.removeEventListener("keydown", onKey);
    };
  }, [onOpen, next, prev]);

  return (
    <Page width="full">
      <div className="mb-4 flex items-center gap-2 text-sm">
        <nav aria-label="Breadcrumb" className="flex items-center gap-1.5">
          <button
            type="button"
            className="text-muted-foreground hover:text-foreground"
            onClick={() => {
              onOpen(null);
            }}
          >
            Episodes
          </button>
          <span className="text-muted-foreground">/</span>
          <span className="font-medium">{episode.id}</span>
        </nav>
        <span className="ml-auto text-xs text-muted-foreground">J/K next · previous, Esc back</span>
        <Button
          size="icon-sm"
          variant="outline"
          aria-label="Previous Episode"
          disabled={!prev}
          onClick={() => {
            onOpen(prev);
          }}
        >
          <ChevronLeft />
        </Button>
        <Button
          size="icon-sm"
          variant="outline"
          aria-label="Next Episode"
          disabled={!next}
          onClick={() => {
            onOpen(next);
          }}
        >
          <ChevronRight />
        </Button>
      </div>
      <Workstation episode={episode} initialT={props.initialT} />
    </Page>
  );
}
