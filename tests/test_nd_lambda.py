from scripts.calibrate_lambda_nd import session_bucket
def test_session_bucket():
    assert session_bucket('2025-01-01T01:00:00Z') in ('ASIA','EU','US','OFF')
