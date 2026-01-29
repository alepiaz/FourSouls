from foursouls.engine.rng import RNG


def test_die_roll_deterministic():
    r1 = RNG(seed=123)
    r2 = RNG(seed=123)

    rolls1 = [r1.roll_d6() for _ in range(10)]
    rolls2 = [r2.roll_d6() for _ in range(10)]

    assert rolls1 == rolls2
    assert all(1 <= x <= 6 for x in rolls1)


def test_shuffle_deterministic():
    items1 = list(range(20))
    items2 = list(range(20))

    r1 = RNG(seed=999)
    r2 = RNG(seed=999)

    r1.shuffle(items1)
    r2.shuffle(items2)

    assert items1 == items2
    assert items1 != list(range(20))


def test_choice_deterministic():
    pool = ["a", "b", "c", "d", "e"]

    r1 = RNG(seed=42)
    r2 = RNG(seed=42)

    picks1 = [r1.choice(pool) for _ in range(10)]
    picks2 = [r2.choice(pool) for _ in range(10)]

    assert picks1 == picks2


def test_choice_empty_raises():
    r = RNG(seed=1)
    try:
        r.choice([])
        assert False, "Expected ValueError"
    except ValueError:
        pass
