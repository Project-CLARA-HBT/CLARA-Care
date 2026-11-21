// Compare every output word to integer long division rounded once to nearest/even.
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {readFileSync, readdirSync} from 'node:fs';
import path from 'node:path';

const [dataDir, outDir] = process.argv.slice(2);
const names = ['fast_float', 'std', 'scalar', 'paired'];
const words = new Map();
function expected(s) {
  if (s === '' || s === '?') return 0x7ff8000000000001n;
  if (words.has(s)) return words.get(s);
  assert.match(s, /^\d+(?:\.\d+)?$/);
  const [whole, frac = ''] = s.split('.');
  const n = BigInt(whole + frac), d = 10n ** BigInt(frac.length);
  let word = 0n;
  if (n > 0n) {
    let e = n.toString(2).length - d.toString(2).length;
    if (e >= 0 ? n < (d << BigInt(e)) : (n << BigInt(-e)) < d) --e;
    assert(e >= -1022 && e <= 52);
    const scaled = n << BigInt(52-e);
    let q = scaled / d;
    const twice = 2n * (scaled % d);
    if (twice > d || (twice === d && q % 2n === 1n)) ++q;
    word = (BigInt(e+1023) << 52n) + q - (1n << 52n);
  }
  words.set(s, word);
  return word;
}
const stats = [];
for (const file of readdirSync(dataDir).filter(f => f.endsWith('.csv')).sort()) {
  const original = readFileSync(path.join(dataDir,file));
  const lines = original.toString('ascii').trimEnd().split(/\r?\n/);
  const fields = lines.flatMap(line => {
    const cols = line.split(';');
    assert.equal(cols.length, 9);
    return cols.slice(2);
  });
  const reference = fields.map(expected);
  const measurement = {
    day:file.slice(0,-4), rows:lines.length, bytes:original.length, tokens:fields.length,
    missing:fields.filter(s=>s === '' || s === '?').length,
    eligible:fields.filter(s=>/^\d{1,3}\.\d{3}$/.test(s)).length,
    eligiblePairs:0,
    inputSha256:createHash('sha256').update(original).digest('hex')
  };
  for (let i=0;i<fields.length;i+=7) {
    for (let k=0;k<6;k+=2) {
      measurement.eligiblePairs += Number(fields.slice(i+k,i+k+2).every(s=>/^\d{1,3}\.\d{3}$/.test(s)));
    }
  }
  for (const arm of names) {
    const out = readFileSync(path.join(outDir, file+'.'+arm));
    assert.equal(out.length, reference.length*8);
    for (let i=0;i<reference.length;++i) assert.equal(out.readBigUInt64LE(i*8),reference[i],file+'/'+arm+'/'+i);
  }
  stats.push(measurement);
}
assert.equal(stats.length,14);
console.log(JSON.stringify(stats,null,2));
