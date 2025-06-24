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
    set((state) => ({
      executions: {
        ...state.executions,
        [execution.id]: execution,
      },
    })),

  updateProgress: (executionId, nodeId, progress) =>
    set((state) => {
      const execution = state.executions[executionId];
      if (!execution) return state;

      return {
        executions: {
          ...state.executions,
          [executionId]: {
            ...execution,
            progress: {
              ...execution.progress,
              [nodeId]: progress,
            },
            status: progress.status === 'failed' ? 'failed' : execution.status,
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
      const { [id]: _, ...rest } = state.executions;
      return {
        executions: rest,
        activeExecution: state.activeExecution === id ? null : state.activeExecution,
      };
    }),
}));
