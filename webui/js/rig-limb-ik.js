// Kéo đầu xương bằng góc xoay, giữ nguyên các vị trí local lúc gắn.
import * as THREE from 'three';
import { UNITY_NAME_OF_LABEL } from './skeleton-templates.js';

const EPSILON = 1e-8;
const pointIn = (space, world) => space ? space.worldToLocal(world.clone()) : world.clone();
const worldOf = (bone) => bone.getWorldPosition(new THREE.Vector3());
const boneChildren = (bone) => bone.children.filter((child) => child.isBone);
const nameOf = (bone) => UNITY_NAME_OF_LABEL[bone.name] ?? UNITY_NAME_OF_LABEL[bone.userData.label] ?? bone.name;

function aim(joint, child, target) {
  const from = child.position.clone().multiply(joint.scale).applyQuaternion(joint.quaternion);
  const to = target.clone().sub(joint.position);
  if (from.lengthSq() < EPSILON ** 2 || to.lengthSq() < EPSILON ** 2) return;
  joint.quaternion.premultiply(new THREE.Quaternion().setFromUnitVectors(from.normalize(), to.normalize())).normalize();
}

function singleLink(joint, end, handle = end) {
  const start = worldOf(handle), offset = worldOf(end).sub(start);
  return {
    joints: [joint],
    moveTo(target) {
      if (target.distanceToSquared(start) < EPSILON ** 2) return;
      aim(joint, end, pointIn(joint.parent, target.clone().add(offset)));
    },
  };
}

function bendDirection(first, axis, isLeg) {
  const bend = first.clone().addScaledVector(axis, -first.dot(axis));
  if (bend.lengthSq() > first.lengthSq() * 1e-8) return bend.normalize();
  // Tay/chân thẳng cần một hướng gập dự phòng để không đổi phía khi kéo qua trục.
  const fallback = Math.abs(axis.z) < 0.9 ? new THREE.Vector3(0, 0, isLeg ? 1 : -1) : new THREE.Vector3(0, 1, 0);
  return fallback.addScaledVector(axis, -fallback.dot(axis)).normalize();
}

function twoLinks(upper, lower, end, isLeg) {
  const space = upper.parent;
  const base = upper.position.clone();
  const mid = pointIn(space, worldOf(lower));
  const tip = pointIn(space, worldOf(end));
  const first = mid.clone().sub(base);
  const firstLength = first.length(), secondLength = tip.distanceTo(mid);
  if (firstLength < EPSILON || secondLength < EPSILON) return singleLink(lower, end);

  const axis = tip.clone().sub(base);
  if (axis.lengthSq() < EPSILON ** 2) axis.copy(first);
  axis.normalize();
  const bend = bendDirection(first, axis, isLeg);
  const tipOrientation = upper.quaternion.clone().multiply(lower.quaternion).multiply(end.quaternion);
  const inverseUpper = new THREE.Matrix4();

  return {
    joints: [upper, lower, end],
    moveTo(worldTarget) {
      const target = pointIn(space, worldTarget);
      if (target.distanceToSquared(tip) < EPSILON ** 2) return;
      const direction = target.sub(base);
      const distance = direction.length();
      if (distance > EPSILON) direction.divideScalar(distance); else direction.copy(axis);
      const reach = THREE.MathUtils.clamp(distance, Math.abs(firstLength - secondLength), firstLength + secondLength);
      // Hai cạnh cố định và khoảng cách tới đích xác định vị trí khuỷu/gối theo định lý cos.
      const along = reach > EPSILON ? (reach * reach + firstLength * firstLength - secondLength * secondLength) / (2 * reach) : 0;
      const height = Math.sqrt(Math.max(0, firstLength * firstLength - along * along));
      const pole = bend.clone().applyQuaternion(new THREE.Quaternion().setFromUnitVectors(axis, direction));
      aim(upper, lower, base.clone().addScaledVector(direction, along).addScaledVector(pole, height));
      inverseUpper.compose(upper.position, upper.quaternion, upper.scale).invert();
      aim(lower, end, base.clone().addScaledVector(direction, reach).applyMatrix4(inverseUpper));
      end.quaternion.copy(upper.quaternion).multiply(lower.quaternion).invert().multiply(tipOrientation).normalize();
    },
  };
}

function createJointMove(bone, allowed) {
  const parent = bone.parent;
  const child = boneChildren(bone)[0];
  if (!allowed.has(parent) || boneChildren(parent).length > 1) {
    // Khớp đầu nhánh (vd. vai) giữ chỗ, tay/nhánh xoay theo hướng kéo.
    return child && allowed.has(bone) ? singleLink(bone, child, bone) : null;
  }

  const name = nameOf(bone);
  const upper = parent.parent;
  const canUseUpper = allowed.has(upper) && boneChildren(upper).length === 1;
  if (/LowerArm$|LowerLeg$/i.test(name) || !canUseUpper || !allowed.has(bone)) return singleLink(parent, bone);
  // Tỉ lệ không đều trên chính một xương làm méo quỹ tích hai đoạn; vẫn có thể xoay một đoạn chính xác.
  const { x, y, z } = upper.scale;
  if (x <= EPSILON || Math.abs(x - y) > EPSILON || Math.abs(x - z) > EPSILON) return singleLink(parent, bone);
  return twoLinks(upper, parent, bone, /Foot$|Toes$/i.test(name));
}

/** Tạo thao tác cho một khớp; bên gọi khôi phục tư thế lúc bắt đầu trước mỗi lần moveTo. */
export function createBoneMove(bone, availableBones) {
  const allowed = availableBones instanceof Set ? availableBones : new Set(availableBones);
  const handleName = nameOf(bone);
  const endName = handleName.replace(/Hand_End$/, 'Hand').replace(/Toes$/, 'Foot');
  const end = bone.parent;
  if (endName !== handleName && allowed.has(end) && nameOf(end) === endName) {
    const move = createJointMove(end, allowed);
    if (move?.joints.length === 3) {
      // Kéo bàn tay hoặc mũi chân bằng cả tay/chân, giữ góc cổ tay/cổ chân.
      const offset = worldOf(end).sub(worldOf(bone));
      return { joints: move.joints, moveTo: (target) => move.moveTo(target.clone().add(offset)) };
    }
  }
  return createJointMove(bone, allowed);
}
