import requests

modules = requests.get(
    'https://yangcatalog.org:8888/api/config/catalog/modules',
    auth=('foo', 'bar'),
    headers={'Accept': 'application/vnd.yang.data+json', 'Content-type': 'application/vnd.yang.data+json'},
).json()
for mod in modules['yang-catalog:modules']['module']:
    if any(x.isupper() for x in mod['organization']):
        print(mod['name'] + ',' + mod['revision'] + ',' + mod['organization'])
