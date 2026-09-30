import type { Evidence, Section } from "./contracts";

export function citationLabels(sections: Section[], citations: Evidence[]): Map<string, string> {
  const byId = new Map(citations.map((item) => [item.id, item]));
  const labels = new Map<string, string>();
  const counts = { technical: 0, journal: 0 };
  const label = (evidence: Evidence) => {
    if (labels.has(evidence.id)) return;
    counts[evidence.kind] += 1;
    labels.set(evidence.id, `${evidence.kind === "technical" ? "S" : "J"}${counts[evidence.kind]}`);
  };
  for (const section of sections) {
    for (const id of section.citation_ids) {
      const evidence = byId.get(id);
      if (evidence) label(evidence);
    }
  }
  citations.forEach(label);
  return labels;
}
