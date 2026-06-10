import { COLLABORATION_LAYOUT_OPTIONS } from '../dashboard/constants';

export function AuthorNetworkToolbar({
  layoutMode,
  setLayoutMode,
  physicsEnabled,
  handlePhysicsToggle,
  importedLayout,
  handleLayoutImportClick,
  handleLayoutImport,
  handleLayoutExport,
  importInputRef,
  minClusterCollaborations,
  setMinClusterCollaborations,
  hasNodes,
  onlyCrossSource,
  setOnlyCrossSource,
  canFilterCrossSource,
}) {
  return (
    <div className="network-layout-controls">
      <div className="network-layout-picker">
        <div className="network-layout-picker__label">Layout</div>
        <div className="network-layout-picker__options network-layout-picker__options--with-actions">
          <input
            ref={importInputRef}
            type="file"
            accept="application/json,.json"
            onChange={handleLayoutImport}
            hidden
          />
          {COLLABORATION_LAYOUT_OPTIONS.map((option) => (
            <label key={option.value} className="network-layout-picker__option">
              <input
                type="radio"
                name="collaboration-layout"
                value={option.value}
                checked={layoutMode === option.value}
                onChange={() => setLayoutMode?.(option.value)}
              />
              <span>{option.label}</span>
            </label>
          ))}
          <button
            type="button"
            className={`network-layout-action-button ${physicsEnabled ? '' : 'network-layout-action-button--active'}`.trim()}
            onClick={handlePhysicsToggle}
            title={physicsEnabled
              ? 'Pause the force simulation so you can manually adjust author positions before exporting the layout.'
              : 'Resume the force simulation for the collaboration graph.'}
            aria-label={physicsEnabled
              ? 'Pause network physics for manual layout adjustments'
              : 'Resume network physics'}
            aria-pressed={!physicsEnabled}
            disabled={!hasNodes}
          >
            {physicsEnabled ? 'freeze physics' : 'resume physics'}
          </button>
          <button
            type="button"
            className={`network-layout-action-button ${importedLayout ? 'network-layout-action-button--active' : ''}`.trim()}
            onClick={handleLayoutImportClick}
            title={importedLayout
              ? `Upload a layout JSON to replace the active imported layout. Current import: ${importedLayout.fileName}.`
              : 'Upload a layout JSON export and apply it to the collaboration graph.'}
            aria-label="Upload authorship network layout JSON"
            disabled={!hasNodes}
          >
            import layout
          </button>
          <button
            type="button"
            className="network-layout-action-button"
            onClick={handleLayoutExport}
            title="Download the current visible collaboration layout as JSON."
            aria-label="Download current authorship network layout as JSON"
            disabled={!hasNodes}
          >
            export layout
          </button>
        </div>
      </div>
      <div className="network-layout-picker network-layout-picker--filter">
        <div className="network-layout-picker__label">Filter</div>
        <div className="network-layout-threshold">
          <span className="network-layout-threshold__copy">Only show components with</span>
          <input
            value={minClusterCollaborations}
            onChange={(event) => setMinClusterCollaborations?.(event.target.value.replace(/[^\d]/g, ''))}
            placeholder="0"
            inputMode="numeric"
            className="p-inputtext p-component network-layout-threshold__input"
          />
          <span className="network-layout-threshold__suffix">or more collaborations.</span>
          <button
            type="button"
            className={`network-layout-action-button network-filter-action-button ${onlyCrossSource ? 'network-layout-action-button--active' : ''}`.trim()}
            onClick={() => setOnlyCrossSource?.(!onlyCrossSource)}
            title="Show only authors and collaborations tied to proposal refs from multiple sources."
            aria-label="Show only cross-source IPs"
            aria-pressed={Boolean(onlyCrossSource)}
            disabled={!canFilterCrossSource}
          >
            only cross-source IPs
          </button>
        </div>
      </div>
    </div>
  );
}
