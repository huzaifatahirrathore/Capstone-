import os
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

from ultralytics import YOLO

if __name__ == '__main__':
    model = YOLO("yolo26m-seg.pt")

    results = model.train(
        data="dataset/dataset_seg.yaml",
        epochs=100,
        imgsz=640,             # seg needs far more VRAM than detection (mask
                               # prototypes + per-instance masks). 960 OOMs on
                               # the 6 GB RTX 3060 even at batch=1; 640 fits.
        batch=2,
        project="runs/segment",
        name="yolov8m_seg_trees",
        patience=30,
        save=True,
        save_period=10,
        plots=True,
        verbose=True,
        workers=4,

        # Augmentation
        copy_paste=0.3,
        mixup=0.0,
        mosaic=1.0,
        scale=0.5,
        fliplr=0.5,
        flipud=0.1,
        hsv_h=0.015,
        hsv_s=0.7,
        hsv_v=0.4,

        # Learning rate
        cos_lr=True,
        lr0=0.005,
        lrf=0.01,

        # Loss weights
        box=10.0,
    )

    metrics = model.val(data="dataset/dataset_seg.yaml", split="test")
    print(f"\nTest mAP50:    {metrics.seg.map50:.4f}")
    print(f"Test mAP50-95: {metrics.seg.map:.4f}")
