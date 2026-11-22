import type { LucideIcon } from 'lucide-react';
import { ArrowRight, Camera, Cpu, Map, Rocket } from 'lucide-react';
import { Link, useLocation } from 'react-router-dom';
import { Panel } from '../../components/ui/Panel';
import styles from './PlaceholderPage.module.css';

const content: Record<string, { icon: LucideIcon; title: string; eyebrow: string; description: string; items: string[] }> = {
  '/launch': { icon: Rocket, title: 'Launch manager', eyebrow: 'SYSTEM ORCHESTRATION', description: 'Allowlisted rover profiles, dependency visibility, and deliberate launch controls will live here.', items: ['Profile readiness', 'Launch sequencing', 'Process health'] },
  '/cameras': { icon: Camera, title: 'Camera workspace', eyebrow: 'VISUAL OPERATIONS', description: 'Low-latency rover feeds will use this workspace without coupling video lifecycle to drive safety.', items: ['Feed selection', 'Stream health', 'Capture controls'] },
  '/mapping': { icon: Map, title: 'Mapping & autonomy', eyebrow: 'MISSION CONTEXT', description: 'Map state, route planning, and autonomy supervision are reserved behind a focused operational boundary.', items: ['Map layers', 'Waypoint planning', 'Autonomy state'] },
  '/systems': { icon: Cpu, title: 'Systems engineering', eyebrow: 'DIAGNOSTICS', description: 'Deep health, motor commissioning, logs, and engineering tools will remain separate from core driving.', items: ['Subsystem health', 'Commissioning', 'Logs & terminal'] },
};

export function PlaceholderPage() {
  const { pathname } = useLocation();
  const page = content[pathname] ?? content['/systems'];
  const Icon = page.icon;
  return (
    <div className={styles.page}>
      <div className={styles.glow} />
      <Panel className={styles.card}>
        <span className={styles.icon}><Icon size={26} /></span>
        <p>{page.eyebrow}</p>
        <h1>{page.title}</h1>
        <div className={styles.rule} />
        <span className={styles.description}>{page.description}</span>
        <div className={styles.items}>{page.items.map((item, index) => <span key={item}><b>0{index + 1}</b>{item}</span>)}</div>
        <Link to="/rover">Return to rover <ArrowRight size={15} /></Link>
      </Panel>
    </div>
  );
}
