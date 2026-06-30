import { useRef } from 'react';
import { useDashboardEcosystem, useDashboardLinkMode, useDashboardSnapshot } from './dashboard/DashboardSnapshotContext';
import { CollapsibleControls } from './dashboard/CollapsibleControls';
import { NetworkDiagramCanvas } from './networkDiagram/NetworkDiagramCanvas';
import { NetworkDiagramToolbar } from './networkDiagram/NetworkDiagramToolbar';
import { useNetworkDiagramState } from './networkDiagram/useNetworkDiagramState';

export { LINK_TYPE_OPTIONS } from './networkDiagram/networkDiagramUtils';

export const NetworkDiagram = ({
  width = 1200,
  height = 800,
  data,
  activeLlmModel = '',
  highlightProposal = '',
  proposalShortPlural = 'IPs',
  minRelations = '0',
  setMinRelations,
  proposalFilterIds = [],
  setProposalFilterText,
  includeConnections = true,
  setIncludeConnections,
  includeThresholdConnections = false,
  setIncludeThresholdConnections,
  extraControls = null,
  controlsClassName = '',
}) => {
  const legendRef = useRef();
  const snapshotLabel = useDashboardSnapshot();
  const linkMode = useDashboardLinkMode();
  const ecosystem = useDashboardEcosystem();

  const state = useNetworkDiagramState({
    data,
    proposalFilterIds,
    snapshotLabel,
    ecosystem,
    setMinRelations,
    setIncludeConnections,
    setIncludeThresholdConnections,
    setProposalFilterText,
  });

  return (
    <div>
      <CollapsibleControls className={controlsClassName}>
        {extraControls}
        <NetworkDiagramToolbar
          colorBy={state.colorBy}
          setColorBy={state.setColorBy}
          linkType={state.linkType}
          setLinkType={state.setLinkType}
          baselineType={state.baselineType}
          setBaselineType={state.setBaselineType}
          linkSubtype={state.linkSubtype}
          setLinkSubtype={state.setLinkSubtype}
          baselineSubtype={state.baselineSubtype}
          setBaselineSubtype={state.setBaselineSubtype}
          groundTruthRelationSubtypeOptions={state.groundTruthRelationSubtypeOptions}
          activeLlmModel={activeLlmModel}
          layoutMode={state.layoutMode}
          setLayoutMode={state.setLayoutMode}
          physicsEnabled={state.physicsEnabled}
          handlePhysicsToggle={state.handlePhysicsToggle}
          importedLayout={state.importedLayout}
          handleLayoutImportClick={state.handleLayoutImportClick}
          handleLayoutImport={state.handleLayoutImport}
          handleLayoutExport={state.handleLayoutExport}
          importInputRef={state.importInputRef}
          legendRef={legendRef}
          isDifferentialMode={state.isDifferentialMode}
          nodes={state.nodes}
          minRelations={minRelations}
          setMinRelations={setMinRelations}
          proposalShortPlural={proposalShortPlural}
          includeThresholdConnections={includeThresholdConnections}
          setIncludeThresholdConnections={setIncludeThresholdConnections}
          onlyCrossSource={state.onlyCrossSource}
          setOnlyCrossSource={state.setOnlyCrossSource}
          canFilterCrossSource={state.canFilterCrossSource}
          linksByType={state.linksByType}
          attributeFilterDimension={state.attributeFilterDimension}
          setAttributeFilterDimension={state.setAttributeFilterDimension}
          attributeFilterValues={state.attributeFilterValues}
          setAttributeFilterValues={state.setAttributeFilterValues}
          attributeFilterOptions={state.attributeFilterOptions}
        />
      </CollapsibleControls>
      <NetworkDiagramCanvas
        width={width}
        height={height}
        nodes={state.nodes}
        links={state.links}
        proposalFilterIds={proposalFilterIds}
        includeConnections={includeConnections}
        includeThresholdConnections={includeThresholdConnections}
        minRelations={minRelations}
        highlightProposal={highlightProposal}
        ecosystem={ecosystem}
        snapshotLabel={snapshotLabel}
        linkMode={linkMode}
        colorBy={state.colorBy}
        linkType={state.linkType}
        baselineType={state.baselineType}
        linkSubtype={state.linkSubtype}
        baselineSubtype={state.baselineSubtype}
        activeLlmModel={activeLlmModel}
        layoutMode={state.layoutMode}
        isDifferentialMode={state.isDifferentialMode}
        onlyCrossSource={state.onlyCrossSource}
        attributeFilterDimension={state.attributeFilterDimension}
        attributeFilterValues={state.attributeFilterValues}
        importedLayout={state.importedLayout}
        physicsEnabledRef={state.physicsEnabledRef}
        simulationRef={state.simulationRef}
        redrawGraphRef={state.redrawGraphRef}
        exportPayloadRef={state.exportPayloadRef}
        updateExportPayloadRef={state.updateExportPayloadRef}
        legendRef={legendRef}
      />
    </div>
  );
};
