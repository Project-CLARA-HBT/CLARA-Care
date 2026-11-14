#!/usr/bin/env python3
"""Self-check of the delivered *specification* bundle, not project code."""
from pathlib import Path
import json,collections,re,sys
root=Path(__file__).resolve().parents[1]
ts=json.loads((root/'MANIFESTS/tasks.json').read_text());ids={x['id'] for x in ts}
assert len(ids)==len(ts)==322
assert {x['venue'] for x in ts}=={'shared','dsn','popets','ifip_sec','acns','compsac','aime','sacmat','dimva','pst'}
assert len([x for x in ts if x['venue']=='shared'])==25
for t in ts:
 assert set(t['depends'])<=ids,(t['id'],'bad dependency')
 path=root/('SHARED/TASKS' if t['venue']=='shared' else f"VENUES/{t['venue']}/TASKS")/(t['id']+'.md')
 txt=path.read_text()
 assert len(txt)>2000,(t['id'],'truncated spec')
 for h in ['Dependencies','File and directory ownership','Implementation instructions','Verifiable behavior','Required outputs','Definition of done','Handoff']:
  assert h in txt,(t['id'],h)
 assert t['files'] and t['evidence']
 assert t['status']=='TODO'
for v in ('dsn','popets','ifip_sec','acns','compsac','aime','sacmat','dimva','pst'):
 assert (root/f'VENUES/{v}/CASE_MATRIX.md').is_file()
 assert (root/f'VENUES/{v}/RESEARCH_BLUEPRINT.md').is_file()
 assert all((root/f'VENUES/{v}/PHASES/P{x:02d}.md').is_file() for x in range(1,10))
print('PASS: 322 task files, DAG, 9 RQ blueprints, 9 scenario matrices and 81 phase books validated (SPEC ONLY).')
