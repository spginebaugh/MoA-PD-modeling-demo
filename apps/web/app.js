const API = window.location.origin;
let pathways = [];
let contract = null;
let pathwayDefinition = null;
let latestGraph = null;
let latestCompiled = null;
let latestSimulation = null;
let latestWarnings = [];
let heroState = null;
let preferredClaimTarget = '';
let claimTargetTouched = false;
let evidencePapers = [];
let evidenceCache = {};
let loadedPaperId = null;
let evidencePaperId = null;
let pathwayAnchorIndex = {};

async function getJson(path) {
  const res = await fetch(API + path);
  if (!res.ok) throw new Error(`${path} failed (${res.status}): ${await res.text()}`);
  return await res.json();
}

async function postJson(path, body) {
  const res = await fetch(API + path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  });
  if (!res.ok) throw new Error(await formatApiError(path, res));
  return await res.json();
}

async function formatApiError(path, res) {
  const body = await res.text();
  try {
    const parsed = JSON.parse(body);
    const messages = (parsed.errors || []).map(error => {
      const params = error.details?.parameters;
      const suffix = Array.isArray(params) && params.length ? ` (${params.join(', ')})` : '';
      return `${error.message}${suffix}`;
    });
    if (messages.length) return `${path} failed (${res.status}): ${messages.join(' ')}`;
  } catch {
    // Fall back to the raw body below.
  }
  return `${path} failed (${res.status}): ${body}`;
}

function esc(value) {
  return String(value).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function setStatus(message, isWarning=false) {
  const el = document.getElementById('status');
  el.className = isWarning ? 'panel warning' : 'panel muted';
  el.textContent = message;
}

function optionsHTML(options, selected=null) {
  return (options || []).map(opt => {
    const value = opt.value ?? opt.pathway_id ?? opt;
    const label = opt.label ?? value;
    return `<option value="${esc(value)}"${value === selected ? ' selected' : ''}>${esc(label)}</option>`;
  }).join('');
}

function currentPathwayId() {
  return document.getElementById('pathway').value;
}

function simulationSettings() {
  return {
    dose: parseFloat(document.getElementById('dose').value || '1'),
    t_end: 48,
    n_points: 161,
    exposure_mode: document.getElementById('exposure-mode').value
  };
}

function selectedStructuredModules() {
  const moduleId = document.getElementById('claim-module').value;
  return moduleId ? [moduleId] : [];
}

function scenarioRequest(extra={}) {
  return {
    pathway_id: currentPathwayId(),
    configuration: document.getElementById('configuration').value || null,
    ...extra
  };
}

function structuredBaseRequest(extra={}) {
  return {
    pathway_id: currentPathwayId(),
    include_modules: selectedStructuredModules(),
    ...extra
  };
}

async function loadInitial() {
  const response = await getJson('/pathways');
  pathways = response.pathways || [];
  document.getElementById('pathway').innerHTML = optionsHTML(pathways);
  await loadPapersList();
  await loadSelectedPathway();
}

async function loadPapersList() {
  try {
    const response = await getJson('/annotation-graphs');
    evidencePapers = response.paper_ids || [];
  } catch {
    evidencePapers = [];
  }
}

async function loadSelectedPathway() {
  const pathwayId = currentPathwayId();
  const [contractResponse, pathwayResponse] = await Promise.all([
    getJson(`/pathways/${pathwayId}/contract`),
    getJson(`/pathways/${pathwayId}`)
  ]);
  contract = contractResponse.contract;
  pathwayDefinition = pathwayResponse.pathway;
  document.getElementById('configuration').innerHTML = optionsHTML(contract.configurations, contract.configurations[0]?.value);
  document.getElementById('claim-effect').innerHTML = effectOptionsHTML('inhibits_edge');
  document.getElementById('claim-module').innerHTML = moduleOptionsHTML();
  const predictionClaims = contract.prediction_claims || [];
  document.getElementById('prediction-claim').innerHTML = predictionClaims.length
    ? optionsHTML(predictionClaims)
    : '<option value="">No prediction tasks configured</option>';
  updatePathwayControls();
  renderPathwayContext();
  loadedPaperId = paperIdForPathway();
  evidencePaperId = loadedPaperId || evidencePapers[0] || null;
  await ensurePathwayAnchors();
  await runScenario();
  refreshEvidencePanel();
}

function updatePathwayControls() {
  const predictionClaims = contract?.prediction_claims || [];
  const predictionSelect = document.getElementById('prediction-claim');
  const predictionButton = document.getElementById('prediction-button');
  const predictionDisabled = predictionClaims.length === 0;
  predictionSelect.disabled = predictionDisabled;
  predictionButton.disabled = predictionDisabled;
  predictionButton.title = predictionDisabled
    ? 'This pathway has no configured graph-patch prediction tasks.'
    : '';

  const moduleSelect = document.getElementById('claim-module');
  const hasModules = (contract?.modules || []).length > 0;
  moduleSelect.disabled = !hasModules;
  moduleSelect.title = hasModules ? '' : 'No optional pathway modules are configured for this pathway.';
}

function renderPathwayContext() {
  const host = document.getElementById('pathwayContext');
  if (!pathwayDefinition) {
    host.className = 'panel muted';
    host.textContent = 'No pathway loaded.';
    return;
  }
  const context = pathwayDefinition.context || {};
  const ext = context.extension || {};
  const metadata = pathwayDefinition.metadata || {};
  const chips = [
    ['Species', context.species],
    ['Endpoint', context.endpoint],
    ['Disease', ext.disease || ext.disease_subtype],
    ['Stage', ext.translation_stage],
    ['Paper', ext.paper_id || metadata.paper_id],
    ['Scale', ext.state_scale || metadata.state_scale]
  ].filter(([, value]) => value != null && value !== '');
  const deferred = Array.isArray(metadata.deferred_components) ? metadata.deferred_components : [];
  const notes = Array.isArray(metadata.curation_notes) ? metadata.curation_notes : [];
  host.className = 'panel pathway-context';
  host.innerHTML =
    `<div class="ctx-title">${esc(pathwayDefinition.label || pathwayDefinition.pathway_id)}</div>` +
    `<div class="ctx-grid">${chips.map(([key, value]) => `<span><b>${esc(key)}</b>${esc(value)}</span>`).join('')}</div>` +
    (context.notes ? `<div class="ctx-note">${esc(context.notes)}</div>` : '') +
    (deferred.length ? `<div class="ctx-subhead">Deferred</div><div class="chip-row">${deferred.map(item => `<span class="chip">${esc(item)}</span>`).join('')}</div>` : '') +
    (notes.length ? `<div class="ctx-subhead">Curation</div>${notes.map(item => `<div class="ctx-note">${esc(item)}</div>`).join('')}` : '');
}

// --- Source paper evidence: data loading -------------------------------------

function paperIdForPathway() {
  const ext = pathwayDefinition?.context?.extension || {};
  return ext.paper_id || pathwayDefinition?.metadata?.paper_id || null;
}

function pathwayIdsSet() {
  return new Set((pathways || []).map(item => item.pathway_id ?? item.value ?? item));
}

function selectPathway(pathwayId) {
  const select = document.getElementById('pathway');
  if (Array.from(select.options).some(option => option.value === pathwayId)) {
    select.value = pathwayId;
    loadSelectedPathway().catch(err => setStatus(err.message, true));
  }
}

async function loadEvidenceArtifacts(paperId) {
  if (!paperId) return null;
  if (evidenceCache[paperId]) return evidenceCache[paperId];
  try {
    const [curatedResponse, proposalResponse, evidenceResponse] = await Promise.all([
      getJson(`/annotation-graphs/${paperId}/curated`),
      getJson(`/annotation-graphs/${paperId}/proposal`),
      getJson(`/annotation-graphs/${paperId}`)
    ]);
    const anchors = {};
    (evidenceResponse.graph.evidence_anchors || []).forEach(anchor => { anchors[anchor.anchor_id] = anchor; });
    (curatedResponse.graph.evidence_anchors || []).forEach(anchor => {
      anchors[anchor.anchor_id] = anchors[anchor.anchor_id] || anchor;
    });
    const artifacts = { curated: curatedResponse.graph, proposal: proposalResponse.proposal, anchors };
    evidenceCache[paperId] = artifacts;
    return artifacts;
  } catch (err) {
    const artifacts = { error: err.message };
    evidenceCache[paperId] = artifacts;
    return artifacts;
  }
}

async function ensurePathwayAnchors() {
  pathwayAnchorIndex = {};
  if (!loadedPaperId) return;
  const artifacts = await loadEvidenceArtifacts(loadedPaperId);
  if (artifacts && !artifacts.error) pathwayAnchorIndex = artifacts.anchors;
}

async function refreshEvidencePanel() {
  if (evidencePaperId && !evidenceCache[evidencePaperId]) {
    renderEvidencePanel();
    await loadEvidenceArtifacts(evidencePaperId);
  }
  renderEvidencePanel();
}

async function viewEvidencePaper(paperId) {
  evidencePaperId = paperId;
  if (evidenceCache[paperId]?.error) delete evidenceCache[paperId];
  await refreshEvidencePanel();
}

// --- Semantic badges and resolvable evidence anchors -------------------------

const SEMANTIC_BADGES = {
  review_status: {
    accepted_for_evidence_graph: ['info', 'Accepted (evidence)'],
    candidate_for_pathway_patch: ['good', 'Candidate for pathway'],
    review_only: ['warn', 'Review only'],
    rejected: ['bad', 'Rejected']
  },
  verdict: {
    verified_therapeutic_moa: ['good', 'Verified MoA'],
    verified_supporting: ['good', 'Verified'],
    model_derived_pd_relation: ['info', 'Model-derived PD'],
    unverified: ['warn', 'Unverified'],
    refuted: ['bad', 'Refuted']
  },
  support_level: {
    model_form_supported: ['good', 'Model-form supported'],
    model_endpoint_supported: ['info', 'Endpoint supported'],
    model_derived_pd_relation: ['info', 'Model-derived PD'],
    review_only_context: ['warn', 'Review-only context']
  },
  role: {
    calibration_or_validation_endpoint: ['warn', 'Calibration endpoint'],
    pk_exposure_endpoint: ['warn', 'Exposure endpoint'],
    pd_endpoint: ['warn', 'PD endpoint'],
    review_only_candidate_input: ['warn', 'Review-only input']
  }
};

function humanize(value) {
  return String(value).replace(/_/g, ' ').replace(/\s+/g, ' ').trim().replace(/^\w/, char => char.toUpperCase());
}

function truncate(text, max) {
  const value = String(text);
  return value.length > max ? `${value.slice(0, max - 1)}…` : value;
}

function semanticBadge(kind, value) {
  if (value == null || value === '') return '';
  const [cls, label] = (SEMANTIC_BADGES[kind] || {})[value] || ['neutral', humanize(value)];
  return `<span class="sbadge ${cls}" title="${esc(value)}">${esc(label)}</span>`;
}

function badgeSet(kind, value) {
  const items = Array.isArray(value) ? value : String(value).split(/\s*;\s*/);
  return items.filter(Boolean).map(item => semanticBadge(kind, item.trim())).join(' ');
}

function prettyId(id) {
  const match = String(id).match(/^([a-zA-Z]+)[ _:-]?0*(\d+)$/);
  return match ? `${match[1].replace(/^\w/, char => char.toUpperCase())} ${match[2]}` : String(id);
}

function anchorLocator(anchor) {
  const bits = [];
  if (anchor.section) bits.push(anchor.section);
  if (anchor.figure_id) bits.push(prettyId(anchor.figure_id));
  if (anchor.table_id) bits.push(prettyId(anchor.table_id));
  const cell = anchor.cell_id || [anchor.row_id, anchor.column_id].filter(Boolean).join('');
  if (cell) bits.push(cell);
  if (!bits.length && anchor.chunk_id) bits.push(anchor.chunk_id);
  return bits.join(' · ') || anchor.source_type || 'source';
}

function anchorChips(ids, index = pathwayAnchorIndex) {
  const items = listValues(ids);
  if (!items.length) return '<span class="muted">none</span>';
  return `<div class="anchor-list">` + items.map(id => {
    const anchor = index[id];
    if (!anchor) return `<code class="chip code" title="Anchor not resolved">${esc(id)}</code>`;
    const quote = anchor.quote ? `<span class="q">${esc(truncate(anchor.quote, 180))}</span>` : '';
    return `<div class="anchor" title="${esc(anchor.quote || id)}"><span class="loc">${esc(anchorLocator(anchor))}</span>${quote}</div>`;
  }).join('') + `</div>`;
}

// --- Source paper evidence: rendering ----------------------------------------

function renderStatusLegend() {
  const items = [['good', 'Candidate / verified'], ['info', 'Model-derived'], ['warn', 'Review-only / calibration'], ['bad', 'Rejected']];
  return `<div class="status-legend">${items.map(([cls, label]) => `<span class="sbadge ${cls}">${esc(label)}</span>`).join('')}</div>`;
}

function renderPaperSwitcher() {
  return `<div class="paper-switcher">` + evidencePapers.map(paperId => {
    const active = paperId === evidencePaperId ? ' active' : '';
    const sourceDot = paperId === loadedPaperId ? '<span class="src-dot" title="Source of the loaded pathway">●</span> ' : '';
    return `<button type="button" class="paper-chip${active}" onclick="viewEvidencePaper('${esc(paperId)}')">${sourceDot}${esc(paperId)}</button>`;
  }).join('') + `</div>`;
}

function renderEvidencePanel() {
  const host = document.getElementById('evidencePanel');
  if (!host) return;
  if (!evidencePapers.length) {
    host.className = 'panel muted';
    host.textContent = 'No extracted paper evidence is available.';
    return;
  }
  host.className = 'panel evidence-panel';
  const header = `<div class="evi-head"><h2>Source paper evidence</h2>${renderStatusLegend()}</div>` +
    renderPaperSwitcher() +
    (loadedPaperId
      ? '<div class="src-caption">● marks the paper backing the loaded pathway.</div>'
      : '<div class="src-caption">The loaded pathway has no source paper; browsing extracted paper evidence.</div>');
  if (!evidencePaperId) {
    host.innerHTML = `${header}<div class="muted">Select a paper to view its extracted evidence.</div>`;
    return;
  }
  const artifacts = evidenceCache[evidencePaperId];
  if (!artifacts) {
    host.innerHTML = `${header}<div class="muted">Loading evidence for ${esc(evidencePaperId)}…</div>`;
    return;
  }
  if (artifacts.error) {
    host.innerHTML = `${header}<div class="warning">Could not load evidence for ${esc(evidencePaperId)}: ${esc(artifacts.error)}</div>`;
    return;
  }
  const { curated, anchors } = artifacts;
  host.innerHTML = header +
    `<div class="evi-paper-title">${esc(curated.title || evidencePaperId)}</div>` +
    renderPromotionGap(artifacts) +
    `<details class="ref" open><summary>Curated MoA evidence graph (${curated.nodes.length} nodes · ${curated.edges.length} edges)</summary>${renderCuratedGraph(curated)}</details>` +
    `<details class="ref"><summary>Causal &amp; model edges (${curated.edges.length})</summary>${renderCuratedEdges(curated, anchors)}</details>` +
    `<details class="ref"><summary>Parameters &amp; calibration endpoints (${curated.parameters.length})</summary>${renderCuratedParameters(curated, anchors)}</details>` +
    `<details class="ref"><summary>Paper equations &amp; model forms (${curated.equations.length})</summary>${renderCuratedEquations(curated, anchors)}</details>`;
}

function reviewStatusCounts(records) {
  const counts = { candidate: 0, review: 0, other: 0 };
  (records || []).forEach(record => {
    if (record.review_status === 'candidate_for_pathway_patch') counts.candidate += 1;
    else if (record.review_status === 'review_only') counts.review += 1;
    else counts.other += 1;
  });
  return counts;
}

function coverageTile(label, counts) {
  const total = counts.candidate + counts.review + counts.other || 1;
  const goodPct = (counts.candidate / total * 100).toFixed(1);
  const warnPct = (counts.review / total * 100).toFixed(1);
  const other = counts.other ? ` · ${counts.other} other` : '';
  return `<div class="promo-stat"><div class="promo-stat-h">${esc(label)}</div>` +
    `<div class="cov-bar"><span class="cov-good" style="width:${goodPct}%"></span><span class="cov-warn" style="width:${warnPct}%"></span></div>` +
    `<div class="promo-stat-sub">${counts.candidate} candidate · ${counts.review} review-only${other}</div></div>`;
}

function dedupeMissing(items) {
  const seen = new Map();
  items.forEach(item => { if (!seen.has(item.name)) seen.set(item.name, item); });
  return Array.from(seen.values());
}

function renderPromotionGap(artifacts) {
  const { curated, proposal } = artifacts;
  const nodeCounts = reviewStatusCounts(curated.nodes);
  const edgeCounts = reviewStatusCounts(curated.edges);
  const paramCounts = reviewStatusCounts(curated.parameters);
  const equationCounts = reviewStatusCounts(curated.equations);
  const knownPathways = pathwayIdsSet();
  const loadButton = id => id === currentPathwayId()
    ? ''
    : `<button type="button" class="link-btn" onclick="selectPathway('${esc(id)}')">load it</button>`;
  const proposedExists = proposal.proposed_pathway_id && knownPathways.has(proposal.proposed_pathway_id);
  const targetExists = proposal.target_pathway_id && knownPathways.has(proposal.target_pathway_id);
  const isLoaded = proposedExists && proposal.proposed_pathway_id === currentPathwayId();
  let banner;
  let bannerClass;
  if (proposal.proposal_kind === 'new_pathway' && proposedExists) {
    bannerClass = 'has-exec';
    banner = isLoaded
      ? `Executable slice loaded: <b>${esc(pathwayDefinition.label || proposal.proposed_pathway_id)}</b>`
      : `Executable slice available: <code>${esc(proposal.proposed_pathway_id)}</code>${loadButton(proposal.proposed_pathway_id)}`;
  } else if (proposal.proposal_kind === 'overlay') {
    bannerClass = 'no-exec';
    const target = targetExists
      ? `<code>${esc(proposal.target_pathway_id)}</code>${loadButton(proposal.target_pathway_id)}`
      : esc(proposal.target_pathway_id || 'an existing pathway');
    banner = `Overlay review artifact — proposes evidence onto ${target}; not a standalone executable pathway.`;
  } else {
    bannerClass = 'no-exec';
    banner = `No executable pathway yet — ${esc(humanize(proposal.proposal_kind))} review artifact only.`;
  }
  const missing = dedupeMissing([...(curated.missing_inputs || []), ...(proposal.required_missing_inputs || [])]);
  const deferred = isLoaded ? (pathwayDefinition.metadata?.deferred_components || []) : [];
  const calloutNeeded = paramCounts.candidate === 0 && paramCounts.review > 0;
  return '<div class="promo">' +
    `<div class="promo-banner ${bannerClass}">${banner}<div class="muted">${esc(proposal.promotion_note || curated.promotion_note || '')}</div></div>` +
    `<div class="promo-grid">${coverageTile('Nodes', nodeCounts)}${coverageTile('Edges', edgeCounts)}${coverageTile('Parameters', paramCounts)}${coverageTile('Equations', equationCounts)}</div>` +
    (calloutNeeded ? `<div class="promo-callout">All ${paramCounts.review} curated parameters are <b>review-only</b> — none are safe to promote to executable priors. The executable slice substitutes explicit prototype priors instead.</div>` : '') +
    (missing.length ? '<div class="prov-subhead">Missing inputs blocking full execution</div>' + missing.map(item =>
      `<div class="gap-item"><span class="sbadge ${item.severity === 'error' ? 'bad' : 'warn'}">${esc(item.severity || 'warning')}</span>` +
      `<div><b>${esc(humanize(item.name))}</b><div class="muted">${esc(item.reason || '')}</div></div></div>`).join('') : '') +
    (deferred.length ? `<div class="prov-subhead">Deferred from the executable slice</div><div class="chip-row">${deferred.map(item => `<span class="chip">${esc(item)}</span>`).join('')}</div>` : '') +
    '</div>';
}

function layerNodes(nodes, edges) {
  const ids = nodes.map(node => node.node_id);
  const idSet = new Set(ids);
  const adjacency = {};
  const indegree = {};
  ids.forEach(id => { adjacency[id] = []; indegree[id] = 0; });
  edges.forEach(edge => {
    if (idSet.has(edge.source) && idSet.has(edge.target) && edge.source !== edge.target) {
      adjacency[edge.source].push(edge.target);
      indegree[edge.target] += 1;
    }
  });
  const layer = {};
  ids.forEach(id => { layer[id] = 0; });
  const queue = ids.filter(id => indegree[id] === 0);
  const remaining = { ...indegree };
  while (queue.length) {
    const id = queue.shift();
    adjacency[id].forEach(target => {
      layer[target] = Math.max(layer[target], layer[id] + 1);
      remaining[target] -= 1;
      if (remaining[target] === 0) queue.push(target);
    });
  }
  const byLayer = {};
  ids.forEach(id => { (byLayer[layer[id]] = byLayer[layer[id]] || []).push(id); });
  const positions = {};
  Object.keys(byLayer).map(Number).sort((a, b) => a - b).forEach(col => {
    byLayer[col].forEach((id, row) => { positions[id] = { col, row }; });
  });
  return positions;
}

function gridLayout(nodes, columns = 4) {
  const positions = {};
  nodes.forEach((node, index) => { positions[node.node_id] = { col: index % columns, row: Math.floor(index / columns) }; });
  return positions;
}

function curatedRelationStyle(relation) {
  const negative = /inhibit|suppress|block|degrade|decreas|down/i.test(relation);
  return { color: negative ? '#B34C4C' : '#2D7A57', marker: negative ? 'tee' : 'arrow' };
}

function statusFill(reviewStatus) {
  if (reviewStatus === 'candidate_for_pathway_patch') return { fill: '#E8F4EE', stroke: '#2D7A57', text: '#173D2B' };
  if (reviewStatus === 'review_only') return { fill: '#FFF7ED', stroke: '#C2772E', text: '#7C3A12' };
  if (reviewStatus === 'rejected') return { fill: '#FEECEC', stroke: '#B34C4C', text: '#7F1D1D' };
  return { fill: '#EEF2F7', stroke: '#64748B', text: '#334155' };
}

function renderCuratedGraph(curated) {
  const nodes = curated.nodes || [];
  const edges = curated.edges || [];
  if (!nodes.length) return '<div class="muted">No curated nodes.</div>';
  const positions = edges.length ? layerNodes(nodes, edges) : gridLayout(nodes);
  const COL_W = 184, ROW_H = 66, NODE_W = 152, NODE_H = 34, PAD = 22;
  let maxCol = 0, maxRow = 0;
  nodes.forEach(node => {
    const position = positions[node.node_id];
    maxCol = Math.max(maxCol, position.col);
    maxRow = Math.max(maxRow, position.row);
  });
  const viewWidth = PAD * 2 + maxCol * COL_W + NODE_W;
  const viewHeight = PAD * 2 + maxRow * ROW_H + NODE_H;
  const center = id => {
    const position = positions[id];
    return { x: PAD + position.col * COL_W + NODE_W / 2, y: PAD + position.row * ROW_H + NODE_H / 2 };
  };
  const boundary = (point, tx, ty) => {
    const dx = tx - point.x, dy = ty - point.y;
    if (!dx && !dy) return [point.x, point.y];
    const scale = Math.min(
      Math.abs(dx) > 1e-6 ? (NODE_W / 2) / Math.abs(dx) : Infinity,
      Math.abs(dy) > 1e-6 ? (NODE_H / 2) / Math.abs(dy) : Infinity
    );
    return [point.x + dx * scale, point.y + dy * scale];
  };
  const nodeById = Object.fromEntries(nodes.map(node => [node.node_id, node]));
  const defs = '<defs>' +
    '<marker id="cur-arrow" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto" markerUnits="strokeWidth"><path d="M0,0 L0,6 L8,3 z" fill="#2D7A57"/></marker>' +
    '<marker id="cur-tee" markerWidth="8" markerHeight="10" refX="1" refY="5" orient="auto" markerUnits="strokeWidth"><rect x="0" y="1" width="2" height="8" fill="#B34C4C"/></marker>' +
    '</defs>';
  let edgeSvg = '';
  edges.forEach(edge => {
    const source = nodeById[edge.source], target = nodeById[edge.target];
    if (!source || !target) return;
    const sourceCenter = center(edge.source), targetCenter = center(edge.target);
    const [x1, y1] = boundary(sourceCenter, targetCenter.x, targetCenter.y);
    const [x2, y2] = boundary(targetCenter, sourceCenter.x, sourceCenter.y);
    const style = curatedRelationStyle(edge.relation);
    const dash = edge.review_status === 'review_only' ? ' stroke-dasharray="5 4"' : '';
    edgeSvg += `<line x1="${x1.toFixed(1)}" y1="${y1.toFixed(1)}" x2="${x2.toFixed(1)}" y2="${y2.toFixed(1)}" stroke="${style.color}" stroke-width="1.8"${dash} marker-end="url(#${style.marker === 'tee' ? 'cur-tee' : 'cur-arrow'})"><title>${esc(humanize(edge.relation))}: ${esc(source.label)} → ${esc(target.label)}</title></line>`;
  });
  const nodeSvg = nodes.map(node => {
    const point = center(node.node_id);
    const fill = statusFill(node.review_status);
    return `<g><title>${esc(node.label)} — ${esc(humanize(node.review_status))}${node.reason ? ': ' + esc(node.reason) : ''}</title>` +
      `<rect x="${(point.x - NODE_W / 2).toFixed(1)}" y="${(point.y - NODE_H / 2).toFixed(1)}" width="${NODE_W}" height="${NODE_H}" rx="8" fill="${fill.fill}" stroke="${fill.stroke}" stroke-width="1.5"/>` +
      `<text x="${point.x.toFixed(1)}" y="${point.y.toFixed(1)}" text-anchor="middle" dominant-baseline="central" style="fill:${fill.text};font-size:11px;font-weight:700">${esc(truncate(node.label, 20))}</text></g>`;
  }).join('');
  return `<svg class="curated-svg" viewBox="0 0 ${viewWidth.toFixed(0)} ${viewHeight.toFixed(0)}" role="img" aria-label="Curated paper MoA evidence graph">${defs}${edgeSvg}${nodeSvg}</svg>`;
}

function renderCuratedEdges(curated, anchors) {
  const edges = curated.edges || [];
  if (!edges.length) return '<div class="muted">No causal or model edges were extracted for this paper.</div>';
  const labelById = Object.fromEntries((curated.nodes || []).map(node => [node.node_id, node.label]));
  return edges.map(edge => {
    const source = labelById[edge.source] || edge.source;
    const target = labelById[edge.target] || edge.target;
    const meta = [humanize(edge.relation), edge.causal_role ? humanize(edge.causal_role) : ''].filter(Boolean).join(' · ');
    return '<div class="prov-card">' +
      `<div class="prov-title"><b>${esc(source)} → ${esc(target)}</b></div>` +
      `<div class="evi-badges">${semanticBadge('review_status', edge.review_status)} ${semanticBadge('support_level', edge.support_level)}</div>` +
      `<div class="muted">${esc(meta)}</div>` +
      (edge.reason ? `<div class="evi-reason">${esc(edge.reason)}</div>` : '') +
      `<div class="prov-subhead">Evidence</div>${anchorChips(edge.evidence_anchor_ids, anchors)}` +
      '</div>';
  }).join('');
}

function renderCuratedParameters(curated, anchors) {
  const parameters = curated.parameters || [];
  if (!parameters.length) return '<div class="muted">No parameters were extracted for this paper.</div>';
  return parameters.map(parameter => {
    const value = parameter.value == null
      ? (parameter.value_text || '—')
      : `${fmtNum(parameter.value)}${parameter.unit ? ` ${parameter.unit}` : ''}`;
    const blockers = (parameter.promotion_blockers || []).map(blocker => `<span class="sbadge bad" title="promotion blocker">${esc(humanize(blocker))}</span>`).join(' ');
    return `<div class="param-card"><div class="param-head"><b>${esc(parameter.name)}</b><span>${esc(value)}</span></div>` +
      `<div class="evi-badges">${semanticBadge('review_status', parameter.review_status)} ${semanticBadge('role', parameter.role)}</div>` +
      (parameter.reason ? `<div class="evi-reason">${esc(parameter.reason)}</div>` : '') +
      (blockers ? `<div class="evi-badges">${blockers}</div>` : '') +
      `<div class="prov-subhead">Evidence</div>${anchorChips(parameter.evidence_anchor_ids, anchors)}</div>`;
  }).join('');
}

function renderCuratedEquations(curated, anchors) {
  const equations = curated.equations || [];
  if (!equations.length) return '<div class="muted">No equations or model forms were extracted for this paper.</div>';
  const execNodeIds = new Set((pathwayDefinition?.base_graph?.nodes || []).map(node => node.metadata?.extension?.curated_node_id).filter(Boolean));
  const execEdgeIds = new Set((pathwayDefinition?.base_graph?.edges || []).map(edge => edge.metadata?.extension?.curated_edge_id).filter(Boolean));
  const showExecTag = loadedPaperId === curated.paper_id;
  return equations.map(equation => {
    const inExec = (equation.target_node_id && execNodeIds.has(equation.target_node_id)) ||
      (equation.target_edge_id && execEdgeIds.has(equation.target_edge_id));
    const execTag = showExecTag
      ? (inExec
        ? '<span class="sbadge good" title="Target exists in the loaded executable slice">In executable slice</span>'
        : '<span class="sbadge neutral">Not in executable slice</span>')
      : '';
    const target = equation.target_node_id || equation.target_edge_id;
    const meta = [humanize(equation.binding_type), target ? `target ${target}` : ''].filter(Boolean).join(' · ');
    return `<div class="param-card"><div class="param-head"><b>${esc(equation.model_form || equation.equation_id)}</b><div class="evi-badges">${semanticBadge('review_status', equation.review_status)} ${execTag}</div></div>` +
      `<div class="eq-expr"><code>${esc(equation.expression_text)}</code></div>` +
      `<div class="muted">${esc(meta)}</div>` +
      (equation.reason ? `<div class="evi-reason">${esc(equation.reason)}</div>` : '') +
      `<div class="prov-subhead">Evidence</div>${anchorChips(equation.evidence_anchor_ids, anchors)}</div>`;
  }).join('');
}

async function compileAndSimulate(graph) {
  const compiled = await postJson('/model/compile', { pathway_id: currentPathwayId(), graph });
  latestCompiled = compiled.model;
  if (!compiled.ok) {
    renderEquations(latestCompiled);
    throw new Error(`Compiled graph is diagnostic-only: ${(compiled.errors || []).map(w => w.message).join(' ')}`);
  }
  const simulation = await postJson('/simulate', {
    compiled_model: latestCompiled,
    settings: simulationSettings()
  });
  latestSimulation = simulation.result;
  latestWarnings = [...(compiled.warnings || []), ...(simulation.warnings || [])];
}

function effectOptionsHTML(selected=null) {
  return (contract?.modifier_relations || []).map(effect => {
    const value = effect.value;
    const label = String(effect.label || value).replace(/\s+edge$/i, '');
    return `<option value="${esc(value)}"${value === selected ? ' selected' : ''}>${esc(label)}</option>`;
  }).join('');
}

function moduleOptionsHTML(selected='') {
  const options = [{ value: '', label: 'None' }, ...(contract?.modules || [])];
  return options.map(module => {
    const value = module.value;
    return `<option value="${esc(value)}"${value === selected ? ' selected' : ''}>${esc(module.label)}</option>`;
  }).join('');
}

function syncStructuredModuleFromGraph(graph) {
  const select = document.getElementById('claim-module');
  const available = new Set(Array.from(select.options).map(option => option.value));
  const active = (graph?.metadata?.included_modules || []).find(module => available.has(module));
  select.value = active || '';
}

async function runScenario() {
  try {
    setStatus('Composing graph, compiling equations, and simulating...');
    const response = await postJson('/graph/compose', scenarioRequest());
    latestGraph = response.graph;
    await compileAndSimulate(latestGraph);
    syncStructuredModuleFromGraph(latestGraph);
    renderAll();
    document.getElementById('prediction').className = 'muted';
    document.getElementById('prediction').textContent = 'No structured patch applied.';
    setStatus(`Loaded ${latestGraph.label}.`);
  } catch (err) {
    setStatus(err.message, true);
  }
}

async function runStructuredBase() {
  try {
    claimTargetTouched = false;
    preferredClaimTarget = '';
    setStatus('Composing structured claim base graph, compiling equations, and simulating...');
    const response = await postJson('/graph/compose', structuredBaseRequest());
    latestGraph = response.graph;
    await compileAndSimulate(latestGraph);
    renderAll();
    document.getElementById('prediction').className = 'muted';
    document.getElementById('prediction').textContent = 'No structured patch applied.';
    setStatus(`Loaded ${latestGraph.label}.`);
  } catch (err) {
    setStatus(err.message, true);
  }
}

async function runStructuredClaim() {
  try {
    if (!latestGraph) throw new Error('Compose a graph before applying an edge modifier.');
    const relation = document.getElementById('claim-effect').value;
    const target = document.getElementById('claim-target').value;
    if (!target) throw new Error('Select a target edge.');
    const expression = structuredModifierExpression(relation);
    setStatus('Applying structured drug modifier and simulating...');
    const sign = relation === 'inhibits_edge' ? '-' : '+';
    const response = await postJson('/graph/compose', structuredBaseRequest({
      ad_hoc_modifiers: [{
        target_edge: target,
        relation,
        sign,
        expression,
        rationale: `Structured UI ${relation} modifier on ${target}.`
      }]
    }));
    latestGraph = response.graph;
    await compileAndSimulate(latestGraph);
    renderAll();
    renderPatch('Structured patch applied', [
      `Effect: ${relation}`,
      `Target edge: ${target}`,
      `Pathway module: ${selectedStructuredModules().join(', ') || 'none'}`
    ]);
    setStatus(`Applied ${relation} to ${target}.`);
  } catch (err) {
    setStatus(err.message, true);
  }
}

function structuredModifierExpression(relation) {
  const drugState = latestGraph?.metadata?.drug_state;
  if (!drugState) throw new Error('The selected graph has no executable drug state for a structured modifier.');
  const drug = { kind: 'state_ref', state: drugState };
  const halfMax = { kind: 'constant', value: 0.75 };
  if (relation === 'inhibits_edge') {
    return { kind: 'hill_inhibition', signal: drug, half_max: halfMax };
  }
  return {
    kind: 'add',
    terms: [
      { kind: 'constant', value: 1.0 },
      {
        kind: 'saturating_activation',
        signal: drug,
        half_max: halfMax
      }
    ]
  };
}

async function runToyModel() {
  try {
    if (!latestGraph) throw new Error('Compose a graph before running graph-patch prediction.');
    const claim = selectedPredictionClaim();
    if (!claim) throw new Error('No supported prediction task is configured for this pathway.');
    setStatus('Predicting graph patch, compiling equations, and simulating...');
    const response = await postJson('/predict/operators/apply', {
      input: {
        pathway_id: currentPathwayId(),
        claim_text: claim
      },
      settings: simulationSettings()
    });
    latestGraph = response.graph;
    latestCompiled = response.compiled_model;
    latestSimulation = response.simulation;
    latestWarnings = response.warnings || [];
    syncStructuredModuleFromGraph(latestGraph);
    renderAll();
    renderToyPrediction(response.prediction, claim, latestWarnings, response);
    setStatus(`Predicted and applied graph patch through ${response.prediction.diagnostics.decision_source}.`);
  } catch (err) {
    setStatus(err.message, true);
  }
}

function selectedPredictionClaim() {
  return document.getElementById('prediction-claim').value;
}

function modifierRelations() {
  return new Set((contract?.modifier_relations || []).map(item => item.value));
}

function structuralEdges(graph) {
  if (!graph) return [];
  const modifiers = modifierRelations();
  return (graph.edges || []).filter(edge => !modifiers.has(edge.relation));
}

function nodeById(graph) {
  return Object.fromEntries((graph?.nodes || []).map(node => [node.id, node]));
}

function edgeLabel(graph, edge) {
  const nodes = nodeById(graph);
  const source = nodes[edge.source]?.label || edge.source;
  const target = nodes[edge.target]?.label || edge.target;
  const style = relationStyle(edge.relation);
  return `${source} -> ${target} (${style.label})`;
}

function selectedOptionLabel(selectId) {
  const select = document.getElementById(selectId);
  return select.selectedOptions[0]?.textContent || select.value;
}

function selectedTargetEdge() {
  const targetId = document.getElementById('claim-target').value;
  return structuralEdges(latestGraph).find(edge => edge.id === targetId) || null;
}

function rememberStructuredTarget() {
  preferredClaimTarget = document.getElementById('claim-target').value;
  claimTargetTouched = true;
}

function meaningfulTokens(text) {
  const stop = new Set(['module', 'mediated', 'receptor', 'pathway', 'turnover', 'signaling', 'with', 'and', 'the']);
  return String(text).toLowerCase().split(/[^a-z0-9]+/).filter(token => token.length >= 3 && !stop.has(token));
}

function modulePreferredEdge(edges) {
  const moduleId = document.getElementById('claim-module').value;
  if (!moduleId) return null;
  const moduleLabel = selectedOptionLabel('claim-module');
  const tokens = meaningfulTokens(`${moduleId} ${moduleLabel}`);
  if (!tokens.length) return null;
  const nodes = nodeById(latestGraph);
  const matching = edges.filter(edge => {
    const source = nodes[edge.source]?.label || edge.source;
    const target = nodes[edge.target]?.label || edge.target;
    const text = `${edge.id} ${source} ${target} ${edge.relation} ${edge.description || ''}`.toLowerCase();
    return tokens.some(token => text.includes(token));
  });
  return matching.find(edge => ['ubiquitinates', 'degrades'].includes(edge.relation)) || matching[0] || null;
}

function updateStructuredTargets() {
  const target = document.getElementById('claim-target');
  const edges = structuralEdges(latestGraph);
  const previous = preferredClaimTarget || target.value;
  target.innerHTML = edges.map(edge => `<option value="${esc(edge.id)}">${esc(edgeLabel(latestGraph, edge))}</option>`).join('') || '<option value="">No target edges</option>';
  const values = new Set(edges.map(edge => edge.id));
  const effect = document.getElementById('claim-effect');
  const structuredButton = document.getElementById('structured-claim-button');
  target.disabled = edges.length === 0;
  effect.disabled = effect.options.length === 0;
  structuredButton.disabled = edges.length === 0 || effect.options.length === 0;
  structuredButton.title = structuredButton.disabled
    ? 'No structural edge is available for a user-defined modifier.'
    : '';
  if (claimTargetTouched && values.has(previous)) {
    target.value = previous;
    return;
  }
  const moduleEdge = modulePreferredEdge(edges);
  if (moduleEdge && values.has(moduleEdge.id)) {
    target.value = moduleEdge.id;
    preferredClaimTarget = moduleEdge.id;
    if (!claimTargetTouched && Array.from(effect.options).some(option => option.value === 'activates_edge')) {
      effect.value = 'activates_edge';
    }
    return;
  }
  if (values.has(previous)) {
    target.value = previous;
    preferredClaimTarget = previous;
  } else {
    preferredClaimTarget = target.value;
  }
}

function relationStyle(relation) {
  return (contract?.presentation?.edge_relation_styles || []).find(item => item.relation === relation) ||
    { relation, label: relation, color: '#64748b', marker: 'arrow' };
}

function nodeStyle(node) {
  const style = (contract?.presentation?.node_type_styles || []).find(item => item.node_type === node.type);
  return style || { fill: '#f1f5f9', stroke: '#64748b', text: '#334155' };
}

function graphLayout(graph) {
  const configured = Object.fromEntries((contract?.presentation?.graph_layout || []).map(item => [item.node, [item.x, item.y]]));
  const nodes = graph.nodes || [];
  const pos = {};
  nodes.forEach((node, index) => {
    if (configured[node.id]) {
      pos[node.id] = configured[node.id];
    } else {
      const col = index % 5;
      const row = Math.floor(index / 5);
      pos[node.id] = [120 + col * 210, 90 + row * 130];
    }
  });
  return pos;
}

function markerId(style) {
  const kind = style.marker === 'tee' ? 'tee' : 'ah';
  const colorKey = String(style.color || '#64748b').replace(/[^a-zA-Z0-9]/g, '').toLowerCase() || '64748b';
  return `${kind}-${colorKey}`;
}

function markerDefinitions(styles) {
  const seen = new Set();
  return styles.map(style => {
    const id = markerId(style);
    if (seen.has(id)) return '';
    seen.add(id);
    const color = style.color || '#64748b';
    if (style.marker === 'tee') {
      return `<marker id="${esc(id)}" markerWidth="8" markerHeight="10" refX="1" refY="5" orient="auto" markerUnits="strokeWidth"><rect x="0" y="1" width="2" height="8" fill="${esc(color)}"/></marker>`;
    }
    return `<marker id="${esc(id)}" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto" markerUnits="strokeWidth"><path d="M0,0 L0,6 L8,3 z" fill="${esc(color)}"/></marker>`;
  }).join('');
}

function renderGraph(graph) {
  if (!graph) return;
  updateStructuredTargets();
  const nodes = graph.nodes || [];
  const nodeMap = nodeById(graph);
  const pos = graphLayout(graph);
  const structural = structuralEdges(graph);
  const structuralById = Object.fromEntries(structural.map(edge => [edge.id, edge]));
  const modifiers = (graph.edges || []).filter(edge => modifierRelations().has(edge.relation) && structuralById[edge.target]);
  const modified = new Set(modifiers.map(edge => edge.target));
  const VW = 1140, VH = 470, NODE_H = 30;
  const box = (node) => {
    const [x, y] = pos[node.id];
    const w = Math.max(64, String(node.id).length * 7.2 + 28);
    return { cx: x, cy: y, w, hw: w / 2, hh: NODE_H / 2 };
  };
  const boxes = Object.fromEntries(nodes.map(node => [node.id, box(node)]));
  const boundary = (b, tx, ty) => {
    const dx = tx - b.cx, dy = ty - b.cy;
    if (!dx && !dy) return [b.cx, b.cy];
    const s = Math.min(Math.abs(dx) > 1e-6 ? b.hw / Math.abs(dx) : Infinity, Math.abs(dy) > 1e-6 ? b.hh / Math.abs(dy) : Infinity);
    return [b.cx + dx * s, b.cy + dy * s];
  };
  const defs = markerDefinitions((graph.edges || []).map(edge => relationStyle(edge.relation)));
  let edgeSvg = '', labelSvg = '';
  structural.forEach(edge => {
    const sb = boxes[edge.source], tb = boxes[edge.target];
    if (!sb || !tb) return;
    const [x1, y1] = boundary(sb, tb.cx, tb.cy);
    const [x2, y2] = boundary(tb, sb.cx, sb.cy);
    const style = relationStyle(edge.relation);
    if (modified.has(edge.id)) edgeSvg += `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="#c4b5fd" stroke-width="7" stroke-linecap="round" opacity="0.7"/>`;
    edgeSvg += `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="${style.color}" stroke-width="${modified.has(edge.id) ? 2.6 : 1.8}" marker-end="url(#${markerId(style)})"/>`;
    labelSvg += `<text class="edge-label" x="${(x1 + x2) / 2}" y="${(y1 + y2) / 2 - 4}" text-anchor="middle">${esc(style.label)}</text>`;
  });
  modifiers.forEach(edge => {
    const target = structuralById[edge.target];
    const sourceBox = boxes[edge.source];
    if (!target || !sourceBox) return;
    const mid = [(pos[target.source][0] + pos[target.target][0]) / 2, (pos[target.source][1] + pos[target.target][1]) / 2];
    const [sx, sy] = boundary(sourceBox, mid[0], mid[1]);
    const style = relationStyle(edge.relation);
    edgeSvg += `<line x1="${sx}" y1="${sy}" x2="${mid[0]}" y2="${mid[1]}" stroke="${style.color}" stroke-width="2" stroke-dasharray="5 4" marker-end="url(#${markerId(style)})"/>`;
  });
  const nodeSvg = nodes.map(node => {
    const b = boxes[node.id], style = nodeStyle(node);
    return `<g><title>${esc(node.label || node.id)}</title><rect x="${b.cx - b.hw}" y="${b.cy - b.hh}" width="${b.w}" height="${NODE_H}" rx="8" fill="${style.fill}" stroke="${style.stroke}" stroke-width="1.5"/><text class="node-label" x="${b.cx}" y="${b.cy}" text-anchor="middle" dominant-baseline="central" style="fill:${style.text}">${esc(node.id)}</text></g>`;
  }).join('');
  document.getElementById('graph').innerHTML = `<svg viewBox="0 0 ${VW} ${VH}" role="img" aria-label="MoA mechanism graph"><defs>${defs}</defs>${edgeSvg}${nodeSvg}${labelSvg}</svg>`;
  renderGraphProvenance(graph);
}

function listValues(value) {
  if (Array.isArray(value)) return value.filter(item => item != null && item !== '');
  if (value == null || value === '') return [];
  return [value];
}

function codeChips(values) {
  const items = listValues(values);
  if (!items.length) return '';
  return `<div class="chip-row">${items.map(item => `<code class="chip code">${esc(item)}</code>`).join('')}</div>`;
}

function provenanceRows(metadata, anchorIndex = pathwayAnchorIndex) {
  const ext = metadata?.extension || {};
  const rows = [
    ['Paper', ext.paper_id, 'text'],
    ['Curated id', ext.curated_edge_id || ext.curated_node_id, 'code'],
    ['Source records', ext.source_record_ids, 'code'],
    ['Evidence', ext.evidence_anchor_ids, 'anchors'],
    ['Section', ext.source_section, 'text'],
    ['Verdict', ext.verification_verdict, 'verdict'],
    ['Review status', ext.review_status, 'review_status'],
    ['Note', ext.curation_note || ext.modeling_note, 'text']
  ];
  return rows
    .filter(([, value]) => listValues(value).length)
    .map(([label, value, type]) => {
      let rendered;
      if (type === 'anchors') rendered = anchorChips(value, anchorIndex);
      else if (type === 'code') rendered = Array.isArray(value) ? codeChips(value) : `<code class="chip code">${esc(value)}</code>`;
      else if (type === 'verdict') rendered = badgeSet('verdict', value);
      else if (type === 'review_status') rendered = semanticBadge('review_status', value);
      else rendered = esc(value);
      return `<div class="prov-row"><span>${esc(label)}</span><div>${rendered}</div></div>`;
    })
    .join('');
}

function evidenceRows(evidence) {
  const items = evidence || [];
  if (!items.length) return '<div class="muted">No evidence attached.</div>';
  return items.map(item => {
    const label = [item.source_label, item.source_type].filter(Boolean).join(' · ');
    const confidence = item.confidence == null ? '' : ` · conf ${fmtNum(item.confidence)}`;
    return `<div class="evidence-row"><b>${esc(label || 'Evidence')}</b>${esc(confidence)}<br><span>${esc(item.description || '')}</span></div>`;
  }).join('');
}

function renderGraphProvenance(graph) {
  const nodes = graph.nodes || [];
  const edges = graph.edges || [];
  const nodeRows = nodes.map(node => {
    const rows = provenanceRows(node.metadata);
    return `<div class="prov-card"><div class="prov-title"><span class="badge">${esc(node.type)}</span><b>${esc(node.label || node.id)}</b></div>${rows || '<div class="muted">No node provenance metadata.</div>'}</div>`;
  }).join('');
  const edgeRows = edges.map(edge => {
    const style = relationStyle(edge.relation);
    const rows = provenanceRows(edge.metadata);
    return `<div class="prov-card"><div class="prov-title"><span class="badge">${esc(style.label)}</span><b>${esc(edge.id)}</b></div>` +
      `<div class="muted">${esc(edge.source)} to ${esc(edge.target)} · sign ${esc(edge.sign)} · conf ${esc(edge.confidence)}</div>` +
      `<div class="prov-subhead">Evidence</div>${evidenceRows(edge.evidence)}` +
      `<div class="prov-subhead">Provenance</div>${rows || '<div class="muted">No edge provenance metadata.</div>'}</div>`;
  }).join('');
  document.getElementById('edgeList').innerHTML =
    `<div class="prov-section"><h3>Nodes</h3>${nodeRows || '<div class="muted">No nodes.</div>'}</div>` +
    `<div class="prov-section"><h3>Edges</h3>${edgeRows || '<div class="muted">No edges.</div>'}</div>`;
}

function expressionText(expr) {
  if (!expr) return '';
  if (expr.text) return expr.text;
  switch (expr.kind) {
    case 'constant': return Number.isInteger(expr.value) ? String(expr.value) : String(Number(expr.value).toPrecision(6)).replace(/\.?0+$/, '');
    case 'state_ref': return expr.state;
    case 'parameter_ref': return expr.parameter;
    case 'add': return (expr.terms || []).map(expressionText).join(' + ').replace(/\+ -/g, '- ');
    case 'multiply': {
      const factors = expr.factors || [];
      if (factors[0]?.kind === 'constant' && factors[0].value === -1) return `- ${factors.slice(1).map(factorText).join(' * ')}`;
      return factors.map(factorText).join(' * ');
    }
    case 'divide': return `${factorText(expr.numerator)} / ${factorText(expr.denominator)}`;
    case 'power': return `${factorText(expr.base)}^${expr.exponent}`;
    case 'hill_inhibition': return `1 / (1 + ${expressionText(expr.signal)} / ${expressionText(expr.half_max)})`;
    case 'saturating_activation': return `${expressionText(expr.signal)} / (${expressionText(expr.half_max)} + ${expressionText(expr.signal)})`;
    case 'first_order_loss': return `- ${expr.rate} * ${expr.state}`;
    default: return JSON.stringify(expr);
  }
}

function factorText(expr) {
  const text = expressionText(expr);
  return expr && expr.kind === 'add' ? `(${text})` : text;
}

function renderEquations(compiled) {
  if (!compiled) return;
  const mods = (compiled.modifiers || []).map(mod => `<div class="eq-term"><span class="badge">${esc(mod.operator)}</span><b>${esc(mod.modifier_id)}</b> on ${esc(mod.target_edge)}: <code>${esc(expressionText(mod.expression))}</code></div>`).join('');
  const terms = (compiled.terms || []).map(term => `<div class="eq-term"><span class="badge">${esc(term.operator)}</span><b>d${esc(term.state)}/dt</b> includes <code>${esc(expressionText(term.expression))}</code><br><span class="muted">source edges: ${esc((term.source_edges || []).join(', ') || 'implicit')}; modifiers: ${esc((term.modifiers || []).join(', ') || 'none')}; ${esc(term.description)}</span></div>`).join('');
  document.getElementById('equations').innerHTML = `<p><span class="badge">${esc(compiled.metadata.execution_model)}</span></p>${mods}${terms}`;
}

function sourceBlock(source) {
  if (!source) return '<div class="muted">No source recorded.</div>';
  const confidence = source.confidence == null ? '' : ` · conf ${fmtNum(source.confidence)}`;
  return `<div class="source-block"><b>${esc(source.source_label || source.source_type || 'Source')}</b>${esc(confidence)}<br>` +
    `<span>${esc(source.description || '')}</span>` +
    (source.reference ? `<br><code>${esc(source.reference)}</code>` : '') +
    `</div>`;
}

function renderParameterCatalog(compiled) {
  const host = document.getElementById('parameterList');
  if (!compiled) {
    host.className = 'muted';
    host.textContent = 'No compiled model loaded.';
    return;
  }
  const catalog = compiled.parameter_catalog || {};
  const priors = Object.values(catalog.priors || {}).sort((a, b) => String(a.id).localeCompare(String(b.id)));
  const generated = Object.values(catalog.generated || {}).sort((a, b) => String(a.id).localeCompare(String(b.id)));
  const priorRows = priors.map(parameter => {
    const bounds = [parameter.lower, parameter.upper].every(value => value != null)
      ? `bounds ${fmtNum(parameter.lower)}-${fmtNum(parameter.upper)}`
      : 'no bounds';
    const [cls, classLabel] = priorClassification(parameter.source);
    return `<div class="param-card"><div class="param-head"><b>${esc(parameter.id)}</b><span>${esc(fmtNum(parameter.value))}${parameter.units ? ` ${esc(parameter.units)}` : ''}</span></div>` +
      `<div class="evi-badges"><span class="sbadge ${cls}">${esc(classLabel)}</span></div>` +
      `<div class="muted">${esc(bounds)}</div>${sourceBlock(parameter.source)}</div>`;
  }).join('');
  const paperDerived = priors.filter(parameter => priorClassification(parameter.source)[1] === 'Paper-derived').length;
  const priorsNote = priors.length
    ? `<div class="src-caption">${priors.length} prior${priors.length === 1 ? '' : 's'} · ${paperDerived} paper-derived · ${priors.length - paperDerived} assumption/calibration</div>`
    : '';
  const generatedRows = generated.map(parameter => {
    const value = parameter.default_value == null ? 'override required' : `default ${fmtNum(parameter.default_value)}`;
    return `<div class="param-card"><div class="param-head"><b>${esc(parameter.id)}</b><span>${esc(value)}</span></div>` +
      `<div class="muted">operator ${esc(parameter.operator || 'n/a')}; source edges ${esc((parameter.source_edges || []).join(', ') || 'none')}; required ${esc(parameter.required_for_execution)}</div></div>`;
  }).join('');
  host.className = '';
  host.innerHTML =
    `<div class="prov-section"><h3>Prior parameters</h3>${priorsNote}${priorRows || '<div class="muted">No prior parameters.</div>'}</div>` +
    `<div class="prov-section"><h3>Generated parameters</h3>${generatedRows || '<div class="muted">No generated parameters.</div>'}</div>`;
}

function priorClassification(source) {
  const type = (source?.source_type || '').toLowerCase();
  const label = (source?.source_label || '').toLowerCase();
  if (type === 'paper') return ['good', 'Paper-derived'];
  if (label.includes('calibration') || label.includes('endpoint')) return ['warn', 'Calibration'];
  if (type === 'expert_review' || label.includes('prototype') || label.includes('assumption')) return ['warn', 'Prototype assumption'];
  return ['neutral', humanize(source?.source_type || 'unspecified')];
}

function plotSpecies() {
  const states = new Set((latestSimulation?.series || []).map(item => item.state));
  return (contract?.presentation?.plot_states || []).filter(item => states.has(item.state));
}

function seriesMap(sim, key='series') {
  return Object.fromEntries((sim?.[key] || []).map(series => [series.state, series.values]));
}

function summaryMap(sim) {
  return Object.fromEntries((sim?.summaries || []).map(summary => [summary.state, summary]));
}

function fmtNum(v) {
  if (v == null) return 'n/a';
  if (v === 0) return '0';
  const a = Math.abs(v);
  if (Number.isInteger(v) && a < 10000) return String(v);
  if (a >= 100) return v.toFixed(0);
  if (a >= 1) return v.toFixed(1);
  if (a >= 0.01) return v.toFixed(2);
  return v.toExponential(1);
}

function niceTicks(min, max, count) {
  if (!Number.isFinite(min) || !Number.isFinite(max) || min === max) return [min || 0];
  const span = max - min;
  const raw = span / Math.max(count - 1, 1);
  const power = Math.pow(10, Math.floor(Math.log10(raw)));
  const scaled = raw / power;
  const step = (scaled <= 1 ? 1 : scaled <= 2 ? 2 : scaled <= 5 ? 5 : 10) * power;
  const start = Math.floor(min / step) * step;
  const end = Math.ceil(max / step) * step;
  const ticks = [];
  for (let value = start; value <= end + step * 0.5; value += step) {
    ticks.push(Math.abs(value) < step * 1e-9 ? 0 : value);
  }
  return ticks;
}

function renderKeyMetrics(sim) {
  if (!sim) return;
  const summaries = summaryMap(sim);
  const cards = plotSpecies().map(spec => {
    const m = summaries[spec.state] || {};
    const drop = m.max_drop_fraction_from_baseline;
    const rise = m.max_rise_fraction_from_baseline;
    const useDrop = drop != null && (rise == null || drop >= rise);
    const peak = useDrop ? -drop : rise;
    const main = peak == null ? 'n/a' : `${peak < 0 ? 'v' : '^'} ${(Math.abs(peak) * 100).toFixed(1)}%`;
    return `<div class="metric"><div class="metric-name"><span class="dot" style="background:${spec.color}"></span>${esc(spec.label)}</div><div class="metric-main ${peak < 0 ? 'down' : 'up'}">${main}</div><div class="metric-sub">final ${fmtNum((m.final_fraction_change_from_baseline || 0) * 100)}%</div></div>`;
  }).join('');
  const logic = (sim.biological_logic || []).map(item => `<span class="badge${item.result ? ' ok' : item.result === false ? ' no' : ''}" title="${esc(item.rationale)}">${esc(item.label)}</span>`).join('');
  document.getElementById('keyMetrics').className = '';
  document.getElementById('keyMetrics').innerHTML = `<div class="metric-row">${cards}</div><div class="bio-logic">${logic}</div>`;
}

const HERO = { w: 820, h: 340, padL: 52, padR: 18, padT: 18, padB: 36 };

function renderHeroChart(sim) {
  if (!sim) return;
  const host = document.getElementById('heroChart');
  const legend = document.getElementById('heroLegend');
  const normalized = seriesMap(sim, 'control_normalized_series');
  const time = sim.time || [];
  const species = plotSpecies()
    .map(spec => {
      const values = normalized[spec.state];
      return values ? { ...spec, values, norm: values.map(value => value * 100) } : null;
    })
    .filter(Boolean);
  if (!species.length) {
    host.innerHTML = '<div class="muted">No control-normalized series.</div>';
    legend.innerHTML = '';
    heroState = null;
    return;
  }
  const n = time.length, xmin = time[0], xmax = time[n - 1];
  const plotW = HERO.w - HERO.padL - HERO.padR, plotH = HERO.h - HERO.padT - HERO.padB;
  const all = species.flatMap(s => s.norm);
  let ymin = Math.min(0, ...all), ymax = Math.max(110, Math.max(...all) * 1.04);
  const yticks = niceTicks(ymin, ymax, 5);
  ymin = Math.min(ymin, yticks[0]);
  ymax = Math.max(ymax, yticks[yticks.length - 1]);
  const xAt = i => HERO.padL + (n <= 1 ? 0 : (i / (n - 1)) * plotW);
  const tToX = t => HERO.padL + (xmax === xmin ? 0 : ((t - xmin) / (xmax - xmin)) * plotW);
  const yAt = v => HERO.padT + (1 - (v - ymin) / (ymax - ymin)) * plotH;
  const right = (HERO.w - HERO.padR).toFixed(1);
  const bottom = (HERO.padT + plotH).toFixed(1);
  let grid = '';
  yticks.forEach(value => {
    const y = yAt(value);
    grid += `<line class="grid" x1="${HERO.padL}" y1="${y.toFixed(1)}" x2="${right}" y2="${y.toFixed(1)}"/>`;
    grid += `<text class="ax-y" x="${HERO.padL - 6}" y="${(y + 4).toFixed(1)}" text-anchor="end">${fmtNum(value)}</text>`;
  });
  niceTicks(xmin, xmax, 5).forEach(value => {
    if (value < xmin || value > xmax) return;
    const x = tToX(value);
    grid += `<line class="grid" x1="${x.toFixed(1)}" y1="${HERO.padT}" x2="${x.toFixed(1)}" y2="${bottom}"/>`;
    grid += `<text class="ax-x" x="${x.toFixed(1)}" y="${(HERO.padT + plotH + 16).toFixed(1)}" text-anchor="middle">${fmtNum(value)}</text>`;
  });
  let refs = `<line class="ref-base" x1="${HERO.padL}" y1="${yAt(100).toFixed(1)}" x2="${right}" y2="${yAt(100).toFixed(1)}"/>`;
  refs += `<text class="ref-label" x="${right}" y="${(yAt(100) - 4).toFixed(1)}" text-anchor="end">control 100%</text>`;
  const y90 = yAt(90);
  if (y90 > HERO.padT && y90 < HERO.padT + plotH) {
    refs += `<line class="ref-thresh" x1="${HERO.padL}" y1="${y90.toFixed(1)}" x2="${right}" y2="${y90.toFixed(1)}"/>`;
    refs += `<text class="ref-label" x="${right}" y="${(y90 + 12).toFixed(1)}" text-anchor="end">-10%</text>`;
  }
  const frame = `<line class="axis" x1="${HERO.padL}" y1="${HERO.padT}" x2="${HERO.padL}" y2="${bottom}"/>` +
    `<line class="axis" x1="${HERO.padL}" y1="${bottom}" x2="${right}" y2="${bottom}"/>`;
  const lines = species.map(s => `<polyline fill="none" stroke="${s.color}" stroke-width="2" points="${s.norm.map((v, i) => `${xAt(i).toFixed(1)},${yAt(v).toFixed(1)}`).join(' ')}"/>`).join('');
  const cursor = `<line id="heroCursor" class="cursor-line" x1="0" y1="${HERO.padT}" x2="0" y2="${bottom}" style="display:none"/>`;
  const dots = species.map((s, i) => `<circle id="heroDot${i}" class="cursor-dot" r="3.5" fill="${s.color}" style="display:none"/>`).join('');
  const titles = `<text class="ax-title" transform="translate(13,${(HERO.padT + plotH / 2).toFixed(1)}) rotate(-90)" text-anchor="middle">% of untreated control</text>` +
    `<text class="ax-title" x="${(HERO.padL + plotW / 2).toFixed(1)}" y="${(HERO.h - 4).toFixed(1)}" text-anchor="middle">time (h)</text>`;
  host.className = '';
  host.innerHTML = `<svg id="heroSvg" viewBox="0 0 ${HERO.w} ${HERO.h}" role="img" aria-label="Normalized PD time courses">${grid}${refs}${frame}${lines}${cursor}${dots}${titles}</svg>`;
  legend.innerHTML = species.map(s => `<span class="leg-item"><span class="dot" style="background:${s.color}"></span>${esc(s.label)} <span class="muted">${s.norm[n - 1].toFixed(0)}%</span></span>`).join('');
  heroState = { species, time, n, plotW, xAt, yAt, xmin, xmax };
  document.getElementById('heroSvg').addEventListener('mousemove', onHeroMove);
  document.getElementById('heroSvg').addEventListener('mouseleave', onHeroLeave);
}

function onHeroMove(evt) {
  if (!heroState) return;
  const svg = document.getElementById('heroSvg');
  const rect = svg.getBoundingClientRect();
  const vbX = (evt.clientX - rect.left) / rect.width * HERO.w;
  const frac = (vbX - HERO.padL) / heroState.plotW;
  const idx = Math.max(0, Math.min(heroState.n - 1, Math.round(frac * (heroState.n - 1))));
  const x = heroState.xAt(idx);
  document.getElementById('heroCursor').setAttribute('x1', x.toFixed(1));
  document.getElementById('heroCursor').setAttribute('x2', x.toFixed(1));
  document.getElementById('heroCursor').style.display = '';
  heroState.species.forEach((s, i) => {
    const dot = document.getElementById('heroDot' + i);
    dot.setAttribute('cx', x.toFixed(1));
    dot.setAttribute('cy', heroState.yAt(s.norm[idx]).toFixed(1));
    dot.style.display = '';
  });
  document.getElementById('heroReadout').className = 'hero-readout';
  document.getElementById('heroReadout').innerHTML = `<b>t = ${fmtNum(heroState.time[idx])} h</b>` + heroState.species.map(s => `<span class="leg-item"><span class="dot" style="background:${s.color}"></span>${esc(s.label)} <b>${s.norm[idx].toFixed(0)}%</b></span>`).join('');
}

function onHeroLeave() {
  const cursor = document.getElementById('heroCursor');
  if (cursor) cursor.style.display = 'none';
  if (heroState) heroState.species.forEach((s, i) => {
    const dot = document.getElementById('heroDot' + i);
    if (dot) dot.style.display = 'none';
  });
  const readout = document.getElementById('heroReadout');
  readout.className = 'hero-readout muted';
  readout.textContent = 'Hover the chart to read values';
}

const SM = { w: 360, h: 188, padL: 46, padR: 12, padT: 20, padB: 26 };

function renderSmallMultiples(sim) {
  if (!sim) return;
  const absolute = seriesMap(sim);
  const summaries = summaryMap(sim);
  const host = document.getElementById('smallMultiples');
  host.className = '';
  host.innerHTML = plotSpecies()
    .map(spec => renderSmallChart(spec, sim.time || [], absolute[spec.state], summaries[spec.state]))
    .join('');
}

function renderSmallChart(spec, time, values, summary) {
  if (!values || !values.length || !time.length) return '';
  const n = time.length;
  const xmin = time[0], xmax = time[n - 1];
  const base = values[0];
  let lo = Math.min(...values), hi = Math.max(...values);
  const minSpan = Math.max(Math.abs(base) * 0.04, 1e-6);
  if (hi - lo < minSpan) {
    lo = base - minSpan / 2;
    hi = base + minSpan / 2;
  }
  const margin = (hi - lo) * 0.08;
  lo -= margin;
  hi += margin;
  const plotW = SM.w - SM.padL - SM.padR;
  const plotH = SM.h - SM.padT - SM.padB;
  const xAt = i => SM.padL + (n <= 1 ? 0 : (i / (n - 1)) * plotW);
  const yAt = v => SM.padT + (1 - (v - lo) / (hi - lo)) * plotH;
  const right = (SM.w - SM.padR).toFixed(1);
  const bottom = (SM.padT + plotH).toFixed(1);
  let grid = '';
  niceTicks(lo, hi, 3).forEach(value => {
    if (value < lo || value > hi) return;
    const y = yAt(value);
    grid += `<line class="grid" x1="${SM.padL}" y1="${y.toFixed(1)}" x2="${right}" y2="${y.toFixed(1)}"/>`;
    grid += `<text class="ax-y" x="${SM.padL - 5}" y="${(y + 4).toFixed(1)}" text-anchor="end">${fmtNum(value)}</text>`;
  });
  const xlabels = `<text class="ax-x" x="${SM.padL}" y="${(SM.padT + plotH + 15).toFixed(1)}" text-anchor="start">${fmtNum(xmin)}</text>` +
    `<text class="ax-x" x="${right}" y="${(SM.padT + plotH + 15).toFixed(1)}" text-anchor="end">${fmtNum(xmax)}h</text>`;
  let extremeValue = values[0], extremeIndex = 0;
  for (let i = 1; i < n; i++) {
    if (Math.abs(values[i] - base) > Math.abs(extremeValue - base)) {
      extremeValue = values[i];
      extremeIndex = i;
    }
  }
  const drop = summary ? summary.max_drop_fraction_from_baseline : null;
  const rise = summary ? summary.max_rise_fraction_from_baseline : null;
  const useDrop = drop != null && (rise == null || drop >= rise);
  const peakChange = useDrop ? -drop : rise;
  let refs = `<line class="ref-base" x1="${SM.padL}" y1="${yAt(base).toFixed(1)}" x2="${right}" y2="${yAt(base).toFixed(1)}"/>`;
  if (peakChange != null && Math.abs(peakChange) > 1e-4) {
    const px = xAt(extremeIndex);
    refs += `<line class="ref-thresh" x1="${px.toFixed(1)}" y1="${SM.padT}" x2="${px.toFixed(1)}" y2="${bottom}"/>`;
    refs += `<circle class="thresh-dot" cx="${px.toFixed(1)}" cy="${yAt(extremeValue).toFixed(1)}" r="3"/>`;
  }
  const frame = `<line class="axis" x1="${SM.padL}" y1="${SM.padT}" x2="${SM.padL}" y2="${bottom}"/>` +
    `<line class="axis" x1="${SM.padL}" y1="${bottom}" x2="${right}" y2="${bottom}"/>`;
  const line = `<polyline fill="none" stroke="${spec.color}" stroke-width="2" points="${values.map((value, i) => `${xAt(i).toFixed(1)},${yAt(value).toFixed(1)}`).join(' ')}"/>`;
  const flat = peakChange != null && Math.abs(peakChange) < 1e-4;
  const marker = peakChange == null || flat ? '' : peakChange < 0 ? 'v' : '^';
  const peakText = peakChange == null ? '' : flat
    ? '<span class="muted">no change</span>'
    : `<span class="sm-chg ${peakChange < 0 ? 'down' : 'up'}">${marker} ${(Math.abs(peakChange) * 100).toFixed(1)}%</span>`;
  const timeValue = summary ? (useDrop ? summary.time_to_nadir : summary.time_to_peak) : time[extremeIndex];
  const timeText = peakChange == null || flat ? '' : `<span class="muted">extreme @ ${timeValue.toFixed(1)}h</span>`;
  return `<div class="chart"><div class="chart-title"><span class="dot" style="background:${spec.color}"></span>${esc(spec.label)} ${peakText} ${timeText}</div>` +
    `<svg viewBox="0 0 ${SM.w} ${SM.h}" role="img" aria-label="${esc(spec.label)} absolute time course">${grid}${xlabels}${refs}${frame}${line}</svg></div>`;
}

function renderPatch(title, lines, warnings=latestWarnings) {
  document.getElementById('prediction').className = '';
  document.getElementById('prediction').innerHTML = `<div class="pred-head"><span class="badge big">${esc(title)}</span></div>` +
    lines.map(line => `<div class="eq-term">${esc(line)}</div>`).join('') +
    warnings.map(w => `<div class="warning">${esc(w.message)}</div>`).join('');
}

function stateLabel(state) {
  return (contract?.presentation?.plot_states || []).find(item => item.state === state)?.label || state;
}

function edgeById(graph, edgeId) {
  return (graph?.edges || []).find(edge => edge.id === edgeId) || null;
}

function relationVerb(relation) {
  if (relation === 'activates_edge') return 'activates';
  if (relation === 'inhibits_edge') return 'inhibits';
  return relation;
}

function summaryByState(sim) {
  return Object.fromEntries((sim?.summaries || []).map(summary => [summary.state, summary]));
}

function dropText(summary) {
  if (!summary) return 'not simulated';
  const drop = (summary.max_drop_fraction_from_baseline || 0) * 100;
  const t10 = summary.time_to_10pct_drop_from_baseline == null ? '10% drop not reached' : `10% drop @ ${fmtNum(summary.time_to_10pct_drop_from_baseline)}h`;
  const final = (summary.final_fraction_change_from_baseline || 0) * 100;
  return `max drop ${drop.toFixed(1)}%; ${t10}; final ${final.toFixed(1)}%`;
}

function renderToyPrediction(prediction, claim, warnings=[], applied=null) {
  const graph = applied?.graph || latestGraph;
  const compiled = applied?.compiled_model || latestCompiled;
  const sim = applied?.simulation || latestSimulation;
  const recommendations = prediction.recommendations || [];
  const patchRows = recommendations.map(item => {
    const target = edgeById(graph, item.target);
    const targetLabel = target ? edgeLabel(graph, target) : item.target;
    return `<div class="pred-rel"><b>${esc(item.source)}</b> ${esc(relationVerb(item.relation))} <b>${esc(targetLabel)}</b><br>` +
      `<span class="muted">${esc(item.rationale)} Support ${(item.support_score * 100).toFixed(0)}%.</span></div>`;
  }).join('') || '<div class="muted">No graph patch recommended.</div>';
  const modifierRows = (compiled?.modifiers || []).map(mod => {
    const target = edgeById(graph, mod.target_edge);
    const targetLabel = target ? edgeLabel(graph, target) : mod.target_edge;
    return `<div class="eq-term"><span class="badge">${esc(mod.operator)}</span><b>${esc(targetLabel)}</b><br>` +
      `<code>${esc(expressionText(mod.expression))}</code><br>` +
      `<span class="muted">modifier ${esc(mod.modifier_id)}; source edges ${(mod.source_edges || []).map(esc).join(', ')}</span></div>`;
  }).join('') || '<div class="muted">No compiled modifier terms.</div>';
  const summaries = summaryByState(sim);
  const configuredStates = [
    ...(contract?.presentation?.endpoint_states || []),
    ...(contract?.presentation?.plot_states || []).map(item => item.state)
  ];
  const keyStates = Array.from(new Set(configuredStates)).filter(state => summaries[state]).slice(0, 6);
  const impactRows = keyStates.map(state => `<div class="candidate-row"><span class="rank"></span><span><b>${esc(stateLabel(state))}</b><br><span class="muted">${esc(dropText(summaries[state]))}</span></span><span class="score"></span></div>`).join('');
  const logicRows = (sim?.biological_logic || []).map(item => `<span class="badge${item.result ? ' ok' : item.result === false ? ' no' : ''}" title="${esc(item.rationale)}">${esc(item.label)}</span>`).join('');
  const probabilities = (prediction.probabilities || []).map(item => {
    const width = Math.max(0, Math.min(100, item.probability * 100));
    return `<div class="prob"><span class="prob-k">${esc(item.operator)}</span><span class="prob-bar"><span style="width:${width.toFixed(1)}%"></span></span><span class="prob-v">${width.toFixed(0)}%</span></div>`;
  }).join('');
  const features = (prediction.diagnostics.matched_positive_features || []).join(', ') || 'none';
  document.getElementById('prediction').className = '';
  document.getElementById('prediction').innerHTML =
    `<div class="pred-head"><span class="badge big">Graph-patch prediction applied</span><span class="badge">${esc(prediction.diagnostics.decision_source)}</span></div>` +
    `<div class="diag"><b>Structured model input</b><br>${esc(claim)}</div>` +
    `<div class="pred-subhead">Predicted patch</div>${patchRows}` +
    `<div class="pred-subhead">Equation impact</div>${modifierRows}` +
    `<div class="pred-subhead">Simulation consequence</div><div class="candidate-list">${impactRows || '<div class="muted">No simulation summaries.</div>'}</div>` +
    `<div class="bio-logic">${logicRows}</div>` +
    `<div class="pred-subhead">Diagnostics</div>` +
    `<div class="diag">Predicted operator: <b>${esc(prediction.predicted_operator)}</b>; modules included: ${esc((prediction.diagnostics.included_modules || []).join(', ') || 'none')}; matched features: ${esc(features)}</div>` +
    `<div class="prob-list">${probabilities}</div>` +
    warnings.map(w => `<div class="warning">${esc(w.message)}</div>`).join('');
}

function renderAll() {
  renderGraph(latestGraph);
  renderEquations(latestCompiled);
  renderParameterCatalog(latestCompiled);
  renderKeyMetrics(latestSimulation);
  renderHeroChart(latestSimulation);
  renderSmallMultiples(latestSimulation);
  document.getElementById('summary').textContent = JSON.stringify({
    settings: latestSimulation?.settings,
    baseline_diagnostics: latestSimulation?.baseline_diagnostics,
    summaries: latestSimulation?.summaries,
    biological_logic: latestSimulation?.biological_logic,
    warnings: latestWarnings
  }, null, 2);
}

loadInitial().catch(err => setStatus(err.message, true));
