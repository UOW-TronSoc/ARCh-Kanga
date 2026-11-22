import type { ButtonHTMLAttributes, PropsWithChildren } from 'react';
import styles from './Button.module.css';

type ButtonVariant = 'primary' | 'secondary' | 'danger' | 'ghost';

export function Button({
  children,
  variant = 'secondary',
  className = '',
  ...props
}: PropsWithChildren<ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ButtonVariant }>) {
  return <button className={`${styles.button} ${styles[variant]} ${className}`} {...props}>{children}</button>;
}
