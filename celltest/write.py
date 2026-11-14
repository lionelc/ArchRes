"""From celltest's generic records to the files gapgraph reads, and back.

  digest input (gapgraph.digest):   results_<state>.json = {'cells': {cell_id: {'status', 'equality', ..., 'verify':
                                    {engine: {...}}, 'timing': {'rounds': [[{'eng': engine key, 'med'}, ...]]}}}}
  paired input (gapgraph.rebuild):  {'knob': ..., 'cells': {cell_id: {'status', 'equality': {arm: 'equal'|'differ'},
                                    ..., 'verify': {arm: [sha256, rc]}, 'timing': {'rounds': [[{'w': arm, 'med'}]]}}}}
  replication input (celltest.sufficiency): {'meta', 'cells': {'<state>|<cell>|<setting>': {'state', 'cell', 'setting',
                                    'role', 'argv', 'verify', '<arms_equal_key>', '<ref_equal_key>', 'timing'}}}
The field order of every writer matches the files cu1's runners wrote, so a re-run writes the same layout."""
import json


def digest_cell(rec, engine_of):
    """engine_of: {arm name: engine key}, e.g. {'gnu': 'gnu', 'uu': 'uu'}; a two-arm ABBA record."""
    eq = 'equal' if all(v == 'equal' for v in rec['equal_to_ref'].values()) else 'differ'
    cell = {'status': 'ok' if eq == 'equal' else 'differ', 'equality': eq, 'family': rec['family'], 'factors': rec['factors'],
            'argv': rec['argv'], 'verify': {engine_of[a]: v for a, v in rec['verify'].items()},
            'timing': {'rounds': [[{'eng': engine_of[b['w']], 'med': b['med']} for b in rd] for rd in rec['timing']['rounds']]}}
    if eq != 'equal':
        cell['timing'] = {'rounds': []}
    return cell


def paired_cell(rec):
    eq = rec['equal_to_ref']
    return {'status': 'ok' if all(v == 'equal' for v in eq.values()) else 'differ', 'equality': eq, 'family': rec['family'],
            'factors': rec['factors'], 'verify': {a: [v['sha256'], v['rc']] for a, v in rec['verify'].items()}, 'timing': rec['timing']}


def rep_cell(rec, arms_equal_key='uu_arms_equal', ref_equal_key='equal_to_gnu', ref_group=None):
    """ref_group: the arm names that must all equal the reference for <ref_equal_key> (cu1: gd, ga and ud)."""
    ver = {a: [v['sha256'], v['rc']] for a, v in rec['verify'].items()}
    ref_ok = all(ver[a] == ver[ref_group[0]] for a in ref_group) if ref_group else all(v == 'equal' for v in rec['equal_to_ref'].values())
    return {'state': rec['state'], 'cell': rec['cell'], 'setting': rec['setting'], 'role': rec['role'], 'argv': rec['argv'],
            'verify': ver, arms_equal_key: all(rec['agree']), ref_equal_key: ref_ok, 'timing': rec['timing']}


def write_json(path, obj):
    with open(path, 'w') as f:
        json.dump(obj, f, indent=1)


def rounds_by_arm(cell):
    """{arm or engine key: [[block ns, block ns] per round]} from any of the three formats."""
    out = {}
    for rd in cell['timing']['rounds']:
        per = {}
        for b in rd:
            per.setdefault(b.get('w', b.get('eng')), []).append(b['med'])
        for k, v in per.items():
            out.setdefault(k, []).append(v)
    return out
