import urllib.request
import json

req = urllib.request.Request(
    'http://localhost:8000/api/v1/policies/policy_2e492307/toggle', 
    data=b'{"is_active": false}', 
    headers={'Content-Type': 'application/json'}, 
    method='PATCH'
)
res = urllib.request.urlopen(req)
print(res.read())

req2 = urllib.request.Request(
    'http://localhost:8000/api/v1/policies/policy_d90db47e', 
    method='DELETE'
)
res2 = urllib.request.urlopen(req2)
print(res2.read())
