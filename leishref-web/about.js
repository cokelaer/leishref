// "What is included": built from catalog.json, so it always describes the catalog the site was built with.
export function summarize(genomes) {
  const count = (key) => {
    const counts = new Map();
    for (const g of genomes) counts.set(g[key] || "unknown", (counts.get(g[key] || "unknown") || 0) + 1);
    return [...counts].sort((a, b) => b[1] - a[1] || (a[0] < b[0] ? -1 : 1));
  };
  const species = new Map();
  for (const g of genomes) {
    const row = species.get(g.species || "unknown") || { species: g.species || "unknown", genomes: 0, gff: 0 };
    row.genomes++;
    if ((g.files || {}).gff) row.gff++;
    species.set(row.species, row);
  }
  return {
    genomes: genomes.length,
    species: species.size,
    withGff: genomes.filter((g) => (g.files || {}).gff).length,
    bySource: count("source"),
    byLevel: count("assembly_level"),
    perSpecies: [...species.values()].sort((a, b) => b.genomes - a.genomes || (a.species < b.species ? -1 : 1)),
  };
}

const el = (tag, text, className) => {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
};

function table(headers, rows) {
  const t = el("table", undefined, "dt");
  const head = el("tr");
  for (const h of headers) head.append(el("th", h));
  const thead = el("thead");
  thead.append(head);
  const body = el("tbody");
  for (const row of rows) {
    const tr = el("tr");
    for (const cell of row) tr.append(el("td", String(cell)));
    body.append(tr);
  }
  t.append(thead, body);
  return t;
}

async function main() {
  let genomes;
  try {
    const response = await fetch("catalog.json");
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    genomes = await response.json();
  } catch (e) {
    document.querySelector("#summary").textContent = `Could not load the catalog: ${e.message}`;
    return;
  }
  const s = summarize(genomes);
  document.querySelector("#summary").textContent = `${s.genomes} genomes of ${s.species} species.`;
  const tiles = [[s.genomes, "genomes"], [s.species, "species"], [s.withGff, "with a GFF"]];
  for (const [value, label] of tiles) {
    const tile = el("div", undefined, "tile");
    tile.append(el("b", String(value)), el("span", label));
    document.querySelector("#tiles").append(tile);
  }
  document.querySelector("#sources").append(table(["source", "genomes"], s.bySource));
  document.querySelector("#levels").append(table(["assembly level", "genomes"], s.byLevel));
  document.querySelector("#gff").textContent = `${s.withGff} of ${s.genomes} entries record a GFF annotation next to the FASTA.`;
  document.querySelector("#species").append(table(["species", "genomes", "with a GFF"], s.perSpecies.map((r) => [r.species, r.genomes, r.gff])));
}

if (typeof document !== "undefined") main();
