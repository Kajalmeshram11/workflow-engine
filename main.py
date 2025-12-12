from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Dict, Any, List, Optional, Callable
import asyncio
import uuid
from datetime import datetime
import json

app = FastAPI(title="Workflow Engine API")

workflow_storage = {}
run_storage = {}
tool_registry = {}

class NodeConfig(BaseModel):
    name: str
    tool: str
    params: Optional[Dict[str, Any]] = {}

class EdgeConfig(BaseModel):
    from_node: str
    to_node: str
    condition: Optional[str] = None

class GraphCreateRequest(BaseModel):
    nodes: List[NodeConfig]
    edges: List[EdgeConfig]
    name: Optional[str] = "workflow"

class GraphRunRequest(BaseModel):
    graph_id: str
    initial_state: Dict[str, Any]

class WorkflowEngine:
    def __init__(self, graph_id: str, nodes: List[NodeConfig], edges: List[EdgeConfig]):
        self.graph_id = graph_id
        self.nodes = {node.name: node for node in nodes}
        self.edges = self._build_edge_map(edges)
        self.execution_log = []
        
    def _build_edge_map(self, edges: List[EdgeConfig]) -> Dict[str, List[tuple]]:
        edge_map = {}
        for edge in edges:
            if edge.from_node not in edge_map:
                edge_map[edge.from_node] = []
            edge_map[edge.from_node].append((edge.to_node, edge.condition))
        return edge_map
    
    def _evaluate_condition(self, condition: str, state: Dict[str, Any]) -> bool:
        if not condition:
            return True
        try:
            return eval(condition, {"state": state})
        except:
            return False
    
    def _get_next_node(self, current_node: str, state: Dict[str, Any]) -> Optional[str]:
        if current_node not in self.edges:
            return None
        
        for next_node, condition in self.edges[current_node]:
            if self._evaluate_condition(condition, state):
                return next_node
        return None
    
    async def execute(self, initial_state: Dict[str, Any], websocket=None) -> Dict[str, Any]:
        state = initial_state.copy()
        state['_meta'] = {
            'start_time': datetime.now().isoformat(),
            'iterations': 0,
            'max_iterations': 50
        }
        
        current_node = list(self.nodes.keys())[0] if self.nodes else None
        
        while current_node and state['_meta']['iterations'] < state['_meta']['max_iterations']:
            node_config = self.nodes[current_node]
            
            log_entry = {
                'node': current_node,
                'timestamp': datetime.now().isoformat(),
                'iteration': state['_meta']['iterations']
            }
            
            if node_config.tool in tool_registry:
                tool_func = tool_registry[node_config.tool]
                try:
                    result = await tool_func(state, **node_config.params)
                    state.update(result)
                    log_entry['status'] = 'success'
                    log_entry['output'] = result
                except Exception as e:
                    log_entry['status'] = 'error'
                    log_entry['error'] = str(e)
                    state['_error'] = str(e)
            else:
                log_entry['status'] = 'tool_not_found'
            
            self.execution_log.append(log_entry)
            
            if websocket:
                try:
                    await websocket.send_json(log_entry)
                except:
                    pass
            
            state['_meta']['iterations'] += 1
            current_node = self._get_next_node(current_node, state)
        
        state['_meta']['end_time'] = datetime.now().isoformat()
        state['_meta']['execution_log'] = self.execution_log
        
        return state

def register_tool(name: str, func: Callable):
    tool_registry[name] = func

@app.post("/graph/create")
async def create_graph(request: GraphCreateRequest):
    graph_id = str(uuid.uuid4())
    workflow_storage[graph_id] = {
        'nodes': request.nodes,
        'edges': request.edges,
        'name': request.name,
        'created_at': datetime.now().isoformat()
    }
    return {"graph_id": graph_id, "message": "Graph created successfully"}

@app.post("/graph/run")
async def run_graph(request: GraphRunRequest):
    if request.graph_id not in workflow_storage:
        raise HTTPException(status_code=404, detail="Graph not found")
    
    graph_data = workflow_storage[request.graph_id]
    run_id = str(uuid.uuid4())
    
    engine = WorkflowEngine(
        request.graph_id,
        [NodeConfig(**node.dict() if hasattr(node, 'dict') else node) for node in graph_data['nodes']],
        [EdgeConfig(**edge.dict() if hasattr(edge, 'dict') else edge) for edge in graph_data['edges']]
    )
    
    final_state = await engine.execute(request.initial_state)
    
    run_storage[run_id] = {
        'graph_id': request.graph_id,
        'state': final_state,
        'created_at': datetime.now().isoformat()
    }
    
    return {
        "run_id": run_id,
        "final_state": final_state,
        "execution_log": engine.execution_log
    }

@app.get("/graph/state/{run_id}")
async def get_run_state(run_id: str):
    if run_id not in run_storage:
        raise HTTPException(status_code=404, detail="Run not found")
    return run_storage[run_id]

@app.websocket("/ws/graph/run/{graph_id}")
async def websocket_run(websocket: WebSocket, graph_id: str):
    await websocket.accept()
    
    try:
        data = await websocket.receive_json()
        initial_state = data.get('initial_state', {})
        
        if graph_id not in workflow_storage:
            await websocket.send_json({"error": "Graph not found"})
            await websocket.close()
            return
        
        graph_data = workflow_storage[graph_id]
        engine = WorkflowEngine(
            graph_id,
            [NodeConfig(**node) for node in graph_data['nodes']],
            [EdgeConfig(**edge) for edge in graph_data['edges']]
        )
        
        final_state = await engine.execute(initial_state, websocket)
        await websocket.send_json({"type": "complete", "final_state": final_state})
        
    except WebSocketDisconnect:
        pass
    except Exception as e:
        await websocket.send_json({"error": str(e)})
    finally:
        await websocket.close()

@app.get("/health")
async def health_check():
    return {"status": "healthy", "graphs": len(workflow_storage), "runs": len(run_storage)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)