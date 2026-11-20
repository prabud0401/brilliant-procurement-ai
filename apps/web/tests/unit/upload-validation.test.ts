import { describe, it, expect } from "vitest";
import {
  validateUploadFile,
  checkMagicBytes,
  MAX_UPLOAD_SIZE_BYTES,
} from "@/lib/documents/validation";

describe("Document upload validation per Design 7.4 & US-01", () => {
  it("accepts valid PDF file with %PDF magic bytes", async () => {
    // PDF magic bytes: 0x25, 0x50, 0x44, 0x46 ("%PDF")
    const pdfBytes = new Uint8Array([0x25, 0x50, 0x44, 0x46, 0x2d, 0x31, 0x2e, 0x37]);
    const file = new File([pdfBytes], "quote.pdf", { type: "application/pdf" });

    const result = await validateUploadFile(file);
    expect(result.valid).toBe(true);
    expect(result.detectedType).toBe("pdf");
    expect(result.detectedMime).toBe("application/pdf");
    expect(result.error).toBeUndefined();
  });

  it("accepts valid PNG file with 8-byte PNG header", async () => {
    // PNG magic bytes: 89 50 4E 47 0D 0A 1A 0A
    const pngBytes = new Uint8Array([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 0x00, 0x00]);
    const file = new File([pngBytes], "delivery_note.png", { type: "image/png" });

    const result = await validateUploadFile(file);
    expect(result.valid).toBe(true);
    expect(result.detectedType).toBe("image");
    expect(result.detectedMime).toBe("image/png");
  });

  it("accepts valid JPEG file with FF D8 FF header", async () => {
    // JPEG magic bytes: FF D8 FF
    const jpegBytes = new Uint8Array([0xff, 0xd8, 0xff, 0xe0, 0x00, 0x10]);
    const file = new File([jpegBytes], "invoice.jpg", { type: "image/jpeg" });

    const result = await validateUploadFile(file);
    expect(result.valid).toBe(true);
    expect(result.detectedType).toBe("image");
    expect(result.detectedMime).toBe("image/jpeg");
  });

  it("accepts valid TIFF file (little-endian & big-endian)", async () => {
    // TIFF little-endian: 49 49 2A 00
    const tiffLe = new Uint8Array([0x49, 0x49, 0x2a, 0x00, 0x08, 0x00]);
    const fileLe = new File([tiffLe], "scan.tiff", { type: "image/tiff" });
    const resultLe = await validateUploadFile(fileLe);
    expect(resultLe.valid).toBe(true);
    expect(resultLe.detectedMime).toBe("image/tiff");

    // TIFF big-endian: 4D 4D 00 2A
    const tiffBe = new Uint8Array([0x4d, 0x4d, 0x00, 0x2a, 0x00, 0x08]);
    const fileBe = new File([tiffBe], "scan.tif", { type: "image/tiff" });
    const resultBe = await validateUploadFile(fileBe);
    expect(resultBe.valid).toBe(true);
  });

  it("rejects files with unsupported extensions", async () => {
    const bytes = new Uint8Array([0x25, 0x50, 0x44, 0x46]);
    const file = new File([bytes], "malicious.exe", { type: "application/x-msdownload" });

    const result = await validateUploadFile(file);
    expect(result.valid).toBe(false);
    expect(result.error).toContain("extension '.exe' is not supported");
  });

  it("rejects empty files (0 bytes)", async () => {
    const emptyFile = new File([], "empty.pdf", { type: "application/pdf" });

    const result = await validateUploadFile(emptyFile);
    expect(result.valid).toBe(false);
    expect(result.error).toContain("empty");
  });

  it("rejects files exceeding 20 MB size limit", async () => {
    const largeSize = MAX_UPLOAD_SIZE_BYTES + 1024;
    // Mock File with large size
    const largeFile = {
      name: "huge.pdf",
      size: largeSize,
      slice: () => ({ arrayBuffer: async () => new ArrayBuffer(16) }),
    } as unknown as File;

    const result = await validateUploadFile(largeFile);
    expect(result.valid).toBe(false);
    expect(result.error).toContain("exceeds maximum allowed limit of 20 MB");
  });

  it("rejects spoofed extension when content bytes are invalid (anti-spoofing)", async () => {
    // Plain text content named as .pdf
    const textBytes = new TextEncoder().encode("Hello world this is plain text not a pdf");
    const spoofedFile = new File([textBytes], "fake.pdf", { type: "application/pdf" });

    const result = await validateUploadFile(spoofedFile);
    expect(result.valid).toBe(false);
    expect(result.error).toContain("does not match any accepted document format");
  });

  it("checkMagicBytes returns error for truncated buffers", () => {
    const shortBuffer = new Uint8Array([0x25, 0x50]);
    const result = checkMagicBytes(shortBuffer);
    expect(result.valid).toBe(false);
    expect(result.error).toContain("too small");
  });
});
