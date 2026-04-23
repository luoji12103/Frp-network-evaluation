import { create } from 'zustand';

interface AdminState {
  topologyId: string | null;
  settings: any;
  schedules: any[];
  nodes: any;
  latestRuns: any[];
  alerts: any[];
  history: any;
  setTopology: (id: string) => void;
}

// Injected by Jinja
const initialState = typeof window !== 'undefined' ? (window as any).__INITIAL_STATE__ || {} : {};

export const useAdminStore = create<AdminState>((set) => ({
  topologyId: initialState.topology_id || null,
  settings: initialState.settings || {},
  schedules: initialState.schedules || [],
  nodes: initialState.nodes || {},
  latestRuns: initialState.latest_runs || [],
  alerts: initialState.alerts || [],
  history: initialState.history || {},
  setTopology: (id) => set({ topologyId: id }),
}));
