import { fireEvent, render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";

import { AnsweredCard } from "./AnsweredCard";
import { QuestionCard } from "./QuestionCard";
import type {
  DisagreeQuestion,
  HardSoftQuestion,
  InterviewAnswer,
  PhraseQuestion,
  SettingQuestion,
  ThresholdQuestion,
} from "./useInterview";

const threshold: ThresholdQuestion = {
  kind: "threshold",
  key: "threshold:longest-still-s",
  prompt: "Is 1.8 s fine for “no long pauses”?",
  options: [
    { answer: "pass", label: "Fine: “no long pauses” passes" },
    { answer: "fail", label: "Not fine: “no long pauses” fails" },
    { answer: "skip", label: "Skip: leave this threshold assumed" },
  ],
  criterion_id: "longest-still-s",
  phrase: "no long pauses",
  english: "Longest stretch with the arm under 0.01 m/s < 1 s",
  episode_id: "droid_100:6",
  value: 1.8,
  measurement: "1.8 s",
  camera: "exterior_1_left",
  clip: { start: 1.2, end: 4.0 },
  asked: 1,
  max_questions: 3,
  near: 2,
};

const unsupported: PhraseQuestion = {
  kind: "phrase",
  key: "phrase:40",
  prompt: "Nothing checks “never drops it”. Nothing tracks the object yet. What should …",
  options: [
    { answer: "accept", label: "Leave it unchecked: it never fails an Episode" },
    { answer: "context", label: "Mark it Context: it describes, it doesn't require" },
  ],
  text: "never drops it",
  start: 40,
  end: 54,
  reason: "Nothing tracks the object yet.",
};

test("a threshold card plays the measured stretch with its value, and its options say which passes", () => {
  const onAnswer = vi.fn();
  render(<QuestionCard question={threshold} pending={false} onAnswer={onAnswer} />);

  expect(screen.getByLabelText("Episode clip")).toHaveAttribute(
    "src",
    "/api/episodes/droid_100%3A6/clips/exterior_1_left#t=1.2,4",
  );
  expect(screen.getByTestId("clip-value")).toHaveTextContent("1.8 s");
  expect(screen.getByText(/^Question 2 of at most 3/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Not fine: “no long pauses” fails" }));
  expect(onAnswer).toHaveBeenCalledWith("fail");
});

test("a Phrase card can send the curator to edit the sentence instead", () => {
  const onEditSentence = vi.fn();
  render(
    <QuestionCard
      question={unsupported}
      pending={false}
      onAnswer={vi.fn()}
      onEditSentence={onEditSentence}
    />,
  );

  fireEvent.click(screen.getByRole("button", { name: "Edit the sentence" }));
  expect(onEditSentence).toHaveBeenCalledWith(40, 54);
});

test("an answered card shows its answer and effect, and undoes it", () => {
  const answer: InterviewAnswer = {
    id: 7,
    key: "threshold:longest-still-s",
    kind: "threshold",
    subject: "no long pauses",
    episode_id: "droid_100:6",
    measurement: "1.8 s",
    answer: "fail",
    effect: "Labelled droid_100:6 fail on “no long pauses”. Threshold 2 s → 1.5 s, margin ± 0.3 s.",
    changed_criterion: "longest-still-s",
    label_id: 3,
    resolution: "set",
    answered_at: "2026-10-29T12:00:00Z",
  };
  const onUndo = vi.fn();
  render(<AnsweredCard answer={answer} pending={false} onUndo={onUndo} onShow={vi.fn()} />);

  expect(screen.getByRole("article")).toHaveTextContent("1.8 s on droid_100:6: not fine");
  expect(screen.getByRole("article")).toHaveTextContent("Threshold 2 s → 1.5 s");
  fireEvent.click(screen.getByRole("button", { name: "Undo" }));
  expect(onUndo).toHaveBeenCalledWith(7);
});

const hardSoft: HardSoftQuestion = {
  kind: "hard_soft",
  key: "hard:grasp-attempts",
  prompt:
    "If an Episode fails “Grasp attempts ≤ 1”, should it be rejected outright, or only lower its quality?",
  options: [
    { answer: "hard", label: "Hard: reject it outright" },
    { answer: "soft", label: "Soft: only lower its quality" },
    { answer: "skip", label: "Skip: leave it hard" },
  ],
  criterion_id: "grasp-attempts",
  phrase: "on the first try",
  english: "Grasp attempts ≤ 1",
  hard: true,
};

const setting: SettingQuestion = {
  kind: "setting",
  key: "setting:gripper_closed_level",
  prompt: "Is the gripper closed at this moment?",
  options: [
    { answer: "pass", label: "Closed" },
    { answer: "fail", label: "Open" },
    { answer: "skip", label: "Skip: leave this setting assumed" },
  ],
  setting: "gripper_closed_level",
  name: "Gripper closed level",
  assumption: "Closed above 0.2 of the gripper's range.",
  episode_id: "droid_100:6",
  value: 1,
  measurement: "closed to 1.00",
  camera: "wrist_image_left",
  clip: { start: 0.5, end: 2.5 },
  asked: 0,
  max_questions: 3,
};

test("a hard/soft card asks about the Criterion, with no sentence to edit", () => {
  const onAnswer = vi.fn();
  render(
    <QuestionCard
      question={hardSoft}
      pending={false}
      onAnswer={onAnswer}
      onEditSentence={vi.fn()}
    />,
  );

  expect(screen.getByText("Hard or soft")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Edit the sentence" })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Soft: only lower its quality" }));
  expect(onAnswer).toHaveBeenCalledWith("soft");
});

test("a setting card plays the moment and names the setting and its assumption", () => {
  const onAnswer = vi.fn();
  render(<QuestionCard question={setting} pending={false} onAnswer={onAnswer} />);

  expect(screen.getByText("Assumed grasp setting")).toBeInTheDocument();
  expect(screen.getByLabelText("Episode clip")).toHaveAttribute(
    "src",
    "/api/episodes/droid_100%3A6/clips/wrist_image_left#t=0.5,2.5",
  );
  expect(screen.getByTestId("clip-value")).toHaveTextContent("closed to 1.00");
  expect(screen.getByText(/Gripper closed level · Closed above 0\.2/)).toBeInTheDocument();
  expect(screen.getByText(/^Question 1 of at most 3/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Closed" }));
  expect(onAnswer).toHaveBeenCalledWith("pass");
});

function answered(fields: Partial<InterviewAnswer>): InterviewAnswer {
  return {
    id: 8,
    key: "",
    kind: "phrase",
    subject: "",
    episode_id: null,
    measurement: null,
    answer: "skip",
    effect: "",
    changed_criterion: null,
    label_id: null,
    resolution: null,
    answered_at: "2026-10-30T12:00:00Z",
    ...fields,
  };
}

test("answered hard/soft and setting cards say what was answered in their own words", () => {
  render(
    <>
      <AnsweredCard
        answer={answered({ kind: "hard_soft", subject: "Grasp attempts ≤ 1", answer: "soft" })}
        pending={false}
        onUndo={vi.fn()}
        onShow={vi.fn()}
      />
      <AnsweredCard
        answer={answered({
          kind: "setting",
          key: "setting:grasp_rise_m",
          subject: "Grasp rise",
          episode_id: "droid_100:6",
          measurement: "rose 9.8 cm",
          answer: "fail",
        })}
        pending={false}
        onUndo={vi.fn()}
        onShow={vi.fn()}
      />
    </>,
  );

  const [hard, rise] = screen.getAllByRole("article");
  expect(hard).toHaveTextContent("“Grasp attempts ≤ 1”: soft");
  expect(rise).toHaveTextContent("Grasp rise: rose 9.8 cm on droid_100:6, not lifted");
});

const disagree: DisagreeQuestion = {
  kind: "disagree",
  key: "disagree:23",
  prompt: "Its Criteria disagree on this Episode. Does “a quick, clean grasp” pass?",
  options: [
    { answer: "pass", label: "Pass: “a quick, clean grasp” passes" },
    { answer: "fail", label: "Fail: “a quick, clean grasp” fails" },
    { answer: "skip", label: "Skip: let its Criteria decide" },
  ],
  phrase: "a quick, clean grasp",
  episode_id: "droid_100:6",
  measurement: "1 fails, 1 passes",
  camera: "exterior_1_left",
  clip: { start: 0, end: 6.5 },
  results: [
    {
      criterion_id: "grasp-attempts",
      english: "Grasp attempts ≤ 1",
      status: "pass",
      measurement: "1 attempt",
      unconfirmed: false,
    },
    {
      criterion_id: "active-duration-s",
      english: "Time the arm is moving < 1 s",
      status: "fail",
      measurement: "5.2 s",
      unconfirmed: false,
    },
  ],
};

test("a disagree card plays the Episode and shows each Criterion's result beside Pass and Fail", () => {
  const onAnswer = vi.fn();
  render(<QuestionCard question={disagree} pending={false} onAnswer={onAnswer} />);

  expect(screen.getByText("Criteria disagree")).toBeInTheDocument();
  expect(screen.getByLabelText("Episode clip")).toHaveAttribute(
    "src",
    "/api/episodes/droid_100%3A6/clips/exterior_1_left#t=0,6.5",
  );
  const results = screen.getAllByTestId("disagree-result");
  expect(results.map((r) => r.textContent)).toEqual([
    "passGrasp attempts ≤ 11 attempt",
    "failTime the arm is moving < 1 s5.2 s",
  ]);
  fireEvent.click(screen.getByRole("button", { name: "Fail: “a quick, clean grasp” fails" }));
  expect(onAnswer).toHaveBeenCalledWith("fail");
});

test("an answered disagree card says what the Phrase did on the Episode", () => {
  render(
    <AnsweredCard
      answer={answered({
        kind: "disagree",
        key: "disagree:23",
        subject: "a quick, clean grasp",
        episode_id: "droid_100:6",
        measurement: "1 fails, 1 passes",
        answer: "fail",
      })}
      pending={false}
      onUndo={vi.fn()}
      onShow={vi.fn()}
    />,
  );

  expect(screen.getByRole("article")).toHaveTextContent(
    "“a quick, clean grasp” on droid_100:6: fails",
  );
});
