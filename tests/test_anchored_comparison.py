import pytest

from trendscale import anchoring as anchored


def test_batches_repeat_the_anchor_and_hold_four_other_terms():
    terms = ['anchor', 'a', 'b', 'c', 'd', 'e', 'f']
    assert anchored.split_batches(terms, 'anchor') == [['anchor', 'a', 'b', 'c', 'd'], ['anchor', 'e', 'f']]


def test_an_anchor_outside_the_terms_still_leads_each_batch():
    assert anchored.split_batches(['a', 'b'], 'anchor') == [['anchor', 'a', 'b']]


def test_a_lone_anchor_makes_one_batch():
    assert anchored.split_batches(['anchor'], 'anchor') == [['anchor']]


def test_second_batch_is_brought_onto_the_first_batchs_scale():
    # In batch two the anchor reads half as high as in batch one, so batch two's terms are twice as strong as they look.
    batches = [
        {'anchor': [50, 100], 'a': [25, 50]},
        {'anchor': [25, 50], 'b': [50, 100]},
    ]
    result = anchored.rescale(batches, 'anchor')
    # b peaks at 100 beside an anchor of 50: 200 on batch one's scale. That is the highest point, so it becomes 100.
    assert result.terms['b'].values == [50.0, 100.0]
    assert result.terms['anchor'].values == [25.0, 50.0]
    assert result.terms['a'].values == [12.5, 25.0]


def test_the_whole_result_peaks_at_one_hundred():
    batches = [{'anchor': [40, 80], 'a': [20, 10]}, {'anchor': [20, 40], 'b': [100, 50]}]
    result = anchored.rescale(batches, 'anchor')
    assert max(max(term.values) for term in result.terms.values()) == 100.0


def test_a_single_batch_keeps_its_values():
    result = anchored.rescale([{'anchor': [100, 100], 'a': [50, 25]}], 'anchor')
    assert result.terms['a'].values == [50.0, 25.0]


def test_an_anchor_with_no_interest_cannot_scale_other_terms():
    with pytest.raises(anchored.AnchorUnreadableError, match='no search interest'):
        anchored.rescale([{'anchor': [0, 0], 'a': [5, 5]}], 'anchor')


def test_an_anchor_with_no_interest_in_a_later_batch_names_that_batchs_terms():
    batches = [{'anchor': [10, 90], 'a': [1, 1]}, {'anchor': [0, 0], 'b': [100, 100]}]
    with pytest.raises(anchored.AnchorUnreadableError, match="'b'"):
        anchored.rescale(batches, 'anchor')


def test_a_faint_anchor_marks_the_result_as_imprecise():
    batches = [{'anchor': [50, 50], 'a': [1, 1]}, {'anchor': [1, 2], 'b': [100, 100]}]
    assert anchored.rescale(batches, 'anchor').imprecise_batches == [1]
