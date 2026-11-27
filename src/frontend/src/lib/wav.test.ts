import { expect, test } from "vitest";
import { encodeWav } from "./wav";

function text(view: DataView, offset: number, length: number): string {
  return String.fromCharCode(
    ...new Uint8Array(view.buffer, offset, length).values(),
  );
}

test("writes a 16 kHz mono 16-bit PCM header", () => {
  const view = new DataView(
    encodeWav({ samples: new Float32Array(3), sampleRate: 16_000 }),
  );

  expect(text(view, 0, 4)).toBe("RIFF");
  expect(view.getUint32(4, true)).toBe(36 + 6);
  expect(text(view, 8, 8)).toBe("WAVEfmt ");
  expect(view.getUint16(20, true)).toBe(1);
  expect(view.getUint16(22, true)).toBe(1);
  expect(view.getUint32(24, true)).toBe(16_000);
  expect(view.getUint32(28, true)).toBe(32_000);
  expect(view.getUint16(32, true)).toBe(2);
  expect(view.getUint16(34, true)).toBe(16);
  expect(text(view, 36, 4)).toBe("data");
});

test("stores one 16-bit sample per input sample, clamped to the range", () => {
  const samples = Float32Array.from([0, 1, -1, 2, -0.5]);
  const view = new DataView(encodeWav({ samples, sampleRate: 16_000 }));

  expect(view.getUint32(40, true)).toBe(samples.length * 2);
  expect(view.byteLength).toBe(44 + samples.length * 2);
  expect(
    Array.from(samples, (_, index) => view.getInt16(44 + index * 2, true)),
  ).toEqual([0, 32767, -32768, 32767, -16384]);
});
