// "HBO Max Amazon Channel" shows the same films as "HBO Max" (same rule as costs.catalog_name in Python).
export const catalogName = name => String(name).replace(/\s+Amazon channels?$/i, '');

// Plans of one provider are one service in the stats: "Netflix Standard with Ads" is Netflix.
// Rent stores and subscriptions stay apart (MagentaTV is not Magenta TV+), as do free and paid tiers of one name.
const PLAN_GROUPS = [[/^Netflix(\s|$)/i, 'Netflix'], [/^(Amazon )?Prime Video( with Ads)?$/i, 'Prime Video'], [/^RTL\+( Premium| Max)?$/i, 'RTL+']];
export function serviceGroup(name) {
  const base = catalogName(name).replace(/\s+(Apple TV|Amazon) channels?$/i, '');
  return (PLAN_GROUPS.find(([pattern]) => pattern.test(base)) || [null, base])[1];
}
