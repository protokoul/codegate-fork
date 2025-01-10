from abc import ABC, abstractmethod
from typing import List

import structlog
from sklearn.metrics.pairwise import cosine_similarity

from codegate.inference.inference_engine import LlamaCppInferenceEngine

logger = structlog.get_logger("codegate")


class BaseCheck(ABC):
    def __init__(self, test_name: str):
        self.test_name = test_name

    @abstractmethod
    async def run_check(self, parsed_response: str, test_data: dict) -> bool:
        pass


class CheckLoader:
    @staticmethod
    def load(test_data: dict) -> List[BaseCheck]:
        test_name = test_data.get("name")
        checks = []
        if test_data.get(DistanceCheck.KEY):
            checks.append(DistanceCheck(test_name))
        if test_data.get(ContainsCheck.KEY):
            checks.append(ContainsCheck(test_name))
        if test_data.get(DoesNotContainCheck.KEY):
            checks.append(DoesNotContainCheck(test_name))

        return checks


class DistanceCheck(BaseCheck):
    KEY = "likes"

    def __init__(self, test_name: str):
        super().__init__(test_name)
        self.inference_engine = LlamaCppInferenceEngine()
        self.embedding_model = "codegate_volume/models/all-minilm-L6-v2-q5_k_m.gguf"

    async def _calculate_string_similarity(self, str1, str2):
        vector1 = await self.inference_engine.embed(self.embedding_model, [str1])
        vector2 = await self.inference_engine.embed(self.embedding_model, [str2])
        similarity = cosine_similarity(vector1, vector2)
        return similarity[0]

    async def run_check(self, parsed_response: str, test_data: dict) -> bool:
        similarity = await self._calculate_string_similarity(
            parsed_response, test_data[DistanceCheck.KEY]
        )
        if similarity < 0.8:
            logger.error(f"Test {self.test_name} failed")
            logger.error(f"Similarity: {similarity}")
            logger.error(f"Response: {parsed_response}")
            logger.error(f"Expected Response: {test_data[DistanceCheck.KEY]}")
            return False
        return True


class ContainsCheck(BaseCheck):
    KEY = "contains"

    async def run_check(self, parsed_response: str, test_data: dict) -> bool:
        if test_data[ContainsCheck.KEY].strip() not in parsed_response:
            logger.error(f"Test {self.test_name} failed")
            logger.error(f"Response: {parsed_response}")
            logger.error(f"Expected Response to contain: '{test_data[ContainsCheck.KEY]}'")
            return False
        return True


class DoesNotContainCheck(BaseCheck):
    KEY = "does_not_contain"

    async def run_check(self, parsed_response: str, test_data: dict) -> bool:
        if test_data[DoesNotContainCheck.KEY].strip() in parsed_response:
            logger.error(f"Test {self.test_name} failed")
            logger.error(f"Response: {parsed_response}")
            logger.error(
                f"Expected Response to not contain: '{test_data[DoesNotContainCheck.KEY]}'"
            )
            return False
        return True