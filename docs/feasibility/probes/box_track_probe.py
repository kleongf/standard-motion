import json, sys
from collections import Counter
from meta_sam_parser import FramePrompt, PromptBox, PromptObject, build_object_prompt
from standard_motion.core.settings import get_settings
from standard_motion.episodes.droid100 import h264_clip, load_signals
from standard_motion.meta.client import MetaClient
from standard_motion.tracking.sam_output import parse_boxes
s = get_settings(); d = s.data_dir / "droid_100"; m = MetaClient(s)
for arg in sys.argv[1:]:
    ep, l, t, r, b, tag = (int(x) if i < 5 else x for i, x in enumerate(arg.split(",")))
    n = len(load_signals(ep, d).timestamps)
    fid = m.upload(h264_clip(ep, "exterior_image_1_left", d))
    prompt = build_object_prompt(size=(320, 180), objects=[PromptObject(id=1, prompts=[FramePrompt(frame=0, box=PromptBox(left=l, top=t, right=r, bottom=b))])])
    call = m.sam_track(fid, prompt, n, f"feasibility:A:ep{ep}:{tag}-box")
    out = s.data_dir / "feasibility" / "sam" / f"ep{ep}_ext1_{tag}_box.txt"; out.parent.mkdir(parents=True, exist_ok=True); out.write_text(call.text)
    boxes = parse_boxes(call.text)
    frames = sorted({bx.frame for bx in boxes}); ids = Counter(bx.object_id for bx in boxes)
    confs = [bx.confidence for bx in boxes if bx.confidence is not None]
    print(f"ep{ep}: frames {n}, tracked in {len(frames)} ({len(frames)/n:.0%}), ids {dict(ids)}, mean conf {sum(confs)/max(len(confs),1):.2f}, min conf {min(confs, default=0):.2f}, ${call.usd:.4f}, {call.latency_s:.1f}s")
    gaps = [f for f in range(n) if f not in set(frames)]
    print("   first missing frames:", gaps[:12], "..." if len(gaps) > 12 else "")
print("spent $", round(m.costs.spent_usd(), 4))
