// Runs the algorithm from index.html outside a browser: reads a JSON list of
// settings on stdin, prints what the page would compute for each.
// The page keeps its algorithm in the first <script> block, free of any DOM use.

const fs = require('fs');
const vm = require('vm');

const page = fs.readFileSync(`${__dirname}/../index.html`, 'utf8');
const algorithm = page.match(/<script>([\s\S]*?)<\/script>/)[1];
const context = vm.createContext({});
const used = '{ solveSkipping, shade, density, borders, zoneOf, edges, probed, PRINTED }';
vm.runInContext(`${algorithm}\nthis.page = ${used};`, context);

const results = JSON.parse(fs.readFileSync(0, 'utf8')).map(({ skipped, ...settings }) => {
  const { tempo, every, rows, passed } = context.page.solveSkipping(settings, new Set(skipped));
  if (!rows) return { passed };
  const beats = rows.map(row => row.beats);
  return { tempo, every, beats, counts: rows.map(row => row.count), passed };
});

const filters = ['00', '0', '1', '2', '3', '4', '5'];
const grey = (stops, filter) => context.page.shade(context.page.density(stops, filter));
const thirds = Array.from({ length: 61 }, (_, i) => i - 30);
const tones = Object.fromEntries(filters.map(filter =>
  [filter, thirds.map(third => [third, grey(third / 3, filter)])]));

// The print's zones: their densities, and per filter the exposure where each gives way to the
// next together with the density the paper really has there
const reached = filter => context.page.borders(filter).map(stops =>
  [stops, context.page.density(stops, filter)]);
const asked = [3, ...context.page.PRINTED, 0];

// Rows given from two stops less to two stops more than the reference, in sixths and a bit:
// where their zones begin and end, and the density probed at 401 places along them
const shares = Array.from({ length: 401 }, (_, i) => i / 400);
const rows = filters.flatMap(filter => Array.from({ length: 25 }, (_, i) => {
  const exposed = (i - 12) / 6 + 0.013 * (i % 3);
  return {
    filter,
    exposed,
    edges: [...context.page.edges(exposed, filter)],
    probed: shares.map(share => [share, context.page.probed(share, exposed, filter)]),
  };
}));
const zones = {
  printed: [...context.page.PRINTED],
  borders: Object.fromEntries(filters.map(filter => [filter, reached(filter)])),
  numbered: asked.map(printed => [printed, context.page.zoneOf(printed)]),
  rows,
};
console.log(JSON.stringify({ results, tones, zones }));
