// The export's preview: per source, the Reference-labelled Episodes outside the Test set by
// Triage decision (the columns the choice exports in bold), those awaiting a label, whose
// decisions stay hidden until exported, and the Test set, never exported.
import {
  Table,
  TableBody,
  TableCell,
  TableFooter,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { cn } from "@/lib/utils";

import { exportedOf, totalCounts, type Counts } from "./exportText";
import type { ExportPreview, Include } from "./useExport";

const COLUMNS: { key: keyof Counts; label: string }[] = [
  { key: "keep", label: "Keep" },
  { key: "needs_review", label: "Needs review" },
  { key: "reject", label: "Reject" },
  { key: "awaiting_label", label: "Awaiting label" },
  { key: "test_set", label: "Test set" },
];

function exported(key: keyof Counts, include: Include): boolean {
  return key === "keep" || (key === "needs_review" && include === "keep_and_review");
}

function Cells(props: { counts: Counts; include: Include }) {
  return (
    <>
      {COLUMNS.map(({ key }) => (
        <TableCell
          key={key}
          className={cn(
            "text-right tabular-nums",
            exported(key, props.include) ? "font-medium" : "text-muted-foreground",
          )}
        >
          {props.counts[key]}
        </TableCell>
      ))}
      <TableCell className="text-right font-medium tabular-nums">
        {exportedOf(props.counts, props.include)}
      </TableCell>
    </>
  );
}

export function PreviewTable(props: { preview: ExportPreview }) {
  const { sources, include } = props.preview;
  return (
    <Table aria-label="Export preview">
      <TableHeader>
        <TableRow>
          <TableHead>Source</TableHead>
          {COLUMNS.map(({ key, label }) => (
            <TableHead key={key} className="text-right">
              {label}
            </TableHead>
          ))}
          <TableHead className="text-right">To export</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {sources.map((s) => (
          <TableRow key={s.source}>
            <TableCell className="font-mono text-xs">{s.source}</TableCell>
            <Cells counts={s} include={include} />
          </TableRow>
        ))}
      </TableBody>
      {sources.length > 1 && (
        <TableFooter>
          <TableRow>
            <TableCell>Total</TableCell>
            <Cells counts={totalCounts(sources)} include={include} />
          </TableRow>
        </TableFooter>
      )}
    </Table>
  );
}
