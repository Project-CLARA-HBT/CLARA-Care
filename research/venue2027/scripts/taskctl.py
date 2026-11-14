#!/usr/bin/env python3
"""CLARA-Care venue2027 task scheduler; operates on local spec bundle only."""
from __future__ import annotations
import argparse, json, pathlib, sys, re, datetime
ROOT=pathlib.Path(__file__).resolve().parents[1]
TASKS=json.loads((ROOT/'MANIFESTS/tasks.json').read_text())
MAP={t['id']:t for t in TASKS}
STATE=ROOT/'STATE/completion.json'

def state():
 if STATE.exists():
  return json.loads(STATE.read_text())
 return {'schema_version':1,'completed':{},'blocked':{}}

def validate():
 ids=set(MAP); issues=[]
 if len(ids)!=len(TASKS):issues.append('duplicate task IDs')
 for t in TASKS:
  for d in t['depends']:
   if d not in ids:issues.append(f"{t['id']} missing {d}")
 done=set();ind={t['id']:set(t['depends']) for t in TASKS}
 while True:
  r={k for k,v in ind.items() if k not in done and not v-done}
  if not r:break
  done|=r
 if len(done)!=len(MAP):issues.append('cycle '+str(sorted(ids-done)[:20]))
 for t in TASKS:
  p=ROOT/('SHARED/TASKS' if t['venue']=='shared' else f"VENUES/{t['venue']}/TASKS")/(t['id']+'.md')
  if not p.is_file():issues.append('missing task file '+str(p))
 if issues:
  print('\n'.join(issues));return 1
 print(f'VALID {len(TASKS)} tasks, {len(done)} topologically resolved, {len({t["venue"] for t in TASKS})} workstreams.')
 return 0

def relevant(venue):
 return [t for t in TASKS if venue in ('all',t['venue'])]

def ready(venue):
 s=state(); completed=set(s['completed']);blocked=set(s['blocked'])
 arr=[t for t in relevant(venue) if t['id'] not in completed and t['id'] not in blocked and set(t['depends'])<=completed]
 order={'P00':0,'P01':1,'P02':2,'P03':3,'P04':4,'P05':5,'P06':6,'P07':7,'P08':8,'P09':9}
 for t in sorted(arr,key=lambda t:(order[t['phase']], 0 if t['priority']=='P0' else 1,t['venue'],t['id'])):
  print(f"{t['id']:45s} {t['phase']} {t['resources']:14s} {t['title']}")
 print(f'{len(arr)} runnable tasks (requires report-backed completion of their dependencies)')
 return 0

def prompt(tid, model="generic"):
 if tid not in MAP:raise ValueError('unknown task id')
 t=MAP[tid]
 p=ROOT/('SHARED/TASKS' if t['venue']=='shared' else f"VENUES/{t['venue']}/TASKS")/(t['id']+'.md')
 print('SYSTEM: Follow AGENTS/EXECUTION_CONTRACT.md and AGENTS/RESOURCE_SCHEDULING.md; output report against AGENTS/TASK_REPORT_SCHEMA.json; do not pretend tests executed.\n')
 print('WORKER MODEL:',model,'\nIMPORTANT: The prompt below is a task SPECIFICATION. To implement, the orchestrator must attach the actual checked-out repository files, relevant venue blueprint/case matrix, and preceding PASS reports; no codebase is embedded here.\n')
 print(p.read_text())

def mark(tid,status,report):
 if tid not in MAP:raise ValueError('unknown task')
 if status not in ('PASS','FAIL','BLOCKED'):raise ValueError('bad status')
 s=state()
 if not report:raise ValueError('report file required; no unverified PASS')
 r=json.loads(pathlib.Path(report).read_text())
 if r.get('task_id')!=tid or r.get('status')!=status:raise ValueError('report mismatch')
 if status=='PASS':
  missing=set(MAP[tid]['depends'])-set(s['completed'])
  if missing:raise ValueError('dependencies not completed: '+str(sorted(missing)))
  if not r.get('commands') or not all(c.get('exit_code')==0 for c in r['commands']):raise ValueError('PASS requires executed zero-exit commands')
  if not r.get('source_sha_after'):raise ValueError('missing git SHA')
 s['completed'].pop(tid,None);s['blocked'].pop(tid,None)
 (s['completed'] if status=='PASS' else s['blocked'])[tid]={'report':str(pathlib.Path(report).resolve()),'status':status,'marked_at':datetime.datetime.now(datetime.timezone.utc).isoformat()}
 STATE.parent.mkdir(parents=True,exist_ok=True);STATE.write_text(json.dumps(s,indent=2)+'\n')
 print(f'{tid} {status} recorded in {STATE}')
 return 0

def main():
 p=argparse.ArgumentParser(); sub=p.add_subparsers(dest='cmd',required=True)
 sub.add_parser('validate')
 sub.add_parser('audit')
 q=sub.add_parser('ready');q.add_argument('--venue',default='all')
 q=sub.add_parser('list');q.add_argument('--venue',default='all');q.add_argument('--phase',default='all')
 q=sub.add_parser('prompt');q.add_argument('id');q.add_argument('--model',choices=['generic','deepseek','gemini'],default='generic')
 q=sub.add_parser('mark');q.add_argument('id');q.add_argument('status',choices=['PASS','FAIL','BLOCKED']);q.add_argument('--report',required=True)
 a=p.parse_args()
 if a.cmd=='validate':return validate()
 if a.cmd=='audit':
  ss=state();print('PASS reports:',len(ss['completed']),'blocked:',len(ss['blocked']),'TODO:',len(TASKS)-len(ss['completed'])-len(ss['blocked']))
  for t in TASKS:
   if t['id'] in ss['completed']:
    q=ss['completed'][t['id']]; rp=pathlib.Path(q['report']);
    if not rp.exists():print('MISSING REPORT',t['id'],rp);continue
    rr=json.loads(rp.read_text());
    if rr.get('status')!='PASS' or not rr.get('commands') or not rr.get('source_sha_after'):print('INVALID PASS REPORT',t['id'])
  return 0
 if a.cmd=='ready':return ready(a.venue)
 if a.cmd=='prompt':prompt(a.id,a.model);return 0
 if a.cmd=='list':
  for t in relevant(a.venue):
   if a.phase in ('all',t['phase']):print(f"{t['id']:45s} {t['phase']} {t['title']}")
  return 0
 if a.cmd=='mark':return mark(a.id,a.status,a.report)
 return 1
if __name__=='__main__':sys.exit(main())
