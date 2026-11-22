import { type PropsWithChildren } from 'react';
import type { OperatorInputState } from './operatorInputState';
import { OperatorInputContext } from './operatorInputContext';

export function OperatorInputProvider({
  children,
  value,
}: PropsWithChildren<{ value: OperatorInputState }>) {
  return <OperatorInputContext.Provider value={value}>{children}</OperatorInputContext.Provider>;
}