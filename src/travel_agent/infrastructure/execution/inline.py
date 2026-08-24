"""Synchronous first-slice executor behind the GenerationExecutor port."""

from __future__ import annotations

from typing import Protocol


class GenerationExecutionHandler(Protocol):
    def handle(self, generation_intent_id: str) -> object: ...


class InlineGenerationExecutor:
    def __init__(self, handler: GenerationExecutionHandler) -> None:
        self._handler = handler

    def submit(self, generation_intent_id: str) -> None:
        self._handler.handle(generation_intent_id)
