// Export writes every Episode outside the Test set by its Triage decision, labelled or not. An
// Episode's decision stays hidden until its blind Reference label, so before exporting ones that
// have none, this says so. It warns and never blocks.
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";

import { unlabelledWarning } from "./exportText";

export function ConfirmExport(props: {
  open: boolean;
  unlabelled: number;
  onOpenChange: (open: boolean) => void;
  onConfirm: () => void;
}) {
  return (
    <AlertDialog open={props.open} onOpenChange={props.onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Export before labelling?</AlertDialogTitle>
          <AlertDialogDescription>{unlabelledWarning(props.unlabelled)}</AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Not yet</AlertDialogCancel>
          <AlertDialogAction onClick={props.onConfirm}>Export anyway</AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
