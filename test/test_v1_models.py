from __future__ import annotations

import json
import unittest
from unittest import mock

import requests

from services.protocol import openai_v1_models


from services.personal_account_service import personal_account_service


AUTH_KEY = "chatgpt2api"
BASE_URL = "http://localhost:8000"


class ModelListTests(unittest.TestCase):
    def test_list_models_returns_exposed_models_when_accounts_exist(self):
        with (
            mock.patch.object(
                openai_v1_models.OpenAIBackendAPI,
                "list_models",
                return_value={"object": "list", "data": []},
            ),
            mock.patch.object(
                personal_account_service,
                "list_accounts",
                return_value=[
                    {"access_token": "token-free", "type": "free"},
                ],
            ),
        ):
            result = openai_v1_models.list_models()

        ids = {item["id"] for item in result["data"]}
        self.assertIn("gpt-image-2", ids)
        self.assertIn("codex-gpt-image-2", ids)
        self.assertIn("auto", ids)
        self.assertIn("gpt-5", ids)

    def test_list_models_returns_upstream_models_when_no_accounts_exist(self):
        with (
            mock.patch.object(
                openai_v1_models.OpenAIBackendAPI,
                "list_models",
                return_value={"object": "list", "data": [{"id": "upstream-model", "object": "model"}]},
            ),
            mock.patch.object(
                personal_account_service,
                "list_accounts",
                return_value=[],
            ),
        ):
            result = openai_v1_models.list_models()

        ids = {item["id"] for item in result["data"]}
        self.assertIn("upstream-model", ids)
        self.assertNotIn("codex-gpt-image-2", ids)

    def test_list_models_function(self):
        """测试直接调用服务层获取模型列表。"""
        result = openai_v1_models.list_models()
        print("function result:")
        print(json.dumps(result, ensure_ascii=False, indent=2))

    def test_list_models_http(self):
        """测试通过 HTTP 接口获取模型列表。"""
        response = requests.get(
            f"{BASE_URL}/v1/models",
            headers={"Authorization": f"Bearer {AUTH_KEY}"},
            timeout=30,
        )
        print("http status:")
        print(response.status_code)
        print("http result:")
        print(json.dumps(response.json(), ensure_ascii=False, indent=2))
