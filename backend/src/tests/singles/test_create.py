from ontology_service import onto_service
from models import PolicyCreate
policy_data = PolicyCreate(**{
  "source_element_id": "module_2",
  "rule_type": "grade_required",
  "target_element_id": "test_1",
  "passing_threshold": 75.5,
  "author_id": "methodologist_ivanov"
})
print("Creating policy...")
print(onto_service.create_policy(policy_data))
