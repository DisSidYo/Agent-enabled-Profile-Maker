import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi import HTTPException
from fastapi.testclient import TestClient

from app import _parse_model_result, app
from agent.loop import run_agent
from agent.tools import list_changed_files, read_git_diff


class AppTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_health_check(self) -> None:
        response = self.client.get("/api/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_serves_built_react_ui(self) -> None:
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Proofpoint", response.text)

    def test_repo_endpoint_reports_local_git_checkout(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            subprocess.run(["git", "init", str(repo_path)], check=True, capture_output=True)
            subprocess.run(
                ["git", "-C", str(repo_path), "config", "user.email", "test@example.com"],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "-C", str(repo_path), "config", "user.name", "Test User"],
                check=True,
                capture_output=True,
            )
            (repo_path / "README.md").write_text("test repo\n", encoding="utf-8")
            subprocess.run(
                ["git", "-C", str(repo_path), "add", "README.md"],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "-C", str(repo_path), "commit", "-m", "initial"],
                check=True,
                capture_output=True,
            )

            response = self.client.post("/api/repo", json={"repo_path": str(repo_path)})

        self.assertEqual(response.status_code, 200)
        self.assertIn(response.json()["branch"], {"main", "master"})
        self.assertEqual(response.json()["working_tree"], "clean")

    def test_generate_rejects_invalid_git_ref_before_model_call(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            subprocess.run(["git", "init", str(repo_path)], check=True, capture_output=True)
            subprocess.run(
                ["git", "-C", str(repo_path), "config", "user.email", "test@example.com"],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "-C", str(repo_path), "config", "user.name", "Test User"],
                check=True,
                capture_output=True,
            )
            (repo_path / "README.md").write_text("test repo\n", encoding="utf-8")
            subprocess.run(
                ["git", "-C", str(repo_path), "add", "README.md"],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "-C", str(repo_path), "commit", "-m", "initial"],
                check=True,
                capture_output=True,
            )

            response = self.client.post(
                "/api/generate",
                json={
                    "repo_path": str(repo_path),
                    "prompt": "Keep the bullets specific and accurate.",
                    "roles": ["Software Engineering"],
                    "base": "--upload-pack=malicious",
                    "head": "HEAD",
                },
            )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Invalid Git ref", response.json()["detail"])

    def test_model_response_is_limited_to_requested_roles(self) -> None:
        model_output = {
            "resume_bullets": [
                {"role": "Software Engineering", "text": "Built a verified feature."},
                {"role": "Consulting", "text": "Should be excluded."},
            ],
            "github_summary": "A verified project summary.",
            "website_copy": "A verified portfolio summary.",
            "linkedin_summary": "",
            "linkedin_post": "",
            "checklist": ["Verify the claim."],
            "evidence_notes": ["Only the code change is confirmed."],
        }

        parsed = _parse_model_result(
            {"result": json.dumps(model_output)},
            ["Software Engineering"],
        )

        self.assertEqual(
            parsed["resume_bullets"],
            [{"role": "Software Engineering", "text": "Built a verified feature."}],
        )
        self.assertEqual(parsed["checklist"], ["Verify the claim."])
        self.assertEqual(parsed["website_copy"], "A verified portfolio summary.")

    def test_model_response_without_checklist_is_rejected(self) -> None:
        with self.assertRaises(HTTPException) as raised:
            _parse_model_result(
                {
                    "result": json.dumps({
                        "resume_bullets": [],
                        "checklist": [],
                        "evidence_notes": [],
                    })
                },
                ["AI / ML"],
            )

        self.assertEqual(raised.exception.status_code, 502)

    def test_sensitive_files_are_excluded_from_agent_git_tools(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            subprocess.run(["git", "init", str(repo_path)], check=True, capture_output=True)
            subprocess.run(
                ["git", "-C", str(repo_path), "config", "user.email", "test@example.com"],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "-C", str(repo_path), "config", "user.name", "Test User"],
                check=True,
                capture_output=True,
            )
            (repo_path / "README.md").write_text("first version\n", encoding="utf-8")
            (repo_path / ".env").write_text("API_TOKEN=should-not-leak\n", encoding="utf-8")
            subprocess.run(
                ["git", "-C", str(repo_path), "add", "-f", "README.md", ".env"],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "-C", str(repo_path), "commit", "-m", "initial"],
                check=True,
                capture_output=True,
            )
            (repo_path / "README.md").write_text("second version\n", encoding="utf-8")
            (repo_path / ".env").write_text("API_TOKEN=another-secret\n", encoding="utf-8")
            subprocess.run(
                ["git", "-C", str(repo_path), "add", "README.md", ".env"],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "-C", str(repo_path), "commit", "-m", "update"],
                check=True,
                capture_output=True,
            )

            changed_files = list_changed_files("HEAD~1", "HEAD", str(repo_path))
            diff = read_git_diff("HEAD~1", "HEAD", str(repo_path))

        self.assertEqual(changed_files, "README.md")
        self.assertIn("second version", diff)
        self.assertNotIn("should-not-leak", diff)
        self.assertNotIn("another-secret", diff)

    def test_agent_tools_are_locked_to_the_selected_repo_and_refs(self) -> None:
        tool_call = SimpleNamespace(
            id="call-1",
            function=SimpleNamespace(
                name="read_git_diff",
                arguments=json.dumps({
                    "base": "OTHER~1",
                    "head": "OTHER",
                    "repo_path": "C:\\private\\unselected-repo",
                }),
            ),
        )
        tool_message = SimpleNamespace(
            tool_calls=[tool_call],
            content=None,
            model_dump=Mock(return_value={"role": "assistant"}),
        )
        final_message = SimpleNamespace(
            tool_calls=[],
            content='{"resume_bullets":[]}',
            model_dump=Mock(return_value={"role": "assistant", "content": "{}"}),
        )
        responses = [
            SimpleNamespace(choices=[SimpleNamespace(message=tool_message)]),
            SimpleNamespace(choices=[SimpleNamespace(message=final_message)]),
        ]
        fake_client = SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(create=Mock(side_effect=responses))
            )
        )
        tool_function = Mock(return_value="safe diff")

        with patch("agent.loop._client", return_value=fake_client), patch.dict(
            "agent.loop.TOOL_FUNCTIONS",
            {"read_git_diff": tool_function},
        ):
            output = run_agent(
                "task",
                repo_path="C:\\selected\\repo",
                base_ref="SELECTED_BASE",
                head_ref="SELECTED_HEAD",
            )

        tool_function.assert_called_once_with(
            base="SELECTED_BASE",
            head="SELECTED_HEAD",
            repo_path="C:\\selected\\repo",
        )
        self.assertEqual(output["result"], '{"resume_bullets":[]}')


if __name__ == "__main__":
    unittest.main()
