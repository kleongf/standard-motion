import json
from standard_motion.core.settings import get_settings
from standard_motion.meta.client import MetaClient
from standard_motion.meta.pricing import SPARK_CONTRIBUTOR
s = get_settings(); m = MetaClient(s)
DESCRIPTION = "Expert pick-and-place: grasps on the first try, never drops the object, places it inside the target, no long pauses."
CONTEXT = """You are compiling a plain-English description of an expert robot demonstration into a Rubric of separate, checkable Criteria.
Available evidence per Episode:
- robot data at 15 Hz: end-effector position x, y, z in metres; gripper state from 0 (open) to 1 (closed). No joint angles, no force sensing.
- tracks from a segmentation model: per-frame bounding boxes of the gripper and of the manipulated object in one exterior camera (pixels).
- the videos themselves (two exterior cameras and a wrist camera), judged by a vision-language model.
For each Criterion choose kind: "measured" (computable from robot data alone), "tracked" (needs the object/gripper tracks, possibly with robot data), or "visual" (needs judgement on video).
Hard Criteria reject the Episode on failure; soft ones only lower a quality score. Give a concrete, computable test for measured and tracked Criteria, including a numeric threshold."""
SCHEMA = {"type": "object", "additionalProperties": False, "required": ["criteria"], "properties": {"criteria": {"type": "array", "items": {
    "type": "object", "additionalProperties": False, "required": ["name", "kind", "hard", "check", "signals"],
    "properties": {"name": {"type": "string"}, "kind": {"type": "string", "enum": ["measured", "tracked", "visual"]}, "hard": {"type": "boolean"},
                   "check": {"type": "string"}, "signals": {"type": "array", "items": {"type": "string"}}}}}}}
call = m.spark(SPARK_CONTRIBUTOR, [{"type": "input_text", "text": CONTEXT + "\n\nDescription: " + DESCRIPTION}], "feasibility:C:compile", SCHEMA, effort="high", max_output_tokens=6000)
rubric = json.loads(call.text)
(s.data_dir / "feasibility" / "rubric.json").write_text(json.dumps(rubric, indent=2))
for c in rubric["criteria"]:
    print(f"- [{c['kind']}{', hard' if c['hard'] else ', soft'}] {c['name']}: {c['check']}  (signals: {', '.join(c['signals'])})")
print(f"{call.input_tokens} in / {call.output_tokens} out, ${call.usd:.4f}, {call.latency_s:.0f}s; spent ${m.costs.spent_usd():.4f}")
