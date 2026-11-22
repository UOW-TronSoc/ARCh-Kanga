import { Navigate, createBrowserRouter } from 'react-router-dom';
import { OperatorShell } from '../layouts/OperatorShell/OperatorShell';
import { LoginPage } from '../pages/LoginPage/LoginPage';
import { PlaceholderPage } from '../pages/PlaceholderPage/PlaceholderPage';
export const router = createBrowserRouter([
  { path: '/login', element: <LoginPage /> },
  {
    element: <OperatorShell />,
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
