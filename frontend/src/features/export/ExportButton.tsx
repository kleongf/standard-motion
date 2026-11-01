// Starts an export with the chosen include. If some Episodes aren't Reference-labelled yet,
// ConfirmExport warns first that exporting shows their decisions; it never blocks.
import { useState } from "react";

import { Button } from "@/components/ui/button";

import { ConfirmExport } from "./ConfirmExport";
import { totalCounts } from "./exportText";
import { useStartExport, type ExportPreview } from "./useExport";

export function ExportButton(props: { preview: ExportPreview | undefined; running: boolean }) {
  const start = useStartExport();
  const [confirming, setConfirming] = useState(false);
  const { preview } = props;
  const unlabelled = preview ? totalCounts(preview.sources).awaiting_label : 0;
  const run = () => {
    if (preview) start.mutate(preview.include);
  };
  return (
    <>
      <Button
        disabled={preview?.nothing_exported !== null || props.running || start.isPending}
        onClick={() => {
          if (unlabelled > 0) setConfirming(true);
          else run();
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
