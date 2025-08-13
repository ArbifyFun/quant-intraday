import json, os
from scripts.autopilot import main
def test_autopilot_neutral(tmp_path):
    live=tmp_path/'live_output'; attrib=tmp_path/'attrib'
    live.mkdir(); attrib.mkdir()
    main(str(live), str(attrib))
    assert (live/'weights.json').exists() and (live/'cooling.json').exists()
