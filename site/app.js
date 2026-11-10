'use strict';

// Category descriptions and reference labels.
const scenes = {
  support: {category: 'SUPPORT & STATIC STABILITY', title: 'Table overhang', description: 'Increase the overhang. The reference changes from stable to falling; the model must respond to this geometric difference.', conditions: ['Smaller overhang · 0.39 m', 'Larger overhang · 0.79 m'], outcomes: ['Stable', 'Falls'], takeaway: ['Outcome flip.', 'In the paper’s overhang example, Wan2.2 makes the block fall in both conditions, missing the outcome flip.']},
  torque: {category: 'TORQUE-DRIVEN ROTATION', title: 'Lever-arm length', description: 'Change the lever arm while keeping the shared physical setup fixed. The reference switches from held to released.', conditions: ['Shorter lever arm · 0.18 m', 'Longer lever arm · 0.46 m'], outcomes: ['Held', 'Released'], takeaway: ['Reference outcomes.', 'Compare the two reference outcomes with the independent model generations. Matching a single outcome does not establish sensitivity to the lever-arm change.']},
  gravity: {category: 'CONSTRAINED GRAVITATIONAL DYNAMICS', title: 'Sphere on a frictionless track', description: 'Change the sphere’s release position on a frictionless track. The reference either crosses the hill or returns.', conditions: ['Higher release · 0.87 m', 'Lower release · 0.40 m'], outcomes: ['Crosses', 'Returns'], takeaway: ['Reference outcomes.', 'Read the paired references together: similar-looking scenes lead to different events under the same shared physical conditions.']},
  contact: {category: 'CONTACT & IMPACT', title: 'Pendulum–target contact', description: 'A controlled geometry edit changes whether the pendulum contacts the target within the observation window.', conditions: ['Target aligned', 'Target offset'], outcomes: ['Hits', 'Misses'], takeaway: ['Reference outcomes.', 'The target event depends on the initial arrangement. Inspect whether the model preserves the objects and reproduces the hit–miss contrast.']},
  elastic: {category: 'ELASTIC INTERACTION', title: 'Spring compression', description: 'Change the initial spring compression. The reference switches between retained contact and separation of the block and piston.', conditions: ['Compression · 0.02 m', 'Compression · 0.50 m'], outcomes: ['Contact retained', 'Separated'], takeaway: ['Reference outcomes.', 'The spring and block must evolve according to the initial configuration. The outcome labels describe the references, not the model videos.']},
  pulley: {category: 'PULLEY-MEDIATED COUPLING', title: 'Pulley-mediated load coupling', description: 'Change the visible load arrangement under the same shared physical conditions. The right payload reverses direction in the references.', conditions: ['Load arrangement A', 'Load arrangement B'], outcomes: ['Right payload rises', 'Right payload falls'], takeaway: ['Event and structure.', 'Inspect the direction of motion and the integrity of the rope, pulley, and payloads. Correct motion and preserved structure are evaluated separately.']}
};

const videos = ['ref-a', 'ref-b', 'model-a', 'model-b'].map(id => document.getElementById(id));
const playButton = document.getElementById('play-pair');
const playLabel = document.getElementById('play-label');
const timeline = document.getElementById('timeline');
const status = document.getElementById('playback-status');
const timeDisplay = document.getElementById('time-display');
const controls = document.getElementById('playback-controls');
const tabs = Array.from(document.querySelectorAll('[role="tab"]'));
let playing = false;
let frame = 0;
let windowLength = 0;
let revision = 0;
let currentCategory = 'support';
let ready = false;

function updateTime(time = 0) {
  timeline.value = windowLength ? Math.min(1000, time / windowLength * 1000) : 0;
  timeDisplay.textContent = `${time.toFixed(1)} / ${windowLength ? windowLength.toFixed(1) : '—'} s`;
  timeline.setAttribute('aria-valuetext', `${time.toFixed(1)} seconds of ${windowLength.toFixed(1)} seconds`);
}
function pause() {
  playing = false;
  cancelAnimationFrame(frame);
  videos.forEach(video => video.pause());
  playLabel.textContent = 'Play together';
  playButton.firstElementChild.textContent = '▶';
  playButton.setAttribute('aria-label', 'Play all four videos');
}
function seek(time) {
  videos.forEach(video => { if (video.readyState >= 1) video.currentTime = Math.min(time, video.duration); });
  updateTime(time);
}
function tick() {
  if (!playing) return;
  const time = videos[0].currentTime;
  if (time >= windowLength - 0.06 || videos.some(video => video.ended)) {
    pause(); seek(0); status.textContent = 'Replay the shared window';
    return;
  }
  updateTime(time);
  frame = requestAnimationFrame(tick);
}
async function play() {
  if (!ready) return;
  const currentRevision = revision;
  if (videos[0].currentTime >= windowLength - 0.06) seek(0);
  playButton.disabled = true;
  try {
    await Promise.all(videos.map(video => video.play()));
    if (currentRevision !== revision) return;
    playing = true;
    playLabel.textContent = 'Pause together';
    playButton.firstElementChild.textContent = 'Ⅱ';
    playButton.setAttribute('aria-label', 'Pause all four videos');
    status.textContent = 'Shared playback window';
    frame = requestAnimationFrame(tick);
  } catch {
    if (currentRevision !== revision) return;
    pause();
    status.textContent = 'Playback unavailable. Try Play again.';
  } finally {
    if (currentRevision === revision) playButton.disabled = !ready;
  }
}
function checkReady() {
  if (!videos.every(video => video.readyState >= 1 && Number.isFinite(video.duration) && video.duration > 0)) return;
  windowLength = Math.min(...videos.map(video => video.duration));
  ready = true;
  playButton.disabled = false;
  timeline.disabled = false;
  status.textContent = 'Shared playback window';
  updateTime();
}
function selectCategory(key, focus = false) {
  if (!scenes[key]) return;
  revision += 1;
  pause();
  ready = false;
  windowLength = 0;
  playButton.disabled = true;
  timeline.disabled = true;
  status.textContent = 'Loading videos…';
  currentCategory = key;
  const scene = scenes[key];
  tabs.forEach(tab => {
    const selected = tab.dataset.category === key;
    tab.setAttribute('aria-selected', String(selected));
    tab.tabIndex = selected ? 0 : -1;
    if (selected && focus) tab.focus();
  });
  document.getElementById('scene-panel').setAttribute('aria-labelledby', `tab-${key}`);
  for (const [id, text] of [['scene-category', scene.category], ['scene-title', scene.title], ['scene-description', scene.description], ['condition-a-title', scene.conditions[0]], ['condition-b-title', scene.conditions[1]], ['outcome-a', scene.outcomes[0]], ['outcome-b', scene.outcomes[1]]]) document.getElementById(id).textContent = text;
  const takeaway = document.getElementById('scene-takeaway');
  const strong = document.createElement('strong'); strong.textContent = scene.takeaway[0];
  takeaway.replaceChildren(strong, document.createTextNode(` ${scene.takeaway[1]}`));
  const configs = [{side:'a', role:'reference'}, {side:'b', role:'reference'}, {side:'a', role:'model'}, {side:'b', role:'model'}];
  configs.forEach((config, index) => {
    const video = videos[index];
    video.poster = `assets/${key}-${config.side}${config.role === 'model' ? '-model' : ''}.webp`;
    video.setAttribute('aria-label', `${scene.category}, condition ${config.side.toUpperCase()}, ${config.role === 'model' ? 'Wan2.2 generation' : 'simulation reference'}`);
    video.querySelectorAll('source').forEach(source => {
      const extension = source.type === 'video/webm' ? 'webm' : 'mp4';
      source.src = `assets/${key}-${config.side}-${config.role}.${extension}`;
    });
    video.load();
  });
  updateTime();
  checkReady();
}
tabs.forEach((tab, index) => {
  tab.addEventListener('click', () => selectCategory(tab.dataset.category));
  tab.addEventListener('keydown', event => {
    let next;
    if (event.key === 'ArrowRight') next = (index + 1) % tabs.length;
    if (event.key === 'ArrowLeft') next = (index + tabs.length - 1) % tabs.length;
    if (event.key === 'Home') next = 0;
    if (event.key === 'End') next = tabs.length - 1;
    if (next !== undefined) { event.preventDefault(); selectCategory(tabs[next].dataset.category, true); }
  });
});
controls.hidden = false;
videos.forEach(video => {
  video.controls = false;
  video.addEventListener('loadedmetadata', checkReady);
  video.addEventListener('error', () => { pause(); ready = false; playButton.disabled = true; status.textContent = 'A clip could not be loaded. Select a category to retry.'; });
  video.querySelectorAll('source').forEach(source => source.addEventListener('error', () => {
    if (Array.from(video.querySelectorAll('source')).every(item => !video.canPlayType(item.type))) {
      status.textContent = 'Video playback is not supported in this browser.';
    }
  }));
});
playButton.addEventListener('click', () => playing ? pause() : play());
document.getElementById('replay-pair').addEventListener('click', () => { pause(); seek(0); play(); });
timeline.addEventListener('input', () => { pause(); seek(Number(timeline.value) / 1000 * windowLength); });
document.addEventListener('visibilitychange', () => { if (document.hidden) pause(); });
selectCategory(currentCategory);

// Sort existing semantic rows so paper results remain available without JavaScript.
const body = document.getElementById('results-body');
const rows = Array.from(body.rows);
const search = document.getElementById('model-search');
let sortKey = 'mean';
let ascending = true;
function renderResults() {
  const query = search.value.trim().toLocaleLowerCase();
  const selected = rows.filter(row => row.dataset.model.toLocaleLowerCase().includes(query));
  selected.sort((a, b) => {
    const difference = Number(a.dataset[sortKey]) - Number(b.dataset[sortKey]);
    return (ascending ? difference : -difference) || Number(a.dataset.order) - Number(b.dataset.order);
  });
  body.replaceChildren(...selected);
  document.getElementById('table-status').textContent = selected.length ? `${selected.length} of ${rows.length} models · ${sortKey === 'mean' ? 'overall mean rank' : sortKey} ${ascending ? 'ascending' : 'descending'}` : 'No matching models. Clear the search to see all results.';
  document.querySelectorAll('th[data-sort]').forEach(th => th.setAttribute('aria-sort', th.dataset.sort === sortKey ? (ascending ? 'ascending' : 'descending') : 'none'));
}
search.addEventListener('input', renderResults);
document.querySelectorAll('button[data-sort]').forEach(button => button.addEventListener('click', () => {
  const key = button.dataset.sort;
  ascending = key === sortKey ? !ascending : key === 'mean';
  sortKey = key;
  renderResults();
}));
renderResults();

const copyButton = document.getElementById('copy-citation');
copyButton.hidden = false;
copyButton.addEventListener('click', async () => {
  const text = document.getElementById('bibtex').textContent;
  const copyStatus = document.getElementById('copy-status');
  try {
    if (!navigator.clipboard) throw new Error('Clipboard unavailable');
    await navigator.clipboard.writeText(text);
    copyStatus.textContent = 'BibTeX copied.';
  } catch {
    const range = document.createRange();
    range.selectNodeContents(document.getElementById('bibtex'));
    const selection = window.getSelection(); selection.removeAllRanges(); selection.addRange(range);
    copyStatus.textContent = 'Citation selected. Press Ctrl+C or ⌘C to copy.';
  }
});
