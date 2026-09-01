/** Split a /rosout graph name into namespace segments. */
export function graphSegments(name) {
  return String(name || "")
    .split("/")
    .map((part) => part.trim())
    .filter(Boolean);
}

/**
 * Nested folders from fully qualified names such as /wheel_bl/can_node.
 * No extra launch metadata: the path is the grouping.
 */
export function buildRosNameTree(names) {
  const root = { label: "", path: "", hasLogger: false, children: new Map() };
  const unique = [...new Set(names.filter(Boolean))];
  for (const name of unique) {
    const parts = graphSegments(name);
    if (parts.length === 0) continue;
    let node = root;
    let path = "";
    parts.forEach((part, index) => {
      path += `/${part}`;
      if (!node.children.has(part)) {
        node.children.set(part, {
          label: part,
          path,
          hasLogger: false,
          children: new Map(),
        });
      }
      node = node.children.get(part);
      if (index === parts.length - 1) node.hasLogger = true;
    });
  }
  return root;
}

export function sortedChildNodes(node) {
  return [...node.children.values()].sort((a, b) => a.label.localeCompare(b.label));
}

export function nameMatchesSelection(name, selection) {
  if (!selection || selection.type === "all") return true;
  if (selection.type === "exact") return name === selection.path;
  if (name === selection.path) return true;
  return String(name).startsWith(`${selection.path}/`);
}
