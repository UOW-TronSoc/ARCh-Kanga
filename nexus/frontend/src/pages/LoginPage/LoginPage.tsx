import { ArrowRight, LockKeyhole } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { Button } from '../../components/ui/Button';
import styles from './LoginPage.module.css';

export function LoginPage() {
  const navigate = useNavigate();
  return (
    <main className={styles.page}>
      <div className={styles.grid} />
      <section className={styles.card}>
        <span className={styles.mark}><img src="https://framerusercontent.com/images/E6L6SZoGo2lOuwrHJT8fDQdAE.png?scale-down-to=512&amp;width=2160&amp;height=2160" alt="TronSoc" /></span>
        <p>KANGA BASESTATION</p><h1>Operator access</h1>
        <span className={styles.copy}>Authentication is represented visually in this frontend slice. Continue into the deterministic mock workspace.</span>
        <label><span>OPERATOR PIN</span><div><LockKeyhole size={16} /><input aria-label="Operator PIN" type="password" placeholder="••••••" maxLength={6} /></div></label>
        <Button variant="primary" onClick={() => navigate('/rover')}>Enter mock workspace <ArrowRight size={16} /></Button>
        <small>MOCK MODE · NO LIVE COMMANDS</small>
      </section>
    </main>
  );
}
