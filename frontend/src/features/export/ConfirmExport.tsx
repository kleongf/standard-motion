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

function warning(unlabelled: number): string {
  if (unlabelled === 1) {
    return "1 Episode isn’t Reference-labelled yet. Exporting shows its decision; label it first if you want it blind.";
  }
  return `${String(unlabelled)} Episodes aren’t Reference-labelled yet. Exporting shows their decisions; label them first if you want them blind.`;
}

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
          <AlertDialogDescription>{warning(props.unlabelled)}</AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Not yet</AlertDialogCancel>
          <AlertDialogAction onClick={props.onConfirm}>Export anyway</AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
