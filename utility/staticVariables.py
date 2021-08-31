# ConfD requests headers
confd_header_str = 'application/yang-data+json'
confd_content_type = {'Content-type': confd_header_str}
confd_accept = {'Accept': confd_header_str}
confd_headers = {**confd_content_type, **confd_accept}

# JSON headers
json_header_str = 'application/json'
json_content_type = {'Content-type': json_header_str}
json_accept = {'Accept': json_header_str}
json_headers = {**json_content_type, **json_accept}

date_format = '%Y-%m-%d_%H:%M:%S-UTC'
