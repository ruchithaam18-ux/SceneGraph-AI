from core.synthetic_data import generate_scenario
from core.analytics import compare_schedules
from core.experiments import run_experiments

def test_seeded_generator():
    a,_=generate_scenario(12,11);b,_=generate_scenario(12,11)
    assert a==b
    c,_=generate_scenario(12,12)
    assert a!=c
def test_compare_fail_not_presented_as_improvement():
    base={'status':'FAILED_FIRST_FIT','metrics':{},'violations':[]}
    opt={'status':'OPTIMAL','metrics':{'production_days':2},'violations':[]}
    result=compare_schedules(base,opt)
    assert not result['comparable'] and result['deltas']=={}
def test_single_experiment():
    rows=run_experiments((10,),(11,),1)
    assert len(rows)==1
    assert rows[0]['scenes']==10
    assert rows[0]['violations']==0
