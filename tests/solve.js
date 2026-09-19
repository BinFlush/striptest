// Runs the algorithm from index.html outside a browser: reads a JSON list of
// settings on stdin, prints what the page would compute for each.
// The page keeps its algorithm in the first <script> block, free of any DOM use.

const fs = require('fs');
const vm = require('vm');

const page = fs.readFileSync(`${__dirname}/../index.html`, 'utf8');
const algorithm = page.match(/<script>([\s\S]*?)<\/script>/)[1];
const context = vm.createContext({});
vm.runInContext(`${algorithm}\nthis.page = { solve, tempoList };`, context);

const results = JSON.parse(fs.readFileSync(0, 'utf8')).map(settings => {
  const { tempo, every, rows } = context.page.solve(settings);
  return { tempo, every, beats: rows.map(row => row.beats), counts: rows.map(row => row.count) };
});

console.log(JSON.stringify({ results, mechanical: context.page.tempoList('mechanical', 40, 208) }));
