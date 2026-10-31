// The workspace's pages. The current one lives in `?page=` so reloads and links land there.
import { navigate, useSearchParams } from "./url";

// Grouped by the work, in the order it's done: set up the Episodes and their blind labels, curate
// with a Rubric, then measure Winnow against the baselines (only needed to prove it works).
export const setupPages = ["prepare", "reference"] as const;
export const curatePages = ["describe", "episodes", "review", "audit"] as const;
export const measurePages = ["select", "evaluation"] as const;
export type Page =
  (typeof setupPages)[number] | (typeof curatePages)[number] | (typeof measurePages)[number];

export const pageLabels: Record<Page, string> = {
  prepare: "Prepare",
  select: "Selection",
  describe: "Describe & run",
  episodes: "Episodes",
  review: "Review",
  audit: "Audit",
  reference: "Reference labels",
  evaluation: "Evaluation",
};

function isPage(value: string | null): value is Page {
  return value !== null && Object.hasOwn(pageLabels, value);
}

export function readPage(params: URLSearchParams): Page {
  const value = params.get("page");
  return isPage(value) ? value : "prepare";
}

/** Go to a page, leaving any open Episode; `extra` sets that page's own params. */
export function goTo(page: Page, extra: Record<string, string | null> = {}): void {
  navigate({ page, episode: null, t: null, queue: null, ...extra });
}

export function usePage(): [Page, (page: Page) => void] {
  const params = useSearchParams();
  return [
    readPage(params),
    (page) => {
      goTo(page);
    },
  ];
}
