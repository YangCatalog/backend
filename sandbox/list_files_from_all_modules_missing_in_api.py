import os

import requests

modules = requests.get(
    'https://yangcatalog.org:8888/api/config/catalog/modules',
    auth=('foo', 'bar'),
    headers={'Accept': 'application/vnd.yang.data+json', 'Content-type': 'application/vnd.yang.data+json'},
).json()
counter = 0
for filename in os.listdir('/var/yang/all_modules'):
    name = filename.split('@')[0]
    rev = filename.split('@')[1].split('.')[0]
    found = False
    for mod in modules['yang-catalog:modules']['module']:
        if mod['name'] == name and mod['revision'] == rev:
            found = True
            break
    if found:
        continue
    print('/var/yang/all_modules/' + filename)
    counter += 1
print(counter)
