from core.synthetic_data import generate_scenario
from core.baseline import greedy_schedule
from core.scheduler import optimize_schedule
from core.constraints import verify_schedule
from core.analytics import compare_schedules

def setup():
    data,cfg=generate_scenario(8,19);cfg['days']=4;cfg['max_seconds']=3
    return data,cfg

def test_optimizer_valid_schedule():
    data,cfg=setup();result=optimize_schedule(data,cfg)
    assert result['status'] in ('FEASIBLE','OPTIMAL','HEURISTIC_FEASIBLE')
    assert len(result['assignments'])==8
    assert result['violations']==[]
    assert verify_schedule(data['scenes'],cfg,result['assignments'])==[]
def test_baseline_respects_same_constraints():
    data,cfg=setup();base=greedy_schedule(data['scenes'],cfg);optimized=optimize_schedule(data,cfg)
    assert base['status']=='FEASIBLE'
    assert compare_schedules(base,optimized)['comparable']
def test_infeasible_precheck_when_actor_blocked():
    data,cfg=setup();cid=data['scenes'][0]['character_ids'][0]
    cfg['actor_blocks']={str(cid):[{'day':d,'start':0,'end':cfg['slots_per_day']} for d in range(cfg['days'])]}
    result=optimize_schedule(data,cfg)
    assert result['status']=='INFEASIBLE'
def test_replanning_after_actor_unavailable():
    data,cfg=setup();original=optimize_schedule(data,cfg)
    a=original['assignments'][0];scene=next(s for s in data['scenes'] if s['scene_id']==a['scene_id'])
    cid=scene['character_ids'][0]
    cfg['actor_blocks']={str(cid):[{'day':a['day'],'start':0,'end':cfg['slots_per_day']}]}
    revised=optimize_schedule(data,cfg,prior_schedule=original)
    assert revised['status'] in ('FEASIBLE','OPTIMAL','HEURISTIC_FEASIBLE')
    assert revised['violations']==[]
    new=next(x for x in revised['assignments'] if x['scene_id']==a['scene_id'])
    assert new['day']!=a['day']
    assert revised['metrics']['moved_scenes']>=1
def test_overlap_detector():
    data,cfg=setup();a=[]
    for s in data['scenes']:
        a.append({'scene_id':s['scene_id'],'day':0,'start_slot':0,'end_slot':s['duration_slots'],'location_id':s['location_id']})
    assert any('overlap' in msg.lower() for msg in verify_schedule(data['scenes'],cfg,a))
