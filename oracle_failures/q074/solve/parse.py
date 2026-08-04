import re

def is_year(n):
    return (1939 <= n <= 1990)

def cell_amount(cell):
    c = cell.strip()
    if c == "":
        return 0.0
    if re.search(r'[A-Za-z]', c):
        return 0.0
    if '/' in c:
        return 0.0
    if re.fullmatch(r'[\.\-\*]+', c):
        return 0.0
    toks = re.findall(r'[\d,]+(?:\.\d+)?', c)
    total = 0.0
    for t in toks:
        val = float(t.replace(',', ''))
        if val == int(val) and is_year(int(val)):
            continue
        total += val
    return total

def row_has_total(cells):
    for c in cells:
        cc = c.strip().rstrip('.')
        if cc.lower().startswith('total'):
            return True
    return False

def parse_maturity(path, start_pat, end_pat):
    lines = open(path).read().splitlines()
    si = None
    for i, l in enumerate(lines):
        if start_pat in l:
            si = i; break
    ei = None
    for i in range(si+1, len(lines)):
        if end_pat in lines[i]:
            ei = i; break
    table_lines = lines[si:ei]
    S = 0.0
    dr = 0
    for l in table_lines:
        if not l.lstrip().startswith('|'):
            continue
        if 'level' in l or '---' in l:
            continue
        cells = [x.strip() for x in l.strip().strip('|').split('|')]
        if row_has_total(cells):
            continue
        rs = sum(cell_amount(c) for c in cells)
        S += rs
        if rs > 0: dr += 1
    return S, dr

base = '/tmp/veriskill-oracle-rrb6fZ/solve/data/treasury_bulletins/'
configs = {
    1948: (base+'treasury_bulletin_1948_01.txt', 'As of November 30, 1947', 'Source: Daily Treasury Statement'),
    1949: (base+'treasury_bulletin_1949_01.txt', 'Outstanding November 30, 1948', 'Source: Daily Treasury Statement and Public Debt Service'),
    1950: (base+'treasury_bulletin_1950_01.txt', 'Outstanding November 30, 1949', 'Source: Daily Treasury Statement and Bureau of the Public Debt'),
    1951: (base+'treasury_bulletin_1951_01.txt', 'Outstanding November 30, 1950', 'Source: Daily Treasury Statement and Bureau of the Public Debt'),
}
total_marketable = {1948:166404, 1949:157731, 1950:155365, 1951:152758}
cpp = {1948:165, 1949:163, 1950:161, 1951:158}
panama = 50
TPM = {y: total_marketable[y]-cpp[y]+panama for y in total_marketable}
res = {}
for y in [1948,1949,1950,1951]:
    path, sp, ep = configs[y]
    S, dr = parse_maturity(path, sp, ep)
    fixed = 2*TPM[y]-S
    res[y]=(TPM[y],S,fixed)
    print(f"{y}: TPM={TPM[y]} S_all={S} detail_rows={dr} fixed_total={fixed} fixed_B={fixed/1000:.4f}")
xs=[1948,1949,1950,1951]; ys=[res[y][2]/1000 for y in xs]
print("ys:",ys)
n=len(xs); xb=sum(xs)/n; yb=sum(ys)/n
b=sum((xs[i]-xb)*(ys[i]-yb) for i in range(n))/sum((xs[i]-xb)**2 for i in range(n))
a=yb-b*xb
p=a+b*1952
print(f"a={a} b={b} proj1952={p} rounded={round(p,1)}")
