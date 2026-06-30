from app.toets import distribute_questions


def test_distribute_simple_proportions():
    assert distribute_questions(10, [0.6, 0.4]) == [6, 4]


def test_distribute_sums_exactly_with_largest_remainder():
    # three equal weights over 10 cannot divide evenly; parts must still sum to 10
    out = distribute_questions(10, [1, 1, 1])
    assert sum(out) == 10
    assert out == [4, 3, 3]


def test_distribute_normalizes_arbitrary_weights():
    # weights need not sum to 1
    assert distribute_questions(20, [3, 1]) == [15, 5]


def test_distribute_zero_total():
    assert distribute_questions(0, [0.5, 0.5]) == [0, 0]


def test_distribute_all_zero_weights_gives_zeros():
    assert distribute_questions(10, [0, 0]) == [0, 0]


def test_distribute_empty_weights():
    assert distribute_questions(10, []) == []
