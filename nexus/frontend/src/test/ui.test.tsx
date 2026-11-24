import { act, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, vi } from 'vitest';
import { MemoryRouter, Outlet, Route, Routes } from 'react-router-dom';
import { AppProviders } from '../app/providers';
import { OperatorShell } from '../layouts/OperatorShell/OperatorShell';
import { initialAppSnapshot } from '../fixtures';
import { LiveTelemetryService, type TelemetrySocket } from '../services/live/LiveTelemetryService';
import { MockAppDataService } from '../services/mock/MockAppDataService';
import {
  buildCriticalSnapshot,
  buildDisconnectedSnapshot,
  buildOperableSnapshot,
  buildStaleSnapshot,
} from './snapshotBuilders';
import type { AppSnapshot } from '../types';

function renderShell(initialPath = '/rover', snapshot: AppSnapshot = initialAppSnapshot) {
  const service = new MockAppDataService(snapshot);
  return {
    service,
    ...render(
      <AppProviders service={service}>
        <MemoryRouter initialEntries={[initialPath]}>
          <Routes>
            <Route element={<OperatorShell />}>
              <Route path="/rover" element={null} />
              <Route path="/launch" element={<><h1>Launch manager</h1><Outlet /></>} />
              <Route path="/cameras" element={<h1>Cameras</h1>} />
              <Route path="/mapping" element={<h1>Mapping</h1>} />
              <Route path="/systems" element={<h1>Systems</h1>} />
            </Route>
          </Routes>
        </MemoryRouter>
      </AppProviders>,
    ),
  };
}

class FakeSocket implements TelemetrySocket {
  onmessage: ((event: { data: string }) => void) | null = null;
  onclose: (() => void) | null = null;
  url = '';
  close() { this.onclose?.(); }
  server(payload: unknown) { this.onmessage?.({ data: JSON.stringify(payload) }); }
}

const liveSockets: FakeSocket[] = [];
let liveService: LiveTelemetryService | null = null;

beforeEach(() => window.sessionStorage.clear());

afterEach(() => {
  liveService?.stop();
  liveService = null;
  liveSockets.length = 0;
  vi.useRealTimers();
});

describe('Kanga operator shell', () => {
  it('renders the drive panel only on Rover with safe startup defaults', () => {
    renderShell();
    expect(screen.getByText('Detected gamepad')).toBeVisible();
    expect(screen.getByRole('button', { name: /Release drivestop/ })).toBeVisible();
    expect(screen.getByRole('navigation', { name: 'Primary navigation' })).toBeVisible();
    expect(screen.getByRole('region', { name: 'Main view: Rover model' })).toBeVisible();
    expect(screen.getByRole('slider', { name: 'Speed limit' })).toHaveValue('42');
  });

  it('hides the drive panel outside Rover while keeping drivestop shortcuts global', async () => {
    const { service } = renderShell();
    await userEvent.click(screen.getByRole('link', { name: /Launch/ }));
    expect(screen.queryByText('Detected gamepad')).not.toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Launch manager' })).toBeVisible();

    act(() => {
      window.dispatchEvent(new KeyboardEvent('keydown', { code: 'Space', key: ' ', bubbles: true }));
    });
    expect(service.getSnapshot().safety.drivestop).toBe(true);
  });

  it('disarms input when navigating away from Rover', async () => {
    const service = new MockAppDataService(buildOperableSnapshot());
    render(
      <AppProviders service={service}>
        <MemoryRouter initialEntries={['/rover']}>
          <Routes>
            <Route element={<OperatorShell />}>
              <Route path="/rover" element={null} />
              <Route path="/launch" element={<h1>Launch manager</h1>} />
            </Route>
          </Routes>
        </MemoryRouter>
      </AppProviders>,
    );

    act(() => {
      service.releaseDrivestop();
      service.toggleInputArm();
    });
    expect(service.getSnapshot().drive.inputArmed).toBe(true);

    await act(async () => {
      await userEvent.click(screen.getByRole('link', { name: /Launch/ }));
    });
    expect(service.getSnapshot().drive.inputArmed).toBe(false);
    expect(service.getSnapshot().safety.closedLoop).toBe(true);
  });

  it('renders critical faults and prevents drive arming', () => {
    renderShell('/rover', buildCriticalSnapshot());
    expect(screen.getAllByText('Front-right encoder fault')[0]).toBeVisible();
    expect(screen.getByRole('button', { name: /Drive input: Disabled/ })).toBeDisabled();
  });

  it('renders drivestop state and blocks drive input', () => {
    renderShell('/rover', initialAppSnapshot);
    expect(screen.getByRole('button', { name: /Release drivestop/ })).toBeVisible();
    expect(screen.getByRole('button', { name: /Drive input: Disabled/ })).toBeDisabled();
  });

  it.each(['stale', 'disconnected'] as const)('shows %s telemetry state', (fixture) => {
    const snapshot = fixture === 'stale' ? buildStaleSnapshot() : buildDisconnectedSnapshot();
    renderShell('/rover', snapshot);
    expect(screen.getAllByText(fixture === 'stale' ? 'stale' : 'unavailable').at(-1)).toBeVisible();
  });

  it('cancels a release without sending it', async () => {
    const service = new MockAppDataService({
      ...initialAppSnapshot,
      control: { role: 'holder', notice: null, error: null },
    });
    const release = vi.spyOn(service, 'releaseDrivestop');
    render(
      <AppProviders service={service}>
        <MemoryRouter initialEntries={['/rover']}>
          <Routes>
            <Route element={<OperatorShell />}>
              <Route path="/rover" element={null} />
            </Route>
          </Routes>
        </MemoryRouter>
      </AppProviders>,
    );
    await userEvent.click(screen.getByRole('button', { name: /Release drivestop/ }));
    expect(screen.getByRole('dialog', { name: 'Release drivestop?' })).toBeVisible();
    await userEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(release).not.toHaveBeenCalled();
    expect(screen.queryByRole('dialog', { name: 'Release drivestop?' })).not.toBeInTheDocument();
  });

  it('does not render a scenario selector', () => {
    renderShell();
    expect(screen.queryByLabelText('Mock scenario')).not.toBeInTheDocument();
  });

  it('shows the read-only drivestop state on the drive panel', () => {
    vi.useFakeTimers();
    liveService = new LiveTelemetryService({
      url: 'ws://nexus/ws/telemetry',
      socketFactory: (url: string) => {
        const socket = new FakeSocket();
        socket.url = url;
        liveSockets.push(socket);
        return socket;
      },
    });
    render(
      <AppProviders service={liveService}>
        <MemoryRouter initialEntries={['/rover']}>
          <Routes>
            <Route element={<OperatorShell />}>
              <Route path="/rover" element={null} />
              <Route path="/launch" element={<h1>Launch manager</h1>} />
            </Route>
          </Routes>
        </MemoryRouter>
      </AppProviders>,
    );
    expect(screen.getByText('WHS offline')).toBeVisible();
    expect(screen.getByRole('button', { name: 'Assert stop' })).toHaveTextContent('Unknown');

    act(() => {
      window.dispatchEvent(new KeyboardEvent('keydown', { code: 'Space', key: ' ', bubbles: true }));
      liveSockets[0]?.server({
        schemaVersion: 1,
        sequence: 1,
        serverTimestamp: '2026-11-22T07:00:00.000Z',
        rosAvailable: true,
        whsAvailable: true,
        drivestop: false,
      });
    });
    expect(screen.getByText('WHS online')).toBeVisible();
    expect(screen.getByRole('button', { name: 'Assert stop' })).toHaveTextContent('Released');
    expect(liveService.getSnapshot().safety.drivestop).toBe(false);

    act(() => {
      liveSockets[0]?.server({
        schemaVersion: 1,
        sequence: 2,
        serverTimestamp: '2026-11-22T07:00:01.000Z',
        rosAvailable: true,
        whsAvailable: true,
        drivestop: true,
      });
    });
    expect(screen.getByRole('button', { name: 'Assert stop' })).toHaveTextContent('Asserted');
    expect(screen.getByRole('button', { name: 'Assert stop' })).toBeDisabled();

    act(() => {
      liveSockets.find((socket) => socket.url?.includes('/ws/control'))?.server({
        type: 'state', role: 'holder', notice: null, error: null, armed: false,
      });
    });
    expect(screen.getByRole('button', { name: 'Release drivestop' })).toBeEnabled();

    act(() => {
      liveSockets[0]?.server({
        schemaVersion: 1,
        sequence: 3,
        serverTimestamp: '2026-11-22T07:00:02.000Z',
        rosAvailable: true,
        whsAvailable: false,
        drivestop: false,
      });
    });
    expect(screen.getByRole('button', { name: 'Assert stop' })).toHaveTextContent('Stale');
    expect(screen.getByRole('button', { name: 'Assert stop' })).toBeEnabled();
  });
});

describe('Rover view panels', () => {
  it('swaps an inset into the main view when clicked', async () => {
    renderShell();
    await userEvent.click(screen.getByRole('button', { name: 'Show Front navigation in main view' }));
    expect(screen.getByRole('region', { name: 'Main view: Front navigation' })).toBeVisible();
    expect(screen.getByRole('region', { name: 'Inset 1: Rover model' })).toBeVisible();
  });

  it('swaps panels when content is chosen from the picker', async () => {
    renderShell();
    await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Main view content' }), 'camera:rear-nav');
    expect(screen.getByRole('region', { name: 'Main view: Rear navigation' })).toBeVisible();
    expect(screen.getByRole('region', { name: 'Inset 2: Rover model' })).toBeVisible();
  });

  it('replaces a panel with content that is not in the layout', async () => {
    renderShell();
    await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Inset 2 content' }), 'camera:payload');
    expect(screen.getByRole('region', { name: 'Inset 2: Payload' })).toBeVisible();
    expect(screen.queryByRole('region', { name: /Rear navigation/ })).not.toBeInTheDocument();
  });

  it('applies a saved inset width to whatever content is in that slot', async () => {
    window.sessionStorage.setItem('nexus.panel-sizes.rover', JSON.stringify({ inset1: 320 }));
    renderShell();
    expect(screen.getByRole('region', { name: 'Inset 1: Front navigation' })).toHaveStyle({ width: '320px' });
    await userEvent.click(screen.getByRole('button', { name: 'Show Front navigation in main view' }));
    expect(screen.getByRole('region', { name: 'Inset 1: Rover model' })).toHaveStyle({ width: '320px' });
    expect(screen.getByRole('region', { name: 'Main view: Front navigation' }).style.width).toBe('');
  });

  it('keeps the rover renderer mounted while another page is shown', async () => {
    renderShell();
    const renderer = screen.getByTestId('mock-rover-renderer');
    await userEvent.click(screen.getByRole('link', { name: /Launch/ }));
    expect(renderer).toBeInTheDocument();
    expect(renderer).not.toBeVisible();
    await userEvent.click(screen.getByRole('link', { name: 'Rover' }));
    expect(screen.getByTestId('mock-rover-renderer')).toBe(renderer);
    expect(renderer).toBeVisible();
  });

  it('keeps the layout when navigating away and back', async () => {
    renderShell();
    await userEvent.click(screen.getByRole('button', { name: 'Show Rear navigation in main view' }));
    await userEvent.click(screen.getByRole('link', { name: /Launch/ }));
    await userEvent.click(screen.getByRole('link', { name: 'Rover' }));
    expect(screen.getByRole('region', { name: 'Main view: Rear navigation' })).toBeVisible();
    expect(screen.getByRole('region', { name: 'Inset 2: Rover model' })).toBeVisible();
  });
});