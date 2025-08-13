import os, json
from scripts.rebalance import main
def test_rebalance_neutral(tmp_path):
    live=tmp_path/'live_output'; attrib=tmp_path/'attrib'
    live.mkdir(); attrib.mkdir()
    main(str(live), str(attrib))
    assert (live/'alloc.json').exists()
