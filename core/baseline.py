"""Fair first-fit baseline respecting all modeled hard constraints."""
import time
from .constraints import validate_config,candidates,verify_schedule,schedule_metrics

def greedy_schedule(scenes,cfg,order=None):
    began=time.perf_counter();validate_config(scenes,cfg)
    occupied=set();out=[]
    sequence=order if order is not None else sorted(scenes,key=lambda s:s['script_order'])
    for scene in sequence:
        feasible=None
        for day,start in candidates(scene,cfg):
            if all((day,t) not in occupied for t in range(start,start+scene['duration_slots'])):
                feasible=(day,start);break
        if feasible is None:
            return {'status':'FAILED_FIRST_FIT','method':'First-fit baseline','assignments':[],'metrics':{},'elapsed_ms':round((time.perf_counter()-began)*1000,1),'violations':[],'message':'Greedy placement failed; this does not prove infeasibility.'}
        day,start=feasible
        occupied.update((day,t) for t in range(start,start+scene['duration_slots']))
        out.append({'scene_id':scene['scene_id'],'day':day,'start_slot':start,'end_slot':start+scene['duration_slots'],'location_id':scene['location_id']})
    out.sort(key=lambda a:(a['day'],a['start_slot']))
    return {'status':'FEASIBLE','method':'First-fit baseline','assignments':out,'metrics':schedule_metrics(out),'elapsed_ms':round((time.perf_counter()-began)*1000,1),'violations':verify_schedule(scenes,cfg,out),'message':'First-fit heuristic; no optimality guarantee.'}
