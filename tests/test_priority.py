from foursouls.engine.priority import PriorityManager
from foursouls.model.refs import PlayerId


def test_priority_cycles_all_passed_two_players():
    pm = PriorityManager([PlayerId("P1"), PlayerId("P2")])

    assert pm.current() == PlayerId("P1")
    assert not pm.all_passed()

    pm.pass_priority()  # P1 passes -> now P2 has priority
    assert pm.current() == PlayerId("P2")
    assert not pm.all_passed()

    pm.pass_priority()  # P2 passes -> back to P1
    assert pm.current() == PlayerId("P1")
    assert pm.all_passed()


def test_priority_cycles_all_passed_three_players():
    pm = PriorityManager([PlayerId("A"), PlayerId("B"), PlayerId("C")])

    pm.pass_priority()  # A
    assert pm.current() == PlayerId("B")
    assert not pm.all_passed()

    pm.pass_priority()  # B
    assert pm.current() == PlayerId("C")
    assert not pm.all_passed()

    pm.pass_priority()  # C
    assert pm.current() == PlayerId("A")
    assert pm.all_passed()


def test_priority_reset_clears_passed_and_sets_current():
    pm = PriorityManager([PlayerId("P1"), PlayerId("P2"), PlayerId("P3")])

    pm.pass_priority()  # P1 passed
    pm.pass_priority()  # P2 passed
    assert pm.passed == {PlayerId("P1"), PlayerId("P2")}
    assert pm.current() == PlayerId("P3")

    pm.reset_to(PlayerId("P2"))
    assert pm.current() == PlayerId("P2")
    assert pm.passed == set()
    assert not pm.all_passed()


def test_priority_rejects_duplicates():
    try:
        PriorityManager([PlayerId("P1"), PlayerId("P1")])
        assert False, "Expected ValueError for duplicate player ids"
    except ValueError:
        pass


def test_priority_rejects_empty():
    try:
        PriorityManager([])
        assert False, "Expected ValueError for empty order"
    except ValueError:
        pass


def test_reset_to_invalid_player_raises():
    pm = PriorityManager([PlayerId("P1"), PlayerId("P2")])
    try:
        pm.reset_to(PlayerId("P3"))
        assert False, "Expected ValueError for invalid player"
    except ValueError:
        pass
