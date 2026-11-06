import type { WorkflowDisplayField } from "../lib/api";

type LoraDisplayEntry = {
  name: string;
  modelStrength: number | string | null;
  clipStrength: number | string | null;
  strengthLabel?: "strength";
};

export function LoraListValue({ value }: { value: WorkflowDisplayField["value"] }) {
  const entries = parseLoraListValue(value);
  if (entries === null) {
    return (
      <pre className="workflow-display-content workflow-display-content--lora-list">
        {typeof value === "string" && value.trim() ? value : "No LoRAs"}
      </pre>
    );
  }
  if (entries.length === 0) {
    return <div className="workflow-display-lora-empty">No LoRAs</div>;
  }
  return (
    <div className="workflow-display-lora-list">
      {entries.map((entry, index) => (
        <div className="workflow-display-lora-item" key={`${entry.name}-${index}`}>
          <strong className="workflow-display-lora-name">{entry.name}</strong>
          <div className="workflow-display-lora-strengths">
            {entry.strengthLabel ? (
              <span className="workflow-display-lora-strength">
                Strength <strong>{formatLoraStrength(entry.modelStrength)}</strong>
              </span>
            ) : (
              <>
                <span className="workflow-display-lora-strength">
                  Model <strong>{formatLoraStrength(entry.modelStrength)}</strong>
                </span>
                <span className="workflow-display-lora-strength">
                  CLIP <strong>{formatLoraStrength(entry.clipStrength)}</strong>
                </span>
              </>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
function parseLoraListValue(value: WorkflowDisplayField["value"]): LoraDisplayEntry[] | null {
  if (Array.isArray(value)) {
    return value.map(([name, model, clip]) => ({
      name,
      modelStrength: model,
      clipStrength: clip,
    }));
  }

  const text = value.trim();
  if (!text) return [];

  const tagMatches = Array.from(
    text.matchAll(
      /<lora:([^:>]+)(?::(-?(?:\d+(?:\.\d+)?|\.\d+)))?(?::(-?(?:\d+(?:\.\d+)?|\.\d+)))?>/gi,
    ),
  );
  const fileMatches = Array.from(
    text.matchAll(
      /(?:^|[\s,;|])([^<>\s,;|]+?\.(?:safetensors|ckpt|pt|bin))(?::(-?(?:\d+(?:\.\d+)?|\.\d+)))?(?=$|[\s,;|])/gi,
    ),
  );
  const extracted = [
    ...tagMatches.map((match) => {
      const [, name, modelStrength, clipStrength] = match;
      const strengths = [modelStrength, clipStrength]
        .filter(Boolean)
        .map((strength) => Number(strength).toFixed(2));
      const strengthLabel: "strength" | undefined = strengths.length === 1
        ? "strength"
        : undefined;
      return {
        index: match.index ?? Number.MAX_SAFE_INTEGER,
        entry: {
          name: name.trim(),
          modelStrength: modelStrength ? Number(modelStrength).toFixed(2) : null,
          clipStrength: clipStrength ? Number(clipStrength).toFixed(2) : null,
          strengthLabel,
        },
      };
    }),
    ...fileMatches.map((match) => {
      const [, name, strength] = match;
      return {
        index: match.index ?? Number.MAX_SAFE_INTEGER,
        entry: {
          name,
          modelStrength: strength ? Number(strength).toFixed(2) : null,
          clipStrength: null,
          strengthLabel: "strength" as const,
        },
      };
    }),
  ].sort((left, right) => left.index - right.index);
  if (extracted.length) {
    return extracted.map(({ entry }) => entry);
  }

  return null;
}

function formatLoraStrength(value: number | string | null): string {
  if (value === null || value === "") return "—";
  const numeric = typeof value === "number" ? value : Number(value);
  return Number.isFinite(numeric) ? numeric.toFixed(2) : String(value);
}
