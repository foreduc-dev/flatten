#!/bin/bash
# Script to automatically add, commit, and push changes with user confirmation

# Stage all changes
git add -A

# Prompt for commit message
read -p "Enter commit message: " COMMIT_MSG
if [ -z "$COMMIT_MSG" ]; then
  echo "Commit message cannot be empty. Aborting."
  exit 1
fi

# Confirm before committing and pushing
read -p "Proceed with commit and push? (y/n): " CONFIRM
if [ "$CONFIRM" != "y" ]; then
  echo "Operation cancelled."
  exit 0
fi

# Commit and push
git commit -m "$COMMIT_MSG"
if [ $? -ne 0 ]; then
  echo "Commit failed. Aborting push."
  exit 1
fi

git push
if [ $? -ne 0 ]; then
  echo "Push failed."
  exit 1
fi

echo "Changes have been pushed successfully."
