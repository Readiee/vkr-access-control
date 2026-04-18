import urllib.request
import json

data = {
  "student_id": "ivanov_1",
  "element_id": "test_1",
  "event_type": "graded",
  "grade": 85.0
}

req = urllib.request.Request(
    'http://localhost:8000/api/v1/events/progress', 
    data=json.dumps(data).encode('utf-8'), 
    headers={'Content-Type': 'application/json'}
)

try:
    with urllib.request.urlopen(req) as response:
        print("Status code:", response.status)
        print("Response:", response.read().decode('utf-8'))
except urllib.error.HTTPError as e:
    print("HTTPError:", e.code, e.reason)
    print(e.read().decode('utf-8'))
