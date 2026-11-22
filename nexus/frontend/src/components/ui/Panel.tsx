import type { HTMLAttributes, PropsWithChildren, ReactNode } from 'react';
import styles from './Panel.module.css';

export function Panel({
  children, title, action, className = '', ...props
}: PropsWithChildren<HTMLAttributes<HTMLElement> & { title?: string; action?: ReactNode }>) {
  return (
    <section className={`${styles.panel} ${className}`} {...props}>
      {(title || action) && <header className={styles.header}>{title && <h2>{title}</h2>}{action}</header>}
      {children}
    </section>
  );
}
