import { existsSync, writeFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))

function argValue(name) {
  const index = process.argv.indexOf(name)
  if (index === -1 || index + 1 >= process.argv.length) return null
  return process.argv[index + 1]
}

const tokometerRoot =
  argValue('--tokometer-root') ||
  process.env.AGENTLEDGER_TOKOMETER_ROOT ||
  resolve(__dirname, '..', '..', 'codex-token-gauge')
const out = argValue('--out')
const codexHome = argValue('--codex-home') || process.env.TOKEN_GAUGE_CODEX_HOME
const dataDir = argValue('--data-dir') || process.env.TOKEN_GAUGE_DATA_DIR

if (!out) {
  console.error('Missing required --out path.')
  process.exit(2)
}

const usageModule = resolve(tokometerRoot, 'server', 'usage.ts')
if (!existsSync(usageModule)) {
  console.error(`Tokometer usage module not found: ${usageModule}`)
  process.exit(3)
}

const { getUsageSummary } = await import(pathToFileURL(usageModule).href)
const summary = await getUsageSummary({ codexHome, dataDir })
const diagnostics = summary.source.parseDiagnostics

const compact = {
  schema_version: 'agentledger.tokometer_summary.v1',
  generated_at: new Date().toISOString(),
  tokometer_root: tokometerRoot,
  source: {
    ...summary.source,
    parseDiagnostics: {
      parsedLines: diagnostics.parsedLines,
      malformedLines: diagnostics.malformedLines,
      parseFailures: diagnostics.parseFailures,
      tokenRecords: diagnostics.tokenRecords,
      usedEvents: diagnostics.usedEvents,
      ignoredEvents: diagnostics.ignoredEvents,
      fallbackTokenSourceUsed: diagnostics.fallbackTokenSourceUsed,
      resetEvents: diagnostics.resetEvents,
      anomalousDeltas: diagnostics.anomalousDeltas,
      filesReported: diagnostics.files.length,
    },
  },
  latest: summary.latest,
  limits: summary.limits,
  windows: summary.windows,
  rates: summary.rates,
  freshness: summary.freshness,
  topSessions: summary.topSessions.slice(0, 10),
  alerts: summary.alerts,
  accuracy: summary.accuracy,
}

writeFileSync(out, `${JSON.stringify(compact, null, 2)}\n`, 'utf8')
