import { useEffect, useRef, useState } from 'react';
import { COLLABORATION_LAYOUT_OPTIONS } from '../dashboard/constants';
import {
  formatSnapshotFilePart,
  normalizeImportedEdgeCurves,
  normalizeImportedPositions,
  sanitizeFilePart,
} from './authorNetworkUtils';

const COLLABORATION_LAYOUT_OPTION_VALUES = new Set(COLLABORATION_LAYOUT_OPTIONS.map((option) => option.value));

export function useAuthorNetworkState({ snapshotLabel, layoutMode, setMinClusterCollaborations, setLayoutMode }) {
  const importInputRef = useRef(null);
  const physicsEnabledRef = useRef(true);
  const simulationRef = useRef(null);
  const redrawGraphRef = useRef(() => {});
  const exportPayloadRef = useRef(null);
  const updateExportPayloadRef = useRef(() => {});

  const [physicsEnabled, setPhysicsEnabled] = useState(true);
  const [importedLayout, setImportedLayout] = useState(null);
  const [onlyCrossSource, setOnlyCrossSource] = useState(false);

  useEffect(() => {
    physicsEnabledRef.current = physicsEnabled;

    const simulation = simulationRef.current;
    if (!simulation) {
      return;
    }

    if (physicsEnabled) {
      simulation.alpha(0.35).alphaTarget(0).restart();
      return;
    }

    simulation.alphaTarget(0);
    simulation.stop();
    redrawGraphRef.current();
    updateExportPayloadRef.current();
  }, [physicsEnabled]);

  const handleLayoutExport = () => {
    if (!exportPayloadRef.current) {
      return;
    }

    const snapshotSlug = formatSnapshotFilePart(snapshotLabel);
    const fileName = `authorship_layout_${snapshotSlug}_${sanitizeFilePart(layoutMode, 'balanced')}.json`;
    const blob = new Blob([`${JSON.stringify(exportPayloadRef.current, null, 2)}\n`], { type: 'application/json' });
    const url = window.URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = fileName;
    document.body.appendChild(anchor);
    anchor.click();
    document.body.removeChild(anchor);
    window.URL.revokeObjectURL(url);
  };

  const handlePhysicsToggle = () => {
    setPhysicsEnabled((current) => !current);
  };

  const handleLayoutImportClick = () => {
    importInputRef.current?.click();
  };

  const handleLayoutImport = async (event) => {
    const file = event.target.files?.[0];
    event.target.value = '';

    if (!file) {
      return;
    }

    try {
      const payload = JSON.parse(await file.text());
      const importedPositions = normalizeImportedPositions(payload);
      const importedEdgeCurves = normalizeImportedEdgeCurves(payload);

      if (Object.keys(importedPositions).length === 0) {
        throw new Error('The selected file does not contain any layout positions.');
      }

      if (COLLABORATION_LAYOUT_OPTION_VALUES.has(payload?.layout_mode)) {
        setLayoutMode?.(payload.layout_mode);
      }

      const importedThreshold = payload?.filter?.min_cluster_collaborations;
      if (importedThreshold != null) {
        setMinClusterCollaborations?.(String(Math.max(0, Number(importedThreshold) || 0)));
      }

      if (typeof payload?.filter?.only_cross_source === 'boolean') {
        setOnlyCrossSource(payload.filter.only_cross_source);
      }

      setImportedLayout({
        fileName: file.name,
        positions: importedPositions,
        edgeCurves: importedEdgeCurves,
      });
      setPhysicsEnabled(false);
    } catch (error) {
      window.alert(
        error instanceof Error
          ? `Could not import layout JSON: ${error.message}`
          : 'Could not import layout JSON.'
      );
    }
  };

  return {
    importInputRef,
    physicsEnabledRef,
    simulationRef,
    redrawGraphRef,
    exportPayloadRef,
    updateExportPayloadRef,
    physicsEnabled,
    importedLayout,
    onlyCrossSource,
    setOnlyCrossSource,
    handleLayoutExport,
    handlePhysicsToggle,
    handleLayoutImportClick,
    handleLayoutImport,
  };
}
