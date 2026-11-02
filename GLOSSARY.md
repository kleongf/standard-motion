# Standard Motion

Standard Motion filters recorded robot demonstrations against a plain-English description of what "expert" looks like, keeping the good ones and explaining every rejection.

## Language

**Episode**:
One recorded robot demonstration: the video plus the robot's joint and gripper data, as a single unit of training data.
_Avoid_: Demo, demonstration, trajectory, rollout

**Dataset**:
A named collection of Episodes, possibly from several sources, together with everything about them that doesn't depend on a Description, such as tracks and hand-drawn boxes; several Projects can share one.
_Avoid_: Collection, corpus, source (a **source** is where Episodes were imported from, e.g. droid_100)

**Project**:
One Description applied to one Dataset, holding its Rubric versions, anchor pool, labels, and runs.
_Avoid_: Workspace, job, experiment

**Anchor pool**:
The Episodes of a Project that the Rubric may be written against and whose statistics Rubric-writing screens show: the Dev set during evaluation, otherwise a fixed sample of about 30.
_Avoid_: Sample, preview set, training set

**Description**:
The user's plain-English statement of what an expert Episode looks like; a Rubric is compiled from it.
_Avoid_: Prompt, spec, instructions (an **instruction** is an Episode's own task text, e.g. "Move the black remote to the left")

**Phrase**:
One clause of a Description, the unit that Criteria trace back to and that Reference labels are given per.
_Avoid_: Clause, requirement

**Rubric**:
The set of criteria Standard Motion compiles from a user's Description, used to judge every Episode.
_Avoid_: Filter, spec, checklist; never use for the hackathon's scoring

**Criterion**:
One check within a Rubric, either hard (failing it rejects the Episode) or soft (it adds to a quality score), and either measured (from robot data), tracked (from object/gripper tracks), or visual (judged from video).
_Avoid_: Rule, check, filter

**Quality**:
How an Episode compares with the rest of its run on the soft Criteria: the mean of their robust z's (median and MAD over the Episodes scored), higher being better. It ranks Episodes and never decides one.
_Avoid_: Score, grade

**Criterion result**:
The outcome of one Criterion on one Episode (pass, fail, or unsure), with its Evidence.
_Avoid_: Verdict, score

**Evidence**:
What supports a Criterion result: timestamps, track plots, measurements, or the frame where something went wrong.
_Avoid_: Explanation, justification

**Uncertainty signal**:
Why a Criterion result is unsure rather than pass or fail, e.g. a measurement near its threshold, Spark's samples disagreeing, or a lost track.
_Avoid_: Flag, warning

**Margin multiplier**:
The one number, s, that widens or narrows every measured and tracked Criterion's margin: effective margin = max(noise floor, interview gap) × s. It is 1 until calibration tunes it on the Dev set's interview and review labels, per Rubric version (a new version from Run starts at 1 again; one made by accepting a Threshold suggestion keeps the s the suggestion was made at), and is shown as "s = 1.0 · tuned on N labels", never as a guarantee.
_Avoid_: Scale, temperature, tolerance

**Threshold suggestion**:
A threshold Standard Motion proposes for a Criterion when two or more labels contradict its crisp result: midway between the closest labelled pass and fail values, their gap as its margin. Only accepting it, as a new Rubric version, moves the threshold; labels never do on their own.
_Avoid_: Auto-tune, correction

**Triage decision**:
The per-Episode outcome after all Criterion results are combined: Keep, Reject, or Needs review.
_Avoid_: Verdict, label, classification

**Reason**:
The one-sentence account of why an Episode got its Triage decision, written from its Evidence.
_Avoid_: Explanation, rationale, justification

**Needs review**:
The Triage decision for an Episode Standard Motion isn't confident about, routed to a human instead of being kept or rejected automatically.
_Avoid_: Uncertain, flagged, borderline

**Audit sample**:
A seeded random sample of the Episodes Standard Motion decided on its own (up to 12 Keeps and 5 Rejects) outside the Test set, drawn once per Rubric version and margin multiplier s. An auditor marks each Good (every Phrase passes) or Bad (naming a failing Phrase); the marks measure Keep precision over the sampled Keeps that are still Keeps, and how many good Episodes Standard Motion rejected among the Rejects still rejected, and never change a Triage decision.
_Avoid_: Spot check, QA sample

**Reference label**:
A human's judgment of one Episode against the description, made without seeing what Standard Motion or a baseline said, used to score them.
_Avoid_: Ground truth, gold label, annotation

**Dataset outcome**:
The success or failure flag an Episode ships with in its source dataset; it answers "was the task done", not "does it meet the description".
_Avoid_: Provider label, ground truth

**Test set**:
The Episodes held out from all Rubric writing, calibration, and tuning, used only for reported numbers.
_Avoid_: Eval set, benchmark

**Dev set**:
The Episodes the Rubric may be written, calibrated, and tuned against; never used for reported numbers.
_Avoid_: Train set, validation set

**Demo video**:
The hackathon submission video showing Standard Motion in use.
_Avoid_: Demo (on its own)

**Judging criteria**:
The hackathon's scoring categories (Impact, Use of Meta AI Tooling, Technical Depth, Demo).
_Avoid_: Rubric
