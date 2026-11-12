"""SceneGraph AI web API. Real accounts, SQL persistence and owner-scoped projects.

FastAPI serves the same frontend locally; GitHub Pages may host docs/ separately.
"""
from __future__ import annotations
import csv, hashlib, hmac, io, os, re, secrets, time
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import timedelta
from pathlib import Path
from typing import Annotated
from fastapi import FastAPI, Request, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response, JSONResponse
from sqlalchemy import select, delete
from sqlalchemy.orm import Session
from models import create_tables, SessionLocal, User, LoginSession, utcnow
from project_service import (create_project, list_projects, enriched, owned_project,
                             modify_scene, modify_cast, modify_settings,
                             add_metadata, add_event, remove_event, schedule, delete_project)
from core.experiments import run_experiments

ROOT=Path(__file__).resolve().parent
FRONT=ROOT/'docs'
ALLOWED_ORIGINS={s.strip().rstrip('/') for s in os.getenv('CORS_ORIGINS', '').split(',') if s.strip()}
ALLOWED_ORIGINS.update({'http://localhost:8000','http://127.0.0.1:8000','http://localhost:5173','http://127.0.0.1:5173'})
SESSION_HOURS=7*24

@asynccontextmanager
async def lifespan(app:FastAPI):
    create_tables()
    yield

app=FastAPI(title='SceneGraph AI API',version='2.0',lifespan=lifespan,
            description='Secure Python REST API for screenplay analytics and constraint-based scheduling.')
app.add_middleware(CORSMiddleware,allow_origins=list(ALLOWED_ORIGINS),allow_methods=['GET','POST','DELETE','OPTIONS'],
                   allow_headers=['Authorization','Content-Type'],allow_credentials=False)

@app.middleware('http')
async def headers_and_limits(request:Request,call_next):
    length=request.headers.get('content-length')
    if length:
        try:
            if int(length)>1_500_000:return JSONResponse({'detail':'Request is larger than 1.5 MB.'},status_code=413)
        except ValueError:return JSONResponse({'detail':'Invalid content length.'},status_code=400)
    response=await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Referrer-Policy']='strict-origin-when-cross-origin'
    response.headers['X-Frame-Options']='DENY'
    response.headers['Cache-Control']='no-store' if request.url.path.startswith('/api/') else 'public, max-age=600'
    return response


def get_db():
    with SessionLocal() as db:yield db


def password_hash(pw:str):
    salt=secrets.token_bytes(16)
    digest=hashlib.pbkdf2_hmac('sha256',pw.encode(),salt,310_000)
    return 'pbkdf2_sha256$310000$'+salt.hex()+'$'+digest.hex()


def verify_password(pw:str,stored:str):
    try:
        algorithm,count,salt,hex_digest=stored.split('$')
        if algorithm!='pbkdf2_sha256':return False
        actual=hashlib.pbkdf2_hmac('sha256',pw.encode(),bytes.fromhex(salt),int(count))
        return hmac.compare_digest(actual,bytes.fromhex(hex_digest))
    except (ValueError,TypeError):return False


def make_session(db:Session,user:User):
    token=secrets.token_urlsafe(40)
    db.add(LoginSession(user_id=user.id, token_hash=hashlib.sha256(token.encode()).hexdigest(),
                        expires_at=utcnow()+timedelta(hours=SESSION_HOURS)))
    db.commit()
    return {'token':token,'user':{'id':user.id,'email':user.email,'display_name':user.display_name}}


def require_user(authorization:Annotated[str|None,Header()]=None,db:Session=Depends(get_db)):
    if not authorization or not authorization.startswith('Bearer '):
        raise HTTPException(status_code=401,detail='Please sign in to access your workspace.')
    token=authorization[7:]
    if len(token)>160:raise HTTPException(status_code=401,detail='Invalid session.')
    row=db.scalar(select(LoginSession).where(LoginSession.token_hash==hashlib.sha256(token.encode()).hexdigest()))
    if not row or row.expires_at<utcnow():
        raise HTTPException(status_code=401,detail='Your session has expired. Please sign in again.')
    user=db.get(User,row.user_id)
    if not user:raise HTTPException(status_code=401,detail='Account not found.')
    return user


# Basic in-process throttle per source IP. Put a reverse proxy/WAF in front for high-traffic production.
_attempts=defaultdict(list)
def check_auth_rate(request:Request):
    ip=request.client.host if request.client else 'unknown'
    now=time.monotonic()
    _attempts[ip]=[t for t in _attempts[ip] if now-t<300]
    if len(_attempts[ip])>=25:raise HTTPException(status_code=429,detail='Too many attempts. Try again later.')
    _attempts[ip].append(now)


def data_or_error(fn,*args,**kwargs):
    try:return fn(*args,**kwargs)
    except (ValueError,TypeError,KeyError) as ex:
        raise HTTPException(status_code=400,detail=str(ex)) from ex


@app.get('/api/health')
def health():return {'ok':True,'product':'SceneGraph AI','version':'2.0','database':'connected'}

@app.post('/api/auth/register')
def register(payload:dict,request:Request,db:Session=Depends(get_db)):
    check_auth_rate(request)
    email=str(payload.get('email','')).strip().lower()
    name=str(payload.get('display_name','')).strip()
    password=str(payload.get('password',''))
    if not re.fullmatch(r'[^@\s]{1,80}@[^@\s]{1,140}\.[^@\s]{2,20}',email):
        raise HTTPException(status_code=400,detail='Enter a valid email address.')
    if len(name)<2 or len(name)>100:raise HTTPException(status_code=400,detail='Name must be 2–100 characters.')
    if len(password)<10 or len(password)>200:raise HTTPException(status_code=400,detail='Password must be at least 10 characters.')
    if db.scalar(select(User).where(User.email==email)):
        raise HTTPException(status_code=409,detail='An account with that email already exists.')
    user=User(email=email,display_name=name,password_hash=password_hash(password))
    db.add(user);db.commit();db.refresh(user)
    demo=(ROOT/'data'/'sample_script.fountain').read_text(encoding='utf8')
    create_project(db,user.id,demo,'THE LAST FRAME — SAMPLE PRODUCTION')
    return make_session(db,user)

@app.post('/api/auth/login')
def login(payload:dict,request:Request,db:Session=Depends(get_db)):
    check_auth_rate(request)
    email=str(payload.get('email','')).strip().lower();pw=str(payload.get('password',''))
    user=db.scalar(select(User).where(User.email==email))
    if not user or not verify_password(pw,user.password_hash):
        raise HTTPException(status_code=401,detail='Incorrect email or password.')
    return make_session(db,user)

@app.post('/api/auth/logout')
def logout(authorization:Annotated[str|None,Header()]=None,db:Session=Depends(get_db),user:User=Depends(require_user)):
    token=(authorization or '')[7:]
    db.execute(delete(LoginSession).where(LoginSession.token_hash==hashlib.sha256(token.encode()).hexdigest(),LoginSession.user_id==user.id))
    db.commit()
    return {'ok':True}

@app.get('/api/auth/me')
def me(user:User=Depends(require_user)):
    return {'id':user.id,'email':user.email,'display_name':user.display_name}

@app.get('/api/projects')
def projects(db:Session=Depends(get_db),user:User=Depends(require_user)):
    return {'projects':list_projects(db,user.id)}

@app.get('/api/state')
def state(project_id:int|None=None,db:Session=Depends(get_db),user:User=Depends(require_user)):
    if project_id is None:
        items=list_projects(db,user.id)
        if not items:raise HTTPException(status_code=404,detail='No productions yet. Import your first screenplay.')
        project_id=items[0]['id']
    return data_or_error(enriched,db,user.id,project_id)

@app.post('/api/import')
def import_script(payload:dict,db:Session=Depends(get_db),user:User=Depends(require_user)):
    text=payload.get('text','')
    if not isinstance(text,str):raise HTTPException(status_code=400,detail='Screenplay must be text.')
    pid,warnings=data_or_error(create_project,db,user.id,text,str(payload.get('title') or 'Untitled Production'))
    return {'state':enriched(db,user.id,pid),'warnings':warnings}

@app.post('/api/scene')
def update_scene(payload:dict,db:Session=Depends(get_db),user:User=Depends(require_user)):
    pid=int(payload.get('project_id',0));sid=int(payload.get('scene_id',0))
    data_or_error(modify_scene,db,user.id,pid,sid,payload.get('changes',{}))
    return {'state':enriched(db,user.id,pid)}

@app.post('/api/cast')
def update_cast(payload:dict,db:Session=Depends(get_db),user:User=Depends(require_user)):
    pid=int(payload.get('project_id',0));sid=int(payload.get('scene_id',0))
    cids=[int(x) for x in payload.get('character_ids',[])]
    data_or_error(modify_cast,db,user.id,pid,sid,cids)
    return {'state':enriched(db,user.id,pid)}

@app.post('/api/settings')
def settings(payload:dict,db:Session=Depends(get_db),user:User=Depends(require_user)):
    pid=int(payload.get('project_id',0))
    data_or_error(modify_settings,db,user.id,pid,payload.get('settings',{}))
    return {'state':enriched(db,user.id,pid)}

@app.post('/api/metadata')
def metadata(payload:dict,db:Session=Depends(get_db),user:User=Depends(require_user)):
    pid=int(payload.get('project_id',0))
    data_or_error(add_metadata,db,user.id,pid,payload.get('kind'),str(payload.get('name','')))
    return {'state':enriched(db,user.id,pid)}

@app.post('/api/event')
def event(payload:dict,db:Session=Depends(get_db),user:User=Depends(require_user)):
    pid=int(payload.get('project_id',0))
    data_or_error(add_event,db,user.id,pid,int(payload.get('scene_id',0)),str(payload.get('prop','')),
                  str(payload.get('action','')),str(payload.get('character','GLOBAL')))
    return {'state':enriched(db,user.id,pid)}

@app.post('/api/delete_event')
def delete_event(payload:dict,db:Session=Depends(get_db),user:User=Depends(require_user)):
    pid=int(payload.get('project_id',0))
    data_or_error(remove_event,db,user.id,pid,int(payload.get('event_id',0)))
    return {'state':enriched(db,user.id,pid)}

@app.post('/api/schedule')
def schedule_project(payload:dict,db:Session=Depends(get_db),user:User=Depends(require_user)):
    pid=int(payload.get('project_id',0))
    return {'state':data_or_error(schedule,db,user.id,pid,bool(payload.get('replan')))}

@app.post('/api/benchmark')
def benchmark(payload:dict,db:Session=Depends(get_db),user:User=Depends(require_user)):
    pid=int(payload.get('project_id',0))
    data_or_error(owned_project,db,user.id,pid)
    sizes=payload.get('sizes',[10,20,40]);seeds=payload.get('seeds',[11,23])
    if not isinstance(sizes,list) or not isinstance(seeds,list) or len(sizes)>3 or len(seeds)>4 or not seeds:
        raise HTTPException(status_code=400,detail='Invalid benchmark parameters.')
    if any(type(x)!=int or x not in (10,20,40) for x in sizes):
        raise HTTPException(status_code=400,detail='Supported scene counts: 10, 20, 40.')
    if any(type(x)!=int or abs(x)>100000 for x in seeds):
        raise HTTPException(status_code=400,detail='Invalid random seeds.')
    seconds=max(1,min(3,int(payload.get('max_seconds',1))))
    return {'rows':run_experiments(tuple(sizes),tuple(seeds),seconds),
            'note':'Synthetic data and fixed seeds; not real-world production measurements.'}

@app.delete('/api/projects/{project_id}')
def delete_owned_project(project_id:int,db:Session=Depends(get_db),user:User=Depends(require_user)):
    data_or_error(delete_project,db,user.id,project_id)
    return {'ok':True}


def report_pdf(project:dict):
    from reportlab.pdfgen.canvas import Canvas
    from reportlab.lib.pagesizes import A4
    b=io.BytesIO();c=Canvas(b,pagesize=A4);w,h=A4
    def txt(x,y,s,size=10):
        s=str(s).encode('latin-1','replace').decode('latin-1')
        c.setFillColorRGB(.1,.16,.22);c.setFont('Helvetica',size);c.drawString(x,y,s[:100])
    txt(45,h-58,'SCENEGRAPH AI / PRODUCTION PLAN',13)
    txt(45,h-86,project['title'][:60],18)
    txt(45,h-110,'Generated from authenticated, persisted production data.',9)
    r=project['schedules'].get('optimized')
    if r:
        txt(45,h-143,'Solver: '+r['method']+' | Status: '+r['status'])
        m=r.get('metrics',{})
        txt(45,h-162,f"Production days: {m.get('production_days','–')}  |  Location transitions: {m.get('location_changes','–')}")
        scenes={s['scene_id']:s for s in project['scenes']}
        y=h-200
        for a in sorted(r.get('assignments',[]),key=lambda x:(x['day'],x['start_slot'])):
            if y<55:c.showPage();y=h-65
            scene=scenes[a['scene_id']]
            minutes=8*60+a['start_slot']*30
            txt(45,y,f"D{a['day']+1}  {minutes//60:02}:{minutes%60:02}   S{scene['script_order']:02}   {scene['heading'][:68]}",9)
            y-=19
    txt(45,30,'Planning estimate — verify availability, safety and on-site requirements.',8)
    c.save();return b.getvalue()

@app.get('/api/export')
def export(project_id:int,format:str='csv',db:Session=Depends(get_db),user:User=Depends(require_user)):
    p=data_or_error(enriched,db,user.id,project_id)
    if format=='json':
        import json
        return Response(json.dumps(p,indent=2).encode('utf8'),media_type='application/json',
                        headers={'Content-Disposition':'attachment; filename="scenegraph_project.json"'})
    if p['schedule_stale']:
        raise HTTPException(status_code=409,detail='The saved schedule is outdated. Replan before exporting.')
    assignments=p['schedules'].get('optimized',{}).get('assignments',[])
    if not assignments:raise HTTPException(status_code=400,detail='Generate a feasible schedule before exporting.')
    if format=='pdf':
        return Response(report_pdf(p),media_type='application/pdf',
                        headers={'Content-Disposition':'attachment; filename="scenegraph_production_report.pdf"'})
    if format=='csv':
        out=io.StringIO();writer=csv.writer(out)
        writer.writerow(['Scene','Heading','Day','Start Slot','End Slot','Location'])
        scenes={s['scene_id']:s for s in p['scenes']}
        for a in assignments:
            s=scenes[a['scene_id']];writer.writerow([s['script_order'],s['heading'],a['day']+1,a['start_slot'],a['end_slot'],s['location']])
        return Response(out.getvalue().encode('utf-8-sig'),media_type='text/csv',
                        headers={'Content-Disposition':'attachment; filename="scenegraph_schedule.csv"'})
    raise HTTPException(status_code=400,detail='Unsupported export format.')

@app.get('/')
def index():return FileResponse(FRONT/'index.html',media_type='text/html')

@app.get('/{filename}')
def assets(filename:str):
    if filename not in {'index.html','app.js','styles.css','favicon.svg','config.js'}:
        raise HTTPException(status_code=404)
    return FileResponse(FRONT/filename)
