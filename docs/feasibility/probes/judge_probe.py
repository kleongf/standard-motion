import json, sys
from standard_motion.core.settings import get_settings
from standard_motion.episodes.droid100 import CAMERAS, h264_clip, load_signals
from standard_motion.meta.client import MetaClient
from standard_motion.meta.pricing import SPARK_CONTRIBUTOR, SPARK_STANDARD
s = get_settings(); d = s.data_dir / "droid_100"; m = MetaClient(s)
INSTRUCTIONS = {
    42: "Move the black remote control to the left",
    3: "Place the pack of doritos inside the sink",
    16: "Pick up the blue block and put it in the white mug on the right",
    48: "Pour the black beans from the grey cup into the red bowl",
    49: "Put the small jar on top of the can",
}
SCHEMA = {"type": "object", "additionalProperties": False, "required": ["success", "failure_time_s", "reason"],
          "properties": {"success": {"type": "boolean"}, "failure_time_s": {"type": ["number", "null"]}, "reason": {"type": "string"}}}
PROMPT = ("These are synchronized recordings of one robot attempt from {n} cameras ({cams}). "
          "Task: {task}. Did the robot complete the task successfully? "
          "If it did not, give the time in seconds when it failed.")
out_path = s.data_dir / "feasibility" / "spark_judge.json"
results = json.loads(out_path.read_text()) if out_path.exists() else {}
for arg in sys.argv[1:]:
    ep_s, model, effort = arg.split(":"); ep = int(ep_s)
    key = f"{ep}:{model}:{effort}"
    if key in results: print("cached", key); continue
    files = [{"type": "input_video", "file_id": m.upload(h264_clip(ep, c, d))} for c in CAMERAS]
    text = PROMPT.format(n=3, cams="exterior 1, exterior 2, wrist", task=INSTRUCTIONS[ep])
    call = m.spark(model, [{"type": "input_text", "text": text}, *files], f"feasibility:B:ep{ep}", SCHEMA, effort=effort, max_output_tokens=8000)
    answer = json.loads(call.text)
    results[key] = {"answer": answer, "input_tokens": call.input_tokens, "output_tokens": call.output_tokens, "usd": call.usd, "latency_s": call.latency_s,
                    "duration_s": load_signals(ep, d).duration_s, "label_success": load_signals(ep, d).success_label}
    out_path.write_text(json.dumps(results, indent=2))
    print(f"ep{ep} {model} {effort}: success={answer['success']} t_fail={answer['failure_time_s']} | {call.input_tokens} in / {call.output_tokens} out ${call.usd:.4f} {call.latency_s:.0f}s")
    print("    ", answer["reason"][:300])
print("spent $", round(m.costs.spent_usd(), 4))
