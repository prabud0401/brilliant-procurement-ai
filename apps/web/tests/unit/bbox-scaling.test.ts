import { describe, it, expect } from "vitest";
import { bboxToOverlay, type BoundingBox } from "@/lib/documents/bbox";

describe("bbox-to-overlay scaling utility", () => {
  it("scales normalized [0.0, 1.0] coordinates into exact percentage styles", () => {
    const bbox: BoundingBox = {
      box: [0.1, 0.2, 0.4, 0.5], // minX=10%, minY=20%, maxX=40%, maxY=50%
    };

    const overlay = bboxToOverlay(bbox);
    expect(overlay).not.toBeNull();
    expect(overlay?.leftPercent).toBeCloseTo(10.0, 1);
    expect(overlay?.topPercent).toBeCloseTo(20.0, 1);
    expect(overlay?.widthPercent).toBeCloseTo(30.0, 1);
    expect(overlay?.heightPercent).toBeCloseTo(30.0, 1);

    expect(overlay?.style.left).toBe("10.00%");
    expect(overlay?.style.top).toBe("20.00%");
    expect(overlay?.style.width).toBe("30.00%");
    expect(overlay?.style.height).toBe("30.00%");
  });

  it("scales Document Intelligence inch coordinates (8.5 x 11.0 in) into percentages", () => {
    // A box from 1.7 inches to 5.1 inches wide, 2.2 inches to 4.4 inches high
    const bbox: BoundingBox = {
      box: [1.7, 2.2, 5.1, 4.4],
    };

    const overlay = bboxToOverlay(bbox, { pageWidth: 8.5, pageHeight: 11.0 });
    expect(overlay).not.toBeNull();

    // 1.7 / 8.5 = 20%
    expect(overlay?.leftPercent).toBeCloseTo(20.0, 1);
    // 2.2 / 11.0 = 20%
    expect(overlay?.topPercent).toBeCloseTo(20.0, 1);
    // (5.1 - 1.7) / 8.5 = 3.4 / 8.5 = 40%
    expect(overlay?.widthPercent).toBeCloseTo(40.0, 1);
    // (4.4 - 2.2) / 11.0 = 2.2 / 11.0 = 20%
    expect(overlay?.heightPercent).toBeCloseTo(20.0, 1);
  });

  it("calculates bounding box from 8-point polygon correctly", () => {
    // Polygon: [x1, y1, x2, y2, x3, y3, x4, y4]
    const bbox: BoundingBox = {
      polygon: [0.2, 0.3, 0.6, 0.3, 0.6, 0.8, 0.2, 0.8],
    };

    const overlay = bboxToOverlay(bbox);
    expect(overlay).not.toBeNull();
    expect(overlay?.leftPercent).toBeCloseTo(20.0, 1);
    expect(overlay?.topPercent).toBeCloseTo(30.0, 1);
    expect(overlay?.widthPercent).toBeCloseTo(40.0, 1);
    expect(overlay?.heightPercent).toBeCloseTo(50.0, 1);
  });

  it("scales PDF point coordinates (e.g. 612 x 792 points) correctly", () => {
    const bbox: BoundingBox = {
      box: [61.2, 79.2, 306.0, 396.0],
    };

    const overlay = bboxToOverlay(bbox, { pageWidth: 612, pageHeight: 792 });
    expect(overlay).not.toBeNull();
    expect(overlay?.leftPercent).toBeCloseTo(10.0, 1);
    expect(overlay?.topPercent).toBeCloseTo(10.0, 1);
    expect(overlay?.widthPercent).toBeCloseTo(40.0, 1);
    expect(overlay?.heightPercent).toBeCloseTo(40.0, 1);
  });

  it("handles inverted coordinates gracefully (min > max)", () => {
    const bbox: BoundingBox = {
      box: [0.8, 0.9, 0.2, 0.3], // inverted
    };

    const overlay = bboxToOverlay(bbox);
    expect(overlay).not.toBeNull();
    expect(overlay?.leftPercent).toBeCloseTo(20.0, 1);
    expect(overlay?.topPercent).toBeCloseTo(30.0, 1);
    expect(overlay?.widthPercent).toBeCloseTo(60.0, 1);
    expect(overlay?.heightPercent).toBeCloseTo(60.0, 1);
  });

  it("clamps out-of-boundary coordinates to stay inside [0, 100]%", () => {
    const bbox: BoundingBox = {
      box: [-0.5, -0.2, 1.5, 1.8],
    };

    const overlay = bboxToOverlay(bbox);
    expect(overlay).not.toBeNull();
    expect(overlay?.leftPercent).toBe(0);
    expect(overlay?.topPercent).toBe(0);
    expect(overlay?.widthPercent).toBeLessThanOrEqual(100);
    expect(overlay?.heightPercent).toBeLessThanOrEqual(100);
  });

  it("returns null for null, undefined, or malformed bbox", () => {
    expect(bboxToOverlay(null)).toBeNull();
    expect(bboxToOverlay(undefined)).toBeNull();
    expect(bboxToOverlay({})).toBeNull();
    expect(bboxToOverlay({ box: [1, 2] as unknown as [number, number, number, number] })).toBeNull();
    expect(bboxToOverlay({ polygon: [1, 2, 3] })).toBeNull();
    expect(bboxToOverlay({ box: [NaN, 1, 2, 3] })).toBeNull();
  });
});
