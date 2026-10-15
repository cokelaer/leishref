const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const mb = (b) => (b ? (b / 1e6).toFixed(1) + " Mb" : "–");
const kb = (b) => (b ? (b >= 1e6 ? (b / 1e6).toFixed(2) + " Mb" : (b / 1e3).toFixed(0) + " kb") : "–");

let genomes = [], limit = 24;

function classifyTech(s) {
  if (!s) return "Unknown";
  const t = s.toLowerCase();
  const f = [/illumina|hiseq|miseq|novaseq|nextseq|gaiix?/, /nanopore|minion|gridion|promethion/, /pacbio|rs ?ii|sequel/, /454|ion ?torrent|solid/].map((r) => r.test(t));
  if (f.filter(Boolean).length > 1) return "Hybrid";
  return f[0] ? "Illumina" : f[1] ? "Oxford Nanopore" : f[2] ? "PacBio" : f[3] ? "Legacy (454/Ion/SOLiD)" : "Other";
}

const hay = (g) =>
  [g.identifier, g.accession, g.species, g.strain, g.source, g.assembly_level, g.taxon_id, g.notes, g.tech, g.techCat, ...(g.aliases || [])]
    .join(" ").toLowerCase();

function installCmd(g) {
  const alias = (g.aliases || [])[0];
  return `leishref install ${g.identifier}` + (alias ? ` --alias ${alias}` : "");
}

function details(g) {
  const rows = [];
  const add = (k, v) => v !== undefined && v !== null && v !== "" && rows.push([k, v]);
  const st = g.stats || {}, pv = g.provenance || {};
  add("accession", g.accession); add("taxon id", g.taxon_id); add("assembly", g.assembly_name);
  add("released", g.release_date); add("added", g.date_added);
  add("contigs", st.num_contigs); add("scaffolds", st.num_scaffolds); add("contig N50", st.contig_n50 && kb(st.contig_n50));
  add("gaps", st.num_gaps); add("ambiguous bases", st.num_ambiguous);
  add("assembler", pv.assembler);
  add("technology", g.tech);
  const files = Object.entries(g.files || {}).map(([k, f]) => `${k}: ${esc(f)}`).join("<br>");
  let html = `<table class="dt"><tbody>` + rows.map(([k, v]) => `<tr><th>${esc(k)}</th><td>${esc(v)}</td></tr>`).join("");
  const ncbi = (label, id, path) => id && /^[A-Z0-9_.]+$/i.test(id) &&
    (html += `<tr><th>${label}</th><td><a href="https://www.ncbi.nlm.nih.gov/${path}/${esc(id)}" target="_blank" rel="noopener">${esc(id)}</a></td></tr>`);
  ncbi("bioproject", pv.bioproject, "bioproject"); ncbi("biosample", pv.biosample, "biosample");
  if (pv.zenodo_doi) html += `<tr><th>zenodo</th><td><a href="https://doi.org/${esc(pv.zenodo_doi)}" target="_blank" rel="noopener">${esc(pv.zenodo_doi)}</a></td></tr>`;
  if (g.accession && /^GC[AF]_/.test(g.accession)) html += `<tr><th>NCBI</th><td><a href="https://www.ncbi.nlm.nih.gov/datasets/genome/${esc(g.accession)}/" target="_blank" rel="noopener">${esc(g.accession)}</a></td></tr>`;
  if (files) html += `<tr><th>files</th><td>${files}</td></tr>`;
  html += `</tbody></table>`;
  if (g.notes) html += `<p class="notes">${esc(String(g.notes).trim())}</p>`;
  return html;
}

function filtered() {
  const terms = $("#q").value.trim().toLowerCase().split(/\s+/).filter(Boolean);
  const src = $("#source").value, lvl = $("#level").value, tc = $("#tech").value;
  const rows = genomes.filter((g) => (!src || g.source === src) && (!lvl || g.assembly_level === lvl) && (!tc || g.techCat === tc) && terms.every((w) => g._h.includes(w)));
  const s = $("#sort").value;
  const cmp = {
    species: (a, b) => (a.species || "").localeCompare(b.species || "") || (a.strain || "").localeCompare(b.strain || ""),
    id: (a, b) => a.identifier.localeCompare(b.identifier),
    size: (a, b) => (b.stats?.num_bases || 0) - (a.stats?.num_bases || 0),
    n50: (a, b) => (b.stats?.scaffold_n50 || 0) - (a.stats?.scaffold_n50 || 0),
    date: (a, b) => String(b.date_added || "").localeCompare(String(a.date_added || "")),
  }[s];
  return rows.sort(cmp);
}

function render() {
  const rows = filtered();
  $("#count").textContent = `${rows.length} of ${genomes.length} genomes`;
  const more = rows.length - limit;
  $("#list").innerHTML = rows.length
    ? rows.slice(0, limit).map((g) => {
        const st = g.stats || {};
        return `<div class="tool" data-id="${esc(g.identifier)}">
        <h3 class="toggle" title="Show details"><span><i>${esc(g.species || "unknown species")}</i> ${esc(g.strain || "")}</span><small>${mb(st.num_bases)}</small></h3>
        <div class="bins">${esc(g.identifier)}${(g.aliases || []).length ? " · " + g.aliases.map(esc).join(", ") : ""}</div>
        <div class="vers">
          <span class="v static">${esc(g.source)}</span>
          ${g.assembly_level ? `<span class="v static">${esc(g.assembly_level)}</span>` : ""}
          ${g.tech ? `<span class="v static tech" data-tip="${esc(g.tech)}">${esc(g.techCat)}</span>` : ""}
          ${st.scaffold_n50 ? `<span class="v static" data-tip="Scaffold N50">N50 ${kb(st.scaffold_n50)}</span>` : ""}
          ${st.gc_percent ? `<span class="v static">GC ${st.gc_percent}%</span>` : ""}
        </div>
        <div class="cmd on" title="Click to copy">${esc(installCmd(g))}</div>
        <div class="det"></div>
      </div>`;
      }).join("") + (more > 0 ? `<button id="more" class="empty">Show ${more} more…</button>` : "")
    : `<div class="empty">No genome matches.</div>`;
}

$("#list").addEventListener("click", (e) => {
  if (e.target.id === "more") { limit = Infinity; render(); return; }
  const c = e.target.closest(".cmd"), h = e.target.closest(".toggle");
  if (c) {
    navigator.clipboard?.writeText(c.textContent);
    const old = c.textContent; c.textContent = "copied"; setTimeout(() => (c.textContent = old), 800);
  } else if (h) {
    const card = h.closest(".tool"), det = card.querySelector(".det");
    if (!det.innerHTML) det.innerHTML = details(genomes.find((g) => g.identifier === card.dataset.id));
    card.classList.toggle("open");
  }
});
["#q"].forEach((s) => $(s).addEventListener("input", () => { limit = 24; render(); }));
["#source", "#level", "#tech", "#sort"].forEach((s) => $(s).addEventListener("change", () => { limit = 24; render(); }));

function fill(sel, vals) {
  $(sel).innerHTML += [...new Set(vals.filter(Boolean))].sort().map((v) => `<option>${esc(v)}</option>`).join("");
}

function stats() {
  const species = new Set(genomes.map((g) => g.species).filter(Boolean));
  const complete = genomes.filter((g) => ["Complete Genome", "Chromosome"].includes(g.assembly_level)).length;
  // The same genome can be in the catalog under several origins (e.g. NCBI and TriTrypDB), so the
  // last tile splits the entries by origin.
  const n = (group) => genomes.filter((g) => g.group === group).length;
  const split = [["NCBI", n("ncbi")], ["TriTrypDB", n("tritrypdb")]];
  split.push(["others", genomes.length - split[0][1] - split[1][1]]);
  const tiles = [[genomes.length, "genomes"], [species.size, "species"], [complete, "chromosome-level"]]
    .map(([v, l]) => `<div class="tile"><b>${v}</b><span>${l}</span></div>`);
  tiles.push(`<div class="tile origins">${split.map(([l, v]) => `<div><b>${v}</b><span>${l}</span></div>`).join("")}</div>`);
  $("#tiles").innerHTML = tiles.join("");
}

/* ---------- tooltip + charts ---------- */
const tip = $("#tip");
const showTip = (e, html) => {
  tip.innerHTML = html; tip.style.opacity = 1;
  tip.style.left = Math.min(e.clientX + 12, innerWidth - 270) + "px"; tip.style.top = e.clientY + 14 + "px";
};
const hideTip = () => (tip.style.opacity = 0);
document.addEventListener("pointermove", (e) => {
  const t = e.target.closest?.("[data-tip]");
  t ? showTip(e, t.dataset.tip) : hideTip();
});

// clicking a bar sends its label to the search box
function search(q) {
  $("#q").value = q; $("#source").value = $("#level").value = $("#tech").value = ""; limit = 24; render();
  $("#q").scrollIntoView({ behavior: "smooth", block: "center" });
}

function barChart(el, items, { w = 900, label = 190, q = (i) => i.label }) {
  const row = 26, h = items.length * row + 8, max = Math.max(...items.map((i) => i.value));
  const x0 = label, span = w - label - 50;
  el.innerHTML = `<svg viewBox="0 0 ${w} ${h}" role="img">` + items.map((it, i) => {
    const y = i * row + 4, bw = Math.max(2, (it.value / max) * span);
    return `<g class="bar" tabindex="0" data-q="${esc(q(it))}" data-tip="<b>${it.value}</b> ${esc(it.tip || "genomes")}<br>${esc(it.label)}">
      <rect class="hit" x="0" y="${y - 2}" width="${w}" height="${row}" fill="transparent"/>
      <text x="${label - 8}" y="${y + 14}" text-anchor="end">${esc(it.label)}</text>
      <rect class="mark" x="${x0}" y="${y + 3}" width="${bw}" height="14" rx="3"/>
      <text class="val" x="${x0 + bw + 6}" y="${y + 14}">${it.value}</text></g>`;
  }).join("") + `</svg>`;
  el.onclick = (e) => { const g = e.target.closest(".bar"); if (g) search(g.dataset.q); };
}

function count(key, fn = (g) => g[key]) {
  const c = {};
  genomes.forEach((g) => { const k = fn(g) || "Unknown"; c[k] = (c[k] || 0) + 1; });
  return Object.entries(c).map(([label, value]) => ({ label, value })).sort((a, b) => b.value - a.value || a.label.localeCompare(b.label));
}

function scatter(el) {
  const pts = genomes.filter((g) => g.stats?.num_bases >= 5e6 && g.stats?.scaffold_n50)
    .map((g) => ({ g, x: Math.log10(g.stats.scaffold_n50), y: g.stats.num_bases / 1e6 }));
  const w = 900, h = 360, m = { l: 50, r: 16, t: 14, b: 44 };
  const xmin = Math.floor(Math.min(...pts.map((p) => p.x))), xmax = Math.ceil(Math.max(...pts.map((p) => p.x)));
  const ymin = Math.floor(Math.min(...pts.map((p) => p.y)) / 5) * 5, ymax = Math.ceil(Math.max(...pts.map((p) => p.y)) / 5) * 5;
  const X = (v) => m.l + ((v - xmin) / (xmax - xmin)) * (w - m.l - m.r);
  const Y = (v) => h - m.b - ((v - ymin) / (ymax - ymin)) * (h - m.t - m.b);
  let svg = `<svg viewBox="0 0 ${w} ${h}" role="img">`;
  for (let v = xmin; v <= xmax; v++) svg += `<line class="grid" x1="${X(v)}" x2="${X(v)}" y1="${m.t}" y2="${h - m.b}"/><text x="${X(v)}" y="${h - m.b + 16}" text-anchor="middle">${v < 3 ? 10 ** v + " b" : kb(10 ** v)}</text>`;
  for (let v = ymin; v <= ymax; v += 5) svg += `<line class="grid" x1="${m.l}" x2="${w - m.r}" y1="${Y(v)}" y2="${Y(v)}"/><text x="${m.l - 6}" y="${Y(v) + 4}" text-anchor="end">${v}</text>`;
  svg += `<text x="${(w + m.l) / 2}" y="${h - 6}" text-anchor="middle">scaffold N50 (log scale)</text>`;
  svg += `<text transform="translate(12 ${(h - m.b) / 2}) rotate(-90)" text-anchor="middle">genome size (Mb)</text>`;
  svg += pts.map((p, i) => `<circle class="dot" cx="${X(p.x)}" cy="${Y(p.y)}" r="4.5" data-i="${i}"/>`).join("") + `<circle id="sel" r="9" class="sel"/></svg>`;
  el.innerHTML = svg;
  const box = el.querySelector("svg"), sel = el.querySelector("#sel");
  // nearest point wins, so the pointer need not land exactly on a dot
  box.addEventListener("pointermove", (e) => {
    const r = box.getBoundingClientRect(), s = w / r.width, px = (e.clientX - r.left) * s, py = (e.clientY - r.top) * s;
    let best = null, bd = 28 * 28;
    pts.forEach((p) => { const d = (X(p.x) - px) ** 2 + (Y(p.y) - py) ** 2; if (d < bd) { bd = d; best = p; } });
    if (!best) { sel.style.opacity = 0; return; }
    sel.setAttribute("cx", X(best.x)); sel.setAttribute("cy", Y(best.y)); sel.style.opacity = 1;
    const g = best.g;
    el.dataset.cur = g.identifier;
    showTip(e, `<b>${esc(g.species || "")} ${esc(g.strain || "")}</b><br>${esc(g.identifier)}<br>${best.y.toFixed(1)} Mb · N50 ${kb(g.stats.scaffold_n50)}<br>${esc(g.assembly_level || "")}${g.tech ? " · " + esc(g.techCat) : ""}`);
  });
  box.addEventListener("pointerleave", () => { sel.style.opacity = 0; hideTip(); });
  box.addEventListener("click", () => el.dataset.cur && search(el.dataset.cur));
}

function charts() {
  const sp = count("species");
  const top = sp.slice(0, 12), rest = sp.slice(12).reduce((a, s) => a + s.value, 0);
  if (rest) top.push({ label: `other (${sp.length - 12} species)`, value: rest, q: "" });
  barChart($("#c-species"), top.map((s) => ({ ...s, tip: "genomes" })), { q: (i) => (i.q === "" ? "" : i.label) });
  barChart($("#c-tech"), count("techCat"), { w: 460, label: 150, q: (i) => (i.label === "Unknown" ? "" : i.label) });
  barChart($("#c-level"), count("assembly_level"), { w: 460, label: 110, q: (i) => i.label });
  scatter($("#c-scatter"));
}

fetch("catalog.json").then((r) => r.json()).then((data) => {
  genomes = data.map((g) => {
    const tech = g.provenance?.sequencing_technology || "";
    const o = { ...g, tech, techCat: classifyTech(tech) };
    o._h = hay(o);
    return o;
  });
  fill("#source", genomes.map((g) => g.source));
  fill("#level", genomes.map((g) => g.assembly_level));
  fill("#tech", genomes.map((g) => g.techCat));
  const p = new URLSearchParams(location.search).get("q");
  if (p) $("#q").value = p;
  stats(); render(); charts();
}).catch((e) => { $("#list").innerHTML = `<div class="err">Could not load catalog.json (${esc(e.message)}). Serve this folder over HTTP.</div>`; });

$("#theme").addEventListener("click", () => {
  const root = document.documentElement;
  const dark = root.getAttribute("data-theme") === "dark" || (!root.getAttribute("data-theme") && matchMedia("(prefers-color-scheme: dark)").matches);
  const next = dark ? "light" : "dark";
  root.setAttribute("data-theme", next); localStorage.setItem("theme", next);
});
