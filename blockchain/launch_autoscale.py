#!/usr/bin/env python3
"""
Auto-Scaling Blockchain Launcher for Wrath of Cali
- Spawns shards dynamically based on load
- Monitors TPS and scales up/down
- Supports infinite shards
"""

import subprocess
import requests
import time
import threading
import sys
import argparse
import signal

PORT_START = 5001
ROUTER_PORT = 6000
MAX_SHARDS = 10000
TPS_THRESHOLD = 15000  # Spawn new shard when avg TPS > this
LOW_TPS_THRESHOLD = 2000  # Stop shard when avg TPS < this
SCALE_COOLDOWN = 10  # Seconds between scale actions

class AutoScaler:
    def __init__(self, initial_shards=50, max_shards=10000, port_start=5001):
        self.initial_shards = initial_shards
        self.max_shards = max_shards
        self.port_start = port_start
        self.shards = {}  # port -> {pid, shard_id, tps, last_seen}
        self.running = True
        self.last_scale_time = 0
        self.lock = threading.Lock()
        
    def start_shard(self, shard_id):
        """Start a new shard process"""
        port = self.port_start + shard_id
        
        if shard_id >= self.max_shards:
            print(f"⚠️ Max shards reached ({self.max_shards})")
            return False
            
        if port in self.shards:
            return False  # Already running
            
        try:
            proc = subprocess.Popen(
                ['./super_node', '--port', str(port), '--shard', str(shard_id)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            
            self.shards[port] = {
                'pid': proc.pid,
                'shard_id': shard_id,
                'tps': 0,
                'last_seen': time.time()
            }
            
            print(f"  ✅ Spawned Shard {shard_id} on port {port} (PID {proc.pid})")
            return True
            
        except Exception as e:
            print(f"  ❌ Failed to spawn shard {shard_id}: {e}")
            return False
    
    def stop_shard(self, port):
        """Stop a shard process"""
        if port not in self.shards:
            return
            
        try:
            proc = self.shards[port]
            import os
            os.kill(proc['pid'], 9)
            print(f"  🛑 Stopped Shard {proc['shard_id']} on port {port}")
            del self.shards[port]
        except:
            pass
    
    def get_shard_health(self, port):
        """Get health metrics from a shard"""
        try:
            resp = requests.get(f'http://localhost:{port}/health', timeout=2)
            data = resp.json()
            
            pending = data.get('pending_txs', 0)
            height = data.get('height', 0)
            
            # Estimate TPS
            tps = pending / 2.0
            
            return {'tps': tps, 'height': height, 'pending': pending}
        except:
            return None
    
    def collect_metrics(self):
        """Collect metrics from all shards"""
        total_tps = 0
        active = 0
        dead_ports = []
        
        with self.lock:
            for port, info in self.shards.items():
                health = self.get_shard_health(port)
                
                if health:
                    info['tps'] = health['tps']
                    info['last_seen'] = time.time()
                    total_tps += health['tps']
                    active += 1
                else:
                    # No response - might be dead
                    if time.time() - info['last_seen'] > 10:
                        dead_ports.append(port)
        
        # Clean up dead shards
        for port in dead_ports:
            print(f"  ⚠️ Shard on port {port} appears dead, removing")
            with self.lock:
                del self.shards[port]
        
        avg_tps = total_tps / active if active > 0 else 0
        
        return {
            'active_shards': active,
            'total_tps': total_tps,
            'avg_tps': avg_tps,
            'total_pending': sum(self.get_shard_health(p).get('pending', 0) for p in self.shards if self.get_shard_health(p))
        }
    
    def evaluate_scaling(self, metrics):
        """Decide whether to scale up or down"""
        now = time.time()
        
        if now - self.last_scale_time < SCALE_COOLDOWN:
            return
        
        avg_tps = metrics['avg_tps']
        active = metrics['active_shards']
        
        # Scale up
        if avg_tps > TPS_THRESHOLD and active < self.max_shards:
            new_shard_id = active
            print(f"\n📈 High TPS ({avg_tps:.0f}) - scaling UP to {new_shard_id + 1} shards")
            self.start_shard(new_shard_id)
            self.last_scale_time = now
        
        # Scale down (only if we have enough shards)
        elif avg_tps < LOW_TPS_THRESHOLD and active > 20:
            # Find the highest port shard to stop
            with self.lock:
                if self.shards:
                    highest_port = max(self.shards.keys())
                    self.stop_shard(highest_port)
                    print(f"\n📉 Low TPS ({avg_tps:.0f}) - scaling DOWN to {active - 1} shards")
                    self.last_scale_time = now
    
    def start_router(self):
        """Start the mesh router"""
        try:
            proc = subprocess.Popen(
                ['./super_node', '--port', str(ROUTER_PORT), '--shard', '-1'],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            print(f"  ✅ Started router on port {ROUTER_PORT}")
            time.sleep(1)
        except Exception as e:
            print(f"  ⚠️ Router might already be running: {e}")
    
    def run(self):
        """Main run loop"""
        print(f"\n🕸️  Wrath of Cali - Auto-Scaling Network")
        print(f"   Initial shards: {self.initial_shards}")
        print(f"   Max shards: {self.max_shards}")
        print(f"   TPS threshold: {TPS_THRESHOLD}")
        print(f"   Port start: {self.port_start}")
        print()
        
        # Start router
        self.start_router()
        
        # Start initial shards
        print(f"Starting {self.initial_shards} initial shards...")
        for i in range(self.initial_shards):
            self.start_shard(i)
            time.sleep(0.05)  # Stagger startup
        print()
        
        # Main monitoring loop
        iteration = 0
        while self.running:
            time.sleep(3)
            
            metrics = self.collect_metrics()
            iteration += 1
            
            # Print status every 3 iterations
            if iteration % 3 == 0:
                print(f"\r  [{time.strftime('%H:%M:%S')}] Shards: {metrics['active_shards']:3d} | "
                      f"Total TPS: {metrics['total_tps']:7.0f} | "
                      f"Avg TPS: {metrics['avg_tps']:5.0f}   ", end='', flush=True)
            
            self.evaluate_scaling(metrics)
    
    def stop(self):
        """Stop all shards"""
        print("\n\nShutting down...")
        with self.lock:
            for port in list(self.shards.keys()):
                self.stop_shard(port)

def main():
    parser = argparse.ArgumentParser(description='Auto-scaling blockchain launcher')
    parser.add_argument('--shards', '-n', type=int, default=50, help='Initial shard count')
    parser.add_argument('--max', '-m', type=int, default=10000, help='Max shards')
    parser.add_argument('--port-start', '-p', type=int, default=5001, help='Starting port')
    args = parser.parse_args()
    
    PORT_START = args.port_start
    
    scaler = AutoScaler(
        initial_shards=args.shards,
        max_shards=args.max,
        port_start=args.port_start
    )
    
    # Handle signals
    def signal_handler(sig, frame):
        scaler.running = False
        scaler.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    scaler.run()

if __name__ == '__main__':
    main()
