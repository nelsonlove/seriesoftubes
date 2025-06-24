import { create } from 'zustand';
import type { ExecutionDetail, ExecutionProgress } from '../types/workflow';

interface ExecutionStore {
  executions: Record<string, ExecutionDetail>;
  activeExecution: string | null;

  // Actions
  setExecution: (execution: ExecutionDetail) => void;
  updateProgress: (executionId: string, nodeId: string, progress: ExecutionProgress) => void;
  setActiveExecution: (id: string | null) => void;
  clearExecution: (id: string) => void;
}

export const useExecutionStore = create<ExecutionStore>((set) => ({
  executions: {},
  activeExecution: null,

  setExecution: (execution) =>
    set((state) => {
      const id = execution.id || execution.execution_id || '';
      return {
        executions: {
          ...state.executions,
          [id]: { ...execution, id },
        },
      };
    }),

  updateProgress: (executionId, nodeId, progress) =>
    set((state) => {
      const execution = state.executions[executionId];
      if (!execution) return state;

      // Determine if we should update the overall execution status
      const progressStatus = typeof progress === 'string' ? progress : progress.status;
      const shouldUpdateStatus = progressStatus === 'failed';

      return {
        executions: {
          ...state.executions,
          [executionId]: {
            ...execution,
            progress: {
              ...execution.progress,
              [nodeId]: progress,
            },
            status: shouldUpdateStatus ? 'failed' : execution.status,
          },
        },
      };
    }),

  setActiveExecution: (id) =>
    set(() => ({
      activeExecution: id,
    })),

  clearExecution: (id) =>
    set((state) => {
      const { [id]: removed, ...rest } = state.executions;
      void removed; // Satisfy linter
      return {
        executions: rest,
        activeExecution: state.activeExecution === id ? null : state.activeExecution,
      };
    }),
}));
