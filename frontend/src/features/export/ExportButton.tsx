// Export: every Episode outside the Test set, by its Triage decision, written as LeRobot
// datasets with the Reason for every Episode left out. If some aren't Reference-labelled yet,
// ConfirmExport warns first; ExportStatus shows how it went.
import { useState } from "react";

import { Button } from "@/components/ui/button";

import { useLatestJob } from "../jobs/useLatestJob";
import { ConfirmExport } from "./ConfirmExport";
import { useExportScope } from "./useExportScope";
import { useStartExport } from "./useStartExport";

export function ExportButton() {
  const job = useLatestJob("export").data;
  const start = useStartExport();
  const scope = useExportScope();
  const [unlabelled, setUnlabelled] = useState<number | null>(null);
  const running = job ? !job.finished : false;
  const run = () => {
    start.mutate();
  };
  return (
    <>
      <Button
        size="sm"
        variant="outline"
        disabled={running || start.isPending || scope.isFetching}
        title="Write the kept Episodes in LeRobot format, with a Reason for each one left out"
        onClick={() => {
          void scope.refetch().then(({ data }) => {
            if (data && data.unlabelled > 0) setUnlabelled(data.unlabelled);
            else if (data) run();
          });
        }}
      >
        Export
      </Button>
      <ConfirmExport
        open={unlabelled !== null}
        unlabelled={unlabelled ?? 0}
        onOpenChange={(open) => {
          if (!open) setUnlabelled(null);
        }}
        onConfirm={run}
      />
    </>
  );
}
