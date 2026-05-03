from foursouls.engine.stack import Stack
from foursouls.model.refs import PlayerId


def test_stack_lifo():
    st = Stack()
    p1 = PlayerId("P1")

    a = st.push(controller_id=p1, source="S1", effect="E1", label="first")
    b = st.push(controller_id=p1, source="S2", effect="E2", label="second")

    assert len(st) == 2
    assert st.top() == b

    popped1 = st.pop()
    assert popped1 == b
    assert st.top() == a

    popped2 = st.pop()
    assert popped2 == a
    assert st.empty()


def test_stack_ids_increase():
    st = Stack()
    p1 = PlayerId("P1")

    a = st.push(controller_id=p1, source=None, effect=None)
    b = st.push(controller_id=p1, source=None, effect=None)

    assert a.stack_id == 1
    assert b.stack_id == 2


def test_pop_empty_raises():
    st = Stack()
    try:
        st.pop()
        assert False, "Expected IndexError"
    except IndexError:
        pass