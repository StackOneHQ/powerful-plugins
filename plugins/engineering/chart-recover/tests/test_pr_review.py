import json
import math
import os
import subprocess
import sys
from pathlib import Path

import pytest

from chart_recover.evidence import claims_from_text
from chart_recover.semantic import parse_document
from chart_recover.synthetic import KINDS, generate_one


@pytest.mark.parametrize('text', ['$' + '9' * 400 + ' revenue', '9' * 400 + 'x growth'])
def test_nonfinite_evidence_leads_are_discarded(text):
    leads = claims_from_text(text, 'https://example.com/report')
    assert leads == []
    json.dumps(leads, allow_nan=False)


def test_rejected_oversized_claim_keeps_a_json_safe_audit_record():
    claims = parse_document({'text': 'Example earned $' + '9' * 400 + ' revenue in January 2026.',
                             'url': 'https://example.com/report'}, entity='Example')
    assert len(claims) == 1
    assert 'nonfinite_amount' in claims[0]['issues']
    assert claims[0]['value'] is None
    json.dumps(claims, allow_nan=False)


@pytest.mark.parametrize('argument,value', [('kind', 'pie'), ('scale', 'unknown'),
                                           ('renderer', 'unknown'), ('variant', 'unknown')])
def test_generator_rejects_invalid_modes_before_creating_outputs(tmp_path, argument, value):
    folder = tmp_path / 'invalid'
    with pytest.raises(ValueError):
        generate_one(folder, 31001, **{argument: value})
    assert not folder.exists()


@pytest.mark.parametrize('kind', KINDS)
def test_logarithmic_generators_preserve_series_and_finite_truth(tmp_path, kind):
    truth = generate_one(tmp_path / kind, 31001, kind=kind, scale='log')
    expected = 3 if kind in ('grouped_bar', 'stacked_bar', 'stacked_area') else 1
    assert len(truth['series']) == expected
    assert math.isfinite(truth['baseline_pixel'])
    for series in truth['series']:
        assert len(series['points']) >= 8
        assert all(p['value'] > 0 and all(math.isfinite(p[key]) for key in ('x', 'y', 'value'))
                   for p in series['points'])
    json.dumps(truth, allow_nan=False)


def test_standalone_hypothesis_benchmark_uses_its_temporary_cache(tmp_path):
    import chart_recover
    environment = dict(os.environ)
    environment.pop('MPLCONFIGDIR', None)
    environment['XDG_CONFIG_HOME'] = str(tmp_path / 'user-config')
    environment['XDG_CACHE_HOME'] = str(tmp_path / 'user-cache')
    environment['PYTHONPATH'] = str(Path(chart_recover.__file__).resolve().parent.parent)
    program = ('import os; from pathlib import Path; import chart_recover.hypothesis_benchmark; import matplotlib; '
               'assert Path(matplotlib.get_configdir()).resolve() == Path(os.environ["MPLCONFIGDIR"]).resolve(); '
               'assert "chart-recover-render-" in matplotlib.get_configdir()')
    subprocess.run([sys.executable, '-c', program], cwd=tmp_path, env=environment,
                   check=True, capture_output=True, text=True, timeout=30)
