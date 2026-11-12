"""Explainable continuity warnings from EXPLICIT, human-reviewed annotations."""
def check_continuity(data):
    order={s['scene_id']:s['script_order'] for s in data['scenes']}
    events=sorted(data.get('events',[]),key=lambda e:(order.get(e['scene_id'],99999),e.get('id',0)))
    warnings=[];state={}
    for ev in events:
        if ev['scene_id'] not in order: raise ValueError('Continuity event references invalid scene')
        key=(ev['character'].upper(),ev['prop'].upper())
        existing=state.get(key,'UNKNOWN');action=ev['action']
        if action=='USE' and existing=='LOST':
            warnings.append({'scene_id':ev['scene_id'],'prop':ev['prop'],'message':f"{ev['character']} uses {ev['prop']} after a recorded loss, with no recovery event.",'severity':'warning'})
        elif action=='LOSE' and existing=='LOST':
            warnings.append({'scene_id':ev['scene_id'],'prop':ev['prop'],'message':f"{ev['prop']} is lost again without a recorded recovery.",'severity':'warning'})
        elif action in ('ACQUIRE','RECOVER'):
            state[key]='HELD'
        elif action=='LOSE':
            state[key]='LOST'
    return warnings
