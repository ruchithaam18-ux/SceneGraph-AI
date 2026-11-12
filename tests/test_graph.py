import json
import pytest
from pathlib import Path
from core.continuity import check_continuity
from core.graph_engine import build_scene_graph,graph_payload
from core.parser import parse_screenplay
from core.normalizer import normalize_script
BASE=Path(__file__).parents[1]
def fixture():return normalize_script(parse_screenplay((BASE/'data/minimal.fountain').read_text()))
def test_relationship_count():
    d=fixture();g=build_scene_graph(d)
    assert len(g.nodes())==3+2+2
    assert len(g.edges())==3+4
    assert graph_payload(d)['character_scene_counts']['NORA']==2
def test_invalid_character_reference():
    d=fixture();d['scenes'][0]['character_ids']=[999]
    with pytest.raises(ValueError,match='unknown character'):build_scene_graph(d)
@pytest.mark.parametrize('idx',range(6))
def test_continuity_reference_cases(idx):
    tests=json.loads((BASE/'data/continuity_examples.json').read_text())['cases']
    case=tests[idx];scenes=[{'scene_id':i,'script_order':i} for i in range(1,4)]
    assert len(check_continuity({'scenes':scenes,'events':case['events']}))==case['expected_warnings']
def test_story_order_not_event_insertion():
    d={'scenes':[{'scene_id':1,'script_order':1},{'scene_id':2,'script_order':2}],
       'events':[{'id':10,'scene_id':2,'prop':'KEY','character':'MIRA','action':'USE'},{'id':5,'scene_id':1,'prop':'KEY','character':'MIRA','action':'LOSE'}]}
    assert len(check_continuity(d))==1

def test_annotated_prop_nodes_are_source_linked():
    d=fixture();d['events']=[{'id':1,'scene_id':1,'prop':'KEY','action':'LOSE','character':'NORA'}]
    graph=build_scene_graph(d)
    assert graph.nodes['pKEY']['kind']=='prop'
    assert graph.edges['pKEY','s1']['kind']=='PROP_ANNOTATED_IN'
