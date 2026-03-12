

"""
Main entry point for the emulator


"""
import asyncio  # we're running multiple loops concurrently
import logging  # structured runtime logs
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from emulator import config
from emulator.json_reader import load_all_cameras
from emulator.camera_sender import CameraSender
from emulator.network_sim import NetworkSimulator
from emulator.hub import Hub
from emulator.websocket_server import WebSocketServer


def setup_logging():
    """Configure logging."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] [%(name)s] %(message)s',
        datefmt='%H:%M:%S'
    )
    # For anything whose logger name starts with emulator , we set the logging level to DEBUG to get deeper logs.
    logging.getLogger('emulator').setLevel(logging.DEBUG)


async def main():
    """Main entry point."""
    logger = logging.getLogger('App')
    logger.info("="*70)
    logger.info("MULTI-CAMERA EMULATOR STARTING")
    logger.info("="*70)

    # Load JSON data
    logger.info("Loading JSON data...")
    all_camera_data = load_all_cameras(
        config.JSON_DIR,
        config.CAMERAS,
        config.JSON_PATTERN
    )

    if not all_camera_data:
        logger.error("Failed to load camera data. Exiting.")
        return

    # Three Queues (THIS IS THE PIPELINE)
    sender_to_network_queue = asyncio.Queue()
    network_to_hub_queue = asyncio.Queue()
    hub_to_websocket_queue = asyncio.Queue()

    # Create camera senders
    camera_senders = []
    for camera_id in config.CAMERAS:
        if camera_id in all_camera_data:
            # Calculate local start time for this camera
            # Formula: local_start = global_start - offset
            # This ensures all cameras start at the same GLOBAL time
            camera_offset = config.CAMERA_TIME_OFFSETS.get(camera_id, 0.0)
            local_start_time = config.GLOBAL_START_TIME - camera_offset

            # Calculate local end time
            # Formula: local_end = global_end - offset
            # With global clock strategy, cameras naturally stop when their data ends
            local_end_time = config.GLOBAL_END_TIME - camera_offset

            logger.info(f"Camera {camera_id}: offset={camera_offset:.3f}s, "
                       f"local_start={local_start_time:.3f}s, "
                       f"local_end={local_end_time:.3f}s, "
                       f"global_start={config.GLOBAL_START_TIME:.3f}s, "
                       f"global_end={config.GLOBAL_END_TIME:.3f}s")

            sender = CameraSender(
                camera_id=camera_id,
                fps=config.FPS,
                detections_by_timestamp=all_camera_data[camera_id],
                start_time=local_start_time,  # Each camera starts at different local time
                end_time=local_end_time,  # Each camera ends at different local time (same global time)
                sentence_word=config.SENTENCE_WORDS.get(camera_id, ''),
                time_offset=camera_offset,  # Apply time offset for synchronization
                loop_enabled=config.LOOP_ENABLED  # Enable infinite looping
            )
            camera_senders.append(sender)
        else:
            logger.warning(f"No data for {camera_id}, skipping")
    # Log how many senders were created.
    logger.info(f"Created {len(camera_senders)} camera senders")

    # Create network simulator
    network_sim = NetworkSimulator(
        base_latency_ms=config.BASE_LATENCY_MS,
        jitter_ms=config.JITTER_MS,
        packet_loss_prob=config.PACKET_LOSS_PROB
    )

    # Create hub
    hub = Hub(
        camera_ids=config.CAMERAS,
        camera_time_offsets=config.CAMERA_TIME_OFFSETS,
        watermark_ms=config.WATERMARK_MS,   # how long to wait for late cameras.
        quorum=config.QUORUM,
        time_step=config.TIME_STEP
    )

    # Create WebSocket server
    ws_server = WebSocketServer(
        host=config.WS_HOST,
        port=config.WS_PORT,
        network_sim=network_sim  # Pass reference for dynamic config updates
    )

    # Create tasks
    tasks = []

    # Camera sender tasks
    for sender in camera_senders:
        tasks.append(asyncio.create_task(sender.run(sender_to_network_queue)))

    # Network simulator task
    tasks.append(asyncio.create_task(
        network_sim.run(sender_to_network_queue, network_to_hub_queue)
    ))

    # Hub task
    tasks.append(asyncio.create_task(
        hub.run(network_to_hub_queue, hub_to_websocket_queue)
    ))

    # WebSocket server task
    tasks.append(asyncio.create_task(
        ws_server.run(hub_to_websocket_queue)
    ))

    logger.info(f"All {len(tasks)} tasks created")
    logger.info("="*70)
    logger.info(f"WebSocket server: ws://{config.WS_HOST}:{config.WS_PORT}")
    logger.info(f"Emulating time range: global {config.GLOBAL_START_TIME}s - {config.GLOBAL_END_TIME}s")
    logger.info("Press Ctrl+C to stop")
    logger.info("="*70)

    # Wait for clients to connect before starting data transmission
    logger.info("⏳ Waiting 2 seconds for clients to connect...")
    await asyncio.sleep(2)
    logger.info("🚀 Starting data transmission...")
    logger.info("="*70)

    # Run all tasks
    try:
        await asyncio.gather(*tasks)
    except KeyboardInterrupt:
        logger.info("\nShutdown signal received. Stopping all tasks...")
    finally:
        # Cancel all tasks
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        logger.info("Shutdown complete")


if __name__ == '__main__':
    setup_logging()
    asyncio.run(main())
