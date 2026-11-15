const { test } = require('node:test');
const assert = require('node:assert/strict');
const { isSafeExternal } = require('./links.cjs');
test('external links cannot execute commands or expose local files', () => {
  for (const value of ['file:///C:/secret', 'javascript:alert(1)', 'cmd:calc', 'https://user:password@example.com', 'not a url']) assert.equal(isSafeExternal(value), false);
  assert.equal(isSafeExternal('https://doi.org/10.1234/example'), true);
});
