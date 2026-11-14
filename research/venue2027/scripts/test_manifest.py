#!/usr/bin/env python3
import json,pathlib,subprocess,sys
r=pathlib.Path(__file__).resolve().parents[1]
t=json.loads((r/'MANIFESTS/tasks.json').read_text())
assert len({x['id'] for x in t})==len(t)
assert set(x['venue'] for x in t)=={'shared','dsn','popets','ifip_sec','acns','compsac','aime','sacmat','dimva','pst'}
for x in t:
 assert x['phase'].startswith('P') and x['files'] and x['depends'] is not None
 assert 'strong_baselines' in x and 'falsification' in x
 assert all(dep in {z['id'] for z in t} for dep in x['depends'])
 v=x['venue'];p=r/('SHARED/TASKS' if v=='shared' else f'VENUES/{v}/TASKS')/(x['id']+'.md')
 assert p.exists(),p
 assert 'Definition of done' in p.read_text(),p
res=subprocess.run([sys.executable,str(r/'scripts/taskctl.py'),'validate'],capture_output=True,text=True)
assert res.returncode==0,res.stdout+res.stderr
print('PASS: task manifest, schema, DAG and task documentation')
