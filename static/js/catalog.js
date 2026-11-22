// "HBO Max Amazon Channel" shows the same films as "HBO Max" (same rule as costs.catalog_name in Python).
export const catalogName = name => String(name).replace(/\s+Amazon channels?$/i, '');
