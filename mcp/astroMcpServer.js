// Astro Agent MCP server — the read-only tool registry the Python ADK agents
// (astro_agent/) call. Every tool wraps logic that already powers the REST
// API; none of them write, spend wallet balance, or book anything.
//
// A fresh McpServer is built per HTTP request (stateless Streamable HTTP), bound
// to the authenticated caller, so every kundali lookup is ownership-checked
// against the JWT user exactly like /api/v1/ai/chat/stream does.

const mongoose = require('mongoose');
const { z } = require('zod');
const { McpServer } = require('@modelcontextprotocol/sdk/server/mcp.js');
const Kundali = require('../models/KundaliEnhanced');
const facts = require('../services/agentTools/astroFacts');
const kb = require('../services/agentTools/kbSearch');
const logger = require('../config/logger');

const READ_ONLY = { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false };

class ToolError extends Error {}

function ok(data) {
  return { content: [{ type: 'text', text: JSON.stringify(data) }] };
}

function fail(message) {
  return { isError: true, content: [{ type: 'text', text: JSON.stringify({ error: message }) }] };
}

async function loadOwnedKundali(kundaliId, user, { hydrate = false } = {}) {
  if (!kundaliId) throw new ToolError('kundali_id is required.');
  const find = (q) => (hydrate ? Kundali.findOne(q) : Kundali.findOne(q).lean());
  let doc = null;
  if (mongoose.Types.ObjectId.isValid(kundaliId)) doc = await find({ _id: kundaliId });
  if (!doc) doc = await find({ kundaliID: kundaliId });
  if (!doc) throw new ToolError(`No kundali found for id ${kundaliId}.`);
  if (doc.createdBy && doc.createdBy.toString() !== user._id.toString()) {
    throw new ToolError('This kundali does not belong to the signed-in user.');
  }
  return doc;
}

function buildAstroMcpServer({ user }) {
  const server = new McpServer({ name: 'pixel-astro-tools', version: '1.0.0' });

  const register = (name, description, inputSchema, handler) => {
    server.registerTool(name, { description, inputSchema, annotations: READ_ONLY }, async (args) => {
      const started = Date.now();
      try {
        const result = await handler(args || {});
        logger.info(`[astro-mcp] ${name} ok user=${user._id} ${Date.now() - started}ms`);
        return ok(result);
      } catch (err) {
        if (err instanceof ToolError) return fail(err.message);
        logger.error(`[astro-mcp] ${name} failed user=${user._id}: ${err.message}`);
        return fail('Internal error while reading chart data.');
      }
    });
  };

  const kundaliId = z.string().describe('Kundali Mongo _id or public kundaliID (PXK-...) from list_my_kundalis.');

  register(
    'list_my_kundalis',
    'List the kundalis (birth charts) saved by the signed-in user. Call this first to resolve which chart the user means.',
    {},
    async () => {
      const docs = await Kundali.find({ createdBy: user._id })
        .select('name gender dateOfBirth timeOfBirth placeOfBirth kundaliID calculatedAt')
        .sort({ calculatedAt: -1 })
        .limit(25)
        .lean();
      return {
        count: docs.length,
        kundalis: docs.map((d) => ({
          kundaliId: String(d._id),
          publicId: d.kundaliID || null,
          name: d.name || null,
          gender: d.gender || null,
          dateOfBirth: d.dateOfBirth || null,
          timeOfBirth: d.timeOfBirth || null,
          placeOfBirth: d.placeOfBirth || null,
        })),
      };
    },
  );

  register(
    'get_chart_houses',
    'Ascendant, planet positions (sign, degree, house, nakshatra, dignity, retrograde), the 12 houses with lords/occupants, and Shadbala strengths.',
    { kundali_id: kundaliId },
    async ({ kundali_id }) => facts.chartHouses(await loadOwnedKundali(kundali_id, user)),
  );

  register(
    'get_dasha_periods',
    'Vimshottari dasha timeline with dates and ages. Antardashas are returned for the current and next mahadasha, and for any mahadasha/antardasha of the given planets.',
    {
      kundali_id: kundaliId,
      planets: z.array(z.string()).optional().describe('Optional planets to expand, e.g. ["Venus","Jupiter"] for marriage timing.'),
    },
    async ({ kundali_id, planets }) => facts.dashaPeriods(await loadOwnedKundali(kundali_id, user), { planets }),
  );

  register(
    'get_transits',
    'Current and upcoming planetary transits relative to the natal chart (a snapshot from when the kundali was calculated — see computedAt).',
    { kundali_id: kundaliId },
    async ({ kundali_id }) => facts.transits(await loadOwnedKundali(kundali_id, user)),
  );

  register(
    'get_yogas',
    'Yogas and doshas detected in the chart, plus the remedies the calculation engine recorded for them.',
    { kundali_id: kundaliId },
    async ({ kundali_id }) => facts.yogasAndDoshas(await loadOwnedKundali(kundali_id, user)),
  );

  register(
    'match_kundali',
    'Ashtakoota (36-guna) compatibility between two of the user\'s kundalis: guna scores, doshas, strengths and challenges.',
    {
      boy_kundali_id: z.string().describe('Groom\'s kundali id.'),
      girl_kundali_id: z.string().describe('Bride\'s kundali id.'),
    },
    async ({ boy_kundali_id, girl_kundali_id }) => {
      // Lazy: kundaliController is large and only this tool needs it.
      const { calculateKundaliMatch } = require('../controllers/kundaliController');
      const boy = await loadOwnedKundali(boy_kundali_id, user, { hydrate: true });
      const girl = await loadOwnedKundali(girl_kundali_id, user, { hydrate: true });
      if (!boy.planetaryPositions?.length || !girl.planetaryPositions?.length) {
        throw new ToolError('One of the kundalis has no planetary positions calculated.');
      }
      return {
        boy: facts.nativeSummary(boy),
        girl: facts.nativeSummary(girl),
        match: calculateKundaliMatch(boy, girl),
      };
    },
  );

  register(
    'search_kb',
    'Keyword search over the Pixel Astro Vedic knowledge base (classical rules, remedies, doshas, dashas, transits). Returns the most relevant passages with their source document.',
    {
      query: z.string().min(2).describe('What to look up, e.g. "Mangal dosha remedies" or "Saturn transit 8th from Moon".'),
      category: z.string().optional().describe('Optional category filter (see availableCategories in a previous result).'),
      top_k: z.number().int().min(1).max(10).optional().describe('Number of passages, default 5.'),
    },
    async ({ query, category, top_k }) => kb.search(query, { topK: top_k, category }),
  );

  return server;
}

module.exports = { buildAstroMcpServer };
