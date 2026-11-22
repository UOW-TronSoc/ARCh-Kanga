import { Component, useEffect, useRef, useState, type CSSProperties, type ErrorInfo, type ReactNode } from 'react';
import { Expand, TriangleAlert } from 'lucide-react';
import { ContentPicker, type ContentPickerOption } from './ContentPicker';
import { PanelActionsContext } from './panelActionsContext';
import type { PanelContentDefinition, PanelSize } from './types';
import styles from './ViewPanel.module.css';

interface BoundaryProps { label: string; onRetry: () => void; children: ReactNode }
interface BoundaryState { failed: boolean }

class PanelErrorBoundary extends Component<BoundaryProps, BoundaryState> {
  state: BoundaryState = { failed: false };

  static getDerivedStateFromError(): BoundaryState { return { failed: true }; }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error(`Panel content "${this.props.label}" failed`, error, info);
  }

  render() {
    if (!this.state.failed) return this.props.children;
    return (
      <button className={styles.notice} type="button" onClick={this.props.onRetry}>
        <TriangleAlert size={16} /><span>{this.props.label} unavailable<small>Retry</small></span>
      </button>
    );
  }
}

interface ViewPanelProps {
  content: PanelContentDefinition | undefined;
  size: PanelSize;
  active: boolean;
  slotLabel: string;
  options: readonly ContentPickerOption[];
  onSelect: (contentId: string) => void;
  onPromote?: () => void;
  onResize?: (width: number) => void;
  className?: string;
  style?: CSSProperties;
}

export function ViewPanel({ content, size, active, slotLabel, options, onSelect, onPromote, onResize, className = '', style }: ViewPanelProps) {
  const panelRef = useRef<HTMLElement>(null);
  const [actionsTarget, setActionsTarget] = useState<HTMLElement | null>(null);
  const [attempt, setAttempt] = useState(0);
  const label = content?.label ?? 'Empty panel';
  const Icon = content?.icon;

  const onResizeRef = useRef(onResize);
  useEffect(() => { onResizeRef.current = onResize; });

  // CSS `resize` writes an inline width; only that, not layout-driven width changes, counts as a user size.
  useEffect(() => {
    const panel = panelRef.current;
    if (!panel || typeof ResizeObserver === 'undefined') return;
    const observer = new ResizeObserver(() => {
      const width = parseFloat(panel.style.width);
      if (Number.isFinite(width)) onResizeRef.current?.(Math.round(width));
    });
    observer.observe(panel);
    return () => observer.disconnect();
  }, []);

  const toggleFullscreen = () => {
    if (document.fullscreenElement) void document.exitFullscreen();
    else void panelRef.current?.requestFullscreen();
  };

  return (
    <section ref={panelRef} className={`${styles.panel} ${styles[size]} ${className}`} style={style} aria-label={`${slotLabel}: ${label}`}>
      <header className={styles.header}>
        {Icon && <Icon size={13} />}
        <ContentPicker className={styles.picker} label={`${slotLabel} content`} value={content?.id ?? ''} options={options} onChange={onSelect} />
        <div ref={setActionsTarget} className={styles.actions} />
        {size !== 'inset' && (
          <button className={styles.iconButton} type="button" aria-label="Toggle fullscreen" title="Toggle fullscreen" onClick={toggleFullscreen}><Expand size={15} /></button>
        )}
      </header>
      <div className={styles.body}>
        <PanelActionsContext.Provider value={actionsTarget}>
          {content
            ? <PanelErrorBoundary key={`${content.id}-${attempt}`} label={label} onRetry={() => setAttempt((value) => value + 1)}>{content.render({ size, active })}</PanelErrorBoundary>
            : <div className={styles.notice}>No content assigned</div>}
        </PanelActionsContext.Provider>
        {onPromote && <button className={styles.promote} type="button" aria-label={`Show ${label} in main view`} title={`Show ${label} in main view`} onClick={onPromote} />}
      </div>
    </section>
  );
}
