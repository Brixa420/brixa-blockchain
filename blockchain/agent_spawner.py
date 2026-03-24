"""Real agent spawner using subprocess"""
import subprocess
import json
import os
import uuid
import threading

SPAWNED_AGENTS = {}

def spawn_agent_task(agent_name: str, task: str) -> dict:
    """Spawn a real agent using subprocess"""
    session_id = f"agent-{agent_name}-{uuid.uuid4().hex[:8]}"
    
    # Create a task file that the agent will pick up
    task_file = f"/Users/laura/.openclaw/workspace/wrath-of-cali/blockchain/tasks/{session_id}.json"
    os.makedirs(os.path.dirname(task_file), exist_ok=True)
    
    task_data = {
        "agent": agent_name,
        "task": task,
        "session_id": session_id,
        "status": "pending"
    }
    
    with open(task_file, 'w') as f:
        json.dump(task_data, f, indent=2)
    
    # Use Python to spawn agent in background - simple approach
    # The agent picks up the task from the file
    log_file = f"/Users/laura/.openclaw/workspace/wrath-of-cali/blockchain/tasks/{session_id}.log"
    
    cmd = [
        "python3", "-c",
        f"""
import json
import sys
sys.path.insert(0, '/Users/laura/.openclaw/workspace/wrath-of-cali/blockchain')
from agent_queue import add_prompt
add_prompt('{agent_name}', '{task.replace("'", "''")}', 'single')
print('Task queued: {agent_name}')
"""
    ]
    
    try:
        subprocess.Popen(cmd, stdout=open(log_file, 'w'), stderr=subprocess.STDOUT)
    except Exception as e:
        print(f"Failed to spawn: {e}")
    
    SPAWNED_AGENTS[session_id] = {
        "agent": agent_name,
        "task": task,
        "status": "running",
        "task_file": task_file
    }
    
    return {"session_id": session_id, "status": "spawned", "agent": agent_name}

def get_active_agents():
    """Get all active agents"""
    return SPAWNED_AGENTS
