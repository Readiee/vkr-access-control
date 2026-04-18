import urllib.request
import json

data = {
  "elements": [
    {
      "element_id": "module_1",
      "element_type": "Module",
      "parent_id": "course_python_101"
    },
    {
      "element_id": "lecture_1",
      "element_type": "Lecture",
      "parent_id": "module_1"
    },
    {
      "element_id": "test_1",
      "element_type": "Test",
      "parent_id": "module_1"
    }
  ]
}

req = urllib.request.Request(
    'http://localhost:8000/api/v1/courses/course_python_101/sync', 
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
