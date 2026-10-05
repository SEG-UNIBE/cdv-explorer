import { Card } from 'primereact/card';

export function ExportableCard({
  children,
  className = '',
  style,
}) {
  return (
    <div className={`exportable-card-shell${className ? ` ${className}` : ''}`} style={style}>
      <Card className="exportable-card">
        {children}
      </Card>
    </div>
  );
}
