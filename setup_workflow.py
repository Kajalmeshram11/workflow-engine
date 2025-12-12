import requests
import json

BASE_URL = "http://localhost:8000"

def create_code_review_workflow():
    workflow = {
        "name": "Code Review Workflow",
        "nodes": [
            {"name": "extract", "tool": "extract_functions", "params": {}},
            {"name": "complexity", "tool": "check_complexity", "params": {}},
            {"name": "issues", "tool": "detect_issues", "params": {}},
            {"name": "improve", "tool": "suggest_improvements", "params": {}}
        ],
        "edges": [
            {"from_node": "extract", "to_node": "complexity", "condition": None},
            {"from_node": "complexity", "to_node": "issues", "condition": None},
            {"from_node": "issues", "to_node": "improve", "condition": None},
            {"from_node": "improve", "to_node": "improve", "condition": "state.get('quality_score', 100) < 70 and state['_meta']['iterations'] < 3"}
        ]
    }
    
    response = requests.post(f"{BASE_URL}/graph/create", json=workflow)
    return response.json()

def run_code_review(graph_id: str, code: str):
    initial_state = {
        "code": code,
        "quality_threshold": 70
    }
    
    response = requests.post(
        f"{BASE_URL}/graph/run",
        json={"graph_id": graph_id, "initial_state": initial_state}
    )
    return response.json()

if __name__ == "__main__":
    print("Creating workflow...")
    result = create_code_review_workflow()
    graph_id = result['graph_id']
    print(f"Workflow created: {graph_id}")
    
    sample_code = """
def process_data(x, y, z, a, b, c):
    global counter
    try:
        result = x + y + z + a + b + c
        counter += 1
        return result
    except:
        pass

def another_function(data):
    for i in range(100):
        for j in range(100):
            for k in range(100):
                print(i, j, k)
"""
    
    print("\nRunning code review...")
    result = run_code_review(graph_id, sample_code)
    print(json.dumps(result, indent=2))