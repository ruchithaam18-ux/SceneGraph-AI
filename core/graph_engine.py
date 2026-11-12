"""Scene-character-location knowledge graph; source IDs retained."""
try:
    import networkx as nx
except ImportError:
    nx = None

def build_scene_graph(data):
    if nx is None: raise RuntimeError('NetworkX not installed; pip install networkx')
    g=nx.Graph()
    ids={c['id'] for c in data['characters']}
    locids={loc['id'] for loc in data['locations']}
    for c in data['characters']:
        g.add_node('c'+str(c['id']),label=c['name'],kind='character')
    for loc in data['locations']:
        g.add_node('l'+str(loc['id']),label=loc['name'].title(),kind='location')
    for scene in data['scenes']:
        sid='s'+str(scene['scene_id'])
        g.add_node(sid,label='S'+str(scene['script_order']),kind='scene',heading=scene['heading'])
        if scene['location_id'] not in locids:raise ValueError('Scene references unknown location')
        g.add_edge(sid,'l'+str(scene['location_id']),kind='SET_AT')
        for cid in scene['character_ids']:
            if cid not in ids:raise ValueError('Scene references unknown character')
            g.add_edge(sid,'c'+str(cid),kind='HAS_SPEAKER')
    for e in data.get('events',[]):
        pid='p'+e['prop'].strip().upper().replace(' ','_')
        if not g.has_node(pid):g.add_node(pid,label=e['prop'],kind='prop')
        sid='s'+str(e['scene_id'])
        if not g.has_node(sid):raise ValueError('Event references unknown scene')
        g.add_edge(pid,sid,kind='PROP_ANNOTATED_IN')
    return g

def graph_payload(data):
    g=build_scene_graph(data)
    counts={ch['name']:len([n for n in g.neighbors('c'+str(ch['id'])) if n.startswith('s')]) for ch in data['characters']}
    loc_counts={loc['name']:len([n for n in g.neighbors('l'+str(loc['id'])) if n.startswith('s')]) for loc in data['locations']}
    return {'nodes':[{'id':k,**v} for k,v in g.nodes(data=True)],'edges':[{'source':a,'target':b,**v} for a,b,v in g.edges(data=True)],'character_scene_counts':counts,'location_scene_counts':loc_counts}
