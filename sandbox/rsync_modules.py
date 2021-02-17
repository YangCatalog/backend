import requests
from os import path

orgs = ['ieee', 'ietf']
for org in orgs:
    url = 'https://yangcatalog.org/api/search-filter'
    body = {"input": { "organization": org }}


    response = requests.post(url, json=body)
    print(response.status_code)
    resp_body = response.json()
    modules = resp_body['yang-catalog:modules']['module']

    for mod in modules:
        name = mod['name']
        revision = mod['revision']
        yang_file = '{}@{}.yang'.format(name, revision)
        if not path.exists("/var/yang/all_modules/{}".format(yang_file)):
            print(yang_file)
