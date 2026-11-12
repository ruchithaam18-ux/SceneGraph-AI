"""Owner-scoped CRUD and scheduling orchestration for SceneGraph.

All user-editable data is stored in a real SQL database, not JS/localStorage.
"""
from __future__ import annotations
import hashlib, json
from sqlalchemy import select, delete
from sqlalchemy.orm import Session
from models import (Project, Scene, Character, Location, SceneCharacter,
                    ContinuityEvent, AuditEvent, utcnow)
from core.parser import parse_screenplay
from core.normalizer import normalize_script, canonical_name
from core.graph_engine import graph_payload
from core.continuity import check_continuity
from core.scheduler import optimize_schedule
from core.baseline import greedy_schedule
from core.analytics import compare_schedules


def audited(db: Session, uid: int, project_id: int | None, action: str, detail: str = ''):
    db.add(AuditEvent(owner_id=uid, project_id=project_id, action=action, detail=detail[:250]))


def owned_project(db: Session, uid: int, pid: int):
    p = db.scalar(select(Project).where(Project.id == pid, Project.owner_id == uid))
    if p is None:
        raise ValueError('Project not found or you do not have access.')
    return p


def create_project(db: Session, uid: int, text: str, title: str):
    parsed = normalize_script(parse_screenplay(text))
    if len(parsed['scenes']) > 80:
        raise ValueError('This release supports up to 80 scenes per project.')
    title = str(title).strip()[:110] or 'Untitled Production'
    project = Project(owner_id=uid, title=title, source_text=text,
                      settings={'days': 4, 'slots_per_day': 12, 'actor_blocks': {}, 'location_blocks': {}, 'max_seconds': 8}, schedules={})
    db.add(project); db.flush()
    locations = {}
    for l in parsed['locations']:
        row=Location(project_id=project.id, name=canonical_name(l['name']))
        db.add(row); db.flush(); locations[l['id']]=row.id
    chars={}
    for c in parsed['characters']:
        row=Character(project_id=project.id,name=canonical_name(c['name']))
        db.add(row); db.flush(); chars[c['id']]=row.id
    for s in parsed['scenes']:
        scene=Scene(project_id=project.id, script_order=s['script_order'],heading=s['heading'][:240],
                    location_id=locations[s['location_id']],time_of_day=s['time_of_day'],
                    duration_slots=s['duration_slots'],body=s['body'])
        db.add(scene);db.flush()
        for cid in s['character_ids']:
            db.add(SceneCharacter(scene_id=scene.id, character_id=chars[cid]))
    audited(db,uid,project.id,'IMPORT',f'{len(parsed["scenes"])} scenes imported')
    db.commit()
    return project.id, parsed['warnings']


def list_projects(db: Session, uid: int):
    projects=db.scalars(select(Project).where(Project.owner_id==uid).order_by(Project.updated_at.desc(),Project.id.desc())).all()
    return [{'id':p.id,'title':p.title,'created_at':p.created_at.isoformat(),'updated_at':p.updated_at.isoformat()} for p in projects]


def project_data(db: Session, uid: int, pid: int):
    p=owned_project(db,uid,pid)
    locations=db.scalars(select(Location).where(Location.project_id==pid).order_by(Location.name)).all()
    characters=db.scalars(select(Character).where(Character.project_id==pid).order_by(Character.name)).all()
    scenes=db.scalars(select(Scene).where(Scene.project_id==pid).order_by(Scene.script_order)).all()
    locmap={l.id:l.name for l in locations};chmap={c.id:c.name for c in characters}
    scene_ids=[s.id for s in scenes]
    edges=db.scalars(select(SceneCharacter).where(SceneCharacter.scene_id.in_(scene_ids))).all() if scenes else []
    byscene={s.id:[] for s in scenes}
    for edge in edges:
        if edge.character_id in chmap: byscene[edge.scene_id].append(edge.character_id)
    events=db.scalars(select(ContinuityEvent).where(ContinuityEvent.project_id==pid).order_by(ContinuityEvent.id)).all()
    return {
        'id':p.id,'title':p.title,'created_at':p.created_at.isoformat(),
        'scenes':[{'scene_id':s.id,'script_order':s.script_order,'heading':s.heading,
                   'location_id':s.location_id,'location':locmap.get(s.location_id,'UNSPECIFIED'),
                   'time_of_day':s.time_of_day,'duration_slots':s.duration_slots,'body':s.body,
                   'character_ids':sorted(byscene[s.id]),'speakers':[chmap[x] for x in sorted(byscene[s.id])]} for s in scenes],
        'characters':[{'id':c.id,'name':c.name} for c in characters],
        'locations':[{'id':l.id,'name':l.name} for l in locations],
        'events':[{'id':e.id,'scene_id':e.scene_id,'prop':e.prop,'action':e.action,'character':e.character} for e in events],
        'settings':p.settings or {}, 'schedules':p.schedules or {},
    }


def signature(data):
    inp={'scenes':[{'id':s['scene_id'],'duration_slots':s['duration_slots'],'location_id':s['location_id'],
                    'character_ids':sorted(s['character_ids'])} for s in data['scenes']],
         'settings':data['settings']}
    return hashlib.sha256(json.dumps(inp,sort_keys=True).encode('utf8')).hexdigest()


def enriched(db: Session, uid: int, pid: int):
    data=project_data(db,uid,pid)
    data['graph']=graph_payload(data)
    data['continuity_warnings']=check_continuity(data)
    optimized=data['schedules'].get('optimized')
    data['schedule_stale']=bool(optimized and optimized.get('signature')!=signature(data))
    baseline=data['schedules'].get('baseline')
    data['comparison']=compare_schedules(baseline,optimized) if baseline and optimized and not data['schedule_stale'] else None
    return data


def modify_scene(db:Session,uid:int,pid:int,sid:int,changes:dict):
    owned_project(db,uid,pid)
    scene=db.scalar(select(Scene).where(Scene.id==sid,Scene.project_id==pid))
    if scene is None:raise ValueError('Scene does not belong to this project.')
    fields={'heading','location_id','time_of_day','duration_slots'}
    changes={k:v for k,v in changes.items() if k in fields}
    if not changes:raise ValueError('No editable fields provided.')
    if 'location_id' in changes:
        lid=int(changes['location_id'])
        if not db.scalar(select(Location).where(Location.id==lid,Location.project_id==pid)):
            raise ValueError('Location is not part of the project.')
        scene.location_id=lid
    if 'heading' in changes:
        heading=str(changes['heading']).strip()
        if not heading or len(heading)>240:raise ValueError('Heading length must be 1–240.')
        scene.heading=heading
    if 'time_of_day' in changes:
        tod=str(changes['time_of_day']).strip().upper()
        if not tod or len(tod)>40:raise ValueError('Invalid time-of-day label.')
        scene.time_of_day=tod
    if 'duration_slots' in changes:
        d=int(changes['duration_slots'])
        if not 1<=d<=24:raise ValueError('Duration must be 1–24 slots.')
        scene.duration_slots=d
    audited(db,uid,pid,'SCENE_UPDATED',f'scene {sid}')
    db.commit()


def modify_cast(db:Session,uid:int,pid:int,sid:int,cids:list[int]):
    owned_project(db,uid,pid)
    if not db.scalar(select(Scene).where(Scene.id==sid,Scene.project_id==pid)):
        raise ValueError('Scene does not belong to this project.')
    valid={c.id for c in db.scalars(select(Character).where(Character.project_id==pid)).all()}
    if not set(cids).issubset(valid):raise ValueError('Cast contains a character from another project.')
    db.execute(delete(SceneCharacter).where(SceneCharacter.scene_id==sid))
    for cid in set(cids):db.add(SceneCharacter(scene_id=sid,character_id=cid))
    audited(db,uid,pid,'CAST_UPDATED',f'scene {sid}')
    db.commit()


def modify_settings(db:Session,uid:int,pid:int,config:dict):
    p=owned_project(db,uid,pid)
    data=project_data(db,uid,pid)
    try:days=int(config.get('days',4)); slots=int(config.get('slots_per_day',12));seconds=int(config.get('max_seconds',8))
    except (TypeError,ValueError): raise ValueError('Days, slots, and seconds must be integers.')
    if not 1<=days<=14 or not 2<=slots<=24:raise ValueError('Days must be 1–14 and slots per day 2–24.')
    valid_chars={str(c['id']) for c in data['characters']};valid_locs={str(l['id']) for l in data['locations']}
    result={'days':days,'slots_per_day':slots,'max_seconds':max(1,min(15,seconds))}
    for typ,valid in [('actor_blocks',valid_chars),('location_blocks',valid_locs)]:
        blocks=config.get(typ,{})
        if not isinstance(blocks,dict):raise ValueError('Availability data must be a dictionary.')
        clean={}
        for key,arr in blocks.items():
            if key not in valid or not isinstance(arr,list) or len(arr)>30:raise ValueError('Unknown participant or excessive blocks.')
            checked=[]
            for b in arr:
                try:day=int(b['day']);start=int(b['start']);end=int(b['end'])
                except (TypeError,KeyError,ValueError):raise ValueError('Malformed availability block.')
                if not (0<=day<days and 0<=start<end<=slots):raise ValueError('Availability outside production calendar.')
                checked.append({'day':day,'start':start,'end':end})
            clean[key]=checked
        result[typ]=clean
    p.settings=result
    audited(db,uid,pid,'SETTINGS_UPDATED','availability or crew calendar')
    db.commit()


def add_metadata(db:Session,uid:int,pid:int,kind:str,name:str):
    owned_project(db,uid,pid)
    name=canonical_name(name)
    if not name or len(name)>80:raise ValueError('Name must be 1–80 characters.')
    model={'character':Character,'location':Location}.get(kind)
    if model is None:raise ValueError('Type must be character or location.')
    existing=db.scalar(select(model).where(model.project_id==pid,model.name==name))
    if not existing:
        db.add(model(project_id=pid,name=name));audited(db,uid,pid,'METADATA_ADDED',f'{kind}: {name}')
        db.commit()


def add_event(db:Session,uid:int,pid:int,sid:int,prop:str,action:str,character:str):
    owned_project(db,uid,pid)
    if not db.scalar(select(Scene).where(Scene.project_id==pid,Scene.id==sid)):
        raise ValueError('Invalid scene.')
    action=action.upper(); prop=canonical_name(prop);character=canonical_name(character or 'GLOBAL')
    if action not in {'ACQUIRE','LOSE','USE','RECOVER'}:raise ValueError('Invalid continuity action.')
    if not 1<=len(prop)<=80 or not 1<=len(character)<=80:raise ValueError('Invalid prop/character label.')
    db.add(ContinuityEvent(project_id=pid,scene_id=sid,prop=prop,action=action,character=character))
    audited(db,uid,pid,'CONTINUITY_ANNOTATED',f'scene {sid}: {action} {prop}')
    db.commit()


def remove_event(db:Session,uid:int,pid:int,eid:int):
    owned_project(db,uid,pid)
    event=db.scalar(select(ContinuityEvent).where(ContinuityEvent.id==eid,ContinuityEvent.project_id==pid))
    if event is None:raise ValueError('Event does not belong to this project.')
    db.delete(event);audited(db,uid,pid,'EVENT_DELETED',f'event {eid}')
    db.commit()


def schedule(db:Session,uid:int,pid:int,replan:bool=False):
    p=owned_project(db,uid,pid)
    data=project_data(db,uid,pid)
    prior=data['schedules'].get('optimized') if replan else None
    baseline=greedy_schedule(data['scenes'],data['settings'])
    opt=optimize_schedule(data,data['settings'],prior_schedule=prior)
    sign=signature(data)
    baseline['signature']=sign;opt['signature']=sign
    p.schedules={'baseline':baseline,'optimized':opt}
    audited(db,uid,pid,'REPLAN' if replan else 'OPTIMIZE',f'{opt["status"]}; {opt["method"]}')
    db.commit()
    return enriched(db,uid,pid)


def delete_project(db:Session,uid:int,pid:int):
    p=owned_project(db,uid,pid)
    db.delete(p);audited(db,uid,pid,'DELETE_PROJECT','User deleted project')
    db.commit()
