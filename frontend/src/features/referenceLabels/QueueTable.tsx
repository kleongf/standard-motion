// A queue's Episodes: which are labelled, and, only for those, the Dataset outcome in its own
// column. The relabel pass never shows the outcome or the first pass, so it stays blind.
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

import type { Episode } from "../episodes/useEpisodes";
import { labelledIds, type ReferenceLabel } from "./useReferenceLabels";

function outcome(value: boolean | null): string {
  if (value === null) return "none shipped";
  return value ? "success" : "failure";
}

export function QueueTable(props: {
  episodes: Episode[];
  labels: ReferenceLabel[] | undefined;
  relabel: boolean;
  remaining: string[];
  onOpen: (id: string) => void;
}) {
  const done = labelledIds(props.labels, props.relabel);
  const left = new Set(props.remaining);
  if (props.episodes.length === 0) {
    return (
      <p className="mt-6 text-sm text-muted-foreground">
        No Episodes in this set yet: add them with `winnow sets add`.
      </p>
    );
  }
  return (
    <Table className="mt-4">
      <TableHeader>
        <TableRow>
          <TableHead className="w-32">Episode</TableHead>
          <TableHead>Instruction</TableHead>
          <TableHead className="w-24 text-right">Length</TableHead>
          <TableHead className="w-28">{props.relabel ? "Relabelled" : "Labelled"}</TableHead>
          {!props.relabel && <TableHead className="w-32">Dataset outcome</TableHead>}
        </TableRow>
      </TableHeader>
      <TableBody>
        {props.episodes.map((e) => (
          <TableRow
            key={e.id}
            className={left.has(e.id) ? "cursor-pointer" : "text-muted-foreground"}
            onClick={() => {
              if (left.has(e.id)) props.onOpen(e.id);
            }}
          >
            <TableCell className="font-medium tabular-nums">{e.id}</TableCell>
            <TableCell className="max-w-md truncate">
              {e.instruction ?? <span className="text-muted-foreground">None recorded</span>}
            </TableCell>
            <TableCell className="text-right tabular-nums">{e.duration_s.toFixed(1)} s</TableCell>
            <TableCell>
              {done.has(e.id) ? "yes" : left.has(e.id) ? "to do" : "needs first pass"}
            </TableCell>
            {!props.relabel && (
              <TableCell data-testid={`outcome-${e.id}`}>
                {done.has(e.id) ? outcome(e.dataset_outcome) : ""}
              </TableCell>
            )}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
