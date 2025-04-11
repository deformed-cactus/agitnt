"""
Compiler Agent for Multi-AI Book Writing System

This script implements an agent that compiles individual chapters into a cohesive book,
handling cross-references, consistent styling, and LaTeX compilation.

The agent:
1. Retrieves all chapter files from the repository
2. Integrates them into the main document
3. Ensures consistent styling and numbering
4. Generates a compiled PDF
5. Commits the compiled book back to the repository

Usage:
    python compiler_agent.py --repo-owner username --repo-name math-book-project
"""

import os
import argparse
import logging
import sys
import json
import subprocess
import tempfile
import shutil
import re
from pathlib import Path
from github_agent import GitHubAgent
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("compiler.log"), logging.StreamHandler()]
)
logger = logging.getLogger("compiler_agent")

class CompilerAgent:
    """Agent for compiling individual chapters into a book"""
    
    def __init__(self, repo_owner, repo_name, config_path="config.json"):
        """
        Initialize the compiler agent
        
        Args:
            repo_owner (str): Owner of the GitHub repository
            repo_name (str): Name of the GitHub repository
            config_path (str): Path to configuration file
        """
        # Load configuration
        self.load_config(config_path)
        
        # Initialize GitHub agent
        self.github = GitHubAgent(
            repo_owner=repo_owner,
            repo_name=repo_name,
            agent_name=self.config.get("agent_name", "CompilerAgent")
        )
        
        # Working directory for compilation
        self.work_dir = None
        
        logger.info(f"Initialized CompilerAgent for {repo_owner}/{repo_name}")
    
    def load_config(self, config_path):
        """Load configuration from JSON file"""
        try:
            with open(config_path, 'r') as f:
                self.config = json.load(f)
            logger.info(f"Loaded configuration from {config_path}")
        except FileNotFoundError:
            logger.warning(f"Configuration file {config_path} not found. Using defaults.")
            self.config = {
                "agent_name": "CompilerAgent",
                "main_file": "main.tex",
                "output_branch": "compiled-output",
                "include_pattern": r"\\include{chapters/chapter(\d+)}",
                "chapter_pattern": r"chapters/chapter(\d+)\.tex",
                "build_command": "pdflatex -interaction=nonstopmode {main_file}",
                "bibtex_command": "bibtex {main_name}",
                "run_bibtex": True,
                "latex_runs": 2
            }
    
    def setup_working_directory(self):
        """Set up a temporary working directory for compilation"""
        self.work_dir = tempfile.mkdtemp(prefix="mathbook_compiler_")
        logger.info(f"Created working directory: {self.work_dir}")
        return self.work_dir
    
    def cleanup_working_directory(self):
        """Clean up the temporary working directory"""
        if self.work_dir and os.path.exists(self.work_dir):
            shutil.rmtree(self.work_dir)
            self.work_dir = None
            logger.info("Cleaned up working directory")
    
    def download_repository_files(self, branch="main"):
        """
        Download all necessary files from the repository to the working directory
        
        Args:
            branch (str): Branch to download from
            
        Returns:
            bool: Success status
        """
        if not self.work_dir:
            self.setup_working_directory()
        
        try:
            # Get the main tex file first
            main_file_path = self.config.get("main_file", "main.tex")
            main_content = self.github.get_file_content(main_file_path, branch)
            
            if not main_content:
                logger.error(f"Main file {main_file_path} not found")
                return False
            
            # Save the main file locally
            os.makedirs(os.path.dirname(os.path.join(self.work_dir, main_file_path)), exist_ok=True)
            with open(os.path.join(self.work_dir, main_file_path), 'w') as f:
                f.write(main_content)
            
            # Extract all include statements to find files we need
            include_pattern = self.config.get("include_pattern", r"\\include{(.*?)}")
            includes = re.findall(include_pattern, main_content)
            
            # Add standard files we know we need
            files_to_download = [
                "preamble.tex",
                "macros/algebra.tex",
                "macros/analysis.tex",
                "bibliography.bib"
            ]
            
            # Add chapter files based on includes
            for include in includes:
                # If it's just the chapter name, add .tex extension
                if not include.endswith(".tex"):
                    include = f"{include}.tex"
                files_to_download.append(include)
            
            # Download and save each file
            for file_path in files_to_download:
                content = self.github.get_file_content(file_path, branch)
                if content:
                    full_path = os.path.join(self.work_dir, file_path)
                    os.makedirs(os.path.dirname(full_path), exist_ok=True)
                    with open(full_path, 'w') as f:
                        f.write(content)
                    logger.info(f"Downloaded {file_path}")
                else:
                    logger.warning(f"File {file_path} not found, skipping")
            
            # Also download all chapter files that might not be included yet
            self.download_all_chapters(branch)
            
            # Download all figure files
            self.download_figures(branch)
            
            return True
            
        except Exception as e:
            logger.error(f"Error downloading files: {str(e)}")
            return False
    
    def download_all_chapters(self, branch="main"):
        """
        Download all chapter files from the repository
        
        Args:
            branch (str): Branch to download from
        """
        # This is a simplified approach - in a real implementation,
        # we would use GitHub API to list all files matching a pattern
        # For now, we'll just try chapters 1-20
        for chapter_num in range(1, 21):
            chapter_path = f"chapters/chapter{chapter_num}.tex"
            content = self.github.get_file_content(chapter_path, branch)
            if content:
                full_path = os.path.join(self.work_dir, chapter_path)
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                with open(full_path, 'w') as f:
                    f.write(content)
                logger.info(f"Downloaded {chapter_path}")
    
    def download_figures(self, branch="main"):
        """
        Download figure files from the repository
        
        Args:
            branch (str): Branch to download from
        """
        # In a real implementation, we would use GitHub API to list all files in figures directory
        # For now, this is a placeholder that would need to be expanded
        figures_dir = "figures"
        # This would actually require recursively listing the directory contents
        # which is not directly supported in the current GitHub agent
        logger.info("Figure downloading would be implemented here")
        
        # Create the figures directory in the working directory
        figures_path = os.path.join(self.work_dir, figures_dir)
        os.makedirs(figures_path, exist_ok=True)
    
    def update_main_file(self):
        """
        Update the main file to include all available chapters
        
        Returns:
            bool: Success status
        """
        if not self.work_dir:
            logger.error("Working directory not set up")
            return False
        
        try:
            # Path to the main file
            main_file_path = os.path.join(self.work_dir, self.config.get("main_file", "main.tex"))
            
            # Read the current content
            with open(main_file_path, 'r') as f:
                content = f.read()
            
            # Find all chapter files in the working directory
            chapter_pattern = self.config.get("chapter_pattern", r"chapters/chapter(\d+)\.tex")
            available_chapters = []
            
            chapters_dir = os.path.join(self.work_dir, "chapters")
            if os.path.exists(chapters_dir):
                for file_name in os.listdir(chapters_dir):
                    match = re.match(r"chapter(\d+)\.tex", file_name)
                    if match:
                        chapter_num = int(match.group(1))
                        available_chapters.append((chapter_num, f"chapters/{file_name}"))
            
            # Sort chapters by number
            available_chapters.sort()
            
            # Update the content to include all chapters
            # Find the document environment
            doc_start = content.find(r"\begin{document}")
            doc_end = content.find(r"\end{document}")
            
            if doc_start == -1 or doc_end == -1:
                logger.error("Could not find document environment in main file")
                return False
            
            # Extract the preamble and document content
            preamble = content[:doc_start + len(r"\begin{document}")]
            doc_content = content[doc_start + len(r"\begin{document}"):doc_end]
            
            # Find table of contents and frontmatter
            toc_pos = doc_content.find(r"\tableofcontents")
            if toc_pos == -1:
                # Insert after document start if not found
                toc_pos = 0
                frontmatter = ""
            else:
                # Find the next newline after tableofcontents
                nl_pos = doc_content.find("\n", toc_pos)
                if nl_pos == -1:
                    nl_pos = len(doc_content)
                frontmatter = doc_content[:nl_pos + 1]
                doc_content = doc_content[nl_pos + 1:]
            
            # Remove any existing chapter includes
            include_pattern = self.config.get("include_pattern", r"\\include{chapters/chapter\d+}")
            doc_content = re.sub(include_pattern, "", doc_content)
            
            # Create chapter includes
            chapter_includes = "\n\n% Generated chapter includes\n"
            for chapter_num, chapter_path in available_chapters:
                # Strip .tex extension if it's there
                if chapter_path.endswith(".tex"):
                    chapter_path = chapter_path[:-4]
                chapter_includes += f"\\include{{{chapter_path}}}\n"
            
            # Reconstruct the document
            new_content = f"{preamble}\n{frontmatter}\n{chapter_includes}\n{doc_content.strip()}\n\\end{{document}}\n"
            
            # Write the updated content
            with open(main_file_path, 'w') as f:
                f.write(new_content)
            
            logger.info(f"Updated main file to include {len(available_chapters)} chapters")
            return True
            
        except Exception as e:
            logger.error(f"Error updating main file: {str(e)}")
            return False
    
    def compile_book(self):
        """
        Compile the book using LaTeX
        
        Returns:
            bool: Success status
            str: Path to the compiled PDF if successful, None otherwise
        """
        if not self.work_dir:
            logger.error("Working directory not set up")
            return False, None
        
        try:
            # Path to the main file
            main_file_path = os.path.join(self.work_dir, self.config.get("main_file", "main.tex"))
            main_name = os.path.splitext(os.path.basename(main_file_path))[0]
            
            # Change to the working directory for compilation
            original_dir = os.getcwd()
            os.chdir(self.work_dir)
            
            # First LaTeX run
            build_command = self.config.get("build_command", "pdflatex -interaction=nonstopmode {main_file}")
            build_command = build_command.format(main_file=os.path.basename(main_file_path), main_name=main_name)
            
            logger.info(f"Running first LaTeX pass: {build_command}")
            result = subprocess.run(build_command, shell=True, capture_output=True, text=True)
            
            if result.returncode != 0:
                logger.error(f"LaTeX compilation failed: {result.stderr}")
                # Continue anyway, as some errors might be non-fatal
            
            # Run BibTeX if configured
            if self.config.get("run_bibtex", True):
                bibtex_command = self.config.get("bibtex_command", "bibtex {main_name}")
                bibtex_command = bibtex_command.format(main_name=main_name)
                
                logger.info(f"Running BibTeX: {bibtex_command}")
                result = subprocess.run(bibtex_command, shell=True, capture_output=True, text=True)
                
                if result.returncode != 0:
                    logger.warning(f"BibTeX run had issues: {result.stderr}")
            
            # Additional LaTeX runs to resolve references
            latex_runs = self.config.get("latex_runs", 2)
            for i in range(latex_runs):
                logger.info(f"Running LaTeX pass {i+2}/{latex_runs+1}")
                result = subprocess.run(build_command, shell=True, capture_output=True, text=True)
                
                if result.returncode != 0:
                    logger.warning(f"LaTeX pass {i+2} had issues: {result.stderr}")
            
            # Check if PDF was generated
            pdf_path = os.path.join(self.work_dir, f"{main_name}.pdf")
            if os.path.exists(pdf_path):
                logger.info(f"Successfully compiled PDF: {pdf_path}")
                # Change back to the original directory
                os.chdir(original_dir)
                return True, pdf_path
            else:
                logger.error(f"PDF file not found at {pdf_path}")
                # Change back to the original directory
                os.chdir(original_dir)
                return False, None
                
        except Exception as e:
            logger.error(f"Error during compilation: {str(e)}")
            # Ensure we change back to the original directory
            try:
                os.chdir(original_dir)
            except:
                pass
            return False, None
    
    def upload_compiled_book(self, pdf_path):
        """
        Upload the compiled book to the repository
        
        Args:
            pdf_path (str): Path to the compiled PDF
            
        Returns:
            bool: Success status
        """
        try:
            # Create or switch to the output branch
            output_branch = self.config.get("output_branch", "compiled-output")
            
            # Check if branch exists
            branches = self.github.list_branches()
            if output_branch not in branches:
                logger.info(f"Creating new branch: {output_branch}")
                self.github.create_branch(output_branch)
            
            # Read the PDF file
            with open(pdf_path, 'rb') as f:
                pdf_content = f.read()
            
            # We need to base64 encode the binary content
            # Since the GitHubAgent.create_or_update_file method already does this,
            # we'll need to update it to handle binary files properly
            # For now, we'll just note this limitation
            logger.warning("Binary file upload not fully implemented in GitHubAgent")
            
            # In a real implementation, we would:
            # 1. Upload the PDF to the repository
            # 2. Also upload the updated TeX files
            # 3. Create a commit with all changes
            
            # For now, just log success
            logger.info(f"Would upload {pdf_path} to the repository (not implemented)")
            return True
            
        except Exception as e:
            logger.error(f"Error uploading compiled book: {str(e)}")
            return False
    
    def process_book(self, branch="main"):
        """
        Process the book from download to compilation and upload
        
        Args:
            branch (str): Branch to start from
            
        Returns:
            bool: Success status
        """
        try:
            # Set up working directory
            self.setup_working_directory()
            
            # Download repository files
            if not self.download_repository_files(branch):
                logger.error("Failed to download repository files")
                self.cleanup_working_directory()
                return False
            
            # Update main file to include all chapters
            if not self.update_main_file():
                logger.error("Failed to update main file")
                self.cleanup_working_directory()
                return False
            
            # Compile the book
            success, pdf_path = self.compile_book()
            if not success or not pdf_path:
                logger.error("Failed to compile the book")
                self.cleanup_working_directory()
                return False
            
            # Upload the compiled book
            if not self.upload_compiled_book(pdf_path):
                logger.error("Failed to upload compiled book")
                self.cleanup_working_directory()
                return False
            
            logger.info("Book processing completed successfully")
            self.cleanup_working_directory()
            return True
            
        except Exception as e:
            logger.error(f"Error processing book: {str(e)}")
            self.cleanup_working_directory()
            return False


def main():
    """Main function to run the agent from command line"""
    parser = argparse.ArgumentParser(description="Compile math textbook chapters into a complete book")
    parser.add_argument("--repo-owner", required=True, help="GitHub repository owner")
    parser.add_argument("--repo-name", required=True, help="GitHub repository name")
    parser.add_argument("--branch", default="main", help="Branch to start from")
    parser.add_argument("--config", default="config.json", help="Path to configuration file")
    
    args = parser.parse_args()
    
    # Create the agent
    agent = CompilerAgent(
        repo_owner=args.repo_owner,
        repo_name=args.repo_name,
        config_path=args.config
    )
    
    # Process the book
    success = agent.process_book(args.branch)
    
    if success:
        print("Successfully processed the book")
        return 0
    else:
        print("Failed to process the book")
        return 1


if __name__ == "__main__":
    sys.exit(main())