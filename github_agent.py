"""
GitHub Agent for Multi-AI Book Writing System

This script provides the foundation for AI agents to interact with GitHub repositories.
It handles authentication, reading/writing files, creating branches, and managing pull requests.

Usage:
    1. Set up GitHub access token in .env file
    2. Configure the repository settings
    3. Use the GitHubAgent class methods to interact with the repository
"""

import os
import base64
import requests
from dotenv import load_dotenv
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("github_agent.log"), logging.StreamHandler()]
)
logger = logging.getLogger("github_agent")

class GitHubAgent:
    """Agent for interacting with GitHub repositories"""
    
    def __init__(self, repo_owner, repo_name, agent_name="ClaudeAgent"):
        """
        Initialize the GitHub agent
        
        Args:
            repo_owner (str): Owner of the GitHub repository
            repo_name (str): Name of the GitHub repository
            agent_name (str): Name of the agent (used for commits and PRs)
        """
        # Load environment variables
        load_dotenv()
        self.token = os.getenv("GITHUB_TOKEN")
        if not self.token:
            raise ValueError("GitHub token not found. Set GITHUB_TOKEN in .env file")
        
        # Repository information
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.agent_name = agent_name
        self.base_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}"
        self.headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        logger.info(f"Initialized {agent_name} for {repo_owner}/{repo_name}")
    
    def _make_request(self, method, endpoint, data=None, params=None):
        """Make HTTP request to GitHub API"""
        url = f"{self.base_url}{endpoint}"
        response = requests.request(
            method=method,
            url=url,
            headers=self.headers,
            json=data,
            params=params
        )
        
        # Handle rate limiting
        if response.status_code == 403 and 'X-RateLimit-Remaining' in response.headers:
            if int(response.headers['X-RateLimit-Remaining']) == 0:
                logger.warning("GitHub API rate limit reached!")
        
        response.raise_for_status()
        return response.json() if response.content else None
    
    def get_file_content(self, file_path, branch="main"):
        """
        Get the content of a file from the repository
        
        Args:
            file_path (str): Path to the file
            branch (str): Branch name
            
        Returns:
            str: Decoded content of the file
        """
        try:
            response = self._make_request(
                "GET", 
                f"/contents/{file_path}", 
                params={"ref": branch}
            )
            
            # Decode content from base64
            content = base64.b64decode(response["content"]).decode("utf-8")
            logger.info(f"Retrieved {file_path} from {branch}")
            return content
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                logger.warning(f"File {file_path} not found on branch {branch}")
                return None
            raise
    
    def create_or_update_file(self, file_path, content, commit_message, branch="main", update=False):
        """
        Create or update a file in the repository
        
        Args:
            file_path (str): Path to the file
            content (str): Content to write to the file
            commit_message (str): Commit message
            branch (str): Branch name
            update (bool): Whether to update existing file
            
        Returns:
            dict: GitHub API response
        """
        encoded_content = base64.b64encode(content.encode("utf-8")).decode("utf-8")
        data = {
            "message": commit_message,
            "content": encoded_content,
            "branch": branch,
            "committer": {
                "name": self.agent_name,
                "email": f"{self.agent_name.lower()}@example.com"
            }
        }
        
        # If updating, need the file's SHA
        if update:
            file_info = self._make_request("GET", f"/contents/{file_path}", params={"ref": branch})
            if file_info:
                data["sha"] = file_info["sha"]
        
        response = self._make_request("PUT", f"/contents/{file_path}", data=data)
        logger.info(f"{'Updated' if update else 'Created'} {file_path} on {branch}")
        return response
    
    def list_branches(self):
        """List all branches in the repository"""
        branches = self._make_request("GET", "/branches")
        return [branch["name"] for branch in branches]
    
    def create_branch(self, branch_name, base_branch="main"):
        """
        Create a new branch
        
        Args:
            branch_name (str): Name of the new branch
            base_branch (str): Name of the base branch
            
        Returns:
            dict: GitHub API response
        """
        # Get the SHA of the latest commit on the base branch
        base_ref = self._make_request("GET", f"/git/ref/heads/{base_branch}")
        base_sha = base_ref["object"]["sha"]
        
        # Create a new reference (branch)
        data = {
            "ref": f"refs/heads/{branch_name}",
            "sha": base_sha
        }
        
        try:
            response = self._make_request("POST", "/git/refs", data=data)
            logger.info(f"Created branch {branch_name} from {base_branch}")
            return response
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 422:  # Branch already exists
                logger.warning(f"Branch {branch_name} already exists")
                return None
            raise
    
    def create_pull_request(self, title, body, head_branch, base_branch="main"):
        """
        Create a pull request
        
        Args:
            title (str): Title of the pull request
            body (str): Body/description of the pull request
            head_branch (str): Name of the head branch (changes)
            base_branch (str): Name of the base branch (target)
            
        Returns:
            dict: GitHub API response with PR details
        """
        data = {
            "title": title,
            "body": body,
            "head": head_branch,
            "base": base_branch
        }
        
        response = self._make_request("POST", "/pulls", data=data)
        pr_number = response["number"]
        logger.info(f"Created PR #{pr_number}: {title}")
        return response
    
    def comment_on_pull_request(self, pr_number, comment):
        """
        Add a comment to a pull request
        
        Args:
            pr_number (int): Pull request number
            comment (str): Comment text
            
        Returns:
            dict: GitHub API response
        """
        data = {"body": comment}
        response = self._make_request("POST", f"/issues/{pr_number}/comments", data=data)
        logger.info(f"Added comment to PR #{pr_number}")
        return response
    
    def get_pull_request_comments(self, pr_number):
        """
        Get all comments on a pull request
        
        Args:
            pr_number (int): Pull request number
            
        Returns:
            list: List of comments
        """
        return self._make_request("GET", f"/issues/{pr_number}/comments")
    
    def create_file_comment(self, pr_number, file_path, comment, line_number=None):
        """
        Add a comment to a specific file in a pull request
        
        Args:
            pr_number (int): Pull request number
            file_path (str): Path to the file
            comment (str): Comment text
            line_number (int, optional): Line number to comment on
            
        Returns:
            dict: GitHub API response
        """
        # Get the pull request to get the commit ID
        pr_info = self._make_request("GET", f"/pulls/{pr_number}")
        commit_id = pr_info["head"]["sha"]
        
        data = {
            "body": comment,
            "path": file_path,
            "commit_id": commit_id,
        }
        
        if line_number:
            data["line"] = line_number
            data["side"] = "RIGHT"  # Comment on the new version
        
        response = self._make_request("POST", f"/pulls/{pr_number}/comments", data=data)
        logger.info(f"Added comment to {file_path} in PR #{pr_number}")
        return response


# Example usage
if __name__ == "__main__":
    # Example configuration
    agent = GitHubAgent(
        repo_owner="your-username",
        repo_name="math-book-project",
        agent_name="ClaudeChapterWriter"
    )
    
    # Create a new branch for a chapter
    chapter_branch = f"chapter-1-{datetime.now().strftime('%Y%m%d')}"
    agent.create_branch(chapter_branch)
    
    # Create or update a chapter file
    chapter_content = r"""
\chapter{Introduction to Abstract Algebra}

\section{Groups and Group Actions}
In this chapter, we explore the fundamental concepts of group theory...

% More LaTeX content here
    """
    
    agent.create_or_update_file(
        file_path="chapters/chapter1.tex",
        content=chapter_content,
        commit_message="Add initial version of Chapter 1",
        branch=chapter_branch
    )
    
    # Create a pull request for review
    pr = agent.create_pull_request(
        title="Chapter 1: Introduction to Abstract Algebra",
        body="This PR contains the first draft of Chapter 1. Please review the content for mathematical accuracy and pedagogical clarity.",
        head_branch=chapter_branch
    )
    
    # Example of how a reviewer agent would add comments
    pr_number = pr["number"]
    agent.comment_on_pull_request(
        pr_number,
        "I've reviewed this chapter and have some suggestions for improving the examples in section 1.2."
    )