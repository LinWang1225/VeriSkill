import re
def is_year(n): return 1939<=n<=1990
def cell_amount(cell):
    c=cell.strip()
    if c=="": return 0.0
    if re.search(r'[A-Za-z]',c): return 0.0
    if '/' in c: return 0.0
    if re.fullmatch(r'[\.\-\*]+',c): return 0.0
    t=0.0
    for tk in re.findall(r'[\d,]+(?:\.\d+)?',c):
        v=float(tk.replace(',',''))
        if v==int(v) and is_year(int(v)): continue
        t+=v
    return t
def row_has_total(cells):
    for c in cells:
        if c.strip().rstrip('.').lower().startswith('total'): return True
    return False
def parse(path):
    lines=open(path).read().splitlines()
    si=next(i for i,l in enumerate(lines) if 'Maturity Schedule of Interest-Bearing' in l)
    ei=next(i for i in range(si+1,len(lines)) if 'callable issues appear twice' in lines[i])
    S=0.0; dr=0
    for l in lines[si:ei]:
        if not l.lstrip().startswith('|'): continue
        if 'level' in l or '---' in l: continue
        cells=[x.strip() for x in l.strip().strip('|').split('|')]
        if row_has_total(cells): continue
        rs=sum(cell_amount(c) for c in cells)
        S+=rs
        if rs>0: dr+=1
    return S,dr
base='/tmp/veriskill-oracle-rrb6fZ/solve/data/treasury_bulletins/'
tm={1948:166404,1949:157731,1950:155365,1951:152758}
cpp={1948:165,1949:163,1950:161,1951:158}
TPM={y:tm[y]-cpp[y]+50 for y in tm}
res={}
for y in [1948,1949,1950,1951]:
    S,dr=parse(base+f'treasury_bulletin_{y}_01.txt')
    fixed=2*TPM[y]-S
    res[y]=(TPM[y],S,fixed)
    print(f"{y}: TPM={TPM[y]} S_all={S} detail_rows={dr} fixed_total={fixed} fixed_B={fixed/1000:.6f}")
xs=[1948,1949,1950,1951]; ys=[res[y][2]/1000 for y in xs]
print("ys:",ys)
n=len(xs);xb=sum(xs)/n;yb=sum(ys)/n
b=sum((xs[i]-xb)*(ys[i]-yb) for i in range(n))/sum((xs[i]-xb)**2 for i in range(n))
a=yb-b*xb; p=a+b*1952
print(f"a={a} b={b} proj1952={p} rounded={round(p,1)}")
