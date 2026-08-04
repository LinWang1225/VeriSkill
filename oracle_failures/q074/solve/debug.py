import re
def is_year(n): return 1939<=n<=1990
def cell_amount(cell):
    c=cell.strip()
    if c=="" : return 0.0
    if re.search(r'[A-Za-z]',c): return 0.0
    if '/' in c: return 0.0
    if re.fullmatch(r'[\.\-\*]+',c): return 0.0
    toks=re.findall(r'[\d,]+(?:\.\d+)?',c)
    t=0.0
    for tk in toks:
        v=float(tk.replace(',',''))
        if v==int(v) and is_year(int(v)): continue
        t+=v
    return t
def row_has_total(cells):
    for c in cells:
        if c.strip().rstrip('.').lower().startswith('total'): return True
    return False
path='/tmp/veriskill-oracle-rrb6fZ/solve/data/treasury_bulletins/treasury_bulletin_1949_01.txt'
lines=open(path).read().splitlines()
si=next(i for i,l in enumerate(lines) if 'Outstanding November 30, 1948' in l)
ei=next(i for i in range(si+1,len(lines)) if 'Source: Daily Treasury Statement and Public Debt Service' in lines[i])
print("range",si,ei)
S=0.0
for idx in range(si,ei):
    l=lines[idx]
    if not l.lstrip().startswith('|'): continue
    if 'level' in l or '---' in l: continue
    cells=[x.strip() for x in l.strip().strip('|').split('|')]
    if row_has_total(cells): continue
    rs=sum(cell_amount(c) for c in cells)
    if rs>0:
        print(idx+1, rs, l[:120])
        S+=rs
print("S_all=",S)
