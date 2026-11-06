import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
  type MouseEvent,
} from "react";

import type { PromptRegistryHeatmap } from "../lib/api";

type HeatmapGroup = {
  source: string;
  startIndex: number;
  count: number;
  startY: number;
  cellStartY: number;
  rowCount: number;
};

type HeatmapLayout = {
  columns: number;
  cellSize: number;
  gap: number;
  labelHeight: number;
  height: number;
  groups: HeatmapGroup[];
};

type TooltipPosition = {
  x: number;
  y: number;
};

const HEATMAP_GAP = 2;
const HEATMAP_LABEL_HEIGHT = 20;
const HEATMAP_GROUP_GAP = 12;

function mediaCountColor(mediaCount: number): string {
  if (mediaCount <= 0) return "#292c2b";
  if (mediaCount === 1) return "#b8d9bf";
  if (mediaCount <= 3) return "#86c894";
  if (mediaCount <= 7) return "#5bad73";
  if (mediaCount <= 15) return "#348e59";
  return "#1c633f";
}

function groupForIndex(layout: HeatmapLayout, index: number): HeatmapGroup | null {
  return (
    layout.groups.find(
      (group) => index >= group.startIndex && index < group.startIndex + group.count,
    ) ?? null
  );
}

function moveSelection(
  layout: HeatmapLayout,
  currentIndex: number,
  direction: "left" | "right" | "up" | "down",
): number {
  const group = groupForIndex(layout, currentIndex);
  if (!group) return currentIndex;
  const localIndex = currentIndex - group.startIndex;
  let nextLocalIndex = localIndex;
  if (direction === "left") nextLocalIndex = Math.max(0, localIndex - 1);
  if (direction === "right") nextLocalIndex = Math.min(group.count - 1, localIndex + 1);
  if (direction === "up") {
    nextLocalIndex = Math.max(0, localIndex - layout.columns);
  }
  if (direction === "down") {
    nextLocalIndex = Math.min(group.count - 1, localIndex + layout.columns);
  }
  return group.startIndex + nextLocalIndex;
}

export function PromptRegistryHeatmap({
  data,
  promptId,
  includeNotFaved,
  includeTrash,
  onIncludeNotFavedChange,
  onIncludeTrashChange,
  onSelectPrompt,
}: {
  data: PromptRegistryHeatmap;
  promptId: string;
  includeNotFaved: boolean;
  includeTrash: boolean;
  onIncludeNotFavedChange: (value: boolean) => void;
  onIncludeTrashChange: (value: boolean) => void;
  onSelectPrompt: (promptId: string) => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [containerWidth, setContainerWidth] = useState(720);
  const [zoom, setZoom] = useState(1);
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);
  const [keyboardSelectedIndex, setKeyboardSelectedIndex] = useState<number | null>(null);
  const [tooltipPosition, setTooltipPosition] = useState<TooltipPosition | null>(null);

  const promptIndex = useMemo(() => {
    const index = new Map<string, number>();
    data.items.forEach((item, itemIndex) => index.set(item.prompt_id, itemIndex));
    return index;
  }, [data.items]);

  const selectedIndex = promptId ? (promptIndex.get(promptId) ?? keyboardSelectedIndex) : keyboardSelectedIndex;

  useEffect(() => {
    const element = containerRef.current;
    if (!element) return;
    const updateWidth = () => {
      // Measure the canvas content box, not the padded wrapper: the canvas is
      // laid out at 100% of that box, so using the wrapper width would draw
      // cells for a wider coordinate space than the browser actually shows.
      const width = canvasRef.current?.clientWidth ?? 0;
      setContainerWidth(Math.max(width || element.clientWidth, 1));
    };
    updateWidth();
    if (typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(updateWidth);
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  const layout = useMemo<HeatmapLayout>(() => {
    const cellSize = Math.round(8 * zoom);
    const columns = Math.max(
      1,
      Math.floor((containerWidth + HEATMAP_GAP) / (cellSize + HEATMAP_GAP)),
    );
    const groups: HeatmapGroup[] = [];
    let startIndex = 0;
    let currentY = 0;
    let currentSource = "";
    let currentCount = 0;

    const flushGroup = () => {
      if (!currentSource) return;
      const rowCount = Math.max(1, Math.ceil(currentCount / columns));
      groups.push({
        source: currentSource,
        startIndex,
        count: currentCount,
        startY: currentY,
        cellStartY: currentY + HEATMAP_LABEL_HEIGHT,
        rowCount,
      });
      currentY +=
        HEATMAP_LABEL_HEIGHT +
        rowCount * (cellSize + HEATMAP_GAP) -
        HEATMAP_GAP +
        HEATMAP_GROUP_GAP;
      startIndex += currentCount;
      currentSource = "";
      currentCount = 0;
    };

    for (const item of data.items) {
      if (item.source !== currentSource) {
        flushGroup();
        currentSource = item.source;
      }
      currentCount += 1;
    }
    flushGroup();

    return {
      columns,
      cellSize,
      gap: HEATMAP_GAP,
      labelHeight: HEATMAP_LABEL_HEIGHT,
      height: Math.max(HEATMAP_LABEL_HEIGHT, currentY - HEATMAP_GROUP_GAP),
      groups,
    };
  }, [containerWidth, data.items, zoom]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    let context: CanvasRenderingContext2D | null = null;
    try {
      context = canvas.getContext("2d");
    } catch {
      return;
    }
    if (!context) return;

    const devicePixelRatio = Math.min(globalThis.devicePixelRatio || 1, 2);
    canvas.width = Math.max(1, Math.round(containerWidth * devicePixelRatio));
    canvas.height = Math.max(1, Math.round(layout.height * devicePixelRatio));
    canvas.style.height = `${layout.height}px`;
    context.setTransform(devicePixelRatio, 0, 0, devicePixelRatio, 0, 0);
    context.clearRect(0, 0, containerWidth, layout.height);
    context.fillStyle = "#0b0d0c";
    context.fillRect(0, 0, containerWidth, layout.height);
    context.font = '600 10px "SFMono-Regular", Consolas, monospace';
    context.textBaseline = "top";

    for (const group of layout.groups) {
      context.fillStyle = "#8f9991";
      context.fillText(group.source, 0, group.startY + 3);
      for (let localIndex = 0; localIndex < group.count; localIndex += 1) {
        const item = data.items[group.startIndex + localIndex];
        const row = Math.floor(localIndex / layout.columns);
        const column = localIndex % layout.columns;
        const x = column * (layout.cellSize + layout.gap);
        const y = group.cellStartY + row * (layout.cellSize + layout.gap);
        context.fillStyle = mediaCountColor(item.media_count);
        context.fillRect(x, y, layout.cellSize, layout.cellSize);
        if (group.startIndex + localIndex === hoveredIndex) {
          context.strokeStyle = "#f0f3cf";
          context.lineWidth = 1.5;
          context.strokeRect(x - 0.75, y - 0.75, layout.cellSize + 1.5, layout.cellSize + 1.5);
        } else if (group.startIndex + localIndex === selectedIndex) {
          context.strokeStyle = "#d7e67a";
          context.lineWidth = 1.5;
          context.strokeRect(x - 0.75, y - 0.75, layout.cellSize + 1.5, layout.cellSize + 1.5);
        }
      }
    }
  }, [containerWidth, data.items, hoveredIndex, layout, selectedIndex]);

  function hitTest(event: MouseEvent<HTMLCanvasElement>): number | null {
    const canvas = canvasRef.current;
    if (!canvas) return null;
    const bounds = canvas.getBoundingClientRect();
    const x = event.clientX - bounds.left;
    const y = event.clientY - bounds.top;
    for (const group of layout.groups) {
      const groupHeight = group.rowCount * (layout.cellSize + layout.gap);
      if (y < group.cellStartY || y >= group.cellStartY + groupHeight) continue;
      const row = Math.floor((y - group.cellStartY) / (layout.cellSize + layout.gap));
      const column = Math.floor(x / (layout.cellSize + layout.gap));
      if (column < 0 || column >= layout.columns) return null;
      const cellX = column * (layout.cellSize + layout.gap);
      const cellY = group.cellStartY + row * (layout.cellSize + layout.gap);
      if (
        x < cellX ||
        x > cellX + layout.cellSize ||
        y < cellY ||
        y > cellY + layout.cellSize
      ) {
        return null;
      }
      const index = group.startIndex + row * layout.columns + column;
      return index < group.startIndex + group.count ? index : null;
    }
    return null;
  }

  function activateIndex(index: number | null) {
    if (index === null) return;
    const item = data.items[index];
    if (!item) return;
    setKeyboardSelectedIndex(index);
    onSelectPrompt(item.prompt_id);
  }

  function handleKeyDown(event: KeyboardEvent<HTMLCanvasElement>) {
    if (!data.items.length) return;
    const currentIndex = selectedIndex ?? 0;
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      activateIndex(currentIndex);
      return;
    }
    if (!["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(event.key)) return;
    event.preventDefault();
    const direction = event.key.replace("Arrow", "").toLowerCase() as
      | "left"
      | "right"
      | "up"
      | "down";
    setKeyboardSelectedIndex(moveSelection(layout, currentIndex, direction));
  }

  const activeIndex = hoveredIndex ?? selectedIndex;
  const activeItem = activeIndex === null ? null : data.items[activeIndex] ?? null;
  const maxLabel = data.max_media_count > 0 ? `${data.max_media_count} max` : "no linked media";
  const scopeLabel = [
    "favorites",
    includeNotFaved ? "not-faved" : null,
    includeTrash ? "trash" : null,
  ]
    .filter(Boolean)
    .join(" + ");
  const footerText = activeItem
    ? `${activeItem.prompt_id} · ${activeItem.media_count} media`
    : `Showing ${scopeLabel}. Click a square to open its prompt`;

  return (
    <section className="prompt-registry-heatmap" aria-label="Prompt contribution matrix">
      <div className="prompt-registry-heatmap-toolbar">
        <div>
          <p className="kicker">Prompt contribution matrix</p>
          <h3>
            {data.total.toLocaleString()} prompts <span className="muted">· {maxLabel}</span>
          </h3>
        </div>
        <div className="prompt-registry-heatmap-controls">
          <div
            className="prompt-registry-heatmap-scope"
            role="group"
            aria-label="Heatmap media scope"
          >
            <label>
              <input
                type="checkbox"
                checked={includeNotFaved}
                onChange={(event) => onIncludeNotFavedChange(event.target.checked)}
              />
              Include not-faved
            </label>
            <label>
              <input
                type="checkbox"
                checked={includeTrash}
                onChange={(event) => onIncludeTrashChange(event.target.checked)}
              />
              Include trash
            </label>
          </div>
          <label className="prompt-registry-heatmap-zoom">
            Zoom
            <input
              type="range"
              min="0.75"
              max="2"
              step="0.25"
              value={zoom}
              onChange={(event) => setZoom(Number(event.target.value))}
              aria-label="Prompt heatmap zoom"
            />
          </label>
        </div>
      </div>
      <div ref={containerRef} className="prompt-registry-heatmap-canvas-wrap">
        <canvas
          ref={canvasRef}
          className="prompt-registry-heatmap-canvas"
          role="img"
          aria-label="Prompt registry heatmap. Use arrow keys to select a prompt and Enter to open it."
          aria-keyshortcuts="ArrowLeft ArrowRight ArrowUp ArrowDown Enter"
          tabIndex={0}
          data-testid="prompt-registry-heatmap-canvas"
          onClick={(event) => activateIndex(hitTest(event))}
          onKeyDown={handleKeyDown}
          onMouseMove={(event) => {
            const nextIndex = hitTest(event);
            setHoveredIndex((current) => (current === nextIndex ? current : nextIndex));
            if (nextIndex === null) {
              setTooltipPosition(null);
            } else {
              // Keep the tooltip inside the canvas wrapper: an absolutely
              // positioned tooltip that crosses the padded edge would create
              // scrollbars and shift the matrix while hovering.
              const wrap = containerRef.current;
              const maxX = (wrap?.clientWidth ?? 0) - 272;
              const maxY = (wrap?.clientHeight ?? 0) - 56;
              setTooltipPosition({
                x: Math.max(8, Math.min(event.nativeEvent.offsetX + 12, maxX)),
                y: Math.max(8, Math.min(event.nativeEvent.offsetY + 12, maxY)),
              });
            }
          }}
          onMouseLeave={() => {
            setHoveredIndex(null);
            setTooltipPosition(null);
          }}
        />
        {activeItem && tooltipPosition ? (
          <div
            className="prompt-registry-heatmap-tooltip"
            style={{ left: tooltipPosition.x, top: tooltipPosition.y }}
          >
            <strong>{activeItem.prompt_id}</strong>
            <span>{activeItem.media_count} media</span>
          </div>
        ) : null}
      </div>
      <div className="prompt-registry-heatmap-footer">
        <div className="prompt-registry-heatmap-legend" aria-label="Media count legend">
          {[0, 1, 2, 4, 8, 16].map((mediaCount) => (
            <span key={mediaCount}>
              <i style={{ background: mediaCountColor(mediaCount) }} />
              {mediaCount === 0 ? "0" : mediaCount === 16 ? "16+" : mediaCount}
            </span>
          ))}
        </div>
        <p className="muted" aria-live="polite" title={footerText}>
          {footerText}
        </p>
      </div>
    </section>
  );
}
