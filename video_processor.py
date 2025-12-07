import cv2
import threading
import time
import numpy as np


class VideoProcessor:
    def __init__(self, alarm_manager, traffic_data, current_thresholds_getter):
        self.alarm_manager = alarm_manager
        self.traffic_data = traffic_data
        self.get_current_thresholds = current_thresholds_getter

        self.is_processing = False
        self.processing_thread = None
        self.video_path = None

        # Frame storage for streaming
        self.current_frame = None
        self.frame_lock = threading.Lock()

        # Simple config
        self.PROCESS_EVERY_N_FRAMES = 2   # process every 2nd frame
        self.FPS = 30

        print("✓ Simple VideoProcessor (no YOLO) initialized")

    def start_processing(self, video_path):
        """Start background processing of the uploaded video."""
        if self.is_processing:
            print("⚠️ Processing already running")
            return False

        if not video_path or not isinstance(video_path, str):
            print("❌ Invalid video path")
            return False

        self.video_path = video_path
        self.is_processing = True

        self.processing_thread = threading.Thread(
            target=self._process_video,
            daemon=True
        )
        self.processing_thread.start()

        print("✓ Simple video processing started (no YOLO)")
        return True

    def stop_processing(self):
        """Stop processing and clear state."""
        if not self.is_processing:
            return

        print("🛑 Stopping simple video processing...")
        self.is_processing = False

        if self.processing_thread and self.processing_thread.is_alive():
            self.processing_thread.join(timeout=2)

        with self.frame_lock:
            self.current_frame = None

        print("✓ Simple video processing stopped")

    def get_current_frame(self):
        """Return the latest annotated frame (or None)."""
        with self.frame_lock:
            if self.current_frame is not None:
                return self.current_frame.copy()
        return None

    def _process_video(self):
        """Main loop: read video, draw dummy boxes, store frame."""
        print(f"📹 Opening video: {self.video_path}")
        cap = cv2.VideoCapture(self.video_path)

        if not cap.isOpened():
            print(f"❌ Failed to open video: {self.video_path}")
            self.is_processing = False
            return

        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps and fps > 0:
            self.FPS = fps
        else:
            self.FPS = 30
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        print(f"📊 Video info: {total_frames} frames @ {self.FPS:.2f} FPS")

        frame_count = 0

        while cap.isOpened() and self.is_processing:
            ret, frame = cap.read()
            if not ret:
                # Loop the video
                print("📹 Video ended, looping...")
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                frame_count = 0
                continue

            frame_count += 1

            # Skip some frames for speed
            if frame_count % self.PROCESS_EVERY_N_FRAMES != 0:
                with self.frame_lock:
                    self.current_frame = frame
                continue

            try:
                annotated = self._draw_dummy_boxes(frame, frame_count)

                # Store for streaming
                with self.frame_lock:
                    self.current_frame = annotated

            except Exception as e:
                print(f"⚠️ Frame {frame_count} error (dummy draw): {e}")

            time.sleep(0.01)

        cap.release()
        print("✓ Simple video processing loop ended")

    def _draw_dummy_boxes(self, frame, frame_count):
        """
        Draw some fake bounding boxes and labels for testing.
        No detection, just rectangles that move around.
        """
        h, w, _ = frame.shape

        # Example: three moving boxes based on frame_count
        boxes = []

        # Box 1 – "2WHLR"
        x1 = int((frame_count * 5) % (w - 100))
        y1 = int(h * 0.3)
        boxes.append((x1, y1, x1 + 120, y1 + 60, (0, 255, 0), "2WHLR"))

        # Box 2 – "LMV"
        x2 = int((frame_count * 3) % (w - 150))
        y2 = int(h * 0.5)
        boxes.append((x2, y2, x2 + 160, y2 + 80, (255, 0, 0), "LMV"))

        # Box 3 – "HMV"
        x3 = int((frame_count * 2) % (w - 180))
        y3 = int(h * 0.7)
        boxes.append((x3, y3, x3 + 180, y3 + 90, (0, 165, 255), "HMV"))

        annotated = frame.copy()

        for (x1, y1, x2, y2, color, label) in boxes:
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
            cv2.putText(
                annotated,
                label,
                (x1 + 5, y1 - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                color,
                2,
                cv2.LINE_AA,
            )

        # Optional: draw frame counter
        cv2.putText(
            annotated,
            f"Frame: {frame_count}",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )

        return annotated
