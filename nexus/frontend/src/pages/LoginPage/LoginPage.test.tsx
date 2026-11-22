import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { LoginPage, safeNextPath } from './LoginPage';

function renderLogin(path = '/login') {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/login" element={<LoginPage mode="live" />} />
        <Route path="/rover" element={<h1>Rover</h1>} />
        <Route path="/cameras" element={<h1>Cameras</h1>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('PIN entry', () => {
  it('stays on the login screen when the PIN is wrong', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false }));
    renderLogin();
    await userEvent.type(screen.getByLabelText('Operator PIN'), '000000');
    await userEvent.click(screen.getByRole('button', { name: 'Continue' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Incorrect PIN');
    expect(screen.getByRole('heading', { name: 'Operator access' })).toBeVisible();
    vi.unstubAllGlobals();
  });

  it('opens the requested page after a correct PIN', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true }));
    renderLogin('/login?next=/cameras');
    await userEvent.type(screen.getByLabelText('Operator PIN'), '123456');
    await userEvent.click(screen.getByRole('button', { name: 'Continue' }));
    expect(await screen.findByRole('heading', { name: 'Cameras' })).toBeVisible();
    vi.unstubAllGlobals();
  });

  it('ignores an off-site next path', () => {
    expect(safeNextPath('https://example.com')).toBe('/rover');
    expect(safeNextPath('//example.com')).toBe('/rover');
    expect(safeNextPath('/cameras')).toBe('/cameras');
  });
});
