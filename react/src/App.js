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

const aboutPublications = [
  {
    title: 'Beyond Software Families: Community-Driven Variability',
    citation: 'Roman Bögli, Alexander Boll, Alexander Schultheiß and Timo Kehrer, in Companion Proc. Int’l Conf. on the Foundations of Software Engineering (FSE), Trondheim, Norway, Jun. 2025.',
    href: 'https://dl.acm.org/doi/10.1145/3696630.3728501',
    doi: '10.1145/3696630.3728501',
  },
  {
    title: 'Community-Driven Variability: Characterizing a new Software Variability Paradigm',
    citation: 'Roman Bögli, Alexander Boll, Alexander Schultheiß and Timo Kehrer, Autom. Softw. Eng., Mar. 2026.',
    href: 'https://link.springer.com/article/10.1007/s10515-026-00594-0',
    doi: '10.1007/s10515-026-00594-0',
  },
  {
    title: 'Towards Systematic Treatment of Community-Driven Variability',
    citation: 'Roman Bögli, in Companion Proc. Int’l Conf. on Software Engineering (ICSE): Doctoral Symposium, Rio de Janeiro, Brazil, Apr. 2026.',
    href: 'https://doi.org/10.1145/3774748.3787644',
    doi: '10.1145/3774748.3787644',
  },
  {
    title: 'CDV-Explorer: Navigating Improvement Proposal Spectra in Decentralized OSS Ecosystem',
    citation: 'Roman Bögli and Timo Kehrer, in Companion Proc. Int’l Conf. on Software and Systems Reuse, Product Lines, and Configuration (VARIABILITY), Limassol, Cyprus, Sep. 2026.',
  },
];

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
  const { resolvedTheme } = useTheme();
  const publicBase = import.meta.env.BASE_URL;
  const unibeLogoSrc = `${publicBase}about/${resolvedTheme === 'dark' ? 'unibe_logo_darkmode.png' : 'unibe_logo_lightmode.png'}`;

  return (
    <section className="content about-page">
      <div className="about-page__intro">
        <h1>About CDV-Explorer</h1>
        <p>
          CDV-Explorer is a research tool for analyzing improvement proposals (IPs) in decentralized open-source software ecosystems. It supports the study of Community-Driven Variability (CDV) by making proposal histories, authorship, classifications, status evolution, and inter-proposal relations explorable across IP sources and historic snapshots.
        </p>
      </div>

      <div className="about-page__section">
        <div className="about-page__cards about-page__cards--two-column">
          <Card className="about-page__card about-page__card--link">
            <a
              className="about-page__link-tile"
              href="https://github.com/SEG-UNIBE/cdv-explorer"
              target="_blank"
              rel="noreferrer"
            >
              <span className="about-page__link-icon-wrap">
                <i className="pi pi-github about-page__link-icon" aria-hidden="true" />
              </span>
              <span className="about-page__link-copy">
                <span className="about-page__link-label">Code Repository</span>
                <span className="about-page__link-target">github.com/SEG-UNIBE/cdv-explorer</span>
              </span>
            </a>
          </Card>
          <Card className="about-page__card about-page__card--link">
            <a
              className="about-page__link-tile"
              href="https://youtu.be/56GKRexRuoI"
              target="_blank"
              rel="noreferrer"
            >
              <span className="about-page__link-icon-wrap">
                <i className="pi pi-youtube about-page__link-icon" aria-hidden="true" />
              </span>
              <span className="about-page__link-copy">
                <span className="about-page__link-label">Demo Video</span>
                <span className="about-page__link-target">youtu.be/56GKRexRuoI</span>
              </span>
            </a>
          </Card>
        </div>
      </div>

      <div className="about-page__section">
        <h2>Related Publications</h2>
        <div className="about-page__publications">
          {aboutPublications.map((publication) => (
            <Card key={publication.title} className="about-page__card about-page__card--publication">
              <p className="about-page__publication-entry">
                <strong>{publication.title}.</strong>{' '}
                {publication.citation}{' '}
                {publication.doi ? (
                  <a
                    className="about-page__publication-doi"
                    href={publication.href}
                    target="_blank"
                    rel="noreferrer"
                  >
                    DOI: {publication.doi}
                  </a>
                ) : (
                  <span className="about-page__publication-doi about-page__publication-doi--muted">
                    DOI: forthcoming
                  </span>
                )}
              </p>
            </Card>
          ))}
        </div>
      </div>

      <div className="about-page__section">
        <h2>Organization</h2>
        <div className="about-page__cards about-page__cards--two-column">
          <Card className="about-page__card about-page__card--organization">
            <p className="about-page__organization-copy">
              CDV-Explorer is primarily developed and maintained by{' '}
              <a href="https://romanboegli.ch" target="_blank" rel="noreferrer">Roman Bögli</a>.
              {' '}The project is part of his PhD work at the Software Engineering Group (SEG).
            </p>
            <div className="about-page__logo-card about-page__logo-card--seg">
              <img
                className="about-page__logo about-page__logo--seg"
                src={`${publicBase}about/seg_logo.png`}
                alt="Software Engineering Group logo"
              />
            </div>
          </Card>
          <Card className="about-page__card about-page__card--organization">
            <div className="about-page__organization-split">
              <p className="about-page__organization-copy">
                SEG is part of the Institute of Computer Science at the{' '}
                <a href="https://www.unibe.ch/" target="_blank" rel="noreferrer">University of Bern</a> in Switzerland🇨🇭.
              </p>
              <div className="about-page__logo-card about-page__logo-card--unibe">
                <img
                  className="about-page__logo about-page__logo--unibe"
                  src={unibeLogoSrc}
                  alt="University of Bern logo"
                />
              </div>
            </div>
          </Card>
        </div>
      </div>
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
