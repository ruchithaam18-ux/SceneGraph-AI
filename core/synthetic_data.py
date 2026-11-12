"""Controlled, seeded test scenarios; generated numbers are NOT empirical production data."""
import random

def generate_scenario(n_scenes=12,seed=11):
    if not 2<=n_scenes<=50:raise ValueError('Scene count must be 2-50')
    rng=random.Random(seed);nactors=max(4,min(12,n_scenes//3));nloc=max(3,min(7,n_scenes//4))
    actors=[{'id':i+1,'name':f'ACTOR {i+1}'} for i in range(nactors)]
    locs=[{'id':i+1,'name':f'LOCATION {i+1}'} for i in range(nloc)]
    scenes=[]
    for i in range(n_scenes):
        nc=rng.choice([1,1,2,2,3]);ids=sorted(rng.sample(range(1,nactors+1),min(nc,nactors)))
        scenes.append({'scene_id':i+1,'script_order':i+1,'heading':f'INT. LOCATION {i%nloc+1} - DAY',
                       'duration_slots':rng.choice([1,2,2,3]),'character_ids':ids,'location_id':(i%nloc)+1})
    days=min(14,max(3,(sum(s['duration_slots'] for s in scenes)+8)//10))
    cfg={'days':days,'slots_per_day':12,'actor_blocks':{},'location_blocks':{},'max_seconds':4}
    return {'scenes':scenes,'characters':actors,'locations':locs},cfg
