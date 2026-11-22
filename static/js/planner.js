// Planning with the data of the subscriptions page: what a set of services covers, the best set within a
// budget, a rotation (one service per month) and a what-if. Pure functions, tested with node.
//
// data: {weights: {filmKey: weight}, base: [filmKey] (free on your free services), services: {name: [filmKey]}}

export function coverage(selected, data) {
  const films = new Set(data.base || []);
  selected.forEach(name => (data.services[name] || []).forEach(key => films.add(key)));
  let weight = 0;
  films.forEach(key => { weight += data.weights[key] || 0; });
  const total = Object.keys(data.weights).length;
  return {films: films.size, weight, percent: total ? Math.round((100 * films.size) / total) : 0};
}

// The best sets of services that cost at most `budget` together: most weighted films first, cheaper on a tie.
// prices: {name: price}. Only services with a price take part; at most `max` of them (the biggest gains) are tried.
export function bestCombinations(data, prices, budget, {limit = 3, max = 14} = {}) {
  const names = Object.keys(prices)
    .filter(name => data.services[name] && prices[name] >= 0)
    .sort((a, b) => coverage([b], data).weight - coverage([a], data).weight || a.localeCompare(b))
    .slice(0, max);
  const results = [];
  for (let mask = 1; mask < 1 << names.length; mask += 1) {
    const chosen = names.filter((_, index) => mask & (1 << index));
    const cost = chosen.reduce((sum, name) => sum + prices[name], 0);
    if (cost > budget + 1e-9) continue;
    const covered = coverage(chosen, data);
    results.push({names: chosen, cost: Math.round(cost * 100) / 100, ...covered});
  }
  results.sort((a, b) => b.weight - a.weight || a.cost - b.cost || a.names.length - b.names.length);
  return results.slice(0, limit);
}

// One service a month: each month the one that adds the most weight to what is covered so far.
export function rotation(data, months = 3, exclude = []) {
  const taken = [];
  const plan = [];
  for (let month = 1; month <= months; month += 1) {
    const before = coverage(taken, data);
    let best = null;
    Object.keys(data.services).filter(name => !taken.includes(name) && !exclude.includes(name)).sort().forEach(name => {
      const gain = coverage([...taken, name], data);
      if (gain.weight > before.weight && (!best || gain.weight > best.after.weight)) best = {name, after: gain};
    });
    if (!best) break;
    plan.push({month, name: best.name, films: best.after.films - before.films, weight: best.after.weight - before.weight, percent: best.after.percent});
    taken.push(best.name);
  }
  return plan;
}
