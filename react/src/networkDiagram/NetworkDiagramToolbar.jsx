import { Dropdown } from 'primereact/dropdown';
import { InputSwitch } from 'primereact/inputswitch';
import { InputText } from 'primereact/inputtext';
import { MultiSelect } from 'primereact/multiselect';
import {
  ATTRIBUTE_FILTER_DIMENSION_OPTIONS,
  BASELINE_OPTIONS,
  COLOR_BY_OPTIONS,
  DIFFERENTIAL_EDGE_COLORS,
  DEFAULT_EDGE_COLORS,
  LAYOUT_OPTIONS,
  LINK_TYPE_OPTIONS,
  PREAMBLE_EXTRACTED,
  formatRelationTypeLabel,
  getLinkTypeLabel,
  getPreambleRelationDasharray,
  getPreambleRelationStroke,
  getPreambleRelationTypes,
} from './networkDiagramUtils';

function EdgeLegendLine({ stroke, dasharray }) {
  return (
    <svg className="dependency-edge-legend__line" viewBox="0 0 36 12" aria-hidden="true">
      <line
        x1="2"
        y1="6"
        x2="34"
        y2="6"
        stroke={stroke}
        strokeWidth="2.5"
        strokeDasharray={dasharray || undefined}
        strokeLinecap="round"
      />
    </svg>
  );
}

export function NetworkDiagramToolbar({
  colorBy,
  setColorBy,
  linkType,
  setLinkType,
  baselineType,
  setBaselineType,
  layoutMode,
  setLayoutMode,
  physicsEnabled,
  handlePhysicsToggle,
  importedLayout,
  handleLayoutImportClick,
  handleLayoutImport,
  handleLayoutExport,
  importInputRef,
  legendRef,
  isDifferentialMode,
  nodes,
  minRelations,
  setMinRelations,
  proposalShortPlural,
  includeThresholdConnections,
  setIncludeThresholdConnections,
  onlyCrossSource,
  setOnlyCrossSource,
  canFilterCrossSource,
  linksByType,
  attributeFilterDimension,
  setAttributeFilterDimension,
  attributeFilterValues,
  setAttributeFilterValues,
  attributeFilterOptions,
}) {
  const preambleRelationTypes = getPreambleRelationTypes(linksByType);
  const edgeLegendItems = isDifferentialMode
    ? [
      { label: getLinkTypeLabel(linkType), dasharray: null, stroke: DIFFERENTIAL_EDGE_COLORS.approach_only },
      { label: `Also in ${getLinkTypeLabel(baselineType)}`, dasharray: null, stroke: DIFFERENTIAL_EDGE_COLORS.overlap },
      { label: `Missing from ${getLinkTypeLabel(linkType)}`, dasharray: '7 5', stroke: DIFFERENTIAL_EDGE_COLORS.baseline_only },
    ]
    : linkType === PREAMBLE_EXTRACTED
      ? preambleRelationTypes.map((relationType) => ({
        label: formatRelationTypeLabel(relationType),
        dasharray: getPreambleRelationDasharray(relationType, preambleRelationTypes),
        stroke: getPreambleRelationStroke(),
      }))
      : [{ label: getLinkTypeLabel(linkType), dasharray: null, stroke: DEFAULT_EDGE_COLORS[linkType] || '#667085' }];

  const approachLegendItems = isDifferentialMode
    ? [{ label: getLinkTypeLabel(linkType), dasharray: null, stroke: DIFFERENTIAL_EDGE_COLORS.approach_only }]
    : edgeLegendItems;

  const baselineLegendItems = isDifferentialMode
    ? [
      { label: `Also in ${getLinkTypeLabel(baselineType)}`, dasharray: null, stroke: DIFFERENTIAL_EDGE_COLORS.overlap },
      { label: `Missing from ${getLinkTypeLabel(linkType)}`, dasharray: '7 5', stroke: DIFFERENTIAL_EDGE_COLORS.baseline_only },
    ]
    : [];

  return (
    <>
      <div className="dependency-graph-toolbar">
        <div className="dependency-graph-field dependency-graph-field--layout">
          <div className="network-layout-picker__label">Layout</div>
          <div className="dependency-graph-field__body">
            <input
              ref={importInputRef}
              type="file"
              accept="application/json,.json"
              onChange={handleLayoutImport}
              hidden
            />
            <div className="network-layout-picker__options network-layout-picker__options--with-actions dependency-graph-layout-options">
              {LAYOUT_OPTIONS.map((option) => (
                <label key={option.value} className="network-layout-picker__option">
                  <input
                    type="radio"
                    name="dependency-layout"
                    value={option.value}
                    checked={layoutMode === option.value}
                    onChange={() => setLayoutMode(option.value)}
                  />
                  <span>{option.label}</span>
                </label>
              ))}
            </div>
            <div className="dependency-graph-actions">
              <button
                type="button"
                className={`network-layout-action-button ${physicsEnabled ? '' : 'network-layout-action-button--active'}`.trim()}
                onClick={handlePhysicsToggle}
                title={physicsEnabled
                  ? 'Pause the force simulation so you can manually adjust node positions before exporting the layout.'
                  : 'Resume the force simulation for the relationship graph.'}
                aria-label={physicsEnabled
                  ? 'Pause network physics for manual layout adjustments'
                  : 'Resume network physics'}
                aria-pressed={!physicsEnabled}
                disabled={nodes.length === 0}
              >
                {physicsEnabled ? 'freeze physics' : 'resume physics'}
              </button>
              <button
                type="button"
                className={`network-layout-action-button ${importedLayout ? 'network-layout-action-button--active' : ''}`.trim()}
                onClick={handleLayoutImportClick}
                title={importedLayout
                  ? `Upload a layout JSON to replace the active imported layout. Current import: ${importedLayout.fileName}.`
                  : 'Upload a layout JSON export and apply its graph construction to the current card.'}
                aria-label="Upload network layout JSON"
                disabled={nodes.length === 0}
              >
                import layout
              </button>
              <button
                type="button"
                className="network-layout-action-button"
                onClick={handleLayoutExport}
                title="Download the current visible network layout as JSON."
                aria-label="Download current network layout as JSON"
                disabled={nodes.length === 0}
              >
                export layout
              </button>
            </div>
          </div>
        </div>
        <div className="dependency-graph-field dependency-graph-field--filter">
          <div className="network-layout-picker__label">Filter</div>
          <div className="dependency-graph-field__body">
            <div className="network-layout-threshold dependency-graph-threshold dependency-graph-threshold--attribute">
              <Dropdown
                value={attributeFilterDimension}
                options={ATTRIBUTE_FILTER_DIMENSION_OPTIONS}
                onChange={(event) => {
                  setAttributeFilterDimension?.(event.value || '');
                  setAttributeFilterValues?.([]);
                }}
                placeholder="Filter dimension"
                aria-label="Dependency graph filter dimension"
                className="dependency-graph-attribute-filter__dimension"
                showClear={Boolean(attributeFilterDimension)}
              />
              <MultiSelect
                value={attributeFilterValues}
                options={attributeFilterOptions}
                onChange={(event) => setAttributeFilterValues?.(event.value || [])}
                placeholder="Select values"
                aria-label="Dependency graph filter values"
                className="dependency-graph-attribute-filter__values"
                disabled={!attributeFilterDimension}
                display="chip"
                maxSelectedLabels={2}
              />
            </div>
            <div className="network-layout-threshold dependency-graph-threshold">
              <span className="network-layout-threshold__copy">Only show {proposalShortPlural} with</span>
              <InputText
                value={minRelations}
                onChange={(event) => setMinRelations?.(event.target.value.replace(/[^\d]/g, ''))}
                placeholder="0"
                inputMode="numeric"
                aria-label={`Minimum relations threshold for ${proposalShortPlural}`}
                className="network-layout-threshold__input"
              />
              <span className="network-layout-threshold__suffix">or more relations.</span>
            </div>
            <div className="dependency-graph-switch-row">
              <label htmlFor="dependency-cross-source-switch">Only show cross-source IPs</label>
              <InputSwitch
                inputId="dependency-cross-source-switch"
                checked={Boolean(onlyCrossSource)}
                onChange={(event) => setOnlyCrossSource?.(event.value)}
                aria-label="Show only cross-source IPs"
                disabled={!canFilterCrossSource}
                className="dependency-graph-switch"
              />
              <label className="dependency-filter-checkbox">
                <input
                  type="checkbox"
                  checked={includeThresholdConnections}
                  onChange={(event) => setIncludeThresholdConnections?.(event.target.checked)}
                />
                <span>transient</span>
              </label>
            </div>
          </div>
        </div>
      </div>
      <div className="network-control-grid dependency-graph-detail-grid">
        <div className="dependency-graph-detail-column dependency-graph-detail-column--left">
          <div className="dependency-graph-detail-field">
            <div className="network-layout-picker">
              <label className="network-layout-picker__label" htmlFor="linkType">Approach</label>
              <Dropdown
                inputId="linkType"
                value={linkType}
                options={LINK_TYPE_OPTIONS}
                onChange={(event) => setLinkType(event.value)}
                placeholder="Approach"
                className="w-full md:w-18rem"
                style={{ minWidth: '260px' }}
              />
            </div>
            <div className="dependency-edge-legend">
              {approachLegendItems.map((item) => (
                <div key={item.label} className="dependency-edge-legend__item">
                  <EdgeLegendLine stroke={item.stroke} dasharray={item.dasharray} />
                  <span>{item.label}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="dependency-graph-detail-field">
            <div className="network-layout-picker">
              <label className="network-layout-picker__label" htmlFor="baselineType">Baseline</label>
              <Dropdown
                inputId="baselineType"
                value={baselineType}
                options={BASELINE_OPTIONS}
                onChange={(event) => setBaselineType(event.value)}
                placeholder="Baseline"
                className="w-full md:w-18rem"
                style={{ minWidth: '260px' }}
              />
            </div>
            {baselineLegendItems.length > 0 ? (
              <div className="dependency-edge-legend">
                {baselineLegendItems.map((item) => (
                  <div key={item.label} className="dependency-edge-legend__item">
                    <EdgeLegendLine stroke={item.stroke} dasharray={item.dasharray} />
                    <span>{item.label}</span>
                  </div>
                ))}
              </div>
            ) : null}
          </div>
        </div>

        <div className="dependency-graph-detail-column dependency-graph-detail-column--right">
          <div className="dependency-graph-detail-field">
            <div className="network-layout-picker">
              <label className="network-layout-picker__label" htmlFor="dependency-colorBy">Coloring</label>
              <Dropdown
                inputId="dependency-colorBy"
                value={colorBy}
                options={COLOR_BY_OPTIONS}
                onChange={(event) => setColorBy(event.value)}
                placeholder="Coloring"
                className="w-full md:w-14rem"
                style={{ minWidth: '180px' }}
              />
            </div>
            <div ref={legendRef} className="network-control-grid__legend dependency-graph-color-legend" />
          </div>
        </div>
      </div>
    </>
  );
}
