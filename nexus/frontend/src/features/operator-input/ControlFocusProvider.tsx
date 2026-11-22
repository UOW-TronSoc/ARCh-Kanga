import { useEffect, useMemo, useRef, type PropsWithChildren } from 'react';
import { useMatch } from 'react-router-dom';
import { useAppDataService } from '../../app/appDataContext';
import { ControlFocusContext } from './controlFocusContext';
import { controlTargetForRoverRoute } from './controlFocusRoute';

const ROVER_PATH = '/rover';

export function ControlFocusProvider({ children }: PropsWithChildren) {
  const onRover = useMatch(ROVER_PATH) !== null;
  const focus = useMemo(() => controlTargetForRoverRoute(onRover), [onRover]);
  const service = useAppDataService();
  const previousKindRef = useRef(focus.kind);

  useEffect(() => {
    if (previousKindRef.current !== focus.kind) {
      service.disarmDriveInput();
      previousKindRef.current = focus.kind;
    }
  }, [focus.kind, service]);

  return <ControlFocusContext.Provider value={focus}>{children}</ControlFocusContext.Provider>;
}