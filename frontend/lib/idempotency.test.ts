import { describe, expect, it, vi } from "vitest";

import { createIdempotencyKey } from "./idempotency";


describe("createIdempotencyKey", () => {
  it("usa randomUUID cuando esta disponible", () => {
    const randomUUID = vi.fn(() => "11111111-2222-4333-8444-555555555555");
    const getRandomValues = vi.fn((bytes: Uint8Array) => bytes);

    expect(createIdempotencyKey({ randomUUID, getRandomValues })).toBe(
      "11111111-2222-4333-8444-555555555555",
    );
    expect(getRandomValues).not.toHaveBeenCalled();
  });

  it("genera un UUID v4 con getRandomValues cuando randomUUID no existe", () => {
    const getRandomValues = vi.fn((bytes: Uint8Array) => bytes.fill(0));

    expect(createIdempotencyKey({ getRandomValues })).toBe(
      "00000000-0000-4000-8000-000000000000",
    );
  });
});
