import requests
# replace modules by modules that were removed
modules = [
{"name":"bbf-hardware-rpf-dpu-config", "revision":"2018-10-01", "organization":"bbf"},
{"name":"bbf-hardware-rpf-dpu-diagnostics", "revision":"2018-10-01", "organization":"bbf"},
{"name":"bbf-hardware-rpf-dpu-inventory", "revision":"2018-10-01", "organization":"bbf"},
{"name":"bbf-hardware-rpf-dpu-performance", "revision":"2018-10-01", "organization":"bbf"},
{"name":"bbf-hardware-rpf-dpu-state-diagnostics", "revision":"2018-10-01", "organization":"bbf"},
{"name":"bbf-hardware-rpf-dpu-state-inventory", "revision":"2018-10-01", "organization":"bbf"},
{"name":"bbf-hardware-rpf-dpu-state-performance", "revision":"2018-10-01", "organization":"bbf"},
{"name":"bbf-hardware-rpf-dpu-state-status", "revision":"2018-10-01", "organization":"bbf"},
{"name":"bbf-hardware-rpf-dpu-status", "revision":"2018-10-01", "organization":"bbf"}
]

yangcatalog_api_prefix = "https://yangcatalog.org/api/"
all_mods = requests.get('{}search/modules'.format(yangcatalog_api_prefix)).json()
for mod in modules:
    for existing_module in all_mods['module']:
        if existing_module.get('dependents') is not None:
            dependents = existing_module['dependents']
            for dep in dependents:
                if dep['name'] == mod['name'] and dep['revision'] == mod['revision']:
                    path = 'http://localhost:8008/api/config/catalog/modules/module/{},{},{}/dependents/{}'.format(
                                                           existing_module['name'], existing_module['revision'],
                                                           existing_module['organization'], dep['name'])
                    print('deleting on path {}'.format(path))
                    response = requests.delete(path, auth=("foo", 'bar'))
                    if response.status_code != 204:
                        print('Couldn\'t delete module on path {}. Error : {}'
                                     .format(path, response.text))
                    else:
                        print('removed succesfully status {}'.format(response.status_code)) 
