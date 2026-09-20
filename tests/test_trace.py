from oma_info_system.platform.trace import TraceManager


def test_trace_manager_appends_and_reads_session_events(tmp_path):
    manager = TraceManager(tmp_path / "traces")

    manager.emit("session-1", "task_received", mode="yolo")
    manager.emit("session-1", "workflow_finished", status="completed")

    events = manager.read("session-1")
    assert [event["event"] for event in events] == ["task_received", "workflow_finished"]
    assert events[0]["session_id"] == "session-1"
    assert events[1]["status"] == "completed"
