import base64, sys, time
from pathlib import Path
from standard_motion.core.settings import get_settings
from standard_motion.meta.client import MetaClient, _as_input
from standard_motion.meta.costs import CostEntry
m = MetaClient(get_settings())
def url(p): return "data:image/png;base64," + base64.b64encode(Path(p).read_bytes()).decode()
for arg in sys.argv[1:]:
    img, concept = arg.split("::")
    m.costs.ensure_affordable(0.0025); t = time.monotonic()
    r = m._openai.responses.create(model="sam-3.1", input=_as_input([{"type":"input_text","text":concept},{"type":"input_image","image_url":url(img)}]), metadata={"include_confidence":"true"})
    m.costs.record(CostEntry("sam-3.1","feasibility:A:image-probe",0.0025,time.monotonic()-t,{"concept":concept}))
    boxes = [seg.split("|>")[0] for seg in r.output_text.split("<|box;")[1:]]
    print(f"{Path(img).name:16s} {concept:24s} n={len(boxes)} {boxes[:2]}")
print("spent $", round(m.costs.spent_usd(), 4))
