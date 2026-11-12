from __future__ import annotations
from pathlib import Path


def first_project(client, headers):
    r=client.get('/api/projects',headers=headers)
    assert r.status_code==200
    return r.json()['projects'][0]['id']


def test_home_and_health(client):
    assert client.get('/').status_code==200
    assert 'SCENEGRAPH' in client.get('/').text
    assert client.get('/config.js').status_code==200
    assert client.get('/api/health').json()['ok'] is True
    assert client.get('/etc/passwd').status_code==404


def test_login_protected(client):
    assert client.get('/api/projects').status_code==401
    assert client.post('/api/schedule',json={'project_id':1}).status_code==401
    assert client.get('/api/export?project_id=1&format=json').status_code==401


def test_registration_validation(client):
    result=client.post('/api/auth/register',json={'display_name':'Jane','email':'invalid','password':'a'*11})
    assert result.status_code==400
    result=client.post('/api/auth/register',json={'display_name':'Jane','email':'jane@example.test','password':'short'})
    assert result.status_code==400


def test_login_logout(client,alice):
    invalid=client.post('/api/auth/login',json={'email':'alice@example.test','password':'wrong'})
    assert invalid.status_code==401
    right=client.post('/api/auth/login',json={'email':'alice@example.test','password':'MyStrongPass2026!'})
    assert right.status_code==200
    assert client.get('/api/auth/me',headers=alice).json()['display_name']=='Alice Camera'
    assert client.post('/api/auth/logout',headers=alice).status_code==200
    assert client.get('/api/auth/me',headers=alice).status_code==401


def test_new_account_has_sample_with_real_sql_data(client,alice):
    pid=first_project(client,alice)
    state=client.get('/api/state',params={'project_id':pid},headers=alice).json()
    assert len(state['scenes'])==12
    assert len(state['characters'])>=3
    assert state['graph']['nodes']
    assert state['settings']['days']==4
    assert not state['schedule_stale']


def test_account_isolation(client,alice,bob):
    a=first_project(client,alice)
    b=first_project(client,bob)
    assert a!=b
    assert client.get('/api/state',params={'project_id':a},headers=bob).status_code==400
    assert client.post('/api/schedule',headers=bob,json={'project_id':a}).status_code==400
    assert client.get('/api/export',params={'project_id':a,'format':'json'},headers=bob).status_code==400
    assert client.delete('/api/projects/'+str(a),headers=bob).status_code==400
    assert client.get('/api/state',params={'project_id':a},headers=alice).status_code==200


def test_scheduling_replanning_staleness_and_exports(client,alice):
    pid=first_project(client,alice)
    rs=client.post('/api/schedule',headers=alice,json={'project_id':pid})
    assert rs.status_code==200,rs.text
    state=rs.json()['state'];opt=state['schedules']['optimized']
    assert opt['status'] in {'OPTIMAL','FEASIBLE','HEURISTIC_FEASIBLE'}
    assert opt['violations']==[]
    assert len(opt['assignments'])==12
    assert client.get('/api/export',params={'project_id':pid,'format':'csv'},headers=alice).status_code==200
    assert client.get('/api/export',params={'project_id':pid,'format':'pdf'},headers=alice).content.startswith(b'%PDF')
    assert client.get('/api/export',params={'project_id':pid,'format':'json'},headers=alice).json()['id']==pid
    chosen=opt['assignments'][0]
    sid=chosen['scene_id']; day=chosen['day']
    scene=next(s for s in state['scenes'] if s['scene_id']==sid)
    if scene['character_ids']:
        key=str(scene['character_ids'][0]);blocks=state['settings']['actor_blocks'];blocks[key]=[{'day':day,'start':0,'end':state['settings']['slots_per_day']}]
    else:
        key=str(scene['location_id']);blocks=state['settings']['location_blocks'];blocks[key]=[{'day':day,'start':0,'end':state['settings']['slots_per_day']}]
    change=client.post('/api/settings',headers=alice,json={'project_id':pid,'settings':state['settings']})
    assert change.status_code==200,change.text
    assert change.json()['state']['schedule_stale']
    assert client.get('/api/export',params={'project_id':pid,'format':'csv'},headers=alice).status_code==409
    replan=client.post('/api/schedule',headers=alice,json={'project_id':pid,'replan':True})
    assert replan.status_code==200,replan.text
    result=replan.json()['state']
    assert not result['schedule_stale']
    assert result['schedules']['optimized']['violations']==[]
    new_assign=next(a for a in result['schedules']['optimized']['assignments'] if a['scene_id']==sid)
    assert new_assign['day']!=day


def test_edit_persists_and_fails_safe(client,alice):
    pid=first_project(client,alice)
    state=client.get('/api/state',params={'project_id':pid},headers=alice).json()
    scene=state['scenes'][0]
    res=client.post('/api/scene',headers=alice,json={'project_id':pid,'scene_id':scene['scene_id'], 'changes':{'duration_slots':3}})
    assert res.status_code==200,res.text
    assert client.get('/api/state',params={'project_id':pid},headers=alice).json()['scenes'][0]['duration_slots']==3
    assert client.post('/api/scene',headers=alice,json={'project_id':pid,'scene_id':scene['scene_id'], 'changes':{'duration_slots':0}}).status_code==400


def test_import_graph_events_and_delete(client,alice):
    script='INT. LIBRARY - DAY\n\nMIRA\nWhere is it?\n\nEXT. PARK - NIGHT\n\nARI\nI lost it.\n\nINT. LIBRARY - NIGHT\n\nMIRA\nIt was here.\n'
    res=client.post('/api/import',headers=alice,json={'title':'Second Production','text':script})
    assert res.status_code==200,res.text
    data=res.json()['state'];pid=data['id'];assert len(data['scenes'])==3
    events=[(data['scenes'][0]['scene_id'],'ACQUIRE'),(data['scenes'][1]['scene_id'],'LOSE'),(data['scenes'][2]['scene_id'],'USE')]
    for sid,action in events:
        r=client.post('/api/event',headers=alice,json={'project_id':pid,'scene_id':sid,'prop':'KEY','action':action,'character':'MIRA'})
        assert r.status_code==200,r.text
    state=client.get('/api/state',params={'project_id':pid},headers=alice).json()
    assert len(state['continuity_warnings'])==1
    assert any(n['kind']=='prop' for n in state['graph']['nodes'])
    assert client.delete(f'/api/projects/{pid}',headers=alice).status_code==200
    assert client.get('/api/state',params={'project_id':pid},headers=alice).status_code==400


def test_cors_exact_origin(client):
    res=client.options('/api/projects',headers={'Origin':'https://approved.github.io','Access-Control-Request-Method':'GET'})
    assert res.headers.get('access-control-allow-origin')!='*'


def test_frontend_uses_relative_assets():
    html=Path('docs/index.html').read_text()
    assert 'href="./styles.css"' in html
    assert 'src="./app.js"' in html
    assert 'src="./config.js"' in html
    assert 'SCENEGRAPH_API_BASE' in Path('docs/config.js').read_text()
