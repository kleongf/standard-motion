// Every export written under the data dir's exports/, newest first: where, when, how many
// Episodes and what it included.
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

import { CopyPath } from "./CopyPath";
import { INCLUDE_LABELS } from "./exportText";
import type { PastExport } from "./useExport";

const DATE_FORMAT = new Intl.DateTimeFormat(undefined, {
  year: "numeric",
  month: "short",
  day: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
});

export function PastExports(props: { exports: PastExport[] }) {
  if (props.exports.length === 0) {
    return <p className="mt-2 text-sm text-muted-foreground">No exports yet.</p>;
  }
  return (
    <Table className="mt-2 table-fixed" aria-label="Past exports">
      <TableHeader>
        <TableRow>
          <TableHead>Folder</TableHead>
          <TableHead className="w-44">Exported</TableHead>
          <TableHead className="w-24 text-right">Episodes</TableHead>
          <TableHead className="w-44">Included</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {props.exports.map((e) => (
          <TableRow key={e.path}>
            <TableCell>
              <CopyPath path={e.path} />
            </TableCell>
            <TableCell className="tabular-nums">
              {DATE_FORMAT.format(new Date(e.created_at))}
            </TableCell>
            <TableCell className="text-right tabular-nums">{e.episodes}</TableCell>
            <TableCell>{INCLUDE_LABELS[e.include]}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
