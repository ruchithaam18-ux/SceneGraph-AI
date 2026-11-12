"""Canonical identifiers and validation for parser output."""
import re

def canonical_name(value):
    return re.sub(r'\s+',' ',str(value).strip()).upper()

def normalize_script(parsed):
    chars={}; locs={}
    for s in parsed['scenes']:
        s['heading']=s['heading'].strip()
        s['location']=re.sub(r'\s+',' ',s['location'].strip())
        key=canonical_name(s['location']); locs.setdefault(key, len(locs)+1)
        s['location_id']=locs[key]
        out=[]
        for name in s.get('speakers',[]):
            key=canonical_name(name)
            if key and key not in out: out.append(key)
            if key: chars.setdefault(key,len(chars)+1)
        s['speakers']=out
        s['character_ids']=[chars[x] for x in out]
    parsed['characters']=[{'id':v,'name':k} for k,v in chars.items()]
    parsed['locations']=[{'id':v,'name':k} for k,v in locs.items()]
    return parsed
