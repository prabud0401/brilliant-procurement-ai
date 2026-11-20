/**
 * Document file validation mirroring backend checks per Design 7.4 and US-01.
 */

export const MAX_UPLOAD_SIZE_BYTES = 20 * 1024 * 1024; // 20 MB
export const ALLOWED_MIME_TYPES = new Set([
  "application/pdf",
  "image/png",
  "image/jpeg",
  "image/tiff",
]);

export const ALLOWED_EXTENSIONS = new Set([
  ".pdf",
  ".png",
  ".jpg",
  ".jpeg",
  ".tiff",
  ".tif",
]);

export interface ValidationResult {
  valid: boolean;
  error?: string;
  detectedType?: string;
  detectedMime?: string;
}

/**
 * Checks magic bytes of a file buffer to verify true content type (anti-spoofing).
 */
export function checkMagicBytes(buffer: Uint8Array): { valid: boolean; mime?: string; error?: string } {
  if (buffer.length < 4) {
    return { valid: false, error: "File is too small or corrupt." };
  }

  // 1. PDF: %PDF (0x25, 0x50, 0x44, 0x46)
  if (
    buffer[0] === 0x25 &&
    buffer[1] === 0x50 &&
    buffer[2] === 0x44 &&
    buffer[3] === 0x46
  ) {
    return { valid: true, mime: "application/pdf" };
  }

  // 2. PNG: 89 50 4E 47 0D 0A 1A 0A
  if (
    buffer.length >= 8 &&
    buffer[0] === 0x89 &&
    buffer[1] === 0x50 &&
    buffer[2] === 0x4e &&
    buffer[3] === 0x47 &&
    buffer[4] === 0x0d &&
    buffer[5] === 0x0a &&
    buffer[6] === 0x1a &&
    buffer[7] === 0x0a
  ) {
    return { valid: true, mime: "image/png" };
  }

  // 3. JPEG: FF D8 FF
  if (buffer[0] === 0xff && buffer[1] === 0xd8 && buffer[2] === 0xff) {
    return { valid: true, mime: "image/jpeg" };
  }

  // 4. TIFF: II*\0 (0x49 0x49 0x2A 0x00) or MM\0* (0x4D 0x4D 0x00 0x2A)
  if (
    (buffer[0] === 0x49 && buffer[1] === 0x49 && buffer[2] === 0x2a && buffer[3] === 0x00) ||
    (buffer[0] === 0x4d && buffer[1] === 0x4d && buffer[2] === 0x00 && buffer[3] === 0x2a)
  ) {
    return { valid: true, mime: "image/tiff" };
  }

  return {
    valid: false,
    error: "File content does not match any accepted document format (PDF, PNG, JPEG, TIFF).",
  };
}

/**
 * Safely reads the initial bytes of a File/Blob across all browser and test (jsdom) environments.
 */
export async function readFileBytes(file: File | Blob, maxBytes = 16): Promise<Uint8Array> {
  const target = typeof file.slice === "function" ? file.slice(0, maxBytes) : file;

  if (typeof target.arrayBuffer === "function") {
    try {
      const buffer = await target.arrayBuffer();
      return new Uint8Array(buffer);
    } catch {
      // Fallback
    }
  }

  if (typeof FileReader !== "undefined") {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => {
        resolve(new Uint8Array(reader.result as ArrayBuffer));
      };
      reader.onerror = () => reject(reader.error);
      reader.readAsArrayBuffer(target);
    });
  }

  throw new Error("FileReader not supported");
}

/**
 * Validates file size, extension, and content bytes client-side.
 */
export async function validateUploadFile(file: File): Promise<ValidationResult> {
  // 1. Check size limit
  if (file.size <= 0) {
    return { valid: false, error: "The selected file is empty." };
  }
  if (file.size > MAX_UPLOAD_SIZE_BYTES) {
    const sizeMb = (file.size / (1024 * 1024)).toFixed(1);
    return {
      valid: false,
      error: `File size (${sizeMb} MB) exceeds maximum allowed limit of 20 MB.`,
    };
  }

  // 2. Check extension
  const ext = "." + (file.name.split(".").pop()?.toLowerCase() || "");
  if (!ALLOWED_EXTENSIONS.has(ext)) {
    return {
      valid: false,
      error: `File extension '${ext}' is not supported. Please upload a PDF, PNG, JPG, or TIFF file.`,
    };
  }

  // 3. Verify magic bytes from first 16 bytes
  try {
    const bytes = await readFileBytes(file, 16);
    const magic = checkMagicBytes(bytes);

    if (!magic.valid) {
      return { valid: false, error: magic.error };
    }

    return {
      valid: true,
      detectedMime: magic.mime,
      detectedType: magic.mime === "application/pdf" ? "pdf" : "image",
    };
  } catch {
    return { valid: false, error: "Could not read file header to verify format." };
  }
}
