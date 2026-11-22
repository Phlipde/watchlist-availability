// "Abroad on your services": where your own services have the film although they do not at home.
// Pure functions (node tests them); app.js fetches the data and wires the clicks.
import {escapeHtml} from './ui.js';
import {catalogName} from './catalog.js';

// Which countries to show first, with no setting: neighbours and the same language count, then the well-known
// VPN countries; tiny states go last. Only the regions the app offers have entries.
export const COUNTRY_CONFIG = {
  neighbors: {
    DE: ['AT', 'CH', 'NL', 'BE', 'FR', 'DK', 'PL', 'CZ', 'LU'],
    FR: ['BE', 'LU', 'DE', 'CH', 'IT', 'ES', 'MC', 'AD'],
    GB: ['IE', 'FR', 'BE', 'NL'],
    US: ['CA', 'MX'],
  },
  sameLanguage: {
    DE: ['AT', 'CH', 'LI'],
    FR: ['BE', 'CH', 'LU', 'MC', 'CA'],
    GB: ['US', 'IE', 'AU', 'NZ', 'CA'],
    US: ['GB', 'CA', 'AU', 'IE', 'NZ'],
  },
  popularVpn: ['US', 'GB', 'CA', 'NL', 'FR', 'JP', 'AU', 'ES', 'IT', 'SE'],
  tiny: ['AD', 'SM', 'VA', 'LI', 'MC', 'MT', 'GI', 'IM', 'JE', 'GG', 'FO', 'AX'],
};

export function countryScore(code, region, config = COUNTRY_CONFIG) {
  return (config.neighbors[region]?.includes(code) ? 3 : 0)
    + (config.sameLanguage[region]?.includes(code) ? 3 : 0)
    + (config.popularVpn.includes(code) ? 2 : 0)
    - (config.tiny.includes(code) ? 5 : 0);
}

// Best first; a tie is alphabetical by the shown name.
export function rankCountries(codes, region, nameOf = code => code, config = COUNTRY_CONFIG) {
  return [...codes].sort((a, b) => countryScore(b, region, config) - countryScore(a, region, config) || nameOf(a).localeCompare(nameOf(b)));
}

const WATCH = ['free', 'ads', 'flatrate'];
const HINT = {free: 'Free', ads: 'With ads'};

// byCountry: {country: {service: kinds}} → one row per own service that has the film abroad but not at home:
// [{service, countries: [codes, best first], hint}], the most countries first.
export function abroadRows(byCountry, own, region, nameOf = code => code, config = COUNTRY_CONFIG) {
  const mine = name => own.has(name) || own.has(catalogName(name));
  const watchKind = kinds => WATCH.find(kind => (kinds || []).includes(kind));
  const atHome = new Set(Object.entries(byCountry?.[region] || {}).filter(([, kinds]) => watchKind(kinds)).map(([name]) => catalogName(name)));
  const rows = new Map();
  for (const [country, offers] of Object.entries(byCountry || {})) {
    if (country === region) continue;
    for (const [name, kinds] of Object.entries(offers)) {
      const service = catalogName(name);
      const kind = watchKind(kinds);
      if (!kind || !mine(name) || atHome.has(service)) continue;
      const row = rows.get(service) || {service, kinds: new Map()};
      row.kinds.set(country, kind);
      rows.set(service, row);
    }
  }
  return [...rows.values()].map(row => {
    const kinds = [...new Set(row.kinds.values())];
    return {
      service: row.service,
      countries: rankCountries(row.kinds.keys(), region, nameOf, config),
      kinds: Object.fromEntries(row.kinds),
      hint: kinds.length === 1 ? HINT[kinds[0]] || '' : '',
    };
  }).sort((a, b) => b.countries.length - a.countries.length || a.service.localeCompare(b.service));
}

// For the grid of the remaining countries.
const EUROPE = 'AD AL AT AX BA BE BG BY CH CY CZ DE DK EE ES FI FO FR GB GG GI GR HR HU IE IM IS IT JE LI LT LU LV MC MD ME MK MT NL NO PL PT RO RS RU SE SI SK SM UA VA XK'.split(' ');
const AMERICAS = 'AG AR AW BB BO BR BS BZ CA CL CO CR CU DO EC GT GY HN HT JM MX NI PA PE PR PY SR SV TT US UY VE'.split(' ');
const ASIA_PACIFIC = 'AE AF AM AU AZ BD BH BN BT CN FJ GE HK ID IL IN IQ IR JO JP KG KH KR KW KZ LA LB LK MM MN MO MV MY NP NZ OM PG PH PK PS QA SA SG SY TH TJ TL TM TR TW UZ VN YE'.split(' ');
export function regionGroup(code) {
  return EUROPE.includes(code) ? 'Europe' : AMERICAS.includes(code) ? 'Americas' : ASIA_PACIFIC.includes(code) ? 'Asia / Pacific' : 'Rest of the world';
}

// [[group, codes]] in a fixed order, groups without a country left out.
export function groupByRegion(codes) {
  return ['Europe', 'Americas', 'Asia / Pacific', 'Rest of the world']
    .map(group => [group, codes.filter(code => regionGroup(code) === group)]).filter(([, list]) => list.length);
}

const flag = (code, name, serviceName, kind) => {
  const tip = `${name} · ${serviceName}${kind ? ` (${kind === 'flatrate' ? 'subscription' : kind === 'ads' ? 'with ads' : kind})` : ''}`;
  return `<span class="flag" role="img" tabindex="0" aria-label="${escapeHtml(tip)}" data-tip="${escapeHtml(tip)}"><img src="/static/flags/${escapeHtml(code.toLowerCase())}.svg" alt="" width="20" height="15" loading="lazy"></span>`;
};

// The block inside "Other services": a heading with the country count, the VPN note and one compact line per
// service (logo, three flags, "+N" for the rest). logoOf(name) → <img> or ''. nameOf(code) → country name.
export function abroadHtml(rows, {nameOf, logoOf}) {
  if (!rows.length) return '';
  const total = new Set(rows.flatMap(row => row.countries)).size;
  const table = rows.map(row => {
    const shown = row.countries.slice(0, 3);
    const more = row.countries.slice(3);
    const grid = more.length
      ? `<div class="flag-grid" hidden>${groupByRegion(more).map(([group, codes]) => `<section><h4>${group}</h4><ul>${codes.map(code => `<li>${flag(code, nameOf(code), row.service, row.kinds[code])}<span>${escapeHtml(nameOf(code))}</span></li>`).join('')}</ul></section>`).join('')}</div>`
      : '';
    const logo = logoOf(row.service, 'provider-logo-sm');
    return `<li class="abroad-row"><div class="abroad-line"><span class="abroad-service" title="${escapeHtml(row.service)}">${logo || escapeHtml(row.service)}</span><span class="abroad-flags">${shown.map(code => flag(code, nameOf(code), row.service, row.kinds[code])).join('')}${more.length ? `<button class="flag-more" type="button" aria-expanded="false">+${more.length} <i class="ti ti-chevron-right" aria-hidden="true"></i></button>` : ''}</span>${row.hint ? `<span class="abroad-hint">${row.hint}</span>` : ''}</div>${grid}</li>`;
  }).join('');
  return `<div class="abroad"><h3 class="offer-heading">Abroad on your services <span class="abroad-count">· ${total} ${total === 1 ? 'country' : 'countries'}</span></h3><p class="abroad-note">Needs a VPN or being in that country.</p><ul class="abroad-table">${table}</ul></div>`;
}

// The best country-and-service for one film, from the server's {service: {country: kind}}: the service with the
// most countries, its countries best first (the same order as in the drawer). null when there is nothing.
export function abroadForFilm(entry, region, nameOf = code => code, config = COUNTRY_CONFIG) {
  const rows = Object.entries(entry || {}).map(([service, byCountry]) => ({
    service,
    countries: rankCountries(Object.keys(byCountry), region, nameOf, config),
    kinds: byCountry,
  }));
  rows.sort((a, b) => b.countries.length - a.countries.length || a.service.localeCompare(b.service));
  return rows[0] || null;
}

// A copy of the film for the list when it is shown because of the abroad switch: only your services abroad count
// as its offers (so the cost filters sort it as free or subscription), and `abroadOnly` tells the card.
export function abroadFilm(film, entry) {
  const providers = {};
  for (const [service, byCountry] of Object.entries(entry || {})) providers[service] = [...new Set(Object.values(byCountry))];
  return {...film, providers, abroadOnly: true};
}
