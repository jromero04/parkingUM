type ErrorEnvelope = {
  error?: { code?: string; message?: string; details?: Record<string, unknown> };
  correlation_id?: string;
};

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
    readonly correlationId?: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export async function apiFetch<T>(path: string, token?: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(path, {
    ...options,
    headers: {
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  });
  const body = (await response.json().catch(() => null)) as ErrorEnvelope | T | null;
  if (!response.ok) {
    const envelope = body as ErrorEnvelope | null;
    throw new ApiError(
      response.status,
      envelope?.error?.code ?? "HTTP_ERROR",
      envelope?.error?.message ?? `Error ${response.status}`,
      envelope?.correlation_id,
    );
  }
  return body as T;
}
