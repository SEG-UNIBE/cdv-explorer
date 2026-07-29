import { useEffect, useMemo } from 'react';
import { useDashboardEcosystem, useDashboardLinkMode, useDashboardSnapshot } from './dashboard/DashboardSnapshotContext';
import { CollapsibleControls } from './dashboard/CollapsibleControls';
import { AuthorNetworkCanvas } from './authorNetwork/AuthorNetworkCanvas';
import { AuthorNetworkToolbar } from './authorNetwork/AuthorNetworkToolbar';
import {
  authorNetworkHasCrossSourceRefs,
  filterAuthorNetworkByMinAuthoredIps,
  filterCrossSourceAuthorNetwork,
} from './authorNetwork/authorNetworkUtils';
import { useAuthorNetworkState } from './authorNetwork/useAuthorNetworkState';

export const AuthorCollaborationNetwork = ({
  data,
  width = 1200,
  height = 700,
  highlightAuthor = '',
  layoutMode = 'balanced',
  setLayoutMode,
  minClusterCollaborations = '0',
  setMinClusterCollaborations,
  minAuthoredIps = '1',
  setMinAuthoredIps,
  extraControls = null,
}) => {
  const snapshotLabel = useDashboardSnapshot();
  const linkMode = useDashboardLinkMode();
  const ecosystem = useDashboardEcosystem();

  const state = useAuthorNetworkState({
    snapshotLabel,
    layoutMode,
    setMinClusterCollaborations,
    setLayoutMode,
  });
  const { onlyCrossSource, setOnlyCrossSource, showAllLabels, setShowAllLabels } = state;

  const canFilterCrossSource = useMemo(
    () => authorNetworkHasCrossSourceRefs(data),
    [data]
  );
  useEffect(() => {
    if (!canFilterCrossSource && onlyCrossSource) {
      setOnlyCrossSource(false);
    }
  }, [canFilterCrossSource, onlyCrossSource, setOnlyCrossSource]);

  const graphData = useMemo(() => {
    const crossSourceFiltered = onlyCrossSource && canFilterCrossSource
      ? filterCrossSourceAuthorNetwork(data)
      : data;
    return filterAuthorNetworkByMinAuthoredIps(crossSourceFiltered, minAuthoredIps);
  }, [canFilterCrossSource, data, minAuthoredIps, onlyCrossSource]);

  const hasNodes = Array.isArray(graphData?.nodes) && graphData.nodes.length > 0;

  return (
    <div>
      <CollapsibleControls className="author-collaboration-controls">
        {extraControls}
        <AuthorNetworkToolbar
          layoutMode={layoutMode}
          setLayoutMode={setLayoutMode}
          physicsEnabled={state.physicsEnabled}
          handlePhysicsToggle={state.handlePhysicsToggle}
          importedLayout={state.importedLayout}
          handleLayoutImportClick={state.handleLayoutImportClick}
          handleLayoutImport={state.handleLayoutImport}
          handleLayoutExport={state.handleLayoutExport}
          importInputRef={state.importInputRef}
          minClusterCollaborations={minClusterCollaborations}
          setMinClusterCollaborations={setMinClusterCollaborations}
          minAuthoredIps={minAuthoredIps}
          setMinAuthoredIps={setMinAuthoredIps}
          hasNodes={hasNodes}
          onlyCrossSource={onlyCrossSource}
          setOnlyCrossSource={setOnlyCrossSource}
          canFilterCrossSource={canFilterCrossSource}
          showAllLabels={showAllLabels}
          setShowAllLabels={setShowAllLabels}
        />
      </CollapsibleControls>
      <AuthorNetworkCanvas
        data={graphData}
        width={width}
        height={height}
        highlightAuthor={highlightAuthor}
        layoutMode={layoutMode}
        minClusterCollaborations={minClusterCollaborations}
        ecosystem={ecosystem}
        snapshotLabel={snapshotLabel}
        linkMode={linkMode}
        importedLayout={state.importedLayout}
        physicsEnabledRef={state.physicsEnabledRef}
        simulationRef={state.simulationRef}
        redrawGraphRef={state.redrawGraphRef}
        exportPayloadRef={state.exportPayloadRef}
        updateExportPayloadRef={state.updateExportPayloadRef}
        onlyCrossSource={onlyCrossSource}
        showAllLabels={showAllLabels}
      />
    </div>
  );
};
