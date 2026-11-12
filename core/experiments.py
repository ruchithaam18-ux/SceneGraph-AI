"""Reproducible CLI experiments: python -m core.experiments --out output/benchmark.csv"""
import csv,json,os,argparse
from .synthetic_data import generate_scenario
from .baseline import greedy_schedule
from .scheduler import optimize_schedule
from .analytics import compare_schedules

def run_experiments(sizes=(10,20,40),seeds=(11,23,37),max_seconds=4):
    rows=[]
    for size in sizes:
        for seed in seeds:
            data,cfg=generate_scenario(size,seed);cfg['max_seconds']=max_seconds
            base=greedy_schedule(data['scenes'],cfg)
            opt=optimize_schedule(data,cfg)
            comp=compare_schedules(base,opt)
            rows.append({'scenes':size,'seed':seed,'days_available':cfg['days'],'baseline_status':base['status'],
                         'optimizer_status':opt['status'],'solver':opt['method'],'baseline_days':base.get('metrics',{}).get('production_days'),
                         'optimized_days':opt.get('metrics',{}).get('production_days'),'baseline_location_changes':base.get('metrics',{}).get('location_changes'),
                         'optimized_location_changes':opt.get('metrics',{}).get('location_changes'),
                         'baseline_runtime_ms':base['elapsed_ms'],'optimizer_runtime_ms':opt['elapsed_ms'],
                         'comparable':comp['comparable'],'violations':len(opt.get('violations',[]))})
    return rows

def export_rows(rows,path):
    os.makedirs(os.path.dirname(os.path.abspath(path)),exist_ok=True)
    with open(path,'w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    return path

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--out',default='output/benchmark.csv');ap.add_argument('--seconds',type=int,default=3)
    args=ap.parse_args();rows=run_experiments(max_seconds=args.seconds);export_rows(rows,args.out)
    print(json.dumps(rows,indent=2))
