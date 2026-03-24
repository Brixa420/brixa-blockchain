"""Agent prompt queue for Dev Studio"""
import json
import os
import time
from datetime import datetime

QUEUE_FILE = "/Users/laura/.openclaw/workspace/wrath-of-cali/blockchain/agent_queue.json"

def init_queue():
    if not os.path.exists(QUEUE_FILE):
        with open(QUEUE_FILE, 'w') as f:
            json.dump({"pending": [], "completed": []}, f)

def add_prompt(agent: str, task: str, prompt_type: str = "single"):
    """Add a prompt to the queue"""
    init_queue()
    with open(QUEUE_FILE, 'r') as f:
        queue = json.load(f)
    
    entry = {
        "id": f"{int(time.time())}_{agent}",
        "agent": agent,
        "task": task,
        "type": prompt_type,
        "timestamp": datetime.now().isoformat(),
        "status": "pending"
    }
    
    queue["pending"].append(entry)
    
    with open(QUEUE_FILE, 'w') as f:
        json.dump(queue, f, indent=2)
    
    return entry

def get_pending():
    """Get all pending prompts"""
    init_queue()
    with open(QUEUE_FILE, 'r') as f:
        queue = json.load(f)
    return queue.get("pending", [])

def mark_completed(prompt_id: str):
    """Mark a prompt as completed"""
    init_queue()
    with open(QUEUE_FILE, 'r') as f:
        queue = json.load(f)
    
    for p in queue.get("pending", []):
        if p["id"] == prompt_id:
            p["status"] = "completed"
            p["completed_at"] = datetime.now().isoformat()
            queue["completed"].append(p)
            queue["pending"].remove(p)
            break
    
    with open(QUEUE_FILE, 'w') as f:
        json.dump(queue, f, indent=2)

def clear_completed():
    """Clear completed prompts"""
    init_queue()
    with open(QUEUE_FILE, 'r') as f:
        queue = json.load(f)
    queue["completed"] = []
    with open(QUEUE_FILE, 'w') as f:
        json.dump(queue, f, indent=2)

if __name__ == "__main__":
    init_queue()
