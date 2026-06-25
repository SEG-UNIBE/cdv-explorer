import { getClassificationColorMap } from './classificationColors';

export const ClassificationLegend = ({ dimension, colorDomain, data, maxRows = 12 }) => {
  if (!Array.isArray(data) || data.length === 0) return null;
  const chartData = data.filter((entry) => Number(entry.value || 0) > 0);
  if (chartData.length === 0) return null;

  const total = chartData.reduce((sum, entry) => sum + Number(entry.value || 0), 0);
  const colorMap = getClassificationColorMap(
    dimension,
    Array.isArray(colorDomain) && colorDomain.length
      ? colorDomain
      : chartData.map((entry) => entry.id),
  );

  return (
    <ul className="classification-legend" aria-label="Classification legend">
      {chartData.slice(0, maxRows).map((entry) => {
        const pct = total > 0 ? Math.round((entry.value / total) * 100) : 0;
        return (
          <li key={entry.id} className="classification-legend__row">
            <span
              className="classification-legend__swatch"
              style={{ background: colorMap[entry.id] || '#888' }}
              aria-hidden="true"
            />
            <span className="classification-legend__label" title={entry.id}>{entry.id}</span>
            <span className="classification-legend__count">{entry.value} ({pct}%)</span>
          </li>
        );
      })}
    </ul>
  );
};
