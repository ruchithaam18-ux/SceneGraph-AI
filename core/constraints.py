"""Hard constraints: single crew, one assignment per scene, valid calendars, fixed durations."""
def validate_config(scenes,cfg):
    if not scenes:raise ValueError('At least one scene is required')
    days=cfg['days'];spd=cfg['slots_per_day']
    if not (1<=days<=14 and 2<=spd<=24):raise ValueError('Invalid production calendar')
    ids=[s['scene_id'] for s in scenes]
    if len(set(ids))!=len(ids):raise ValueError('Duplicate scene IDs')
    if any(s['duration_slots']>spd or s['duration_slots']<1 for s in scenes):raise ValueError('A scene does not fit in the daily schedule')

def allowed(scene,day,start,cfg):
    end=start+scene['duration_slots']
    if not 0<=day<cfg['days'] or not 0<=start<end<=cfg['slots_per_day']:return False
    for cid in scene['character_ids']:
        for b in cfg.get('actor_blocks',{}).get(str(cid),[]):
            if b['day']==day and start<b['end'] and end>b['start']:return False
    for b in cfg.get('location_blocks',{}).get(str(scene['location_id']),[]):
        if b['day']==day and start<b['end'] and end>b['start']:return False
    return True

def candidates(scene,cfg):
    dur=scene['duration_slots'];return [(d,s) for d in range(cfg['days']) for s in range(cfg['slots_per_day']-dur+1) if allowed(scene,d,s,cfg)]

def verify_schedule(scenes,cfg,assignments):
    expected={s['scene_id']:s for s in scenes};seen=set();occupied=set();violations=[]
    for a in assignments:
        sid=a['scene_id'];s=expected.get(sid)
        if not s:violations.append(f'Unknown scene {sid}');continue
        if sid in seen:violations.append(f'Scene {sid} assigned twice')
        seen.add(sid)
        day=a['day'];start=a['start_slot'];end=a['end_slot']
        if end!=start+s['duration_slots'] or not allowed(s,day,start,cfg):violations.append(f'Scene {sid} violates availability/duration')
        for t in range(start,end):
            key=(day,t)
            if key in occupied:violations.append(f'Crew overlap on day {day+1}, slot {t}')
            occupied.add(key)
    if seen!=set(expected):violations.append('Missing scene assignments')
    return sorted(set(violations))

def schedule_metrics(assignments,prior=None):
    ordered=sorted(assignments,key=lambda a:(a['day'],a['start_slot']))
    days=len({a['day'] for a in ordered});changes=0
    for a,b in zip(ordered,ordered[1:]):
        if a['day']==b['day'] and a['location_id']!=b['location_id']:changes+=1
    old={a['scene_id']:(a['day'],a['start_slot']) for a in (prior or [])}
    moved=sum(old.get(a['scene_id']) not in (None,(a['day'],a['start_slot'])) for a in ordered)
    return {'production_days':days,'last_day':(max([a['day'] for a in ordered],default=-1)+1),'location_changes':changes,'moved_scenes':moved,'total_scenes':len(ordered)}
