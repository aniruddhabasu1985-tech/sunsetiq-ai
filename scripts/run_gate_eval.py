import sys; sys.path.insert(0, "src"); sys.path.insert(0, "eval")
from datasets import GATE_HELDOUT
from sunsetiq.gate_eval import evaluate_gate
from sunsetiq.jev_layer import MockJevClient
r = evaluate_gate(GATE_HELDOUT, MockJevClient())
print(r["summary"])
for row in r["rows"]:
    print(row)
