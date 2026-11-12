"""Conservative Fountain screenplay parser. Unknown syntax creates warnings, not invented metadata."""
from __future__ import annotations
import re
from typing import Any

HEADING = re.compile(r"^(?:INT\.?/?EXT\.?|EXT\.?/?INT\.?|I/E\.?|INT\.|EXT\.|EST\.)\s+(.+)$", re.I)
TIME = re.compile(r"\s+[-–]\s+(DAY|NIGHT|DAWN|DUSK|MORNING|EVENING|SUNSET|SUNRISE|CONTINUOUS|LATER|SAME|AFTERNOON)(?:\s|$)", re.I)
CUE = re.compile(r"^[A-Z0-9][A-Z0-9 .#'\-()_/]*$", re.ASCII)
SUFFIX = re.compile(r"\s*\((?:V\.O\.|O\.S\.|O\.C\.|CONT'D|CONT’D|OFF|V/O|O/S)\)\s*$", re.I)
BAD_CUES = {'CUT TO:', 'FADE OUT:', 'DISSOLVE TO:', 'THE END', 'CONTINUED', 'FADE IN:'}


def _heading(line: str):
    if line.startswith('.') and len(line)>1 and line[1].isalnum():
        return line[1:].strip(), 'UNKNOWN'
    m = HEADING.match(line)
    if not m: return None
    rest=m.group(1).strip()
    return line, rest


def _normalize_location(heading:str):
    raw = re.sub(r"^(?:INT\.?/?EXT\.?|EXT\.?/?INT\.?|I/E\.?|INT\.|EXT\.|EST\.)\s*", "", heading, flags=re.I).lstrip('.')
    m = TIME.search(raw)
    when = m.group(1).upper() if m else 'UNSPECIFIED'
    location = raw[:m.start()].strip() if m else raw.strip()
    return location or 'UNSPECIFIED', when


def parse_screenplay(text: str) -> dict[str, Any]:
    if not isinstance(text,str): raise ValueError('Screenplay must be UTF-8 text')
    if len(text.encode('utf-8')) > 1024*1024: raise ValueError('Screenplay exceeds 1 MB upload limit')
    if not text.strip(): raise ValueError('Screenplay is empty')
    lines = text.replace('\r\n','\n').replace('\r','\n').split('\n')
    scenes=[]; warnings=[]; current=None; last_cue=None
    for line_no, raw in enumerate(lines,1):
        line=raw.strip()
        heading = _heading(line) if line else None
        if heading and (line.startswith('.') or (not line_no or line_no == 1 or not lines[line_no-2].strip())):
            heading_str=heading[0]
            loc, tod=_normalize_location(heading_str)
            current={'scene_id':len(scenes)+1,'script_order':len(scenes)+1,'heading':heading_str,'location':loc,'time_of_day':tod,'duration_slots':2,'body':'','speakers':[],'dialogue':[],'line_no':line_no}
            scenes.append(current)
            if loc=='UNSPECIFIED' or tod=='UNSPECIFIED': warnings.append({'line':line_no,'type':'metadata','message':f'Check location/time in scene {len(scenes)}'})
            last_cue=None; continue
        if not current:
            if line and not (line.startswith('Title:') or line.startswith('Author:') or line.startswith('Credit:') or line.startswith('Source:') or line.startswith('Draft date:') or line.startswith('Contact:')):
                if len(warnings)<24: warnings.append({'line':line_no,'type':'unassigned','message':'Content before first scene was not assigned'})
            continue
        current['body'] += raw + '\n'
        if not line: last_cue=None; continue
        if line.startswith('!') or line.startswith('>') or line.startswith('(') or line.endswith(':') or line.upper() in BAD_CUES: continue
        candidate=SUFFIX.sub('',line).strip()
        # A Fountain dialogue cue must be uppercase with a following nonempty line.
        if (CUE.fullmatch(line) and candidate and len(candidate)<=34 and len(candidate.split())<=5
            and not line[-1] in '.!?' and line.upper() not in BAD_CUES and line not in {'THE END','CUT TO'}):
            next_line=lines[line_no].strip() if line_no<len(lines) else ''
            if next_line and not _heading(next_line) and next_line.upper()!=next_line and not next_line.startswith('#'):
                if candidate not in current['speakers']: current['speakers'].append(candidate)
                last_cue=candidate
                continue
        if last_cue and not line.startswith('('):
            current['dialogue'].append({'speaker':last_cue,'text':line})
    if not scenes: raise ValueError('No Fountain scene headings found; start headings with INT. or EXT.')
    return {'title':'Untitled Screenplay','scenes':scenes,'warnings':warnings,'source_text':text}
