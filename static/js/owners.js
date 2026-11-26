// Together: whose service is it? Pure functions, tested with node (tests/js/owners.test.mjs).
// serviceOwners comes from /api/together ({raw service name: [profile ids]}); members[0] is the active profile.
import {catalogName} from './catalog.js';

// The members who have the service, in member order: [{id, name, initial}]. "HBO Max" and its Amazon Channel are one.
export function ownersOf(service, serviceOwners = {}, members = []) {
  const wanted = catalogName(service);
  const ids = new Set(Object.entries(serviceOwners)
    .filter(([raw]) => catalogName(raw) === wanted)
    .flatMap(([, list]) => list));
  return members.filter(member => ids.has(member.id))
    .map(member => ({id: member.id, name: member.name, initial: ([...String(member.name).trim()][0] || '?').toUpperCase()}));
}

// The word before the service: "your", "Anna's", or '' when several share it (or nobody has it).
export function whose(owners, activeId) {
  if (owners.length !== 1) return '';
  return owners[0].id === activeId ? 'your' : `${owners[0].name}'s`;
}

// What a screen reader and the bubble say about it: "your service", "Anna's service", "shared: you, Anna".
export function ownerText(owners, activeId) {
  if (!owners.length) return '';
  if (owners.length === 1) return `${whose(owners, activeId)} service`;
  return `shared: ${owners.map(owner => (owner.id === activeId ? 'you' : owner.name)).join(', ')}`;
}
