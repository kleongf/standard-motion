# Standard Motion — Project Plan

*Meta Global AI Developer Hackathon · Indie Developer track · Theme: Push the Frontier (robotics)*

**Working name:** Standard Motion
**Alternatives:** Plainsight, Assay, Sift, Keepers

---

## 1. The pitch (keep it this short)

**One line:** Describe what a good robot demonstration looks like. Standard Motion watches every one and keeps only those.

**Problem (one sentence):** Robots learn from human demonstrations, but teams can't watch thousands of them, and today's best AI judges say "success" when they're unsure, so bad demos slip into training.

**Solution (one sentence):** You write "expert" in plain English; Meta's models check every episode against it, keep the good ones, flag the uncertain ones for a human, and show exactly why each rejected one failed.

**Why I'm building it:** My robotics club (Triton Droids) is training a ping pong policy and struggling to curate expert demonstrations. Standard Motion is my own project; ping pong is the motivation, not the product.

**Pitch test:** a non-roboticist should be able to repeat the one-liner back after hearing it once.

---

## 2. The problem, with numbers

| Fact | Number | Source |
|---|---|---|
| Cost of teleoperation data (standard pick-and-place, fully loaded) | ~$118 / hour (early 2026), down from ~$340 in early 2024 | Robotics Center, State of Robotics 2026 |
| Share of collected demos rejected in quality review | 15–30% | Axis Robotics guide |
| How much of the data humans actually review | 1–5% weekly random sample, or 10–20% per session | Robotics Center checklist; Claru guide |
| Best AI success judge on 2,197 robot attempts (~1,600 real, ~600 simulated; FailBench) | 0.77 mean balanced accuracy; the best overall judge (Gemini 3 Flash) catches only 40% of failures on a 30-episode failure-only subset (REFLECT; other models range 0–100% there). A lean toward "success" under ambiguity is reported qualitatively (one model's reasoning traces), not measured | FailBench (Sep 2026) |
| Where AI judges fail | Strong on some visible-object-motion sources (0.89–0.95), but only 0.72 on the DROID robot slice; no model exceeds 0.60 on contact-heavy tasks. Cropping to the region that decides the outcome raises the DROID slice from 0.740 to 0.810 (+7 points) | FailBench |
| Gain from curating demos (Demo-SCORE) | 15–35% higher absolute policy success vs training on all demos | Demo-SCORE paper |
| Gain from filtering to the top 25% of demos | 30–50% higher success on contact-rich tasks | Mandlekar et al., via Claru |
| Effect of low-quality data | 20% low-quality examples → 30% worse training loss (Open X-Embodiment) | Hugging Face blog |
| Robot training data market | Estimates: >$242M (2025) → $5.25B (2030); or $536M (2025) → $750M (2026) | ResearchInChina; LP Information |

**Pitch line:** *Teams watch only a fraction of their robot demos, and today's best AI judges still miss most real failures in hard cases: the best judge caught 40% on FailBench's 30-episode failure-only set and scored 0.72 balanced accuracy on DROID robots. That's exactly backwards for cleaning data.*

> ⚠️ Do NOT claim "1 in 5 failures in droid_100 were never flagged." Those 19 episodes came from DROID's raw `/failure/` folders; their outcome survives in `next.reward` (0 on the last frame), but their task instructions were dropped during format conversion. It's a real data-quality issue but not "undetected failures." Episode 42 (marked success: three failed grasps, then the object released ~10 cm above the target) is still a fair example.

---

## 3. Who has the problem

1. **Robot-learning teams at labs and student clubs** (primary user in the pitch). No QA staff; curation = someone scrubbing videos. Firsthand story: Triton Droids.
2. **Humanoid / robotics companies' data operations.** Figure is hiring dedicated TeleOps Quality Support staff to review teleop sessions. 1X reportedly has 700+ gig operators collecting data at home. Volume grows faster than anyone can watch.
3. **Data platforms and vendors** (Encord, Labelbox, Claru). Encord reports total revenue up more than 10× in the 18 months before its Feb 2026 round (not physical-AI revenue specifically) — evidence of a growing market, and potential future customers or competitors.

---

## 4. Existing approaches and the gap

| Approach | Examples | What it misses |
|---|---|---|
| Motion-quality metrics | FiftyOne episode quality (smoothness, jerk, idle time) | Measures *how* it moved, not whether it did the task the way your team means "expert" |
| Teleop feedback | DQAF (May 2026) | Fixed metric set (telemetry + VLM subtask progress) for live operator feedback; no arbitrary criteria, no abstention |
| Rollout-based curation | Demo-SCORE, CUPID | Needs a trained policy + 25–100 robot rollouts; fails when demos are too poor for a first policy to succeed |
| Failure detectors | RoboFAC, Guardian, RoboReward, Instance (YC S26) | Pass/fail only; FailBench's fine-tuned detectors (Guardian, RoboReward-8B, ViFailback-8B, RoboFAC-7B, FailSense) underperform general models. Instance isn't in FailBench |
| Rubric-based QA services | Shotwell AI (YC Spring 2026) | Step-by-step pass/fail against the customer's SOP with timestamps, LeRobot input; a 24-hour service, with no stated use of robot telemetry or uncertainty (vendor claims) |
| Natural-language search | Roboto Agents (Jul 2026) | Finds *moments* from a plain-language description across logs and video; doesn't judge Episodes against a quality bar |
| Data platforms | Encord, Labelbox | General infrastructure, not task-semantic judgment |

**Gap:** Tools now exist that score or search robot Episodes (Shotwell, Roboto, DQAF, commercial scoring services). None that we found turns a team's own English definition of "expert" into checks over robot data, object tracks *and* video, or reports how often its "keep" is wrong and abstains when unsure. An independent audit of one commercial scorer found it gave robot telemetry zero weight and its human corrections only raised scores (CosmicBrain, Oct 2026).

**Nuance to design for:** CUPID found "higher quality" doesn't always mean "better robot" (quality filtering can favor brittle strategies). This supports user-defined criteria (e.g., "always uses the same grasp strategy") over generic smoothness scores.

---

## 5. How Standard Motion works

1. **Describe (an interview)** — e.g. *"Expert pick-and-place: grasps on the first try, never drops the object, places it inside the target, no long pauses."* Spark drafts the Rubric and splits the Description into Phrases (each Checked, Context, or Unsupported); Standard Motion's code checks coverage: Phrases no Criterion covers, and values Spark had to assume. Code then picks questions anchored on Episodes from an **anchor pool** (the Dev set during evaluation; no dataset-wide numbers before the run), worded from templates: uncovered Phrases first, then assumed thresholds by bisection ("Is this 1.8 s pause long?", ≤ 3 per threshold, margin = the bracketing gap), then hard/soft and the grasp settings, then Episodes where a Phrase's Criteria disagree. Spark recompiles only when the user answers in free text. It ends when every Phrase is covered; Run never blocks, and leftover assumptions stay visible. Every answer is also a label, keyed by (Episode, Phrase). Decided in [Rubric compile and the Describe interview](https://github.com/kleongf/winnow/issues/18).
2. **Compile** — each Criterion is a **typed call** to one fixed primitive with one comparator (params, threshold, unit, margin, window, camera views, source Phrase), and the English shown to the user is rendered from those fields, so the Rubric and the code can't drift apart. A Phrase may compile to several Criteria from different sources (e.g. placement = a visual question + box overlap with a SAM text-prompted target box); all run, and their disagreement is an uncertainty signal. One Spark call with a capabilities manifest, one repair turn, else Unsupported. Hard or soft comes from the wording. The user drags thresholds, toggles hard/soft, or disables a Criterion directly; structural changes go through the chat. Spark routes each Criterion to the cheapest source that can decide it:
   - **Measured from robot data** (end-effector pose + gripper in droid_100; joint states and camera extrinsics too in droid_1.0.1): failed grasp attempts, pauses, completion time, release height, path efficiency.
   - **Tracked from SAM 3.1** across the views each Criterion needs (wrist for in-hand, one boxed exterior view for placement): object slips in transit, falls after release, moved, overlaps the target box at the end.
   - **Visual** (Spark on a specific moment the measurements point to, cropped to the SAM box): what geometry can't decide, e.g. "grasped by the handle", spills, upright.
   - Each Criterion is **hard** (fail = reject) or **soft** (adds to a quality score; scored relative to the dataset, never rejects alone). A free dry run shows each Criterion's pass rate before the user confirms.
3. **Score** — every Episode gets per-Criterion results with Evidence (value, threshold, time window, track plot, the frame where it went wrong). Every visual Criterion runs as a fixed-shape Spark call (no investigator tool loop: slides-only this week). The **Reason** is a template first, with Spark's Reason swapped in if built.
4. **Triage with self-monitoring** — Criterion results resolve per Phrase: a Phrase **fails** on any crisp *conclusive* fail (a per-primitive flag: `release_height_m` is inconclusive because of stacking; `final_overlap`, the other primitives and a unanimous `ask_video` are conclusive), **passes** when one of its Criteria passes crisply and the rest are only unsure, unless one of those is an inconclusive primitive's, whose fail or unsure always blocks (changed Nov 3 on the Dev set, where a Phrase's second check rarely had evidence), and is otherwise unsure. Then a weakest link over hard Phrases: any failing → Reject (Reason from the earliest-in-time conclusive fail); all passing → Keep; otherwise Needs review, with its Uncertainty signals as the Reason. No Spark refuter: a Reject is final unless a human label overrides it. Soft Criteria never touch the decision; their robust z (median/MAD within the run) averages into a quality score. Uncertainty signals:
   - measurement within a Criterion's margin of its threshold; `grasp_attempts` is unsure when any closure sits within the margins of the gripper-closed level or the 2 cm grasp rule (Episode 49)
   - Spark's 3 paraphrased samples split 2–1, or any answers "unsure"; no extra samples on splits
   - an inconclusive fail with nothing to back it (the "sources disagree" case)
   - lost track in the Criterion's window: box area > 4× the track's median, centre jump > 1 box-width between 5 fps frames, or no box on > 20% of frames (not SAM confidence; thresholds re-checked on the Dev set)
   - source missing or step failed
   - **second opinion** (if built): Glimmer on keyframes disagrees with a unanimous Spark answer on an end-state Criterion; it can only add Needs review, never resolve it
   - **Rubric sanity monitor** (a Rubric warning, never per Episode): a hard Criterion failing < 2% or > 95% of Episodes (Wilson interval), plus the Episodes only it rejects. Also on the dry run.
   - **Confidence** (for the risk–coverage curve, review order, matched coverage): measured/tracked p = 1/(1 + e^(−3m)) with m the signed margin distance; visual p = (agreeing + 1)/(K + 2), ties broken by stated confidence (the same score as Spark alone); inconclusive fails clamped to ≥ 0.5; no value → 0.5; human label → 1 or 0. Phrase = min over its Criteria; P_keep = min over hard Phrases; confidence = max(P_keep, 1 − P_keep).
5. **Calibrate** — every human label is keyed by (Episode, Phrase) with a `source`: interview, review or audit (Reference labels stay separate and only score). Any human label overrides that Phrase's result for that Episode. **Interview and review labels** (Needs review strictly least confident first) tune one global margin multiplier s: effective margin = max(noise floor, interview gap) × s, scanned over {2, 1.5, 1, 0.75, 0.5} widest first, stopping at the last s whose labelled (Episode, Phrase) errors have a one-sided Clopper–Pearson upper bound ≤ 0.2 at 90%; a leave-one-out check shows "margins unstable" if dropping 2 labels moves s; shown as "tuned on N labels", never a guarantee. Two or more contradicting labels *suggest* a threshold (midpoint between the closest labelled pass and fail) the user may accept as a new Rubric version. **Audit labels** (a seeded uniform sample of 12 auto-Keeps, plus 5 auto-Rejects if budget allows; a bad mark names its Phrase) are the only input to precision, reported as a count plus a Wilson interval ("14/15 good, 95% CI 0.70–0.99"; all-good also shows the one-sided "≥ 0.86 (90%)"), never "±". In evaluation all tuning labels come from the Dev set. *"Label 20 Episodes (8 review + 12 audit), curate 2,000."* Decided in [Triage decision rule and calibration](https://github.com/kleongf/winnow/issues/19).
6. **Output** — filtered dataset in the same (LeRobot) format + a Reason for every rejection.
7. **Iterate** — edit one sentence, re-sort instantly (cache keyed by Criterion, params and Episode; only changed Criteria re-run; dragging a threshold calls no model).

**The workspace** (shadcn/ui on Radix). A **Dataset** holds Episodes and all Description-independent work (clips, tracks, hand-drawn boxes), shared by its **Projects**; a Project is one Description over one Dataset (Rubric versions, anchor pool, Test set held out, labels, runs). A sidebar holds the Dataset switcher and its Projects; each stage is its own page: **Prepare** (Dataset-level: ingest status and a frame-0 grid of unboxed Episodes, drawn in a dialog with Save & next), **Describe** (the interview as anchored question cards beside the live Rubric; anchor-pool numbers only), **Episodes** (filterable table → full-page Workstation), **Review** (Needs review queue, least confident first, answering only unsure Phrases), **Audit**, and **Evaluation** (the only place the Spark-alone contrast appears). Decided in [Workspace shape: datasets, projects, Episode browser, and Criterion chat](https://github.com/kleongf/winnow/issues/20).

---

## 6. Meta models — used in non-obvious ways

| Model | Role | What makes it more than a basic integration |
|---|---|---|
| **SAM 3.1** (Model API, `sam-3.1`) | Tracks the gripper and objects from a seed box (text prompts fail on the gripper and small objects at 320×180); each call takes one concept and one camera and returns per-frame boxes, masks, track ids, and confidence | The *measurement backbone*: with robot data, it decides physical facts (lifted, dropped, moved, inside target) across camera views, and steers Spark to the right moment and crop |
| **Muse Spark 1.3** | Runs the Describe interview; composes typed Criteria; picks what SAM tracks; judges only what geometry can't; writes Reasons; proposes missing Criteria | Never the holistic judge (that's the baseline). Checks run in Standard Motion's own code (the API has no hosted code execution), which Spark calls as function tools |
| **Muse Voice Transcribe** | Push-to-talk labeling on the Review page: narrate while watching an Episode | Each turn is transcribed through the backend; its moment is the playhead at the turn's onset (the API has no word-level timestamps); one Spark call maps the transcript onto the Episode's unsure Phrases as pass or fail, shown as chips the user confirms before they save as ordinary review labels (voice is only the input mode). Answering the Describe interview by voice is slides-only |
| **Muse Glimmer** (open weights; hosted via OpenRouter, not on the Meta Model API) | One-way second opinion on keyframes for end-state visual Criteria Spark answered unanimously; disagreement only adds Needs review (images only, no video); running locally is roadmap (needs a 32 GB+ Mac) | Different model than Spark catches different mistakes; open-weights bonus |
| **Muse Wonder** | (Stretch / roadmap) agent that improves the rubric against labeled episodes, with budget and stopping rules | Applies my self-monitoring research-agent architecture |
| **Muse Image** | (Roadmap) edit a keyframe to insert an obvious failure; check whether the judge's verdict flips | An image model auditing another model's attention |

**Cost cascade:** each Criterion routes to the cheapest source that can decide it (robot data is free; visual judging on Spark's cheaper tier); uncertainty goes to Needs review, not to more model calls. Pitch metric: cost per 1,000 episodes curated. Pricing: Spark contributor $0.10 / $0.20 per 1M tokens (150 RPM, no `max` reasoning), standard $1.25 / $4.25 (3,000 RPM); SAM 3.1 $0.20 per 1,000 frames. Measured on Day 1: Spark video is ~72 input tokens per camera-second, and reasoning output is 50–80% of the per-Episode cost, so improve a visual Criterion by changing its input (crop, window), not with `max`. SAM dominates spend: ~$0.40 per Episode at full fps for 3 views × 3 concepts, ~$0.08 with the gripper taken from robot data and SAM at ~5 fps (untested).

---

## 7. Rubric alignment

| Criterion (weight) | Fit | Notes |
|---|---|---|
| **Impact (30%)** | Strong | Real data costs, sampled review, AI judges that miss real failures; fast-growing market; firsthand club story. Risk: "infra for ML people" → frame as "robots learn from examples; bad examples make bad robots." |
| **Use of Meta AI tooling (25%)** | Very strong | SAM as evidence + attention steering; Spark compiling language into filters; voice as a labeling interface; Glimmer second opinion. |
| **Technical depth (20%)** | Strong | Evidence fusion, calibrated abstention, risk–coverage curve, comparison vs Spark-alone baseline. |
| **Demo (25%)** | Strong | Type a sentence → 100 episodes sort → click a rejected "success" and see where it went wrong. |

**Bonus prizes in reach:** Best Build on Open Weight Models (Glimmer; confirm a hosted call qualifies), Best Agentic Use-Case (if rubric agent is built), Most Viral (post demo on X).
**Anti-project risk:** low — agentic video reasoning over datasets, not a simple image analyzer. Keep ping pong out of the hero demo (avoid any "sports analyzer" misread).

---

## 8. Decisions locked

- **Track:** Indie. **Theme:** Push the Frontier (robotics).
- **Hero demo:** pick-and-place on public data.
- **Bar to beat:** same episodes, same Meta model — **Spark alone vs. Standard Motion**. Win on **right decision for the right reason**: decision accuracy and false-keep rate on true failures, plus whether each Reject's Reason matches what happened (failure type and time). On Day 1, Spark alone got all 5 decisions right but told the wrong story on episode 42.
- **Ping pong:** motivation and "what's next," not the product.
- **Cost tier:** contributor tier is fine (public data); escalated judging needs the standard tier (contributor has no `max` reasoning and a 150 RPM cap).
- **Philosophy:** somewhat functional + very well presented. Not everything needs to be built.

---

## 9. Demo script (~2.5 min) — written first, build backward

| Time | On screen | Purpose |
|---|---|---|
| 0:00 | Robot clip labeled "success" that's clearly sloppy | Hook |
| 0:15 | "Teams can't watch every demo, and AI judges miss real failures." | Problem |
| 0:30 | Type the expert description → rubric appears | Core idea |
| 0:50 | 100 episodes sort into keep / reject / needs review | Scale |
| 1:10 | Click a rejected "success": video + SAM masks, timeline marking where it failed, gripper data, one-line reason | Wow moment |
| 1:35 | Needs-review pile → narrate a verdict by voice → thresholds update | Self-monitoring + Meta tooling |
| 2:00 | Change one sentence ("pauses are fine") → instant re-sort | Flexibility |
| 2:15 | Results: Standard Motion vs Spark alone; cost per 1,000 episodes | Proof |
| 2:35 | "Any robot, any task, described in English." Ping pong as what's next | Close |

---

## 10. Cut line

Decided in [Cut line and day-by-day build plan](https://github.com/kleongf/winnow/issues/12). **Must-ship** is built, exercised, and measured. **Nice-to-have** is built strictly in rank order, and only after the gate: end-to-end numbers on the Dev set. **Slides-only** is "what's next" in the Demo video, never built. A nice-to-have not reached by Mon Nov 2 night drops to slides-only, so nothing is demoed half-built. Rules require demoing only what was built during the hackathon, so label future work clearly. Precomputed runs (the full dataset, cached SAM tracks and measurements) are fine if said on screen.

**Must-ship** (the floor of rubric compiling, scoring ~100 Episodes, the Episode detail view and Spark-alone numbers, plus what those and the pitch depend on):

1. Ingest: droid_100 plus the droid_1.0.1 selection pass, a frozen Test set and Dev set, AV1→H.264, the SQLite Meta cache and the asyncio runner.
2. Prepare page (hand-drawn box) and the SAM text-prompted target box with a hand-drawn fallback.
3. SAM tracks: wrist seeded from robot data, one boxed exterior view.
4. The catalog: 5 measured primitives, 4 tracked, `ask_video`.
5. Reference label mode, and the Test set and Dev set labelled in it.
6. Triage: the Phrase rule with conclusive-fail flags, every Uncertainty signal including tracking health, min-based confidence, template Reasons.
7. Episodes table and the full-page Workstation.
8. Evaluation: the Spark-alone baseline at ingest; the `evaluation` module, `eval` CLI and Evaluation page (false keeps, right reason, risk–coverage, matched coverage, length-alone baseline, $0 source ablation, cost per 1,000 Episodes).
9. Review queue with the (Episode, Phrase, source) label store; labels override results.
10. Instant re-sort: drag a threshold or edit a sentence; only changed Criteria re-run.
11. Describe as a minimal interview: compile, coverage, and code-picked question cards for uncovered Phrases and threshold bisection on the anchor pool.

The **cost cascade** needs no separate build: routing to the cheapest source is how compile works, and the cost log gives the metric.

**Nice-to-have, in build order:**

1. Audit tab with Keep precision (count plus Wilson interval).
2. Calibration: margin-multiplier scan with the leave-one-out check, plus threshold suggestions.
3. Rubric sanity monitor.
4. Voice labeling, push-to-talk on the Review page (§6).
5. Spark's Reason swapped in over the template.
6. The rest of the interview: hard/soft and grasp-setting questions, Criteria-disagree questions, free-text recompile.
7. LeRobot-format export of kept Episodes.
8. Background dry run of visual Criteria on the anchor pool.
9. Soft-Criterion quality score (until then soft Criteria show results but never touch the Triage decision).
10. Criterion chat, and more than one Dataset and Project.
11. Glimmer second opinion on end-state Criteria.

**Slides-only:** Spark as investigator (a tool loop over cached crop/track), the rubric-improving agent (Wonder), the image-edit judge test (Muse Image), Glimmer running locally and its activation probes, voice answers to the Describe interview, training a policy on filtered data.

---

## 11. Build plan

Build days are Thu Oct 29 – Mon Nov 2; Nov 3–4 is for the Demo video and submission. The table is a guide, not a contract. Only two orderings are fixed: the user's blind Reference labels land before any tuning (and before they see Standard Motion's or Spark-alone's output on those Episodes), and the gate comes before any nice-to-have.

| Day | Build | Human |
|---|---|---|
| Thu Oct 29 | Ingest and the selection pass, Meta cache and runner, frozen sets; workspace shell, Prepare page, Reference label mode | Confirm the selection; Discord questions (§14); label the Dev set |
| Fri Oct 30 | SAM tracks at ingest (wrist, exterior, target box); measured and tracked primitives; Spark-alone baseline at ingest, hidden from the UI | Label the Test set, plus the ~15-Episode relabel for slack |
| Sat Oct 31 | Compile, `ask_video`, Triage, Uncertainty signals, confidence, template Reasons; Episodes table and Workstation; minimal interview | Interview on the anchor pool; Dev set tuning |
| Sun Nov 1 | Review queue and label store, instant re-sort, evaluation module and page; **gate**; first logged Test run | Review pass on the Dev set |
| Mon Nov 2 | Nice-to-haves in rank order; freeze at night with a final logged Test run | Teammate interviews, validation to-dos |

**Rules:**

- Each day ends with `pnpm verify` green and its work merged to `main`, one short-lived branch and PR per must-ship item.
- A slipped must-ship item moves to the front of the next day and costs Monday's nice-to-haves; must-ship is never cut.
- The one sanctioned fallback: if tracked primitives aren't working on the Dev set by Sat noon, ship measured and visual Criteria only and report SAM's absence in the source ablation.
- **Test set hygiene:** the Test set may be run more than once, but every run is appended to a dated log, no threshold, margin or Rubric change is made because of a Test result, and the reported numbers come from the last run before the freeze.

### Day-1 feasibility test (done Oct 27: conditional go, then go)
1. Get Meta API key + credits working.
2. Load `lerobot/droid_100` (small; no big download). Avoid full DROID (~1.7 TB RLDS). Transcode its AV1 video to H.264 (not on SAM's accepted list); the `v2.0` branch has one mp4 per episode per camera.
3. Pick 5 pick-and-place episodes: episode 42 (marked success, appears to fail; recovered instruction "Move the black remote control to the left"), 2 known failures (their instructions are blank — write one by watching), 2 true successes.
4. SAM 3.1 with prompts like "robot gripper" + the object from the task instruction → does tracking hold?
5. Spark: video + instruction → success? if not, when did it fail?
6. Spark: compile one expert description → rubric; check measured criteria compute from the episode data.
7. Record cost and latency per episode.

**Go/no-go:** if Spark catches episode 42 and SAM's tracks support the verdict, build. If not, adjust before committing more time.

---

## 12. Evaluation plan

Decided in [Evaluation protocol](https://github.com/kleongf/winnow/issues/10), which holds the detail.

- **Ground truth:** blind **Reference labels** against one frozen description (*"Expert pick-and-place: grasps the object on the first try, never drops it, places it in or on the target named in the instruction, no long pauses."*): each phrase pass/fail, each fail with an interval; instructions written where missing. The **Dataset outcome** is a second column; disagreements get their own table.
- **Fallback used (Nov 2):** no time to give ~130 blind Reference labels, so `GROUND_TRUTH=dataset_outcome` scores every set Episode against its **Dataset outcome** instead and opens the blind gate. It answers "was the task done", not "does it meet the Description", so a flagged success that regrasps counts as a false reject; right reason and failures per Phrase need labels and are not measured. Instructions DROID dropped are written from Spark's object and target names (`standard-motion instructions fill`). Say all of this on screen.
- **Sets:** a frozen **Test set** of 100 Episodes with ≥ 30 description failures (droid_100's unseen pick-and-place-like Episodes, topped up from `lerobot/droid_1.0.1`), labelled before any tuning; a **Dev set** of ~30 (including every Episode already seen) for the interview, calibration, and tuning. droid_1.0.1 Episodes are chosen by task type only (Spark pre-filter on contact sheets + human confirm, fixed seed).
- **Baselines:** Spark alone (same tier, all 3 views, description + instruction, structured output, 3 samples for a confidence score); a FailBench "did it succeed?" check against the Dataset outcome; **episode length alone** with a hindsight threshold (5 of 7 curation metrics exploit length; in droid_100 failures are *shorter*).
- **Right reason:** a Reject's Reason is right when its failure type matches a failing phrase and its time falls in that phrase's labelled interval plus a slack measured from the labeller's own relabelling of ~15 Dev set Episodes; also shown as a curve over slack.
- **Metrics:** false keeps on true failures (Wilson CI) with the worst case of every Needs review kept; false rejects separately; right reason k/n; Keep precision at matched coverage; risk–coverage curves; McNemar discordant counts (counts only); balanced accuracy; failures per phrase; a $0 source ablation (robot data / + SAM / + Spark visual / all); SAM tracking health; review minutes saved (label-mode timer); cost per 1,000 Episodes extrapolated from the Test set cost log.
- **Tooling:** a Reference label mode in the app (outputs hidden, timer, exterior hand-drawn box) and an `evaluation` module behind a route and an `eval` CLI subcommand.
- **Dropped for now:** RoboFAC (no robot data, near-saturated) and synthetic trimmed failures.
- **Not in scope:** training a policy on filtered data (needs GPUs) → "next steps."

---

## 13. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Vague descriptions → vague filter | Compile → confirm → calibrate loop; rubric shown before running |
| AI judges weak on contact-heavy tasks | Hero demo on pick-and-place (object motion visible); route ambiguity to review |
| Video token cost | Measure on day 1; compute measured criteria from robot data; send video only for visual criteria; crop to SAM boxes in our own code (savings unproven until measured) |
| SAM loses small/fast objects; text prompts fail | All LeRobot DROID video is 320×180. Seed SAM with boxes (candidates under evaluation: project the gripper from robot data + droid_1.0.1 camera extrinsics, a small gripper detector, one hand-drawn box per Episode as the fallback); track the views each Criterion needs (wrist for in-hand); poor tracking health in every view → Needs review |
| "Infra for ML people" perception | Lead with the simple pitch and a concrete clip; firsthand club story |
| Competition (Shotwell, Roboto, Instance, RoboFAC, data platforms) | "Plain-English criteria" alone is no longer unique. Lead with fusing robot data, tracks and video, calibrated Needs review, and reported false-keep rates |
| Quality filtering hurts diversity (CUPID; Bedi) | Hard or soft follows the user's wording, not a default; the sanity monitor shows *what* a Criterion removes; claim review time saved, not better policies |
| Rules: new work only | Fresh public repo; no club code; club data only with permission |

---

## 14. Validation to-dos (this week)

- [ ] Interview 2–3 Triton Droids teammates: how many episodes, how long review takes, what makes a demo "expert." Get one quotable line.
- [ ] Ask in the LeRobot community: "How do you curate teleoperation data before training?"
- [ ] Ask one UCSD robotics lab the same question.
- [x] Confirm Spark contributor-tier pricing (done: see §6). Video limits are undocumented — measure on day 1.
- [ ] Ask on hackathon Discord whether a hosted Glimmer call counts for Best Open Weight Build.
- [ ] Ask on hackathon Discord if anything about the idea raises concerns.

---

## 15. Hackathon logistics

- **Submission deadline:** Nov 4, 9:00 PM ET (6:00 PM PT). Judging Nov 4–8; finals Nov 9.
- **Rules:** public repo; teams ≤4 (solo OK); demo only what was built during the event; avoid anti-projects (chat wrappers, basic RAG, simple image analyzers, sports analyzers/coaches, medical advice, education chatbots, political).
- **Judging:** Stage 1 pass/fail viability → Stage 2 rubric scores (0–10) → top 5 per track: judges watch demo videos live.
- **Rubric:** Impact 30% · Use of Meta AI Tooling 25% · Technical Depth & Execution 20% · Demo 25%.
- **Credits:** $150 Meta Model API credits.
- **Bonus:** Most Viral (X post by Nov 8), Best Open Weight Build, Community Vote, Best Agentic Use-Case, Best Creative Build.

---

## 16. Sources

- Meta hackathon: https://dev.meta.ai/events/global-hackathon
- Muse Spark: https://dev.meta.ai/models/muse-spark/ · Muse Glimmer: https://dev.meta.ai/models/muse-glimmer/ · Muse Wonder: https://dev.meta.ai/models/muse-wonder/
- SAM 3.1 on Meta Model API: https://www.mind-verse.de/news/meta-sam-3-1-bild-video-analyse-api · https://digg.com/ai/icmesfai
- FailBench: https://arxiv.org/pdf/2609.03611 · summary: https://academy.dair.ai/papers/failbench-how-reliable-are-vlms-at-judging-robot-task-success-2609.03611
- Teleop data cost: https://roboticscenter.ai/state-of-robotics-2026
- Rejection rate: https://axisrobotics.ai/resources/guides/reduce-robot-data-collection-cost
- Review sampling: https://www.roboticscenter.ai/blog/teleoperation-data-quality-checklist · https://claru.ai/guides/how-to-collect-teleoperation-data
- Top-25% filtering (Mandlekar): https://claru.ai/blog/physical-ai-training-data-guide
- Low-quality data effect: https://huggingface.co/blog/robotdata/gigo
- Demo-SCORE: https://arxiv.org/html/2503.03707v1 · limitations: https://arxiv.org/pdf/2503.03707
- CUPID: https://arxiv.org/pdf/2506.19121
- Curation still manual (QoQ): https://arxiv.org/pdf/2603.09056
- droid_100 label audit: https://huggingface.co/datasets/lerobot/droid_100/discussions/2
- DROID size / LeRobot porting: https://huggingface.co/docs/lerobot/porting_datasets_v3
- RoboFAC: https://arxiv.org/pdf/2505.12224 · dataset (official, MIT): https://huggingface.co/datasets/MINT-SJTU/RoboFAC-dataset
- DROID 1.0.1 (LeRobot, explicit success flag; credit DROID, CC BY 4.0): https://huggingface.co/datasets/lerobot/droid_1.0.1
- Instance (YC S26): https://www.ycombinator.com/launches/RPi-instance-automated-evaluation-for-robot-policies-starting-with-the-success-detector
- DQAF: https://huggingface.co/papers/2605.26349
- Figure TeleOps QA role: https://ev.careers/jobs/533784258/apply
- 1X gig operators: https://claru.ai/blog/gig-workers-training-humanoid-robots-data-quality
- Encord growth: https://pulse2.com/encord-60-million-series-c-raised-to-scale-ai-native-data-infrastructure/amp/
- Market estimates: https://giikorea.co.kr/report/rinc2027361-embodied-artificial-intelligence-eai-robot-data.html · https://animeanime.jp/release/dreamnews/20260821/307283.html