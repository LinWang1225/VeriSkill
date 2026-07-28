#!/bin/bash
# Quick script to run VeriSkill rounds 8-10
set -e

for r in 8 9 10; do
  echo "=== ROUND $r ==="
  mkdir -p rounds/r$r/new_traj rounds/r$r/replaced rounds/r$r/g_fail_items
  cp -r workspace/critics/ history/r${r}_D_before/
  cp -r workspace/actor_skills/ history/r${r}_G_before/

  python3 lib/pool.py sample --meta pool/meta.json --round $r --batch 30 --replay-k 3 --out-batch rounds/r$r/batch.list 2>&1 || { echo "POOL EXHAUSTED"; exit 0; }

  bash verify.sh rounds/r$r/batch.list rounds/r$r/verdicts.jsonl 2>&1 || true

  # Retry any failed items
  if [ -f rounds/r$r/verdicts.jsonl ]; then
    python3 -c "
import json
batch = open('rounds/r$r/batch.list').read().strip().split()
verdicts = {v['item']:v for v in [json.loads(l) for l in open('rounds/r$r/verdicts.jsonl') if l.strip()]}
missing = [i for i in batch if i not in verdicts]
if missing:
    print('Retrying: ' + ' '.join(missing))
    open('rounds/r$r/retry.list','w').write('\n'.join(missing))
" 2>&1

    if [ -f rounds/r$r/retry.list ]; then
      bash verify.sh rounds/r$r/retry.list rounds/r$r/retry_verdicts.jsonl 2>&1 || true
      python3 -c "
import json
with open('rounds/r$r/verdicts.jsonl') as f: main = {v['item']:v for v in [json.loads(l) for l in f if l.strip()]}
import os
if os.path.exists('rounds/r$r/retry_verdicts.jsonl'):
  with open('rounds/r$r/retry_verdicts.jsonl') as f:
    for v in [json.loads(l) for l in f if l.strip()]:
      main[v['item']] = v
with open('rounds/r$r/verdicts.jsonl','w') as f:
  for i in sorted(main.keys()):
    f.write(json.dumps(main[i], ensure_ascii=False) + '\n')
# Add fallback for still missing
batch = open('rounds/r$r/batch.list').read().strip().split()
for i in batch:
  if i not in main:
    main[i] = {'item':i,'verdict':'fail','rules_hit':[],'rubric_scores':{},'normalized_score':0,'confidence':0,'reason':'verify missing'}
with open('rounds/r$r/verdicts.jsonl','w') as f:
  for i in sorted(main.keys()):
    f.write(json.dumps(main[i], ensure_ascii=False) + '\n')
" 2>&1
      rm -f rounds/r$r/retry.list
    fi
  fi

  FP=$(bash oracle_run.sh --fingerprint 2>&1)
  echo "FP=$FP"

  python3 lib/pool.py audit-queue --verdicts rounds/r$r/verdicts.jsonl --audited stats/audited.json --fingerprint $FP --budget 6 --round $r > rounds/r$r/audit_queue.jsonl 2>&1
  cat rounds/r$r/audit_queue.jsonl

  # Run audits
  for item in $(python3 -c "import json; q=[l['item'] for l in [json.loads(l) for l in open('rounds/r$r/audit_queue.jsonl') if l.strip()]]; print(' '.join(q))" 2>/dev/null); do
    bash oracle_run.sh pool/traj/$item.md --new-traj-out rounds/r$r/new_traj/$item.md 2>&1 &
  done
  wait

  # Process audit results
  python3 -c "
import json, os, shutil

FP = '$FP'
queue = [json.loads(l) for l in open('rounds/r$r/audit_queue.jsonl') if l.strip()]
verdicts = {v['item']:v for v in [json.loads(l) for l in open('rounds/r$r/verdicts.jsonl') if l.strip()]}

audit = []
for q in queue:
    item = q['item']
    nt = f'rounds/r$r/new_traj/{item}.md'
    if not os.path.exists(nt): continue
    content = open(nt).read()
    # Parse oracle result from the traj file
    op = 'true' if '\"oracle_pass\": true' in content else 'false' if '\"oracle_pass\": false' in content else 'unknown'
    if op == 'unknown': continue
    oracle_pass = op == 'true'
    v = verdicts.get(item, {})
    dv = v.get('verdict', 'pass')
    ns = v.get('normalized_score', 1.0)
    rh = v.get('rules_hit', [])

    if dv == 'fail' and not oracle_pass: kind = 'TP'
    elif dv == 'fail' and oracle_pass: kind = 'FP'
    elif dv == 'pass' and not oracle_pass: kind = 'FN'
    else: kind = 'TN'

    evidence = 'checker: audit done'
    # Try to extract evidence from file
    import re
    m = re.search(r'oracle_evidence[^:]*:\s*(.*)', content)
    if m: evidence = m.group(1).strip().strip('\"')

    audit.append({'item':item,'segment':q['segment'],'d_verdict':dv,'oracle_pass':oracle_pass,'kind':kind,'skill_hash':FP,'truth_source':'checker','rules_hit':rh,'normalized_score':ns,'oracle_evidence':evidence,'skill_result':''})

    # Replace
    old = f'pool/traj/{item}.md'
    if os.path.exists(old): shutil.copy2(old, f'rounds/r$r/replaced/{item}.md')
    if kind == 'TN': shutil.copy2(old, f'stats/tn_traj/{item}.md')
    shutil.copy2(nt, f'pool/traj/{item}.md')
    shutil.copy2(nt, f'pool/traj.full/{item}.md')

json.dump(audit, open('rounds/r$r/audit.jsonl','w'), ensure_ascii=False)
json.dump([a for a in audit if a['kind'] in ('TN','FP')], open('rounds/r$r/audit_g.jsonl','w'), ensure_ascii=False)

# Update meta
meta = json.load(open('pool/meta.json'))
imap = {i['id']:i for i in meta['items']}
for a in audit:
    if a['item'] in imap: imap[a['item']]['g_version'] = 3
json.dump(meta, open('pool/meta.json','w'), indent=1)

# Stats
audited = json.load(open('stats/audited.json'))
audited.extend([f\"{a['item']}@{FP}\" for a in audit])
json.dump(audited, open('stats/audited.json','w'))

tally = json.load(open('stats/audit_tally.json'))
for a in audit: tally['recent'].append(a['kind'])
tally['recent'] = tally['recent'][-20:]
json.dump(tally, open('stats/audit_tally.json','w'))

tn_seen = [l.strip() for l in open('stats/tn_seen.list') if l.strip()]
for a in audit:
    if a['kind'] == 'TN' and a['item'] not in tn_seen: tn_seen.append(a['item'])
open('stats/tn_seen.list','w').write('\n'.join(tn_seen)+'\n')

# fn_pending
pending = [json.loads(l) for l in open('stats/fn_pending.jsonl') if l.strip()]
existing_ids = {p['item'] for p in pending}
for a in audit:
    if a['kind'] == 'FN':
        if a['item'] in existing_ids: pending = [p for p in pending if p['item'] != a['item']]
        pending.append({'item':a['item'],'round':$r,'rules_hit':[],'oracle_evidence':a['oracle_evidence']})
open('stats/fn_pending.jsonl','w').write('\n'.join(json.dumps(p,ensure_ascii=False) for p in pending)+'\n')

# g_fail_items
os.makedirs(f'rounds/r$r/g_fail_items', exist_ok=True)
for a in audit:
    if a['kind'] == 'TP':
        replaced = f'rounds/r$r/replaced/{a[\"item\"]}.md'
        if os.path.exists(replaced):
            shutil.copy2(replaced, f'rounds/r$r/g_fail_items/{a[\"item\"]}.md')
            open(f'rounds/r$r/g_fail_items/{a[\"item\"]}.meta','w').write('audited: true\n')

# Ledger
l = json.load(open('ledger.json'))
l['oracle_attempts'] += len(audit)
l['round'] = $r
json.dump(l, open('ledger.json','w'), indent=1)

fp = sum(1 for a in audit if a['kind']=='FP')
fn = sum(1 for a in audit if a['kind']=='FN')
tp = sum(1 for a in audit if a['kind']=='TP')
tn = sum(1 for a in audit if a['kind']=='TN')
print(f'Round $r: TN={tn} FN={fn} TP={tp} FP={fp}')
" 2>&1
done
echo "=== ROUNDS 8-10 COMPLETE ==="