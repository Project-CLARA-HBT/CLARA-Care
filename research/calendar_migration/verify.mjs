// Verify release observations independently using IANA's published transition dates.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { createHash } from 'node:crypto';

const [result, cache] = process.argv.slice(2);
const data = JSON.parse(fs.readFileSync(result, 'utf8'));
for (const [key, value] of Object.entries(data.sources)) {
  assert.equal(createHash('sha256').update(fs.readFileSync(path.join(cache, key))).digest('hex'), value.sha256);
}
const start = Date.UTC(2023, 2, 26) - 2 * 3600000;
const end = Date.UTC(2023, 3, 21) - 2 * 3600000;
assert.equal(data.beirut.length, 1);
const period = data.beirut[0];
assert.equal(Date.parse(period.start_utc), start);
assert.equal(Date.parse(period.end_utc), end);
assert.deepEqual(period.offset_min, [120, 180]);
assert.equal(period.hours, (end-start)/3600000);
const text = name => fs.readFileSync(path.join(cache, name), 'utf8');
const blocks = text('gold').split(/\r?\n\s*\r?\n/).filter(b => /^RRULE:/m.test(b));
assert.equal(blocks.length,data.fixtures.libical_gold.rules);
assert.ok(blocks.every(b => /^INSTANCES:/m.test(b) && !b.includes('Asia/Beirut')));
const events = [...text('events').matchAll(/BEGIN:VEVENT([\s\S]*?)END:VEVENT/g)];
assert.equal(events.length, data.fixtures.libical_events.vevents);
assert.ok(events.every(m => m[1].includes('X-EXPECT-NUMEVENTS') && !m[1].includes('Asia/Beirut')));
console.log('Verified six source digests, both release boundaries and the two libical fixture denominators.');
