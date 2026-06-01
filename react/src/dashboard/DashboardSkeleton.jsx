// SVG silhouettes ---------------------------------------------------------

function TimelineSvg() {
  return (
    <svg viewBox="0 0 400 130" preserveAspectRatio="none" className="sk-svg">
      <path
        d="M0,100 C60,88 120,65 165,50 C210,35 250,42 290,28 C325,16 360,26 400,18 L400,130 L0,130Z"
        className="sk-area"
      />
      <path
        d="M0,100 C60,88 120,65 165,50 C210,35 250,42 290,28 C325,16 360,26 400,18"
        fill="none" strokeWidth="2" className="sk-line"
      />
      <line x1="0" y1="126" x2="400" y2="126" strokeWidth="1" className="sk-axis" />
    </svg>
  );
}

function HBarSvg() {
  const bars = [[145, 8], [110, 30], [88, 52], [125, 74], [68, 96], [52, 118]];
  return (
    <svg viewBox="0 0 180 145" className="sk-svg">
      {bars.map(([w, y]) => (
        <rect key={y} x="6" y={y} width={w} height="14" rx="3" className="sk-bar" />
      ))}
      <line x1="6" y1="4" x2="6" y2="140" strokeWidth="1" className="sk-axis" />
    </svg>
  );
}

function VBarSvg() {
  const bars = [[12, 62, 24], [44, 36, 24], [76, 78, 24], [108, 48, 24], [140, 22, 24], [172, 58, 24]];
  return (
    <svg viewBox="0 0 220 115" preserveAspectRatio="none" className="sk-svg">
      {bars.map(([x, y, w]) => (
        <rect key={x} x={x} y={y} width={w} height={110 - y} rx="3" className="sk-bar" />
      ))}
      <line x1="5" y1="110" x2="215" y2="110" strokeWidth="1" className="sk-axis" />
    </svg>
  );
}

function StackedBarSvg() {
  const bars = [
    [58, 28, 14], [50, 33, 17], [62, 24, 14], [45, 38, 17],
    [70, 18, 12], [54, 30, 16], [60, 26, 14],
  ];
  return (
    <svg viewBox="0 0 220 115" preserveAspectRatio="none" className="sk-svg">
      {bars.flatMap((segs, i) => {
        const x = 10 + i * 28;
        let y = 106;
        return segs.map((h, j) => {
          y -= h;
          return (
            <rect
              key={`${i}-${j}`} x={x} y={y} width="22" height={h}
              rx={j === segs.length - 1 ? 3 : 0}
              className={`sk-bar sk-bar--${j}`}
            />
          );
        });
      })}
      <line x1="5" y1="107" x2="215" y2="107" strokeWidth="1" className="sk-axis" />
    </svg>
  );
}

function NetworkSvg() {
  const nodes = [
    [100, 55], [195, 28], [280, 75], [175, 108], [300, 138],
    [58, 108], [240, 155], [140, 38], [340, 58], [76, 38],
  ];
  const radii = [12, 9, 8, 7, 6, 7, 5, 10, 5, 6];
  const edges = [
    [0, 1], [1, 2], [0, 3], [3, 4], [1, 7], [7, 0],
    [2, 8], [3, 5], [4, 6], [0, 9], [9, 5], [7, 3],
  ];
  return (
    <svg viewBox="0 0 400 190" className="sk-svg">
      {edges.map(([a, b], i) => (
        <line
          key={i}
          x1={nodes[a][0]} y1={nodes[a][1]}
          x2={nodes[b][0]} y2={nodes[b][1]}
          strokeWidth="1.5" className="sk-edge"
        />
      ))}
      {nodes.map(([x, y], i) => (
        <circle key={i} cx={x} cy={y} r={radii[i]} className="sk-node" />
      ))}
    </svg>
  );
}

function ChordSvg() {
  return (
    <svg viewBox="0 0 180 180" className="sk-svg">
      <path d="M90,10 A80,80 0 0,1 160,50"  fill="none" strokeWidth="14" strokeLinecap="butt" className="sk-arc" />
      <path d="M160,52 A80,80 0 0,1 160,128" fill="none" strokeWidth="14" strokeLinecap="butt" className="sk-arc" style={{ opacity: 0.7 }} />
      <path d="M160,130 A80,80 0 0,1 90,170"  fill="none" strokeWidth="14" strokeLinecap="butt" className="sk-arc" style={{ opacity: 0.5 }} />
      <path d="M90,170 A80,80 0 0,1 20,128"  fill="none" strokeWidth="14" strokeLinecap="butt" className="sk-arc" style={{ opacity: 0.4 }} />
      <path d="M20,128 A80,80 0 0,1 20,52"   fill="none" strokeWidth="14" strokeLinecap="butt" className="sk-arc" style={{ opacity: 0.6 }} />
      <path d="M20,50 A80,80 0 0,1 90,10"    fill="none" strokeWidth="14" strokeLinecap="butt" className="sk-arc" style={{ opacity: 0.35 }} />
      <path d="M90,18 Q90,90 152,56"  fill="none" strokeWidth="10" className="sk-chord" />
      <path d="M153,57 Q90,90 90,162" fill="none" strokeWidth="7"  className="sk-chord" style={{ opacity: 0.65 }} />
      <path d="M26,125 Q90,90 153,125" fill="none" strokeWidth="5" className="sk-chord" style={{ opacity: 0.4 }} />
    </svg>
  );
}

function TableRowsSvg() {
  return (
    <div className="sk-table-rows">
      {TABLE_ROW_KEYS.map((i) => (
        <div key={i} className="sk-table-row">
          <div className="sk-block" style={{ width: 38, flexShrink: 0 }} />
          <div className="sk-block" style={{ flex: 1 }} />
          <div className="sk-block" style={{ width: 72, flexShrink: 0 }} />
          <div className="sk-block" style={{ width: 52, flexShrink: 0 }} />
        </div>
      ))}
    </div>
  );
}

const TABLE_ROW_KEYS = [0, 1, 2, 3, 4, 5, 6];

// Card + section wrappers -------------------------------------------------

function SkCard({ children, minHeight }) {
  return (
    <div className="sk-card" style={minHeight ? { minHeight } : undefined}>
      <div className="sk-card__header">
        <div className="sk-block sk-block--h3" />
        <div className="sk-block sk-block--p" />
      </div>
      <div className="sk-card__body">
        {children}
      </div>
    </div>
  );
}

function SkSection({ children }) {
  return (
    <div className="dashboard-section">
      <div className="dashboard-section__header">
        <div className="sk-block sk-block--section-title" />
      </div>
      {children}
    </div>
  );
}

// Full skeleton -----------------------------------------------------------

export function DashboardSkeleton() {
  return (
    <div className="dashboard-skeleton">
      {/* Authorship */}
      <SkSection>
        <div className="dashboard-grid dashboard-grid--wide-left mb-4">
          <SkCard><TimelineSvg /></SkCard>
          <SkCard><HBarSvg /></SkCard>
        </div>
        <div className="dashboard-grid dashboard-grid--two-up mb-4">
          <SkCard><VBarSvg /></SkCard>
          <SkCard><VBarSvg /></SkCard>
        </div>
        <SkCard minHeight={320}><NetworkSvg /></SkCard>
      </SkSection>

      {/* Classification */}
      <SkSection>
        <div className="dashboard-grid dashboard-grid--classification mb-4">
          <SkCard><ChordSvg /></SkCard>
          <SkCard><StackedBarSvg /></SkCard>
        </div>
      </SkSection>

      {/* Evolution */}
      <SkSection>
        <SkCard><StackedBarSvg /></SkCard>
      </SkSection>

      {/* Dependencies */}
      <SkSection>
        <SkCard minHeight={380}><NetworkSvg /></SkCard>
      </SkSection>

      {/* Conformity */}
      <SkSection>
        <SkCard><TableRowsSvg /></SkCard>
      </SkSection>
    </div>
  );
}
