import React, { useState } from 'react';
import { Dialog } from 'primereact/dialog';
import { Button } from 'primereact/button';
import { Link } from 'react-router-dom';
import { FaGithub } from 'react-icons/fa';
import { useTheme } from './theme';
import './Navbar.scss';

const REPOSITORY_URL = 'https://github.com/ranonymousse/cdv-explorer';

const Navbar = () => {
  const [mobileMenuVisible, setMobileMenuVisible] = useState(false);
  const { themeMode, resolvedTheme, cycleThemeMode } = useTheme();

  const items = [
    { label: 'Home', url: '/' },
    { label: 'About', url: '/about' },
  ];

  const toggleMobileMenu = () => {
    setMobileMenuVisible(!mobileMenuVisible);
  };

  const themeLabel = themeMode === 'system'
    ? `Auto (${resolvedTheme})`
    : themeMode.charAt(0).toUpperCase() + themeMode.slice(1);
  const themeIcon = themeMode === 'system'
    ? 'pi pi-desktop'
    : resolvedTheme === 'dark'
      ? 'pi pi-moon'
      : 'pi pi-sun';

  return (
    <div className="nav-bar">
      <div className="nav-logo">
        <Link to="/" className="nav-brand">CDV Explorer</Link>
      </div>

      <div className="nav-items">
        {items.map((item) => (
          <Link to={item.url} key={item.url} className="nav-item">
            {item.label}
          </Link>
        ))}
      </div>

      <div className="nav-actions">
        <button
          type="button"
          className="nav-action-button nav-theme-button"
          onClick={cycleThemeMode}
          title={`Theme mode: ${themeLabel}. Click to cycle system, dark, and light.`}
          aria-label={`Theme mode: ${themeLabel}. Click to cycle system, dark, and light.`}
        >
          <i className={themeIcon} aria-hidden="true" />
          <span>{themeLabel}</span>
        </button>

        <a
          href={REPOSITORY_URL}
          className="nav-action-button nav-github-button"
          target="_blank"
          rel="noreferrer"
          aria-label="Open the repository on GitHub"
          title="Open the repository on GitHub"
        >
          <FaGithub aria-hidden="true" />
        </a>
      </div>

      <div className="mobile-menu">
        <Button
          icon="pi pi-bars"
          className="mobile-menu__toggle"
          text
          rounded
          aria-label="Open navigation menu"
          onClick={toggleMobileMenu}
        />

        <Dialog
          visible={mobileMenuVisible}
          modal
          style={{ width: '95vw' }}
          onHide={toggleMobileMenu}
          closable
          draggable={false}
          resizable={false}
          blockScroll
          dismissableMask
        >
          {items.map((item) => (
            <Link
              to={item.url}
              key={item.url}
              className="mobile-nav-item"
              onClick={toggleMobileMenu}
            >
              {item.label}
            </Link>
          ))}

          <button
            type="button"
            className="mobile-nav-action"
            onClick={cycleThemeMode}
          >
            <i className={themeIcon} aria-hidden="true" />
            <span>{`Theme: ${themeLabel}`}</span>
          </button>

          <a
            href={REPOSITORY_URL}
            className="mobile-nav-action"
            target="_blank"
            rel="noreferrer"
          >
            <FaGithub aria-hidden="true" />
            <span>GitHub Repository</span>
          </a>
        </Dialog>
      </div>
    </div>
  );
};

export default Navbar;
