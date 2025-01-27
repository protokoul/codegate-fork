import json

import structlog
from fastapi import HTTPException, Request

from codegate.pipeline.factory import PipelineFactory
from codegate.providers.base import BaseProvider
from codegate.providers.llamacpp.completion_handler import LlamaCppCompletionHandler
from codegate.providers.llamacpp.normalizer import LLamaCppInputNormalizer, LLamaCppOutputNormalizer


class LlamaCppProvider(BaseProvider):
    def __init__(
        self,
        pipeline_factory: PipelineFactory,
    ):
        completion_handler = LlamaCppCompletionHandler()
        super().__init__(
            LLamaCppInputNormalizer(),
            LLamaCppOutputNormalizer(),
            completion_handler,
            pipeline_factory,
        )

    @property
    def provider_route_name(self) -> str:
        return "llamacpp"

    def _setup_routes(self):
        """
        Sets up the /completions and /chat/completions routes for the
        provider as expected by the Llama API.
        """

        @self.router.post(f"/{self.provider_route_name}/completions")
        @self.router.post(f"/{self.provider_route_name}/chat/completions")
        async def create_completion(
            request: Request,
        ):
            body = await request.body()
            data = json.loads(body)
            logger = structlog.get_logger("codegate")

            is_fim_request = self._is_fim_request(request, data)
            try:
                stream = await self.complete(data, None, is_fim_request=is_fim_request)
            except RuntimeError as e:
                # propagate as error 500
                logger.error("Error in LlamaCppProvider completion", error=str(e))
                raise HTTPException(status_code=500, detail=str(e))
            except ValueError as e:
                # capture well known exceptions
                logger.error("Error in LlamaCppProvider completion", error=str(e))
                if str(e).startswith("Model path does not exist") or str(e).startswith(
                    "No file found"
                ):
                    raise HTTPException(status_code=404, detail=str(e))
                elif "exceed" in str(e):
                    raise HTTPException(status_code=429, detail=str(e))
                else:
                    # just continue raising the exception
                    raise e
            return self._completion_handler.create_response(stream)
