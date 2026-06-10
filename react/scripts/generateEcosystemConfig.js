const fs = require('fs');
const path = require('path');
const yaml = require('js-yaml');

const reactRoot = path.resolve(__dirname, '..');
const repoRoot = path.resolve(reactRoot, '..');
const ecosystemsRoot = path.join(repoRoot, 'ecosystems');
const outputDir = path.join(reactRoot, 'src', 'generated');
const outputPath = path.join(outputDir, 'ecosystems.json');
const tempOutputPath = path.join(outputDir, `ecosystems.json.${process.pid}.tmp`);

function titleCase(value) {
  const text = String(value || '').replace(/[_-]+/g, ' ').trim();
  return text ? text.charAt(0).toUpperCase() + text.slice(1) : '';
}

function cleanText(value) {
  return String(value || '').trim();
}

function sourceShortLabel(source) {
  const acronym = String(source.proposal_acronym || '').trim();
  return acronym ? `${acronym}s` : source.display_name;
}

function proposalPluralWithAcronym(source) {
  const plural = String(source.proposal_term_plural || source.display_name || '').trim();
  const acronym = String(source.proposal_acronym || '').trim();
  return acronym && plural && !plural.includes(`(${acronym})`) ? `${plural} (${acronym}s)` : plural;
}

function buildClassificationDimensions(source) {
  const dimensions = source.classification?.dimensions || {};
  return Object.keys(dimensions).map((field) => ({
    field,
    label: titleCase(field),
  }));
}

function buildSourceConfig(ecosystemSlug, sourceSlug, source) {
  const frontend = source.frontend || {};
  const sourceId = cleanText(frontend.source_id || source.document_prefix || sourceSlug);
  const acronym = cleanText(source.proposal_acronym);

  return {
    sourceId,
    sourceSlug,
    acronym,
    label: cleanText(source.display_name),
    shortLabel: frontend.short_label || sourceShortLabel(source),
    proposalPlural: frontend.proposal_plural || proposalPluralWithAcronym(source),
    proposalShortPlural: frontend.proposal_short_plural || sourceShortLabel(source),
    proposalTermSingular: source.proposal_term_singular,
    proposalTermPlural: source.proposal_term_plural,
    sourceRepositories: [`github/${source.repository_owner}/${source.repository_name}`],
    dataPath: source.analysis,
    classificationDimensions: buildClassificationDimensions(source),
    classificationChordBadgeOffsets: frontend.classification_chord_badge_offsets || {},
    complianceStandards: frontend.compliance_standards || [],
    complianceChecker: source.compliance_checker || null,
    documentPrefix: source.document_prefix,
    primaryIdField: source.primary_id_field,
    referencePattern: source.reference_pattern,
    maxProposalId: source.max_proposal_id,
    repositoryOwner: source.repository_owner,
    repositoryName: source.repository_name,
    currentBaseUrl: cleanText(source.current_base_url),
    ecosystemSlug,
  };
}

function buildEcosystemConfig(filePath) {
  const ecosystem = yaml.load(fs.readFileSync(filePath, 'utf8')) || {};
  const slug = ecosystem.slug || path.basename(filePath, '.yml');
  const frontend = ecosystem.frontend || {};
  const sourceEntries = Object.entries(ecosystem.sources || {});
  const builtSources = sourceEntries.map(([sourceSlug, source]) => (
    buildSourceConfig(slug, sourceSlug, source || {})
  ));
  const sources = Object.fromEntries(builtSources.map((source) => [source.sourceId, source]));
  const sourceOrder = builtSources.map((source) => source.sourceId);
  const defaultSourceId = frontend.default_source_id || sourceOrder[0] || null;
  const defaultSource = defaultSourceId ? sources[defaultSourceId] : {};
  const name = cleanText(ecosystem.display_name) || titleCase(slug);
  const ecosystemAcronym = cleanText(frontend.acronym) || defaultSource.acronym;
  const ecosystemProposalPlural = cleanText(frontend.proposal_plural) || defaultSource.proposalPlural;
  const ecosystemProposalShortPlural = cleanText(frontend.proposal_short_plural) || defaultSource.proposalShortPlural;

  return {
    id: slug,
    name,
    status: cleanText(frontend.status) || (sourceOrder.length ? 'available' : 'coming-soon'),
    description: cleanText(frontend.description) || `Improvement proposals across the ${name} ecosystem`,
    ecosystemDescription: cleanText(frontend.ecosystem_description),
    sources,
    sourceOrder,
    defaultSourceId,
    ...defaultSource,
    acronym: ecosystemAcronym,
    proposalPlural: ecosystemProposalPlural,
    proposalShortPlural: ecosystemProposalShortPlural,
  };
}

function buildIndex() {
  if (!fs.existsSync(ecosystemsRoot)) {
    return [];
  }

  return fs.readdirSync(ecosystemsRoot)
    .filter((fileName) => fileName.endsWith('.yml'))
    .sort()
    .map((fileName) => buildEcosystemConfig(path.join(ecosystemsRoot, fileName)));
}

fs.mkdirSync(outputDir, { recursive: true });
fs.writeFileSync(tempOutputPath, `${JSON.stringify(buildIndex(), null, 2)}\n`, 'utf8');
fs.renameSync(tempOutputPath, outputPath);
console.log(`Wrote ${path.relative(reactRoot, outputPath)}`);
