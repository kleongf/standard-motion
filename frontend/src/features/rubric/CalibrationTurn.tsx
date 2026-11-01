// Spark's turn at the end of the Describe conversation: the Rubric version in use, its margin
// multiplier s with the Calibrate control, and a way to the thresholds labels suggest for it,
// which are accepted on the version itself (`?version=`).
import { Button } from "@/components/ui/button";

import { CalibrationControl } from "../calibration/CalibrationControl";
import { useCalibration } from "../calibration/useCalibration";
import { navigate } from "../core/url";
import { AgentRow } from "./ThreadParts";
import { useRubric } from "./useRubric";

export function CalibrationTurn() {
  const version = useRubric().data?.version;
  const calibration = useCalibration(version).data;
  if (version === undefined || calibration?.rubric_version !== version) return null;
  const suggested = calibration.suggestions.length;
  return (
    <AgentRow>
      <p>Rubric v{version} is in use. Calibrate its margins on your interview and review labels:</p>
      <CalibrationControl calibration={calibration} />
      {suggested > 0 && (
        <Button
          size="xs"
          variant="link"
          className="mt-1 px-0"
          onClick={() => {
            navigate({ version: String(version) });
          }}
        >
          See the {suggested === 1 ? "threshold" : `${String(suggested)} thresholds`} your labels
          suggest on v{version}
        </Button>
      )}
    </AgentRow>
  );
}
