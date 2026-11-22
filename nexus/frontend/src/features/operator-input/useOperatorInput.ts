import { useContext } from 'react';
import { OperatorInputContext } from './operatorInputContext';

export function useOperatorInput() {
  return useContext(OperatorInputContext);
}