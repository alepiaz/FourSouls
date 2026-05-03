from foursouls.engine.events import AllPlayersPassed, DebugEvent, PriorityPassed, StackItemPushed
from foursouls.engine.log import EventLog
from foursouls.model.refs import PlayerId


def test_event_log_keeps_order():
    log = EventLog()

    e1 = DebugEvent({"a": 1})
    e2 = PriorityPassed(PlayerId("P1"))
    e3 = AllPlayersPassed()

    log.append(e1)
    log.append(e2)
    log.append(e3)

    assert [e.name for e in log.events] == ["DebugEvent", "PriorityPassed", "AllPlayersPassed"]
    assert log.last() == e3


def test_stack_item_pushed_event_fields():
    e = StackItemPushed(stack_id=7, controller_id=PlayerId("P2"), label="loot:coin")
    assert e.name == "StackItemPushed"
    assert e.stack_id == 7
    assert e.controller_id == PlayerId("P2")
    assert e.label == "loot:coin"