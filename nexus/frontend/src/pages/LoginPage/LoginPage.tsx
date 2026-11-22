import { FormEvent, useState } from 'react';
import { ArrowRight, LockKeyhole } from 'lucide-react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Button } from '../../components/ui/Button';
import styles from './LoginPage.module.css';

export function safeNextPath(value: string | null): string {
  if (!value || !value.startsWith('/') || value.startsWith('//')) return '/rover';
  return value;
}

export function LoginPage({ mode = import.meta.env.VITE_NEXUS_DATA_SOURCE }: { mode?: string }) {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [pin, setPin] = useState('');
  const [error, setError] = useState<string | null>(null);
  const live = mode === 'live';

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!live) {
      navigate('/rover');
      return;
    }
    const response = await fetch('/api/session', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pin }),
    });
    if (!response.ok) {
      setError('Incorrect PIN');
      return;
    }
    navigate(safeNextPath(params.get('next')));
  }

  return (
    <main className={styles.page}>
      <div className={styles.grid} />
      <section className={styles.card}>
        <span className={styles.mark}><img src="https://framerusercontent.com/images/E6L6SZoGo2lOuwrHJT8fDQdAE.png?scale-down-to=512&amp;width=2160&amp;height=2160" alt="TronSoc" /></span>
        <p>KANGA BASESTATION</p><h1>Operator access</h1>
        {!live && <span className={styles.copy}>Authentication is represented visually in this frontend slice. Continue into the deterministic mock workspace.</span>}
        <form onSubmit={submit}>
          <label><span>OPERATOR PIN</span><div><LockKeyhole size={16} /><input aria-label="Operator PIN" type="password" placeholder="••••••" maxLength={6} value={pin} onChange={(event) => setPin(event.target.value)} /></div></label>
          {error && <p role="alert">{error}</p>}
          <Button variant="primary" type="submit">{live ? 'Continue' : 'Enter mock workspace'} <ArrowRight size={16} /></Button>
        </form>
        {!live && <small>MOCK MODE · NO LIVE COMMANDS</small>}
      </section>
    </main>
  );
}
