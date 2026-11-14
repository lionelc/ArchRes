"""Diagnostic prompts for DEVIATIONS #13, arm D. Each one copies an original prompt and adds exactly one sentence that
states the premise the original leaves implicit. The system prompt is unchanged.

  python3 build_diag_prompts.py      writes prompts_diag/<id>.json

Expected class if a builder follows the stated premise (registered in #13):
  D_plant_mutable    fixable        the plant's duration is declared a setting, so F's least work is 0
  D_plant_frozen     architectural  the duration is declared frozen, so F costs 84.284 ms in every version (L = 0.53)
  D_cp512_ceiling    architectural  8 GB/s is declared a ceiling, so each forced transfer costs >= 67.1 ms
  D_cp512_noceiling  candidate      the 8 GB/s rates are declared achieved rates only; a certificate needs some other bound
"""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'prompts_diag')

PLANT_ANCHOR = 'is FROZEN and runs once in every invocation.'
CP_ANCHOR = 'and write() of a buffer into a new file at about 8 GB/s, on this file system.'

VARIANTS = [
    ('D_plant_mutable', 'P_sort_frozen_plant', PLANT_ANCHOR,
     ' The environment variable GAPCR_PLANT_US is a setting of Y\'s process: the contract freezes the code of F, not this variable.'),
    ('D_plant_frozen', 'P_sort_frozen_plant', PLANT_ANCHOR,
     ' The contract also freezes the variable GAPCR_PLANT_US = 84284: every admissible version of Y runs F with this value.'),
    ('D_cp512_ceiling', 'W_cp512', CP_ANCHOR,
     ' Take as given (envelope premise): no admissible calling context moves file data through fd_read or fd_write faster than 8 GB/s in either direction.'),
    ('D_cp512_noceiling', 'W_cp512', CP_ANCHOR,
     ' These rates were achieved with 1 MiB buffers; whether any admissible calling context is faster has not been measured.'),
]


def main():
    os.makedirs(OUT, exist_ok=True)
    for new_id, src, anchor, sentence in VARIANTS:
        pr = json.load(open(os.path.join(HERE, 'prompts', f'{src}.json')))
        assert pr['user'].count(anchor) == 1, (src, anchor)
        pr = dict(pr, gap=new_id, user=pr['user'].replace(anchor, anchor + sentence), derived_from=src, added_sentence=sentence)
        json.dump(pr, open(os.path.join(OUT, f'{new_id}.json'), 'w'), indent=1)
        print(new_id, 'from', src)


if __name__ == '__main__':
    main()
