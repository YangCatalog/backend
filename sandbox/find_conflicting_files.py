import os
import json
import filecmp
from utility import yangParser

conflicting = []
fnames = {}
top = '/home/richard/code/yang'
for dirname, _, files in os.walk(top):
    dirname = os.path.join(top, dirname)
    for f in files:
        if f.endswith('.yang'):
            parsed = yangParser.parse(os.path.join(dirname, f))
            try:
                revision = parsed.search('revision')[0].arg
            except:
                revision = '1970-01-01'
            if f not in fnames:
                fnames[f] = {}
            if not revision in fnames[f]:
                fnames[f][revision] = os.path.join(dirname, f)
            else:
                if not filecmp.cmp(fnames[f][revision], os.path.join(dirname, f), shallow=False):
                    conflicting.append((fnames[f][revision], os.path.join(dirname, f)))

with open('conflicting.json', 'w') as f:
    json.dump(conflicting, f)
