// A frozen Rubric version, read only: what Run froze, and how it sorts the anchor pool. The
// version in use also shows its margin multiplier s, to calibrate, and any thresholds labels
// suggest, each accepted as the next version.
import { CalibrationControl } from "../calibration/CalibrationControl";
import type { SuggestionAction } from "../calibration/SuggestionNote";
import {
  type Calibration,
  useAcceptSuggestion,
  useCalibration,
} from "../calibration/useCalibration";
import { CriterionCard } from "./CriterionCard";
import { cm, SettingCard } from "./SettingCard";
import type { Criterion } from "./useDraft";
import type { AnchorPreview } from "./useDraftEdits";
import { type RubricVersion, useRubric } from "./useRubric";

/** Each suggestion's Accept, by Criterion id; none unless `calibration` is this version's. */
function suggestionsFor(
  version: number,
  calibration: Calibration | undefined,
  accept: ReturnType<typeof useAcceptSuggestion>,
): (criterion: Criterion) => SuggestionAction | undefined {
  return (criterion) => {
    if (calibration?.rubric_version !== version) return undefined;
    const suggestion = calibration.suggestions.find((s) => s.criterion_id === criterion.id);
    if (!suggestion) return undefined;
    return {
      suggestion,
      nextVersion: version + 1,
      pending: accept.isPending,
      onAccept: () => {
        accept.mutate(criterion.id);
      },
    };
  };
}

function Settings(props: { rubric: RubricVersion["rubric"] }) {
  const { gripper_closed_level: closed, grasp_rise_m: rise } = props.rubric.settings;
  return (
    <div className="mt-3 grid grid-cols-2 gap-2">
      <SettingCard label="Gripper closed above" shown={closed.value} setting={closed} />
      <SettingCard
        label="Grasp: the last closure that rises"
        shown={cm(rise.value)}
        unit="cm"
        setting={rise}
      />
    </div>
  );
}

export function VersionPanel(props: {
  version: RubricVersion;
  preview?: AnchorPreview | undefined;
}) {
  const { rubric, origin, created_at: createdAt, version } = props.version;
  const inUseVersion = useRubric().data?.version;
  const inUse = inUseVersion === version;
  // Calibration is the version in use's: only that version shows it.
  const calibration = useCalibration(inUseVersion).data;
  const accept = useAcceptSuggestion();
  const suggestionFor = suggestionsFor(version, calibration, accept);
  const accepted = accept.data?.version.version === version ? accept.data : undefined;
  return (
    <div>
      <p className="mb-3 text-xs text-muted-foreground">
        {origin === "seed" ? "Seeded" : "Run"} {new Date(createdAt).toLocaleString()} · frozen, so
        nothing here can change. Edits go to the draft.
      </p>
      <div className="rounded-lg border bg-card p-4">
        <div className="mb-1 text-[11px] font-medium tracking-wide text-muted-foreground uppercase">
          Description
        </div>
        <p className="text-[15px] leading-7">{rubric.description}</p>
      </div>
      <Settings rubric={rubric} />
      {accepted && (
        <p className="mt-3 text-xs text-muted-foreground" data-testid="accept-note">
          v{version} froze the suggested threshold. {accepted.draft_note}
        </p>
      )}
      {accept.error && <p className="mt-3 text-xs text-destructive">{accept.error.message}</p>}
      {inUse && calibration?.rubric_version === version && (
        <CalibrationControl calibration={calibration} />
      )}
      {rubric.phrases.map((phrase) => {
        const criteria = rubric.criteria.filter((c) => c.phrase === phrase);
        return (
          <section key={phrase} aria-label={`Phrase: ${phrase}`} className="mt-5">
            <span className="rounded bg-muted px-1.5 py-0.5 text-sm">“{phrase}”</span>
            {criteria.length === 0 && (
              <span className="ml-2 text-xs text-muted-foreground">not checked</span>
            )}
            <div className="mt-2 grid gap-2">
              {criteria.map((c) => {
                const preview = props.preview?.criteria.find((p) => p.criterion_id === c.id);
                return (
                  <CriterionCard
                    key={c.id}
                    criterion={c}
                    english={preview?.english ?? c.id}
                    enabled
                    preview={preview}
                    suggestion={inUse ? suggestionFor(c) : undefined}
                  />
                );
              })}
            </div>
          </section>
        );
      })}
    </div>
  );
}
