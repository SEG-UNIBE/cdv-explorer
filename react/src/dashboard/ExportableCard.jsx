import { Card } from 'primereact/card';

export function ExportableCard({
  children,
  className = '',
  style,
}) {
  return (
    <div className={className} style={style}>
      <Card className="exportable-card">
        {children}
      </Card>
    </div>
  );
}
