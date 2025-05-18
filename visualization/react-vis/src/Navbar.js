import React, { useState } from 'react';
import { Dialog } from 'primereact/dialog';
import { Button } from 'primereact/button';
import './Navbar.scss';
import logo from './logo.png';

const Navbar = () => {
  // State for controlling mobile menu visibility
  const [mobileMenuVisible, setMobileMenuVisible] = useState(false);

  // Sample navbar items
  const items = [
    { label: 'Home', url: '/' },
    { label: 'About', url: '/about' }
  ];

  // Function to toggle mobile menu visibility
  const toggleMobileMenu = () => {
    setMobileMenuVisible(!mobileMenuVisible);
  };

  return (
    <div className="nav-bar">
      <div className="nav-logo">
      <img src={logo} alt="Logo" style={{ height: '40px' }} />
      </div>

      <div className="nav-items">
        {items.map((item) => (
          <a href={item.url} key={item.url} className="nav-item">
            {item.label}
          </a>
        ))}
      </div>

      <div className="mobile-menu">
        {/* Mobile menu button */}
        <Button
          icon="pi pi-bars"
          style={{ fontSize: '2rem' }}
          onClick={toggleMobileMenu}
        />

        {/* Mobile menu dialog */}
        <Dialog
          visible={mobileMenuVisible}
          modal={true}
          style={{ width: '95vw' }}
          onHide={toggleMobileMenu}
          closable={true}
          draggable={false}
          resizable={false}
          blockScroll={true}
          dismissableMask={true}
        >
          {items.map((item) => (
            <a
              href={item.url}
              key={item.url}
              className="mobile-nav-item"
              onClick={toggleMobileMenu}
            >
              {item.label}
            </a>
          ))}
        </Dialog>
      </div>
    </div>
  );
};

export default Navbar;
