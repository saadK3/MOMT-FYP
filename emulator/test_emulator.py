"""
Comprehensive Emulator Test Suite

Tests all components of the emulator system:
1. JSON data loading
2. Packet generation
3. Network simulation
4. Hub aggregation
5. WebSocket broadcasting
"""
import asyncio
import json
import time
import websockets
from pathlib import Path
from collections import defaultdict
from typing import Dict, List

# Test configuration
TEST_DURATION_SECONDS = 30
WS_URL = "ws://localhost:8765"


class EmulatorTestClient:
    """WebSocket client for testing emulator output."""

    def __init__(self):
        self.decisions = []
        self.packets_received = 0
        self.start_time = None
        self.metrics = {
            'total_decisions': 0,
            'complete_decisions': 0,
            'partial_decisions': 0,
            'drop_decisions': 0,
            'latencies': [],
            'camera_arrivals': defaultdict(int),
            'camera_losses': defaultdict(int)
        }

    async def connect_and_listen(self, duration: int):
        """Connect to WebSocket and collect data."""
        print(f"🔌 Connecting to {WS_URL}...")

        try:
            async with websockets.connect(WS_URL) as websocket:
                print("✅ Connected to emulator WebSocket")
                self.start_time = time.time()
                end_time = self.start_time + duration

                while time.time() < end_time:
                    try:
                        # Wait for message with timeout
                        message = await asyncio.wait_for(
                            websocket.recv(),
                            timeout=2.0
                        )

                        data = json.loads(message)
                        self.packets_received += 1

                        if data.get('type') == 'decision':
                            self._process_decision(data)
                            self._print_decision(data)

                    except asyncio.TimeoutError:
                        print("⏳ Waiting for data...")
                        continue
                    except json.JSONDecodeError as e:
                        print(f"❌ JSON decode error: {e}")
                        continue

                print(f"\n✅ Test completed. Collected {len(self.decisions)} decisions")

        except ConnectionRefusedError:
            print("❌ Connection refused. Is the emulator running?")
            print("   Run: python emulator/app.py")
            return False
        except Exception as e:
            print(f"❌ Error: {e}")
            return False

        return True

    def _process_decision(self, decision: Dict):
        """Process and store decision metrics."""
        self.decisions.append(decision)
        self.metrics['total_decisions'] += 1

        # Count decision types
        decision_type = decision.get('decision', 'unknown')
        if decision_type == 'complete':
            self.metrics['complete_decisions'] += 1
        elif decision_type == 'partial':
            self.metrics['partial_decisions'] += 1
        elif decision_type == 'drop':
            self.metrics['drop_decisions'] += 1

        # Track latencies
        latency = decision.get('latency_ms', 0)
        self.metrics['latencies'].append(latency)

        # Track camera arrivals and losses
        sentence_status = decision.get('sentence_status', {})
        for camera_id, status in sentence_status.items():
            if status.get('arrived'):
                self.metrics['camera_arrivals'][camera_id] += 1
            else:
                self.metrics['camera_losses'][camera_id] += 1

    def _print_decision(self, decision: Dict):
        """Print decision in real-time."""
        timestamp = decision.get('timestamp', 0)
        decision_type = decision.get('decision', 'unknown').upper()
        arrived = len(decision.get('arrived_cameras', []))
        missing = len(decision.get('missing_cameras', []))
        latency = decision.get('latency_ms', 0)

        # Color coding
        if decision_type == 'COMPLETE':
            icon = '✅'
        elif decision_type == 'PARTIAL':
            icon = '⚠️'
        else:
            icon = '❌'

        print(f"{icon} t={timestamp:.1f}s | {decision_type:8} | "
              f"{arrived}/{arrived+missing} cameras | {latency}ms")

    def print_summary(self):
        """Print comprehensive test summary."""
        if not self.decisions:
            print("\n❌ No decisions received. Emulator may not be running.")
            return

        duration = time.time() - self.start_time

        print("\n" + "="*70)
        print("📊 EMULATOR TEST SUMMARY")
        print("="*70)

        # Basic stats
        print(f"\n⏱️  Test Duration: {duration:.1f}s")
        print(f"📦 Total Decisions: {self.metrics['total_decisions']}")
        print(f"📈 Decisions/sec: {self.metrics['total_decisions']/duration:.2f}")

        # Decision distribution
        print(f"\n🎯 Decision Distribution:")
        total = self.metrics['total_decisions']
        print(f"   ✅ COMPLETE: {self.metrics['complete_decisions']} "
              f"({100*self.metrics['complete_decisions']/total:.1f}%)")
        print(f"   ⚠️  PARTIAL:  {self.metrics['partial_decisions']} "
              f"({100*self.metrics['partial_decisions']/total:.1f}%)")
        print(f"   ❌ DROP:     {self.metrics['drop_decisions']} "
              f"({100*self.metrics['drop_decisions']/total:.1f}%)")

        # Latency stats
        if self.metrics['latencies']:
            latencies = self.metrics['latencies']
            print(f"\n⏱️  Latency Statistics:")
            print(f"   Min:  {min(latencies)}ms")
            print(f"   Max:  {max(latencies)}ms")
            print(f"   Avg:  {sum(latencies)/len(latencies):.1f}ms")
            print(f"   Med:  {sorted(latencies)[len(latencies)//2]}ms")

        # Camera performance
        print(f"\n📹 Camera Performance:")
        cameras = ['c001', 'c002', 'c003', 'c004', 'c005']
        for camera in cameras:
            arrivals = self.metrics['camera_arrivals'][camera]
            losses = self.metrics['camera_losses'][camera]
            total_cam = arrivals + losses
            if total_cam > 0:
                success_rate = 100 * arrivals / total_cam
                print(f"   {camera}: {arrivals}/{total_cam} arrived "
                      f"({success_rate:.1f}% success)")

        # Packet loss estimation
        print(f"\n📉 Network Simulation:")
        total_expected = self.metrics['total_decisions'] * 5  # 5 cameras
        total_arrived = sum(self.metrics['camera_arrivals'].values())
        total_lost = sum(self.metrics['camera_losses'].values())
        loss_rate = 100 * total_lost / total_expected
        print(f"   Expected packets: {total_expected}")
        print(f"   Arrived packets:  {total_arrived}")
        print(f"   Lost packets:     {total_lost}")
        print(f"   Loss rate:        {loss_rate:.2f}%")

        print("\n" + "="*70)

    def validate_results(self) -> bool:
        """Validate test results against expected behavior."""
        print("\n🔍 VALIDATION CHECKS")
        print("="*70)

        all_passed = True

        # Check 1: Received decisions
        if self.metrics['total_decisions'] > 0:
            print("✅ Check 1: Received decisions from emulator")
        else:
            print("❌ Check 1: No decisions received")
            all_passed = False

        # Check 2: Decision rate (should be ~1 per second at 1 FPS)
        duration = time.time() - self.start_time
        expected_rate = 1.0  # 1 FPS
        actual_rate = self.metrics['total_decisions'] / duration
        if 0.8 <= actual_rate <= 1.2:  # Allow 20% tolerance
            print(f"✅ Check 2: Decision rate OK ({actual_rate:.2f} decisions/sec)")
        else:
            print(f"⚠️  Check 2: Decision rate unexpected ({actual_rate:.2f} vs {expected_rate:.2f} expected)")
            all_passed = False

        # Check 3: Packet loss rate (should be ~1%)
        total_expected = self.metrics['total_decisions'] * 5
        total_lost = sum(self.metrics['camera_losses'].values())
        loss_rate = 100 * total_lost / total_expected if total_expected > 0 else 0
        if 0 <= loss_rate <= 5:  # Allow up to 5% (configured is 1%)
            print(f"✅ Check 3: Packet loss rate OK ({loss_rate:.2f}%)")
        else:
            print(f"⚠️  Check 3: Packet loss rate high ({loss_rate:.2f}%)")

        # Check 4: All cameras active
        cameras = ['c001', 'c002', 'c003', 'c004', 'c005']
        all_cameras_active = all(
            self.metrics['camera_arrivals'][cam] > 0 for cam in cameras
        )
        if all_cameras_active:
            print("✅ Check 4: All 5 cameras active")
        else:
            print("❌ Check 4: Some cameras not sending data")
            all_passed = False

        # Check 5: Latency within bounds (should be ~60ms base + jitter)
        if self.metrics['latencies']:
            avg_latency = sum(self.metrics['latencies']) / len(self.metrics['latencies'])
            if 0 <= avg_latency <= 500:  # Reasonable bounds
                print(f"✅ Check 5: Latency within bounds ({avg_latency:.1f}ms avg)")
            else:
                print(f"⚠️  Check 5: Latency unusual ({avg_latency:.1f}ms avg)")

        # Check 6: Quorum decisions working
        if self.metrics['partial_decisions'] > 0 or self.metrics['complete_decisions'] > 0:
            print("✅ Check 6: Hub making decisions (complete/partial)")
        else:
            print("❌ Check 6: No complete/partial decisions (only drops)")
            all_passed = False

        print("="*70)

        if all_passed:
            print("\n🎉 ALL VALIDATION CHECKS PASSED!")
            print("✅ Emulator is ready for cross-camera integration")
        else:
            print("\n⚠️  SOME CHECKS FAILED")
            print("   Review the issues above before proceeding")

        return all_passed


async def main():
    """Run emulator test suite."""
    print("="*70)
    print("🧪 EMULATOR TEST SUITE")
    print("="*70)
    print(f"\nTest Configuration:")
    print(f"  Duration: {TEST_DURATION_SECONDS}s")
    print(f"  WebSocket: {WS_URL}")
    print(f"\n⚠️  Make sure the emulator is running:")
    print(f"     python emulator/app.py")
    print("\nStarting test in 3 seconds...")
    await asyncio.sleep(3)

    # Create test client
    client = EmulatorTestClient()

    # Run test
    success = await client.connect_and_listen(TEST_DURATION_SECONDS)

    if success:
        # Print summary
        client.print_summary()

        # Validate results
        client.validate_results()

        # Save results to file
        results_file = Path(__file__).parent / "test_results.json"
        with open(results_file, 'w') as f:
            json.dump({
                'timestamp': time.time(),
                'duration': TEST_DURATION_SECONDS,
                'metrics': {
                    'total_decisions': client.metrics['total_decisions'],
                    'complete': client.metrics['complete_decisions'],
                    'partial': client.metrics['partial_decisions'],
                    'drop': client.metrics['drop_decisions'],
                    'avg_latency': sum(client.metrics['latencies']) / len(client.metrics['latencies']) if client.metrics['latencies'] else 0,
                    'packet_loss_rate': 100 * sum(client.metrics['camera_losses'].values()) / (client.metrics['total_decisions'] * 5) if client.metrics['total_decisions'] > 0 else 0
                },
                'decisions': client.decisions[:100]  # Save first 100 decisions
            }, f, indent=2)

        print(f"\n💾 Results saved to: {results_file}")
    else:
        print("\n❌ Test failed. Check that emulator is running.")


if __name__ == '__main__':
    asyncio.run(main())
