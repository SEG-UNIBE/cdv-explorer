import { InputSwitch } from 'primereact/inputswitch';
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
  minAuthoredIps,
  setMinAuthoredIps,
  hasNodes,
  onlyCrossSource,
  setOnlyCrossSource,
  canFilterCrossSource,
  showAllLabels,
  setShowAllLabels,
}) {
  return (
    <div className="author-collaboration-toolbar">
      <div className="author-collaboration-field author-collaboration-field--layout">
        <div className="network-layout-picker__label">Layout</div>
        <div className="author-collaboration-field__body">
          <input
            ref={importInputRef}
            type="file"
            accept="application/json,.json"
            onChange={handleLayoutImport}
            hidden
          />
          <div className="network-layout-picker__options network-layout-picker__options--with-actions author-collaboration-layout-options">
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
          </div>
          <div className="author-collaboration-actions">
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
      </div>
      <div className="author-collaboration-field author-collaboration-field--filter">
        <div className="network-layout-picker__label">Filter</div>
        <div className="author-collaboration-field__body">
          <div className="network-layout-threshold author-collaboration-threshold">
            <span className="network-layout-threshold__copy">Only show components with</span>
            <input
              value={minClusterCollaborations}
              onChange={(event) => setMinClusterCollaborations?.(event.target.value.replace(/[^\d]/g, ''))}
              placeholder="0"
              inputMode="numeric"
              className="p-inputtext p-component network-layout-threshold__input"
            />
            <span className="network-layout-threshold__suffix">or more collaborations.</span>
          </div>
          <div className="network-layout-threshold author-collaboration-threshold">
            <span className="network-layout-threshold__copy">Only show originators who authored</span>
            <input
              value={minAuthoredIps}
              onChange={(event) => setMinAuthoredIps?.(event.target.value.replace(/[^\d]/g, ''))}
              placeholder="1"
              inputMode="numeric"
              className="p-inputtext p-component network-layout-threshold__input"
            />
            <span className="network-layout-threshold__suffix">or more IPs.</span>
          </div>
          <div className="author-collaboration-switch-row">
            <label htmlFor="author-cross-source-switch">Only show cross-source IPs</label>
            <InputSwitch
              inputId="author-cross-source-switch"
              checked={Boolean(onlyCrossSource)}
              onChange={(event) => setOnlyCrossSource?.(event.value)}
              aria-label="Show only cross-source IPs"
              disabled={!canFilterCrossSource}
              className="author-collaboration-switch"
            />
          </div>
          <div className="author-collaboration-switch-row">
            <label htmlFor="author-show-all-labels-switch">Show all labels</label>
            <InputSwitch
              inputId="author-show-all-labels-switch"
              checked={Boolean(showAllLabels)}
              onChange={(event) => setShowAllLabels?.(event.value)}
              aria-label="Show labels for all originators"
              className="author-collaboration-switch"
            />
          </div>
        </div>
      </div>
    </div>
  );
}
