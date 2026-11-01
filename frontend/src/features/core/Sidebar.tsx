// The workspace sidebar: the Dataset and its Prepare page, then the Project and its stages.
import {
  BarChart3,
  ClipboardCheck,
  Database,
  FolderKanban,
  ListFilter,
  ListChecks,
  MessageSquareText,
  ScanSearch,
  SquareDashedMousePointer,
  Tags,
} from "lucide-react";
import type { ComponentType } from "react";

import { cn } from "@/lib/utils";

import { useDatasetStatus } from "../dataset/useDatasetStatus";
import { HealthStatus } from "./HealthStatus";
import { pageLabels, projectPages, type Page } from "./pages";
import { ThemeToggle } from "./ThemeToggle";

// One Project this week; more Datasets and Projects are a nice-to-have.
const PROJECT_NAME = "Expert pick-and-place";

const icons: Record<Page, ComponentType<{ className?: string }>> = {
  prepare: SquareDashedMousePointer,
  select: ListFilter,
  describe: MessageSquareText,
  episodes: ListChecks,
  review: ScanSearch,
  audit: ClipboardCheck,
  reference: Tags,
  evaluation: BarChart3,
};

export function Sidebar(props: { page: Page; onPage: (page: Page) => void }) {
  const dataset = useDatasetStatus();
  const sources = dataset.data?.sources.map((s) => `${s.name} ${String(s.episodes)}`);
  const nav = (page: Page, count?: string) => (
    <NavItem
      key={page}
      icon={icons[page]}
      label={pageLabels[page]}
      count={count}
      active={props.page === page}
      onClick={() => {
        props.onPage(page);
      }}
    />
  );
  return (
    <aside className="sticky top-0 flex h-screen w-60 shrink-0 flex-col border-r bg-sidebar">
      <div className="flex items-center gap-2 px-4 pt-4 pb-3 text-sm font-semibold">
        <span className="grid size-6 place-items-center rounded bg-primary text-[11px] text-primary-foreground">
          W
        </span>
        Winnow
      </div>
      <div className="px-4">
        <SectionLabel>Dataset</SectionLabel>
        <div className="flex items-center gap-2 text-sm font-medium">
          <Database className="size-3.5 text-muted-foreground" />
          {dataset.data?.name ?? "…"}
        </div>
        <div className="mt-0.5 text-[11px] text-muted-foreground">
          {sources?.length ? sources.join(" · ") : "No Episodes yet"}
        </div>
      </div>
      <nav className="mt-3 px-3">
        {nav("prepare", dataset.data && String(dataset.data.episodes))}
        {nav("select")}
      </nav>
      <div className="mt-4 px-4">
        <SectionLabel>Project</SectionLabel>
      </div>
      <div className="flex-1 px-3">
        <div className="flex items-center gap-2 px-2 py-1.5 text-sm font-medium">
          <FolderKanban className="size-3.5" />
          {PROJECT_NAME}
        </div>
        <div className="ml-3 border-l pl-2">{projectPages.map((page) => nav(page))}</div>
      </div>
      <div className="flex items-center gap-2 border-t px-4 py-3 text-[11px] text-muted-foreground">
        <div className="min-w-0 flex-1">
          <HealthStatus />
        </div>
        <ThemeToggle />
      </div>
    </aside>
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
  label: string;
  count: string | undefined;
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
      <Icon className={cn("size-3.5", props.active ? "text-primary" : "text-muted-foreground")} />
      <span>{props.label}</span>
      <span className="ml-auto text-xs text-muted-foreground tabular-nums">{props.count}</span>
    </button>
  );
}
