"""Parse Caliper console logs into one row per benchmark round.
Usage: python3 rounds.py LOG_DIR rounds.csv   (LOG_DIR holds caliper-*.log)"""
import re, sys, glob, os, csv
ANSI = re.compile(r'\x1b\[[0-9;]*m')
ROW = re.compile(r'^\|\s*(E\d)-([a-z]+)-p(\d+)-a(\d+)-L(\d+)-(\d+)tps-t(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*([\d.]+)\s*\|\s*([\d.\-]+)\s*\|\s*([\d.\-]+)\s*\|\s*([\d.\-]+)\s*\|\s*([\d.]+)\s*\|')
R, out = sys.argv[1], sys.argv[2]
rows = {}
for p in sorted(glob.glob(R + '/caliper-*.log')):
    part = os.path.basename(p).split('-')[1]
    for line in open(p, errors='replace'):
        m = ROW.match(ANSI.sub('', line).strip())
        if not m: continue
        e,s,n,a,L,load,t,su,fa,send,mx,mn,avg,thr = m.groups()
        rows[(e,s,n,a,L,load,t)] = dict(exp=e,strategy=s,N=int(n),actors=int(a),limit=int(L),load=int(load),trial=int(t),
            part=part,succ=int(su),fail=int(fa),send=float(send),avg_lat=None if avg=='-' else float(avg),thr=float(thr))
w = csv.DictWriter(open(out,'w',newline=''), fieldnames=list(next(iter(rows.values()))))
w.writeheader(); w.writerows(rows.values()); print(len(rows), 'rounds ->', out)
