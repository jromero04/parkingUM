import { afterEach, describe, expect, it, vi } from "vitest";

import { apiFetch } from "./api";

afterEach(() => vi.unstubAllGlobals());

describe("apiFetch", () => {
  it("envia el bearer token", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ ok: true }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    await apiFetch("/api/test", "token");
    expect(fetchMock.mock.calls[0][1].headers.Authorization).toBe("Bearer token");
  });

  it("convierte el sobre de error del backend", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({
      error: { code: "SPOT_UNAVAILABLE", message: "No disponible", details: {} },
      correlation_id: "trace-id",
    }), { status: 409 })));
    await expect(apiFetch("/api/test")).rejects.toMatchObject({
      status: 409,
      code: "SPOT_UNAVAILABLE",
      message: "No disponible",
    });
  });
});
