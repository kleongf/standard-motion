import base64, json, sys
from pathlib import Path
from standard_motion.core.settings import get_settings
from standard_motion.meta.client import MetaClient
from standard_motion.meta.pricing import SPARK_CONTRIBUTOR
m = MetaClient(get_settings())
SCHEMA = {"type": "object", "additionalProperties": False, "required": ["objects"], "properties": {"objects": {"type": "array", "items": {"type": "object", "additionalProperties": False, "required": ["label", "visible", "x_min", "y_min", "x_max", "y_max"], "properties": {"label": {"type": "string"}, "visible": {"type": "boolean"}, "x_min": {"type": "integer"}, "y_min": {"type": "integer"}, "x_max": {"type": "integer"}, "y_max": {"type": "integer"}}}}}}
def url(p): return "data:image/png;base64," + base64.b64encode(Path(p).read_bytes()).decode()
for arg in sys.argv[1:]:
    img, labels = arg.split("::")
    prompt = (f"Locate each of these in the image: {labels}. For each, give a tight bounding box on a 0-1000 normalized grid "
              "(x from left edge, y from top edge). Set visible=false if it is not visible.")
    r = m.spark(SPARK_CONTRIBUTOR, [{"type": "input_text", "text": prompt}, {"type": "input_image", "image_url": url(img)}], "feasibility:A:locate", SCHEMA, effort="medium", max_output_tokens=3000)
    out = json.loads(r.text)
    for o in out["objects"]:
        px = [round(o[k] * (320 if k[0] == "x" else 180) / 1000) for k in ("x_min", "y_min", "x_max", "y_max")]
        print(f"{Path(img).name} {o['label']:22s} visible={o['visible']} px320x180={px}")
    print(f"  {r.input_tokens} in / {r.output_tokens} out, ${r.usd:.5f}, {r.latency_s:.1f}s")
print("spent $", round(m.costs.spent_usd(), 4))
