import { Panel } from 'primereact/panel';

function ControlPanelHeader(options) {
  const handleHeaderClick = (event) => {
    const target = event.target;
    if (target instanceof Element && target.closest('.p-panel-toggler')) {
      return;
    }
    options.onTogglerClick(event);
  };

  const handleHeaderKeyDown = (event) => {
    if (event.key !== 'Enter' && event.key !== ' ') {
      return;
    }
    event.preventDefault();
    options.onTogglerClick(event);
  };

  return (
    <div
      className={`${options.className} collapsible-controls__header`.trim()}
      role="button"
      tabIndex={0}
      aria-expanded={!options.collapsed}
      onClick={handleHeaderClick}
      onKeyDown={handleHeaderKeyDown}
    >
      <span className="p-panel-title">
        <i className="pi pi-cog collapsible-controls__gear" aria-hidden="true" />
        <span>{options.props.header}</span>
      </span>
      {options.iconsElement}
    </div>
  );
}

export function CollapsibleControls({
  header = 'Controls',
  children,
  className = '',
  collapsed = true,
}) {
  return (
    <Panel
      header={header}
      headerTemplate={ControlPanelHeader}
      toggleable
      collapsed={collapsed}
      className={`collapsible-controls ${className}`.trim()}
    >
      {children}
    </Panel>
  );
}
