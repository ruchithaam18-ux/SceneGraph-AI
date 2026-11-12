"""Transparent evaluation: compute comparable metrics, not invented improvement percentages."""
from .constraints import schedule_metrics

def compare_schedules(baseline,optimized):
    status_baseline=baseline.get('status','UNKNOWN');status_optimized=optimized.get('status','UNKNOWN')
    valid_base=status_baseline in {'FEASIBLE','OPTIMAL','HEURISTIC_FEASIBLE'} and not baseline.get('violations')
    valid_opt=status_optimized in {'FEASIBLE','OPTIMAL','HEURISTIC_FEASIBLE'} and not optimized.get('violations')
    def metric(r,k):return r.get('metrics',{}).get(k)
    result={'baseline_status':status_baseline,'optimized_status':status_optimized,'comparable':valid_base and valid_opt,
            'baseline':baseline.get('metrics',{}),'optimized':optimized.get('metrics',{}),
            'runtime_ms':{'baseline':baseline.get('elapsed_ms'),'optimized':optimized.get('elapsed_ms')},'deltas':{},'note':''}
    if result['comparable']:
        for key in ['production_days','last_day','location_changes']:
            a=metric(baseline,key);b=metric(optimized,key)
            result['deltas'][key]=a-b
        result['note']='Positive delta means the optimized schedule uses fewer units. Location changes are measured from sorted assignments and are not the exact solver objective.'
    else:result['note']='Not directly comparable: one or both methods failed to produce a valid full schedule. Greedy failure does not prove infeasibility.'
    return result
