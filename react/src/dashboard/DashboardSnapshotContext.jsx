import { createContext, useContext } from 'react';

const DashboardSnapshotContext = createContext({
  snapshot: null,
  linkMode: 'history',
  ecosystem: null,
});

export function DashboardSnapshotProvider({ snapshot, linkMode = 'history', ecosystem = null, children }) {
  return (
    <DashboardSnapshotContext.Provider value={{
      snapshot: snapshot || null,
      linkMode,
      ecosystem,
    }}
    >
      {children}
    </DashboardSnapshotContext.Provider>
  );
}

export function useDashboardSnapshot() {
  return useContext(DashboardSnapshotContext).snapshot;
}

export function useDashboardLinkMode() {
  return useContext(DashboardSnapshotContext).linkMode;
}

export function useDashboardEcosystem() {
  return useContext(DashboardSnapshotContext).ecosystem;
}
