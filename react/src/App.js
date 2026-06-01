import { lazy, Suspense, useEffect } from 'react';
import { Card } from 'primereact/card';
import { Tag } from 'primereact/tag';
import { HashRouter as Router, Route, Routes, useNavigate } from 'react-router-dom';
import Navbar from './Navbar';
import './App.scss';
import { ecosystems } from './ecosystems';
import { ThemeProvider, useTheme } from './theme';
import { fetchDatasetForSelection, getAvailableSnapshots } from './data';

const EcosystemDashboard = lazy(() =>
  import(/* webpackPrefetch: true */ './dashboard/EcosystemDashboard').then((m) => ({ default: m.EcosystemDashboard }))
);

function EcosystemLanding() {
  const navigate = useNavigate();

  // Kick off data fetch for the newest snapshot of each available ecosystem
  // during browser idle time, so the data is already cached when the user
  // navigates to the dashboard.
  useEffect(() => {
    const ric = typeof requestIdleCallback === 'function' ? requestIdleCallback : (cb) => setTimeout(cb, 300);
    const cic = typeof cancelIdleCallback === 'function' ? cancelIdleCallback : clearTimeout;
    const id = ric(() => {
      ecosystems
        .filter((e) => e.status === 'available')
        .forEach((e) => {
          const snapshots = getAvailableSnapshots(e.id);
          if (snapshots[0]) fetchDatasetForSelection(e.id, snapshots[0]);
        });
    });
    return () => cic(id);
  }, []);

  return (
    <section className="content">
      <h1>Community-Driven Variability Ecosystem Explorer</h1>
      <p>
        Modern decentralized software ecosystems evolve through crowdsourced improvement proposals (IPs) that are continuously shaped and autonomously implemented by independent actors. As a result, these ecosystems exhibit so-called Community-Driven
Variability (CDV), a novel paradigm that extends beyond traditional variability-intensive systems. This page allows to explore the proposal space of such ecosystems by providing interactive visualizations and insights about their evolution, authorship, classification, conformity, and inter-proposal relationships.
      </p>

      <div className="ecosystem-grid">
        {ecosystems.map((ecosystem) => {
          const available = ecosystem.status === 'available';

          return (
            <Card
              key={ecosystem.id}
              className={`ecosystem-card${available ? ' ecosystem-card--available' : ' ecosystem-card--muted'}`}
              onClick={available ? () => navigate(`/ecosystem/${ecosystem.id}`) : undefined}
              tabIndex={available ? 0 : undefined}
              role={available ? 'button' : undefined}
              onKeyDown={available ? (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); navigate(`/ecosystem/${ecosystem.id}`); } } : undefined}
            >
              <div>
                <div className="ecosystem-card-header">
                  <img className="ecosystem-logo" src={ecosystem.logo} alt={`${ecosystem.name} logo`} />
                  <h2>{ecosystem.name}</h2>
                </div>
                <p>{ecosystem.description}</p>
                <div className="ecosystem-meta">
                  <div className="ecosystem-meta__info">
                    <Tag
                      severity={available ? 'success' : 'secondary'}
                      value={available ? 'Available now' : 'Coming soon'}
                    />
                    <span>{ecosystem.proposalShortPlural}</span>
                  </div>
                  {available ? (
                    <span className="ecosystem-meta__open" aria-hidden="true">
                      Open <i className="pi pi-arrow-right" />
                    </span>
                  ) : null}
                </div>
              </div>
            </Card>
          );
        })}
      </div>
    </section>
  );
}

function AboutPage() {
  return (
    <section className="content" style={{ padding: '2rem' }}>
      <h1>About This Project</h1>
      <p>
        This app is evolving from a Bitcoin-focused explorer into a more general proposal-analysis frontend.
        Bitcoin is the first implemented ecosystem, but the repo is now being organized so other ecosystems
        such as Nostr NIPs or Tor proposals can be added behind the same navigation model.
      </p>
    </section>
  );
}

function AppShell() {
  const { resolvedTheme } = useTheme();

  useEffect(() => {
    let prev = null;
    function onMove(e) {
      const card = e.target.closest('.p-card');
      if (prev && prev !== card) {
        prev.style.removeProperty('--mx');
        prev.style.removeProperty('--my');
      }
      prev = card;
      if (!card) return;
      const r = card.getBoundingClientRect();
      const x = ((e.clientX - r.left) / r.width - 0.5) * 8;
      const y = ((e.clientY - r.top) / r.height - 0.5) * 8;
      card.style.setProperty('--mx', -x);
      card.style.setProperty('--my', -y);
    }
    document.addEventListener('mousemove', onMove);
    return () => document.removeEventListener('mousemove', onMove);
  }, []);

  return (
    <Router>
      <div className={`App App--${resolvedTheme}`}>
        <Navbar />
        <Routes>
          <Route path="/" element={<EcosystemLanding />} />
          <Route
            path="/ecosystem/:ecosystemId"
            element={
              <Suspense fallback={<section className="content" />}>
                <EcosystemDashboard />
              </Suspense>
            }
          />
          <Route path="/about" element={<AboutPage />} />
        </Routes>
      </div>
    </Router>
  );
}

function App() {
  return (
    <ThemeProvider>
      <AppShell />
    </ThemeProvider>
  );
}

export default App;
