import requests

modules = requests.get('https://yangcatalog.org:8888/api/config/catalog/modules', auth=("admin", 'Y@ng_adm1n->(paSS)'),headers={
                               'Accept': 'application/vnd.yang.data+json',
                               'Content-type': 'application/vnd.yang.data+json'}).json()
module_org = {}
for mod in modules['yang-catalog:modules']['module']:
    n = mod['name']
    r = mod['revision']
    o = mod['organization']
    if ("{}@{}".format(n, r) in module_org):
        module_org["{}@{}".format(n, r)].add(o)
    else:
        module_org["{}@{}".format(n, r)] = set()
        module_org["{}@{}".format(n, r)].add(o)
for key, val in module_org.items():
    if len(val) > 1:
        print(key)
        print(val)
        print('\n')
        
