import styles from './Metric.module.css';

export function Metric({ label, value, unit, emphasis = false }: { label: string; value: string | number; unit?: string; emphasis?: boolean }) {
  return <div className={`${styles.metric} ${emphasis ? styles.emphasis : ''}`}><span>{label}</span><strong>{value}{unit && <small>{unit}</small>}</strong></div>;
}
