// Every Reference-labelled Episode where Spark alone and Winnow disagree, scored live (the latest
// Rubric version, labels in force, as the Workstation shows it). A row opens its Workstation,
// which shows Winnow only: this list is the one place the contrast appears.
import type { ReactNode } from "react";

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

import { SectionHeading } from "../core/PageHeader";
import { navigate } from "../core/url";
import { SetTag } from "../sets/SetTag";
import { TriageBadge } from "../triage/TriageBadge";
import { useDisagreements, type Disagreement } from "./useEvaluation";

function openWorkstation(episodeId: string) {
  navigate({ page: "episodes", episode: episodeId, t: null, triage: null, queue: null });
}

function Decided(props: { reason: string | null; children: ReactNode }) {
  return (
    <div className="flex flex-col items-start gap-1">
      {props.children}
      {props.reason && (
        <span className="line-clamp-2 text-xs whitespace-normal text-muted-foreground">
          {props.reason}
        </span>
      )}
    </div>
  );
}

function Row(props: { row: Disagreement }) {
  const { row } = props;
  const failed = row.failed_phrases;
  return (
    <TableRow
      className="cursor-pointer align-top"
      data-testid="disagreement"
      onClick={() => {
        openWorkstation(row.episode_id);
      }}
    >
      <TableCell className="font-medium tabular-nums">{row.episode_id}</TableCell>
      <TableCell>
        <SetTag name={row.set_name ?? undefined} />
      </TableCell>
      <TableCell className="w-2/5">
        <Decided reason={row.winnow_reason}>
          <TriageBadge decision={row.winnow} />
        </Decided>
      </TableCell>
      <TableCell className="w-2/5">
        <Decided reason={row.spark_alone_reason}>
          {row.spark_alone ? (
            <TriageBadge decision={row.spark_alone} />
          ) : (
            <span className="text-xs text-muted-foreground">Samples split</span>
          )}
        </Decided>
      </TableCell>
      <TableCell className="text-xs whitespace-normal">
        {failed.length > 0 ? `Fails ${failed.map((p) => `“${p}”`).join(", ")}` : "Meets it"}
      </TableCell>
    </TableRow>
  );
}

export function DisagreementList() {
  const { data, error } = useDisagreements();
  return (
    <div data-testid="disagreements">
      <SectionHeading
        level={2}
        title="Where Spark alone and Winnow disagree"
        info={
          <>
            Every Episode with a Reference label whose Triage decision, as its Workstation shows it
            now, differs from Spark alone&apos;s majority answer; both deciding, but differently,
            first. Click a row to open its Workstation.
          </>
        }
      />
      {error && <p className="mt-2 text-sm text-destructive">{error.message}</p>}
      {data?.length === 0 && (
        <p className="mt-2 text-sm text-muted-foreground">
          No disagreements: on every labelled Episode Spark alone answered, they agree.
        </p>
      )}
      {data && data.length > 0 && (
        <Table className="mt-2" aria-label="Spark alone and Winnow disagree">
          <TableHeader>
            <TableRow>
              <TableHead className="w-28">Episode</TableHead>
              <TableHead className="w-20">Set</TableHead>
              <TableHead>Winnow</TableHead>
              <TableHead>Spark alone</TableHead>
              <TableHead className="w-40">Reference label</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.map((row) => (
              <Row key={row.episode_id} row={row} />
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  );
}
