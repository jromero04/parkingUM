"use client";

import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";

import { ApiError, apiFetch } from "@/lib/api";
import type { User } from "@/lib/types";

type LoginResponse = { access_token: string; token_type: "bearer"; expires_in: number; user: User };
type AuthValue = {
  token: string | null;
  user: User | null;
  login: (email: string, password: string) => Promise<User>;
  register: (name: string, email: string, password: string) => Promise<void>;
  logout: () => void;
  request: <T>(path: string, options?: RequestInit) => Promise<T>;
};

const AuthContext = createContext<AuthValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<{ token: string; user: User } | null>(null);

  const login = useCallback(async (email: string, password: string) => {
    const result = await apiFetch<LoginResponse>("/api/v1/usuarios/login", undefined, {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
    setSession({ token: result.access_token, user: result.user });
    return result.user;
  }, []);

  const register = useCallback(async (name: string, email: string, password: string) => {
    await apiFetch("/api/v1/usuarios/registro", undefined, {
      method: "POST",
      body: JSON.stringify({ name, email, password }),
    });
    await login(email, password);
  }, [login]);

  const logout = useCallback(() => setSession(null), []);
  const request = useCallback(async <T,>(path: string, options: RequestInit = {}) => {
    if (!session) throw new ApiError(401, "UNAUTHORIZED", "La sesión no está disponible.");
    try {
      return await apiFetch<T>(path, session.token, options);
    } catch (problem) {
      if (problem instanceof ApiError && problem.status === 401) logout();
      throw problem;
    }
  }, [logout, session]);

  const value = useMemo<AuthValue>(() => ({
    token: session?.token ?? null,
    user: session?.user ?? null,
    login,
    register,
    logout,
    request,
  }), [login, logout, register, request, session]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth debe usarse dentro de AuthProvider");
  return value;
}
