import logging
from datasets import load_dataset

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    logger.info("Starting automated download and caching of the lmms-lab/RefCOCOg dataset...")
    
    # Pre-download and cache all splits (train, validation, test)
    try:
        dataset = load_dataset("lmms-lab/RefCOCOg")
        logger.info("Successfully downloaded and cached RefCOCOg dataset splits:")
        for split in dataset.keys():
            logger.info(f" - {split}: {len(dataset[split])} samples")
            
        # Print a sample to verify structure
        sample = dataset["val"][0]
        logger.info("Sample record format verification:")
        for key, value in sample.items():
            if key == "image":
                logger.info(f" - image: {type(value)} (Size: {value.size})")
            else:
                logger.info(f" - {key}: {value}")
                
        print("SUCCESS")
    except Exception as e:
        logger.error(f"Failed to download dataset: {e}")
        print("FAILED")

if __name__ == "__main__":
    main()
