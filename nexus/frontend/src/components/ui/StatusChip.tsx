import type { PropsWithChildren } from 'react';
import type { StatusTone } from '../../types';
import styles from './StatusChip.module.css';

export function StatusChip({ children, tone = 'neutral', pulse = false }: PropsWithChildren<{ tone?: StatusTone; pulse?: boolean }>) {
  return <span className={`${styles.chip} ${styles[tone]}`}><span className={`${styles.dot} ${pulse ? styles.pulse : ''}`} />{children}</span>;
}
