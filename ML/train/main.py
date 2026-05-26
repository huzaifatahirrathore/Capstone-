import os
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

from ultralytics import YOLO

if __name__ == '__main__':
    # Use YOLO26 medium — good balance of speed and accuracy for tree detection
    model = YOLO("yolo26m.pt")

    results = model.train(
        data="dataset/dataset.yaml",
        epochs=200,
        imgsz=960,
        batch=2,               # RTX 3060 Laptop (5.67 GiB) — 1280 OOMs, 960 is the sweet spot
        project="runs/tree_detect",
        name="yolo26m_trees",
        patience=30,           # early stopping if no improvement for 30 epochs
        save=True,
        save_period=10,        # checkpoint every 10 epochs
        plots=True,
        verbose=True,
        workers=4,             # reduce dataloader workers to save system memory

        # Data augmentation
        augment=True,
        mosaic=1.0,            # mosaic augmentation (combines 4 images)
        mixup=0.15,            # blends two images together
        scale=0.5,             # random scaling ±50%
        fliplr=0.5,            # horizontal flip
        flipud=0.1,            # vertical flip (useful for aerial/satellite views)
        hsv_h=0.015,           # hue variation
        hsv_s=0.7,             # saturation variation
        hsv_v=0.4,             # brightness variation

        # Learning rate tuning
        lr0=0.005,             # lower starting learning rate for stable convergence
        lrf=0.01,              # final learning rate fraction
    )

    # Validate on test set
    metrics = model.val(data="dataset/dataset.yaml", split="test")
    print(f"\nTest mAP50:    {metrics.box.map50:.4f}")
    print(f"Test mAP50-95: {metrics.box.map:.4f}")