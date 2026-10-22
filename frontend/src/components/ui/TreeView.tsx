import { useState } from "react";

// Navegação em árvore (Onda 7): pastas/subpastas expansíveis.
export interface TreeNode { id: string; label: string; icon?: string; children?: TreeNode[] }

function Node({ node, depth, onSelect }: { node: TreeNode; depth: number; onSelect?: (n: TreeNode) => void }) {
  const [open, setOpen] = useState(depth < 1);
  const has = !!node.children?.length;
  return (
    <div>
      <div className="flex items-center gap-1 py-0.5 rounded hover:bg-edge/40 cursor-pointer text-sm" style={{ paddingLeft: depth * 14 + 2 }}
        onClick={() => { if (has) setOpen((o) => !o); onSelect?.(node); }}>
        <span className="w-3 text-muted text-[10px]">{has ? (open ? "▼" : "▶") : ""}</span>
        <span>{node.icon ?? (has ? "📁" : "📄")}</span>
        <span className="text-text">{node.label}</span>
      </div>
      {has && open && node.children!.map((c) => <Node key={c.id} node={c} depth={depth + 1} onSelect={onSelect} />)}
    </div>
  );
}

export function TreeView({ data, onSelect }: { data: TreeNode[]; onSelect?: (n: TreeNode) => void }) {
  return <div>{data.map((n) => <Node key={n.id} node={n} depth={0} onSelect={onSelect} />)}</div>;
}
