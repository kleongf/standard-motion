// Editing the draft on its Criterion cards. A threshold mid-drag is held here, unsaved, and
// previewed on the anchor pool as it moves; letting go saves it. Toggles and settings save at
// once. None of it calls a model. While a compile is under way the cards are read-only: it may
// replace the Criteria being edited.
import { useState } from "react";

import type { CardEditor } from "./CriterionCard";
import { roundThreshold } from "./histogram";
import type { DraftEditing } from "./RubricPanel";
import type { Criterion, RubricDraft } from "./useDraft";
import { useDraftPreview, useEditDraft } from "./useDraftEdits";

type Thresholds = Record<string, number>;

function without(thresholds: Thresholds, id: string): Thresholds {
  return Object.fromEntries(Object.entries(thresholds).filter(([key]) => key !== id));
}

export function useDraftEditor(draft: RubricDraft | null | undefined, compiling: boolean) {
  const [dragged, setDragged] = useState<Thresholds>({});
  const edit = useEditDraft();
  const criteria = Object.fromEntries(
    Object.entries(dragged).map(([id, threshold]) => [id, { threshold }]),
  );
  const preview = useDraftPreview({ criteria }, Boolean(draft));

  const cardEditor = (criterion: Criterion): CardEditor => ({
    threshold: dragged[criterion.id] ?? criterion.threshold,
    onDrag: (value) => {
      setDragged((d) => ({ ...d, [criterion.id]: roundThreshold(value, criterion.unit) }));
    },
    onCommit: (value) => {
      const threshold = roundThreshold(value, criterion.unit);
      edit.mutate(
        { criteria: { [criterion.id]: { threshold } } },
        // Held until saved, so the preview never shows the old threshold in between.
        {
          onSettled: () => {
            setDragged((d) => without(d, criterion.id));
          },
        },
      );
    },
    onEdit: (change) => {
      edit.mutate({ criteria: { [criterion.id]: change } });
    },
  });

  const editing: DraftEditing = {
    preview: preview.data,
    editorFor: (criterion) => (compiling ? undefined : cardEditor(criterion)),
    onSettings: (settings) => {
      edit.mutate({ criteria: {}, ...settings });
    },
  };
  return { editing, preview: preview.data, error: edit.error ?? preview.error };
}
