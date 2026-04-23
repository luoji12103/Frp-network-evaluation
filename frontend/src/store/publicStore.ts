import { create } from 'zustand';

interface PublicState {
  pageInfo: any;
  topologyId: string | null;
  summary: any;
  nodes: any;
  paths: any;
  alerts: any[];
  latestRuns: any[];
  history: any;
  // Specific payload for paths or roles
  path_id?: string;
  role?: string;
  metric_groups?: any;
}

const initialState = typeof window !== 'undefined' ? (window as any).__INITIAL_STATE__ || {} : {};
const pageInfo = typeof window !== 'undefined' ? (window as any).__PUBLIC_PAGE__ || { kind: 'overview' } : { kind: 'overview' };

export const usePublicStore = create<PublicState>(() => ({
  pageInfo,
  ...initialState
}));
