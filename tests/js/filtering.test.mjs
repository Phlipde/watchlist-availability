import {test} from 'node:test';
import assert from 'node:assert/strict';

import {filmKey, bestRelaxation, countVisible, facetCounts, filterFilms, matchesSection, selectedChanges, selectedKinds, similarOnServices, sortFilms, ageMatches, sortRatings, comingSoon, elsewhereOnServices} from '../../static/js/filtering.js';

const baseFilters = {
  query: '', availability: 'all', kind: 'all', minRating: 0, minVotes: 0, genres: {include: [], exclude: []}, keyword: 'all', maxRuntime: 0, mode: 'any',
  yearFrom: 0, yearTo: 9999, media: 'all', change: 'all', minimumProviders: 0, favoriteStatus: 'all',
  sort: 'title', favoritesOnly: false,
};
const films = [
  {title: 'Alpha', director: 'Nolan', year: 2001, rating: 7.5, popularity: 12, vote_count: 1000, keywords: ['heist'], runtime: 100, genres: ['Drama'], providers: {Netflix: ['flatrate'], 'Apple TV Store': ['rent']}},
  {title: 'Beta', year: 1999, rating: 6, popularity: 30, vote_count: 100, runtime: 80, genres: ['Comedy'], providers: {Arte: ['free'], Netflix: ['flatrate']}},
  {title: 'Gamma', year: 2020, rating: 8, popularity: 20, vote_count: 10000, runtime: 130, genres: ['Drama'], providers: {'Apple TV Store': ['rent']}},
];
const unavailable = [{title: 'Delta', year: 2010}];
const context = (selected, favorites = new Map()) => ({selected: new Set(selected), favorites});
const titles = list => list.map(film => film.title);

test('films appear in each section with a selected provider', () => {
  const view = filterFilms(films, unavailable, baseFilters, context(['Netflix', 'Arte']));
  assert.deepEqual(titles(view.sections.Free), ['Beta']);
  assert.deepEqual(titles(view.sections.Paid), ['Alpha', 'Beta']);
});

test('visible count counts each available film once and skips unavailable films', () => {
  const view = filterFilms(films, unavailable, baseFilters, context(['Netflix', 'Arte']));
  assert.equal(view.visibleCount, 2);
  assert.deepEqual(titles(view.unavailable), ['Delta']);
});

test('offer type only counts offers from selected providers', () => {
  const rent = {...baseFilters, kind: 'rent'};
  assert.equal(filterFilms(films, [], rent, context(['Netflix'])).visibleCount, 0);
  assert.deepEqual(titles(filterFilms(films, [], rent, context(['Netflix', 'Apple TV Store'])).sections.Paid), ['Alpha', 'Gamma']);
  assert.deepEqual(selectedKinds(films[0], new Set(['Netflix'])), ['flatrate']);
});

test('offer type belongs to its section', () => {
  const free = {...baseFilters, kind: 'free'};
  assert.equal(matchesSection(films[1], 'Paid', free, context(['Arte', 'Netflix'])), false);
  assert.equal(matchesSection(films[1], 'Free', free, context(['Arte', 'Netflix'])), true);
});

test('unavailable films only show for matching availability and no offer type', () => {
  const ctx = context(['Netflix']);
  assert.equal(filterFilms(films, unavailable, {...baseFilters, availability: 'available'}, ctx).unavailable.length, 0);
  assert.equal(filterFilms(films, unavailable, {...baseFilters, availability: 'unavailable'}, ctx).unavailable.length, 1);
  assert.equal(filterFilms(films, unavailable, {...baseFilters, availability: 'unavailable'}, ctx).visibleCount, 0);
  assert.equal(filterFilms(films, unavailable, {...baseFilters, kind: 'flatrate'}, ctx).unavailable.length, 0);
});

test('match mode "all" needs every selected provider', () => {
  const all = {...baseFilters, mode: 'all'};
  assert.deepEqual(titles(filterFilms(films, [], all, context(['Netflix'])).sections.Paid), ['Alpha', 'Beta']);
  assert.equal(filterFilms(films, [], all, context(['Netflix', 'Apple TV Store'])).sections.Paid.length, 1);
  assert.equal(filterFilms(films, [], all, context([])).visibleCount, 0);
});

test('common filters', () => {
  const ctx = context(['Netflix', 'Arte', 'Apple TV Store']);
  const count = filters => filterFilms(films, [], {...baseFilters, ...filters}, ctx).visibleCount;
  assert.equal(count({query: 'alp'}), 1);
  assert.equal(count({minRating: 7}), 2);
  assert.equal(count({genres: {include: ['Drama'], exclude: []}}), 2);
  // Several genres: any of them; an excluded genre drops the film.
  assert.equal(count({genres: {include: ['Drama', 'Comedy'], exclude: []}}), 3);
  assert.equal(count({genres: {include: [], exclude: ['Drama']}}), 1);
  assert.equal(count({maxRuntime: 90}), 1);
  assert.equal(count({maxRuntime: 120}), 2);
  assert.equal(count({yearFrom: 2000, yearTo: 2010}), 1);
  assert.equal(count({minimumProviders: 2}), 2);
  assert.equal(count({minVotes: 1000}), 2);
  assert.equal(count({query: 'nolan'}), 1);
  assert.equal(count({keyword: 'heist'}), 1);
});

test('minimum providers only counts selected providers', () => {
  const count = (selected, minimumProviders) => filterFilms(films, [], {...baseFilters, minimumProviders}, context(selected)).visibleCount;
  // Alpha and Beta have two providers each, but only one of them is selected.
  assert.equal(count(['Netflix'], 2), 0);
  assert.equal(count(['Netflix', 'Arte'], 2), 1);
});

test('exclusive availability shows the films the server marked', () => {
  const marked = films.map((film, index) => ({...film, only_on_my_services: index === 0}));
  const view = filterFilms(marked, [], {...baseFilters, exclusive: true}, context(['Netflix', 'Arte']));
  assert.deepEqual(view.sections.Paid.map(film => film.title), ['Alpha']);
  assert.equal(view.visibleCount, 1);
});

test('favorites filter uses the status', () => {
  const favorites = new Map([['Alpha|2001', {status: 'watched'}], ['Beta|1999', {status: 'plan'}]]);
  const ctx = context(['Netflix', 'Arte'], favorites);
  const view = filterFilms(films, [], {...baseFilters, favoritesOnly: true, favoriteStatus: 'plan'}, ctx);
  assert.equal(view.visibleCount, 1);
  assert.deepEqual(titles(view.sections.Paid), ['Beta']);
});

test('change filter only counts changes on selected providers', () => {
  const changed = [{title: 'Alpha', year: 2001, providers: {Netflix: ['flatrate']}, provider_changes: {added: ['Netflix'], removed: ['MUBI']}}];
  const gone = [{title: 'Delta', year: 2010, providers: {}, provider_changes: {added: [], removed: ['Netflix']}}];
  const count = (change, selected) => {
    const view = filterFilms(changed, gone, {...baseFilters, change}, context(selected));
    return [view.visibleCount, view.unavailable.length];
  };
  assert.deepEqual(count('added', ['Netflix']), [1, 0]);
  assert.deepEqual(count('removed', ['Netflix']), [0, 1]);
  assert.deepEqual(count('removed', ['Netflix', 'MUBI']), [1, 1]);
  assert.deepEqual(selectedChanges(changed[0], new Set(['Arte'])), {added: [], removed: []});
  // Left the only selected provider but still runs elsewhere: shown under "removed" only.
  const moved = [{title: 'Moved', year: 2000, providers: {Arte: ['free']}, provider_changes: {added: [], removed: ['Netflix']}}];
  assert.equal(filterFilms(moved, [], baseFilters, context(['Netflix'])).visibleCount, 0);
  assert.equal(filterFilms(moved, [], {...baseFilters, change: 'removed'}, context(['Netflix'])).visibleCount, 1);
});

test('sorting breaks ties by title', () => {
  const list = [{title: 'b', year: 2000}, {title: 'a', year: 2000}, {title: 'c', year: 2010}];
  assert.deepEqual(titles(sortFilms(list, 'year-desc')), ['c', 'a', 'b']);
});

test('the eight sorts: priority, runtime, recently added, newly available, random', () => {
  const list = [
    {key: '1', title: 'Fav', letterboxd_rating: 3, rating: 6, runtime: 150, watchlist_position: 4},
    {key: '2', title: 'Top', letterboxd_rating: 4.5, rating: 8, runtime: 90, watchlist_position: 0, provider_changes: {added: ['Netflix']}},
    {key: '3', title: 'Mid', letterboxd_rating: 3.5, rating: 9, runtime: 120, watchlist_position: 2},
    {key: '4', title: 'None', rating: 7},
  ];
  assert.deepEqual(titles(sortFilms(list, 'priority', {favorites: new Map([['1', {}]])})), ['Fav', 'Top', 'Mid', 'None']);
  assert.deepEqual(titles(sortFilms(list, 'rating')), ['Mid', 'Top', 'None', 'Fav']);
  assert.deepEqual(titles(sortFilms(list, 'runtime')), ['Top', 'Mid', 'Fav', 'None']);
  assert.deepEqual(titles(sortFilms(list, 'recent')), ['Top', 'Mid', 'Fav', 'None']);
  assert.deepEqual(titles(sortFilms(list, 'new')), ['Top', 'Mid', 'Fav', 'None']);
  // Random keeps its order for the same seed, so a redraw does not reshuffle the grid.
  assert.deepEqual(titles(sortFilms(list, 'random', {seed: 7})), titles(sortFilms([...list].reverse(), 'random', {seed: 7})));
});

test('counts per option leave their own filter out; the best way out of an empty result', () => {
  const ctx = context(['Netflix', 'Arte', 'Apple TV Store']);
  const filters = {...baseFilters, genres: {include: ['Comedy'], exclude: []}, maxRuntime: 90};
  assert.equal(countVisible(films, filters, ctx), 1);
  const genres = facetCounts(films, filters, ctx, (f, c) => [{...f, genres: {include: [], exclude: []}}, c], film => film.genres || []);
  assert.deepEqual(Object.fromEntries(genres), {Comedy: 1});
  const empty = {...baseFilters, genres: {include: ['Drama'], exclude: []}, maxRuntime: 90};
  assert.equal(countVisible(films, empty, ctx), 0);
  const way = bestRelaxation(films, empty, ctx, [
    {id: 'runtime', label: 'runtime', open: (f, c) => [{...f, maxRuntime: 0}, c]},
    {id: 'genre', label: 'genre', open: (f, c) => [{...f, genres: {include: [], exclude: []}}, c]},
  ]);
  assert.deepEqual([way.id, way.count], ['runtime', 2]);
});

test('years entered the wrong way round are swapped', async () => {
  const {readFilters} = await import('../../static/js/filters.js');
  const values = {'year-from': '2020', 'year-to': '2000'};
  const doc = {getElementById: id => ({value: values[id] ?? ''})};
  const filters = readFilters(doc, false);
  assert.equal(filters.yearFrom, 2000);
  assert.equal(filters.yearTo, 2020);
  values['year-to'] = '';
  assert.deepEqual([readFilters(doc, false).yearFrom, readFilters(doc, false).yearTo], [2020, 9999]);
});

test('every set filter gets a chip and reset clears them all', async () => {
  const {FILTER_CONTROLS, activeFilters, resetFilters} = await import('../../static/js/filters.js');
  const select = (value, values) => ({value, options: values.map(item => ({value: item, text: `Label ${item}`})), get selectedIndex() { return values.indexOf(this.value); }, dataset: {}});
  const controls = {
    'film-search': {value: 'heat', dataset: {}},
    'rating-filter': select('tmdb:7', ['', 'tmdb:7']),
    'cost-filter': {value: 'free', dataset: {default: 'all', text: 'Free'}},
    'media-filter': select('trailer', ['all', 'trailer']),
    'provider-count-filter': select('2', ['0', '2']),
    'change-filter': select('all', ['all', 'added']),
    'exclusive-filter': {type: 'checkbox', checked: true, dataset: {}},
  };
  const doc = {getElementById: id => controls[id] ?? null};
  assert.equal(FILTER_CONTROLS.length, 16);
  assert.deepEqual(activeFilters(doc).map(chip => chip.label), ['Search', 'Cost', 'Rating', 'Trailer', 'Services', 'Only on one of my services']);
  assert.equal(activeFilters(doc).find(chip => chip.id === 'rating-filter').text, 'Label tmdb:7');
  // A hidden input behind a custom control carries its readable text and its default.
  assert.equal(activeFilters(doc).find(chip => chip.id === 'cost-filter').text, 'Free');
  resetFilters(doc);
  assert.deepEqual(activeFilters(doc), []);
  assert.equal(controls['rating-filter'].value, '');
  assert.equal(controls['cost-filter'].value, 'all');
  assert.equal(controls['exclusive-filter'].checked, false);
});

test('the compare button counts the chosen films', async () => {
  const {compareButtonState} = await import('../../static/js/rendering.js');
  assert.deepEqual(compareButtonState(0), {text: 'Compare'});
  assert.deepEqual(compareButtonState(3), {text: 'Compare (3)'});
});

test('similar films: only watchlist films on own services, in TMDB order, not watched', () => {
  const heat = {key: '949', title: 'Heat', similar_ids: [3, 2, 1, 4, 949], providers: {}};
  const films = [
    heat,
    {key: '1', title: 'One', providers: {Netflix: ['flatrate']}},
    {key: '2', title: 'Two', providers: {Netflix: ['rent']}},
    {key: '3', title: 'Three', providers: {Arte: ['free']}},
    {key: '4', title: 'Four', providers: {Netflix: ['flatrate']}},
  ];
  const titles = list => list.map(film => film.title);
  assert.deepEqual(titles(similarOnServices(heat, films, new Set(['Netflix', 'Arte']))), ['Three', 'One', 'Four']);
  assert.deepEqual(titles(similarOnServices(heat, films, new Set(['Netflix']), new Set(['1']))), ['Four']);
  assert.deepEqual(similarOnServices({key: 'x', title: 'Old scan'}, films, new Set(['Netflix'])), []);
});

test('age rating: up to a number, exact for other systems, unrated films out', () => {
  assert.equal(ageMatches('all', undefined), true);
  assert.equal(ageMatches(undefined, '18'), true);
  assert.equal(ageMatches('12', '6'), true);
  assert.equal(ageMatches('12', '16'), false);
  assert.equal(ageMatches('12', null), false);
  assert.equal(ageMatches('PG-13', 'PG-13'), true);
  assert.equal(ageMatches('PG-13', 'R'), false);
  assert.deepEqual(sortRatings(['16', 'PG', '6', null, '12', '6', 'G']), ['6', '12', '16', 'G', 'PG']);
});

test('coming soon: only future dates, soonest first', () => {
  const films = [
    {title: 'Out', cinema_date: '2025-01-01', home_date: '2025-05-01'},
    {title: 'Home later', cinema_date: '2026-01-01', home_date: '2026-12-01'},
    {title: 'Cinema soon', cinema_date: '2026-11-20'},
    {title: 'No dates'},
  ];
  assert.deepEqual(comingSoon(films, '2026-11-16').map(film => film.title), ['Cinema soon', 'Home later']);
});

test('language and country of origin filters', () => {
  const films = [
    {key: '1', title: 'Shoplifters', original_language: 'ja', origin_countries: ['JP'], providers: {Netflix: ['flatrate']}},
    {key: '2', title: 'Heat', original_language: 'en', origin_countries: ['US'], providers: {Netflix: ['flatrate']}},
  ];
  const titles = extra => filterFilms(films, [], {...baseFilters, ...extra}, {selected: new Set(['Netflix']), favorites: new Map()}).sections.Paid.map(film => film.title);
  assert.deepEqual(titles({language: 'ja'}), ['Shoplifters']);
  assert.deepEqual(titles({origin: 'US'}), ['Heat']);
  assert.deepEqual(titles({language: 'all', origin: 'all'}), ['Heat', 'Shoplifters']);
});

test('other countries: only own services without extra cost, current country left out', () => {
  const byCountry = {
    DE: {Netflix: ['flatrate']},
    US: {Netflix: ['flatrate'], Hulu: ['flatrate']},
    GB: {Netflix: ['rent'], MUBI: ['flatrate']},
    FR: {Arte: ['free'], Netflix: ['ads']},
  };
  assert.deepEqual(elsewhereOnServices(byCountry, new Set(['Netflix', 'Arte']), 'DE'), [['FR', ['Arte', 'Netflix']], ['US', ['Netflix']]]);
  assert.deepEqual(elsewhereOnServices(null, new Set(['Netflix']), 'DE'), []);
});

test('Letterboxd rating: minimum filter and sort, unrated films last', () => {
  const films = [
    {key: '1', title: 'Low', letterboxd_rating: 3.1, providers: {Netflix: ['flatrate']}},
    {key: '2', title: 'High', letterboxd_rating: 4.4, providers: {Netflix: ['flatrate']}},
    {key: '3', title: 'Unrated', providers: {Netflix: ['flatrate']}},
  ];
  const titles = extra => filterFilms(films, [], {...baseFilters, ...extra}, {selected: new Set(['Netflix']), favorites: new Map()}).sections.Paid.map(film => film.title);
  assert.deepEqual(titles({minLetterboxd: 4}), ['High']);
  assert.deepEqual(titles({sort: 'letterboxd'}), ['High', 'Low', 'Unrated']);
});

test('the merged list holds each film once, in order, and marks films of both sections', () => {
  const view = filterFilms(films, [], baseFilters, context(['Netflix', 'Arte']));
  const keys = view.films.map(film => film.title);
  assert.equal(new Set(keys).size, keys.length);
  assert.deepEqual(keys, [...keys].sort());  // sort 'title' in the test setup
  const section = title => view.sectionOf.get(filmKey(view.films.find(film => film.title === title)));
  assert.equal(section('Beta'), 'All');  // free on Arte and on a paid service
  assert.equal(section('Alpha'), 'Paid');
});
