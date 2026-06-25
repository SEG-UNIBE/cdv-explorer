import { useEffect, useState } from 'react';
import { fetchDatasetForSelection, isDatasetCached } from '../data';

export function useDashboardDatasetLoader({
  ecosystem,
  ecosystemId,
  selectedSnapshot,
  orderedSelectedSourceIds,
  emptyDataset,
}) {
  const [selectedDataset, setSelectedDataset] = useState(emptyDataset);
  const [dataLoading, setDataLoading] = useState(true);
  const [dataReady, setDataReady] = useState(false);
  const [skeletonActive, setSkeletonActive] = useState(true);
  const [contentEntered, setContentEntered] = useState(false);
  const [fetchError, setFetchError] = useState(null);
  const [retryCounter, setRetryCounter] = useState(0);

  useEffect(() => {
    if (!ecosystem || ecosystem.status !== 'available' || !selectedSnapshot || orderedSelectedSourceIds.length === 0) {
      setSelectedDataset(emptyDataset);
      setDataLoading(false);
      setFetchError(null);
      return undefined;
    }
    if (!isDatasetCached(ecosystemId, selectedSnapshot, orderedSelectedSourceIds)) {
      setDataReady(false);
      setSkeletonActive(true);
      setContentEntered(false);
    }
    let cancelled = false;
    setDataLoading(true);
    setFetchError(null);
    fetchDatasetForSelection(ecosystemId, selectedSnapshot, orderedSelectedSourceIds)
      .then((dataset) => {
        if (!cancelled) {
          setSelectedDataset(dataset);
          setDataLoading(false);
          setDataReady(true);
        }
      })
      .catch((error) => {
        if (!cancelled) {
          setDataLoading(false);
          setSkeletonActive(false);
          setFetchError({
            snapshot: selectedSnapshot,
            sourceIds: orderedSelectedSourceIds,
            message: error instanceof Error ? error.message : String(error),
          });
        }
      });
    return () => { cancelled = true; };
  }, [ecosystem, ecosystemId, selectedSnapshot, orderedSelectedSourceIds, emptyDataset, retryCounter]);

  return {
    selectedDataset,
    dataLoading,
    dataReady,
    skeletonActive,
    setSkeletonActive,
    contentEntered,
    setContentEntered,
    fetchError,
    retryLoad: () => {
      setSkeletonActive(true);
      setRetryCounter((current) => current + 1);
    },
  };
}
