import json
import os


loaded = dict()
with open('save.json', 'r') as f:
    loaded = json.load(f)
modules = dict()
for key, value in loaded.items():
    isfile = os.path.isfile(value)
    if isfile:
        modules[key] = value
    if not isfile:
        print('file {} does not exists'.format(value))

with open('save2.json', 'w') as f:
    json.dump(modules, f)
