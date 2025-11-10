from platform_challenge_sdk import challenge, Context, run


def test_challenge_registry():
    assert challenge is not None
    assert hasattr(challenge, "on_startup")
    assert hasattr(challenge, "on_ready")
    assert hasattr(challenge, "on_job")
    assert hasattr(challenge, "on_cleanup")
    assert hasattr(challenge, "on_weights")
    assert hasattr(challenge, "api")


def test_context():
    ctx = Context(
        validator_base_url="http://test",
        session_token="token",
        job_id="job1",
        challenge_id="ch1",
        validator_hotkey="hotkey",
        client=None,
        cvm=None,
        values=None,
        results=None,
    )
    assert ctx.validator_base_url == "http://test"
    assert ctx.session_token == "token"
    assert ctx.job_id == "job1"
    assert ctx.challenge_id == "ch1"
    assert ctx.validator_hotkey == "hotkey"
