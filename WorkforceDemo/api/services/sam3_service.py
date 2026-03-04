"""
SAM3 Service - Facebook's Segment Anything Model 3 integration.

Provides text-prompted object segmentation on images using SAM3.
"""

import numpy as np
import cv2
from typing import Optional, Dict, Any, List
from PIL import Image


class Sam3Service:
    """Service for SAM3 text-prompted segmentation."""

    def __init__(self):
        self._model = None
        self._processor = None
        self._loaded = False

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    def load_model(self):
        """Lazy-load the SAM3 model and processor."""
        if self._loaded:
            return

        print("[SAM3] Loading SAM3 model...")
        try:
            from sam3 import build_sam3_image_model, Sam3Processor

            self._model = build_sam3_image_model()
            self._processor = Sam3Processor(self._model)
            self._loaded = True
            print("[SAM3] Model loaded successfully")
        except Exception as e:
            print(f"[SAM3] Failed to load model: {e}")
            raise RuntimeError(f"Failed to load SAM3 model: {e}")

    def segment(self, image: np.ndarray, text_prompt: str) -> Dict[str, Any]:
        """
        Run text-prompted segmentation on an image.

        Args:
            image: BGR numpy array from OpenCV
            text_prompt: Text description of objects to segment (e.g. "a car")

        Returns:
            Dict with annotated_image (np.ndarray), detections list, num_masks
        """
        if not self._loaded:
            self.load_model()

        # Convert BGR numpy array to PIL Image (RGB)
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(rgb)

        # Run SAM3 inference
        self._processor.set_image(pil_image)
        results = self._processor.set_text_prompt(text_prompt)

        # Extract masks, scores, boxes
        masks = results.get("masks", [])
        scores = results.get("scores", [])
        boxes = results.get("boxes", [])

        # Draw annotations on image copy
        annotated = image.copy()
        detections = []

        # Color palette for masks
        colors = [
            (0, 255, 255),   # cyan
            (255, 0, 255),   # magenta
            (0, 255, 0),     # green
            (255, 165, 0),   # orange
            (255, 0, 0),     # blue (BGR)
            (0, 0, 255),     # red (BGR)
            (255, 255, 0),   # cyan-ish
            (128, 0, 255),   # purple
        ]

        for i, mask in enumerate(masks):
            color = colors[i % len(colors)]
            score = scores[i] if i < len(scores) else 0.0

            # Convert mask to numpy if needed
            if hasattr(mask, 'cpu'):
                mask_np = mask.cpu().numpy()
            elif isinstance(mask, np.ndarray):
                mask_np = mask
            else:
                mask_np = np.array(mask)

            # Ensure mask is 2D binary
            if mask_np.ndim > 2:
                mask_np = mask_np.squeeze()
            mask_bool = mask_np.astype(bool)

            # Semi-transparent mask overlay
            overlay = annotated.copy()
            overlay[mask_bool] = color
            cv2.addWeighted(overlay, 0.4, annotated, 0.6, 0, annotated)

            # Draw contour outlines
            mask_uint8 = (mask_bool.astype(np.uint8)) * 255
            contours, _ = cv2.findContours(mask_uint8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            cv2.drawContours(annotated, contours, -1, color, 2)

            # Calculate area
            area = int(mask_bool.sum())

            # Draw bounding box and label if available
            if i < len(boxes):
                box = boxes[i]
                if hasattr(box, 'cpu'):
                    box = box.cpu().numpy()
                if hasattr(box, 'tolist'):
                    box = box.tolist()
                if len(box) >= 4:
                    x1, y1, x2, y2 = int(box[0]), int(box[1]), int(box[2]), int(box[3])
                    cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
                    label = f"#{i} {score:.2f}"
                    cv2.putText(annotated, label, (x1, y1 - 8),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

            detections.append({
                "mask_index": i,
                "score": round(float(score), 4),
                "area": area,
            })

        return {
            "annotated_image": annotated,
            "detections": detections,
            "num_masks": len(masks),
        }


# Singleton instance
_sam3_service: Optional[Sam3Service] = None


def get_sam3_service() -> Sam3Service:
    """Get or create the SAM3 service singleton."""
    global _sam3_service
    if _sam3_service is None:
        _sam3_service = Sam3Service()
    return _sam3_service
