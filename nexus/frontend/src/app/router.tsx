import { useEffect, useState } from 'react';
import { Navigate, createBrowserRouter, useLocation } from 'react-router-dom';
import { OperatorShell } from '../layouts/OperatorShell/OperatorShell';
import { LoginPage } from '../pages/LoginPage/LoginPage';
import { PlaceholderPage } from '../pages/PlaceholderPage/PlaceholderPage';

function LiveSessionGate() {
  const live = import.meta.env.VITE_NEXUS_DATA_SOURCE === 'live';
  const location = useLocation();
  const [authed, setAuthed] = useState<boolean | null>(live ? null : true);

  useEffect(() => {
    if (!live) return undefined;
    let cancelled = false;
    fetch('/api/session', { credentials: 'same-origin' })
      .then((response) => response.json())
      .then((body: { authenticated?: boolean }) => {
        if (!cancelled) setAuthed(Boolean(body.authenticated));
      })
      .catch(() => {
        if (!cancelled) setAuthed(false);
      });
    return () => {
      cancelled = true;
    };
  }, [live, location.pathname]);

  if (!live) return <OperatorShell />;
  if (authed === null) return null;
  if (!authed) return <Navigate to={`/login?next=${encodeURIComponent(location.pathname)}`} replace />;
  return <OperatorShell />;
}

export const router = createBrowserRouter([
  { path: '/login', element: <LoginPage /> },
  {
    element: <LiveSessionGate />,
    children: [
      { path: '/rover', element: null },
      { path: '/launch', element: <PlaceholderPage /> },
      { path: '/cameras', element: <PlaceholderPage /> },
      { path: '/mapping', element: <PlaceholderPage /> },
      { path: '/systems', element: <PlaceholderPage /> },
    ],
  },
  { path: '*', element: <Navigate to="/rover" replace /> },
]);
