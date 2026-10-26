from app.state import SensorState


def test_sequence_is_persisted_and_confirm_advances(tmp_path):
    path=str(tmp_path/"state.db"); first=SensorState(path,"sensor","spot")
    event1=first.prepare_event(); assert event1["data"]["sequence"]==1
    restarted=SensorState(path,"sensor","spot")
    assert restarted.prepare_event()==event1
    assert restarted.confirm(event1["event_id"]) is True
    event2=restarted.prepare_event(); assert event2["data"]["sequence"]==2
    assert event2["event_id"]!=event1["event_id"]


def test_physical_state_changes_only_next_unprepared_event(tmp_path):
    state=SensorState(str(tmp_path/"state.db"),"sensor","spot")
    pending=state.prepare_event(); state.set_occupied(True)
    assert state.prepare_event()==pending and pending["data"]["physical_occupied"] is False
    state.confirm(pending["event_id"])
    assert state.prepare_event()["data"]["physical_occupied"] is True


def test_wrong_confirmation_does_not_clear_pending(tmp_path):
    state=SensorState(str(tmp_path/"state.db"),"sensor","spot"); pending=state.prepare_event()
    assert state.confirm("other") is False
    assert state.inspect()["pending_event"]["event_id"]==pending["event_id"]


def test_failure_state_is_durable_and_does_not_change_physical_state(tmp_path):
    path=str(tmp_path/"state.db"); state=SensorState(path,"sensor","spot")
    state.set_occupied(True); state.set_failed(True)
    restarted=SensorState(path,"sensor","spot")
    assert restarted.is_failed() is True
    assert restarted.inspect()["physical_occupied"] is True
    restarted.set_failed(False)
    assert restarted.is_failed() is False
