import { useDashboardEcosystem, useDashboardLinkMode, useDashboardSnapshot } from './dashboard/DashboardSnapshotContext';
import { AuthorNetworkCanvas } from './authorNetwork/AuthorNetworkCanvas';
import { AuthorNetworkToolbar } from './authorNetwork/AuthorNetworkToolbar';
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

  const hasNodes = Array.isArray(data?.nodes) && data.nodes.length > 0;

  return (
    <div>
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
        hasNodes={hasNodes}
      />
      <AuthorNetworkCanvas
        data={data}
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
      />
    </div>
  );
};
