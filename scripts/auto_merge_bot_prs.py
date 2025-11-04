"""
Auto-merge pre-commit and dependabot PRs across selected
public repositories. This script checks specified
repositories for a given GitHub user and automatically
merges open pull requests from pre-commit.ci and
dependabot if they pass all CI checks and have no merge
conflicts.
"""

import json
import os
import time
from pathlib import Path

from github import Github, GithubException


def should_auto_merge(pr):
    """
    Check if a PR should be auto-merged.

    Parameters
    ----------
    pr : PullRequest
        GitHub pull request object.

    Returns
    -------
    should_merge : bool
        Whether the PR should be auto-merged.
    reason : str
        Reason for the decision.

    """
    # check if PR is from pre-commit.ci or dependabot
    author = pr.user.login.lower()
    if author not in [
        "pre-commit-ci[bot]",
        "dependabot[bot]",
        "dependabot",
        "dependabot-preview[bot]",
    ]:
        return False, f"Author {author} is not a bot we auto-merge."

    # check if PR is mergeable (no conflicts)
    if not pr.mergeable:
        return False, "PR has merge conflicts."

    # check if all status checks and check runs pass
    commit = pr.get_commits().reversed[0]

    # check status API (older CI systems)
    combined_status = commit.get_combined_status()
    has_statuses = combined_status.total_count > 0

    # check runs API (GitHub Actions)
    check_runs = commit.get_check_runs()
    has_check_runs = check_runs.totalCount > 0

    # if no checks at all, allow merge
    if not has_statuses and not has_check_runs:
        return True, "No CI checks configured, proceeding."

    # check status API results
    if has_statuses and combined_status.state != "success":
        return False, f"Status checks: {combined_status.state}."

    # check runs API results
    if has_check_runs:
        for check_run in check_runs:
            # only consider required checks
            if check_run.status != "completed":
                return (
                    False,
                    (
                        f"Check run '{check_run.name}' not completed: "
                        f"{check_run.status}."
                    ),
                )
            if check_run.conclusion not in ["success", "neutral", "skipped"]:
                return (
                    False,
                    (
                        f"Check run '{check_run.name}' failed: "
                        f"{check_run.conclusion}."
                    ),
                )

    return True, "All checks passed."


def auto_merge_repo_prs(repo):
    """
    Auto-merge eligible PRs in a repository.

    Parameters
    ----------
    repo : Repository
        GitHub repository object.

    Returns
    -------
    list[dict]
        List of merge results containing repo, PR number, status, and message.
    """
    results = []
    try:
        prs = repo.get_pulls(state="open")

        for pr in prs:
            should_merge, reason = should_auto_merge(pr)

            if should_merge:
                try:
                    pr.merge(
                        merge_method="squash",
                        commit_title=f"{pr.title}",
                        commit_message=(
                            "Auto-merged by auto-merge workflow."
                            f"\n\n{pr.body or ''}"
                        ),
                    )
                    results.append(
                        {
                            "repo": repo.full_name,
                            "pr": pr.number,
                            "status": "merged",
                            "message": (
                                "Successfully merged PR "
                                f"#{pr.number}: {pr.title}."
                            ),
                        }
                    )
                    print(
                        f"Merged {repo.full_name} PR #{pr.number}: {pr.title}."
                    )
                except GithubException as e:
                    results.append(
                        {
                            "repo": repo.full_name,
                            "pr": pr.number,
                            "status": "failed",
                            "message": f"Failed to merge: {str(e)}.",
                        }
                    )
                    print(
                        f"Failed to merge {repo.full_name} PR "
                        f"#{pr.number}: {str(e)}."
                    )
            else:
                print(f"Skipped {repo.full_name} PR #{pr.number}: {reason}")

    except GithubException as e:
        print(f"Error accessing {repo.full_name}: {str(e)}.")

    return results


def load_repositories_config(config_path="config/repositories.json"):
    """
    Load the list of repositories to check from a config file.

    Parameters
    ----------
    config_path : str
        Path to the configuration file.

    Returns
    -------
    list[str]
        List of repository names.
    """
    config_file = Path(config_path)

    if not config_file.exists():
        print(f"Warning: Config file {config_path} not found.")
        print(
            "Please create a repositories.json file in the config folder "
            "with the list of repositories to target."
        )
        return []

    try:
        with open(config_file) as f:
            config = json.load(f)
            return config.get("repositories", [])
    except json.JSONDecodeError as e:
        print(f"Error parsing {config_path}: {e}.")
        return []


def main():
    """
    Main execution function.

    Returns
    -------
    int
        Exit code (0 for success, 1 for error).
    """
    token = os.environ.get("GITHUB_TOKEN")
    username = os.environ.get("GITHUB_USERNAME")

    if not token:
        print("Error: GITHUB_TOKEN not set.")
        return 1

    repo_names = load_repositories_config()

    if not repo_names:
        print("No repositories configured. Exiting.")
        return 1

    g = Github(token)

    print(f"Checking {len(repo_names)} repositories...")
    print("=" * 60)

    all_results = []

    for repo_name in repo_names:
        # handle both "owner/repo" and "repo" formats
        if "/" not in repo_name:
            full_repo_name = f"{username}/{repo_name}"
        else:
            full_repo_name = repo_name

        try:
            repo = g.get_repo(full_repo_name)

            if repo.archived:
                print(f"\nSkipping archived repository: {full_repo_name}.")
                continue

            print(f"\nChecking {full_repo_name}...")
            results = auto_merge_repo_prs(repo)
            all_results.extend(results)

        except GithubException as e:
            print(f"Error accessing {full_repo_name}: {str(e)}.")

        # rate limit protection
        time.sleep(1)

    print("\n" + "=" * 60)
    print("Summary:")
    merged_count = sum(1 for r in all_results if r["status"] == "merged")
    failed_count = sum(1 for r in all_results if r["status"] == "failed")
    print(f"Total merged: {merged_count}")
    print(f"Total failed: {failed_count}")

    if failed_count > 0:
        print("\nFailed merges:")
        for r in all_results:
            if r["status"] == "failed":
                print(f"  - {r['repo']} PR #{r['pr']}: {r['message']}")

    return 0


if __name__ == "__main__":
    exit(main())
