"""Reference-label evaluation of bundled demonstration Fountain scripts."""
import json
from pathlib import Path
from .parser import parse_screenplay
from .normalizer import normalize_script

ROOT=Path(__file__).resolve().parents[1]
def evaluate():
    spec=json.loads((ROOT/'data/parser_reference.json').read_text(encoding='utf-8'))
    results=[]
    for entry in spec['scripts']:
        parsed=normalize_script(parse_screenplay((ROOT/'data'/entry['file']).read_text(encoding='utf-8')))
        scenes=parsed['scenes'];n=len(entry['scene_headings'])
        headings=sum(a['heading']==expect for a,expect in zip(scenes,entry['scene_headings']))
        cast=sum(set(a['speakers'])==set(expect) for a,expect in zip(scenes,entry['speakers']))
        results.append({'script':entry['file'],'expected_scene_count':n,'extracted_scene_count':len(scenes),'heading_matches':headings,'speaker_set_matches':cast,'fully_matched':len(scenes)==n and headings==cast==n})
    return results
if __name__=='__main__':print(json.dumps(evaluate(),indent=2))
