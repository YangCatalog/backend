import os

import requests

modules = requests.get(
    'https://yangcatalog.org:8888/api/config/catalog/modules',
    auth=('foo', 'bar'),
    headers={'Accept': 'application/vnd.yang.data+json', 'Content-type': 'application/vnd.yang.data+json'},
).json()
counter = 0
module_set = {(module['name'], module['revision']) for module in modules}
for filename in os.listdir('/var/yang/all_modules'):
    name = filename.split('@')[0]
    revision = filename.split('@')[1].split('.')[0]
    if (name, revision) not in module_set:
        print('/var/yang/all_modules/' + filename)
        counter += 1
print(counter)
