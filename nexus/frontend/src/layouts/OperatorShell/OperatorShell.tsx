import { useEffect } from 'react';
import { Camera, Cpu, Map, Orbit, Rocket } from 'lucide-react';
import { NavLink, Outlet, useMatch } from 'react-router-dom';
import { useAppDataService, useAppSnapshot } from '../../app/appDataContext';
import { useSafetyState } from '../../hooks';
import { DriveControlPanel } from '../../features/drive-control/DriveDock';
import { ControlFocusProvider } from '../../features/operator-input/ControlFocusProvider';
import { OperatorInputCoordinator } from '../../features/operator-input/OperatorInputCoordinator';
import { RoverPage } from '../../pages/RoverPage/RoverPage';
import styles from './OperatorShell.module.css';

const ROVER_PATH = '/rover';

const navItems = [
  { to: ROVER_PATH, label: 'Rover', icon: Orbit },
  { to: '/launch', label: 'Launch', icon: Rocket },
  { to: '/cameras', label: 'Cameras', icon: Camera },
  { to: '/mapping', label: 'Mapping', icon: Map },
  { to: '/systems', label: 'Systems', icon: Cpu },
];

export function OperatorShell() {
  const safety = useSafetyState();
  const service = useAppDataService();
  const holdingControl = useAppSnapshot().control?.role === 'holder';
  const onRover = useMatch(ROVER_PATH) !== null;
  useEffect(() => {
    const live = service as { start?: () => void; stop?: () => void };
    live.start?.();
    return () => live.stop?.();
  }, [service]);

  return (
    <ControlFocusProvider>
      <OperatorInputCoordinator>
        <div className={styles.shell}>
          <header className={`${styles.topbar} ${safety.drivestop ? styles.drivestopActive : ''} ${holdingControl ? styles.controlHeld : ''}`}>
            <div className={styles.brand}>
              <span className={styles.mark}><img src="https://framerusercontent.com/images/E6L6SZoGo2lOuwrHJT8fDQdAE.png?scale-down-to=512&amp;width=2160&amp;height=2160" alt="TronSoc" /></span>
              <span><strong>KANGA</strong><small>BASESTATION</small></span>
            </div>
            <div className={styles.team}>UOW <b>TRONSOC</b></div>
          </header>

          <nav className={styles.nav} aria-label="Primary navigation">
            {navItems.map(({ to, label, icon: Icon }) => (
              <NavLink key={to} to={to} className={({ isActive }) => `${styles.navItem} ${isActive ? styles.active : ''}`}>
                <Icon size={20} strokeWidth={1.8} /><span>{label}</span>
              </NavLink>
            ))}
          </nav>

          {onRover && <DriveControlPanel />}
          <main className={styles.content}>
            {/* Kept mounted so the 3D renderer and camera feeds survive route changes. */}
            <div className={styles.persistentPage} hidden={!onRover}><RoverPage /></div>
            <Outlet />
          </main>
        </div>
      </OperatorInputCoordinator>
    </ControlFocusProvider>
  );
}