# 🚀 Migration Guide: Merging `feat/fastapi-angular-migration` into `main`

The `feat/fastapi-angular-migration` branch represents a complete architectural overhaul of **Phyrexian Forge**. The application has moved away from the Streamlit monolithic architecture to a modern, decoupled stack using **Angular 19** for the frontend and **FastAPI** for the backend, while keeping the AI (Gemini) and data persistence (MongoDB) intact.

This guide provides the exact steps required to merge this branch into `main` safely.

## ⚠️ Prerequisites Before Merging
1. **Ensure working directory is clean**: Run `git status` on your branch to verify all changes are committed.
2. **Ensure tests pass**: Run the backend and frontend test suites to guarantee no regressions.
   - Backend: `poetry run pytest tests/`
   - Frontend: `cd client && npm test`
3. **Verify Configuration**: Ensure your `.env` contains valid credentials (`GEMINI_API_KEY`, `MONGO_URI`) and that `config.json` is present or auto-generated.

## Step-by-Step Merge Process

### Step 1: Checkout the `main` branch
First, switch your local environment to the `main` branch and pull the latest changes to ensure you are up to date with the remote repository.
```bash
git checkout main
git pull origin main
```

### Step 2: Merge the Feature Branch
Merge the migration branch into your local `main`. Because this is a major architectural rewrite, you may encounter merge conflicts (especially in `readme.md`, `main.py`, or `requirements.txt`).
```bash
git merge feat/fastapi-angular-migration
```

### Step 3: Resolve Merge Conflicts (If Any)
If Git reports conflicts, follow these guidelines:
- **Python / Backend Files**: Favor the changes from `feat/fastapi-angular-migration`. The old Streamlit routing logic in `main.py` should be completely replaced by the FastAPI initialization code.
- **Frontend / Client**: The entire `client/` folder is new. Accept all additions.
- **Documentation**: Favor the `readme.md` and `GEMINI.md` from the migration branch, as they detail the new Angular/FastAPI commands.
- **Dependency Files**: `pyproject.toml` and `poetry.lock` should use the migration branch versions which include `fastapi`, `uvicorn`, etc.

Once conflicts are resolved:
```bash
git add .
git commit -m "Merge branch 'feat/fastapi-angular-migration' into main"
```

### Step 4: Verify the Merged State
Before pushing to the remote repository, do a final sanity check of the application on the `main` branch.
```bash
# Start the full stack
./start.sh
```
Open `http://localhost:4200` in your browser. Verify that you can:
1. Log in / access a character.
2. View the Player Dashboard or DM Workspace.
3. Test a dice roll (verifies WebSocket connectivity).

### Step 5: Push to Remote
Once you are confident the merged `main` branch is stable, push the changes to GitHub.
```bash
git push origin main
```

### Step 6: Cleanup (Optional)
If the merge was successful and deployed, you can safely delete the migration branch to keep your repository clean.
```bash
git branch -d feat/fastapi-angular-migration
git push origin --delete feat/fastapi-angular-migration
```

## 🎉 Post-Migration Actions
- Notify your development team that the `main` branch now uses the new Angular/FastAPI architecture.
- Update any CI/CD pipelines (e.g., GitHub Actions) to include `npm install` and `npm build` steps for the frontend, and run the FastAPI server instead of Streamlit.
