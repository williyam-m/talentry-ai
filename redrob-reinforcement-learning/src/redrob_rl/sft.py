"""
SFT warm-start for the candidate-ranking task.

We construct gold JSON answers from the rule-based labels and run a tiny
supervised fine-tune so the policy can actually emit the target format
*before* GRPO kicks in. Without this step, every group of completions
from Qwen3-0.6B has identical reward → zero advantage → zero gradient
under GRPO. This is the standard recipe in the GRPO papers.

Gold answer template
--------------------
{"decision": "<gold_decision>", "score": <gold_score>, "reasons": [<3-4 grounded bullets>]}

The reasons are deterministic, generated from the candidate context
(skills + headline + tenure) so they are always grounded and pass the
`no_hallucination` check.
"""

from __future__ import annotations

import json
import random
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Sequence

import torch
from datasets import Dataset
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    DataCollatorForLanguageModeling,
    Trainer,
    TrainingArguments,
)

from .dataset import SYSTEM_PROMPT, PromptSample


# --------------------------------------------------------------------------- #
# Gold answer construction
# --------------------------------------------------------------------------- #

_SKILL_RE = re.compile(r"Top skills:\s*(.+)")
_HEAD_RE = re.compile(r"Headline:\s*(.+)")
_CURRENT_RE = re.compile(r"Current:\s*(.+)")
_YOE_RE = re.compile(r"YoE:\s*([0-9.]+)")


def _extract(text: str, regex: re.Pattern) -> str:
    m = regex.search(text)
    return m.group(1).strip() if m else ""


def _split_skills(skill_str: str) -> List[str]:
    return [s.strip() for s in skill_str.split(",") if s.strip()][:4]


def gold_answer(sample: PromptSample) -> Dict[str, Any]:
    """Build a grounded JSON answer from the candidate's own profile."""
    ctx = sample.context
    head = _extract(ctx, _HEAD_RE) or "experienced candidate"
    current = _extract(ctx, _CURRENT_RE) or ""
    yoe = _extract(ctx, _YOE_RE) or "?"
    skills = _split_skills(_extract(ctx, _SKILL_RE))

    reasons: List[str] = []
    if skills:
        reasons.append(f"Brings hands-on skills: {', '.join(skills[:3])}.")
    if yoe and yoe != "?":
        reasons.append(f"{yoe} years of experience matches the role's seniority.")
    if current:
        # strip the size suffix in parens
        cur_clean = re.sub(r"\s*\([^)]*\)\s*$", "", current).strip()
        if cur_clean:
            reasons.append(f"Currently {cur_clean}, relevant to the JD focus.")
    if sample.decision == "reject":
        # tilt the reasons toward a rejection rationale
        reasons = []
        if not skills:
            reasons.append("Profile lists no skills matching the JD's core stack.")
        else:
            reasons.append(
                f"Listed skills ({', '.join(skills[:3])}) only partially overlap the JD."
            )
        if yoe == "?" or (yoe != "?" and float(yoe) < 2):
            reasons.append("Years-of-experience signal is weak for this role.")
        reasons.append("Headline does not match the JD's primary responsibilities.")
    if len(reasons) < 2:
        reasons.append("See profile for additional supporting evidence.")
    reasons = reasons[:4]

    return {
        "decision": sample.decision,
        "score": round(float(sample.score), 2),
        "reasons": reasons,
    }


# --------------------------------------------------------------------------- #
# SFT trainer
# --------------------------------------------------------------------------- #

def _format_example(tokenizer, sample: PromptSample) -> Dict[str, Any]:
    """Apply the chat template to (system, user, assistant=gold)."""
    answer = json.dumps(gold_answer(sample), ensure_ascii=False, separators=(",", ":"))
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": sample.prompt},
        {"role": "assistant", "content": answer},
    ]
    text = tokenizer.apply_chat_template(messages, tokenize=False)
    return {"text": text, "answer": answer}


def run_sft(
    *,
    model: AutoModelForCausalLM,
    tokenizer: AutoTokenizer,
    samples: Sequence[PromptSample],
    output_dir: Path,
    epochs: int = 2,
    batch_size: int = 1,
    grad_accum: int = 2,
    learning_rate: float = 1.0e-5,
    max_length: int = 1024,
    seed: int = 7,
) -> Trainer:
    """Run a small SFT pass that teaches the policy the target JSON format.

    Returns the (in-memory) ``Trainer`` so the caller can pass
    ``trainer.model`` to GRPO without reloading from disk.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    shuffled = list(samples)
    rng.shuffle(shuffled)

    rows = [_format_example(tokenizer, s) for s in shuffled]
    ds = Dataset.from_list(rows)

    def _tok(batch):
        enc = tokenizer(
            batch["text"],
            max_length=max_length,
            truncation=True,
            padding="max_length",
        )
        return enc

    tok_ds = ds.map(_tok, batched=True, remove_columns=["text", "answer"])
    tok_ds.set_format(type="torch")

    collator = DataCollatorForLanguageModeling(tokenizer, mlm=False)

    args = TrainingArguments(
        output_dir=str(output_dir),
        per_device_train_batch_size=batch_size,
        gradient_accumulation_steps=grad_accum,
        learning_rate=learning_rate,
        num_train_epochs=epochs,
        logging_steps=2,
        save_strategy="no",
        report_to="none",
        remove_unused_columns=False,
        seed=seed,
        bf16=False,
        fp16=False,
        gradient_checkpointing=True,
        gradient_checkpointing_kwargs={"use_reentrant": False},
        optim="adamw_torch",
    )

    trainer = Trainer(
        model=model,
        args=args,
        train_dataset=tok_ds,
        data_collator=collator,
    )
    print(f"[sft] starting SFT warm-start on {len(rows)} examples "
          f"({epochs} epochs)…")
    trainer.train()
    print("[sft] done.")
    return trainer
