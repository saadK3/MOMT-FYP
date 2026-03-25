import * as THREE from "./vendor/three.module.js";
import {
  centroidToWorld,
  computeVehicleTransform,
  getVehicleHeight,
  mapPointToWorld,
} from "./coordinates-3d.js";
import {
  createVehicleModel,
  setVehicleHighlight,
} from "./vehicle-models-3d.js";

const EXPIRE_SECONDS = 5;
const TRAIL_LENGTH = 30;

export class VehicleManager3D {
  constructor(scene) {
    this.scene = scene;
    this.vehicles = new Map();
    this.selectedGlobalId = null;
  }

  update(message, options = {}) {
    const timestamp = message?.timestamp ?? 0;
    const showTrails = options.showTrails ?? true;
    const showLabels = options.showLabels ?? true;
    const grouped = new Map();

    for (const vehicle of message?.vehicles || []) {
      const list = grouped.get(vehicle.global_id) || [];
      list.push(vehicle);
      grouped.set(vehicle.global_id, list);
    }

    for (const [globalId, group] of grouped.entries()) {
      const primary = group[group.length - 1];
      if (!primary?.footprint || primary.footprint.length !== 8) {
        continue;
      }

      const transform = computeVehicleTransform(primary.footprint);
      const height = getVehicleHeight(primary.class);

      if (!this.vehicles.has(globalId)) {
        const color = hslaToHex(primary.color || "hsla(216, 82%, 59%, 0.85)");
        const model = createVehicleModel({
          width: transform.width,
          height,
          length: transform.length,
          vehicleClass: primary.class,
          color,
        });
        model.position.set(transform.centroid.x, 0, transform.centroid.z);
        model.rotation.y = transform.heading;
        tagGroup(model, globalId);
        this.scene.add(model);

        const trail = createTrail(color);
        this.scene.add(trail);

        const label = createLabel(`G${globalId}`);
        label.position.set(transform.centroid.x, height + 0.8, transform.centroid.z);
        this.scene.add(label);

        this.vehicles.set(globalId, {
          globalId,
          model,
          trail,
          label,
          labelHeight: height + 0.8,
          lastSeen: timestamp,
          path: [[transform.centroid.x, transform.centroid.z]],
          cameraState: primary.camera_state || [primary.camera],
          className: primary.class,
        });
      } else {
        const entry = this.vehicles.get(globalId);
        entry.model.position.set(transform.centroid.x, 0, transform.centroid.z);
        entry.model.rotation.y = transform.heading;
        entry.lastSeen = timestamp;
        entry.cameraState = primary.camera_state || [primary.camera];
        entry.path.push([transform.centroid.x, transform.centroid.z]);
        if (entry.path.length > TRAIL_LENGTH) {
          entry.path.shift();
        }
        entry.label.position.set(
          transform.centroid.x,
          entry.labelHeight,
          transform.centroid.z,
        );
      }
    }

    for (const [globalId, entry] of this.vehicles.entries()) {
      const isExpired = timestamp - entry.lastSeen > EXPIRE_SECONDS;
      if (isExpired) {
        disposeObject(entry.model);
        disposeLine(entry.trail);
        disposeSprite(entry.label);
        this.scene.remove(entry.model, entry.trail, entry.label);
        this.vehicles.delete(globalId);
        continue;
      }

      syncTrail(entry.trail, entry.path, showTrails);
      entry.label.visible = showLabels;
    }

    this.setSelectedGlobalId(options.selectedGlobalId ?? this.selectedGlobalId);
  }

  setSelectedGlobalId(globalId) {
    this.selectedGlobalId = globalId ?? null;

    for (const [vehicleId, entry] of this.vehicles.entries()) {
      const isSelected = this.selectedGlobalId === vehicleId;
      setVehicleHighlight(entry.model, isSelected);
      entry.label.scale.setScalar(isSelected ? 1.18 : 1);
      entry.trail.material.opacity = isSelected ? 0.95 : 0.42;
    }
  }

  focusTarget(globalId) {
    const entry = this.vehicles.get(globalId);
    if (!entry) {
      return null;
    }

    return {
      x: entry.model.position.x,
      y: 0,
      z: entry.model.position.z,
    };
  }

  pick(intersections) {
    for (const hit of intersections) {
      let current = hit.object;
      while (current) {
        if (Number.isInteger(current.userData.globalId)) {
          return current.userData.globalId;
        }
        current = current.parent;
      }
    }
    return null;
  }

  dispose() {
    for (const entry of this.vehicles.values()) {
      disposeObject(entry.model);
      disposeLine(entry.trail);
      disposeSprite(entry.label);
      this.scene.remove(entry.model, entry.trail, entry.label);
    }
    this.vehicles.clear();
  }
}

export function createJourneyObjects(scene, journey, options = {}) {
  const objects = [];
  const showLabels = options.showLabels ?? true;
  const showTrails = options.showTrails ?? true;

  for (const segment of journey?.segments || []) {
    const positions = [];
    for (const point of segment.points) {
      const mapped = mapPointToWorld(point.centroid);
      positions.push(mapped.x, 0.12, mapped.z);
    }

    if (positions.length >= 6) {
      const geometry = new THREE.BufferGeometry();
      geometry.setAttribute(
        "position",
        new THREE.Float32BufferAttribute(positions, 3),
      );

      const line = new THREE.Line(
        geometry,
        new THREE.LineBasicMaterial({
          color: cameraStateColor(segment.camera_state),
          transparent: true,
          opacity: showTrails ? 0.95 : 0.18,
        }),
      );
      scene.add(line);
      objects.push(line);
    }
  }

  for (const transition of journey?.transitions || []) {
    const marker = new THREE.Mesh(
      new THREE.OctahedronGeometry(0.75, 0),
      new THREE.MeshStandardMaterial({
        color: 0xf8fafc,
        emissive: new THREE.Color(0x334155),
        emissiveIntensity: 0.45,
        roughness: 0.25,
        metalness: 0.55,
      }),
    );
    const point = mapPointToWorld(transition.centroid);
    marker.position.set(point.x, 1.2, point.z);
    scene.add(marker);
    objects.push(marker);

    if (showLabels) {
      const label = createLabel(
        `${transition.from_camera_label} -> ${transition.to_camera_label}`,
        { width: 360, height: 84, fontSize: 24 },
      );
      label.position.set(point.x, 2.1, point.z);
      scene.add(label);
      objects.push(label);
    }
  }

  const pathPoints = journey?.path_points || [];
  if (pathPoints.length > 0) {
    const start = createPointMarker(pathPoints[0], 0x22c55e, "Start", showLabels);
    const end = createPointMarker(
      pathPoints[pathPoints.length - 1],
      0xef4444,
      "End",
      showLabels,
    );

    for (const object of start.concat(end)) {
      scene.add(object);
      objects.push(object);
    }
  }

  if (options.activeVehicle?.centroid) {
    const active = new THREE.Mesh(
      new THREE.TorusGeometry(1.4, 0.18, 12, 36),
      new THREE.MeshStandardMaterial({
        color: 0xffffff,
        emissive: new THREE.Color(0x60a5fa),
        emissiveIntensity: 0.65,
        roughness: 0.25,
        metalness: 0.8,
      }),
    );
    const point = centroidToWorld(options.activeVehicle.centroid);
    active.rotation.x = Math.PI / 2;
    active.position.set(point.x, 0.22, point.z);
    scene.add(active);
    objects.push(active);
  }

  return objects;
}

function createPointMarker(point, color, labelText, showLabel) {
  const objects = [];
  const mapped = mapPointToWorld(point.centroid);
  const sphere = new THREE.Mesh(
    new THREE.SphereGeometry(0.65, 18, 18),
    new THREE.MeshStandardMaterial({
      color,
      emissive: new THREE.Color(color).multiplyScalar(0.25),
      emissiveIntensity: 0.8,
      roughness: 0.25,
      metalness: 0.4,
    }),
  );
  sphere.position.set(mapped.x, 0.72, mapped.z);
  objects.push(sphere);

  if (showLabel) {
    const label = createLabel(`${labelText} ${point.timestamp.toFixed(1)}s`);
    label.position.set(mapped.x, 1.9, mapped.z);
    objects.push(label);
  }

  return objects;
}

function createTrail(color) {
  return new THREE.Line(
    new THREE.BufferGeometry(),
    new THREE.LineBasicMaterial({
      color,
      transparent: true,
      opacity: 0.42,
    }),
  );
}

function syncTrail(line, path, visible) {
  line.visible = visible && path.length > 1;
  if (path.length < 2) {
    return;
  }

  const positions = [];
  for (const point of path) {
    positions.push(point[0], 0.08, point[1]);
  }

  line.geometry.dispose();
  line.geometry = new THREE.BufferGeometry();
  line.geometry.setAttribute(
    "position",
    new THREE.Float32BufferAttribute(positions, 3),
  );
}

function createLabel(text, options = {}) {
  const width = options.width || 192;
  const height = options.height || 64;
  const fontSize = options.fontSize || 26;
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;

  const context = canvas.getContext("2d");
  context.fillStyle = "rgba(7, 12, 20, 0.88)";
  context.strokeStyle = "rgba(255, 255, 255, 0.14)";
  context.lineWidth = 2;
  roundRect(context, 2, 2, width - 4, height - 4, 12);
  context.fill();
  context.stroke();

  context.fillStyle = "#f8fafc";
  context.font = `600 ${fontSize}px Inter, sans-serif`;
  context.textAlign = "center";
  context.textBaseline = "middle";
  context.fillText(text, width / 2, height / 2);

  const texture = new THREE.CanvasTexture(canvas);
  texture.needsUpdate = true;
  const material = new THREE.SpriteMaterial({
    map: texture,
    transparent: true,
    depthWrite: false,
  });
  const sprite = new THREE.Sprite(material);
  sprite.scale.set(width / 42, height / 42, 1);
  sprite.userData.canvasTexture = texture;
  return sprite;
}

function roundRect(context, x, y, width, height, radius) {
  context.beginPath();
  context.moveTo(x + radius, y);
  context.lineTo(x + width - radius, y);
  context.quadraticCurveTo(x + width, y, x + width, y + radius);
  context.lineTo(x + width, y + height - radius);
  context.quadraticCurveTo(x + width, y + height, x + width - radius, y + height);
  context.lineTo(x + radius, y + height);
  context.quadraticCurveTo(x, y + height, x, y + height - radius);
  context.lineTo(x, y + radius);
  context.quadraticCurveTo(x, y, x + radius, y);
  context.closePath();
}

function tagGroup(group, globalId) {
  group.userData.globalId = globalId;
  group.traverse((child) => {
    child.userData.globalId = globalId;
  });
}

function cameraStateColor(cameraState) {
  if (!cameraState || cameraState.length === 0) {
    return 0x94a3b8;
  }

  if (cameraState.length > 1) {
    return 0xf59e0b;
  }

  const colorMap = {
    c001: 0x4ade80,
    c002: 0x38bdf8,
    c003: 0xf472b6,
    c004: 0xf59e0b,
    c005: 0xa78bfa,
  };
  return colorMap[cameraState[0]] || 0x94a3b8;
}

function hslaToHex(colorString) {
  const match = colorString.match(/hsla?\((\d+),\s*(\d+)%,\s*(\d+)%/i);
  if (!match) {
    return 0x3b82f6;
  }

  const h = Number(match[1]) / 360;
  const s = Number(match[2]) / 100;
  const l = Number(match[3]) / 100;
  const a = s * Math.min(l, 1 - l);
  const convert = (offset) => {
    const k = (offset + h * 12) % 12;
    const channel = l - a * Math.max(Math.min(k - 3, 9 - k, 1), -1);
    return Math.round(channel * 255);
  };

  return (convert(0) << 16) | (convert(8) << 8) | convert(4);
}

function disposeObject(object) {
  object.traverse((child) => {
    if (child.geometry) {
      child.geometry.dispose();
    }
    if (child.material) {
      if (Array.isArray(child.material)) {
        for (const material of child.material) {
          material.dispose();
        }
      } else {
        child.material.dispose();
      }
    }
  });
}

function disposeLine(line) {
  line.geometry.dispose();
  line.material.dispose();
}

function disposeSprite(sprite) {
  if (sprite.material?.map) {
    sprite.material.map.dispose();
  }
  sprite.material.dispose();
}
