// Runs the algorithm from index.html outside a browser: reads a JSON list of
// settings on stdin, prints what the page would compute for each.
// The page keeps its algorithm in the first <script> block, free of any DOM use.

const fs = require('fs');
const vm = require('vm');

const page = fs.readFileSync(`${__dirname}/../index.html`, 'utf8');
const algorithm = page.match(/<script>([\s\S]*?)<\/script>/)[1];
const context = vm.createContext({});
const used = '{ solveSkipping, density, shade, borders, zoneOf, edges, probed, PRINTED }';
vm.runInContext(`${algorithm}\nthis.page = ${used};`, context);
const { solveSkipping, density, shade, borders, zoneOf, edges, probed, PRINTED } = context.page;

const results = JSON.parse(fs.readFileSync(0, 'utf8')).map(({ skipped, ...settings }) => {
  const { tempo, every, rows, passed } = solveSkipping(settings, new Set(skipped));
  if (!rows) return { passed };
  const beats = rows.map(row => row.beats);
  return { tempo, every, beats, counts: rows.map(row => row.count), passed };
});

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

// Rows given from two stops less to two stops more than the reference, in sixths and a bit:
// where their zones begin and end, and the density probed at 401 places along them
const shares = Array.from({ length: 401 }, (_, i) => i / 400);
const strips = filters.flatMap(filter => Array.from({ length: 25 }, (_, i) => {
  const exposed = (i - 12) / 6 + 0.013 * (i % 3);
  return {
    filter,
    exposed,
    edges: [...edges(exposed, filter)],
    probed: shares.map(share => [share, probed(share, exposed, filter)]),
  };
}));
console.log(JSON.stringify({ results, tones, zones, strips }));
