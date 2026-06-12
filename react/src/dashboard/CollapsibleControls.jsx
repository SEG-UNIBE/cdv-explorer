import { Panel } from 'primereact/panel';

export function CollapsibleControls({
  header = 'Controls',
  children,
  className = '',
  collapsed = true,
}) {
  return (
    <Panel
      header={header}
      toggleable
      collapsed={collapsed}
      className={`collapsible-controls ${className}`.trim()}
    >
      {children}
    </Panel>
  );
}
