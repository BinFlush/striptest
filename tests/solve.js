// Runs the algorithm from index.html outside a browser: reads a JSON list of
// settings on stdin, prints what the page would compute for each.
// The page keeps its algorithm in the script block named below, free of any DOM use.

const fs = require('fs');
const vm = require('vm');

const page = fs.readFileSync(`${__dirname}/../index.html`, 'utf8');
const algorithm = page.match(/<script id="algorithm">([\s\S]*?)<\/script>/)[1];
const context = vm.createContext({});
const used = `{ solveSkipping, timed, formatAdd, schedule, climb,
  FUNDAMENTAL, BEND, CLIMBS, COUNT_IN,
  density, shade, borders, zoneOf, edges, probed, PAPERS, SPEEDS, PRINTED }`;
vm.runInContext(`${algorithm}\nthis.page = ${used};`, context);
const { solveSkipping, timed, formatAdd, schedule, climb } = context.page;
const { FUNDAMENTAL, BEND, CLIMBS, COUNT_IN } = context.page;
const { density, shade, borders, zoneOf, edges, probed, PAPERS, SPEEDS, PRINTED } = context.page;

const asked = JSON.parse(fs.readFileSync(0, 'utf8'));
const results = asked.map(({ skipped, ...settings }) => {
  const { tempo, every, rows, passed } = solveSkipping(settings, new Set(skipped));
  if (!rows) return { passed };
  const beats = rows.map(row => row.beats);
  return { tempo, every, beats, counts: rows.map(row => row.count), passed };
});

// The same strips timed with a timer, and how what is added for a patch is written
const timers = asked.map(settings => timed(settings));
const added = [[5, 5], [6.3 - 5, 6.3], [0.1, 0.1], [12, 22]]
  .map(([add, seconds]) => formatAdd(add, seconds));

// The run the page would sound for those same strips: when every mark falls, and the glide
// through gaps of very different lengths
const runs = asked.map(settings => schedule(timed(settings), COUNT_IN));
const waits = [0, 1.5, 12].map(countIn => ({ countIn, marks: schedule(timed(asked[0] ?? {
  base: 10, stepsize: 3, numsteps: 7, baseplace: 3,
}), countIn) }));
const climbs = [[0, COUNT_IN], [4, 4.39], [10, 20], [0, 0.1], [3, 3.002]]
  .map(([from, mark]) => ({ from, mark, points: climb(from, mark) }));
const sound = { FUNDAMENTAL, BEND, CLIMBS, COUNT_IN };

// Everything about the tones is worked out for every paper the page offers
const ALL = ['00', '0', '1', '2', '3', '4', '5'];
const thirds = Array.from({ length: 61 }, (_, i) => i - 30);
const shares = Array.from({ length: 201 }, (_, i) => i / 200);
const papers = Object.fromEntries(Object.keys(PAPERS).map(paper => {
  // Only the filters this paper's own sheet draws: not every maker publishes all seven
  const filters = ALL.filter(filter => filter in PAPERS[paper]);
  const pairs = filters.flatMap(filter => filters.map(other => [filter, other]));
  // The grey on the screen for every third of a stop, ten stops either side of the base
  const tones = Object.fromEntries(filters.map(filter =>
    [filter, thirds.map(third => [third, shade(density(third / 3, filter, paper))])]));

  // The print's zones: their densities, the number zoneOf() gives each of them and a density
  // beyond either end, and per filter the exposure where one zone gives way to the next together
  // with the density the paper really has there
  const zones = {
    printed: [...PRINTED[paper]],
    numbered: [3, ...PRINTED[paper], 0].map(printed => [printed, zoneOf(printed, paper)]),
    borders: Object.fromEntries(filters.map(filter =>
      [filter, borders(filter, paper).map(stops => [stops, density(stops, filter, paper)])])),
  };

  // Rows given from two stops less to two stops more than the reference, in sixths and a bit, at
  // the reference row's filter and at every other: where their zones begin and end, and the
  // density probed at 201 places along them
  const strips = pairs.flatMap(([filter, other]) => Array.from({ length: 25 }, (_, i) => {
    const exposed = (i - 12) / 6 + 0.013 * (i % 3);
    return {
      filter,
      other,
      exposed,
      edges: [...edges(exposed, filter, other, paper)],
      probed: shares.map(share => [share, probed(share, exposed, filter, other, paper)]),
    };
  }));

  // The tone ISO speed is measured at, 0.6 above paper white, found in the reference row and
  // probed at every filter there: in rows given a stop less, the same and a stop more, and in
  // one given what the page's own speeds say the other filter needs
  const white = PRINTED[paper][PRINTED[paper].length - 1];
  const measured = (zoneOf(white + 0.6, paper) + 0.5) / 11;
  const speeds = pairs.map(([filter, other]) => {
    const needed = Math.log2(SPEEDS[paper][filter] / SPEEDS[paper][other]);
    return {
      filter,
      other,
      probed: [...new Set([-1, 0, 1, needed])]
        .map(exposed => [exposed, probed(measured, exposed, filter, other, paper)]),
    };
  });
  return [paper, { filters, tones, zones, strips, speeds }];
}));
console.log(JSON.stringify({ results, timers, added, runs, waits, climbs, sound, papers }));
