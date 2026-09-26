"""Check live revised phase evidence against its actual representative frames."""
import json
import math
from pathlib import Path
from urllib.parse import quote
from urllib.request import urlopen

root = 'http://127.0.0.1:8000/matches/2017461'
def get(path):
    return json.load(urlopen(root + path, timeout=600))

ranked = get('/findings')['ranked_findings']
checked = []
for finding in ranked:
    if finding['finding_type'] != 'phase_shape_variability':
        continue
    path = '/findings/' + quote(finding['finding_id'], safe='')
    detail = get(path)
    metrics = detail['evidence']['exact_metrics']
    moments = detail['evidence']['representative_moments']
    assert len(moments) == 3
    assert len({(m['period'], m['phase_frame_start'], m['phase_frame_end']) for m in moments}) == 3
    for i, moment in enumerate(moments):
        frame = get(path + f'/moments/{i}/frame')
        players = [p for p in frame['players'] if p['team_id'] == finding['team_id'] and p['position'] != 'Goalkeeper']
        axis = 'y' if metrics['dimension'] == 'width' else 'x'
        actual = max(p[axis] for p in players) - min(p[axis] for p in players)
        assert math.isclose(actual, moment['metric_value_metres'], abs_tol=1e-8)
        assert moment['phase_frame_start'] <= frame['frame'] < moment['phase_frame_end']
        assert all(p.get('player_number') is not None for p in frame['players'])
    checked.append({'rank': finding['rank'], 'title': finding['title'], 'sample_size': finding['sample_size'],
                    'metrics': metrics, 'moments': moments})
assert checked, 'No revised phase findings returned'
out = Path('artifacts/ui_review/phase_evidence_verified.json')
out.write_text(json.dumps(checked, indent=2), encoding='utf-8')
print(f'Validated {len(checked)} phase findings and {len(checked)*3} source pitch frames', flush=True)
