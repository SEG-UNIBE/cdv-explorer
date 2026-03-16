import React, { useState } from 'react';
import { Dialog } from 'primereact/dialog';
import { Button } from 'primereact/button';
import { Link } from 'react-router-dom'; // ✅ Import Link
import './Navbar.scss';

const Navbar = () => {
  const [mobileMenuVisible, setMobileMenuVisible] = useState(false);

  const items = [
    { label: 'Home', url: '/' },
    { label: 'About', url: '/about' }
  ];

  const toggleMobileMenu = () => {
    setMobileMenuVisible(!mobileMenuVisible);
  };

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

      <div className="mobile-menu">
        <Button
          icon="pi pi-bars"
          style={{ fontSize: '2rem' }}
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
        </Dialog>
      </div>
    </div>
  );
};

export default Navbar;
