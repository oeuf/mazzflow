"""MCP Server for analyzing pull requests and generating code."""

import json
import os
from dataclasses import asdict, dataclass
from typing import Any, Dict

import openai
from dotenv import load_dotenv
from flask import Flask, jsonify, request
from github import Github
from github.GithubException import GithubException

# Load environment variables
load_dotenv()

# GitHub configuration
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
REPO_NAME = os.getenv("GITHUB_REPO")
gh = Github(GITHUB_TOKEN)
repo = gh.get_repo(REPO_NAME)

# Initialize Flask app
app = Flask(__name__)


@dataclass
class MCPContext:
    """Context for MCP operations."""

    context_type: str
    metadata: Dict[str, Any]
    content: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary.

        Returns:
            Dictionary representation of the context.
        """
        return asdict(self)


@app.route("/api/pr/analyze", methods=["POST"])
def analyze_pull_request():
    """Analyze a pull request using the MCP context."""
    data = request.json
    pr_number = data.get("pr_number")

    if not pr_number:
        return jsonify({"error": "PR number is required"}), 400

    try:
        # Get PR data from GitHub
        pr = repo.get_pull(pr_number)
        files = list(pr.get_files())

        # Build MCP context
        context = MCPContext(
            context_type="github_pull_request",
            metadata={
                "repo": REPO_NAME,
                "prNumber": pr_number,
                "author": pr.user.login,
                "createdAt": pr.created_at.isoformat(),
            },
            content={
                "title": pr.title,
                "description": pr.body,
                "changedFiles": [
                    {
                        "path": file.filename,
                        "status": file.status,
                        "additions": file.additions,
                        "deletions": file.deletions,
                        "patch": file.patch if file.patch else None,
                    }
                    for file in files
                ],
                "comments": [
                    {
                        "author": comment.user.login,
                        "text": comment.body,
                        "timestamp": comment.created_at.isoformat(),
                    }
                    for comment in pr.get_comments()
                ],
            },
        )

        # Send to LLM for analysis
        prompt = f"""
        Analyze this pull request based on the following context:
        {json.dumps(context.to_dict(), indent=2)}

        Please provide:
        1. A summary of changes
        2. Potential issues or bugs
        3. Suggestions for improvement
        4. Questions for the author
        """

        response = openai.chat.completions.create(
            model="gpt-4",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a code review assistant that analyzes "
                        "pull requests."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        )

        analysis = response.choices[0].message.content

        return jsonify({"pr_number": pr_number, "analysis": analysis})

    except GithubException as e:
        return jsonify({"error": f"GitHub API error: {e!s}"}), 500
    except Exception as e:
        return jsonify({"error": f"Server error: {e!s}"}), 500


@app.route("/api/code/generate", methods=["POST"])
def generate_code():
    """Generate code using the MCP context."""
    data = request.json
    description = data.get("description")
    file_path = data.get("file_path")

    if not description or not file_path:
        return jsonify({"error": "Description and file path are required"}), 400

    try:
        # Get existing file content if it exists
        try:
            file_content = repo.get_contents(file_path).decoded_content.decode("utf-8")
        except GithubException:
            file_content = ""

        # Build MCP context
        context = MCPContext(
            context_type="github_code_generation",
            metadata={
                "repo": REPO_NAME,
                "filePath": file_path,
                "requestedBy": "user",  # This could be dynamic based on authentication
            },
            content={
                "description": description,
                "existingCode": file_content,
                "relatedFiles": [],  # This could be populated with related files
            },
        )

        # Send to LLM for code generation
        prompt = f"""
        Generate Python code based on the following context:
        {json.dumps(context.to_dict(), indent=2)}

        Return only the code without any explanations or markdown.
        """

        response = openai.chat.completions.create(
            model="gpt-4",
            messages=[
                {
                    "role": "system",
                    "content": "You are a Python code generation assistant.",
                },
                {"role": "user", "content": prompt},
            ],
        )

        generated_code = response.choices[0].message.content

        return jsonify({"file_path": file_path, "generated_code": generated_code})

    except GithubException as e:
        return jsonify({"error": f"GitHub API error: {e!s}"}), 500
    except Exception as e:
        return jsonify({"error": f"Server error: {e!s}"}), 500


if __name__ == "__main__":
    app.run(debug=True, port=5000)
