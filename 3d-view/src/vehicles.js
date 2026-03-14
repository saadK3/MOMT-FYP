/**
 * 3D Vehicle Manager — creates and updates Three.js cube meshes
 * from tracking_update WebSocket messages.
 */

import * as THREE from "three";
import {
  footprintToCorners,
  centroidToLocal,
  computeVehicleGeometry,
  getVehicleHeight,
} from "./coordinates.js";

const EXPIRE_SECONDS = 5;
const CUBE_COLOR = 0x3b82f6; // Uniform blue for all vehicles

export class VehicleManager3D {
  /**
   * @param {THREE.Scene} scene
   */
  constructor(scene) {
    this.scene = scene;
    /** @type {Map<number, {mesh: THREE.Mesh, lastSeen: number}>} */
    this.vehicles = new Map();
    this.material = new THREE.MeshStandardMaterial({
      color: CUBE_COLOR,
      roughness: 0.4,
      metalness: 0.3,
      transparent: true,
      opacity: 0.85,
    });
  }

  /**
   * Process a tracking_update message — create/update/remove vehicle cubes.
   * @param {object} msg
   */
  update(msg) {
    const timestamp = msg.timestamp;
    const seenIds = new Set();

    for (const v of msg.vehicles) {
      const gid = v.global_id;
      seenIds.add(gid);

      // Skip if footprint is invalid
      if (!v.footprint || v.footprint.length !== 8) continue;

      // Compute geometry from footprint
      const corners = footprintToCorners(v.footprint);
      const { width, length, heading } = computeVehicleGeometry(corners);
      const height = getVehicleHeight(v.class);
      const pos = centroidToLocal(v.centroid);

      if (this.vehicles.has(gid)) {
        // Update existing cube
        const entry = this.vehicles.get(gid);
        const mesh = entry.mesh;

        // Smoothly move toward target position
        mesh.position.x = pos.x;
        mesh.position.y = height / 2;
        mesh.position.z = pos.z;
        mesh.rotation.y = heading;

        // Update geometry if size changed significantly
        const geo = mesh.geometry;
        if (geo._w !== width || geo._l !== length || geo._h !== height) {
          mesh.geometry.dispose();
          mesh.geometry = new THREE.BoxGeometry(width, height, length);
          mesh.geometry._w = width;
          mesh.geometry._l = length;
          mesh.geometry._h = height;
        }

        entry.lastSeen = timestamp;
      } else {
        // Create new cube
        const geometry = new THREE.BoxGeometry(width, height, length);
        geometry._w = width;
        geometry._l = length;
        geometry._h = height;

        const mesh = new THREE.Mesh(geometry, this.material);
        mesh.position.set(pos.x, height / 2, pos.z);
        mesh.rotation.y = heading;
        mesh.castShadow = true;
        mesh.receiveShadow = true;

        // Store GID on the mesh for click detection later
        mesh.userData.globalId = gid;
        mesh.userData.vehicleClass = v.class;
        mesh.userData.camera = v.camera;

        this.scene.add(mesh);
        this.vehicles.set(gid, { mesh, lastSeen: timestamp });
      }
    }

    // Remove expired vehicles
    for (const [gid, entry] of this.vehicles) {
      if (timestamp - entry.lastSeen > EXPIRE_SECONDS) {
        this.scene.remove(entry.mesh);
        entry.mesh.geometry.dispose();
        this.vehicles.delete(gid);
      }
    }
  }

  /** Active count. */
  get count() {
    return this.vehicles.size;
  }
}
