/**
 * Split a /rosout logger name into namespace segments.
 *
 * rcl writes the node logger as dots (`wheel_bl.can_node`), not slashes
 * (`/wheel_bl/can_node`). Underscores stay in the node name.
 */
export function graphSegments(name) {
  return String(name || "")
    .split(/[/.]+/)
    .map((part) => part.trim())
    .filter(Boolean);
}

function joinPath(parts) {
  return parts.join(".");
}

/**
 * Nested folders from logger names such as wheel_bl.can_node.
 */
export function buildRosNameTree(names) {
  const root = { label: "", path: "", hasLogger: false, children: new Map() };
  const unique = [...new Set(names.filter(Boolean))];
  for (const name of unique) {
    const parts = graphSegments(name);
    if (parts.length === 0) continue;
    let node = root;
    const walked = [];
    parts.forEach((part, index) => {
      walked.push(part);
      const path = joinPath(walked);
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

function partsStartWith(nameParts, prefixParts) {
  if (nameParts.length < prefixParts.length) return false;
  return prefixParts.every((part, index) => nameParts[index] === part);
}

export function nameMatchesSelection(name, selection) {
  if (!selection || selection.type === "all") return true;
  const nameParts = graphSegments(name);
  const selParts = graphSegments(selection.path);
  if (selParts.length === 0) return true;
  if (selection.type === "exact") {
    return (
      nameParts.length === selParts.length
      && partsStartWith(nameParts, selParts)
    );
  }
  return partsStartWith(nameParts, selParts);
}
