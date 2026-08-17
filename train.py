import os
import torch
from torch.utils.data import Dataset, DataLoader
from transformers import AutoProcessor, AutoModelForCausalLM, TrainingArguments, Trainer
from peft import LoraConfig, get_peft_model
from datasets import load_dataset
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Config
MODEL_ID = "microsoft/Florence-2-base"
LORA_OUTPUT_DIR = "./model_cache/florence2_lora"
BATCH_SIZE = 2
EPOCHS = 3
LEARNING_RATE = 1e-4

class FlorenceRefCOCOgDataset(Dataset):
    def __init__(self, hf_dataset, processor):
        self.dataset = hf_dataset
        self.processor = processor
        self.samples = []
        
        # Optimize dataset initialization by reading 'answer' column directly
        # to avoid deserializing images for all rows upfront
        answers = self.dataset["answer"]
        for idx, captions in enumerate(answers):
            for cap in captions:
                self.samples.append((idx, cap))

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        item_idx, caption = self.samples[idx]
        sample = self.dataset[item_idx]
        image = sample["image"].convert("RGB")
        bbox = sample["bbox"] # [x, y, w, h]
        
        # Scale coordinates to 0-999
        w, h = image.size
        # Bbox is [x, y, width, height]
        bx, by, bw, bh = bbox
        x1 = bx
        y1 = by
        x2 = bx + bw
        y2 = by + bh
        
        # Scale
        x1_scaled = max(0, min(999, int(round((x1 / w) * 999))))
        y1_scaled = max(0, min(999, int(round((y1 / h) * 999))))
        x2_scaled = max(0, min(999, int(round((x2 / w) * 999))))
        y2_scaled = max(0, min(999, int(round((y2 / h) * 999))))

        # Manually resize PIL image to a uniform size (768, 768) to prevent stacking errors in batch collation
        image = image.resize((768, 768))

        # Prefix for caption-to-phrase-grounding
        prompt = f"<CAPTION_TO_PHRASE_GROUNDING> {caption}"
        # Florence-2 target output format: text + location labels
        target = f"{caption} <loc_{x1_scaled}><loc_{y1_scaled}><loc_{x2_scaled}><loc_{y2_scaled}>"

        return {
            "image": image,
            "prompt": prompt,
            "target": target
        }

def get_collate_fn(processor):
    def collate_fn(batch):
        prompts = [item["prompt"] for item in batch]
        targets = [item["target"] for item in batch]
        images = [item["image"] for item in batch]
        
        inputs = processor(
            text=prompts,
            images=images,
            return_tensors="pt",
            padding=True
        )
        
        # Tokenize labels
        labels = processor.tokenizer(
            text=targets,
            return_tensors="pt",
            padding=True,
            return_token_type_ids=False
        ).input_ids

        # Replace padding token id with -100 so it is ignored in loss computation
        labels[labels == processor.tokenizer.pad_token_id] = -100
        
        inputs["labels"] = labels
        return inputs
    return collate_fn

def main():
    logger.info("Setting up device...")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info(f"Using device: {device}")

    logger.info(f"Loading processor and model: {MODEL_ID}...")
    processor = AutoProcessor.from_pretrained(MODEL_ID, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID, 
        trust_remote_code=True,
        torch_dtype=torch.float16 if device == "cuda" else torch.float32
    )

    # Configure LoRA
    logger.info("Configuring LoRA...")
    lora_config = LoraConfig(
        r=8,
        lora_alpha=16,
        target_modules=["q_proj", "o_proj", "k_proj", "v_proj", "linear", "Conv2d"],
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM"
    )
    
    # We convert model to peft
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    # Load local cached dataset
    logger.info("Loading RefCOCOg dataset from cache...")
    dataset = load_dataset("lmms-lab/RefCOCOg")
    
    train_ds = FlorenceRefCOCOgDataset(dataset["val"], processor)
    val_ds = FlorenceRefCOCOgDataset(dataset["test"], processor)

    logger.info("Defining training arguments...")
    training_args = TrainingArguments(
        output_dir=LORA_OUTPUT_DIR,
        per_device_train_batch_size=BATCH_SIZE,
        per_device_eval_batch_size=BATCH_SIZE,
        num_train_epochs=EPOCHS,
        learning_rate=LEARNING_RATE,
        weight_decay=0.01,
        eval_strategy="epoch",
        save_strategy="epoch",
        remove_unused_columns=False,
        logging_steps=10,
        dataloader_num_workers=0,
        fp16=(device == "cuda"),
        load_best_model_at_end=True,
        metric_for_best_model="loss",
        greater_is_better=False,
        save_total_limit=1,
        report_to="none" # Disable logging to wandb/tensorboard for simplicity
    )

    logger.info("Initializing Trainer...")
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_ds,
        eval_dataset=val_ds,
        data_collator=get_collate_fn(processor),
    )

    logger.info("Starting training...")
    trainer.train()

    logger.info(f"Saving final trained adapter weights to {LORA_OUTPUT_DIR}...")
    model.save_pretrained(LORA_OUTPUT_DIR)
    processor.save_pretrained(LORA_OUTPUT_DIR)
    logger.info("Training complete and adapter model saved successfully!")

if __name__ == "__main__":
    main()
