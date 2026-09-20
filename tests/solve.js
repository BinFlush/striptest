// Runs the algorithm from index.html outside a browser: reads a JSON list of
// settings on stdin, prints what the page would compute for each.
// The page keeps its algorithm in the first <script> block, free of any DOM use.

const fs = require('fs');
const vm = require('vm');

const page = fs.readFileSync(`${__dirname}/../index.html`, 'utf8');
const algorithm = page.match(/<script>([\s\S]*?)<\/script>/)[1];
const context = vm.createContext({});
const used = `{ solveSkipping, timed, worst, formatAdd,
  density, shade, borders, zoneOf, edges, probed, PRINTED }`;
vm.runInContext(`${algorithm}\nthis.page = ${used};`, context);
const { solveSkipping, timed, worst, formatAdd } = context.page;
const { density, shade, borders, zoneOf, edges, probed, PRINTED } = context.page;

const asked = JSON.parse(fs.readFileSync(0, 'utf8'));
const results = asked.map(({ skipped, ...settings }) => {
  const { tempo, every, rows, passed } = solveSkipping(settings, new Set(skipped));
  if (!rows) return { passed };
  const beats = rows.map(row => row.beats);
  return { tempo, every, beats, counts: rows.map(row => row.count), passed, worst: worst(rows) };
});

// The same strips timed with a timer, and how what is added for a patch is written
const timers = asked.map(settings => timed(settings));
const added = [[5, 5], [6.3 - 5, 6.3], [0.1, 0.1], [12, 22]]
  .map(([add, seconds]) => formatAdd(add, seconds));

// The grey on the screen for every third of a stop, ten stops either side of the base
const filters = ['00', '0', '1', '2', '3', '4', '5'];
const thirds = Array.from({ length: 61 }, (_, i) => i - 30);
const tones = Object.fromEntries(filters.map(filter =>
  [filter, thirds.map(third => [third, shade(density(third / 3, filter))])]));

// The print's zones: their densities, the number zoneOf() gives each of them and a density
// beyond either end, and per filter the exposure where one zone gives way to the next together
// with the density the paper really has there
const zones = {
  printed: [...PRINTED],
  numbered: [3, ...PRINTED, 0].map(printed => [printed, zoneOf(printed)]),
  borders: Object.fromEntries(filters.map(filter =>
    [filter, borders(filter).map(stops => [stops, density(stops, filter)])])),
};

// Rows given from two stops less to two stops more than the reference, in sixths and a bit, at
// the reference row's filter and at every other: where their zones begin and end, and the
// density probed at 201 places along them
const shares = Array.from({ length: 201 }, (_, i) => i / 200);
const pairs = filters.flatMap(filter => filters.map(other => [filter, other]));
const strips = pairs.flatMap(([filter, other]) => Array.from({ length: 25 }, (_, i) => {
  const exposed = (i - 12) / 6 + 0.013 * (i % 3);
  return {
    filter,
    other,
    exposed,
    edges: [...edges(exposed, filter, other)],
    probed: shares.map(share => [share, probed(share, exposed, filter, other)]),
  };
}));

// The tone ISO speed is measured at, 0.6 above paper white, found in the reference row and
// probed at every filter there, in rows given a stop less, the same and a stop more
const measured = (zoneOf(0.63) + 0.5) / 11;
const speeds = pairs.map(([filter, other]) => ({
  filter,
  other,
  probed: [-1, 0, 1].map(exposed => [exposed, probed(measured, exposed, filter, other)]),
}));
console.log(JSON.stringify({ results, timers, added, tones, zones, strips, speeds }));
