import type { CSSProperties } from "react";

export interface BoundingBox {
  page?: number;
  box?: [number, number, number, number]; // [min_x, min_y, max_x, max_y]
  polygon?: number[]; // [x1, y1, x2, y2, x3, y3, x4, y4]
  [key: string]: unknown;
}

export interface OverlayScalingOptions {
  pageWidth?: number; // e.g. 8.5 for inches or 612 for PDF points
  pageHeight?: number; // e.g. 11.0 for inches or 792 for PDF points
  viewportWidth?: number;
  viewportHeight?: number;
}

export interface OverlayBox {
  leftPercent: number;
  topPercent: number;
  widthPercent: number;
  heightPercent: number;
  style: CSSProperties;
}

/**
 * Normalizes and converts Document Intelligence / extraction bounding boxes
 * into responsive CSS percentage coordinates for rendering highlight overlays.
 *
 * Coordinates from Document Intelligence may be:
 * 1. Normalized values (0.0 to 1.0)
 * 2. Inches (e.g. 0 to 8.5 width, 0 to 11.0 height for US Letter)
 * 3. PDF points (e.g. 0 to 612 width, 0 to 792 height)
 * 4. Pixels
 */
export function bboxToOverlay(
  bbox: BoundingBox | null | undefined,
  options: OverlayScalingOptions = {}
): OverlayBox | null {
  if (!bbox) return null;

  let minX: number | undefined;
  let minY: number | undefined;
  let maxX: number | undefined;
  let maxY: number | undefined;

  if (Array.isArray(bbox.box) && bbox.box.length >= 4) {
    [minX, minY, maxX, maxY] = bbox.box;
  } else if (Array.isArray(bbox.polygon) && bbox.polygon.length >= 8) {
    const xs = bbox.polygon.filter((_, i) => i % 2 === 0);
    const ys = bbox.polygon.filter((_, i) => i % 2 === 1);
    minX = Math.min(...xs);
    maxX = Math.max(...xs);
    minY = Math.min(...ys);
    maxY = Math.max(...ys);
  }

  if (
    minX === undefined ||
    minY === undefined ||
    maxX === undefined ||
    maxY === undefined ||
    isNaN(minX) ||
    isNaN(minY) ||
    isNaN(maxX) ||
    isNaN(maxY)
  ) {
    return null;
  }

  // Ensure min <= max
  if (minX > maxX) [minX, maxX] = [maxX, minX];
  if (minY > maxY) [minY, maxY] = [maxY, minY];

  // Determine coordinate domain
  let leftPercent: number;
  let topPercent: number;
  let widthPercent: number;
  let heightPercent: number;

  const isNormalized = maxX <= 1.05 && maxY <= 1.05;

  if (isNormalized) {
    leftPercent = minX * 100;
    topPercent = minY * 100;
    widthPercent = (maxX - minX) * 100;
    heightPercent = (maxY - minY) * 100;
  } else if (maxX <= 20 && maxY <= 25) {
    // Inches (standard Document Intelligence default: US Letter 8.5 x 11 in)
    const pWidth = options.pageWidth ?? 8.5;
    const pHeight = options.pageHeight ?? 11.0;
    leftPercent = (minX / pWidth) * 100;
    topPercent = (minY / pHeight) * 100;
    widthPercent = ((maxX - minX) / pWidth) * 100;
    heightPercent = ((maxY - minY) / pHeight) * 100;
  } else {
    // PDF points or pixels
    const pWidth = options.pageWidth ?? 612;
    const pHeight = options.pageHeight ?? 792;
    leftPercent = (minX / pWidth) * 100;
    topPercent = (minY / pHeight) * 100;
    widthPercent = ((maxX - minX) / pWidth) * 100;
    heightPercent = ((maxY - minY) / pHeight) * 100;
  }

  // Clamp percentages within page boundaries (0 to 100%)
  const clampedLeft = Math.max(0, Math.min(100, leftPercent));
  const clampedTop = Math.max(0, Math.min(100, topPercent));
  const clampedWidth = Math.max(0.5, Math.min(100 - clampedLeft, widthPercent));
  const clampedHeight = Math.max(0.5, Math.min(100 - clampedTop, heightPercent));

  return {
    leftPercent: clampedLeft,
    topPercent: clampedTop,
    widthPercent: clampedWidth,
    heightPercent: clampedHeight,
    style: {
      left: `${clampedLeft.toFixed(2)}%`,
      top: `${clampedTop.toFixed(2)}%`,
      width: `${clampedWidth.toFixed(2)}%`,
      height: `${clampedHeight.toFixed(2)}%`,
    },
  };
}
