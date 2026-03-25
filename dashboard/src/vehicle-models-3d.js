import * as THREE from "./vendor/three.module.js";

export function createVehicleModel({ width, height, length, vehicleClass, color }) {
  const group = new THREE.Group();
  const bodyColor = new THREE.Color(color);
  const darkTrim = bodyColor.clone().multiplyScalar(0.45);
  const glassColor = new THREE.Color(0x9fd5ff);

  switch (vehicleClass) {
    case "Sedan":
      buildSedan(group, width, height, length, bodyColor, darkTrim, glassColor);
      break;
    case "SUV / Hatchback":
      buildSUV(group, width, height, length, bodyColor, darkTrim, glassColor);
      break;
    case "Pickup / Minitruck":
      buildPickup(group, width, height, length, bodyColor, darkTrim, glassColor);
      break;
    case "Truck":
      buildTruck(group, width, height, length, bodyColor, darkTrim, glassColor);
      break;
    case "Bus":
      buildBus(group, width, height, length, bodyColor, darkTrim, glassColor);
      break;
    case "Motorcycle":
      buildMotorcycle(group, width, height, length, bodyColor, darkTrim);
      break;
    default:
      buildGeneric(group, width, height, length, bodyColor, darkTrim, glassColor);
  }

  group.traverse((child) => {
    if (child instanceof THREE.Mesh) {
      child.castShadow = true;
      child.receiveShadow = true;
      child.userData.baseEmissive = child.material.emissive
        ? child.material.emissive.clone()
        : new THREE.Color(0x000000);
    }
  });

  return group;
}

export function setVehicleHighlight(group, isHighlighted) {
  const highlightColor = new THREE.Color(0xffe082);

  group.traverse((child) => {
    if (!(child instanceof THREE.Mesh)) {
      return;
    }

    if ("emissive" in child.material) {
      if (isHighlighted) {
        child.material.emissive.copy(highlightColor);
        child.material.emissiveIntensity = 0.45;
      } else {
        child.material.emissive.copy(child.userData.baseEmissive || 0x000000);
        child.material.emissiveIntensity = 0;
      }
    }
  });
}

function buildGeneric(group, width, height, length, bodyColor, trimColor, glassColor) {
  const body = createMesh(
    new THREE.BoxGeometry(width * 0.92, height * 0.56, length),
    bodyMaterial(bodyColor),
  );
  body.position.y = height * 0.28;
  group.add(body);

  const roof = createMesh(
    new THREE.BoxGeometry(width * 0.72, height * 0.22, length * 0.52),
    bodyMaterial(trimColor),
  );
  roof.position.set(0, height * 0.67, -length * 0.04);
  group.add(roof);

  addGlassStrip(group, width, height, length, glassColor);
}

function buildSedan(group, width, height, length, bodyColor, trimColor, glassColor) {
  const lowerBody = createMesh(
    new THREE.BoxGeometry(width * 0.94, height * 0.44, length),
    bodyMaterial(bodyColor),
  );
  lowerBody.position.y = height * 0.22;
  group.add(lowerBody);

  const cabin = createMesh(
    new THREE.BoxGeometry(width * 0.72, height * 0.24, length * 0.52),
    bodyMaterial(trimColor),
  );
  cabin.position.set(0, height * 0.58, -length * 0.05);
  group.add(cabin);

  addGlassStrip(group, width, height, length, glassColor);
}

function buildSUV(group, width, height, length, bodyColor, trimColor, glassColor) {
  const body = createMesh(
    new THREE.BoxGeometry(width * 0.96, height * 0.58, length * 0.94),
    bodyMaterial(bodyColor),
  );
  body.position.y = height * 0.29;
  group.add(body);

  const roof = createMesh(
    new THREE.BoxGeometry(width * 0.88, height * 0.16, length * 0.76),
    bodyMaterial(trimColor),
  );
  roof.position.set(0, height * 0.66, -length * 0.04);
  group.add(roof);

  addGlassStrip(group, width, height, length, glassColor);
}

function buildPickup(group, width, height, length, bodyColor, trimColor, glassColor) {
  const cabLength = length * 0.42;
  const bedLength = length * 0.53;

  const cab = createMesh(
    new THREE.BoxGeometry(width * 0.92, height * 0.56, cabLength),
    bodyMaterial(bodyColor),
  );
  cab.position.set(0, height * 0.28, -length * 0.22);
  group.add(cab);

  const bed = createMesh(
    new THREE.BoxGeometry(width * 0.94, height * 0.26, bedLength),
    bodyMaterial(trimColor),
  );
  bed.position.set(0, height * 0.13, length * 0.18);
  group.add(bed);

  addGlassStrip(group, width, height, cabLength, glassColor, -length * 0.22);
}

function buildTruck(group, width, height, length, bodyColor, trimColor, glassColor) {
  const cab = createMesh(
    new THREE.BoxGeometry(width * 0.86, height * 0.56, length * 0.28),
    bodyMaterial(bodyColor),
  );
  cab.position.set(0, height * 0.28, -length * 0.34);
  group.add(cab);

  const cargo = createMesh(
    new THREE.BoxGeometry(width * 0.96, height * 0.66, length * 0.62),
    bodyMaterial(trimColor),
  );
  cargo.position.set(0, height * 0.33, length * 0.12);
  group.add(cargo);

  addGlassStrip(group, width, height, length * 0.28, glassColor, -length * 0.34);
}

function buildBus(group, width, height, length, bodyColor, trimColor, glassColor) {
  const body = createMesh(
    new THREE.BoxGeometry(width * 0.96, height * 0.82, length),
    bodyMaterial(bodyColor),
  );
  body.position.y = height * 0.41;
  group.add(body);

  const stripe = createMesh(
    new THREE.BoxGeometry(width * 0.99, height * 0.06, length * 0.98),
    bodyMaterial(trimColor),
  );
  stripe.position.y = height * 0.12;
  group.add(stripe);

  addGlassStrip(group, width, height, length * 0.92, glassColor);
}

function buildMotorcycle(group, width, height, length, bodyColor, trimColor) {
  const frame = createMesh(
    new THREE.BoxGeometry(Math.max(width * 0.3, 0.35), height * 0.32, length * 0.72),
    bodyMaterial(bodyColor),
  );
  frame.position.y = height * 0.22;
  group.add(frame);

  const seat = createMesh(
    new THREE.BoxGeometry(Math.max(width * 0.22, 0.26), height * 0.12, length * 0.2),
    bodyMaterial(trimColor),
  );
  seat.position.set(0, height * 0.42, 0);
  group.add(seat);

  addWheel(group, 0, -length * 0.33);
  addWheel(group, 0, length * 0.33);
}

function addGlassStrip(group, width, height, length, glassColor, zOffset = 0) {
  const glass = createMesh(
    new THREE.BoxGeometry(width * 0.64, height * 0.14, Math.max(length * 0.52, 0.8)),
    glassMaterial(glassColor),
  );
  glass.position.set(0, height * 0.58, zOffset);
  group.add(glass);
}

function addWheel(group, x, z) {
  const wheel = createMesh(
    new THREE.CylinderGeometry(0.18, 0.18, 0.12, 14),
    bodyMaterial(new THREE.Color(0x161616)),
  );
  wheel.rotation.z = Math.PI / 2;
  wheel.position.set(x, 0.18, z);
  group.add(wheel);
}

function bodyMaterial(color) {
  return new THREE.MeshStandardMaterial({
    color,
    roughness: 0.45,
    metalness: 0.35,
    emissive: new THREE.Color(0x000000),
  });
}

function glassMaterial(color) {
  return new THREE.MeshStandardMaterial({
    color,
    roughness: 0.1,
    metalness: 0.65,
    transparent: true,
    opacity: 0.72,
    emissive: new THREE.Color(0x000000),
  });
}

function createMesh(geometry, material) {
  return new THREE.Mesh(geometry, material);
}
