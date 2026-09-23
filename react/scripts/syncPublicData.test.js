import { createRequire } from 'node:module';
import { describe, expect, it } from 'vitest';
import { SECTION_PAYLOAD_FILES } from '../src/data';

const require = createRequire(import.meta.url);
const { DATASET_FILES } = require('./syncPublicData');

describe('public data synchronization', () => {
  it('publishes every deferred dashboard payload', () => {
    expect(DATASET_FILES).toEqual(
      expect.arrayContaining(Object.values(SECTION_PAYLOAD_FILES)),
    );
  });
});
