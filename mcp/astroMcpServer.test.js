jest.mock('../config/logger', () => ({ info: jest.fn(), error: jest.fn(), warn: jest.fn() }));

const OWNER_ID = '64b000000000000000000001';
const OTHER_ID = '64b000000000000000000002';
const KUNDALI_ID = '64b0000000000000000000aa';

const kundaliDoc = {
  _id: KUNDALI_ID,
  kundaliID: 'PXK-TEST-0101-01',
  createdBy: OWNER_ID,
  name: 'Asha',
  dateOfBirth: '1995-01-01',
  timeOfBirth: '10:30',
  placeOfBirth: 'Bhubaneswar',
  calculatedAt: '2026-09-01T00:00:00.000Z',
  lagnaStrength: { lagnaSign: 'Aries', lagnaLord: 'Mars', overallStatus: 'Strong' },
  planetaryPositions: [
    { name: 'Mars', sign: 'Aries', house: 'House 1', longitude: 12.5, nakshatra: 'Ashwini', pada: 4 },
    { name: 'Venus', sign: 'Libra', house: 'House 7', longitude: 190.25, special: 'Retrograde' },
  ],
  houses: [{ house: 1, sign: 'Aries' }, { house: 7, sign: 'Libra' }],
  vimshottariDashas: {
    current: { mahadasha: 'Venus', antardasha: 'Sun' },
    dashas: [
      { planet: 'Venus', start: '2020-01-01', end: '2040-01-01', status: 'Current',
        bhuktis: [{ planet: 'Venus', start: '2020-01-01', end: '2023-05-01' }, { planet: 'Sun', start: '2023-05-01', end: '2024-05-01' }] },
      { planet: 'Sun', start: '2040-01-01', end: '2046-01-01', status: 'Future',
        bhuktis: [{ planet: 'Sun', start: '2040-01-01', end: '2040-04-01' }] },
      { planet: 'Moon', start: '2046-01-01', end: '2056-01-01', status: 'Future',
        bhuktis: [{ planet: 'Moon', start: '2046-01-01', end: '2046-11-01' }, { planet: 'Mars', start: '2046-11-01', end: '2047-06-01' }] },
    ],
  },
  yogas: [{ name: 'Malavya Yoga', planets: ['Venus'], strength: 'Strong' }],
  doshas: [],
  remedies: [{ planet: 'Saturn', remedy: 'Chant Shani mantra on Saturdays' }],
};

const mockStore = [kundaliDoc, { ...kundaliDoc, _id: '64b0000000000000000000bb', kundaliID: 'PXK-OTHER', createdBy: OTHER_ID }];
const mockMatchQuery = (q) => mockStore.find((d) => Object.entries(q).every(([k, v]) => String(d[k]) === String(v))) || null;
const mockChain = (value) => ({ lean: () => Promise.resolve(value), then: (r, j) => Promise.resolve(value).then(r, j) });

jest.mock('../models/KundaliEnhanced', () => ({
  findOne: jest.fn((q) => mockChain(mockMatchQuery(q))),
  find: jest.fn((q) => {
    const rows = mockStore.filter((d) => String(d.createdBy) === String(q.createdBy));
    const c = { select: () => c, sort: () => c, limit: () => c, lean: () => Promise.resolve(rows) };
    return c;
  }),
}));

const { Client } = require('@modelcontextprotocol/sdk/client/index.js');
const { InMemoryTransport } = require('@modelcontextprotocol/sdk/inMemory.js');
const { buildAstroMcpServer } = require('./astroMcpServer');

async function connect(userId = OWNER_ID) {
  const server = buildAstroMcpServer({ user: { _id: userId } });
  const [clientT, serverT] = InMemoryTransport.createLinkedPair();
  const client = new Client({ name: 'test', version: '0.0.0' });
  await Promise.all([server.connect(serverT), client.connect(clientT)]);
  return client;
}

const call = async (client, name, args = {}) => {
  const res = await client.callTool({ name, arguments: args });
  return { isError: !!res.isError, data: JSON.parse(res.content[0].text) };
};

describe('astro MCP server', () => {
  let client;
  beforeEach(async () => { client = await connect(); });

  test('exposes only the read-only tool registry', async () => {
    const { tools } = await client.listTools();
    expect(tools.map((t) => t.name).sort()).toEqual([
      'get_chart_houses', 'get_dasha_periods', 'get_transits', 'get_yogas',
      'list_my_kundalis', 'match_kundali', 'search_kb',
    ]);
    for (const t of tools) expect(t.annotations.readOnlyHint).toBe(true);
  });

  test('list_my_kundalis returns only the caller\'s charts', async () => {
    const { data } = await call(client, 'list_my_kundalis');
    expect(data.count).toBe(1);
    expect(data.kundalis[0].publicId).toBe('PXK-TEST-0101-01');
  });

  test('get_chart_houses returns structured houses with lords and occupants', async () => {
    const { isError, data } = await call(client, 'get_chart_houses', { kundali_id: 'PXK-TEST-0101-01' });
    expect(isError).toBe(false);
    expect(data.ascendant).toEqual({ sign: 'Aries', lord: 'Mars', strength: 'Strong' });
    expect(data.houses[1]).toMatchObject({ house: 7, lord: 'Venus', lordPlacedInHouse: 7, occupants: ['Venus'] });
    expect(data.planets.find((p) => p.planet === 'Venus').retrograde).toBe(true);
  });

  test('get_dasha_periods expands current/next MD and requested planets only', async () => {
    const { data } = await call(client, 'get_dasha_periods', { kundali_id: KUNDALI_ID, planets: ['Mars'] });
    const [venus, sun, moon] = data.mahadashas;
    expect(venus.antardashas).toHaveLength(2);
    expect(sun.antardashas).toHaveLength(1);
    expect(moon.antardashas.map((a) => a.planet)).toEqual(['Mars']);
    expect(venus.ageRange).toEqual([25, 45]);
  });

  test('missing data is reported, not invented', async () => {
    const { data: t } = await call(client, 'get_transits', { kundali_id: KUNDALI_ID });
    expect(t.current).toEqual([]);
    expect(t.missing).toEqual(['transits']);
    const { data: y } = await call(client, 'get_yogas', { kundali_id: KUNDALI_ID });
    expect(y.missing).toEqual(['doshas']);
  });

  test('another user\'s kundali is refused', async () => {
    const { isError, data } = await call(client, 'get_chart_houses', { kundali_id: 'PXK-OTHER' });
    expect(isError).toBe(true);
    expect(data.error).toMatch(/does not belong/);
  });

  test('search_kb returns ranked passages from the knowledge base', async () => {
    const { data } = await call(client, 'search_kb', { query: 'Saturn sade sati', top_k: 3 });
    expect(data.results.length).toBeGreaterThan(0);
    expect(data.results.length).toBeLessThanOrEqual(3);
    expect(data.results[0]).toHaveProperty('document');
  });
});
