import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import api from '../api/client';

interface User {
  id: string;
  username: string;
  email: string | null;
  is_active: boolean;
  is_admin: boolean;
}

interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;

  // Actions
  login: (username: string, password: string) => Promise<void>;
  register: (username: string, email: string, password: string) => Promise<void>;
  logout: () => void;
  clearError: () => void;
  checkAuth: () => void;
}

// Configure api defaults
const setupApiInterceptors = (token: string | null) => {
  if (token) {
    api.defaults.headers.common['Authorization'] = `Bearer ${token}`;
  } else {
    delete api.defaults.headers.common['Authorization'];
  }
};

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      token: null,
      isAuthenticated: false,
      isLoading: false,
      error: null,

      login: async (username: string, password: string) => {
        set({ isLoading: true, error: null });
        try {
          const response = await api.post('/auth/login', { username, password });
          const { access_token } = response.data;

          // Set token in api defaults
          setupApiInterceptors(access_token);

          // Get user info from /auth/me endpoint
          const userResponse = await api.get('/auth/me');
          const user: User = userResponse.data;

          set({
            token: access_token,
            user,
            isAuthenticated: true,
            isLoading: false,
            error: null,
          });
        } catch (error: any) {
          console.error('Auth store login error:', error);
          const errorMessage = error.response?.data?.detail || 'Login failed';
          console.log('Setting error state:', errorMessage);
          set({
            isLoading: false,
            error: errorMessage,
          });
          throw error;
        }
      },

      register: async (username: string, email: string, password: string) => {
        set({ isLoading: true, error: null });
        try {
          const response = await api.post('/auth/register', {
            username,
            email,
            password,
          });

          const user: User = response.data;

          set({
            isLoading: false,
            error: null,
          });

          // After registration, user needs to login
          // Return the user data for UI feedback
          return user;
        } catch (error: any) {
          set({
            isLoading: false,
            error: error.response?.data?.detail || 'Registration failed',
          });
          throw error;
        }
      },

      logout: () => {
        setupApiInterceptors(null);
        set({
          user: null,
          token: null,
          isAuthenticated: false,
          error: null,
        });
      },

      clearError: () => set({ error: null }),

      checkAuth: () => {
        const state = get();
        if (state.token) {
          setupApiInterceptors(state.token);
        }
      },
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({
        user: state.user,
        token: state.token,
        isAuthenticated: state.isAuthenticated,
      }),
      onRehydrateStorage: () => (state) => {
        // Setup api interceptors when store is rehydrated
        if (state?.token) {
          setupApiInterceptors(state.token);
        }
      },
    }
  )
);
