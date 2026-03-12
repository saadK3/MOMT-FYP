/**
 * Vehicle Manager — tracks active vehicles and their recent trail history.
 */

const TRAIL_LENGTH = 30; // max centroid positions to keep per vehicle
const EXPIRE_SECONDS = 5; // remove if not seen for this long

export class VehicleManager {
  constructor() {
    /** @type {Map<number, VehicleState>} */
    this.vehicles = new Map();
  }

  /**
   * Process a tracking_update message.
   * @param {object} msg  tracking_update message from server
   */
  update(msg) {
    const timestamp = msg.timestamp;
    const seenIds = new Set();

    for (const v of msg.vehicles) {
      const gid = v.global_id;
      seenIds.add(gid);

      if (!this.vehicles.has(gid)) {
        // New vehicle
        this.vehicles.set(gid, {
          global_id: gid,
          camera: v.camera,
          track_id: v.track_id,
          class: v.class,
          color: v.color,
          footprint: v.footprint,
          centroid: v.centroid,
          trail: [v.centroid],
          lastSeen: timestamp,
        });
      } else {
        // Update existing
        const state = this.vehicles.get(gid);
        state.camera = v.camera;
        state.track_id = v.track_id;
        state.footprint = v.footprint;
        state.centroid = v.centroid;
        state.color = v.color;
        state.lastSeen = timestamp;

        // Append to trail (keep bounded)
        state.trail.push(v.centroid);
        if (state.trail.length > TRAIL_LENGTH) {
          state.trail.shift();
        }
      }
    }

    // Expire stale vehicles
    for (const [gid, state] of this.vehicles) {
      if (timestamp - state.lastSeen > EXPIRE_SECONDS) {
        this.vehicles.delete(gid);
      }
    }
  }

  /** Get array of active vehicle states. */
  getActive() {
    return Array.from(this.vehicles.values());
  }

  /** Get count of active vehicles. */
  get count() {
    return this.vehicles.size;
  }
}
