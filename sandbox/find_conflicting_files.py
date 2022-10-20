import filecmp
import json
import os

from utility.util import resolve_revision

conflicting = []
fnames = {}
top = '/backend/tests/resources/yangmodels/yang/'
for dirname, _, files in os.walk(top):
    dirname = os.path.join(top, dirname)
    for f in files:
        if f.endswith('.yang'):
            revision = resolve_revision(os.path.join(dirname, f))
            if f not in fnames:
                fnames[f] = {}
            if revision not in fnames[f]:
                fnames[f][revision] = os.path.join(dirname, f)
            else:
                if not filecmp.cmp(fnames[f][revision], os.path.join(dirname, f), shallow=False):
                    conflicting.append((fnames[f][revision], os.path.join(dirname, f)))

with open('conflicting.json', 'w') as f:
    json.dump(conflicting, f)
