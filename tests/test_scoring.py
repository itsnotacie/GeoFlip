import pytest
from geoflip.core import score, overall_ranking, inside


def row(sid, task, label, pair=None):
    return {'id': sid, 'task': task, 'reference_label': label, 'pair_id': pair}


def test_task_macro_class_balance_and_missing_denominator():
    truth = [row('a', 'x', 'still', 'p'), row('b', 'x', 'fall', 'p'),
             row('c', 'x', 'still'), row('d', 'y', 'left')]
    pred = [{'id': 'a', 'label': 'still', 'violation': 'clear'},
            {'id': 'b', 'label': 'other', 'violation': 'flagged'},
            {'id': 'd', 'label': 'left', 'violation': 'uncertain'}]
    result = score(truth, pred)
    assert result['event_percent'] == pytest.approx(62.5)
    assert result['structure_percent'] == pytest.approx(100 / 6)
    assert result['missing'] == 1
    assert result['complete_pairs'] == 1
    assert result['pair_complete_accuracy'] == 0


def test_error_and_uncertainty_cannot_improve_score():
    truth = [row('a', 'x', 'still'), row('b', 'x', 'fall')]
    result = score(truth, [{'id': 'a', 'label': 'still', 'violation': 'clear', 'error_type': 'DecodeError'},
                           {'id': 'b', 'label': 'uncertain', 'violation': 'uncertain'}])
    assert result['event_percent'] == result['structure_percent'] == 0
    assert result['failed'] == 1
    assert result['prediction_coverage'] == .5


def test_reject_duplicate_and_wrong_scope():
    truth = [row('a', 'x', 'still')]
    with pytest.raises(ValueError, match='duplicate'):
        score(truth, [{'id': 'a'}, {'id': 'a'}])
    with pytest.raises(ValueError, match='outside'):
        score(truth, [{'id': 'b'}])
    with pytest.raises(ValueError, match='Empty'):
        score([], [])


def test_rank_similarity_is_one_of_three_equal_dimensions():
    rows = [{'model': 'a', 'event': 10, 'structure': 20, 'psnr': 30, 'ssim': .8},
            {'model': 'b', 'event': 20, 'structure': 10, 'psnr': 10, 'ssim': .9},
            {'model': 'c', 'event': 10, 'structure': 20, 'psnr': 30, 'ssim': .8}]
    result = overall_ranking(rows)
    a = next(r for r in result if r['model'] == 'a')
    c = next(r for r in result if r['model'] == 'c')
    assert a['mean_rank'] == pytest.approx((2.5 + 1.5 + (1.5 + 2.5) / 2) / 3)
    assert a['rank'] == c['rank']


def test_dataset_cannot_escape_root(tmp_path):
    with pytest.raises(ValueError, match='leaves'):
        inside(tmp_path, '../private-file')
    with pytest.raises(ValueError, match='relative'):
        inside(tmp_path, str(tmp_path / 'absolute-file'))
