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
  const [confirming, setConfirming] = useState(false);
  const [unlabelled, setUnlabelled] = useState(0); // kept while the warning closes
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
            if (!data) return;
            setUnlabelled(data.unlabelled);
            if (data.unlabelled > 0) setConfirming(true);
            else run();
          });
        }}
      >
        Export
      </Button>
      <ConfirmExport
        open={confirming}
        unlabelled={unlabelled}
        onOpenChange={setConfirming}
        onConfirm={run}
      />
    </>
  );
}
