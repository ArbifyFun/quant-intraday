from quant_intraday.engine.queue_tracker import QueueTracker
def test_queue_est():
    q=QueueTracker(); q.on_new_order('buy', 10, 100.0, 500.0)
    r=q.on_book([[100.0,500.0]], [[100.1,300.0]], 0.1)
    assert 0<=r<=1
