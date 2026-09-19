// Runs the algorithm from index.html outside a browser: reads a JSON list of
// settings on stdin, prints what the page would compute for each.
// The page keeps its algorithm in the first <script> block, free of any DOM use.

const fs = require('fs');
const vm = require('vm');

const page = fs.readFileSync(`${__dirname}/../index.html`, 'utf8');
const algorithm = page.match(/<script>([\s\S]*?)<\/script>/)[1];
const context = vm.createContext({});
vm.runInContext(`${algorithm}\nthis.solveSkipping = solveSkipping;`, context);

const results = JSON.parse(fs.readFileSync(0, 'utf8')).map(({ skipped, ...settings }) => {
  const { tempo, every, rows, passed } = context.solveSkipping(settings, new Set(skipped));
  if (!rows) return { passed };
  const beats = rows.map(row => row.beats);
  return { tempo, every, beats, counts: rows.map(row => row.count), passed };
});

console.log(JSON.stringify(results));
