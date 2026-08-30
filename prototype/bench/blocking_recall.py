import random, sys, itertools, time
sys.path.insert(0, "/Users/igor/Projects/Obscura/prototype")
from pseudex.fuzzy import bucket_keys, candidate_lengths, within_one_typo
D = "/Users/igor/Projects/Obscura/prototype/licensing/data/"
vocab = sorted(set(w.strip() for w in open(D+"surnames.txt") if w.strip())
             | set(w.strip() for w in open(D+"first_names.txt") if w.strip()))
AL = "абвгдеёжзийклмнопрстуфхцчшщъыьэюя"; random.seed(20260830)

idxA = {}
for w in vocab:
    for k in bucket_keys(w): idxA.setdefault((k, len(w)), []).append(w)
def genA(q):
    for k, L in itertools.product(bucket_keys(q), candidate_lengths(q)):
        yield from idxA.get((k, L), ())

idxB = {}
for w in vocab:
    a = len(w)//2
    idxB.setdefault(("P", w[:a], len(w)), []).append(w)
    idxB.setdefault(("S", w[a:], len(w)), []).append(w)
def genB(q):
    # boundary-transposition repair: also probe q with the split-point pair swapped
    for L in candidate_lengths(q):
        a = L//2; sl = L-a
        variants = [q]
        if 0 < a < len(q):
            variants.append(q[:a-1] + q[a] + q[a-1] + q[a+1:])
        for v in variants:
            yield from idxB.get(("P", v[:a], L), ())
            if sl <= len(v): yield from idxB.get(("S", v[len(v)-sl:], L), ())

idxC = {}
def dels(w):
    yield w
    for i in range(len(w)): yield w[:i]+w[i+1:]
for w in vocab:
    for d in dels(w): idxC.setdefault(d, []).append(w)
def genC(q):
    for d in dels(q): yield from idxC.get(d, ())

def corrupt(w):
    op = random.choice(("sub","del","ins","swap")); i = random.randrange(len(w))
    if op=="sub": return w[:i]+random.choice(AL)+w[i+1:]
    if op=="del": return w[:i]+w[i+1:]
    if op=="ins": return w[:i]+random.choice(AL)+w[i:]
    if len(w)<2: return w
    i = random.randrange(len(w)-1); return w[:i]+w[i+1]+w[i]+w[i+2:]

words=[w for w in random.sample(vocab,40000) if len(w)>=3]
trials=[(w,q) for w in words for q in [corrupt(w)] if q!=w and within_one_typo(q,w)]
from collections import defaultdict
hit=defaultdict(lambda: defaultdict(int)); tot=defaultdict(int); cost=defaultdict(int)
gens={"A":genA,"B":genB,"C":genC}
for w,q in trials:
    L=len(w); tot[L]+=1
    for name,g in gens.items():
        cands=list(g(q)); cost[name]+=len(cands)
        if w in cands: hit[name][L]+=1
print(f"trials {len(trials):,}   vocab {len(vocab):,}")
print(f"{'len':>4} {'n':>7} {'A first3/last3':>15} {'B halves+swap':>14} {'C deletion':>11}")
for L in sorted(tot):
    if tot[L]<30: continue
    n=tot[L]; print(f"{L:>4} {n:>7} {hit['A'][L]/n:>14.1%} {hit['B'][L]/n:>13.1%} {hit['C'][L]/n:>10.1%}")
N=len(trials)
print(f"{'ALL':>4} {N:>7} {sum(hit['A'].values())/N:>14.1%} {sum(hit['B'].values())/N:>13.1%} {sum(hit['C'].values())/N:>10.1%}")
print("\nCOST: mean candidates verified per lookup")
for k in "ABC": print(f"  {k}: {cost[k]/N:8.1f}")
print("\nINDEX SIZE (entries / postings)")
for k,ix in (("A",idxA),("B",idxB),("C",idxC)):
    post=sum(len(v) for v in ix.values())
    print(f"  {k}: {len(ix):>9,} keys  {post:>10,} postings  ({post/len(vocab):.1f}x vocab)")
# latency
import timeit
qs=[q for _,q in trials[:2000]]
for k,g in gens.items():
    t=timeit.timeit(lambda: [any(within_one_typo(q,c) for c in g(q)) for q in qs], number=1)
    print(f"  {k}: {t/len(qs)*1e6:8.1f} us/lookup (python, incl. verification)")
