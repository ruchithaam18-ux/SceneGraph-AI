import pytest
from pathlib import Path
from core.parser import parse_screenplay
from core.normalizer import normalize_script
BASE=Path(__file__).parents[1]
def test_twelve_scenes_and_verified_dialogue():
    d=normalize_script(parse_screenplay((BASE/'data/sample_script.fountain').read_text()))
    assert len(d['scenes'])==12
    assert {x['name'] for x in d['characters']}=={'MIRA','ARJUN','DEV','TARA'}
    assert d['scenes'][0]['speakers']==['MIRA','ARJUN']
    assert d['scenes'][0]['location']=='EDITING LAB'
    assert d['scenes'][0]['time_of_day']=='DAY'
def test_empty_and_missing_heading():
    with pytest.raises(ValueError,match='empty'):parse_screenplay('  ')
    with pytest.raises(ValueError,match='No Fountain'):parse_screenplay('There were no formatted scenes.')
def test_forced_scene_heading():
    parsed=normalize_script(parse_screenplay('.DREAM SEQUENCE\n\nNORA\nI remember.\n'))
    assert parsed['scenes'][0]['heading']=='DREAM SEQUENCE'
def test_title_not_confused_for_actor():
    parsed=normalize_script(parse_screenplay('Title: ANOTHER FILM\n\nINT. OFFICE - DAY\n\nTARA\nI can hear you.'))
    assert parsed['scenes'][0]['speakers']==['TARA']
def test_parser_size_limit():
    with pytest.raises(ValueError,match='1 MB'):parse_screenplay('x'*(1024*1024+1))

def test_two_manual_reference_sets_match():
    from core.parser_eval import evaluate
    outcome=evaluate()
    assert len(outcome)==2
    assert sum(x['expected_scene_count'] for x in outcome)==15
    assert all(x['fully_matched'] for x in outcome)
