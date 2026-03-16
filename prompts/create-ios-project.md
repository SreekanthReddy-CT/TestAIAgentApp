# iOS Project Creation Flow

**AI AGENT INSTRUCTIONS:** You are an expert iOS project generator. When the user asks to **create an iOS app / new project** (e.g., "create ios app", "new app", "generate project"), you MUST follow these exact steps in order. Do not skip any steps.

---

## 🛑 STRICT EXECUTION RULES FOR AI AGENT
1. **IMMEDIATE START:** The moment the user asks to create a project, do NOT explain what you are going to do. Do NOT summarize this document. Immediately execute Step 1 using the `AskQuestion` tool.
2. **LINEAR PROGRESSION:** You are a state machine. You must complete the current step before looking at the next. 
3. **TARGET DIRECTORY:** All generation steps default to the user's current working directory (`./`) UNLESS the user explicitly specifies a different folder in their initial prompt (e.g., "create it in ./LocalTestRun/"). If they provide a custom folder, use that as your `projectPath` for all operations.
4. **SPLIT OF RESPONSIBILITY:** The AI agent will now only handle Steps 1–4 (asking the questions and saving the spec). Step 5 (the file-level project generation) MUST be executed by running the repository's Python script (`./scripts/generate_ios_project.py`) via the terminal. Do not create or modify project files directly in Step 5 — invoke the script and relay its result.

---

## Step 1 — App Name (Use AskQuestion Tool)
Use the `AskQuestion` tool to ask the user: "What is your app name in PascalCase? (e.g., MyApp, CardGame, FinanceApp)".
**Rule:** Wait for the user's response. If the provided name ends with "App", keep it as-is. Otherwise, append "App" internally for the struct/file names later.

## Step 2 — Structured Questions (Use AskQuestion Tool)
Use the `AskQuestion` tool to sequentially ask the user the following questions to gather the project specifications. Wait for the answer to each before asking the next.

1. **Bundle ID:** Use the `AskQuestion` tool to ask: "What is your Bundle identifier? (e.g., com.company.app). You can type it, or I can use com.company.{AppName} as a default."
2. **Architecture:** Use the `AskQuestion` tool to ask: "Which architecture pattern would you like? Choose between: 1) MVVM + Builder + Router (recommended), 2) VIPER, or 3) Clean Architecture."

## Step 3 — Spec Summary & User Confirmation (Use AskQuestion Tool)
After receiving all answers, use the `AskQuestion` tool to display the full spec summary and ask for final confirmation. Use this exact text for the question prompt:

```text
Here's your project spec — ready to generate?

  App Name:      {AppName}
  Bundle ID:     {bundle_id}
  Architecture:  {architecture}

Type "yes" or "go" to start generation, or let me know if you'd like to change anything.
```

**🛑 CRITICAL:** Do NOT begin any file generation until the user confirms via the `AskQuestion` prompt (e.g., replies "yes", "go", "proceed"). If the user requests changes, update the relevant answer and re-trigger the `AskQuestion` summary.

## Step 4 — Save the Spec
Once the user confirms, immediately create a file at `./spec.md` (in the current directory) containing the finalized App Name, Bundle ID, and Architecture.

## Step 5 — Generate the Project (Run Script)
This repository includes an automated generator script that performs Steps 5.1–5.8. The AI agent MUST NOT manually edit or create project files for Step 5. Instead, run the Python generator script in the repository root:

```bash
./scripts/prepare_ios_base_project.py --name {AppName} --bundle-id {bundle_id} --dir {projectPath}
```

Requirements for the agent when executing Step 5:
- Execute the script in the repository root (so relative paths resolve).
- Capture and surface the script's stdout/stderr and exit code to the user.
- If the script exits non-zero, present the script output and stop; do NOT attempt manual fixes.
- If the script succeeds, proceed to Step 6 verification (the script also performs verification, but the agent should confirm success and report any remaining checks).

### Script semantics
- The script will copy the template contents, perform ordered replacements (BaseTemplateApp → FINAL_STRUCT_NAME, then BaseTemplate → AppName), rename files/folders, apply bundle identifier from `spec.md`, and verify there are no remaining `BaseTemplate` strings.
- The script creates backups during merge and will not leave the target directory in a partially-updated state on failure.

## Step 6 — Verification (After Script)
After the script completes successfully, verify:
1. `grep "BaseTemplate" ./{AppName}.xcodeproj/project.pbxproj` returns no matches.
2. The App entry file is correctly named `{FINAL_APP_STRUCT_NAME}.swift` and contains `struct {FINAL_APP_STRUCT_NAME}: App`.
3. Inform the user the project is ready, or surface any script-reported errors.
