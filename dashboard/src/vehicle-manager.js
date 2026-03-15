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
    const grouped = new Map();

    for (const vehicle of msg.vehicles) {
      const gid = vehicle.global_id;
      if (!grouped.has(gid)) grouped.set(gid, []);
      grouped.get(gid).push(vehicle);
    }

    for (const [gid, group] of grouped.entries()) {
      const primary = group[group.length - 1];
      const cameraState =
        primary.camera_state ||
        [...new Set(group.map((vehicle) => vehicle.camera))].sort();
      const cameraStateLabel =
        primary.camera_state_label ||
        cameraState.map((camera) => camera.toUpperCase()).join(" + ");

      if (!this.vehicles.has(gid)) {
        this.vehicles.set(gid, {
          global_id: gid,
          camera: primary.camera,
          cameraState,
          cameraStateLabel,
          track_id: primary.track_id,
          class: primary.class,
          color: primary.color,
          footprint: primary.footprint,
          centroid: primary.centroid,
          hasCameraChanged: Boolean(primary.has_camera_changed),
          trail: [primary.centroid],
          lastSeen: timestamp,
        });
        continue;
      }

      const state = this.vehicles.get(gid);
      state.camera = primary.camera;
      state.cameraState = cameraState;
      state.cameraStateLabel = cameraStateLabel;
      state.track_id = primary.track_id;
      state.footprint = primary.footprint;
      state.centroid = primary.centroid;
      state.color = primary.color;
      state.hasCameraChanged = Boolean(primary.has_camera_changed);
      state.lastSeen = timestamp;

      state.trail.push(primary.centroid);
      if (state.trail.length > TRAIL_LENGTH) {
        state.trail.shift();
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

  /** Get one active vehicle state by global ID. */
  getByGlobalId(globalId) {
    return this.vehicles.get(globalId) || null;
  }

  /** Get count of active vehicles. */
  get count() {
    return this.vehicles.size;
  }
}
