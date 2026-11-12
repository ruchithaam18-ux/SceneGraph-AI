"""Constraint-based production scheduler: OR-Tools CP-SAT / SciPy MILP / heuristic fallback.
All model formulations enforce exactly-once scene assignment and single-crew non-overlap.
"""
from __future__ import annotations
import time
from .constraints import candidates, validate_config, verify_schedule, schedule_metrics
from .baseline import greedy_schedule


def _places(scenes,cfg):
    return {s['scene_id']:candidates(s,cfg) for s in scenes}

def _result(scenes,cfg,selected,status,method,began,prior,message):
    assignments=[]
    for s in scenes:
        d,t=selected[s['scene_id']]
        assignments.append({'scene_id':s['scene_id'],'day':int(d),'start_slot':int(t),'end_slot':int(t+s['duration_slots']),'location_id':s['location_id']})
    assignments.sort(key=lambda a:(a['day'],a['start_slot']))
    violations=verify_schedule(scenes,cfg,assignments)
    return {'status':status if not violations else 'INVALID','method':method,'assignments':assignments,'metrics':schedule_metrics(assignments,prior),'elapsed_ms':round((time.perf_counter()-began)*1000,1),'violations':violations,'message':message}

def _cp_sat(scenes,cfg,places,prior,began):
    from ortools.sat.python import cp_model
    model=cp_model.CpModel()
    xs={};days=cfg['days'];spd=cfg['slots_per_day']
    for s in scenes:
        sid=s['scene_id'];vs=[]
        for d,t in places[sid]:
            v=model.new_bool_var(f'p_{sid}_{d}_{t}');xs[(sid,d,t)]=v;vs.append(v)
        model.add_exactly_one(vs)
    for d in range(days):
        for t in range(spd):
            occupied=[v for (sid,day,start),v in xs.items() if day==d and start<=t<start+next(s['duration_slots'] for s in scenes if s['scene_id']==sid)]
            if occupied:model.add_at_most_one(occupied)
    ydays=[];ylocs=[]
    for d in range(days):
        vars_d=[v for (sid,dd,t),v in xs.items() if dd==d]
        active=model.new_bool_var('day_'+str(d));ydays.append(active)
        model.add(sum(vars_d)>=active)
        model.add(sum(vars_d)<=len(scenes)*active)
        for loc in {s['location_id'] for s in scenes}:
            vloc=[v for (sid,dd,t),v in xs.items() if dd==d and next(s['location_id'] for s in scenes if s['scene_id']==sid)==loc]
            if vloc:
                yl=model.new_bool_var(f'loc_{d}_{loc}');ylocs.append(yl)
                model.add(sum(vloc)>=yl);model.add(sum(vloc)<=len(scenes)*yl)
    last=model.new_int_var(1,days,'last_day')
    for d,y in enumerate(ydays):model.add(last>=(d+1)*y)
    prev={a['scene_id']:(a['day'],a['start_slot']) for a in (prior or [])}
    changed=[]
    for sid,old in prev.items():
        if sid not in {s['scene_id'] for s in scenes}:continue
        current=xs.get((sid,*old))
        if current is not None:changed.append(1-current)
        else:changed.append(1)
    # Location-day count is an approximate proxy for location change logistics.
    model.minimize(10000*last + 1000*sum(ydays) + 20*sum(ylocs) + 35*sum(changed))
    solver=cp_model.CpSolver();solver.parameters.max_time_in_seconds=float(cfg.get('max_seconds',8));solver.parameters.num_search_workers=4
    stat=solver.solve(model)
    if stat in (cp_model.OPTIMAL,cp_model.FEASIBLE):
        selected={(sid):(d,t) for (sid,d,t),v in xs.items() if solver.value(v)==1}
        return _result(scenes,cfg,selected,'OPTIMAL' if stat==cp_model.OPTIMAL else 'FEASIBLE','OR-Tools CP-SAT',began,prior,'CP-SAT optimization with production span, used days, location grouping, and replanning stability.')
    return {'status':'INFEASIBLE' if stat==cp_model.INFEASIBLE else 'UNKNOWN','method':'OR-Tools CP-SAT','assignments':[],'metrics':{},'elapsed_ms':round((time.perf_counter()-began)*1000,1),'violations':[],'message':'No valid assignment exists.' if stat==cp_model.INFEASIBLE else 'Solver timed out without finding a solution.'}

def _milp(scenes,cfg,places,prior,began):
    """Exact 0-1 mixed-integer placement model, used if OR-Tools is unavailable."""
    import numpy as np
    from scipy.optimize import milp, Bounds, LinearConstraint
    from scipy.sparse import coo_matrix
    days=cfg['days'];spd=cfg['slots_per_day'];locs=sorted({s['location_id'] for s in scenes})
    keys=[(s['scene_id'],d,t) for s in scenes for d,t in places[s['scene_id']]]
    num=len(keys);idx={key:i for i,key in enumerate(keys)}
    yd={d:num+d for d in range(days)}
    yl={(d,loc):num+days+i for i,(d,loc) in enumerate((d,l) for d in range(days) for l in locs)}
    last_idx=num+days+len(yl);n=last_idx+1
    c=np.zeros(n);c[last_idx]=10000
    for i in yd.values():c[i]=1000
    for i in yl.values():c[i]=20
    prev={a['scene_id']:(a['day'],a['start_slot']) for a in (prior or [])}
    for i,(sid,d,t) in enumerate(keys):
        if sid in prev and prev[sid]==(d,t):c[i]-=35
    row=[];col=[];val=[];lo=[];hi=[]
    def add(terms,lower,upper):
        j=len(lo);lo.append(lower);hi.append(upper)
        for k,v in terms:
            row.append(j);col.append(k);val.append(v)
    for s in scenes:
        add([(idx[(s['scene_id'],d,t)],1) for d,t in places[s['scene_id']]],1,1)
    dur={s['scene_id']:s['duration_slots'] for s in scenes}
    for d in range(days):
        for slot in range(spd):
            terms=[(i,1) for i,(sid,dd,t) in enumerate(keys) if dd==d and t<=slot<t+dur[sid]]
            if terms:add(terms,0,1)
    for d in range(days):
        xday=[(i,1) for i,(_,dd,_) in enumerate(keys) if dd==d]
        add(xday+[(yd[d],-len(scenes))],-np.inf,0)
        add(xday+[(yd[d],-1)],0,np.inf)
        add([(yd[d],d+1),(last_idx,-1)],-np.inf,0)
        for loc in locs:
            xloc=[(i,1) for i,(sid,dd,_) in enumerate(keys) if dd==d and next(s['location_id'] for s in scenes if s['scene_id']==sid)==loc]
            add(xloc+[(yl[(d,loc)],-len(scenes))],-np.inf,0)
            add(xloc+[(yl[(d,loc)],-1)],0,np.inf)
    A=coo_matrix((val,(row,col)),shape=(len(lo),n)).tocsr()
    lower=np.zeros(n);upper=np.ones(n);upper[last_idx]=days;lower[last_idx]=1
    res=milp(c,integrality=np.ones(n),bounds=Bounds(lower,upper),constraints=LinearConstraint(A,np.array(lo),np.array(hi)),options={'time_limit':float(cfg.get('max_seconds',8)),'mip_rel_gap':0.0})
    if res.x is not None and all(abs(res.x[i]-round(res.x[i]))<0.001 for i in range(num)):
        selected={(sid):(d,t) for i,(sid,d,t) in enumerate(keys) if res.x[i]>0.5}
        if len(selected)==len(scenes):return _result(scenes,cfg,selected,'OPTIMAL' if res.status==0 else 'FEASIBLE','SciPy HiGHS MILP',began,prior,'Mixed-integer optimization; location-day grouping is a proxy for travel transitions.')
    return {'status':'INFEASIBLE' if res.status==2 else 'UNKNOWN','method':'SciPy HiGHS MILP','assignments':[],'metrics':{},'elapsed_ms':round((time.perf_counter()-began)*1000,1),'violations':[],'message':str(res.message)[:250]}

def optimize_schedule(data,constraints,prior_schedule=None):
    scenes=data['scenes'] if isinstance(data,dict) else data
    began=time.perf_counter();validate_config(scenes,constraints)
    prior=prior_schedule.get('assignments',[]) if isinstance(prior_schedule,dict) else (prior_schedule or [])
    places=_places(scenes,constraints)
    missing=[s['script_order'] for s in scenes if not places[s['scene_id']]]
    if missing:
        return {'status':'INFEASIBLE','method':'Precheck','assignments':[],'metrics':{},'elapsed_ms':round((time.perf_counter()-began)*1000,1),'violations':[],'message':f'Scenes {missing} have zero valid positions under the current constraints.'}
    try:
        import ortools # noqa
    except ImportError:
        try:
            import scipy # noqa
        except ImportError:
            sorted_scenes=sorted(scenes,key=lambda s:(len(places[s['scene_id']]),-s['duration_slots']))
            result=greedy_schedule(scenes,constraints,order=sorted_scenes)
            result['method']='Constraint-aware heuristic (install OR-Tools for exact optimization)'
            result['status']='HEURISTIC_FEASIBLE' if result['status']=='FEASIBLE' else 'UNKNOWN'
            result['metrics']=schedule_metrics(result['assignments'],prior) if result['assignments'] else {}
            return result
        else:return _milp(scenes,constraints,places,prior,began)
    else:return _cp_sat(scenes,constraints,places,prior,began)
