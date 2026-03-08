
def test_agent_replay_matches_golden_trace():
    golden = read_trace("../replay/traces/cpu_spike_A/audit.jsonl")

    new_events = asyncio.run(
        run_agent_and_capture({"text": "server down"})
    )

    assert new_events == golden