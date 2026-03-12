"""
FPS Configuration Test

Tests the emulator at different FPS rates to validate:
1. 1 FPS (visualization rate)
2. 10 FPS (cross-camera system rate)
3. Performance and stability at each rate
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from emulator import config

# Test configurations
TEST_CONFIGS = {
    '1_FPS_VISUALIZATION': {
        'FPS': 1,
        'TIME_STEP': 1.0,
        'DESCRIPTION': 'Visualization rate (current default)'
    },
    '10_FPS_CROSS_CAMERA': {
        'FPS': 10,
        'TIME_STEP': 0.1,
        'DESCRIPTION': 'Cross-camera tracking rate'
    }
}


def print_current_config():
    """Print current emulator configuration."""
    print("="*70)
    print("📋 CURRENT EMULATOR CONFIGURATION")
    print("="*70)
    print(f"\n⏱️  Timing:")
    print(f"   FPS:              {config.FPS}")
    print(f"   TIME_STEP:        {config.TIME_STEP}s")
    print(f"   GLOBAL_START:     {config.GLOBAL_START_TIME}s")
    print(f"   GLOBAL_END_TIME:  {config.GLOBAL_END_TIME}s")
    print(f"   LOOP_ENABLED:     {config.LOOP_ENABLED}")

    print(f"\n🌐 Network Simulation:")
    print(f"   BASE_LATENCY:     {config.BASE_LATENCY_MS}ms")
    print(f"   JITTER:           {config.JITTER_MS}ms")
    print(f"   PACKET_LOSS:      {config.PACKET_LOSS_PROB*100}%")

    print(f"\n🎯 Hub Settings:")
    print(f"   WATERMARK:        {config.WATERMARK_MS}ms")
    print(f"   QUORUM:           {config.QUORUM} cameras")

    print(f"\n📹 Cameras:")
    print(f"   COUNT:            {len(config.CAMERAS)}")
    print(f"   IDs:              {', '.join(config.CAMERAS)}")

    print(f"\n⏰ Camera Time Offsets:")
    for camera, offset in config.CAMERA_TIME_OFFSETS.items():
        print(f"   {camera}:             {offset:.3f}s")

    print("\n" + "="*70)


def calculate_expected_metrics(fps: int, duration: int = 30):
    """Calculate expected metrics for a given FPS."""
    num_cameras = len(config.CAMERAS)

    # Expected packets
    frames_per_sec = fps
    total_frames = frames_per_sec * duration
    total_packets = total_frames * num_cameras

    # Expected losses (based on configured packet loss rate)
    expected_loss_rate = config.PACKET_LOSS_PROB
    expected_losses = int(total_packets * expected_loss_rate)
    expected_arrivals = total_packets - expected_losses

    # Expected decisions
    expected_decisions = total_frames

    # Expected decision distribution (rough estimates)
    # Assuming ~1% packet loss, most should be complete or partial
    expected_complete = int(expected_decisions * 0.85)  # ~85% complete
    expected_partial = int(expected_decisions * 0.10)   # ~10% partial
    expected_drop = expected_decisions - expected_complete - expected_partial

    return {
        'fps': fps,
        'duration': duration,
        'total_frames': total_frames,
        'total_packets': total_packets,
        'expected_arrivals': expected_arrivals,
        'expected_losses': expected_losses,
        'expected_loss_rate': expected_loss_rate * 100,
        'expected_decisions': expected_decisions,
        'decisions_per_sec': frames_per_sec,
        'packets_per_sec': frames_per_sec * num_cameras,
        'expected_complete': expected_complete,
        'expected_partial': expected_partial,
        'expected_drop': expected_drop
    }


def print_test_scenarios():
    """Print test scenarios for different FPS rates."""
    print("\n" + "="*70)
    print("🧪 TEST SCENARIOS")
    print("="*70)

    for name, cfg in TEST_CONFIGS.items():
        print(f"\n📊 {name}")
        print(f"   Description: {cfg['DESCRIPTION']}")
        print(f"   FPS: {cfg['FPS']}")
        print(f"   Time Step: {cfg['TIME_STEP']}s")

        metrics = calculate_expected_metrics(cfg['FPS'], duration=30)

        print(f"\n   Expected Metrics (30s test):")
        print(f"   • Total Frames:     {metrics['total_frames']}")
        print(f"   • Total Packets:    {metrics['total_packets']}")
        print(f"   • Packets/sec:      {metrics['packets_per_sec']}")
        print(f"   • Decisions/sec:    {metrics['decisions_per_sec']}")
        print(f"   • Expected Losses:  {metrics['expected_losses']} ({metrics['expected_loss_rate']:.1f}%)")

    print("\n" + "="*70)


def print_instructions():
    """Print instructions for testing at different FPS rates."""
    print("\n" + "="*70)
    print("📝 TESTING INSTRUCTIONS")
    print("="*70)

    print("\n🔧 To test at different FPS rates:")
    print("\n1️⃣  Test at 1 FPS (Visualization Rate)")
    print("   • Current default configuration")
    print("   • Run: python emulator/app.py")
    print("   • Run: python emulator/test_emulator.py")
    print("   • Expected: ~1 decision/sec, ~5 packets/sec")

    print("\n2️⃣  Test at 10 FPS (Cross-Camera Rate)")
    print("   • Edit emulator/config.py:")
    print("     - Change: FPS = 10")
    print("     - Change: TIME_STEP = 0.1")
    print("   • Run: python emulator/app.py")
    print("   • Run: python emulator/test_emulator.py")
    print("   • Expected: ~10 decisions/sec, ~50 packets/sec")

    print("\n3️⃣  Monitor Performance")
    print("   • Watch CPU and memory usage")
    print("   • Check for any lag or delays")
    print("   • Verify decision latencies stay reasonable")
    print("   • Test for at least 5 minutes at 10 FPS")

    print("\n⚠️  Important Notes:")
    print("   • Stop emulator (Ctrl+C) before changing config")
    print("   • Restart emulator after config changes")
    print("   • Frontend visualization may need adjustment for 10 FPS")
    print("   • Save test results for comparison")

    print("\n" + "="*70)


def main():
    """Main entry point."""
    print_current_config()
    print_test_scenarios()
    print_instructions()

    print("\n💡 TIP: Run this script anytime to see current configuration")
    print("         and expected test metrics.\n")


if __name__ == '__main__':
    main()
