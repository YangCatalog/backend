1. Set up a local OIDC OP server according to the instructions here: https://github.com/OpenIDC/pyoidc/blob/master/oidc_example/op2/README.md
2. Register a client according to the instructions with the following redirect_uris:
    - `http://localhost/api/admin/ping`
    - `http://localhost/api/admin/healthcheck`
3. In `config_simple.py`, set `ISSUER = 'http://172.17.0.1'`
4. Run the OP server on port 8040
5. Copy the `client_secret` and the `client_id` from the output to the `Secrets-Section` of the yangcatalog.conf file
6. In the `Web-Section` of yangcatalog.conf, set `ip=localhost` and `issuer=http://172.17.0.1:8040/`

Registered username password pairs are:
```json
{
    "diana": "krall",
    "babs": "howes",
    "upper": "crust"
}
```