// The workspace sidebar: the Dataset and Project it works on, then its pages grouped by the work:
// numbered steps to set up and curate, each with where it stands and the next one marked, and the
// pages that measure Standard Motion.
import {
  BarChart3,
  ClipboardCheck,
  Database,
  FolderKanban,
  FolderOutput,
  ListFilter,
  ListChecks,
  MessageSquareText,
  ScanSearch,
  SquareDashedMousePointer,
  Tags,
} from "lucide-react";
import type { ComponentType, ReactNode } from "react";

import { cn } from "@/lib/utils";

import { useDatasetStatus } from "../dataset/useDatasetStatus";
import { HealthStatus } from "./HealthStatus";
import { Logo } from "./Logo";
import { nextStep, stepNotes } from "./flow";
import { curatePages, measurePages, pageLabels, setupPages, type Page } from "./pages";
import { ThemeToggle } from "./ThemeToggle";
import { useFlow } from "./useFlow";

// One Project this week; more Datasets and Projects are a nice-to-have.
const PROJECT_NAME = "Expert pick-and-place";

const icons: Record<Page, ComponentType<{ className?: string }>> = {
  prepare: SquareDashedMousePointer,
  select: ListFilter,
  describe: MessageSquareText,
  episodes: ListChecks,
  review: ScanSearch,
  audit: ClipboardCheck,
  export: FolderOutput,
  reference: Tags,
  evaluation: BarChart3,
};

export function Sidebar(props: { page: Page; onPage: (page: Page) => void }) {
  const dataset = useDatasetStatus();
  const sources = dataset.data?.sources.map((s) => `${s.name} ${String(s.episodes)}`);
  const counts = useFlow();
  const notes = stepNotes(counts);
  const next = nextStep(counts);
  const nav = (page: Page, step?: number) => (
    <NavItem
      key={page}
      icon={icons[page]}
      step={step}
      label={pageLabels[page]}
      note={notes[page]}
      next={next === page}
      active={props.page === page}
      onClick={() => {
        props.onPage(page);
      }}
    />
  );
  return (
    <aside className="sticky top-0 flex h-screen w-60 shrink-0 flex-col border-r bg-sidebar">
      <div className="flex items-center gap-2 px-4 pt-4 pb-3 text-sm font-semibold">
        <Logo className="size-6" />
        Standard Motion
      </div>
      <div className="grid gap-2 px-4 text-sm">
        <div>
          <div className="flex items-center gap-2 font-medium">
            <Database className="size-3.5 text-muted-foreground" />
            {dataset.data?.name ?? "…"}
          </div>
          <div className="mt-0.5 pl-5.5 text-[11px] text-muted-foreground">
            {sources?.length ? sources.join(" · ") : "No Episodes yet"}
          </div>
        </div>
        <div className="flex items-center gap-2 font-medium">
          <FolderKanban className="size-3.5 text-muted-foreground" />
          {PROJECT_NAME}
        </div>
      </div>
      <nav aria-label="Steps" className="mt-4 flex flex-1 flex-col gap-4 overflow-y-auto px-3">
        <NavGroup label="Set up">{setupPages.map((page, i) => nav(page, i + 1))}</NavGroup>
        <NavGroup label="Curate">
          {curatePages.map((page, i) => nav(page, setupPages.length + i + 1))}
        </NavGroup>
        <NavGroup label="Measure">{measurePages.map((page) => nav(page))}</NavGroup>
      </nav>
      <div className="flex items-center gap-2 border-t px-4 py-3 text-[11px] text-muted-foreground">
        <div className="min-w-0 flex-1">
          <HealthStatus />
        </div>
        <ThemeToggle />
      </div>
    </aside>
  );
}

function NavGroup(props: { label: string; children: ReactNode }) {
  return (
    <div>
      <div className="px-2">
        <SectionLabel>{props.label}</SectionLabel>
      </div>
      {props.children}
    </div>
  );
}

function SectionLabel(props: { children: string }) {
  return (
    <div className="mb-1 text-[11px] font-medium tracking-wide text-muted-foreground uppercase">
      {props.children}
    </div>
  );
}

function NavItem(props: {
  icon: ComponentType<{ className?: string }>;
  step: number | undefined;
  label: string;
  note: string | undefined;
  next: boolean;
  active: boolean;
  onClick: () => void;
}) {
  const Icon = props.icon;
  return (
    <button
      type="button"
      aria-current={props.active ? "page" : undefined}
      onClick={props.onClick}
      className={cn(
        "flex w-full items-center gap-2 rounded px-2 py-1.5 text-sm",
        props.active ? "bg-primary/10 font-medium text-primary" : "hover:bg-muted",
      )}
    >
      {props.step === undefined ? (
        <Icon
          className={cn("size-4 p-px", props.active ? "text-primary" : "text-muted-foreground")}
        />
      ) : (
        <span
          className={cn(
            "grid size-4 shrink-0 place-items-center rounded-full text-[10px] font-semibold tabular-nums",
            props.next || props.active
              ? "bg-primary text-primary-foreground"
              : "bg-muted-foreground/15 text-muted-foreground",
          )}
        >
          {props.step}
        </span>
      )}
      <span className="min-w-0 flex-1 truncate text-left">
        {props.label}
        {props.next && (
          <span className="block text-[11px] leading-tight font-medium text-primary">
            Next step
          </span>
        )}
      </span>
      <span
        className={cn(
          "shrink-0 text-xs font-normal tabular-nums",
          props.next ? "text-primary" : "text-muted-foreground",
        )}
      >
        {props.note}
      </span>
    </button>
  );
}
