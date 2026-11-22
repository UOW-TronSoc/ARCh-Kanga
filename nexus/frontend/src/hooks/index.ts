import { useAppDataService, useAppSnapshot } from '../app/appDataContext';

export const useRoverSnapshot = () => useAppSnapshot().rover;
export const useSafetyState = () => useAppSnapshot().safety;
export const useSafetyControls = () => {
  const safety = useAppSnapshot().safety;
  const service = useAppDataService();
  return {
    ...safety,
    assertDrivestop: service.assertDrivestop,
    releaseDrivestop: service.releaseDrivestop,
    toggleClosedLoop: service.toggleClosedLoop,
  };
};
export const useConnectionState = () => useAppSnapshot().connection;
export const useDriveControls = () => {
  const drive = useAppSnapshot().drive;
  const service = useAppDataService();
  return {
    ...drive,
    toggleInputArm: service.toggleInputArm,
    setSpeedLimit: service.setSpeedLimit,
  };
};
