// The $0 source ablation and SAM's tracking health: what each Meta model adds to Winnow, and how
// often SAM lost the object. Both are re-scored from what is stored, with no Meta call.
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

import { SectionHeading } from "../core/PageHeader";
import { Rate } from "./Rate";
import type { AblationRow, TrackHealthRow } from "./useEvaluation";

export function AblationTable(props: { rows: AblationRow[] }) {
  return (
    <div data-testid="source-ablation">
      <SectionHeading
        level={3}
        title="Source ablation"
        info={
          <>
            Winnow re-scored from the cache with only some sources&apos; Criteria, as if the Rubric
            had been compiled without the others; a Phrase only they checked goes unchecked. No Meta
            call is made, so it costs $0.
          </>
        }
      />
      <Table className="mt-2" aria-label="Source ablation">
        <TableHeader>
          <TableRow>
            <TableHead>Sources</TableHead>
            <TableHead className="text-right">Criteria</TableHead>
            <TableHead>False keeps</TableHead>
            <TableHead>Right reason</TableHead>
            <TableHead>Coverage</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {props.rows.map((row) => (
            <TableRow key={row.mask} data-testid={`ablation-${row.mask}`}>
              <TableCell className="font-medium">{row.label}</TableCell>
              <TableCell className="text-right tabular-nums">
                {row.criteria} of {row.of}
              </TableCell>
              <TableCell>
                <Rate p={row.false_keeps} />
              </TableCell>
              <TableCell>
                {row.right_reason ? (
                  <Rate p={row.right_reason} />
                ) : (
                  <span className="text-xs text-muted-foreground">No slack yet</span>
                )}
              </TableCell>
              <TableCell>
                <Rate p={row.coverage} />
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

export function TrackingHealthTable(props: { rows: TrackHealthRow[] }) {
  return (
    <div data-testid="tracking-health">
      <SectionHeading
        level={3}
        title="SAM tracking health"
        info={
          <>
            A track is lost when a box swells past 4× the median, jumps over a box-width in a frame,
            or is missing on over 20% of frames. Needs review counts Episodes where a hard Criterion
            reading the lost track is unsure because of it; too small counts lost tracks on Episodes
            excluded at selection as &ldquo;object too small to see&rdquo;.
          </>
        }
      />
      <Table className="mt-2" aria-label="SAM tracking health">
        <TableHeader>
          <TableRow>
            <TableHead>Track</TableHead>
            <TableHead>Flagged lost</TableHead>
            <TableHead className="text-right">Needs review</TableHead>
            <TableHead className="text-right">Too small</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {props.rows.map((row) => (
            <TableRow key={row.kind}>
              <TableCell className="font-medium">{row.label}</TableCell>
              <TableCell>
                <Rate p={row.lost} />
              </TableCell>
              <TableCell className="text-right tabular-nums">{row.needs_review}</TableCell>
              <TableCell className="text-right tabular-nums">{row.too_small}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
